using System.Diagnostics;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

sealed class PdfProcessingService(IServiceScopeFactory scopes, StoragePaths paths, IConfiguration config, IWebHostEnvironment environment, ILogger<PdfProcessingService> logger) : BackgroundService {
    protected override async Task ExecuteAsync(CancellationToken stop) {
        using (var scope = scopes.CreateScope()) {
            var db = scope.ServiceProvider.GetRequiredService<PortalDb>();
            // Outputs from interrupted attempts are retained. Retry creates a new version.
            foreach (var j in await db.Jobs.Where(j => j.Status == "Running").ToListAsync(stop)) { j.Status = "Failed"; j.Error = "Service restarted during processing. Start a new attempt."; j.FinishedUtc = DateTime.UtcNow; }
            await db.SaveChangesAsync(stop);
        }
        while (!stop.IsCancellationRequested) {
            try {
                using var scope = scopes.CreateScope(); var db = scope.ServiceProvider.GetRequiredService<PortalDb>();
                var job = await db.Jobs.Where(j => j.Status == "Queued").OrderBy(j => j.CreatedUtc).FirstOrDefaultAsync(stop);
                if (job is null) { await Task.Delay(2000, stop); continue; }
                await Process(job, db, stop);
            } catch (OperationCanceledException) when (stop.IsCancellationRequested) { break; }
            catch (Exception ex) { logger.LogError(ex, "PDF worker queue error"); await Task.Delay(3000, stop); }
        }
    }
    private async Task Process(ProcessingJob job, PortalDb db, CancellationToken stop) {
        var doc = await db.Documents.FindAsync([job.DocumentId], stop);
        if (doc is null) return;
        job.Status = "Running"; job.Stage = "Starting PDF worker"; await db.SaveChangesAsync(stop);
        var repo = Path.GetFullPath(Path.Combine(environment.ContentRootPath, ".."));
        var python = config["Processing:Python"] ?? Path.Combine(repo, ".venv", OperatingSystem.IsWindows() ? "Scripts/python.exe" : "bin/python");
        var script = config["Processing:Script"] ?? Path.Combine(repo, "worker", "pipeline.py");
        var output = Path.Combine(paths.Root, "jobs", job.Id);
        Directory.CreateDirectory(Path.Combine(paths.Root, "jobs"));
        using var process = new Process();
        process.StartInfo = new ProcessStartInfo(python) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true, WorkingDirectory = repo };
        foreach (var arg in new[] { "-u", script, "--pdf", paths.Pdf(doc.Id), "--output", output }) process.StartInfo.ArgumentList.Add(arg);
        process.StartInfo.Environment["PYTHONUTF8"] = "1";
        // Do not hand administrator bootstrap secrets to parsing subprocesses.
        process.StartInfo.Environment.Remove("Saas__AdminPassword");
        process.StartInfo.Environment.Remove("PTS_DATABASE_URL");
        process.StartInfo.Environment.Remove("Supabase__DatabaseUrl");
        process.StartInfo.Environment.Remove("OPENAI_API_KEY");
        process.StartInfo.Environment.Remove("OpenAI__ApiKey");
        string stage = "Starting PDF worker"; int current = 0, total = 0;
        var errors = new System.Text.StringBuilder();
        try {
            process.Start();
            var readOut = Task.Run(async () => {
                while (await process.StandardOutput.ReadLineAsync() is { } line) {
                    if (line.Length > 4000) continue;
                    try { using var json = JsonDocument.Parse(line); var root = json.RootElement; stage = root.GetProperty("stage").GetString() ?? stage; current = root.GetProperty("current").GetInt32(); total = root.GetProperty("total").GetInt32(); } catch (JsonException) { } catch (KeyNotFoundException) { }
                }
            });
            var readErr = Task.Run(async () => { while (await process.StandardError.ReadLineAsync() is { } line) if (errors.Length < 16000) errors.AppendLine(line); });
            var start = Stopwatch.StartNew();
            while (!process.HasExited) {
                await Task.Delay(750, stop); await db.Entry(job).ReloadAsync(stop);
                process.Refresh();
                if (process.HasExited) break;
                long workingSet;
                try { workingSet = process.WorkingSet64; }
                catch (InvalidOperationException) when (process.HasExited) { break; }
                if (job.CancelRequested || start.Elapsed > TimeSpan.FromMinutes(60) || workingSet > 2_000_000_000) {
                    process.Kill(true); await process.WaitForExitAsync(CancellationToken.None);
                    job.Status = job.CancelRequested ? "Cancelled" : "Failed"; job.Error = job.CancelRequested ? null : "Worker exceeded its time or memory limit."; break;
                }
                job.Stage = stage.Length > 160 ? stage[..160] : stage; job.Current = Math.Max(0,current); job.Total = Math.Max(0,total); await db.SaveChangesAsync(stop);
            }
            await process.WaitForExitAsync(stop); await Task.WhenAll(readOut,readErr);
            if (job.Status == "Running") {
                job.Status = process.ExitCode == 0 && File.Exists(Path.Combine(output,"manifest.json")) ? "NeedsReview" : "Failed";
                job.Error = job.Status == "Failed" ? "PDF extraction failed. The original PDF is preserved; administrator diagnostics are available locally." : null;
            }
            if (errors.Length > 0) await File.WriteAllTextAsync(Path.Combine(paths.Root,"jobs",job.Id+".log"),errors.ToString(),stop);
        } catch (OperationCanceledException) when (stop.IsCancellationRequested) {
            if (process.Id > 0 && !process.HasExited) process.Kill(true);
            throw;
        } catch (Exception ex) {
            try { if (!process.HasExited) process.Kill(true); } catch (InvalidOperationException) { }
            logger.LogError(ex,"PDF job {JobId} failed",job.Id);job.Status="Failed";job.Error="Worker could not process this PDF. Check the installed Python environment and server logs.";
        }
        job.Stage=job.Status;job.FinishedUtc=DateTime.UtcNow;doc.Status=job.Status=="NeedsReview"?"PDF context ready · extracted facts require review":job.Status;
        await db.SaveChangesAsync(stop);
    }
}
