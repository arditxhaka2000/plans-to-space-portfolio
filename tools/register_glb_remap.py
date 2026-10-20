"""Local maintenance: register an explicit, checksum-bound correction manifest.
Uses the existing private portal DB; does not infer identity from node ordering.
"""
import argparse, hashlib, json, sqlite3, uuid
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--data',required=True);a=p.parse_args();data=Path(a.data);manifest=json.loads(Path(a.manifest).read_text());db=sqlite3.connect(data/'portal.db');db.execute('pragma foreign_keys=on')
source=manifest['sourceSha256'].upper();target=manifest['revisionSha256'].upper()
for digest in [source,target]:assert hashlib.sha256((data/'models'/f'{digest}.glb').read_bytes()).hexdigest().upper()==digest
targets=db.execute('select Id,ParentId from ModelRevisions where Sha256=?',(target,)).fetchall();assert targets,'Import the corrected GLB first'
with db:
    for revision,parent in targets:
        assert db.execute('select Sha256 from ModelRevisions where Id=?',(parent,)).fetchone()==(source,),'Parent checksum mismatch'
        old=dict(db.execute('select NodeIndex,Id from ModelComponents where RevisionId=?',(parent,)));new=dict(db.execute('select NodeIndex,Id from ModelComponents where RevisionId=?',(revision,)))
        assert len(manifest['nodeRemaps'])==len(old)
        for row in manifest['nodeRemaps']:
            reason=row['kind']+': '+manifest['description']
            db.execute('insert into ComponentRemaps(Id,RevisionId,OldComponentId,NewComponentId,Reason) values(?,?,?,?,?) on conflict(RevisionId,OldComponentId) do nothing',(uuid.uuid4().hex,revision,old[row['oldNode']],new[row['newNode']],reason))
print('Registered checksum-bound component remaps without moving historical notes.')
