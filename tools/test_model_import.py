"""Integration tests against an isolated portal database and the actual UMD GLB."""
import concurrent.futures, json, os, secrets, struct, subprocess, tempfile, time
from pathlib import Path
import requests
root=Path(__file__).resolve().parents[1]
data=tempfile.mkdtemp(prefix='model-test-',dir=root/'work');base='http://127.0.0.1:5094'
password=os.environ.get('WORKFLOW_TEST_PASSWORD') or secrets.token_urlsafe(24)
env={**os.environ,'ASPNETCORE_ENVIRONMENT':'Development','Saas__DataPath':data,'Saas__AdminEmail':'model@example.test','Saas__AdminPassword':password,'Processing__Enabled':'false','AutomaticPdf__Enabled':'false','Logging__LogLevel__Default':'Warning'}
def start():
    p=subprocess.Popen(['dotnet',os.environ.get('PORTAL_TEST_DLL') or str(root/'work/workflow-build/Flamingo3D.Api.dll'),'--urls',base],cwd=root/'server',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    for _ in range(100):
        try:
            if requests.get(base+'/api/csrf').ok:return p
        except requests.ConnectionError:pass
        time.sleep(.1)
    raise RuntimeError('Service did not start')
def post(s,path,body=None,**kw):return s.post(base+path,json=body,headers={'X-CSRF-TOKEN':s.get(base+'/api/csrf').json()['token']},**kw)
def good(r,code=200):assert r.status_code==code,(r.status_code,r.text[:500]);return r.json() if r.content else None
def changed_glb(raw):
    length=struct.unpack_from('<I',raw,12)[0];j=json.loads(raw[20:20+length]);j['asset']['extras']={'testRevision':True};j['nodes'][0]['extras']={'component_id':'supplied-window-123','material':'supplied unverified'}
    j['nodes'][0],j['nodes'][1]=j['nodes'][1],j['nodes'][0]
    for scene in j['scenes']:scene['nodes']=[1-i if i in (0,1) else i for i in scene['nodes']]
    encoded=json.dumps(j,separators=(',',':')).encode();encoded+=b' '*((-len(encoded))%4);tail=raw[20+length:];return struct.pack('<III',0x46546c67,2,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+tail
proc=start()
try:
    s=requests.Session();good(post(s,'/api/auth/login',{'email':'model@example.test','password':password}))
    b=good(post(s,'/api/admin/buildings',{'name':'GLB integration'}))['id']
    pdf=(root/'work/chatgpt-glb-handoff/pdf-to-glb-handoff/source-pdfs/UMD-Team-reACT-90-percent-construction-set.pdf').read_bytes()
    d=good(post(s,f'/api/buildings/{b}/documents',files={'pdf':('source.pdf',pdf)}))['id']
    pdf_launch=s.get(base+f'/buildings/{b}/model',allow_redirects=False)
    assert pdf_launch.status_code==302 and pdf_launch.headers['Location']==f'/buildings/{b}/documents/{d}/review?view=model'
    assert good(post(s,f'/api/buildings/{b}/documents',files={'pdf':('renamed.pdf',pdf)}))['id']==d
    raw=(root/'work/chatgpt-glb-handoff/pdf-to-glb-handoff/models/UMD-reACT-v2.glb').read_bytes()
    def upload(data,parent=None):return post(s,f'/api/buildings/{b}/models',data={'documentId':d,'parentId':parent or ''},files={'glb':('model.glb',data)})
    r=good(upload(raw));rid=r['id'];detail=good(s.get(base+f'/api/models/{rid}'));assert len(detail['components'])==1090
    component=detail['components'][0]
    good(post(s,f'/api/models/{rid}/components/{component["id"]}',{'elementType':'window','typeReviewed':True,'hidden':False}))
    assert good(s.get(base+f'/api/models/{rid}'))['components'][0]['typeReviewed']
    ids=[c['id'] for c in detail['components']];assert len(set(ids))==1090
    assert len({c['name'] for c in detail['components']})<1090
    assert good(upload(raw))['id']==rid
    assert s.get(base+f'/api/models/{rid}/file').content==raw
    group=good(post(s,f'/api/models/{rid}/groups',{'name':'PV logical group','members':ids[:3]}))
    note={'targetId':group['id'],'text':'Check drawing','page':7,'sheet':'A-102','region':[.1,.2,.3,.4],'material':'PV','takeoffItem':'PV-01','status':'needs-review','quantityBasis':'drawing-transcribed','quantity':3,'unit':'each'}
    good(post(s,f'/api/models/{rid}/notes',note));good(post(s,f'/api/models/{rid}/notes',{**note,'region':[.9,.9,.5,.5]}),400)
    good(post(s,f'/api/models/{rid}/notes',{**note,'quantityBasis':'none'}),400)
    revised=changed_glb(raw);r2=good(upload(revised,rid));id2=r2['id'];new=good(s.get(base+f'/api/models/{id2}'))
    assert new['revision']['reviewState']=='needs-reconciliation' and len(new['parentNotes'])==1 and not new['notes']
    assert not set(ids)&{c['id'] for c in new['components']}
    assert any(c['suppliedId']=='supplied-window-123' for c in new['components'])
    good(post(s,f'/api/models/{id2}/remaps',{'oldComponentId':ids[0],'newComponentId':new['components'][1]['id'],'reason':'Test: explicit reordering of first two nodes; same geometry'}))
    good(post(s,f'/api/models/{rid}/activate',{}));assert next(r for r in good(s.get(base+f'/api/buildings/{b}/models')) if r['active'])['id']==rid
    user=good(post(s,'/api/admin/users',{'email':'other@example.test','password':password}));other=requests.Session();good(post(other,'/api/auth/login',{'email':'other@example.test','password':password}))
    for path in [f'/api/models/{rid}',f'/api/models/{rid}/file',f'/api/buildings/{b}/models',f'/api/documents/{d}/view']:
        good(other.get(base+path),404)
    good(post(other,f'/api/models/{rid}/notes',note),403);good(post(other,f'/api/models/{rid}/activate',{}),403)
    good(post(s,f'/api/models/{id2}/groups',{'name':'bad','members':[ids[0]]}),400)
    assert requests.get(base+f'/api/models/{rid}/file').status_code==401
    assert s.post(base+f'/api/models/{rid}/activate').status_code==400
    assert len(good(s.get(base+f'/api/documents/{d}/jobs')))==1
    assert s.get(base+f'/api/documents/{d}/view').headers['X-Frame-Options']=='SAMEORIGIN'
    good(post(s,'/api/admin/grants',{'buildingId':b,'userId':user['id'],'allow':True}))
    good(post(other,f'/api/buildings/{b}/models',data={'documentId':d},files={'glb':('model.glb',raw)}),403)
    model_launch=s.get(base+f'/buildings/{b}/model',allow_redirects=False)
    assert model_launch.status_code==302 and model_launch.headers['Location'].endswith(f'/documents/{d}/review?view=model')
    def delete(session,bid):return session.delete(base+f'/api/admin/buildings/{bid}',headers={'X-CSRF-TOKEN':session.get(base+'/api/csrf').json()['token']})
    good(delete(other,b),403);good(post(other,f'/api/admin/buildings/{b}/restore',{}),403)
    assert s.delete(base+f'/api/admin/buildings/{b}').status_code==400
    good(delete(s,b));good(delete(s,b))
    assert b not in [item['id'] for item in good(s.get(base+'/api/buildings'))]
    for path in [f'/buildings/{b}',f'/buildings/{b}/model',f'/api/models/{rid}',f'/api/models/{rid}/file',f'/api/documents/{d}/download']:
        good(s.get(base+path),404)
    # Deleting the sample must not recreate it on startup.
    good(delete(s,'flamingo-demo'))
    proc.terminate();proc.wait(10);proc=start()
    assert not good(s.get(base+'/api/buildings'))
    good(post(s,f'/api/admin/buildings/{b}/restore',{}));good(post(s,f'/api/admin/buildings/{b}/restore',{}))
    good(post(s,'/api/admin/buildings/flamingo-demo/restore',{}))
    assert s.get(base+'/buildings/flamingo-demo/model').status_code==200
    assert s.get(base+f'/api/documents/{d}/download').content==pdf
    assert good(s.get(base+f'/api/documents/{d}/jobs'))[0]['status']=='Cancelled'
    print('PASS: unified PDF/GLB launcher, admin-only deletion, CSRF, idempotent delete/undo, hidden workspace/link denial, restart persistence, retained notes/files/grants and Flamingo restoration.')
    persisted=good(s.get(base+f'/api/models/{rid}'));assert persisted['notes'][0]['text']=='Check drawing' and [c['id'] for c in persisted['components']]==ids
    assert s.get(base+f'/api/models/{id2}/file').content==revised
    good(post(s,f'/api/models/{rid}/notes',{**note,'targetId':rid,'text':'Missing roof detail; upload corrected GLB'}))
    assert s.get(base+f'/api/documents/{d}/ai-runs').status_code==404
    import sqlite3
    with sqlite3.connect(Path(data)/'portal.db') as db:assert not db.execute("select 1 from sqlite_master where name='AiRuns'").fetchone()
    assert len(list((Path(data)/'models').glob('*.glb')))==2
    print('PASS: actual 1090-node GLB, repeated names, import/reimport, byte-preserving downloads, revision identity, groups, notes, source regions, quantity provenance, remaps, activation, CSRF, cross-project denial, restart persistence, and no extra PDF jobs.')
    print('Isolated test data:',data)
finally:
    if os.environ.get('WORKFLOW_KEEP_TEST_SERVER'):print('UI test route:',base+f'/buildings/{b}/documents/{d}/review')
    else:proc.terminate();proc.wait(10)
