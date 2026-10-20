import * as THREE from 'three';
import {OrbitControls} from 'three/examples/jsm/controls/OrbitControls.js';
import {pdfDraftOption} from './pdf-draft';
import {importedReview} from './imported-review';
import {recipeReview} from './recipe-review';
import {automaticReview} from './automatic-review';
const $=<T extends HTMLElement>(s:string)=>document.querySelector<T>(s)!;
const route=location.pathname.match(/^\/buildings\/([^/]+)\/documents\/([^/]+)\/review\/?$/)!;
const [,building,documentId]=route;
$<HTMLAnchorElement>('#back').href=`/buildings/${building}`;
async function get(url:string){const r=await fetch(url);if(r.status===401)location.assign('/login');if(!r.ok)throw Error('Content unavailable or access denied.');return r.json()}
const canvas=$<HTMLCanvasElement>('canvas'),scene=new THREE.Scene(),geometry=new THREE.Group();scene.add(geometry);scene.background=new THREE.Color('#edf1ee');
scene.add(new THREE.HemisphereLight(0xffffff,0x697568,2.5));const sun=new THREE.DirectionalLight(0xffffff,3);sun.position.set(20,40,30);scene.add(sun);
let camera:THREE.PerspectiveCamera|THREE.OrthographicCamera=new THREE.PerspectiveCamera(45,1,.01,10000);
const renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.SRGBColorSpace;
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;
new ResizeObserver(()=>{const w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;renderer.setSize(w,h,false);if(camera instanceof THREE.PerspectiveCamera)camera.aspect=w/h;else{const span=camera.top-camera.bottom;camera.left=-span*w/h/2;camera.right=span*w/h/2}camera.updateProjectionMatrix()}).observe(canvas);
renderer.setAnimationLoop(()=>{controls.update();renderer.render(scene,camera)});
$('#toggle-source').onclick=()=>{const hidden=!$('#drawing-panel').hidden;$('#drawing-panel').hidden=hidden;$('#viewer-layout').classList.toggle('comparing',!hidden);$('#toggle-source').textContent=hidden?'Show PDF context':'Hide PDF context'};
async function context(){
 const box=document.createElement('section');box.className='card';box.innerHTML='<h2>PDF context</h2><p>Extracted text is source evidence, not a reviewed component link. Assign references in component notes.</p><p class="context-status"></p><select aria-label="PDF context page"></select><input aria-label="Search this page" placeholder="Search this page"><pre style="white-space:pre-wrap;max-height:32vh;overflow:auto"></pre>';
 $('#drawing-panel').append(box);const select=box.querySelector('select')!,search=box.querySelector('input')!,pre=box.querySelector('pre')!;let text='';
 const flags=document.createElement('details'),flagTitle=document.createElement('summary'),flagList=document.createElement('div');flags.append(flagTitle,flagList);box.append(flags);
 search.oninput=()=>{const term=search.value.toLowerCase();pre.textContent=term?text.split('\n').filter(l=>l.toLowerCase().includes(term)).join('\n'):text};
 const refresh=async()=>{try{const jobs=await get(`/api/documents/${documentId}/jobs`),job=jobs.find((j:{status:string})=>j.status==='NeedsReview');
 if(!job){box.querySelector('.context-status')!.textContent=jobs[0]?.error??jobs[0]?.stage??'PDF context not processed.';if(jobs.some((j:{status:string})=>['Queued','Running'].includes(j.status)))setTimeout(refresh,3000);
 else if(!box.querySelector('.retry-context')&&(await get('/api/me')).role==='admin'){const retry=document.createElement('button');retry.className='retry-context';retry.textContent='Retry PDF context';retry.onclick=async()=>{try{retry.disabled=true;const token=await get('/api/csrf');const response=await fetch(`/api/documents/${documentId}/process`,{method:'POST',headers:{'X-CSRF-TOKEN':token.token}});if(!response.ok)throw Error('Could not restart PDF context processing.');retry.remove();await refresh()}catch(e){box.querySelector('.context-status')!.textContent=String(e);retry.disabled=false}};box.append(retry)}return}
 const base=`/api/jobs/${job.id}/files/`,manifest=await get(base+'manifest.json');box.querySelector('.context-status')!.textContent=`${manifest.sheets.length} pages · extracted, unverified`;
 for(const sheet of manifest.sheets)select.add(new Option(`${sheet.page} · ${sheet.code??'Sheet ID unassigned'} · ${sheet.title}`,sheet.evidence));
 const preview=document.createElement('img');preview.alt='Selected PDF page';preview.style.cssText='width:100%;height:auto';box.prepend(preview);const pdfFrame=$<HTMLIFrameElement>('#drawing-panel iframe');if(pdfFrame){pdfFrame.hidden=true;pdfFrame.src='about:blank'}window.addEventListener('pdf-page-selected',((event:CustomEvent<number>)=>{const sheet=manifest.sheets.find((s:{page:number})=>s.page===event.detail);if(sheet){select.value=sheet.evidence;select.dispatchEvent(new Event('change'))}}) as EventListener);
 const pdfToggle=document.createElement('button');pdfToggle.textContent='Open PDF viewer here';preview.before(pdfToggle);let currentPage=1;
 pdfToggle.onclick=()=>{if(!pdfFrame)return;pdfFrame.hidden=!pdfFrame.hidden;preview.hidden=!pdfFrame.hidden;pdfToggle.textContent=pdfFrame.hidden?'Open PDF viewer here':'Show page preview';if(!pdfFrame.hidden)pdfFrame.src=`/api/documents/${documentId}/view#page=${currentPage}&view=Fit`};
 select.onchange=async()=>{try{const data=await get(base+select.value);text=data.text??'';search.dispatchEvent(new Event('input'));const sheet=manifest.sheets.find((s:{page:number})=>s.page===data.page);preview.src=base+sheet.preview;
 const uncertain=(data.observations??[]).filter((r:{reviewFlags?:string[]})=>r.reviewFlags?.length);flagTitle.textContent=`${uncertain.length} text observations need review`;flagList.replaceChildren();for(const r of uncertain){const line=document.createElement('p');line.textContent=`${r.text} — ${r.reviewFlags.join(', ')} · PDF bounds ${r.bounds.map((n:number)=>n.toFixed(1)).join(', ')}`;flagList.append(line)}
 currentPage=data.page;const pageInput=$<HTMLInputElement>('#drawing-panel input[aria-label="PDF page"]');if(pageInput)pageInput.value=String(data.page);const sourceLink=$<HTMLAnchorElement>('#drawing-panel a[target="_blank"]');if(sourceLink)sourceLink.href=`/api/documents/${documentId}/view#page=${data.page}`;
 const frame=$<HTMLIFrameElement>('#drawing-panel iframe');if(frame&&!frame.hidden)frame.src=`/api/documents/${documentId}/view#page=${data.page}&view=Fit`; }catch(e){pre.textContent=String(e)}};select.dispatchEvent(new Event('change'));
 }catch(e){box.querySelector('.context-status')!.textContent=String(e)}};await refresh();
}
(async()=>{try{
 const hasModel=await importedReview({building,documentId,scene,geometry,canvas,controls,setCamera:c=>{camera=c}});
 if(!hasModel){
 $('#results').hidden=false;$('#progress').hidden=true;$('.model-card').hidden=true;$('#drawing-panel').hidden=false;
 $('#status').textContent='Your PDF is available. Model generation runs separately in the background.';
 const link=document.createElement('a');link.href=`/buildings/${building}`;link.textContent='Upload GLB';$('.processing').append(link);
 const frame=document.createElement('iframe');frame.title='Original PDF';frame.src=`/api/documents/${documentId}/view`;frame.style.cssText='width:100%;height:65vh';$('#drawing-panel').append(frame);
 }await recipeReview(documentId);await automaticReview(documentId,hasModel);
 const legacy=document.createElement('details');legacy.className='card';legacy.id='legacy-pdf-assessment';const legacyTitle=document.createElement('summary');legacyTitle.textContent='Optional: limited automatic PDF massing assessment';legacy.append(legacyTitle);$('.processing').after(legacy);
 let assessmentOpened=false;legacy.ontoggle=()=>{if(legacy.open&&!assessmentOpened){assessmentOpened=true;void pdfDraftOption(building,documentId,legacy)}};
 await context();
 }catch(e){$('#error').textContent=String(e);$('#progress').hidden=true}})();
