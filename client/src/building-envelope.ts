import * as THREE from 'three';
import {FLOORS,SCALE} from './floor-data';
import {SCALE_Z} from './parking-evidence';

/** Exterior presentation of the four-floor study. Fin depths and joints are schematic. */
export function buildingEnvelope(){
 const g=new THREE.Group();g.name='Exterior · A3.11–A3.14 / A4.11';
 const white=new THREE.MeshStandardMaterial({color:0xeeeae1,roughness:.8});
 const silver=new THREE.MeshStandardMaterial({color:0xb8babb,roughness:.55});
 const top=FLOORS[10].datum;
 const x=(v:number)=>(v-909)*SCALE,z=(v:number)=>(v-740)*SCALE_Z;
 function box(name:string,w:number,h:number,d:number,px:number,py:number,pz:number,mat=white){const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),mat);m.position.set(px,py,pz);m.name=name;m.userData={sheet:'A3.11–A3.14 / A4.11'};g.add(m);return m}
 // Continuous slab-edge bands on the tower, coordinated with the plan perimeter.
 for(const f of FLOORS.slice(1).filter(f=>f.level<=11)){
  const y=f.datum;
  if(f.level>=3){box('North slab-edge band',449*SCALE,.22,.18,x(908.5),y-.05,z(520));}
  box('South slab-edge band',449*SCALE,.22,.18,x(908.5),y-.05,z(955));
  for(const side of [684,1133])box('Side slab-edge band',.18,.22,435*SCALE_Z,x(side),y-.05,z(737.5));
 }
 // South paired solid fields align to apartment boundaries on A2.13/A2.14.
 for(const [px,width] of [[820,19],[989,19]]){
  box('South continuous facade field · A3.11',width*SCALE,top,.2,x(px),top/2,z(959));
  for(let i=0;i<10;i++){
   const bottom=FLOORS[i].datum,h=FLOORS[i].height;
   const coords=new Float32Array([x(px-9),bottom,z(963),x(px+9),bottom+h,z(963),x(px+9),bottom,z(963)]);
   const geom=new THREE.BufferGeometry();geom.setAttribute('position',new THREE.BufferAttribute(coords,3));geom.computeVertexNormals();
   const m=new THREE.Mesh(geom,new THREE.MeshStandardMaterial({color:i%2?0xd0d0cc:0xe5e1d8,side:THREE.DoubleSide}));m.name='Folded facade panel · geometry schematic';g.add(m);
  }
 }
 // North and side solid vertical fields as shown by the elevation views.
 for(const px of [792,945,1031])box('North facade field · A3.12',.48,top-5.691,.16,x(px),(top+5.691)/2,z(518),silver);
 for(const side of [682,1135])for(const py of [688,758])box('Side vertical panel · A3.13 / A3.14',.16,top-3.048,.62,x(side),(top+3.048)/2,z(py),silver);
 // Main and mechanical roof slabs are supplied by their own source-linked levels.
 box('Entry canopy / soffit',143*SCALE,.18,97*SCALE_Z,x(908.5),3.0,z(906.5));
 box('Entry forecourt',143*SCALE,.10,145*SCALE_Z,x(908.5),-.12,z(930),silver);
 box('Beach Avenue sidewalk · context',34,.12,4,0,-.2,z(1050),silver);
 // A3.13 G is the narrow grating at the tower face, between the rear tower
 // grid and the next south grid. Do not place a garage door on the lot boundary.
 // Grating is built once from the source opening in floor-data.ts.
 return g;
}
