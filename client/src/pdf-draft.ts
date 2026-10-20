import * as THREE from 'three';
import {GLTFExporter} from 'three/examples/jsm/exporters/GLTFExporter.js';

// Coordinates come from the source-vector assessment, never text reading order.
export function footprintDraft(points:number[][],heights:number[],source:Record<string,unknown>){
 if(points.length<3||points.length>40||heights.length<1||heights.length>60)throw Error('Use 3–40 footprint vertices and 1–60 floor heights.');
 if(points.some(p=>p.length!==2||p.some(v=>!Number.isFinite(v)||Math.abs(v)>500))||heights.some(h=>!Number.isFinite(h)||h<1||h>20))throw Error('Use metre coordinates within ±500 and floor heights from 1 to 20 metres.');
 const cross=(a:number[],b:number[],c:number[])=> (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
 const on=(a:number[],b:number[],p:number[])=>Math.abs(cross(a,b,p))<1e-8&&p[0]>=Math.min(a[0],b[0])-1e-8&&p[0]<=Math.max(a[0],b[0])+1e-8&&p[1]>=Math.min(a[1],b[1])-1e-8&&p[1]<=Math.max(a[1],b[1])+1e-8;
 for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++){
  if(j===i+1||(i===0&&j===points.length-1))continue;
  const a=points[i],b=points[(i+1)%points.length],c=points[j],d=points[(j+1)%points.length];
  if((cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0)||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b))throw Error('Footprint edges must not cross or touch.');
 }
 const signed=points.reduce((sum,p,i)=>{const q=points[(i+1)%points.length];return sum+p[0]*q[1]-q[0]*p[1]},0)/2;
 if(Math.abs(signed)<1)throw Error('Footprint must enclose at least one square metre.');
 const root=new THREE.Group();root.name='PDF exterior massing · extracted footprint';
 const shape=new THREE.Shape(points.map(p=>new THREE.Vector2(p[0],-p[1])));
 const wallMat=new THREE.MeshStandardMaterial({color:0xd5d3c9,side:THREE.DoubleSide});const slabMat=new THREE.MeshStandardMaterial({color:0x9da7a4,side:THREE.DoubleSide});
 const add=(mesh:THREE.Mesh,name:string)=>{mesh.name=name;mesh.userData={...source,component_id:`draft-${root.children.length}`,reviewStatus:'unverified',assumptions:'Repeated footprint; flat roof; wall and slab surfaces have zero thickness; no openings or facade details.'};root.add(mesh)};
 let y=0;
 const slab=(level:number,name:string)=>{const mesh=new THREE.Mesh(new THREE.ShapeGeometry(shape),slabMat);mesh.rotation.x=-Math.PI/2;mesh.position.y=level;add(mesh,name)};
 heights.forEach((height,floor)=>{slab(y,`Level ${floor+1} slab surface`);points.forEach((a,i)=>{const b=points[(i+1)%points.length],length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length<.01)throw Error('Remove repeated footprint vertices.');const mesh=new THREE.Mesh(new THREE.PlaneGeometry(length,height),wallMat);mesh.position.set((a[0]+b[0])/2,y+height/2,(a[1]+b[1])/2);mesh.rotation.y=-Math.atan2(b[1]-a[1],b[0]-a[0]);add(mesh,`Level ${floor+1} wall ${i+1}`)});y+=height});slab(y,'Flat roof surface');return root;
}

export async function pdfDraftOption(building:string,documentId:string,host?:HTMLElement){
 const me=await (await fetch('/api/me')).json();
 const panel=document.createElement('section');panel.className='card';panel.id='pdf-geometry-draft';panel.innerHTML='<h2>PDF exterior assessment</h2><p role="status" class="assessment">Checking plans, scale, heights and elevations…</p><ul class="findings"></ul><p class="scope"></p>';
 if(host)host.append(panel);else document.querySelector('.processing')!.after(panel);const status=panel.querySelector('.assessment')!,findings=panel.querySelector('.findings')!;let busy=false;
 const show=(items:string[])=>{findings.replaceChildren();for(const text of items){const li=document.createElement('li');li.textContent=text;findings.append(li)}};
 async function post(url:string,body?:FormData){const token=await (await fetch('/api/csrf')).json();const r=await fetch(url,{method:'POST',headers:{'X-CSRF-TOKEN':token.token},body});const value=await r.json().catch(()=>null);if(!r.ok)throw Error(value?.message??(r.status===429?'Request limit reached. Try again after the limit resets.':`Request failed (${r.status}).`));return value}
 async function create(context:any){if(busy)return;busy=true;let root:THREE.Group|null=null;try{
  status.textContent='Building exterior massing from extracted drawing geometry…';await new Promise(r=>setTimeout(r,30));
  const source={origin:'automatic-pdf-exterior-massing',sourceDocumentId:documentId,sourceSha256:context.sourceSha256,sourcePage:context.geometry.sourcePage,scaleEvidence:context.geometry.scaleEvidence,heightEvidence:context.geometry.heightEvidence,readerVersion:context.version,limitations:context.limitations};
  root=footprintDraft(context.geometry.points,context.geometry.heights,source);root.name='PDF exterior massing · unverified';root.updateMatrixWorld(true);
  const bytes=await new GLTFExporter().parseAsync(root,{binary:true});if(!(bytes instanceof ArrayBuffer))throw Error('Could not encode draft.');
  const existing=await (await fetch(`/api/buildings/${building}/models`)).json();const parent=existing.find((r:any)=>r.documentId===documentId&&r.active);
  const form=new FormData();form.set('documentId',documentId);if(parent)form.set('parentId',parent.id);form.set('glb',new Blob([bytes],{type:'model/gltf-binary'}),'PDF-exterior-massing-draft.glb');
  status.textContent='Saving separate draft revision…';const revision=await post(`/api/buildings/${building}/models`,form);location.assign(`/buildings/${building}/documents/${documentId}/review?revision=${revision.id}`);
 }catch(e){status.textContent=String(e);busy=false;const retry=document.createElement('button');retry.textContent='Retry saving draft';retry.onclick=()=>{retry.remove();void create(context)};panel.append(retry)}finally{root?.traverse(o=>{if(o instanceof THREE.Mesh){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose())}})}}
 async function refresh(){try{
  const r=await fetch(`/api/documents/${documentId}/geometry-context`);if(!r.ok)throw Error('PDF assessment unavailable.');const context=await r.json();
  if(context.status==='processing'){status.textContent=`Analyzing PDF · ${context.message}`;setTimeout(refresh,3000);return}
  if(context.status==='needs-analysis'){status.textContent='This PDF needs the current exterior assessment.';if(me.role==='admin'&&!panel.querySelector('button')){const button=document.createElement('button');button.textContent='Analyze PDF for exterior';button.onclick=async()=>{button.disabled=true;try{await post(`/api/documents/${documentId}/process`);button.remove();await refresh()}catch(e){status.textContent=String(e);button.disabled=false}};panel.append(button)}return}
  show([...(context.missing??[]),...(context.limitations??[])]);
  panel.querySelector('.scope')!.textContent='PDF evidence is not proof of architectural completeness. Existing models and review history are retained.';
  if(context.status!=='ready'){status.textContent='This PDF is outside the limited automatic massing reader. This assessment does not prevent generation from an interpreted recipe above.';return}
  const revisions=await (await fetch(`/api/buildings/${building}/models`)).json();
  if(revisions.some((x:any)=>x.documentId===documentId)){status.textContent='Exterior massing evidence found. Your existing model remains available.';return}
  if(me.role==='admin')await create(context);else status.textContent='Exterior massing evidence found. An administrator can create the draft.';
 }catch(e){status.textContent=String(e)}}
 await refresh();
}
