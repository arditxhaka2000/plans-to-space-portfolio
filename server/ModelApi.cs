using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text.Json;
using Microsoft.EntityFrameworkCore;

static class ModelApi {
    static readonly string[] ElementTypes=["window","door","wall","roof","slab","column","railing","solar panel","other"];
    static readonly SemaphoreSlim Writes = new(1, 1);
    static IResult Bad(string message) => Results.BadRequest(new { message });
    static string Artifact(StoragePaths p, string hash) => Path.Combine(p.Root, "models", hash + ".glb");
    static async Task<ModelRevision?> Accessible(string id, HttpContext c, PortalDb db) {
        var r = await db.ModelRevisions.FindAsync(id);
        return r != null && await PortalAuth.CanAccess(c.User, db, r.BuildingId) ? r : null;
    }
    public static List<ModelComponent> Inspect(byte[] bytes) {
        uint U(int n) => BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(n,4));
        if(bytes.Length<24 || U(0)!=0x46546C67 || U(4)!=2 || U(8)!=bytes.Length || U(16)!=0x4E4F534A) throw new InvalidDataException("Expected a glTF 2 binary file.");
        var jsonLength=checked((int)U(12));
        if(jsonLength<2 || jsonLength>bytes.Length-20 || jsonLength%4!=0) throw new InvalidDataException("Invalid GLB JSON chunk.");
        int offset=20+jsonLength, binLength=0;
        if(offset<bytes.Length) {
            if(offset+8>bytes.Length || U(offset+4)!=0x004E4942) throw new InvalidDataException("Invalid binary chunk.");
            binLength=checked((int)U(offset));
            if(binLength%4!=0 || offset+8L+binLength!=bytes.Length) throw new InvalidDataException("Invalid binary length.");
        }
        using var json=JsonDocument.Parse(bytes.AsMemory(20,jsonLength));var root=json.RootElement;
        if(root.GetProperty("asset").GetProperty("version").GetString()!="2.0") throw new InvalidDataException("Expected glTF 2.0.");
        if(root.TryGetProperty("extensionsRequired",out var required) && required.GetArrayLength()>0) throw new InvalidDataException("Required glTF extensions are not supported by this importer yet.");
        foreach(var key in new[]{"buffers","images"}) if(root.TryGetProperty(key,out var entries)) foreach(var entry in entries.EnumerateArray()) {
            if(entry.TryGetProperty("uri",out _)) throw new InvalidDataException("Use a self-contained GLB with embedded buffers and images.");
            if(key=="buffers" && entry.GetProperty("byteLength").GetInt32()>binLength) throw new InvalidDataException("Buffer exceeds the binary chunk.");
        }
        var buffers=root.GetProperty("buffers");
        if(buffers.GetArrayLength()!=1)throw new InvalidDataException("Expected one embedded buffer.");
        var views=root.GetProperty("bufferViews");
        foreach(var view in views.EnumerateArray()) {
            var start=view.TryGetProperty("byteOffset",out var o)?o.GetInt64():0;var length=view.GetProperty("byteLength").GetInt64();
            if(view.GetProperty("buffer").GetInt32()!=0||start<0||length<0||start+length>buffers[0].GetProperty("byteLength").GetInt64())throw new InvalidDataException("Invalid buffer view.");
        }
        var accessors=root.GetProperty("accessors");
        foreach(var a in accessors.EnumerateArray()) {
            if(a.TryGetProperty("sparse",out _))throw new InvalidDataException("Sparse accessors are not supported yet.");
            var vi=a.GetProperty("bufferView").GetInt32();if(vi<0||vi>=views.GetArrayLength())throw new InvalidDataException("Invalid accessor view.");var v=views[vi];
            var width=a.GetProperty("componentType").GetInt32() switch {5120 or 5121=>1,5122 or 5123=>2,5125 or 5126=>4,_=>throw new InvalidDataException("Invalid accessor type.")};
            var count=a.GetProperty("count").GetInt64();var arity=a.GetProperty("type").GetString() switch {"SCALAR"=>1,"VEC2"=>2,"VEC3"=>3,"VEC4" or "MAT2"=>4,"MAT3"=>9,"MAT4"=>16,_=>throw new InvalidDataException("Invalid accessor shape.")};
            var start=a.TryGetProperty("byteOffset",out var o)?o.GetInt64():0;var stride=v.TryGetProperty("byteStride",out var st)?st.GetInt32():width*arity;
            if(count<1||count>10000000||start<0||stride<width*arity||start+(count-1)*stride+width*arity>v.GetProperty("byteLength").GetInt64())throw new InvalidDataException("Accessor exceeds buffer view.");
        }
        double Value(JsonElement a,int row,int axis=0) {
            var v=views[a.GetProperty("bufferView").GetInt32()];var type=a.GetProperty("componentType").GetInt32();var width=type is 5120 or 5121?1:type is 5122 or 5123?2:4;
            var arity=a.GetProperty("type").GetString()=="VEC3"?3:1;var stride=v.TryGetProperty("byteStride",out var st)?st.GetInt32():width*arity;
            var pos=checked(offset+8+(v.TryGetProperty("byteOffset",out var vo)?vo.GetInt32():0)+(a.TryGetProperty("byteOffset",out var ao)?ao.GetInt32():0)+row*stride+axis*width);
            return type switch {5126=>BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(bytes.AsSpan(pos,4))),5125=>BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(pos,4)),5123=>BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(pos,2)),5121=>bytes[pos],_=>throw new InvalidDataException("Unsupported geometry component type.")};
        }
        foreach(var mesh in root.GetProperty("meshes").EnumerateArray())foreach(var primitive in mesh.GetProperty("primitives").EnumerateArray()) {
            var position=primitive.GetProperty("attributes").GetProperty("POSITION").GetInt32();
            if(position<0||position>=accessors.GetArrayLength()||accessors[position].GetProperty("type").GetString()!="VEC3")throw new InvalidDataException("Invalid position accessor.");
            var pa=accessors[position];if(pa.GetProperty("componentType").GetInt32()!=5126)throw new InvalidDataException("Positions must be float32.");
            for(int row=0;row<pa.GetProperty("count").GetInt32();row++)for(int axis=0;axis<3;axis++)if(!double.IsFinite(Value(pa,row,axis)))throw new InvalidDataException("Nonfinite position.");
            if(primitive.TryGetProperty("indices",out var ix)){
                var ai=ix.GetInt32();if(ai<0||ai>=accessors.GetArrayLength())throw new InvalidDataException("Invalid index accessor.");var ia=accessors[ai];
                if(ia.GetProperty("type").GetString()!="SCALAR"||ia.GetProperty("componentType").GetInt32() is not (5121 or 5123 or 5125))throw new InvalidDataException("Invalid index type.");
                for(int row=0;row<ia.GetProperty("count").GetInt32();row++)if(Value(ia,row)>=pa.GetProperty("count").GetInt32())throw new InvalidDataException("Index exceeds vertex count.");
            }
        }
        var nodes=root.GetProperty("nodes");if(nodes.GetArrayLength()>50000) throw new InvalidDataException("Model has too many nodes.");
        // A scene must be a tree. Reject cycles, multiple parents and invalid mesh references.
        var parents=new HashSet<int>();var meshCount=root.GetProperty("meshes").GetArrayLength();
        var result=new List<ModelComponent>();int index=0;
        foreach(var node in nodes.EnumerateArray()) {
            foreach(var key in new[]{"translation","scale","rotation","matrix"})if(node.TryGetProperty(key,out var transform)){
                var expected=key=="matrix"?16:key=="rotation"?4:3;
                if(transform.ValueKind!=JsonValueKind.Array||transform.GetArrayLength()!=expected||transform.EnumerateArray().Any(v=>v.ValueKind!=JsonValueKind.Number||!v.TryGetDouble(out var number)||!double.IsFinite(number)))throw new InvalidDataException("Invalid node transform.");
            }
            if(node.TryGetProperty("children",out var children)) foreach(var child in children.EnumerateArray()) if(child.GetInt32()<0 || child.GetInt32()>=nodes.GetArrayLength() || !parents.Add(child.GetInt32())) throw new InvalidDataException("Invalid node hierarchy.");
            if(node.TryGetProperty("mesh",out var mesh)) {
                if(mesh.GetInt32()<0 || mesh.GetInt32()>=meshCount) throw new InvalidDataException("Invalid mesh reference.");
                var component=new ModelComponent{NodeIndex=index,Name=node.TryGetProperty("name",out var name)?(name.GetString()??"Unnamed"):"Unnamed"};
                if((node.TryGetProperty("extras",out var extras)||root.GetProperty("meshes")[mesh.GetInt32()].TryGetProperty("extras",out extras))&&extras.ValueKind==JsonValueKind.Object){
                    if(extras.GetRawText().Length<=16000)component.Metadata=extras.GetRawText();
                    foreach(var key in new[]{"component_id","componentId","id"})if(extras.TryGetProperty(key,out var identity)&&identity.ValueKind is JsonValueKind.String or JsonValueKind.Number){var value=identity.ToString();if(value.Length is >0 and <=500){component.SuppliedId=value;break;}}
                }
                string? suppliedType=null;
                foreach(var source in new[]{node,root.GetProperty("meshes")[mesh.GetInt32()]})
                    if(source.TryGetProperty("extras",out var metadata)&&metadata.ValueKind==JsonValueKind.Object&&metadata.TryGetProperty("elementType",out var supplied)&&supplied.ValueKind==JsonValueKind.String&&ElementTypes.Contains(supplied.GetString()?.Trim().ToLowerInvariant())){suppliedType=supplied.GetString()!.Trim().ToLowerInvariant();break;}
                component.ElementType=suppliedType!=null&&ElementTypes.Contains(suppliedType)?suppliedType:ElementTypes.Where(t=>t!="other").FirstOrDefault(t=>component.Name.Contains(t,StringComparison.OrdinalIgnoreCase))??"other";
                result.Add(component);
            }
            index++;
        }
        var visiting=new HashSet<int>();var visited=new HashSet<int>();
        void Walk(int i,int depth) { if(depth>256 || !visiting.Add(i)) throw new InvalidDataException("Cyclic or overly deep hierarchy."); if(nodes[i].TryGetProperty("children",out var children)) foreach(var ch in children.EnumerateArray()) Walk(ch.GetInt32(),depth+1);visiting.Remove(i);visited.Add(i); }
        for(int i=0;i<nodes.GetArrayLength();i++) if(!visited.Contains(i)) Walk(i,0);
        var scenes=root.GetProperty("scenes");var sceneIndex=root.TryGetProperty("scene",out var active)?active.GetInt32():0;
        if(sceneIndex<0||sceneIndex>=scenes.GetArrayLength())throw new InvalidDataException("Invalid default scene.");
        var reachable=new HashSet<int>();
        void Reach(int i) {if(i<0||i>=nodes.GetArrayLength()||!reachable.Add(i))throw new InvalidDataException("Invalid scene hierarchy.");if(nodes[i].TryGetProperty("children",out var children))foreach(var ch in children.EnumerateArray())Reach(ch.GetInt32());}
        foreach(var node in scenes[sceneIndex].GetProperty("nodes").EnumerateArray())Reach(node.GetInt32());
        result=result.Where(c=>reachable.Contains(c.NodeIndex)).ToList();
        if(result.Count==0) throw new InvalidDataException("No mesh components found.");return result;
    }
    public static async Task<IResult> Persist(string building,string docId,string parentId,string filename,string actor,byte[] bytes,List<ModelComponent> components,PortalDb db,StoragePaths paths) {
            var hash=Convert.ToHexString(SHA256.HashData(bytes));
            await Writes.WaitAsync();try {
                var prior=await db.ModelRevisions.SingleOrDefaultAsync(r=>r.BuildingId==building&&r.DocumentId==docId&&r.Sha256==hash);
                if(prior!=null)return Results.Ok(prior);
                if(parentId.Length>0&&!await db.ModelRevisions.AnyAsync(r=>r.Id==parentId&&r.BuildingId==building&&r.DocumentId==docId))return Bad("Parent revision must use the same project and PDF.");
                Directory.CreateDirectory(Path.Combine(paths.Root,"models"));var path=Artifact(paths,hash);
                if(!File.Exists(path)) { var temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";try {await File.WriteAllBytesAsync(temp,bytes);File.Move(temp,path,false);} finally {if(File.Exists(temp))File.Delete(temp);} }
                await using var transaction=await db.Database.BeginTransactionAsync();
                await db.ModelRevisions.Where(r=>r.BuildingId==building&&r.Active).ExecuteUpdateAsync(s=>s.SetProperty(r=>r.Active,false));
                var revision=new ModelRevision{BuildingId=building,DocumentId=docId,Sha256=hash,OriginalName=Path.GetFileName(filename),Size=bytes.Length,UploadedBy=actor,Active=true,ParentId=parentId.Length>0?parentId:null,ReviewState=parentId.Length>0?"needs-reconciliation":"unverified"};
                db.ModelRevisions.Add(revision);foreach(var component in components){component.RevisionId=revision.Id;db.ModelComponents.Add(component);}await db.SaveChangesAsync();await transaction.CommitAsync();return Results.Ok(revision);
            } finally {Writes.Release();}
    }
    public static async Task ImportLocal(string filename,string documentId,string? parentId,PortalDb db,StoragePaths paths) {
        var doc=await db.Documents.FindAsync(documentId) ?? throw new InvalidDataException("Source document does not exist.");
        var bytes=await File.ReadAllBytesAsync(filename);
        if(bytes.Length>75_000_000)throw new InvalidDataException("GLB exceeds 75 MB.");
        var result=await Persist(doc.BuildingId,doc.Id,parentId??"",filename,"local-maintenance",bytes,Inspect(bytes),db,paths);
        if(result is not Microsoft.AspNetCore.Http.HttpResults.Ok<ModelRevision> ok)throw new InvalidDataException("Import refused; verify parent revision.");
        Console.WriteLine(JsonSerializer.Serialize(new{revision=ok.Value!.Id,document=doc.Id,components=await db.ModelComponents.CountAsync(x=>x.RevisionId==ok.Value.Id)}));
    }
    public static void Map(WebApplication app) {
        app.MapPost("/api/models/{id}/components/batch",async(string id,BatchComponentInput input,HttpContext c,PortalDb db)=>{
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            if(await Accessible(id,c,db)==null)return Results.NotFound();
            if(input.Ids==null||input.Ids.Length is <1 or >500||input.Ids.Distinct().Count()!=input.Ids.Length||input.ElementType!=null&&!ElementTypes.Contains(input.ElementType))return Bad("Supply 1–500 unique component IDs and a supported type.");
            var members=await db.ModelComponents.Where(x=>x.RevisionId==id&&input.Ids.Contains(x.Id)).ToListAsync();
            if(members.Count!=input.Ids.Length)return Bad("All components must belong to this revision.");
            foreach(var member in members){if(input.ElementType!=null)member.ElementType=input.ElementType;if(input.TypeReviewed.HasValue)member.TypeReviewed=input.TypeReviewed.Value;if(input.Hidden.HasValue)member.Hidden=input.Hidden.Value;}
            await db.SaveChangesAsync();return Results.Ok(new{updated=members.Count});
        }).RequireAuthorization();
        app.MapPost("/api/models/{id}/components/{componentId}",async(string id,string componentId,ComponentInput input,HttpContext c,PortalDb db)=>{
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            if(await Accessible(id,c,db)==null)return Results.NotFound();
            var component=await db.ModelComponents.SingleOrDefaultAsync(x=>x.Id==componentId&&x.RevisionId==id);if(component==null)return Results.NotFound();
            if(!ElementTypes.Contains(input.ElementType))return Bad("Choose a supported element type.");
            component.ElementType=input.ElementType;component.TypeReviewed=input.TypeReviewed;component.Hidden=input.Hidden;await db.SaveChangesAsync();return Results.Ok(component);
        }).RequireAuthorization();
        app.MapGet("/api/buildings/{building}/models",async(string building,HttpContext c,PortalDb db)=> {
            if(!await PortalAuth.CanAccess(c.User,db,building))return Results.NotFound();
            return Results.Ok(await db.ModelRevisions.Where(r=>r.BuildingId==building).OrderByDescending(r=>r.CreatedUtc).ToListAsync());
        }).RequireAuthorization();
        app.MapPost("/api/buildings/{building}/models",async(string building,HttpContext c,PortalDb db,StoragePaths paths)=> {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            if(!await PortalAuth.CanAccess(c.User,db,building))return Results.NotFound();
            if(!c.Request.HasFormContentType)return Bad("Choose a GLB and its source PDF.");
            var form=await c.Request.ReadFormAsync();var file=form.Files.GetFile("glb");var docId=form["documentId"].ToString();var parentId=form["parentId"].ToString();
            if(!await db.Documents.AnyAsync(d=>d.Id==docId&&d.BuildingId==building))return Bad("Select a source PDF in this project.");
            if(file==null||file.Length<24||file.Length>75_000_000||!file.FileName.EndsWith(".glb",StringComparison.OrdinalIgnoreCase))return Bad("Choose a GLB up to 75 MB.");
            using var buffer=new MemoryStream();await file.CopyToAsync(buffer);var bytes=buffer.ToArray();List<ModelComponent> components;
            try { components=Inspect(bytes); } catch(Exception e) when(e is InvalidDataException or JsonException or KeyNotFoundException or InvalidOperationException or OverflowException or ArgumentException) {return Bad("GLB validation failed: "+(e is InvalidDataException?e.Message:"Malformed glTF structure."));}
            return await Persist(building,docId,parentId,file.FileName,PortalAuth.UserId(c.User),bytes,components,db,paths);
        }).RequireAuthorization().RequireRateLimiting("upload");
        app.MapGet("/api/models/{id}",async(string id,HttpContext c,PortalDb db)=> {
            var r=await Accessible(id,c,db);if(r==null)return Results.NotFound();
            return Results.Ok(new{revision=r,components=await db.ModelComponents.Where(x=>x.RevisionId==id).ToListAsync(),groups=await db.ModelGroups.Where(x=>x.RevisionId==id).ToListAsync(),notes=await db.ModelNotes.Where(x=>x.RevisionId==id).OrderBy(x=>x.CreatedUtc).ToListAsync(),remaps=await db.ComponentRemaps.Where(x=>x.RevisionId==id).ToListAsync(),parentNotes=r.ParentId==null?new List<ModelNote>():await db.ModelNotes.Where(x=>x.RevisionId==r.ParentId).ToListAsync()});
        }).RequireAuthorization();
        app.MapGet("/api/models/{id}/file",async(string id,HttpContext c,PortalDb db,StoragePaths paths)=> {
            var r=await Accessible(id,c,db);if(r==null)return Results.NotFound();var path=Artifact(paths,r.Sha256);
            return File.Exists(path)?Results.File(path,"model/gltf-binary",r.OriginalName,enableRangeProcessing:true):Results.NotFound();
        }).RequireAuthorization();
        app.MapPost("/api/models/{id}/activate",async(string id,HttpContext c,PortalDb db)=> {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            var r=await Accessible(id,c,db);if(r==null)return Results.NotFound();await Writes.WaitAsync();try {
                await using var tx=await db.Database.BeginTransactionAsync();await db.ModelRevisions.Where(x=>x.BuildingId==r.BuildingId&&x.Active).ExecuteUpdateAsync(s=>s.SetProperty(x=>x.Active,false));
                await db.ModelRevisions.Where(x=>x.Id==id).ExecuteUpdateAsync(s=>s.SetProperty(x=>x.Active,true));await tx.CommitAsync();return Results.Ok();
            }finally{Writes.Release();}
        }).RequireAuthorization();
        app.MapPost("/api/models/{id}/groups",async(string id,GroupInput input,HttpContext c,PortalDb db)=> {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            if(await Accessible(id,c,db)==null)return Results.NotFound();
            if(string.IsNullOrWhiteSpace(input.Name)||input.Name.Length>200||input.Members==null||input.Members.Length==0||input.Members.Length>10000)return Bad("Enter a group name and component IDs.");
            var members=input.Members.Distinct().ToArray();if(await db.ModelComponents.CountAsync(x=>x.RevisionId==id&&members.Contains(x.Id))!=members.Length)return Bad("Group members must belong to this revision.");
            var group=new ModelGroup{RevisionId=id,Name=input.Name,Members=JsonSerializer.Serialize(members)};db.ModelGroups.Add(group);await db.SaveChangesAsync();return Results.Ok(group);
        }).RequireAuthorization();
        app.MapPost("/api/models/{id}/notes",async(string id,NoteInput input,HttpContext c,PortalDb db)=> {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            if(await Accessible(id,c,db)==null)return Results.NotFound();
            if(input.TargetId!=id&&!await db.ModelComponents.AnyAsync(x=>x.Id==input.TargetId&&x.RevisionId==id)&&!await db.ModelGroups.AnyAsync(x=>x.Id==input.TargetId&&x.RevisionId==id))return Bad("Select the model, a component or group in this revision.");
            if(string.IsNullOrWhiteSpace(input.Text)||input.Text.Length>10000||input.Page is <=0 or >100000||new[]{input.Sheet,input.Material,input.TakeoffItem,input.Unit}.Any(s=>s?.Length>500))return Bad("Invalid note or source link.");
            if(!new[]{"unreviewed","needs-review","reviewed","rejected"}.Contains(input.Status)||!new[]{"none","drawing-transcribed","model-calculated","reviewed"}.Contains(input.QuantityBasis))return Bad("Invalid review status or quantity basis.");
            if(input.Quantity is double q&&(!double.IsFinite(q)||q<0||input.QuantityBasis=="none"||string.IsNullOrWhiteSpace(input.Unit)))return Bad("Quantities require a basis and unit.");
            if(input.QuantityBasis!="none"&&input.Quantity==null)return Bad("Enter the quantity or select no quantity.");
            if(input.Region!=null&&(input.Page==null||input.Region.Length!=4||input.Region.Any(v=>!double.IsFinite(v)||v<0||v>1)||input.Region[2]<=0||input.Region[3]<=0||input.Region[0]+input.Region[2]>1||input.Region[1]+input.Region[3]>1))return Bad("Region must be normalized x, y, width, height within the PDF page.");
            var note=new ModelNote{RevisionId=id,TargetId=input.TargetId,Text=input.Text,Page=input.Page,Sheet=input.Sheet,Region=input.Region==null?null:JsonSerializer.Serialize(input.Region),Material=input.Material,TakeoffItem=input.TakeoffItem,Status=input.Status,QuantityBasis=input.QuantityBasis,Quantity=input.Quantity,Unit=input.Unit,Author=PortalAuth.UserId(c.User)};
            db.ModelNotes.Add(note);await db.SaveChangesAsync();return Results.Ok(note);
        }).RequireAuthorization();
        app.MapPost("/api/models/{id}/remaps",async(string id,RemapInput input,HttpContext c,PortalDb db)=> {
            if(!c.User.IsInRole("admin"))return Results.Forbid();
            var r=await Accessible(id,c,db);if(r==null)return Results.NotFound();
            if(r.ParentId==null||string.IsNullOrWhiteSpace(input.Reason)||input.Reason.Length>2000||!await db.ModelComponents.AnyAsync(x=>x.RevisionId==r.ParentId&&x.Id==input.OldComponentId)||!await db.ModelComponents.AnyAsync(x=>x.RevisionId==id&&x.Id==input.NewComponentId))return Bad("Select components from the parent and current revision and document the reason.");
            if(await db.ComponentRemaps.AnyAsync(x=>x.RevisionId==id&&x.OldComponentId==input.OldComponentId))return Results.Conflict(new{message="This component already has a remap. Historical notes remain on the original revision."});
            var map=new ComponentRemap{RevisionId=id,OldComponentId=input.OldComponentId,NewComponentId=input.NewComponentId,Reason=input.Reason};db.ComponentRemaps.Add(map);await db.SaveChangesAsync();return Results.Ok(map);
        }).RequireAuthorization();
        app.MapGet("/api/documents/{id}/view",async(string id,HttpContext c,PortalDb db,StoragePaths paths)=> {
            var d=await db.Documents.FindAsync(id);if(d==null||!await PortalAuth.CanAccess(c.User,db,d.BuildingId))return Results.NotFound();
            c.Response.Headers["X-Frame-Options"]="SAMEORIGIN";c.Response.Headers["Content-Security-Policy"]="default-src 'none'; frame-ancestors 'self'";
            return Results.File(paths.Pdf(id),"application/pdf",enableRangeProcessing:true);
        }).RequireAuthorization();
    }
}
    record GroupInput(string Name,string[] Members);
    record ComponentInput(string ElementType,bool TypeReviewed,bool Hidden);
record NoteInput(string TargetId,string Text,int? Page,string? Sheet,double[]? Region,string? Material,string? TakeoffItem,string Status,string QuantityBasis,double? Quantity,string? Unit);
record RemapInput(string OldComponentId,string NewComponentId,string Reason);
record BatchComponentInput(string[] Ids,string? ElementType,bool? TypeReviewed,bool? Hidden);
