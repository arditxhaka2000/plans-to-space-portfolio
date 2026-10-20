using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.EntityFrameworkCore;

sealed class RecipeBuild {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string DocumentId { get; set; } = "";
    public string RecipeHash { get; set; } = "";
    public string DocumentHash { get; set; } = "";
    public string GeneratorVersion { get; set; } = RecipeWorkflow.Version;
    public string Actor { get; set; } = "";
    public string? ParentId { get; set; }
    public string? RevisionId { get; set; }
    public string Status { get; set; } = "Queued";
    public string? Error { get; set; }
    public DateTime CreatedUtc { get; set; } = DateTime.UtcNow;
    public DateTime? FinishedUtc { get; set; }
}

static class RecipeWorkflow {
    public const string Version="recipe-1.1.0";
    public const string InterpreterVersion="drawing-interpreter-1.0.1";
    public static bool IsAutomatic(RecipeBuild job)=>job.RecipeHash.StartsWith("pdf:drawing-interpreter-",StringComparison.Ordinal);
    static readonly SemaphoreSlim Gate=new(1,1);
    public static string Folder(StoragePaths paths,string id)=>Path.Combine(paths.Root,"recipe-builds",id);
    public static async Task<RecipeBuild> QueueAutomatic(ProjectDocument doc,string actor,PortalDb db,StoragePaths paths){
        await Gate.WaitAsync();try{
            var key="pdf:"+InterpreterVersion;
            var previous=await db.RecipeBuilds.FirstOrDefaultAsync(j=>j.DocumentId==doc.Id&&j.DocumentHash==doc.Sha256&&j.RecipeHash==key&&j.GeneratorVersion==Version);
            if(previous!=null)return previous;
            var job=new RecipeBuild{DocumentId=doc.Id,DocumentHash=doc.Sha256,RecipeHash=key,Actor=actor};
            Directory.CreateDirectory(Folder(paths,job.Id));db.RecipeBuilds.Add(job);await db.SaveChangesAsync();return job;
        }finally{Gate.Release();}
    }
    public static async Task Ensure(PortalDb db)=>await db.Database.ExecuteSqlRawAsync("""
        CREATE TABLE IF NOT EXISTS RecipeBuilds (
        Id TEXT PRIMARY KEY NOT NULL, DocumentId TEXT NOT NULL REFERENCES Documents(Id),
        RecipeHash TEXT NOT NULL, DocumentHash TEXT NOT NULL, GeneratorVersion TEXT NOT NULL,
        Actor TEXT NOT NULL, ParentId TEXT NULL, RevisionId TEXT NULL,
        Status TEXT NOT NULL, Error TEXT NULL, CreatedUtc TEXT NOT NULL, FinishedUtc TEXT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS IX_RecipeBuilds_Key ON RecipeBuilds(DocumentId,DocumentHash,RecipeHash,GeneratorVersion);
        """);
    static JsonNode? Canonical(JsonNode? n)=>n switch {
        JsonObject o=>new JsonObject(o.OrderBy(p=>p.Key,StringComparer.Ordinal).Select(p=>new KeyValuePair<string,JsonNode?>(p.Key,Canonical(p.Value)))),
        JsonArray a=>new JsonArray(a.Select(Canonical).ToArray()), _=>n?.DeepClone()
    };
    static async Task<IResult> Queue(string documentId,JsonNode recipe,string? parentId,HttpContext c,PortalDb db,StoragePaths paths){
        var doc=await db.Documents.FindAsync(documentId);
        if(doc==null||!await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
        if(recipe is not JsonObject||recipe["schemaVersion"]?.ToString()!="1.0"||!string.Equals(recipe["sourceDocumentHash"]?.ToString(),doc.Sha256,StringComparison.OrdinalIgnoreCase))return Results.BadRequest(new{message="Recipe version/source hash must match the selected PDF."});
        if(parentId!=null&&!await db.ModelRevisions.AnyAsync(r=>r.Id==parentId&&r.DocumentId==doc.Id))return Results.BadRequest(new{message="Parent must belong to this PDF."});
        var raw=Canonical(recipe)!.ToJsonString();if(Encoding.UTF8.GetByteCount(raw)>12_000_000)return Results.BadRequest(new{message="Recipe exceeds 12 MB."});
        var hash=Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(raw)));
        await Gate.WaitAsync();try {
            var previous=await db.RecipeBuilds.FirstOrDefaultAsync(j=>j.DocumentId==doc.Id&&j.DocumentHash==doc.Sha256&&j.RecipeHash==hash&&j.GeneratorVersion==Version);
            if(previous!=null)return Results.Ok(previous);
            var job=new RecipeBuild{DocumentId=doc.Id,DocumentHash=doc.Sha256,RecipeHash=hash,Actor=PortalAuth.UserId(c.User),ParentId=parentId};
            var folder=Folder(paths,job.Id);Directory.CreateDirectory(folder);await File.WriteAllTextAsync(Path.Combine(folder,"input.json"),raw);
            db.RecipeBuilds.Add(job);await db.SaveChangesAsync();return Results.Accepted($"/api/recipe-builds/{job.Id}",job);
        }finally{Gate.Release();}
    }
    public static void Map(WebApplication app){
        app.MapPost("/api/documents/{id}/interpret",async(string id,HttpContext c,PortalDb db,StoragePaths paths)=>{
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            var doc=await db.Documents.FindAsync(id);if(doc==null||!await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            var job=await QueueAutomatic(doc,PortalAuth.UserId(c.User),db,paths);return Results.Accepted($"/api/recipe-builds/{job.Id}",job);
        }).RequireAuthorization().RequireRateLimiting("processing");
        app.MapPost("/api/documents/{id}/recipe-builds",async(string id,RecipeInput input,HttpContext c,PortalDb db,StoragePaths paths)=>{
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            if(input.Recipe==null)return Results.BadRequest(new{message="Supply a recipe JSON object."});
            return await Queue(id,input.Recipe,input.ParentId,c,db,paths);
        }).RequireAuthorization().RequireRateLimiting("processing");
        app.MapGet("/api/documents/{id}/recipe-builds",async(string id,HttpContext c,PortalDb db)=>{
            var doc=await db.Documents.FindAsync(id);if(doc==null||!await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            return Results.Ok(await db.RecipeBuilds.Where(j=>j.DocumentId==id).OrderByDescending(j=>j.CreatedUtc).ToListAsync());
        }).RequireAuthorization();
        app.MapGet("/api/recipe-builds/{id}",async(string id,HttpContext c,PortalDb db)=>{
            var j=await Authorized(id,c,db);return j==null?Results.NotFound():Results.Ok(j);
        }).RequireAuthorization();
        app.MapGet("/api/recipe-builds/{id}/files/{asset}",async(string id,string asset,HttpContext c,PortalDb db,StoragePaths paths)=>{
            var j=await Authorized(id,c,db);if(j==null||asset is not ("recipe.json" or "evidence.json" or "interpretation.json"))return Results.NotFound();
            if(asset!="interpretation.json"&&j.Status!="Completed"||!File.Exists(Path.Combine(Folder(paths,id),asset)))return Results.NotFound();
            return Results.File(Path.Combine(Folder(paths,id),asset),"application/json",asset);
        }).RequireAuthorization();
        app.MapPost("/api/recipe-builds/{id}/windows/{windowId}/width",async(string id,string windowId,WindowWidthInput input,HttpContext c,PortalDb db,StoragePaths paths)=>{
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            var j=await Authorized(id,c,db);if(j==null)return Results.NotFound();
            if(j.Status!="Completed"||!double.IsFinite(input.Width)||input.Width<=0||input.Width>10000)return Results.BadRequest(new{message="Choose a completed recipe and positive width in metres."});
            var recipe=JsonNode.Parse(await File.ReadAllTextAsync(Path.Combine(Folder(paths,id),"recipe.json")))!;
            var decodedWindowId=Uri.UnescapeDataString(windowId);
            var openings=recipe["walls"]!.AsArray().SelectMany(w=>w!["openings"]!.AsArray()).Where(o=>o!["id"]!.ToString()==decodedWindowId).ToList();
            if(openings.Count!=1||openings[0]!["kind"]!.ToString()!="window")return Results.NotFound();
            openings[0]!["width"]=input.Width;
            return await Queue(j.DocumentId,recipe,j.RevisionId,c,db,paths);
        }).RequireAuthorization().RequireRateLimiting("processing");
    }
    static async Task<RecipeBuild?> Authorized(string id,HttpContext c,PortalDb db){
        var job=await db.RecipeBuilds.FindAsync(id);if(job==null)return null;
        var doc=await db.Documents.FindAsync(job.DocumentId);return doc!=null&&await PortalAuth.CanAccess(c.User,db,doc.BuildingId)?job:null;
    }
}
record RecipeInput(JsonNode? Recipe,string? ParentId);
record WindowWidthInput(double Width);

// Uses the portal's persisted SQLite queue/BackgroundService pattern. No browser lifecycle dependency.
sealed class RecipeBuildService(IServiceScopeFactory scopes,StoragePaths paths,IConfiguration config,IWebHostEnvironment environment,ILogger<RecipeBuildService> logger):BackgroundService {
    protected override async Task ExecuteAsync(CancellationToken stop){
        using(var scope=scopes.CreateScope()){
            var db=scope.ServiceProvider.GetRequiredService<PortalDb>();
            await db.RecipeBuilds.Where(j=>j.Status=="Running").ExecuteUpdateAsync(s=>s.SetProperty(j=>j.Status,"Queued"),stop);
        }
        while(!stop.IsCancellationRequested){
            try{
                using var scope=scopes.CreateScope();var db=scope.ServiceProvider.GetRequiredService<PortalDb>();
                var job=await db.RecipeBuilds.Where(j=>j.Status=="Queued").OrderBy(j=>j.CreatedUtc).FirstOrDefaultAsync(stop);
                if(job==null){await Task.Delay(1000,stop);continue;}
                await Build(job,db,stop);
            }catch(OperationCanceledException)when(stop.IsCancellationRequested){break;}
            catch(Exception ex){logger.LogError(ex,"Recipe queue error");await Task.Delay(2000,stop);}
        }
    }
    async Task Build(RecipeBuild job,PortalDb db,CancellationToken stop){
        job.Status="Running";await db.SaveChangesAsync(stop);var folder=RecipeWorkflow.Folder(paths,job.Id);
        using var process=new Process();bool started=false;
        try{
            var doc=await db.Documents.FindAsync([job.DocumentId],stop)??throw new InvalidDataException("Missing source PDF.");
            if(await db.WorkspaceDeletions.AnyAsync(d=>d.BuildingId==doc.BuildingId,stop))throw new InvalidDataException("Workspace is deleted.");
            var sourceHash=Convert.ToHexString(SHA256.HashData(await File.ReadAllBytesAsync(paths.Pdf(doc.Id),stop)));
            if(!string.Equals(sourceHash,job.DocumentHash,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Source checksum mismatch.");
            var repo=Path.GetFullPath(Path.Combine(environment.ContentRootPath,".."));
            var python=config["Processing:Python"]??Path.Combine(repo,".venv",OperatingSystem.IsWindows()?"Scripts/python.exe":"bin/python");
            process.StartInfo=new ProcessStartInfo(python){UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,WorkingDirectory=repo};
            var automatic=RecipeWorkflow.IsAutomatic(job);
            foreach(var arg in automatic?new[]{"-u",Path.Combine(repo,"worker","pdf_interpret.py"),"--pdf",paths.Pdf(doc.Id),"--output",folder}:new[]{"-u",Path.Combine(repo,"worker","recipe_generate.py"),"--recipe",Path.Combine(folder,"input.json"),"--output",folder})process.StartInfo.ArgumentList.Add(arg);
            foreach(var key in process.StartInfo.Environment.Keys.Where(k=>k.Contains("PASSWORD",StringComparison.OrdinalIgnoreCase)||k.Contains("SECRET",StringComparison.OrdinalIgnoreCase)||k.Contains("TOKEN",StringComparison.OrdinalIgnoreCase)||k.Contains("KEY",StringComparison.OrdinalIgnoreCase)||k.Contains("DATABASE",StringComparison.OrdinalIgnoreCase)).ToArray())process.StartInfo.Environment.Remove(key);
            process.StartInfo.Environment["PYTHONUTF8"]="1";process.Start();started=true;
            var stdout=process.StandardOutput.ReadToEndAsync(stop);var stderr=process.StandardError.ReadToEndAsync(stop);
            using var deadline=CancellationTokenSource.CreateLinkedTokenSource(stop);deadline.CancelAfter(TimeSpan.FromMinutes(automatic?15:5));
            while(!process.HasExited){
                await Task.Delay(250,deadline.Token);process.Refresh();if(process.HasExited)break;
                try{if(process.WorkingSet64>2_000_000_000)throw new InvalidDataException("Recipe worker exceeded its 2 GB memory limit.");}
                catch(InvalidOperationException)when(process.HasExited){break;}
            }
            await process.WaitForExitAsync(deadline.Token);var output=await stdout;var error=await stderr;
            if(process.ExitCode!=0){
                await File.WriteAllTextAsync(Path.Combine(folder,"diagnostics.log"),error.Length>16000?error[..16000]:error,stop);
                string message="Recipe validation or generation failed. Administrator diagnostics retained locally.";
                if(process.ExitCode is 2 or 3)try{using var problem=JsonDocument.Parse(output);message=problem.RootElement.GetProperty("error").GetString()??message;}catch(JsonException){}
                if(process.ExitCode==3){job.Status="NeedsInput";job.Error=message;job.FinishedUtc=DateTime.UtcNow;await db.SaveChangesAsync(stop);return;}
                throw new InvalidDataException(message.Length>2000?message[..2000]:message);
            }
            var modelPath=Path.Combine(folder,"model.glb");if(new FileInfo(modelPath).Length>75_000_000)throw new InvalidDataException("Generated model exceeds 75 MB.");
            using var manifest=JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(folder,"evidence.json"),stop));
            var validatedHash=Convert.ToHexString(SHA256.HashData(await File.ReadAllBytesAsync(Path.Combine(folder,"recipe.json"),stop)));
            if(manifest.RootElement.GetProperty("generatorVersion").GetString()!=job.GeneratorVersion||!string.Equals(manifest.RootElement.GetProperty("sourceDocumentHash").GetString(),job.DocumentHash,StringComparison.OrdinalIgnoreCase)||!string.Equals(manifest.RootElement.GetProperty("recipeHash").GetString(),validatedHash,StringComparison.OrdinalIgnoreCase))throw new InvalidDataException("Generated evidence/version checksum mismatch.");
            var bytes=await File.ReadAllBytesAsync(modelPath,stop);var components=ModelApi.Inspect(bytes);
            if(components.Any(c=>c.SuppliedId==null)||components.Select(c=>c.SuppliedId).Distinct().Count()!=components.Count)throw new InvalidDataException("Generated identity collision.");
            var result=await ModelApi.Persist(doc.BuildingId,doc.Id,job.ParentId??"",automatic?"automatically-interpreted-pdf-draft.glb":"interpreted-recipe.glb",job.Actor,bytes,components,db,paths);
            if(result is not Microsoft.AspNetCore.Http.HttpResults.Ok<ModelRevision> ok)throw new InvalidDataException("Revision save refused.");
            var revision=ok.Value!;components=await db.ModelComponents.Where(c=>c.RevisionId==revision.Id).ToListAsync(stop);var byId=components.ToDictionary(c=>c.SuppliedId!,c=>c.Id);
            await using var tx=await db.Database.BeginTransactionAsync(stop);
            if(!await db.ModelGroups.AnyAsync(g=>g.RevisionId==revision.Id,stop))foreach(var g in manifest.RootElement.GetProperty("groups").EnumerateArray())db.ModelGroups.Add(new ModelGroup{RevisionId=revision.Id,Name=g.GetProperty("name").GetString()!,Members=JsonSerializer.Serialize(g.GetProperty("members").EnumerateArray().Select(m=>byId[m.GetString()!]))});
            if(job.ParentId!=null&&!await db.ComponentRemaps.AnyAsync(m=>m.RevisionId==revision.Id,stop)){
                // Identity is established only within a generated recipe lineage, never by imported names.
                var parentBuild=await db.RecipeBuilds.FirstOrDefaultAsync(j=>j.RevisionId==job.ParentId&&j.DocumentId==job.DocumentId&&j.Status=="Completed",stop);
                if(parentBuild!=null)foreach(var old in await db.ModelComponents.Where(c=>c.RevisionId==job.ParentId).ToListAsync(stop))if(old.SuppliedId!=null&&byId.TryGetValue(old.SuppliedId,out var current))db.ComponentRemaps.Add(new ComponentRemap{RevisionId=revision.Id,OldComponentId=old.Id,NewComponentId=current,Reason="Stable recipe component ID in generated lineage. Historical evidence requires recheck."});
            }
            job.RevisionId=revision.Id;job.Status="Completed";job.FinishedUtc=DateTime.UtcNow;await db.SaveChangesAsync(stop);await tx.CommitAsync(stop);
        }catch(OperationCanceledException)when(stop.IsCancellationRequested){throw;}
        catch(Exception ex){logger.LogWarning(ex,"Recipe build {Id} failed",job.Id);job.Status="Failed";job.Error=ex is InvalidDataException?ex.Message:"Recipe build failed; administrator diagnostics are available locally.";job.FinishedUtc=DateTime.UtcNow;await db.SaveChangesAsync(stop);}
        finally{if(started&&!process.HasExited){process.Kill(true);await process.WaitForExitAsync(CancellationToken.None);}}
    }
}
