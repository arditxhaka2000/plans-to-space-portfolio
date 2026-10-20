using Microsoft.EntityFrameworkCore;
using System.Text.RegularExpressions;
static class ProcessingApi {
    public static void Map(WebApplication app) {
        app.MapGet("/api/documents/{id}/geometry-context", async(string id,HttpContext c,PortalDb db,StoragePaths paths) => {
            var doc=await db.Documents.FindAsync(id);
            if(doc is null||!await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            var job=await db.Jobs.Where(j=>j.DocumentId==id).OrderByDescending(j=>j.CreatedUtc).FirstOrDefaultAsync();
            if(job is not null&&job.Status=="NeedsReview"){
                var file=Path.Combine(paths.Root,"jobs",job.Id,"exterior-assessment.json");
                if(File.Exists(file))return Results.File(file,"application/json");
            }
            return Results.Ok(new {status=job?.Status is "Queued" or "Running"?"processing":"needs-analysis",message=job?.Error??job?.Stage??"PDF has not been assessed.",sourceSha256=doc.Sha256});
        }).RequireAuthorization();
        app.MapGet("/api/documents/{id}/jobs", async (string id,HttpContext c,PortalDb db) => {
            var doc=await db.Documents.FindAsync(id);if(doc is null || !await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            return Results.Ok(await db.Jobs.Where(j=>j.DocumentId==id).OrderByDescending(j=>j.CreatedUtc).ToListAsync());
        }).RequireAuthorization();
        app.MapPost("/api/documents/{id}/process", async (string id,HttpContext c,PortalDb db,LoginGate gate) => {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            var doc=await db.Documents.FindAsync(id);if(doc is null || !await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            await gate.Mutex.WaitAsync();try{
                if(await db.Jobs.AnyAsync(j=>j.DocumentId==id&&(j.Status=="Queued"||j.Status=="Running")))return Results.Conflict(new{message="This PDF already has an active job."});
                var job=new ProcessingJob{DocumentId=id};db.Jobs.Add(job);doc.Status="Queued for extraction";await db.SaveChangesAsync();return Results.Ok(job);
            }finally{gate.Mutex.Release();}
        }).RequireAuthorization().RequireRateLimiting("processing");
        app.MapPost("/api/jobs/{id}/cancel", async (string id,HttpContext c,PortalDb db) => {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            var job=await db.Jobs.FindAsync(id);if(job is null)return Results.NotFound();var doc=await db.Documents.FindAsync(job.DocumentId);
            if(doc is null||!await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            if(job.Status is not ("Queued" or "Running"))return Results.Conflict(new{message="Job has already finished."});
            job.CancelRequested=true;if(job.Status=="Queued"){job.Status="Cancelled";job.FinishedUtc=DateTime.UtcNow;}await db.SaveChangesAsync();return Results.Ok();
        }).RequireAuthorization();
        app.MapGet("/api/jobs/{id}/files/{**asset}", async (string id,string asset,HttpContext c,PortalDb db,StoragePaths paths) => {
            if(!Regex.IsMatch(asset,@"\A(?:artifacts/[a-f0-9]{64}\.(?:json|png)|cloud-status\.json|exterior-assessment\.json|exterior\.json|evidence-summary\.json|evidence\.sqlite|manifest\.json|model\.json|validation\.json|vectors\.json|candidate-overlay\.png|pages/[0-9]{3}(?:-appearance)?\.(?:png|json)|visualization/(?:generation-manifest\.json|[a-z0-9-]+\.(?:jpg|png)))\z"))return Results.NotFound();
            var job=await db.Jobs.FindAsync(id);if(job is null||job.Status!="NeedsReview")return Results.NotFound();
            var doc=await db.Documents.FindAsync(job.DocumentId);if(doc is null||!await PortalAuth.CanAccess(c.User,db,doc.BuildingId))return Results.NotFound();
            var path=Path.Combine(paths.Root,"jobs",job.Id,asset);if(!File.Exists(path))return Results.NotFound();
            return Results.File(path,asset.EndsWith(".png")?"image/png":asset.EndsWith(".jpg")?"image/jpeg":asset.EndsWith(".sqlite")?"application/vnd.sqlite3":"application/json");
        }).RequireAuthorization();
        app.MapGet("/buildings/{building}/documents/{document}/review", async(string building,string document,HttpContext c,PortalDb db,IWebHostEnvironment env)=>{
            if(c.User.Identity?.IsAuthenticated!=true)return Results.Redirect("/login");
            if(!await PortalAuth.CanAccess(c.User,db,building)||!await db.Documents.AnyAsync(d=>d.Id==document&&d.BuildingId==building))return Results.NotFound();
            return Results.File(Path.Combine(env.WebRootPath,"review.html"),"text/html");
        });
    }
}
