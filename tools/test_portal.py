"""Local integration tests; disposable accounts/database, no real client data."""
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
import requests

root=Path(__file__).resolve().parents[1]
data=tempfile.mkdtemp(prefix='portal-test-',dir=root/'work')
base='http://127.0.0.1:5092'
password=secrets.token_urlsafe(24)
env={**os.environ,'ASPNETCORE_ENVIRONMENT':'Development','Saas__DataPath':data,
     'Saas__AdminEmail':'admin@example.test','Saas__AdminPassword':password,
     'Logging__LogLevel__Default':'Warning','Processing__Enabled':'false'}

def start():
    proc=subprocess.Popen(['dotnet',os.environ.get('PORTAL_TEST_DLL') or str(root/'work/workflow-build/Flamingo3D.Api.dll'),'--urls',base],cwd=root/'server',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    for _ in range(80):
        try:
            if requests.get(base+'/api/csrf').status_code==200:return proc
        except requests.ConnectionError:pass
        if proc.poll() is not None:raise RuntimeError('Test service failed to start')
        time.sleep(.1)
    proc.terminate();raise RuntimeError('Test startup timeout')

def csrf(s):return s.get(base+'/api/csrf').json()['token']
def post(s,path,obj=None,**kw):
    return s.post(base+path,json=obj,headers={'X-CSRF-TOKEN':csrf(s)},**kw)
def login(s,email):return post(s,'/api/auth/login',{'email':email,'password':password})
def check(response,status,label):
    assert response.status_code==status,(label,response.status_code,response.text[:300])
    print('PASS',label)

proc=start()
try:
    admin=requests.Session();a=requests.Session();b=requests.Session();anon=requests.Session()
    check(anon.get(base+'/api/buildings'),401,'anonymous API denied')
    check(anon.get(base+'/login'),200,'clean login route')
    assert anon.get(base+'/portal.html',allow_redirects=False).headers['Location']=='/login'
    assert anon.get(base+'/dashboard',allow_redirects=False).headers['Location']=='/login'
    print('PASS legacy login redirect and protected dashboard')
    check(anon.get(base+'/FLOORS.html',allow_redirects=False),302,'case-variant static viewer protected')
    check(anon.post(base+'/api/auth/login',json={'email':'admin@example.test','password':password}),400,'login requires CSRF')
    check(login(admin,'admin@example.test'),200,'administrator login')
    admin_second=requests.Session()
    check(login(admin_second,'admin@example.test'),200,'administrator login from another browser')
    check(admin.get(base+'/api/me'),200,'first administrator browser remains signed in')
    check(admin.get(base+'/dashboard'),200,'authenticated dashboard')
    check(admin.get(base+'/buildings/flamingo-demo/model'),200,'clean model route')
    ua=post(admin,'/api/admin/users',{'email':'a@example.test','password':password}).json()
    ub=post(admin,'/api/admin/users',{'email':'b@example.test','password':password}).json()
    building=post(admin,'/api/admin/buildings',{'name':'Private test building'}).json()
    bid=building['id']
    check(post(admin,'/api/admin/grants',{'buildingId':bid,'userId':ua['id'],'allow':True}),200,'building assignment')
    check(login(a,'a@example.test'),200,'client first browser enrollment')
    check(login(b,'b@example.test'),200,'second client login')
    check(a.get(base+'/api/admin/users'),403,'client cannot administer')
    check(b.get(base+f'/api/buildings/{bid}/documents'),404,'unassigned building hidden')
    check(a.get(base+'/floors.html'),404,'unassigned Flamingo viewer denied')
    check(a.get(base+f'/buildings/{bid}'),200,'assigned building direct refresh')
    check(b.get(base+f'/buildings/{bid}'),404,'unassigned building page denied')
    check(login(requests.Session(),'a@example.test'),409,'second browser rejected')
    check(login(a,'b@example.test'),409,'second account on enrolled browser rejected')
    saved=requests.Session();saved.cookies.update(a.cookies)
    check(login(a,'a@example.test'),200,'same browser can sign in again')
    check(saved.get(base+'/api/me'),401,'prior session revoked')
    pdf=b'%PDF-1.4\n% harmless test fixture\n%%EOF'
    check(post(a,f'/api/buildings/{bid}/documents',files={'pdf':('denied.pdf',pdf,'application/pdf')}),403,'client upload denied')
    response=post(admin,f'/api/buildings/{bid}/documents',files={'pdf':('test.pdf',pdf,'application/pdf')})
    check(response,200,'administrator PDF upload');doc=response.json()
    jobs=a.get(base+f"/api/documents/{doc['id']}/jobs").json()
    assert len(jobs)==1 and jobs[0]['status']=='Queued'
    jid=jobs[0]['id']
    check(b.get(base+f"/api/documents/{doc['id']}/jobs"),404,'cross-client jobs denied')
    check(a.get(base+f"/buildings/{bid}/documents/{doc['id']}/review"),200,'generic review route')
    check(b.get(base+f"/buildings/{bid}/documents/{doc['id']}/review"),404,'cross-client review denied')
    check(post(admin,f'/api/jobs/{jid}/cancel',{}),200,'queued job cancelled')
    check(post(admin,f"/api/documents/{doc['id']}/process",{}),200,'new extraction version queued')
    check(post(admin,f"/api/documents/{doc['id']}/process",{}),409,'duplicate active job rejected')
    check(b.get(base+f"/api/documents/{doc['id']}/download"),404,'cross-client download denied')
    assert a.get(base+f"/api/documents/{doc['id']}/download").content==pdf
    print('PASS original PDF bytes preserved')
    check(post(admin,f'/api/buildings/{bid}/documents',files={'pdf':('bad.pdf',b'not a PDF file','application/pdf')}),400,'non-PDF header rejected')
    proc.terminate();proc.wait(timeout=10);proc=start()
    check(a.get(base+'/api/me'),200,'session survives service restart')
    assert len(a.get(base+f'/api/buildings/{bid}/documents').json())==1
    print('PASS database and document metadata survive restart')
    check(post(admin,f"/api/admin/users/{ua['id']}/reset-device",{}),200,'administrator device reset')
    check(a.get(base+'/api/me'),401,'device reset revokes session')
    fresh=requests.Session();check(login(fresh,'a@example.test'),200,'replacement browser enrollment')
    check(post(admin,'/api/admin/grants',{'buildingId':bid,'userId':ua['id'],'allow':False}),200,'assignment revoked')
    check(fresh.get(base+f"/api/documents/{doc['id']}/download"),404,'revocation immediately removes PDF access')
    check(post(admin,f"/api/admin/users/{ub['id']}/status",{'disabled':True}),200,'account disabled')
    check(b.get(base+'/api/me'),401,'disabled account session rejected')
    print('ALL PORTAL INTEGRATION CHECKS PASSED')
finally:
    proc.terminate();proc.wait(timeout=10)
    print('Disposable test data retained at',data)
