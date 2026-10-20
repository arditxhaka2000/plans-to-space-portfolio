"""Upload latest completed evidence per document using server-only credentials."""
import json, sqlite3, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'worker'))
from cloud_store import publish, publish_exterior
with sqlite3.connect(f"file:{(root/'server/App_Data/saas/portal.db').as_posix()}?mode=ro",uri=True) as db:
    rows=db.execute("""SELECT j.Id,d.Id,d.BuildingId,b.Name,d.OriginalName
        FROM Jobs j JOIN Documents d ON d.Id=j.DocumentId JOIN Buildings b ON b.Id=d.BuildingId
        WHERE j.Status='NeedsReview' AND j.Id=(SELECT j2.Id FROM Jobs j2
        WHERE j2.DocumentId=d.Id AND j2.Status='NeedsReview' ORDER BY julianday(j2.CreatedUtc) DESC LIMIT 1)""").fetchall()
for run,document,project,name,filename in rows:
    out=root/'server/App_Data/saas/jobs'/run
    if not (out/'evidence.sqlite').exists():
        print('Skipped job without evidence:',run,flush=True);continue
    print('Uploading evidence:',run,flush=True)
    try:
        result=publish(out,project,name,document,filename,run)
        result['exteriorRevision']=publish_exterior(out,run)
    except Exception as e:
        print('Upload failed:',type(e).__name__,flush=True);raise SystemExit(1)
    (out/'cloud-status.json').write_text(json.dumps(result),encoding='utf-8')
    print(json.dumps(result),flush=True)
