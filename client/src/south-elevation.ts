import * as THREE from 'three';
import {SCALE_Z} from './parking-evidence';
import {materialColor} from './material-rules';

// Traced from the rendered A3.11 / PDF 28 in its 1888×1335 reference frame.
// These are face-region traces, NOT fabrication dimensions or measured quantities.
export const SOUTH_TAKEOFF=[
 {code:'C',label:'ACM panel · slate grey',quantity:'377.1 sq ft',color:'#ad63b4',modeled:true},
 {code:'L',label:'Cementitious panel · white',quantity:'1,150.9 sq ft',color:'#f4e34a',modeled:true},
 {code:'flashing',label:'Through-wall flashing',quantity:'23.0 ft',color:'#eee950',modeled:false},
 {code:'acm-trim',label:'Vertical ACM trims',quantity:'96.1 ft',color:'#6875dc',modeled:false},
 {code:'panel-trim',label:'Vertical trims at panel',quantity:'174.2 ft',color:'#cb6abe',modeled:false},
 {code:'corner',label:'Outside corners at ACM',quantity:'37.2 ft',color:'#70df66',modeled:false},
];
export function southElevation(){
 const group=new THREE.Group();group.name='South elevation takeoff study · A3.11 / PDF 28';
 const sx=30.2006/650,sy=32.037/(1062-373);
 function region(code:'C'|'L',x1:number,y1:number,x2:number,y2:number,z:number){
  const material=new THREE.MeshStandardMaterial({color:code==='C'?0x52565b:0xf1f0e9,roughness:code==='C'?.48:.82,metalness:code==='C'?.25:0});
  const mesh=new THREE.Mesh(new THREE.BoxGeometry((x2-x1)*sx,(y2-y1)*sy,.035),material);
  mesh.position.set((x1+x2-1742)*sx/2,(1062-(y1+y2)/2)*sy,z);
  mesh.name=code+' · south highlighted face region';
  mesh.userData={sheet:'A3.11 · PDF 28',southCode:code,finishColor:code==='C'?0x52565b:0xf1f0e9,sourceStatus:'Manual face trace; specified finish family with approximate display colour. 35 mm display depth is provisional. Not a fabrication detail.'};group.add(mesh);
 }
 const face=(955-740)*SCALE_Z+.17;
 const relief=new THREE.Group();relief.name='Elevation-derived facade relief';relief.userData.relief=true;group.add(relief);
 function block(name:string,a:number,b:number,c:number,d:number,depth:number,color:number,category:string='wall'){
  const m=new THREE.Mesh(new THREE.BoxGeometry((c-a)*sx,(d-b)*sy,depth),new THREE.MeshStandardMaterial({color,roughness:.72}));
  const offset=name.includes('frame')||name.includes('jamb')||name.includes('sill')||name.includes('metal bar')||name.includes('face line')?.008:0;
  m.position.set(((a+c)/2-871)*sx,(1062-(b+d)/2)*sy,face-depth/2-.025+offset);m.name=name;m.userData={sheet:'A3.11 · PDF 28',reliefCategory:category,sourceStatus:'South elevation raster trace; depth/profile provisional. This is a facade relief, not a coordinated full building.'};relief.add(m);return m;
 }
 // A dedicated elevation relief avoids presenting the incompatible plan-template
 // openings behind the source-derived elevation as if they were reconciled.
 for(const [top,bottom] of [[494,535],[551,600],[609,657],[666,713],[722,770],[779,827],[836,884],[893,940],[950,995]]){
  for(const [a,c] of [[650,755],[804,939],[987,1091]]){
   block('D1 south glazing bay · elevation trace',a,top,c,bottom,.09,0x586263,'opening');
   for(const px of [a,a+(c-a)*.28,a+(c-a)*.65,c-2])block('D1 white frame · spacing traced approximately',px,top,px+2,bottom,.14,0xe9e8e3,'opening');
   block('D1 glazing sill',a,bottom-2,c,bottom,.14,0xe9e8e3,'opening');
  }
 }
 // Balcony slab/guard extents are traced independently of apartment-window bays.
 for(const y of [535,600,657,713,770,827,884,940]){
  for(const [a,c] of (y===535?[[645,755],[804,939],[987,1097]]:[[619,755],[804,939],[987,1126]])){
   const slab=block('South balcony slab edge',a,y,c,y+3,.9,0xdeddd6,'slab');slab.position.z=face+.38;
   const rail=block('E3 existing balcony guard · profile provisional',a,y-24,c,y-2,.025,0xaeb9b8,'guard');rail.position.z=face+.83;(rail.material as THREE.MeshStandardMaterial).transparent=true;(rail.material as THREE.MeshStandardMaterial).opacity=.28;
   const topRail=block('Existing guard top rail',a,y-25,c,y-24,.035,0x7a807e,'guard');topRail.position.z=face+.85;
   for(let px=a;px<c;px+=19){const post=block('Existing guard post · spacing approximate',px,y-24,px+1,y,.035,0x888e8b,'guard');post.position.z=face+.85}
  }
 }
 // Continuous sculptural fields: broad polygonal faces, not repeated little fins.
 function field(name:string,pts:number[][],color:number,paint=false){const shape=new THREE.Shape();pts.forEach(([px,py],i)=>{const x=(px-871)*sx,y=(1062-py)*sy;i?shape.lineTo(x,y):shape.moveTo(x,y)});shape.closePath();const mesh=new THREE.Mesh(new THREE.ExtrudeGeometry(shape,{depth:paint?.002:.22,bevelEnabled:false}),new THREE.MeshStandardMaterial({color,roughness:.88}));mesh.position.z=face+(paint?.272:.05);mesh.name=name;mesh.userData={sheet:'A3.11 · PDF 28',reliefCategory:'wall',sourceStatus:paint?'Painted concrete finish zone, not a folded panel. Raster boundary and display colour provisional.':'Concrete strip face traced; thickness provisional. A1/A2/A3 schedule denotes paint, not evidence of folded geometry.'};relief.add(mesh)}
 field('A1 west painted-concrete strip',[[756,477],[756,454],[795,454],[795,1062],[755,1062]],0xe7e5df);
 field('A1 east painted-concrete strip',[[940,454],[980,454],[980,1062],[940,1062]],0xe7e5df);
 field('A3 west upper silver paint zone',[[775,486],[795,583],[795,601],[759,659]],0xb6b7b4,true);
 field('A2 west upper pink paint zone',[[795,585],[795,745],[759,822],[759,659]],0xc3aaac,true);
 field('A3 west lower silver paint zone',[[759,739],[795,829],[795,945],[759,834]],0xb6b7b4,true);
 field('A2 west base pink paint zone',[[779,982],[795,1018],[795,1062],[770,1062]],0xc3aaac,true);
 field('A3 east upper silver paint zone',[[940,454],[980,454],[980,510],[940,569]],0xb6b7b4,true);
 field('A2 east upper pink paint zone',[[960,486],[980,540],[980,657],[960,608],[940,657],[940,557]],0xc3aaac,true);
 field('A3 east lower silver paint zone',[[960,709],[980,769],[980,915],[940,978],[940,789]],0xb6b7b4,true);
 field('A2 east base pink paint zone',[[980,889],[980,1046],[940,989],[940,949]],0xc3aaac,true);
 // Ground frontage and recessed central entrance must remain separate.
 for(const [a,c] of [[575,620],[634,684],[697,747],[813,865],[877,932],[995,1038],[1042,1087]]){
  block('Ground frontage glazing / entrance · source trace',a,1015,c,1061,.12,0x565d5a,'opening');
  block('Ground frontage white jamb',a,1015,a+2,1061,.18,0xefeee9,'opening');
 }
 block('Right-side overhead door I · south elevation only',1098,1024,1174,1062,.14,0x8c918d,'opening');
 for(let px=1100;px<1174;px+=5)block('Overhead door face line · profile unresolved',px,1024,px+1,1062,.16,0x5d6460,'opening');
 block('Upper right grating G · elevation trace',1098,951,1174,995,.08,0x929b95,'guard');
 for(let px=1100;px<1174;px+=4)block('G white metal bar · spacing provisional',px,951,px+1,995,.12,0xf1f0e9,'guard');
 block('Main roof edge',650,464,1091,478,.3,0xe7e7e1,'slab');
 for(const [a,c] of [[651,755],[804,939],[987,1091]]){
  block('E1 roof guard top · white finish',a,462,c,463,.045,0xf1f0e9,'guard');
  for(let px=a;px<c;px+=22)block('E1 roof guard post · spacing approximate',px,462,px+1,477,.045,0xf1f0e9,'guard');
 }
 block('West podium upper grating · G source region',535,956,644,981,.08,0x69716b,'guard');
 for(let px=536;px<644;px+=4)block('West podium grating bar · spacing provisional',px,956,px+1,981,.095,0xe3e6df,'guard');
 block('West podium concrete frontage',535,982,563,1062,.18,0xd8d9d2);
 // Keep this relief out of the combined model until plan-depth coordination.
 relief.visible=false;
 // Three independent facade bays; never bridge the sculptural concrete fields.
 for(const [y,h] of [[478,15],[535,14],[600,8],[657,8],[713,8],[770,8],[827,8],[884,8],[940,10],[995,9]]){
  for(const [a,b] of [[651,755],[804,939],[987,1091]])region('L',a,y,b,y+h,face);
 }
 region('L',865,494,877,1062,face+.005);
 // Ground-level highlighted surrounds, with openings left between the strips.
 for(const [a,b] of [[563,575],[620,634],[684,697],[747,755],[1087,1097]])region('L',a,1012,b,1062,face);
 region('L',563,996,755,1012,face);region('L',987,996,1097,1012,face);
 // Mechanical enclosure south face: exclude the two visible lower openings.
 const roofFace=(791-740)*SCALE_Z+.12;
 region('C',796,363,946,435,roofFace);
 region('C',826,435,902,478,roofFace);
 region('C',796,435,804,478,roofFace);region('C',923,435,946,478,roofFace);
 // Panel seams are visible on the mechanical enclosure elevation. Width is display-only.
 const seamMat=new THREE.MeshStandardMaterial({color:0x303438,roughness:.8});
 for(const px of [816,838,860,882,904,925]){
  const seam=new THREE.Mesh(new THREE.BoxGeometry(.012,(435-363)*sy,.008),seamMat);
  seam.position.set((px-871)*sx,(1062-399)*sy,roofFace+.022);
  seam.name='Mechanical ACM vertical panel seam · A3.11';seam.userData={sheet:'A3.11 · PDF 28',sourceStatus:'Joint position traced from elevation; 12 mm visual joint width is provisional, not a specified trim section.'};group.add(seam);
 }
 // Entrance callout identifies an enterphone. The PDF does not size the device.
 const intercom=new THREE.Mesh(new THREE.BoxGeometry(.12,.22,.025),new THREE.MeshStandardMaterial({color:0x626a6c,metalness:.5,roughness:.4}));
 intercom.position.set((805-871)*sx,1.35,(858-740)*SCALE_Z+.12);
 intercom.name='Entrance enterphone · A3.11 callout';intercom.userData={sheet:'A3.11 · PDF 28',sourceStatus:'Callout-based approximate location. Device size and mounting height are visualization assumptions.'};group.add(intercom);
 // Plan/elevation registration is approximate: expose the residual, never snap silently.
 group.userData.registration='Elevation 99 ft 1 in property span; main datum 23.90 ft. Independent raster trace; alignment pending dimension reconciliation.';
 return group;
}

export function southFinishMode(group:THREE.Group,highlight:boolean){
 group.traverse(o=>{if(o instanceof THREE.Mesh&&o.userData.southCode){const material=o.material as THREE.MeshStandardMaterial;material.color.set(materialColor(o.userData.southCode,highlight))}});
}
