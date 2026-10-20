const $=s=>document.querySelector(s);
let csrf='',me=null,buildings=[],selected=null;
const notice=message=>$('#notice').textContent=message;
async function token(){const r=await fetch('/api/csrf',{cache:'no-store'});if(!r.ok)throw Error('Portal backend is unavailable. Open the authenticated .NET service, not the static demo.');csrf=(await r.json()).token;}
async function api(url,method='GET',body){
 const headers={};if(method!=='GET')headers['X-CSRF-TOKEN']=csrf;
 if(body && !(body instanceof FormData)){headers['Content-Type']='application/json';body=JSON.stringify(body)}
 const r=await fetch(url,{method,headers,body,cache:'no-store'});
 const text=await r.text();let data;try{data=text?JSON.parse(text):null}catch{data=null}
 if(!r.ok){if(r.status===401&&url!=='/api/auth/login')showLogin();throw Error(data?.message??(r.status===401?'Please sign in.':r.status===403?'You do not have access.':r.status===429?'Too many attempts. Please wait.':'Request failed. Please refresh and try again.'))}
 return data;
}
function showLogin(){me=null;selected=null;history.replaceState(null,'','/login');document.title='Sign in · Plans to Space';$('#login').hidden=false;$('#workspace').hidden=true;$('#logout').hidden=true;$('#identity').textContent='';}
function element(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node}
function button(text,handler){const b=element('button',text);b.type='button';b.onclick=()=>run(handler,b);return b}
async function deleteWorkspace(b){
 if(!confirm(`Delete workspace “${b.name}” from the dashboard? Files and review history will be retained. You can undo this deletion.`))return;
 await token();await api(`/api/admin/buildings/${encodeURIComponent(b.id)}`,'DELETE');
 if(selected?.id===b.id){selected=null;history.replaceState(null,'','/dashboard')}
 await load();notice(`Workspace “${b.name}” deleted. `);
 $('#notice').append(button('Undo',async()=>{await token();await api(`/api/admin/buildings/${encodeURIComponent(b.id)}/restore`,'POST',{});await load();notice('Workspace restored.')}));
}
async function run(fn,b){if(b)b.disabled=true;notice('');try{await fn()}catch(e){notice(e.message)}finally{if(b)b.disabled=false}}
function form(id,handler){$(id).onsubmit=e=>{e.preventDefault();run(()=>handler(new FormData(e.target),e.target),e.submitter)}}
async function load(){
 me=await api('/api/me');await token();$('#identity').textContent=me.email;$('#logout').hidden=false;$('#login').hidden=true;$('#workspace').hidden=false;$('#admin').hidden=me.role!=='admin';
 if(location.pathname==='/login'||location.pathname==='/portal.html')history.replaceState(null,'','/dashboard');
 document.title='Dashboard · Plans to Space';
 buildings=await api('/api/buildings');$('#buildings').replaceChildren();
 for(const b of buildings){const card=element('section',undefined,'card');const actions=element('div',undefined,'workspace-actions');actions.append(button('Open workspace',()=>openBuilding(b)));if(me.role==='admin'){const remove=button('Delete workspace',()=>deleteWorkspace(b));remove.className='delete-workspace';remove.setAttribute('aria-label',`Delete workspace ${b.name}`);actions.append(remove)}card.append(element('h3',b.name),element('p','3D review workspace','muted'),actions);$('#buildings').append(card)}
 if(!buildings.length)$('#buildings').append(element('p','No buildings assigned yet. Contact your administrator.'));
 if(me.role==='admin')await admin();
 if(me.role!=='admin'&&buildings.length===1&&location.pathname==='/dashboard')history.replaceState(null,'',`/buildings/${encodeURIComponent(buildings[0].id)}`);
 const route=location.pathname.match(/^\/buildings\/([^/]+)\/?$/);
 selected=route?buildings.find(b=>b.id===decodeURIComponent(route[1])):null;
 if(selected)await openBuilding(selected,false);else $('#documents').hidden=true;
}
async function openBuilding(b,scroll=true){
 selected=b;$('#documents').hidden=false;$('#building-name').textContent=b.name;$('#viewer').hidden=true;$('#project-files').open=true;$('#upload').hidden=me.role!=='admin';
 if(scroll)history.pushState(null,'',`/buildings/${encodeURIComponent(b.id)}`);
 document.title=b.name+' · Plans to Space';$('#viewer').href=`/buildings/${encodeURIComponent(b.id)}/model`;
 $('#viewer').textContent=`Open ${b.isDemo?'Flamingo':b.name.split('·')[0].trim()} 3D Review Model`;
 $('#building-status').textContent='Loading workspace…';
 const docs=await api(`/api/buildings/${b.id}/documents`);$('#document-list').replaceChildren();
 document.querySelector('#glb-import')?.remove();
 const modelPanel=element('section',undefined,'card');modelPanel.id='glb-import';modelPanel.hidden=me.role!=='admin';modelPanel.append(element('h3','3 · Upload GLB'),element('p','Choose a self-contained GLB in metres, Y up, and its source PDF. Importing a model does not run PDF extraction.'));
 const models=await api(`/api/buildings/${b.id}/models`);const active=models.find(r=>r.active);
 $('#viewer').hidden=!(b.isDemo||models.length);
 $('#building-status').textContent=b.isDemo||models.length?'4 · Open interactive building to review and annotate.':docs.length?'3 · Open PDF context to create a geometry draft, or upload a GLB.':'2 · Building created. Upload its architectural PDF next.';
 if(!b.isDemo&&!active&&!docs.length)$('#project-files').open=true;
 const modelForm=element('form');const pdfSelect=element('select');pdfSelect.name='documentId';pdfSelect.setAttribute('aria-label','Source PDF');for(const d of docs)pdfSelect.add(new Option(d.originalName,d.id));
 const parentSelect=element('select');parentSelect.name='parentId';parentSelect.setAttribute('aria-label','Parent model revision');const parents=()=>{parentSelect.replaceChildren(new Option('New independent model',''));for(const r of models.filter(r=>r.documentId===pdfSelect.value))parentSelect.add(new Option(`Revision ${r.id.slice(0,8)} · ${r.originalName}`,r.id));if(active?.documentId===pdfSelect.value)parentSelect.value=active.id;};pdfSelect.onchange=parents;parents();
 const glb=element('input');glb.type='file';glb.name='glb';glb.accept='.glb';glb.required=true;glb.setAttribute('aria-label','GLB model');const submit=element('button','Import GLB');submit.type='submit';submit.disabled=!docs.length;modelForm.append(pdfSelect,parentSelect,glb,submit);modelPanel.append(modelForm);$('#document-list').after(modelPanel);
 modelForm.onsubmit=e=>{e.preventDefault();run(async()=>{if(!docs.length)throw Error('Upload the source PDF first.');await token();const revision=await api(`/api/buildings/${b.id}/models`,'POST',new FormData(modelForm));location.assign(`/buildings/${b.id}/documents/${revision.documentId}/review?revision=${revision.id}`);},submit)};
 for(const doc of docs){const row=element('div',undefined,'row');const desc=element('div',doc.originalName,'description');desc.append(element('small',`${(doc.size/1024/1024).toFixed(2)} MB · ${doc.status}`));const a=element('a','Download PDF');a.href=`/api/documents/${doc.id}/download`;const review=element('a',models.some(r=>r.documentId===doc.id)?'Open interactive model':'PDF context / create 3D draft');review.href=`/buildings/${b.id}/documents/${doc.id}/review?view=model`;row.append(desc,a,review);$('#document-list').append(row)}
 if(!docs.length)$('#document-list').append(element('p','No PDFs imported yet.','muted'));
 if(scroll)$('#documents').scrollIntoView({block:'start',behavior:'smooth'});
}
async function admin(){
 const users=await api('/api/admin/users');const grants=await api('/api/admin/grants');
 for(const [id,items,key] of [['#grant-user',users.filter(u=>u.role==='client'),'email'],['#grant-building',buildings,'name']]){const select=$(id);select.replaceChildren();for(const item of items){const opt=element('option',item[key]);opt.value=item.id;select.append(opt)}}
 $('#users').replaceChildren();
 for(const u of users){const row=element('div',undefined,'row');const text=element('div',u.email,'description');text.append(element('small',`${u.role} · ${u.disabled?'Disabled':u.deviceEnrolled?'Browser enrolled':'Awaiting first sign-in'}`));row.append(text);
 if(u.id!==me.id)row.append(button('Reset device',async()=>{if(!confirm(`Revoke the current session and allow a new browser for ${u.email}?`))return;await api(`/api/admin/users/${u.id}/reset-device`,'POST',{});await admin()}),button(u.disabled?'Enable':'Disable',async()=>{await api(`/api/admin/users/${u.id}/status`,'POST',{disabled:!u.disabled});await admin()}));$('#users').append(row)}
 $('#grant-list').replaceChildren();for(const g of grants)$('#grant-list').append(element('p',`${users.find(u=>u.id===g.userId)?.email??'User'} → ${buildings.find(b=>b.id===g.buildingId)?.name??'Building'}`,'muted'));
}
form('#login-form',async(d,f)=>{await api('/api/auth/login','POST',{email:d.get('email'),password:d.get('password')});f.reset();await load()});
form('#create-user',async(d,f)=>{await api('/api/admin/users','POST',{email:d.get('email'),password:d.get('password')});f.reset();await admin();notice('Client account created. Assign a building below.')});
form('#create-building',async(d,f)=>{const b=await api('/api/admin/buildings','POST',{name:d.get('name')});f.reset();await load();await openBuilding(b)});
form('#assign',async d=>{await api('/api/admin/grants','POST',{userId:d.get('userId'),buildingId:d.get('buildingId'),allow:d.get('allow')==='on'});await admin();notice('Building access updated.')});
form('#upload',async(d,f)=>{if(!selected)return;const file=d.get('pdf');if(file.size>75000000)throw Error('PDF must be no larger than 75 MB.');const doc=await api(`/api/buildings/${selected.id}/documents`,'POST',d);f.reset();await openBuilding(selected,false);location.assign(`/buildings/${selected.id}/documents/${doc.id}/review`)});
$('#refresh').onclick=()=>run(load);$('#logout').onclick=()=>run(async()=>{await api('/api/auth/logout','POST',{});showLogin();await token()});
const dashboardLink=element('a','Dashboard','button');dashboardLink.href='/dashboard';$('#workspace').prepend(dashboardLink);
window.addEventListener('popstate',()=>run(load));
$('#login-form button').disabled=true;
run(async()=>{await token();try{await load()}catch(e){if(me)throw e;showLogin()}}).finally(()=>$('#login-form button').disabled=false);
