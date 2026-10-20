using Microsoft.EntityFrameworkCore;
sealed class PortalDb(DbContextOptions<PortalDb> options) : DbContext(options) {
    public DbSet<RecipeBuild> RecipeBuilds => Set<RecipeBuild>();
    public DbSet<WorkspaceDeletion> WorkspaceDeletions => Set<WorkspaceDeletion>();
    public DbSet<ModelRevision> ModelRevisions => Set<ModelRevision>();
    public DbSet<ModelComponent> ModelComponents => Set<ModelComponent>();
    public DbSet<ModelGroup> ModelGroups => Set<ModelGroup>();
    public DbSet<ModelNote> ModelNotes => Set<ModelNote>();
    public DbSet<ComponentRemap> ComponentRemaps => Set<ComponentRemap>();
    public DbSet<PortalUser> Users => Set<PortalUser>();
    public DbSet<Building> Buildings => Set<Building>();
    public DbSet<BuildingGrant> Grants => Set<BuildingGrant>();
    public DbSet<ProjectDocument> Documents => Set<ProjectDocument>();
    public DbSet<ProcessingJob> Jobs => Set<ProcessingJob>();
    public DbSet<PortalSession> Sessions => Set<PortalSession>();
    protected override void OnModelCreating(ModelBuilder b) {
        ModelSchema.Configure(b);
        b.Entity<RecipeBuild>().HasIndex(j=>new{j.DocumentId,j.DocumentHash,j.RecipeHash,j.GeneratorVersion}).IsUnique();
        b.Entity<RecipeBuild>().HasOne<ProjectDocument>().WithMany().HasForeignKey(j=>j.DocumentId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<WorkspaceDeletion>().HasKey(x => x.BuildingId);
        b.Entity<WorkspaceDeletion>().HasOne<Building>().WithMany().HasForeignKey(x => x.BuildingId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<PortalUser>().HasIndex(x => x.Email).IsUnique();
        b.Entity<PortalUser>().HasIndex(x => x.DeviceHash).IsUnique();
        b.Entity<BuildingGrant>().HasKey(x => new { x.BuildingId, x.UserId });
        b.Entity<BuildingGrant>().HasOne<PortalUser>().WithMany().HasForeignKey(x => x.UserId);
        b.Entity<BuildingGrant>().HasOne<Building>().WithMany().HasForeignKey(x => x.BuildingId);
        b.Entity<ProjectDocument>().HasOne<Building>().WithMany().HasForeignKey(x => x.BuildingId);
        b.Entity<ProjectDocument>().HasIndex(x => new { x.BuildingId, x.CreatedUtc });
        b.Entity<ProjectDocument>().HasIndex(x => x.Sha256);
        b.Entity<ProcessingJob>().HasOne<ProjectDocument>().WithMany().HasForeignKey(x => x.DocumentId);
        b.Entity<ProcessingJob>().HasIndex(x => new { x.DocumentId, x.CreatedUtc });
        b.Entity<ProcessingJob>().HasIndex(x => new { x.Status, x.CreatedUtc });
        b.Entity<PortalSession>().HasKey(x => x.Id);
        b.Entity<PortalSession>().HasOne<PortalUser>().WithMany().HasForeignKey(x => x.UserId).OnDelete(DeleteBehavior.Cascade);
        b.Entity<PortalSession>().HasIndex(x => new { x.UserId, x.ExpiresUtc });
    }
}
sealed class PortalUser {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string Email { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string Role { get; set; } = "client";
    public string? DeviceHash { get; set; }
    public string? SessionId { get; set; }
    public bool Disabled { get; set; }
    public int FailedAttempts { get; set; }
    public long LockUntil { get; set; }
}
sealed class Building {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string Name { get; set; } = "";
    public bool IsDemo { get; set; }
}
sealed class WorkspaceDeletion {
    public string BuildingId { get; set; } = "";
    public string DeletedBy { get; set; } = "";
    public DateTime DeletedUtc { get; set; } = DateTime.UtcNow;
}
sealed class BuildingGrant { public string BuildingId { get; set; } = ""; public string UserId { get; set; } = ""; }
sealed class ProjectDocument {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string BuildingId { get; set; } = "";
    public string OriginalName { get; set; } = "";
    public string UploadedBy { get; set; } = "";
    public long Size { get; set; }
    public string Sha256 { get; set; } = "";
    public DateTime CreatedUtc { get; set; } = DateTime.UtcNow;
    public string Status { get; set; } = "Stored · extraction and model generation pending";
}
sealed record StoragePaths(string Root) { public string Pdf(string id) => Path.Combine(Root, "pdfs", id + ".pdf"); }
sealed class ProcessingJob {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string DocumentId { get; set; } = "";
    public string Status { get; set; } = "Queued";
    public string Stage { get; set; } = "Waiting for worker";
    public int Current { get; set; }
    public int Total { get; set; }
    public bool CancelRequested { get; set; }
    public DateTime CreatedUtc { get; set; } = DateTime.UtcNow;
    public DateTime? FinishedUtc { get; set; }
    public string? Error { get; set; }
}
sealed class PortalSession {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string UserId { get; set; } = "";
    public DateTime CreatedUtc { get; set; } = DateTime.UtcNow;
    public DateTime ExpiresUtc { get; set; } = DateTime.UtcNow.AddHours(8);
    public DateTime? RevokedUtc { get; set; }
}
sealed class LoginGate { public SemaphoreSlim Mutex { get; } = new(1, 1); }
sealed record PortalCookies {
    public CookieOptions DeviceOptions(HttpContext context) => new() { HttpOnly = true, Secure = context.Request.IsHttps, SameSite = SameSiteMode.Strict, Path = "/", MaxAge = TimeSpan.FromDays(365) };
}
