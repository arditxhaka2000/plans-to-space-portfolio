"""Publish derived exterior revisions for specified already-synced run IDs."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'worker'))
from cloud_store import publish_exterior
if not os.environ.get('PTS_DATABASE_URL'):raise SystemExit('Server-only database connection is not loaded.')
for run in sys.argv[1:]:
    print(run,publish_exterior(root/'server/App_Data/saas/jobs'/run,run))
import psycopg
with psycopg.connect(os.environ['PTS_DATABASE_URL'],sslmode='require',connect_timeout=15) as cloud:
    print('balcony-assembly records',cloud.execute("select count(*) from exterior_components where kind='balcony-assembly'").fetchone()[0])
