"""Real PDF upload-to-artifact test with disposable database and accounts."""
import os, secrets, subprocess, tempfile, time, re, shutil
from pathlib import Path
import requests

root=Path(__file__).resolve().parents[1]
data=tempfile.mkdtemp(prefix='processing-test-',dir=root/'work')
base='http://127.0.0.1:5093'
if os.environ.get('CONTEXT_CACHE_FROM'):
    shutil.copytree(Path(os.environ['CONTEXT_CACHE_FROM'])/'pdf-context-cache',Path(data)/'pdf-context-cache',copy_function=os.link)
password=secrets.token_urlsafe(24)
env={**os.environ,'ASPNETCORE_ENVIRONMENT':'Development','Saas__DataPath':data,'Saas__AdminEmail':'test@example.test','Saas__AdminPassword':password,'Logging__LogLevel__Default':'Warning'}
proc=subprocess.Popen(['dotnet',os.environ.get('PORTAL_TEST_DLL') or str(root/'work/workflow-build/Flamingo3D.Api.dll'),'--urls',base],cwd=root/'server',env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
s=requests.Session()
def post(path,**kwargs):
    token=s.get(base+'/api/csrf').json()['token']
    r=s.post(base+path,headers={'X-CSRF-TOKEN':token},**kwargs);r.raise_for_status();return r
try:
    for _ in range(100):
        try:
            if s.get(base+'/api/csrf').status_code==200:break
        except requests.ConnectionError:pass
        time.sleep(.1)
    post('/api/auth/login',json={'email':'test@example.test','password':password})
    bid=post('/api/admin/buildings',json={'name':'UMD context processing test'}).json()['id']
    with open(root/'work/chatgpt-glb-handoff/pdf-to-glb-handoff/source-pdfs/UMD-Team-reACT-90-percent-construction-set.pdf','rb') as pdf:
        did=post(f'/api/buildings/{bid}/documents',files={'pdf':('UMD.pdf',pdf,'application/pdf')}).json()['id']
    deadline=time.monotonic()+2700
    while time.monotonic()<deadline:
        j=s.get(base+f'/api/documents/{did}/jobs').json()[0]
        if j['status'] not in ('Queued','Running'):break
        time.sleep(2)
    assert j['status']=='NeedsReview',j
    asset=base+f"/api/jobs/{j['id']}/files/"
    m=s.get(asset+'manifest.json').json()
    assert m['summary']['pageCount']==62
    assert not (Path(data)/'jobs'/j['id']/'model.json').exists()
    assert requests.get(asset+'manifest.json').status_code==401
    assert s.get(asset+'pages/062.json').status_code==200
    assert not (Path(data)/'jobs'/j['id']/'exterior.json').exists()
    html=s.get(base+f'/buildings/{bid}/documents/{did}/review').text
    for url in re.findall(r'(?:src|href)="(/portal/[^\"]+)"',html):
        assert requests.get(base+url).status_code==200,url
    print('PASS real upload -> background worker -> private artifacts:',m['summary'])
    print('PASS complete page inventory, private access and generic review dependencies')
finally:
    proc.terminate();proc.wait(timeout=10)
    print('Test artifacts retained:',data)
