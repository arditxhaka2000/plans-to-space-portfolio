"""Read-only storage audit. Never prints connection strings or exception messages."""
import json, os, sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=root/'server/App_Data/saas'
report={}
db=sqlite3.connect(f'file:{(data/"portal.db").as_posix()}?mode=ro',uri=True)
report['local']={'databaseBytes':(data/'portal.db').stat().st_size,'files':{name:sum(p.stat().st_size for p in (data/name).rglob('*') if p.is_file()) for name in ['pdfs','jobs','models']},'duplicatePdfGroups':db.execute('select Sha256,count(*),sum(Size) from Documents group by Sha256 having count(*)>1').fetchall()}
report['local']['largestArtifacts']=sorted([(p.relative_to(data).as_posix(),p.stat().st_size) for p in (data/'jobs').rglob('*') if p.is_file()],key=lambda r:r[1],reverse=True)[:15]
if os.environ.get('PTS_DATABASE_URL'):
    try:
        import psycopg
        with psycopg.connect(os.environ['PTS_DATABASE_URL'],sslmode='require',connect_timeout=15) as conn:
            conn.read_only=True
            with conn.cursor() as c:
                c.execute('select pg_database_size(current_database())');report['postgres']={'databaseBytes':c.fetchone()[0]}
                c.execute("select schemaname,relname,pg_total_relation_size(relid) from pg_catalog.pg_statio_user_tables order by pg_total_relation_size(relid) desc limit 20");report['postgres']['largestRelations']=c.fetchall()
                c.execute('select sha256,count(*) from building_documents group by sha256 having count(*)>1');report['postgres']['duplicateDocuments']=c.fetchall()
                c.execute('select count(*),coalesce(sum(octet_length(content)),0),count(distinct sha256) from exterior_assets');report['postgres']['exteriorAssetsCountBytesDistinct']=c.fetchone()
                c.execute('select count(*) from drawing_observation_chunks');report['postgres']['rawObservationChunks']=c.fetchone()[0]
                c.execute("select to_regclass('storage.objects')");exists=c.fetchone()[0]
                if exists:
                    c.execute("select bucket_id,count(*),sum(case when metadata->>'size' ~ '^[0-9]+$' then (metadata->>'size')::bigint else 0 end) from storage.objects group by bucket_id");report['objectStorage']=c.fetchall()
                else:report['objectStorage']='storage.objects unavailable'
    except Exception as e:report['remoteErrorType']=type(e).__name__
else:report['remoteAccess']='PTS_DATABASE_URL unavailable'
report['quotaLimit']='Plan limits, billing quota, egress and dashboard warnings are not exposed by this database connection.'
dest=root/'evidence/model-storage-audit.json';dest.write_text(json.dumps(report,indent=2,default=str));print(json.dumps(report,indent=2,default=str))
