import * as THREE from 'three';

import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';

import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';

type Revision={id:string;documentId:string;originalName:string;active:boolean;parentId:string|null;reviewState:string;sha256:string};

type Component={id:string;nodeIndex:number;name:string;suppliedId:string|null;metadata:string;elementType:string;typeReviewed:boolean;hidden:boolean};

type Note={id:string;targetId:string;text:string;page:number|null;sheet:string|null;region:string|null;material:string|null;takeoffItem:string|null;status:string;quantityBasis:string;quantity:number|null;unit:string|null};

type Detail={revision:Revision;components:Component[];groups:{id:string;name:string;members:string}[];notes:Note[];parentNotes:Note[];remaps:{oldComponentId:string;newComponentId:string;reason:string}[]};

const $=<T extends HTMLElement>(s:string)=>document.querySelector<T>(s)!;

async function api(url:string,body?:unknown){const headers:Record<string,string>={};if(body!==undefined){headers['X-CSRF-TOKEN']=(await (await fetch('/api/csrf')).json()).token;if(!(body instanceof FormData))headers['Content-Type']='application/json'}const r=await fetch(url,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:body instanceof FormData?body:JSON.stringify(body)});if(!r.ok){if(r.status===401)location.assign('/login');throw Error((await r.json().catch(()=>null))?.message??`Request failed (${r.status})`)}const text=await r.text();return text?JSON.parse(text):null;}

function tag<K extends keyof HTMLElementTagNameMap>(name:K,text?:string){const n=document.createElement(name);if(text)n.textContent=text;return n;}

export async function importedReview(ctx:{building:string;documentId:string;scene:THREE.Scene;geometry:THREE.Group;canvas:HTMLCanvasElement;controls:OrbitControls;setCamera:(camera:THREE.PerspectiveCamera|THREE.OrthographicCamera)=>void}):Promise<boolean>{

 const revisions:Revision[]=await api(`/api/buildings/${ctx.building}/models`);const relevant=revisions.filter(r=>r.documentId===ctx.documentId);if(!relevant.length)return false;

 $('#results').hidden=false;$('#progress').hidden=true;

 $('#drawing-panel').hidden=false;$('#viewer-layout').classList.add('comparing');$('#toggle-source').setAttribute('aria-expanded','true');$('#toggle-source').textContent='Hide drawing';

 $('.model-card h2').textContent='Interactive model review';$('.preview-notice').textContent='Model geometry · metres · Y up. Drawing accuracy is unverified. Model measurements are not reviewed takeoff quantities.';



 const frame=tag('iframe');frame.title='Original source PDF';frame.style.cssText='width:100%;height:65vh;border:1px solid #d1ddd4';$('#drawing-panel').append(frame);

 const sourceLink=tag('a','Open original PDF');sourceLink.target='_blank';sourceLink.rel='noopener';$('#drawing-panel').append(sourceLink);

 const page=tag('input');page.type='number';page.min='1';page.value='1';page.setAttribute('aria-label','PDF page');const pageButton=tag('button','Show PDF page');const sourceTools=tag('div');sourceTools.className='toolbar';sourceTools.append(page,pageButton);frame.before(sourceTools);

 function showPage(n:number){page.value=String(n);frame.src=`/api/documents/${ctx.documentId}/view?page=${n}#page=${n}&view=Fit&navpanes=0`;sourceLink.href=frame.src;window.dispatchEvent(new CustomEvent("pdf-page-selected",{detail:n}));}pageButton.onclick=()=>showPage(Math.max(1,Number(page.value)||1));showPage(1);

 const bar=tag('div');bar.className='toolbar';const select=tag('select');select.setAttribute('aria-label','Model revision');for(const [i,r]of relevant.entries())select.add(new Option(`${relevant.length-i} · ${r.originalName}${r.active?' · active':''}`,r.id));

 const activate=tag('button','Set active revision'),download=tag('a','Download original GLB');bar.append(select,activate,download);$('.processing').prepend(bar);

 const inspector=tag('section');inspector.className='card';inspector.id='model-inspector';const title=tag('h2','Components & review notes');const search=tag('input');search.placeholder='Filter component names';search.setAttribute('aria-label','Filter components');const targets=tag('select');targets.size=8;targets.multiple=true;targets.style.width='100%';targets.setAttribute('aria-label','Components and groups');const hide=tag('button','Hide selected'),show=tag('button','Show all'),groupName=tag('input'),group=tag('button','Group selected components');groupName.placeholder='Logical group name';groupName.setAttribute('aria-label','Group name');const actions=tag('div');actions.className='toolbar';actions.append(hide,show,groupName,group);inspector.append(title,search,targets,actions);$('.model-card').append(inspector);

 const form=tag('form');form.innerHTML='<label>Note<textarea name="text" required maxlength="10000" rows="3"></textarea></label><div class="split"><label>PDF page<input name="page" type="number" min="1"></label><label>Sheet<input name="sheet" maxlength="500" placeholder="A-102"></label><label>Region: x, y, width, height (0–1)<input name="region" placeholder="0.1,0.2,0.3,0.4"></label><label>Material reference<input name="material" maxlength="500"></label><label>Takeoff item reference<input name="takeoffItem" maxlength="500"></label><label>Review status<select name="status"><option>unreviewed</option><option>needs-review</option><option>reviewed</option><option>rejected</option></select></label><label>Quantity basis<select name="quantityBasis"><option value="none">No quantity</option><option>drawing-transcribed</option><option>model-calculated</option><option>reviewed</option></select></label><label>Quantity<input name="quantity" type="number" min="0" step="any"></label><label>Unit<input name="unit" maxlength="500" placeholder="m, m², each"></label></div><button>Save note on selected model/component/group</button>';

 const optional=tag('details');optional.append(tag('summary','Region and quantity details'));for(const name of ['region','takeoffItem','quantityBasis','quantity','unit']){const label=form.querySelector(`[name="${name}"]`)?.closest('label');if(label)optional.append(label)}form.insertBefore(optional,form.lastElementChild);
 const notes=tag('div');inspector.append(form,notes);const reconciliation=tag('details');reconciliation.append(tag('summary','Parent notes & component reconciliation'));const history=tag('div');reconciliation.append(history);inspector.append(reconciliation);

 const componentInfo=tag('p'),metadataView=tag('pre'),typeSelect=tag('select'),reviewed=tag('input'),saveType=tag('button','Save component type');

 typeSelect.setAttribute('aria-label','Element type');for(const value of ['window','door','wall','roof','slab','column','railing','solar panel','other'])typeSelect.add(new Option(value,value));reviewed.type='checkbox';const reviewedLabel=tag('label','Type reviewed ');reviewedLabel.append(reviewed);inspector.insertBefore(componentInfo,search);inspector.insertBefore(typeSelect,search);inspector.insertBefore(reviewedLabel,search);inspector.insertBefore(saveType,search);inspector.insertBefore(metadataView,search);

 const me=await api('/api/me'),isAdmin=me.role==='admin';form.hidden=!isAdmin;group.hidden=!isAdmin;groupName.hidden=!isAdmin;activate.hidden=!isAdmin;saveType.hidden=!isAdmin;typeSelect.disabled=!isAdmin;reviewed.disabled=!isAdmin;

 const style=tag('style');style.textContent='#model-inspector input,#model-inspector textarea{display:block;width:100%;padding:8px;border:1px solid #c1d3c8;border-radius:5px;font:inherit}#model-inspector label{display:block;margin:8px 0}#model-inspector select[multiple]{min-height:180px}#model-inspector .toolbar input{width:220px}#model-inspector form{margin-top:16px}';document.head.append(style);

 let detail:Detail,root:THREE.Group|null=null,objects=new Map<string,THREE.Object3D[]>(),box=new THREE.Box3(),camera:THREE.PerspectiveCamera|THREE.OrthographicCamera;let selectionBox:THREE.Box3Helper|null=null;

 const guarded=(fn:()=>Promise<void>)=>async()=>{try{$('#error').textContent='';await fn()}catch(e){$('#error').textContent=e instanceof Error?e.message:String(e)}};

 function fit(direction='3d') {const size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3()),span=Math.max(size.x,size.y,size.z,.1),aspect=ctx.canvas.clientWidth/Math.max(1,ctx.canvas.clientHeight);const vector=direction==='top'?new THREE.Vector3(0,1,.0001):direction==='-Z'?new THREE.Vector3(0,0,-1):direction==='+Z'?new THREE.Vector3(0,0,1):direction==='+X'?new THREE.Vector3(1,0,0):direction==='-X'?new THREE.Vector3(-1,0,0):new THREE.Vector3(1,.7,1).normalize();

  if(direction==='3d'){camera=new THREE.PerspectiveCamera(45,aspect,span/10000,span*100);camera.position.copy(center).addScaledVector(vector,span*1.55/Math.min(aspect,1));}

  else {const h=span*1.25/Math.min(aspect,1);camera=new THREE.OrthographicCamera(-h*aspect/2,h*aspect/2,h/2,-h/2,span/10000,span*100);camera.position.copy(center).addScaledVector(vector,span*3);}

  ctx.controls.object=camera;ctx.controls.target.copy(center);camera.lookAt(center);ctx.controls.update();ctx.setCamera(camera);

 }

 const viewBar=$('#orbit').parentElement!;for(const [label,direction]of [['−Z elevation','-Z'],['+Z elevation','+Z'],['+X elevation','+X'],['−X elevation','-X']]){const b=tag('button',label);b.onclick=()=>fit(direction);viewBar.append(b)}

 // Cardinal orientation is not inferred from mesh coordinates. These are exact orthographic axis views.

 $('#orbit').onclick=()=>fit();$('#fit').onclick=()=>fit();$('#top').onclick=()=>fit('top');$('#export-glb').hidden=true;

 function selected(){return Array.from(targets.selectedOptions).map(o=>o.value)}

 function targetObjects(id:string):THREE.Object3D[]{const g=detail.groups.find(g=>g.id===id);return g?(JSON.parse(g.members) as string[]).flatMap(id=>objects.get(id)??[]):objects.get(id)??[];}

 function highlight(){if(!detail)return;if(selectionBox){ctx.scene.remove(selectionBox);selectionBox.geometry.dispose();(selectionBox.material as THREE.Material).dispose();selectionBox=null;}const b=new THREE.Box3();for(const id of selected())for(const o of targetObjects(id))b.union(new THREE.Box3().setFromObject(o));if(!b.isEmpty()){selectionBox=new THREE.Box3Helper(b,0xd68d22);ctx.scene.add(selectionBox);}const component=detail.components.find(c=>c.id===selected()[0]),logical=detail.groups.find(g=>g.id===selected()[0]);
 $('#picked').textContent=component?.name??logical?.name??'Select a component';
 componentInfo.textContent=component?`${component.name} | ID ${component.suppliedId??component.id} | ${component.typeReviewed?'Reviewed type':'Unverified type suggestion'} | ${detail.notes.some(n=>n.targetId===component.id&&(n.page||n.sheet))?'See source links below':'Evidence link: unassigned'}`:logical?'Logical group: '+logical.name:'Select a component or group';
 const members=logical?detail.components.filter(c=>(JSON.parse(logical.members) as string[]).includes(c.id)):component?[component]:[];typeSelect.value=members.length&&members.every(c=>c.elementType===members[0].elementType)?members[0].elementType:'other';reviewed.checked=members.length>0&&members.every(c=>c.typeReviewed);metadataView.textContent=component&&component.metadata!=='{}'?JSON.stringify(JSON.parse(component.metadata),null,2):'';renderNotes();}

 function renderTargets(reveal?:string){if(!detail)return;const keep=reveal?[reveal]:selected();targets.replaceChildren();const term=search.value.toLowerCase();const all=[{id:detail.revision.id,name:'Whole model / missing geometry issue'},...detail.groups.map(g=>({id:g.id,name:'Group · '+g.name})),...detail.components];const matches=all.filter(t=>t.name.toLowerCase().includes(term)||t.id.includes(term));const visible=new Map(matches.slice(0,500).map(t=>[t.id,t]));for(const t of all)if(keep.includes(t.id))visible.set(t.id,t);for(const t of visible.values()){const opt=new Option(`${t.name} · ${t.id.slice(0,8)}`,t.id);opt.selected=keep.includes(t.id);targets.add(opt)}search.title=`${matches.length} matches; showing first 500. Filter to find additional components.`;}


 function renderNotes(){if(!detail)return;notes.replaceChildren();const inherited=detail.parentNotes.filter(n=>detail.remaps.some(m=>m.oldComponentId===n.targetId&&selected().includes(m.newComponentId)));for(const n of [...detail.notes.filter(n=>selected().includes(n.targetId)),...inherited]){const historical=inherited.includes(n);const p=tag('p',`${historical?'Parent revision reference (identity mapped; recheck): ':''}${n.text} | ${n.status}${n.material?' | material: '+n.material:''}${n.takeoffItem?' | takeoff: '+n.takeoffItem:''}${n.quantity!==null?` | ${n.quantity} ${n.unit} (${n.quantityBasis})`:''}`);if(n.page){const b=tag('button',`PDF ${n.page} ${n.sheet??''}${n.region?' | region '+n.region:''}`);b.onclick=()=>showPage(n.page!);p.append(b)}notes.append(p)}}

 saveType.onclick=guarded(async()=>{if(selected().length!==1)throw Error('Select one component or logical group.');const logical=detail.groups.find(g=>g.id===selected()[0]);const ids=logical?JSON.parse(logical.members) as string[]:selected();const members=detail.components.filter(c=>ids.includes(c.id));if(!members.length)throw Error('Choose a component or group to classify.');await batch(members.map(c=>c.id),{elementType:typeSelect.value,typeReviewed:reviewed.checked});await metadata();highlight()});

 async function metadata(){detail=await api(`/api/models/${select.value}`);renderTargets();renderNotes();history.replaceChildren();reconciliation.hidden=!detail.revision.parentId;for(const n of detail.parentNotes){const map=detail.remaps.find(m=>m.oldComponentId===n.targetId);history.append(tag('p',`${n.targetId}: ${n.text} · ${map?'Remapped to '+map.newComponentId+'; source note remains historical.':'Needs reconciliation; not transferred.'}`))}if(detail.revision.parentId&&isAdmin){const old=tag('input'),reason=tag('input'),save=tag('button','Map parent component to selected component');old.placeholder='Parent component ID';old.setAttribute('aria-label','Parent component ID');reason.placeholder='Evidence / reason for identity mapping';reason.setAttribute('aria-label','Mapping reason');save.type='button';save.onclick=guarded(async()=>{if(selected().length!==1)throw Error('Select one current component.');await api(`/api/models/${select.value}/remaps`,{oldComponentId:old.value,newComponentId:selected()[0],reason:reason.value});await metadata()});history.append(old,reason,save)}}

 function loading(value:boolean){select.disabled=value;activate.disabled=value;for(const control of inspector.querySelectorAll<HTMLInputElement|HTMLSelectElement|HTMLButtonElement|HTMLTextAreaElement>('input,select,button,textarea'))control.disabled=value;}

 async function load(){loading(true);try{await metadata();const gltf=await new GLTFLoader().loadAsync(`/api/models/${select.value}/file`);if(root){ctx.geometry.remove(root);const resources=new Set<{dispose:()=>void}>();root.traverse(o=>{if(o instanceof THREE.Mesh){resources.add(o.geometry);for(const m of Array.isArray(o.material)?o.material:[o.material]){resources.add(m);for(const v of Object.values(m))if(v instanceof THREE.Texture)resources.add(v)}}});resources.forEach(r=>r.dispose());}root=gltf.scene;objects=new Map();const byNode=new Map(detail.components.map(c=>[c.nodeIndex,c.id]));root.traverse(o=>{let current:THREE.Object3D|null=o;while(current){const index=gltf.parser.associations.get(current)?.nodes;if(index!==undefined&&byNode.has(index)){const id=byNode.get(index)!;o.userData.reviewComponentId=id;if(o instanceof THREE.Mesh)objects.set(id,[...(objects.get(id)??[]),o]);break;}current=current.parent;}});ctx.geometry.add(root);box=new THREE.Box3().setFromObject(root);if(box.isEmpty())throw Error('GLB has no visible geometry in its default scene.');fit();highlight();$('#status').textContent=`${detail.components.length} components · ${detail.revision.reviewState==='ai-draft'?'unverified':detail.revision.reviewState} · ${detail.revision.active?'active revision':'historical revision'}`;download.href=`/api/models/${select.value}/file`;if(detail.components.length===1)$('#status').textContent+=' - Single mesh: individual windows, doors and other architectural parts are unavailable; no segmentation is performed.';for(const c of detail.components)for(const o of objects.get(c.id)??[])o.visible=!c.hidden;}finally{loading(false);typeSelect.disabled=!isAdmin;reviewed.disabled=!isAdmin;}}

 const requested=new URLSearchParams(location.search).get('revision');select.value=(relevant.find(r=>r.id===requested)??relevant.find(r=>r.active)??relevant[0]).id;select.onchange=guarded(load);activate.onclick=guarded(async()=>{await api(`/api/models/${select.value}/activate`,{});await metadata();$('#status').textContent='Active revision saved.'});

 async function batch(ids:string[],patch:{elementType?:string;typeReviewed?:boolean;hidden?:boolean}){const unique=[...new Set(ids)];for(let i=0;i<unique.length;i+=500)await api(`/api/models/${select.value}/components/batch`,{ids:unique.slice(i,i+500),...patch});}
 targets.onchange=highlight;search.oninput=()=>{renderTargets();highlight()};hide.onclick=guarded(async()=>{const ids=new Set<string>();for(const id of selected())for(const o of targetObjects(id))ids.add(o.userData.reviewComponentId);if(isAdmin)await batch([...ids],{hidden:true});for(const id of ids)for(const o of objects.get(id)??[])o.visible=false;for(const c of detail.components)if(ids.has(c.id))c.hidden=true;highlight()});show.onclick=guarded(async()=>{if(isAdmin)await batch(detail.components.filter(c=>c.hidden).map(c=>c.id),{hidden:false});root?.traverse(o=>o.visible=true);for(const c of detail.components)c.hidden=false;});

 group.onclick=guarded(async()=>{await api(`/api/models/${select.value}/groups`,{name:groupName.value,members:selected()});await metadata()});

 form.onsubmit=e=>{e.preventDefault();void guarded(async()=>{if(selected().length!==1)throw Error('Select the whole model, one component or logical group for this note.');const data=new FormData(form),v=(s:string)=>String(data.get(s)??'').trim();await api(`/api/models/${select.value}/notes`,{targetId:selected()[0],text:v('text'),page:v('page')?Number(v('page')):null,sheet:v('sheet')||null,region:v('region')?v('region').split(',').map(Number):null,material:v('material')||null,takeoffItem:v('takeoffItem')||null,status:v('status'),quantityBasis:v('quantityBasis'),quantity:v('quantity')?Number(v('quantity')):null,unit:v('unit')||null});await metadata();$('#status').textContent='Note saved.';})()};

 let down=[0,0];ctx.canvas.onpointerdown=e=>{down=[e.clientX,e.clientY]};ctx.canvas.onpointerup=e=>{if(Math.hypot(e.clientX-down[0],e.clientY-down[1])>4||!root)return;const r=ctx.canvas.getBoundingClientRect(),ray=new THREE.Raycaster();ray.setFromCamera(new THREE.Vector2((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2),camera);const hit=ray.intersectObject(root,true).find(h=>{let o:THREE.Object3D|null=h.object;while(o){if(!o.visible)return false;o=o.parent}return true});if(hit){const id=hit.object.userData.reviewComponentId;search.value='';renderTargets(detail.groups.find(g=>(JSON.parse(g.members) as string[]).includes(id))?.id??id);highlight()}};

 await load();return true;

}

