using Microsoft.EntityFrameworkCore;

sealed class ModelRevision {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string BuildingId { get; set; } = "";
    public string DocumentId { get; set; } = "";
    public string Sha256 { get; set; } = "";
    public string OriginalName { get; set; } = "";
    public string UploadedBy { get; set; } = "";
    public string? ParentId { get; set; }
    public string ReviewState { get; set; } = "unverified";
    public bool Active { get; set; }
    public long Size { get; set; }
    public DateTime CreatedUtc { get; set; } = DateTime.UtcNow;
}
sealed class ModelComponent {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string RevisionId { get; set; } = "";
    // Index is only a locator inside the immutable, checksum-bound revision.
    public int NodeIndex { get; set; }
    public string Name { get; set; } = "";
    public string? SuppliedId { get; set; }
    public string Metadata { get; set; } = "{}";
    public string ElementType { get; set; } = "other";
    public bool TypeReviewed { get; set; }
    public bool Hidden { get; set; }
}
sealed class ModelGroup {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string RevisionId { get; set; } = "";
    public string Name { get; set; } = "";
    public string Members { get; set; } = "[]";
}
sealed class ModelNote {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string RevisionId { get; set; } = "";
    public string TargetId { get; set; } = "";
    public string Text { get; set; } = "";
    public int? Page { get; set; }
    public string? Sheet { get; set; }
    public string? Region { get; set; }
    public string? Material { get; set; }
    public string? TakeoffItem { get; set; }
    public string Status { get; set; } = "unreviewed";
    public string QuantityBasis { get; set; } = "none";
    public double? Quantity { get; set; }
    public string? Unit { get; set; }
    public string Author { get; set; } = "";
    public DateTime CreatedUtc { get; set; } = DateTime.UtcNow;
}
sealed class ComponentRemap {
    public string Id { get; set; } = Guid.NewGuid().ToString("N");
    public string RevisionId { get; set; } = "";
    public string OldComponentId { get; set; } = "";
    public string NewComponentId { get; set; } = "";
    public string Reason { get; set; } = "";
}
static class ModelSchema {
    public static void Configure(ModelBuilder b) {
        b.Entity<ModelRevision>().HasIndex(x => new { x.BuildingId, x.DocumentId, x.Sha256 }).IsUnique();
        b.Entity<ModelRevision>().HasOne<ProjectDocument>().WithMany().HasForeignKey(x => x.DocumentId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<ModelComponent>().HasIndex(x => new { x.RevisionId, x.NodeIndex }).IsUnique();
        b.Entity<ModelComponent>().HasOne<ModelRevision>().WithMany().HasForeignKey(x => x.RevisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<ModelGroup>().HasOne<ModelRevision>().WithMany().HasForeignKey(x => x.RevisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<ModelNote>().HasOne<ModelRevision>().WithMany().HasForeignKey(x => x.RevisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<ComponentRemap>().HasOne<ModelRevision>().WithMany().HasForeignKey(x => x.RevisionId).OnDelete(DeleteBehavior.Restrict);
        b.Entity<ComponentRemap>().HasIndex(x => new { x.RevisionId, x.OldComponentId }).IsUnique();
    }
    public static async Task Ensure(PortalDb db) {
        // Match the portal's existing additive SQLite migration strategy.
        await db.Database.ExecuteSqlRawAsync("""
        CREATE TABLE IF NOT EXISTS ModelRevisions (Id TEXT PRIMARY KEY, BuildingId TEXT NOT NULL, DocumentId TEXT NOT NULL REFERENCES Documents(Id), Sha256 TEXT NOT NULL, OriginalName TEXT NOT NULL, UploadedBy TEXT NOT NULL, ParentId TEXT, ReviewState TEXT NOT NULL, Active INTEGER NOT NULL, Size INTEGER NOT NULL, CreatedUtc TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS IX_ModelRevisions_Content ON ModelRevisions(BuildingId,DocumentId,Sha256);
        CREATE UNIQUE INDEX IF NOT EXISTS IX_ModelRevisions_Active ON ModelRevisions(BuildingId) WHERE Active=1;
        CREATE TABLE IF NOT EXISTS ModelComponents (Id TEXT PRIMARY KEY, RevisionId TEXT NOT NULL REFERENCES ModelRevisions(Id), NodeIndex INTEGER NOT NULL, Name TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS IX_ModelComponents_Node ON ModelComponents(RevisionId,NodeIndex);
        CREATE TABLE IF NOT EXISTS ModelGroups (Id TEXT PRIMARY KEY, RevisionId TEXT NOT NULL REFERENCES ModelRevisions(Id), Name TEXT NOT NULL, Members TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ModelNotes (Id TEXT PRIMARY KEY, RevisionId TEXT NOT NULL REFERENCES ModelRevisions(Id), TargetId TEXT NOT NULL, Text TEXT NOT NULL, Page INTEGER, Sheet TEXT, Region TEXT, Material TEXT, TakeoffItem TEXT, Status TEXT NOT NULL, QuantityBasis TEXT NOT NULL, Quantity REAL, Unit TEXT, Author TEXT NOT NULL, CreatedUtc TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS IX_ModelNotes_Revision ON ModelNotes(RevisionId);
        CREATE TABLE IF NOT EXISTS ComponentRemaps (Id TEXT PRIMARY KEY, RevisionId TEXT NOT NULL REFERENCES ModelRevisions(Id), OldComponentId TEXT NOT NULL, NewComponentId TEXT NOT NULL, Reason TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS IX_ComponentRemaps_Old ON ComponentRemaps(RevisionId,OldComponentId);
        """);
        var connection=db.Database.GetDbConnection();await connection.OpenAsync();
        var columns=new HashSet<string>();
        using(var command=connection.CreateCommand()) {command.CommandText="PRAGMA table_info(ModelComponents)";using var reader=await command.ExecuteReaderAsync();while(await reader.ReadAsync())columns.Add(reader.GetString(1));}
        foreach(var (name,definition) in new[]{("SuppliedId","TEXT"),("Metadata","TEXT NOT NULL DEFAULT '{}'"),("ElementType","TEXT NOT NULL DEFAULT 'other'"),("TypeReviewed","INTEGER NOT NULL DEFAULT 0"),("Hidden","INTEGER NOT NULL DEFAULT 0")})
            if(!columns.Contains(name)){using var command=connection.CreateCommand();command.CommandText=$"ALTER TABLE ModelComponents ADD COLUMN {name} {definition}";await command.ExecuteNonQueryAsync();}
    }
}
