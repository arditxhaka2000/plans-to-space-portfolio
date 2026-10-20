"""Attach source-hash-matched evidence to latest completed local document jobs."""
import json,sqlite3,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'work/multifloor-v2'
summary=json.loads((source/'evidence-summary.json').read_text(encoding='utf-8'))
assert summary['integrity']=='ok' and summary['foreignKeyErrors']==0 and summary['pages']==84
with sqlite3.connect(f"file:{root/'server/App_Data/saas/portal.db'}?mode=ro",uri=True) as db:
    rows=db.execute("SELECT j.Id FROM Jobs j JOIN Documents d ON d.Id=j.DocumentId WHERE lower(d.Sha256)=? AND j.Status='NeedsReview' AND j.Id=(SELECT j2.Id FROM Jobs j2 WHERE j2.DocumentId=d.Id AND j2.Status='NeedsReview' ORDER BY j2.CreatedUtc DESC LIMIT 1)",(summary['sourceSha256'].lower(),)).fetchall()
for (jid,) in rows:
    dest=root/'server/App_Data/saas/jobs'/jid
    manifest=json.loads((dest/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['sourceSha256']==summary['sourceSha256']
    for name in ('evidence.sqlite','evidence-summary.json'):
        if (dest/name).exists():raise ValueError('Refusing to overwrite existing evidence')
        shutil.copyfile(source/name,dest/name)
print('Attached evidence to completed document jobs:',len(rows))
