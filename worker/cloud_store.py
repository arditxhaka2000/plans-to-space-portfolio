"""Transactional, server-only Supabase/Postgres evidence upload.

Credentials come from PTS_DATABASE_URL, never CLI arguments or browser code.
All page observations are retained in lossless compressed chunks.
"""
import argparse
import gzip
import hashlib
import json
import os
import sqlite3
from pathlib import Path


def exterior_reference(out, data):
    """Archive the full analysis locally; Postgres receives queryable metadata."""
    digest=hashlib.sha256(data).hexdigest()
    directory=out/'artifacts';directory.mkdir(exist_ok=True)
    path=directory/(digest+'.json')
    if not path.exists():
        with path.open('xb') as archive:archive.write(data)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Archive checksum mismatch')
    payload=json.loads(data)
    assets=[]
    for elevation in payload.get('elevations',[]):
        appearance=elevation.get('appearance')
        if not appearance:continue
        original=(out/appearance['asset']).resolve()
        if not original.is_relative_to(out.resolve()):raise ValueError('Invalid appearance path')
        content=original.read_bytes();sha=hashlib.sha256(content).hexdigest()
        if sha!=appearance['sha256']:raise ValueError('Appearance checksum mismatch')
        archive=directory/(sha+'.png')
        if not archive.exists():
            with archive.open('xb') as f:f.write(content)
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=sha:raise ValueError('Appearance archive checksum mismatch')
        assets.append({'originalPath':appearance['asset'],'artifact':'artifacts/'+sha+'.png','sha256':sha,'bytes':len(content)})
    return {'format':'exterior-artifact-reference-v1','artifact':'artifacts/'+digest+'.json','sha256':digest,'bytes':len(data),'sourceSha256':payload.get('sourceSha256'),'elevationCount':len(payload.get('elevations',[])),'assets':assets}


def elevation_reference(elevation, reference):
    return {**reference,'page':elevation['page'],'direction':elevation.get('direction'),'regionCount':len(elevation.get('regions',[])),'appearance':elevation.get('appearance')}


def chunks(db, page, size=1000):
    cursor=db.execute('select * from observation where page=? order by id',(page,))
    while rows:=cursor.fetchmany(size):
        yield len(rows),gzip.compress(json.dumps([dict(r) for r in rows],separators=(',',':')).encode(),mtime=0)


def publish_exterior(out,run):
    import psycopg
    from psycopg.types.json import Jsonb
    path=out/'exterior.json'
    if not path.exists():return
    data=path.read_bytes();payload=json.loads(data)
    digest=hashlib.sha256(data).hexdigest()
    reference=exterior_reference(out,data)
    with psycopg.connect(os.environ['PTS_DATABASE_URL'],sslmode='require',connect_timeout=15) as remote:
        with remote.cursor() as c:
            c.execute('select d.sha256 from processing_runs r join building_documents d on d.id=r.document_id where r.id=%s',(run,))
            row=c.fetchone()
            if not row or row[0]!=payload['sourceSha256']:raise ValueError('Exterior source identity mismatch')
            c.execute('insert into exterior_models(run_id,revision_sha256,status,complete,payload) values(%s,%s,%s,%s,%s) on conflict do nothing',
                (run,digest,payload.get('shell',{}).get('status','analysis-only') if payload.get('shell') else 'analysis-only',False,Jsonb(reference)))
            # Exterior revisions are often rebuilt after the evidence-first upload.
            # Keep the normalized elevation rows in sync as well as the JSON model;
            # otherwise older runs can have a model but zero queryable elevations.
            for elevation in payload.get('elevations',[]):
                c.execute('insert into exterior_elevations(run_id,page,direction,payload) values(%s,%s,%s,%s) '
                    'on conflict(run_id,page) do nothing',
                    (run,elevation['page'],elevation.get('direction'),Jsonb(elevation_reference(elevation,reference))))
            for element in (payload.get('shell') or {}).get('elements',[]):
                c.execute('insert into exterior_components(run_id,id,kind,source_page,geometry,verification) values(%s,%s,%s,%s,%s,%s) on conflict do nothing',
                    (run,digest+':'+element['id'],element['kind'],element['sourcePage'],Jsonb(element),element['verification']))
            for elevation in payload.get('elevations',[]):
                appearance=elevation.get('appearance')
                if not appearance:continue
                asset=(out/appearance['asset']).resolve()
                if not asset.is_relative_to(out.resolve()):raise ValueError('Invalid appearance path')
                content=asset.read_bytes()
                if hashlib.sha256(content).hexdigest()!=appearance['sha256']:raise ValueError('Appearance checksum mismatch')
                # The payload already preserves asset path and checksum, and the
                # authenticated job-file route serves the private local artifact.
                # Do not duplicate PNG bytes into Postgres by default.
                if os.environ.get('PTS_STORE_BINARY_ASSETS')=='1':
                    c.execute('insert into exterior_assets(run_id,revision_sha256,asset_path,sha256,mime_type,content) values(%s,%s,%s,%s,%s,%s) on conflict do nothing',
                        (run,digest,appearance['asset'],appearance['sha256'],'image/png',content))
    return digest


def publish(out, project, project_name, document, filename, run):
    import psycopg
    from psycopg.types.json import Jsonb
    connection=os.environ.get('PTS_DATABASE_URL')
    if not connection:raise ValueError('PTS_DATABASE_URL is not configured; evidence remains local.')
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    exterior=json.loads((out/'exterior.json').read_text(encoding='utf-8')) if (out/'exterior.json').exists() else {'elevations':[]}
    exterior_ref=exterior_reference(out,(out/'exterior.json').read_bytes()) if (out/'exterior.json').exists() else None
    local=sqlite3.connect(f'file:{(out/"evidence.sqlite").as_posix()}?mode=ro',uri=True);local.row_factory=sqlite3.Row
    try:
        with psycopg.connect(connection,sslmode='require',connect_timeout=15) as remote:
            with remote.cursor() as c:
                c.execute('insert into building_projects(id,name) values(%s,%s) on conflict(id) do update set name=excluded.name',(project,project_name))
                c.execute('insert into building_documents(id,project_id,sha256,filename) values(%s,%s,%s,%s) on conflict(id) do nothing',(document,project,manifest['sourceSha256'],filename))
                c.execute('select project_id,sha256 from building_documents where id=%s',(document,))
                if c.fetchone()!=(project,manifest['sourceSha256']):raise ValueError('Document identity mismatch')
                c.execute('select document_id from processing_runs where id=%s',(run,))
                previous=c.fetchone()
                if previous:
                    if previous[0]!=document:raise ValueError('Run identity mismatch')
                    return {'status':'already-uploaded','run':run}
                c.execute('insert into processing_runs(id,document_id,status,pipeline_version,summary) values(%s,%s,%s,%s,%s)',
                    (run,document,'NeedsReview',manifest['pipelineVersion'],Jsonb(manifest['summary'])))
                total=0
                store_raw=os.environ.get('PTS_STORE_RAW_OBSERVATIONS')=='1'
                for page in local.execute('select * from page order by number'):
                    p=dict(page);n=p['number']
                    c.execute('insert into drawing_sheets values(%s,%s,%s,%s,%s,%s,%s)',(run,n,p['sheet_code'],p['title'],p['role'],p['full_text'],Jsonb({k:v for k,v in p.items() if k!='full_text'})))
                    if store_raw:
                        for index,(count,data) in enumerate(chunks(local,n)):
                            total+=count
                            c.execute('insert into drawing_observation_chunks values(%s,%s,%s,%s,%s,%s)',(run,n,index,'gzip+json',count,data))
                for table,destination in [('extracted_table','drawing_tables'),('coverage','drawing_coverage')]:
                    for row in local.execute(f'select * from {table}'):
                        d=dict(row)
                        if table=='coverage':c.execute('insert into drawing_coverage values(%s,%s,%s)',(run,d['page'],Jsonb(d)))
                        else:c.execute('insert into drawing_tables values(%s,%s,%s,%s)',(run,d['page'],d['id'],Jsonb(d)))
                for row in local.execute('select * from fact'):
                    d=dict(row);c.execute('insert into drawing_facts values(%s,%s,%s,%s)',(run,d['id'],d['kind'],Jsonb(d)))
                for row in local.execute('select * from sheet_reference'):
                    d=dict(row);c.execute('insert into drawing_references values(%s,%s,%s)',(run,d['id'],Jsonb(d)))
                for i,d in enumerate(manifest['materials']):c.execute('insert into exterior_materials values(%s,%s,%s)',(run,i,Jsonb(d)))
                for i,d in enumerate(manifest['issues']):c.execute('insert into validation_issues values(%s,%s,%s)',(run,i,Jsonb(d)))
                for e in exterior['elevations']:
                    c.execute('insert into exterior_elevations values(%s,%s,%s,%s)',(run,e['page'],e['direction'],Jsonb(elevation_reference(e,exterior_ref))))
                expected=local.execute('select count(*) from observation').fetchone()[0]
                if store_raw:
                    if total!=expected:raise ValueError('Observation coverage mismatch')
                    c.execute('select coalesce(sum(observation_count),0) from drawing_observation_chunks where run_id=%s',(run,))
                    if c.fetchone()[0]!=expected:raise ValueError('Remote observation count mismatch')
                # Historical evidence is retained. Cleanup requires a separately reviewed migration.
        return {'status':'uploaded','run':run,'observations':total,'sourceObservations':expected,'rawObservationStorage':'cloud' if store_raw else 'local-only','pages':len(manifest['sheets'])}
    finally:local.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('output','project','project-name','document','filename','run'):p.add_argument('--'+name,required=True)
    args=p.parse_args()
    try:
        result=publish(Path(args.output),args.project,args.project_name,args.document,args.filename,args.run)
        result['exteriorRevision']=publish_exterior(Path(args.output),args.run)
        (Path(args.output)/'cloud-status.json').write_text(json.dumps(result),encoding='utf-8')
        print(json.dumps(result))
    except Exception as error:
        # Connection exceptions may contain credentials; never print their messages.
        result={'status':'not-uploaded','errorType':type(error).__name__,'message':'Cloud upload failed; local evidence is preserved. Check server-only database configuration.'}
        (Path(args.output)/'cloud-status.json').write_text(json.dumps(result),encoding='utf-8')
        print(json.dumps(result));raise SystemExit(1)
