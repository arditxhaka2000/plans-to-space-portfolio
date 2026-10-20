using Microsoft.AspNetCore.Antiforgery;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.DataProtection;
using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.HttpOverrides;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using System.Threading.RateLimiting;

var builder = WebApplication.CreateBuilder(args);
var dataPath = Path.GetFullPath(builder.Configuration["Saas:DataPath"] ?? Path.Combine(builder.Environment.ContentRootPath, "App_Data", "saas"));
Directory.CreateDirectory(dataPath);
builder.Services.AddSingleton(new StoragePaths(dataPath));
builder.Services.AddDbContext<PortalDb>(o => o.UseSqlite($"Data Source={Path.Combine(dataPath, "portal.db")}"));
builder.Services.AddDataProtection().PersistKeysToFileSystem(new DirectoryInfo(Path.Combine(dataPath, "keys"))).SetApplicationName("FlamingoPortal");
builder.Services.AddSingleton<PasswordHasher<PortalUser>>();
builder.Services.AddSingleton<LoginGate>();
if (builder.Configuration.GetValue<bool?>("Processing:Enabled") != false) builder.Services.AddHostedService<PdfProcessingService>();
if (builder.Configuration.GetValue<bool?>("Recipes:Enabled") != false) builder.Services.AddHostedService<RecipeBuildService>();
builder.Services.Configure<FormOptions>(o => o.MultipartBodyLengthLimit = 80_000_000);
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 80_000_000);
var secureCookies = !builder.Environment.IsDevelopment();
builder.Services.AddSingleton(new PortalCookies());
builder.Services.AddAntiforgery(o => { o.HeaderName = "X-CSRF-TOKEN"; o.Cookie.Name = "Flamingo.Csrf"; o.Cookie.SameSite = SameSiteMode.Strict; o.Cookie.SecurePolicy = secureCookies ? CookieSecurePolicy.Always : CookieSecurePolicy.SameAsRequest; });
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme).AddCookie(o => {
    o.Cookie.Name = "Flamingo.Session"; o.Cookie.HttpOnly = true; o.Cookie.SameSite = SameSiteMode.Strict;
    o.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
    o.ExpireTimeSpan = TimeSpan.FromHours(8); o.SlidingExpiration = false;
    o.Events.OnRedirectToLogin = c => { c.Response.StatusCode = 401; return Task.CompletedTask; };
    o.Events.OnRedirectToAccessDenied = c => { c.Response.StatusCode = 403; return Task.CompletedTask; };
    o.Events.OnValidatePrincipal = PortalAuth.Validate;
});
builder.Services.AddAuthorization();
builder.Services.AddRateLimiter(o => {
    o.RejectionStatusCode = 429;
    o.AddPolicy("login", context => RateLimitPartition.GetFixedWindowLimiter(context.Connection.RemoteIpAddress?.ToString() ?? "unknown", _ => new FixedWindowRateLimiterOptions { PermitLimit = 20, Window = TimeSpan.FromMinutes(5), QueueLimit = 0 }));
    o.AddPolicy("upload", context => RateLimitPartition.GetFixedWindowLimiter(PortalAuth.UserId(context.User) is { Length: > 0 } uid ? uid : context.Connection.RemoteIpAddress?.ToString() ?? "unknown", _ => new FixedWindowRateLimiterOptions { PermitLimit = 5, Window = TimeSpan.FromHours(1), QueueLimit = 0 }));
    o.AddPolicy("processing", context => RateLimitPartition.GetFixedWindowLimiter(PortalAuth.UserId(context.User) is { Length: > 0 } uid ? uid : context.Connection.RemoteIpAddress?.ToString() ?? "unknown", _ => new FixedWindowRateLimiterOptions { PermitLimit = 10, Window = TimeSpan.FromHours(1), QueueLimit = 0 }));
});
builder.Services.Configure<ForwardedHeadersOptions>(o => {
    o.ForwardedHeaders = ForwardedHeaders.XForwardedFor | ForwardedHeaders.XForwardedProto;
    o.KnownProxies.Add(System.Net.IPAddress.Loopback);
    o.KnownProxies.Add(System.Net.IPAddress.IPv6Loopback);
    o.ForwardLimit = 1;
});
var app = builder.Build();
using (var scope = app.Services.CreateScope()) {
    var db = scope.ServiceProvider.GetRequiredService<PortalDb>();
    await db.Database.EnsureCreatedAsync();
    await ModelSchema.Ensure(db);
    await RecipeWorkflow.Ensure(db);
    await db.Database.ExecuteSqlRawAsync("""
        CREATE TABLE IF NOT EXISTS WorkspaceDeletions (
          BuildingId TEXT NOT NULL PRIMARY KEY REFERENCES Buildings(Id),
          DeletedBy TEXT NOT NULL, DeletedUtc TEXT NOT NULL);
        """);
    if (builder.Configuration["import-glb"] is string importFile) {
        await ModelApi.ImportLocal(importFile, builder.Configuration["source-document"] ?? throw new ArgumentException("--source-document is required"), builder.Configuration["parent-revision"], db, scope.ServiceProvider.GetRequiredService<StoragePaths>());
        return;
    }

    // Additive v1 processing migration for existing account databases. Never
    // recreate or drop the user's existing tables.
    await db.Database.ExecuteSqlRawAsync("""
        CREATE TABLE IF NOT EXISTS Jobs (
          Id TEXT NOT NULL PRIMARY KEY, DocumentId TEXT NOT NULL,
          Status TEXT NOT NULL, Stage TEXT NOT NULL, Current INTEGER NOT NULL,
          Total INTEGER NOT NULL, CancelRequested INTEGER NOT NULL,
          CreatedUtc TEXT NOT NULL, FinishedUtc TEXT NULL, Error TEXT NULL,
          FOREIGN KEY(DocumentId) REFERENCES Documents(Id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS IX_Jobs_DocumentId ON Jobs(DocumentId);
        CREATE INDEX IF NOT EXISTS IX_Jobs_DocumentId_CreatedUtc ON Jobs(DocumentId, CreatedUtc DESC);
        CREATE INDEX IF NOT EXISTS IX_Jobs_Status_CreatedUtc ON Jobs(Status, CreatedUtc);
        CREATE INDEX IF NOT EXISTS IX_Documents_BuildingId_CreatedUtc ON Documents(BuildingId, CreatedUtc DESC);
        CREATE INDEX IF NOT EXISTS IX_Documents_Sha256 ON Documents(Sha256);
        CREATE TABLE IF NOT EXISTS Sessions (
          Id TEXT NOT NULL PRIMARY KEY, UserId TEXT NOT NULL,
          CreatedUtc TEXT NOT NULL, ExpiresUtc TEXT NOT NULL, RevokedUtc TEXT NULL,
          FOREIGN KEY(UserId) REFERENCES Users(Id) ON DELETE CASCADE);
        CREATE INDEX IF NOT EXISTS IX_Sessions_UserId_ExpiresUtc ON Sessions(UserId, ExpiresUtc);
        """);
    var email = builder.Configuration["Saas:AdminEmail"];
    var password = builder.Configuration["Saas:AdminPassword"];
    if (!await db.Users.AnyAsync() && !string.IsNullOrEmpty(email) && PortalAuth.ValidPassword(password)) {
        var user = new PortalUser { Email = email.Trim().ToLowerInvariant(), Role = "admin" };
        user.PasswordHash = scope.ServiceProvider.GetRequiredService<PasswordHasher<PortalUser>>().HashPassword(user, password!);
        db.Users.Add(user); await db.SaveChangesAsync();
        app.Logger.LogInformation("Initial administrator created. Remove bootstrap credentials from configuration.");
    }
    if (!await db.Buildings.AnyAsync(b => b.Id == "flamingo-demo")) {
        db.Buildings.Add(new Building { Id = "flamingo-demo", Name = "Flamingo Tower · review model", IsDemo = true }); await db.SaveChangesAsync();
    }
}
app.UseForwardedHeaders();
app.Use(async (ctx, next) => {
    ctx.Response.Headers["X-Content-Type-Options"] = "nosniff";
    ctx.Response.Headers["Referrer-Policy"] = "same-origin";
    ctx.Response.Headers["X-Frame-Options"] = "DENY";
    ctx.Response.Headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'";
    ctx.Response.Headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(), usb=()";
    if (ctx.Request.IsHttps) ctx.Response.Headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains";
    ctx.Response.Headers.CacheControl = "no-store";
    if (!app.Environment.IsDevelopment() && !ctx.Request.IsHttps) { ctx.Response.StatusCode = 400; await ctx.Response.WriteAsync("HTTPS is required. Configure a trusted HTTPS host before client use."); return; }
    await next();
});
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();
app.Use(async (ctx, next) => {
    if (ctx.Request.Path.StartsWithSegments("/api") && !HttpMethods.IsGet(ctx.Request.Method) && !HttpMethods.IsHead(ctx.Request.Method)) {
        try { await ctx.RequestServices.GetRequiredService<IAntiforgery>().ValidateRequestAsync(ctx); }
        catch (AntiforgeryValidationException) { ctx.Response.StatusCode = 400; await ctx.Response.WriteAsJsonAsync(new { message = "Security token expired. Reload and try again." }); return; }
    }
    var p = ctx.Request.Path.Value ?? "/";
    if (p.Equals("/portal.html", StringComparison.OrdinalIgnoreCase)) { ctx.Response.Redirect(ctx.User.Identity?.IsAuthenticated == true ? "/dashboard" : "/login"); return; }
    if (p.Equals("/floors.html", StringComparison.OrdinalIgnoreCase) || p.Equals("/index.html", StringComparison.OrdinalIgnoreCase)) { ctx.Response.Redirect("/buildings/flamingo-demo/model"); return; }
    // Default-deny static content, including case variants on Windows.
    var isViewer = !(p == "/" || p.Equals("/login", StringComparison.OrdinalIgnoreCase) || p.Equals("/dashboard", StringComparison.OrdinalIgnoreCase) || p.StartsWith("/buildings/", StringComparison.OrdinalIgnoreCase) || p.StartsWith("/portal/", StringComparison.OrdinalIgnoreCase) || p.StartsWith("/api/", StringComparison.OrdinalIgnoreCase));
    if (isViewer) {
        var db = ctx.RequestServices.GetRequiredService<PortalDb>();
        if (ctx.User.Identity?.IsAuthenticated != true) { ctx.Response.Redirect("/login"); return; }
        if (!await PortalAuth.CanAccess(ctx.User, db, "flamingo-demo")) { ctx.Response.StatusCode = 403; return; }
    }
    await next();
});
app.UseStaticFiles();
app.MapGet("/", (HttpContext c) => Results.Redirect(c.User.Identity?.IsAuthenticated == true ? "/dashboard" : "/login"));
app.MapGet("/login", (HttpContext c) => c.User.Identity?.IsAuthenticated == true
    ? Results.Redirect("/dashboard") : Results.File(Path.Combine(app.Environment.WebRootPath, "portal.html"), "text/html"));
app.MapGet("/dashboard", (HttpContext c) => c.User.Identity?.IsAuthenticated != true
    ? Results.Redirect("/login") : Results.File(Path.Combine(app.Environment.WebRootPath, "portal.html"), "text/html"));
app.MapGet("/buildings/{id}", async (string id, HttpContext c, PortalDb db) => {
    if (c.User.Identity?.IsAuthenticated != true) return Results.Redirect("/login");
    if (!await PortalAuth.CanAccess(c.User, db, id)) return Results.NotFound();
    return Results.File(Path.Combine(app.Environment.WebRootPath, "portal.html"), "text/html");
});
app.MapGet("/buildings/{id}/model", async (string id, HttpContext c, PortalDb db) => {
    if (c.User.Identity?.IsAuthenticated != true) return Results.Redirect("/login");
    if (!await PortalAuth.CanAccess(c.User, db, id)) return Results.NotFound();
    var activeModel = await db.ModelRevisions.Where(r => r.BuildingId == id && r.Active).Select(r => r.DocumentId).FirstOrDefaultAsync();
    if (activeModel != null) return Results.Redirect($"/buildings/{Uri.EscapeDataString(id)}/documents/{activeModel}/review?view=model");
    var retainedModel = await db.ModelRevisions.Where(r => r.BuildingId == id).OrderByDescending(r => r.CreatedUtc).Select(r => r.DocumentId).FirstOrDefaultAsync();
    if (retainedModel != null) return Results.Redirect($"/buildings/{Uri.EscapeDataString(id)}/documents/{retainedModel}/review?view=model");
    if (id == "flamingo-demo") return Results.File(Path.Combine(app.Environment.WebRootPath, "floors.html"), "text/html");
    var document = await db.Documents.Where(d => d.BuildingId == id)
        .OrderByDescending(d => db.Jobs.Any(j => j.DocumentId == d.Id && j.Status == "NeedsReview"))
        .ThenByDescending(d => d.CreatedUtc).Select(d => d.Id).FirstOrDefaultAsync();
    return Results.Redirect(document == null ? $"/buildings/{Uri.EscapeDataString(id)}" : $"/buildings/{Uri.EscapeDataString(id)}/documents/{document}/review?view=model");
});
PortalApi.Map(app);
ModelApi.Map(app);
RecipeWorkflow.Map(app);
ProcessingApi.Map(app);
app.MapFallback(() => Results.NotFound());
app.Run();
