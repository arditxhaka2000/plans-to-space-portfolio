"""Register a local run against an existing cloud document, then publish exterior data.

Used when the lossless observation upload is already present on an earlier run for
the same immutable document and a later active attempt only needs its derived
exterior revision registered. Identity checks prevent cross-document attachment.
"""
import json,os,sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'worker'))
from cloud_store import publish_exterior

run,document=sys.argv[1:3]
out=root/'server/App_Data/saas/jobs'/run
manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
with psycopg.connect(os.environ['PTS_DATABASE_URL'],sslmode='require',connect_timeout=15) as cloud:
    row=cloud.execute('select sha256 from building_documents where id=%s',(document,)).fetchone()
    if not row or row[0]!=manifest['sourceSha256']:
        raise ValueError('Existing cloud document identity mismatch')
    previous=cloud.execute('select document_id from processing_runs where id=%s',(run,)).fetchone()
    if previous and previous[0]!=document:raise ValueError('Run identity mismatch')
    if not previous:
        cloud.execute('insert into processing_runs(id,document_id,status,pipeline_version,summary) values(%s,%s,%s,%s,%s)',
            (run,document,'NeedsReview',manifest['pipelineVersion'],Jsonb(manifest['summary'])))
print(run,publish_exterior(out,run))
