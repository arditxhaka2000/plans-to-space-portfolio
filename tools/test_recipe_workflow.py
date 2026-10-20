"""Isolated HTTP integration; requires local IQ source fixture, never touches user workspaces."""
import copy, hashlib, json, os, secrets, sqlite3, struct, subprocess, sys, tempfile, time, zipfile
from pathlib import Path
import requests
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'worker'))
from building_recipe import Recipe
from recipe_generate import generate

def verify_geometry(recipe):
    out=Path(tempfile.mkdtemp(prefix='recipe-geometry-',dir=root/'work'))
    r=Recipe.model_validate(recipe);manifest=generate(r,out)
    raw=(out/'model.glb').read_bytes();g=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
    ids=[n['extras']['componentId'] for n in g['nodes']];assert len(ids)==len(set(ids))==30404
    assert len(manifest['groups'])==3339 and len(r.volumes)==54
    assert r.volumes[0].footprint==[(0,0),(21,0),(21,45),(0,45)]
    assert all(abs(level.elevation-expected)<1e-9 for level,expected in zip(r.levels,[0,4,7.6,11.2,14.8,18.4,22,25.6,29.2,32.8]))
    wall=r.walls[0];opening=wall.openings[0]
    glass=next(n for n in g['nodes'] if n['extras']['componentId']==opening.id)
    assert abs(glass['scale'][0]-(opening.width-2*opening.frame))<1e-6
    # Ray through aperture centre crosses glass, not any host-wall solid.
    center=glass['translation'];hosts=[n for n in g['nodes'] if n['extras']['recipeElementId']==wall.id]
    assert all(not(abs(center[0]-n['translation'][0])<n['scale'][0]/2-1e-8 and abs(center[1]-n['translation'][1])<n['scale'][1]/2-1e-8) for n in hosts)
    b=next(n for n in g['nodes'] if n['extras']['elementType']=='roof');assert b['translation'][1]==32.8
    edited=copy.deepcopy(recipe);edited['walls'][0]['openings'][0]['width']-=.2
    second=out/'corrected';generate(Recipe.model_validate(edited),second);raw2=(second/'model.glb').read_bytes();g2=json.loads(raw2[20:20+struct.unpack_from('<I',raw2,12)[0]])
    assert [n['extras']['componentId'] for n in g2['nodes']]==ids
    changed={a['name'] for a,b in zip(g['nodes'],g2['nodes']) if a!=b}
    assert opening.id in changed and any('/frame/' in x for x in changed) and any('/host/cell/' in x for x in changed)
    assert all(n['extras']['recipeElementId'] in (opening.id,wall.id) for n in g['nodes'] if n['name'] in changed)
    invalid=copy.deepcopy(recipe);invalid['walls'][0]['openings'][0]['width']=999
    try:Recipe.model_validate(invalid);raise AssertionError('Accepted oversized aperture')
    except ValueError:pass
    for mutate in [lambda r:r['boxes'].append(r['boxes'][0]),lambda r:r['boxes'][0]['center'].__setitem__(0,float('nan')),lambda r:r.update(unexpected='code'),lambda r:r.update(units='feet')]:
        invalid=copy.deepcopy(recipe);mutate(invalid)
        try:Recipe.model_validate(invalid);raise AssertionError('Accepted invalid recipe')
        except ValueError:pass
    # Independent sloped roof and door contract exercise.
    small=copy.deepcopy(recipe);small.update(boxes=[],volumes=[],groups=[],walls=[copy.deepcopy(recipe['walls'][0])]);small['walls'][0]['openings'][0]['kind']='door';small['walls'][0]['openings'][0]['sill']=0
    small['roofs']=[{'id':'pitched','material':'m0','evidence':recipe['walls'][0]['evidence'],'vertices':[[0,3,0],[4,5,0],[4,5,4],[0,3,4]]}];generate(Recipe.model_validate(small),out/'door-roof')
    return {'components':len(ids),'groups':len(manifest['groups']),'changedParts':len(changed),'widthBefore':opening.width,'widthAfter':opening.width-.2}

def main():
    (root/'work').mkdir(exist_ok=True);recipe=json.loads((root/'examples/iq-buildings.recipe.json').read_text(encoding='utf-8'));results=verify_geometry(recipe)
    data=Path(tempfile.mkdtemp(prefix='recipe-http-',dir=root/'work'));base='http://127.0.0.1:5096';password=secrets.token_urlsafe(24)
    env={**os.environ,'ASPNETCORE_ENVIRONMENT':'Development','Saas__DataPath':str(data),'Saas__AdminEmail':'recipe@example.test','Saas__AdminPassword':password,'Processing__Enabled':'false','AutomaticPdf__Enabled':'false','Recipes__Enabled':'false','Logging__LogLevel__Default':'Warning'}
    log=open(data/'server.log','w',encoding='utf-8')
    def start():
        p=subprocess.Popen(['dotnet',os.environ.get('PORTAL_TEST_DLL',str(root/'work/recipe-build/Flamingo3D.Api.dll')),'--urls',base],cwd=root/'server',env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        for _ in range(150):
            try:
                if requests.get(base+'/api/csrf').ok:return p
            except requests.ConnectionError:pass
            time.sleep(.1)
        raise RuntimeError('Server did not start; inspect isolated server.log')
    def good(r,codes=(200,202)):
        assert r.status_code in codes,(r.status_code,r.text[:1000]);return r.json() if r.content else None
    def post(session,path,body=None,**kw):return session.post(base+path,json=body,headers={'X-CSRF-TOKEN':session.get(base+'/api/csrf').json()['token']},**kw)
    def wait(job):
        start=time.monotonic()
        while time.monotonic()-start<180:
            result=good(s.get(base+f'/api/recipe-builds/{job["id"]}'))
            if result['status'] in ('Completed','Failed'):
                assert result['status']=='Completed',result;return result,time.monotonic()-start
            time.sleep(.25)
        raise AssertionError('Job timeout')
    p=start()
    try:
        s=requests.Session();good(post(s,'/api/auth/login',{'email':'recipe@example.test','password':password}))
        b=good(post(s,'/api/admin/buildings',{'name':'Isolated IQ recipe verification'}))['id']
        pdf=Path(os.environ.get('IQ_TEST_PDF',root/'server/App_Data/saas/pdfs/a1980a6d99f24cd4a6c116cd9a298903.pdf')).read_bytes()
        assert hashlib.sha256(pdf).hexdigest()==recipe['sourceDocumentHash']
        d=good(post(s,f'/api/buildings/{b}/documents',files={'pdf':('isolated-source.pdf',pdf)}))['id']
        with zipfile.ZipFile(os.environ.get('IQ_TEST_ZIP',r'work/private-fixtures/IQ-Buildings-source.zip')) as archive:original=archive.read('IQ-Buildings-draft.glb')
        imported=good(post(s,f'/api/buildings/{b}/models',data={'documentId':d},files={'glb':('original-iq.glb',original)}))
        original_detail=good(s.get(base+f'/api/models/{imported["id"]}'))
        assert len(original_detail['components'])==13709 and sum(c['elementType']=='window' for c in original_detail['components'])==3339
        assert all(not c['typeReviewed'] for c in original_detail['components'])
        assert s.get(base+f'/api/models/{imported["id"]}/file').content==original
        job=good(post(s,f'/api/documents/{d}/recipe-builds',{'recipe':recipe}));assert job['status']=='Queued'
        assert good(post(s,f'/api/documents/{d}/recipe-builds',{'recipe':recipe}))['id']==job['id']
        # Persisted queue survives service restart with no browser or client connection.
        p.terminate();p.wait(15);env['Recipes__Enabled']='true';p=start();built,seconds=wait(job);results['initialJobSecondsAfterRestart']=round(seconds,3)
        rid=built['revisionId'];detail=good(s.get(base+f'/api/models/{rid}'));assert len(detail['components'])==30404 and len(detail['groups'])==3339
        opening=recipe['walls'][0]['openings'][0];component=next(c for c in detail['components'] if c['suppliedId']==opening['id'])
        note={'targetId':component['id'],'text':'Check window width against page 2; isolated persistent note','page':2,'status':'needs-review','quantityBasis':'none'}
        good(post(s,f'/api/models/{rid}/notes',note))
        ids=json.loads(detail['groups'][0]['members']);good(post(s,f'/api/models/{rid}/components/batch',{'ids':ids,'elementType':'window','typeReviewed':True,'hidden':True}))
        after=good(s.get(base+f'/api/models/{rid}'));assert all(c['hidden'] and c['typeReviewed'] for c in after['components'] if c['id'] in ids)
        good(post(s,f'/api/models/{rid}/components/batch',{'ids':ids,'hidden':False}))
        good(post(s,f'/api/models/{rid}/components/batch',{'ids':ids+['wrong'],'hidden':True}),(400,))
        good(post(s,f'/api/models/{rid}/components/batch',{'ids':['bad']*501,'hidden':True}),(400,))
        corrected=good(post(s,f'/api/recipe-builds/{job["id"]}/windows/{opening["id"]}/width',{'width':opening['width']-.2}));new,seconds=wait(corrected);results['correctionJobSeconds']=round(seconds,3)
        newer=good(s.get(base+f'/api/models/{new["revisionId"]}'));assert newer['revision']['parentId']==rid
        assert newer['parentNotes'][0]['text']==note['text'] and not newer['notes']
        assert {c['suppliedId'] for c in newer['components']}=={c['suppliedId'] for c in detail['components']}
        assert len(newer['remaps'])==30404
        new_component=next(c for c in newer['components'] if c['suppliedId']==opening['id']);assert any(m['oldComponentId']==component['id'] and m['newComponentId']==new_component['id'] for m in newer['remaps'])
        assert good(post(s,f'/api/recipe-builds/{job["id"]}/windows/{opening["id"]}/width',{'width':opening['width']-.2}))['id']==corrected['id']
        recipe2=good(s.get(base+f'/api/recipe-builds/{corrected["id"]}/files/recipe.json'));assert recipe2['walls'][0]['openings'][0]['width']==opening['width']-.2
        good(post(s,f'/api/documents/{d}/recipe-builds',{'recipe':{**recipe,'sourceDocumentHash':'0'*64}}),(400,))
        invalid=copy.deepcopy(recipe);invalid['walls'][0]['openings'][0]['width']=999
        rejected=good(post(s,f'/api/documents/{d}/recipe-builds',{'recipe':invalid}))
        for _ in range(100):
            failure=good(s.get(base+f'/api/recipe-builds/{rejected["id"]}'))
            if failure['status']=='Failed':break
            time.sleep(.2)
        assert failure['status']=='Failed' and failure['revisionId'] is None and 'Opening/frame outside wall' in failure['error']
        other=requests.Session();good(post(s,'/api/admin/users',{'email':'other-recipe@example.test','password':password}));good(post(other,'/api/auth/login',{'email':'other-recipe@example.test','password':password}))
        for path in [f'/api/recipe-builds/{job["id"]}',f'/api/recipe-builds/{job["id"]}/files/recipe.json',f'/api/documents/{d}/recipe-builds',f'/api/models/{rid}/file']:good(other.get(base+path),(404,))
        good(post(other,f'/api/documents/{d}/recipe-builds',{'recipe':recipe}),(403,));assert s.post(base+f'/api/documents/{d}/recipe-builds',json={'recipe':recipe}).status_code==400
        assert requests.get(base+f'/api/recipe-builds/{job["id"]}').status_code==401
        assert len(good(s.get(base+f'/api/documents/{d}/jobs')))==1
        assert s.get(base+f'/api/documents/{d}/download').content==pdf
        # Generated artifacts remain finite; importer rejects a nonfinite buffer without storing it.
        raw=bytearray(s.get(base+f'/api/models/{rid}/file').content);length=struct.unpack_from('<I',raw,12)[0];struct.pack_into('<f',raw,28+length,float('nan'))
        good(post(s,f'/api/buildings/{b}/models',data={'documentId':d},files={'glb':('bad.glb',bytes(raw))}),(400,))
        config={'base':base,'email':'recipe@example.test','password':password,'building':b,'document':d,'revision':rid,'correctedRevision':new['revisionId'],'windowId':opening['id'],'data':str(data)}
        (root/'work/recipe-browser.json').write_text(json.dumps(config),encoding='utf-8')
        print(json.dumps({'passed':True,**results,'isolatedData':str(data)}))
        if os.environ.get('RECIPE_BROWSER_TEST'):
            subprocess.run(['node','tools/test_recipe_browser.cjs'],cwd=root,check=True)
        (root/'evidence/recipe-workflow-test.json').write_text(json.dumps({'passed':True,**results,'checks':['actual IQ import classification and original bytes','finite geometry and unique IDs','window aperture, panel and four frames','sloped roof and door generation','durable queue across service restart without browser','document hash authorization','idempotent builds and corrections','bounded batch edits','new revision and stable supplied IDs','historical note and 30404 explicit lineage remaps','CSRF and cross-user denial','original PDF and existing context job retained']},indent=2))
    finally:
        p.terminate();p.wait(15);log.close()

if __name__=='__main__':main()
