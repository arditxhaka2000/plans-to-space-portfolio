"""Seed an explicitly authored model review, idempotently, into local storage."""
import argparse, datetime, hashlib, json, sqlite3, uuid
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('review');p.add_argument('--data',required=True);a=p.parse_args();review=json.loads(Path(a.review).read_text());data=Path(a.data);digest=review['sha256'].upper();assert hashlib.sha256((data/'models'/f'{digest}.glb').read_bytes()).hexdigest().upper()==digest
db=sqlite3.connect(data/'portal.db');db.execute('pragma foreign_keys=on');revisions=db.execute('select Id from ModelRevisions where Sha256=?',(digest,)).fetchall();assert revisions
with db:
    for (revision,) in revisions:
        components=dict(db.execute('select NodeIndex,Id from ModelComponents where RevisionId=?',(revision,)))
        key=lambda value:uuid.uuid5(uuid.NAMESPACE_URL,revision+':'+value).hex
        for group in review.get('groups',[]):
            db.execute('insert into ModelGroups(Id,RevisionId,Name,Members) values(?,?,?,?) on conflict(Id) do nothing',(key(group['key']),revision,group['name'],json.dumps([components[n] for n in group['nodes']])))
        for note in review['notes']:
            db.execute('insert into ModelNotes(Id,RevisionId,TargetId,Text,Page,Sheet,Status,QuantityBasis,Author,CreatedUtc) values(?,?,?,?,?,?,?,?,?,?) on conflict(Id) do nothing',(key(note['key']),revision,components[note['node']],note['text'],note['page'],note['sheet'],'needs-review','none','local-model-review',datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat(' ')))
print('Review notes and groups saved; existing annotations preserved.')
