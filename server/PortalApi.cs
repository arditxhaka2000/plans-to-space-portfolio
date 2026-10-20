using System.Security.Claims;
using System.Security.Cryptography;
using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

static class PortalApi {
    static object UserView(PortalUser u) => new { u.Id, u.Email, u.Role, u.Disabled, deviceEnrolled = u.DeviceHash != null };
    static IResult Error(string message, int status = 400) => Results.Json(new { message }, statusCode: status);
    public static void Map(WebApplication app) {
        app.MapGet("/api/csrf", (HttpContext c, IAntiforgery a) => Results.Ok(new { token = a.GetAndStoreTokens(c).RequestToken }));
        app.MapPost("/api/auth/login", async (Credentials input, HttpContext c, PortalDb db, PasswordHasher<PortalUser> hasher, LoginGate gate, PortalCookies cookies) => {
            if (!PortalAuth.ValidEmail(input.Email) || !PortalAuth.ValidPassword(input.Password)) return Error("Invalid credentials.", 401);
            await gate.Mutex.WaitAsync();
            try {
                var user = await db.Users.SingleOrDefaultAsync(u => u.Email == input.Email.Trim().ToLowerInvariant());
                var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
                if (user is null) { hasher.VerifyHashedPassword(new PortalUser(), DummyHash.Value, input.Password); return Error("Invalid credentials.", 401); }
                if (user.Disabled || user.LockUntil > now) return Error("Sign-in unavailable. Try later or contact your administrator.", 401);
                var verified = hasher.VerifyHashedPassword(user, user.PasswordHash, input.Password);
                if (verified == PasswordVerificationResult.Failed) {
                    user.FailedAttempts++;
                    if (user.FailedAttempts >= 5) { user.LockUntil = now + 900; user.FailedAttempts = 0; }
                    await db.SaveChangesAsync(); return Error("Invalid credentials.", 401);
                }
                var isAdmin = string.Equals(user.Role, "admin", StringComparison.OrdinalIgnoreCase);
                var device = c.Request.Cookies["Flamingo.Device"];
                if (!isAdmin) {
                    if (user.DeviceHash != null && (string.IsNullOrEmpty(device) || user.DeviceHash != PortalAuth.Hash(device))) return Error("This account is enrolled on another browser. Ask your administrator to reset its device.", 409);
                    device ??= Convert.ToHexString(RandomNumberGenerator.GetBytes(32));
                    var hash = PortalAuth.Hash(device);
                    if (await db.Users.AnyAsync(u => u.Id != user.Id && u.DeviceHash == hash)) return Error("This browser is already enrolled to another account.", 409);
                    user.DeviceHash = hash;
                } else {
                    // Administrators are intentionally portable and may keep multiple browser sessions.
                    user.DeviceHash = null;
                }
                db.Sessions.RemoveRange(await db.Sessions.Where(s => s.UserId == user.Id && (s.RevokedUtc != null || s.ExpiresUtc <= DateTime.UtcNow)).ToListAsync());
                user.SessionId = Guid.NewGuid().ToString("N"); user.FailedAttempts = 0; user.LockUntil = 0;
                db.Sessions.Add(new PortalSession { Id = user.SessionId, UserId = user.Id });
                if (verified == PasswordVerificationResult.SuccessRehashNeeded) user.PasswordHash = hasher.HashPassword(user, input.Password);
                await db.SaveChangesAsync();
                if (!isAdmin) c.Response.Cookies.Append("Flamingo.Device", device!, cookies.DeviceOptions(c));
                var principal = new ClaimsPrincipal(new ClaimsIdentity(new[] { new Claim(ClaimTypes.NameIdentifier, user.Id), new Claim(ClaimTypes.Name, user.Email), new Claim(ClaimTypes.Role, user.Role), new Claim("sid", user.SessionId) }, CookieAuthenticationDefaults.AuthenticationScheme));
                await c.SignInAsync(CookieAuthenticationDefaults.AuthenticationScheme, principal, new AuthenticationProperties { IsPersistent = false });
                return Results.Ok(UserView(user));
            } finally { gate.Mutex.Release(); }
        }).RequireRateLimiting("login");
        app.MapGet("/api/me", async (HttpContext c, PortalDb db) => Results.Ok(UserView((await db.Users.FindAsync(PortalAuth.UserId(c.User)))!))).RequireAuthorization();
        app.MapPost("/api/auth/logout", async (HttpContext c, PortalDb db) => {
            var user = await db.Users.FindAsync(PortalAuth.UserId(c.User));
            var sid = c.User.FindFirstValue("sid");
            var session = string.IsNullOrEmpty(sid) ? null : await db.Sessions.FindAsync(sid);
            if (session is not null) session.RevokedUtc = DateTime.UtcNow;
            if (user is not null && !string.Equals(user.Role, "admin", StringComparison.OrdinalIgnoreCase)) user.SessionId = null;
            await db.SaveChangesAsync();
            await c.SignOutAsync(); return Results.Ok();
        }).RequireAuthorization();
        app.MapGet("/api/buildings", async (HttpContext c, PortalDb db) => {
            var uid = PortalAuth.UserId(c.User);
            return Results.Ok(await db.Buildings.Where(b => !db.WorkspaceDeletions.Any(d => d.BuildingId == b.Id) && (c.User.IsInRole("admin") || db.Grants.Any(g => g.BuildingId == b.Id && g.UserId == uid))).ToListAsync());
        }).RequireAuthorization();
        app.MapGet("/api/buildings/{id}/documents", async (string id, HttpContext c, PortalDb db) => {
            if (!await PortalAuth.CanAccess(c.User, db, id)) return Results.NotFound();
            return Results.Ok(await db.Documents.Where(d => d.BuildingId == id).OrderByDescending(d => d.CreatedUtc).ToListAsync());
        }).RequireAuthorization();
        app.MapPost("/api/buildings/{id}/documents", async (string id, HttpContext c, PortalDb db, StoragePaths paths, LoginGate gate,IConfiguration config) => {
            if (!await PortalAuth.CanAccess(c.User, db, id)) return Results.NotFound();
            if (!c.User.IsInRole("admin")) return Results.Forbid();
            if (!c.Request.HasFormContentType) return Error("Expected a PDF upload.");
            var form = await c.Request.ReadFormAsync(); var file = form.Files.GetFile("pdf");
            if (file is null || file.Length < 8 || file.Length > 75_000_000 || !file.FileName.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase)) return Error("Choose a PDF up to 75 MB.");
            await using var input = file.OpenReadStream();
            var signature = new byte[5]; await input.ReadExactlyAsync(signature);
            if (!signature.SequenceEqual("%PDF-"u8.ToArray())) return Error("File does not have a PDF header.");
            var doc = new ProjectDocument { BuildingId = id, UploadedBy = PortalAuth.UserId(c.User), OriginalName = Path.GetFileName(file.FileName), Size = file.Length };
            Directory.CreateDirectory(Path.Combine(paths.Root, "pdfs"));
            var destination = paths.Pdf(doc.Id);
            try {
                await using (var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write)) { await output.WriteAsync(signature); await input.CopyToAsync(output); }
                await using (var read = File.OpenRead(destination)) doc.Sha256 = Convert.ToHexString(await SHA256.HashDataAsync(read));
                await gate.Mutex.WaitAsync();
                try {
                    var existing = await db.Documents.FirstOrDefaultAsync(d => d.BuildingId == id && d.Sha256 == doc.Sha256);
                    if (existing != null) { File.Delete(destination); if(config.GetValue<bool?>("AutomaticPdf:Enabled")!=false)await RecipeWorkflow.QueueAutomatic(existing,PortalAuth.UserId(c.User),db,paths); await db.SaveChangesAsync(); return Results.Ok(existing); }
                    await using var uploadTransaction=await db.Database.BeginTransactionAsync();
                    doc.Status = "Queued for extraction";
                    db.Documents.Add(doc); db.Jobs.Add(new ProcessingJob { DocumentId = doc.Id });
                    await db.SaveChangesAsync();
                    if(config.GetValue<bool?>("AutomaticPdf:Enabled")!=false)await RecipeWorkflow.QueueAutomatic(doc,PortalAuth.UserId(c.User),db,paths);
                    await uploadTransaction.CommitAsync();
                } finally { gate.Mutex.Release(); }
            } catch { if (File.Exists(destination)) File.Delete(destination); throw; }
            return Results.Ok(doc);
        }).RequireAuthorization().RequireRateLimiting("upload");
        app.MapGet("/api/documents/{id}/download", async (string id, HttpContext c, PortalDb db, StoragePaths paths) => {
            var doc = await db.Documents.FindAsync(id);
            if (doc is null || !await PortalAuth.CanAccess(c.User, db, doc.BuildingId)) return Results.NotFound();
            return Results.File(paths.Pdf(doc.Id), "application/pdf", doc.OriginalName, enableRangeProcessing: true);
        }).RequireAuthorization();
        var admin = app.MapGroup("/api/admin").RequireAuthorization(p => p.RequireRole("admin"));
        admin.MapDelete("/buildings/{id}", async (string id, HttpContext c, PortalDb db, LoginGate gate) => {
            await gate.Mutex.WaitAsync();
            try {
                if (!await db.Buildings.AnyAsync(b => b.Id == id)) return Results.NotFound();
                if (await db.WorkspaceDeletions.AnyAsync(d => d.BuildingId == id)) return Results.Ok();
                await using var transaction = await db.Database.BeginTransactionAsync();
                db.WorkspaceDeletions.Add(new WorkspaceDeletion { BuildingId = id, DeletedBy = PortalAuth.UserId(c.User) });
                foreach (var job in await db.Jobs.Where(j => db.Documents.Any(d => d.Id == j.DocumentId && d.BuildingId == id) && (j.Status == "Queued" || j.Status == "Running")).ToListAsync()) {
                    job.CancelRequested = true;
                    if (job.Status == "Queued") { job.Status = "Cancelled"; job.Stage = "Workspace deleted"; job.FinishedUtc = DateTime.UtcNow; }
                }
                await db.SaveChangesAsync(); await transaction.CommitAsync(); return Results.Ok();
            } finally { gate.Mutex.Release(); }
        });
        admin.MapPost("/buildings/{id}/restore", async (string id, PortalDb db, LoginGate gate) => {
            await gate.Mutex.WaitAsync();
            try {
                if (!await db.Buildings.AnyAsync(b => b.Id == id)) return Results.NotFound();
                var deletion = await db.WorkspaceDeletions.FindAsync(id);
                if (deletion != null) { db.WorkspaceDeletions.Remove(deletion); await db.SaveChangesAsync(); }
                return Results.Ok();
            } finally { gate.Mutex.Release(); }
        });
        admin.MapGet("/users", async (PortalDb db) => (await db.Users.ToListAsync()).Select(UserView));
        admin.MapPost("/users", async (Credentials input, PortalDb db, PasswordHasher<PortalUser> hasher) => {
            if (!PortalAuth.ValidEmail(input.Email) || !PortalAuth.ValidPassword(input.Password)) return Error("Use a valid email and a password of 12–128 characters.");
            var email = input.Email.Trim().ToLowerInvariant();
            if (await db.Users.AnyAsync(u => u.Email == email)) return Error("Account already exists.", 409);
            var user = new PortalUser { Email = email }; user.PasswordHash = hasher.HashPassword(user, input.Password);
            db.Users.Add(user); await db.SaveChangesAsync(); return Results.Ok(UserView(user));
        });
        admin.MapPost("/users/{id}/reset-device", async (string id, HttpContext c, PortalDb db, LoginGate gate) => {
            if (id == PortalAuth.UserId(c.User)) return Error("Use a second administrator or local recovery to reset your own device.");
            await gate.Mutex.WaitAsync();
            try { var u = await db.Users.FindAsync(id); if (u is null) return Results.NotFound(); u.DeviceHash = null; u.SessionId = null; foreach (var s in await db.Sessions.Where(s => s.UserId == id && s.RevokedUtc == null).ToListAsync()) s.RevokedUtc = DateTime.UtcNow; await db.SaveChangesAsync(); return Results.Ok(); }
            finally { gate.Mutex.Release(); }
        });
        admin.MapPost("/users/{id}/status", async (string id, AccountStatus input, HttpContext c, PortalDb db) => {
            if (id == PortalAuth.UserId(c.User)) return Error("You cannot disable your own account.");
            var u = await db.Users.FindAsync(id); if (u is null) return Results.NotFound();
            u.Disabled = input.Disabled; u.SessionId = null; foreach (var s in await db.Sessions.Where(s => s.UserId == id && s.RevokedUtc == null).ToListAsync()) s.RevokedUtc = DateTime.UtcNow; await db.SaveChangesAsync(); return Results.Ok();
        });
        admin.MapPost("/buildings", async (BuildingName input, PortalDb db) => {
            if (string.IsNullOrWhiteSpace(input.Name) || input.Name.Length > 160) return Error("Enter a building name up to 160 characters.");
            var b = new Building { Name = input.Name.Trim() }; db.Buildings.Add(b); await db.SaveChangesAsync(); return Results.Ok(b);
        });
        admin.MapGet("/grants", async (PortalDb db) => await db.Grants.Where(g => !db.WorkspaceDeletions.Any(d => d.BuildingId == g.BuildingId)).ToListAsync());
        admin.MapPost("/grants", async (GrantRequest input, PortalDb db) => {
            if (!await db.Users.AnyAsync(u => u.Id == input.UserId) || !await db.Buildings.AnyAsync(b => b.Id == input.BuildingId) || await db.WorkspaceDeletions.AnyAsync(d => d.BuildingId == input.BuildingId)) return Results.NotFound();
            var grant = await db.Grants.FindAsync(input.BuildingId, input.UserId);
            if (input.Allow && grant is null) db.Grants.Add(new BuildingGrant { BuildingId = input.BuildingId, UserId = input.UserId });
            if (!input.Allow && grant != null) db.Grants.Remove(grant);
            await db.SaveChangesAsync(); return Results.Ok();
        });
        app.MapPost("/api/import", () => Error("Use an assigned building to import PDFs.", 410)).RequireAuthorization();
        app.MapMethods("/api/shares/{**rest}", ["GET", "POST"], () => Error("Anonymous sharing has been disabled. Use building assignments.", 410));
    }
    static readonly Lazy<string> DummyHash = new(() => new PasswordHasher<PortalUser>().HashPassword(new PortalUser(), Guid.NewGuid().ToString()));
}
record Credentials(string Email, string Password);
record BuildingName(string Name);
record GrantRequest(string BuildingId, string UserId, bool Allow);
record AccountStatus(bool Disabled);
