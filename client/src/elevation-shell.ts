import * as THREE from 'three';
import {SCALE} from './floor-data';
import {materialColor} from './material-rules';
import {SCALE_Z} from './parking-evidence';

export const ELEVATIONS={south:{page:28,sheet:'A3.11'},north:{page:29,sheet:'A3.12'},east:{page:30,sheet:'A3.13'},west:{page:31,sheet:'A3.14'}};
export type Elevation=keyof typeof ELEVATIONS;
// Independent elevation traces registered to the plan footprint. This registration
// closes the visual shell, but is not a dimensional coordination certification.
export function elevationShell(){
 const root=new THREE.Group();
 for(const direction of ['north','east','west'] as const){
  const side=direction!=='north';
  const cfg=direction==='north'?{left:592,right:1045,roof:534,ground:1112,windows:[[595,640],[710,750],[795,840],[886,929],[995,1042]],columns:[710,750,795,815,840,886,929]}:direction==='east'?{left:530,right:973,roof:505,ground:1084,windows:[[538,575],[662,688],[735,773],[821,844],[929,967]],columns:[662,688,735,773,821,844]}:{left:718,right:1158,roof:500,ground:1078,windows:[[722,762],[846,873],[920,958],[1005,1029],[1116,1153]],columns:[846,873,920,958,1005,1029]};
  const width=side?435*SCALE_Z:449*SCALE;
  const face=new THREE.Group();face.name=direction+' elevation · '+ELEVATIONS[direction].sheet;
  face.rotation.y=direction==='north'?Math.PI:direction==='east'?Math.PI/2:-Math.PI/2;
  face.position.set(direction==='east'?224*SCALE+.12:direction==='west'?-225*SCALE-.12:0,0,direction==='north'?-220*SCALE_Z-.12:0);
  root.add(face);
  const maskTexture=new THREE.TextureLoader().load('/floors/'+direction+'-yellow-mask.png',()=>{face.userData.maskReady=true},undefined,()=>{face.userData.maskError=true});
  maskTexture.colorSpace=THREE.SRGBColorSpace;
  maskTexture.magFilter=THREE.NearestFilter;
  maskTexture.minFilter=THREE.NearestFilter;
  const maskHeight=26.832*(cfg.ground-cfg.roof+10)/(cfg.ground-cfg.roof);
  const sourceMask=new THREE.Mesh(new THREE.PlaneGeometry(width,maskHeight),new THREE.MeshBasicMaterial({map:maskTexture,transparent:true,alphaTest:.5,depthWrite:false,toneMapped:false}));
  sourceMask.position.set(0,maskHeight/2,.115);
  sourceMask.name=direction+' source yellow markup';
  sourceMask.userData={sourceMask:true,elevation:direction,materialCode:'L',sheet:ELEVATIONS[direction].sheet+' · PDF '+ELEVATIONS[direction].page,verification:'unverified',sourceStatus:'Automatically extracted source RGB yellow pixels. Registered facade overlay, not physical panel thickness. Segmentation and 3D registration are not certified.'};
  if(direction==='west'){
   // L1 west exterior is plan x=600, tower exterior x=684. Project the
   // lower source pixels to their own wall, not through the podium.
   const split=3.048;
   const upper=new THREE.PlaneGeometry(width,maskHeight-split);
   const uv=upper.attributes.uv;
   for(let i=0;i<uv.count;i++)uv.setY(i,split/maskHeight+uv.getY(i)*(1-split/maskHeight));
   sourceMask.geometry.dispose();sourceMask.geometry=upper;
   sourceMask.position.y=split+(maskHeight-split)/2;
   const lowerGeometry=new THREE.PlaneGeometry(width,split);
   const lowerUv=lowerGeometry.attributes.uv;
   for(let i=0;i<lowerUv.count;i++)lowerUv.setY(i,lowerUv.getY(i)*split/maskHeight);
   const lower=new THREE.Mesh(lowerGeometry,sourceMask.material);
   lower.position.set(0,split/2,84*SCALE+.115);
   lower.name='West ground-floor source yellow markup';
   lower.userData={...sourceMask.userData,sourceStatus:'Source yellow mask projected to L1 west wall at plan x=600; tower wall at x=684. Depth from manual plan trace, alignment remains unverified.'};
   face.add(lower);
  }
  face.add(sourceMask);
  const x=(v:number)=>(v-(cfg.left+cfg.right)/2)*width/(cfg.right-cfg.left);
  const y=(v:number)=>(cfg.ground-v)*26.832/(cfg.ground-cfg.roof);
  function rect(name:string,a:number,b:number,c:number,d:number,color:number,category:string,highlight=false){
   const mesh=new THREE.Mesh(new THREE.BoxGeometry(x(c)-x(a),y(b)-y(d),.035),new THREE.MeshStandardMaterial({color,roughness:.8}));
   mesh.position.set((x(a)+x(c))/2,(y(b)+y(d))/2,highlight?.065:.02);mesh.name=name;
   mesh.userData={sheet:ELEVATIONS[direction].sheet+' · PDF '+ELEVATIONS[direction].page,elevation:direction,reliefCategory:category,highlight,materialCode:name.split(' ')[0],verification:'unverified',finishColor:color,sourceStatus:'Elevation-registered schematic surface; window subdivisions, thicknesses and local variants remain unverified.'};face.add(mesh);
  }
  rect('A1 painted concrete backing',cfg.left,cfg.roof,cfg.right,cfg.ground,0xe5e3dc,'wall');
  for(let floor=2;floor<=10;floor++){
   const datum=3.048+(floor-2)*2.643;
   const bottom=cfg.ground-datum*(cfg.ground-cfg.roof)/26.832;
   const top=bottom-2.2352*(cfg.ground-cfg.roof)/26.832;
   for(const [a,c] of cfg.windows){
    rect('D1 opening field',a,top,c,bottom-3,0x586465,'opening',true);
    rect('D1 white frame',a,top,a+1.5,bottom-3,0xf1f0e9,'opening',true);
    rect('D1 white frame',c-1.5,top,c,bottom-3,0xf1f0e9,'opening',true);
   }
   for(const [a,c] of cfg.windows.slice(1,-1))rect('L horizontal panel band',a-2,top-5,c+2,top,0xf1f0e9,'panel',true);
  }
  // C cladding on the actual mechanical enclosure footprint, not the tower face.
  const roof=new THREE.Group();roof.rotation.y=face.rotation.y;
  roof.position.set(direction==='east'?(981-909)*SCALE+.08:direction==='west'?(836-909)*SCALE-.08:(908.5-909)*SCALE,0,direction==='north'?(655-740)*SCALE_Z-.08:(723-740)*SCALE_Z);
  root.add(roof);
  const roofWidth=side?136*SCALE_Z:145*SCALE;
  const panel=new THREE.Mesh(new THREE.BoxGeometry(roofWidth,32.494-26.832,.035),new THREE.MeshStandardMaterial({color:materialColor('C',true),roughness:.6}));
  panel.position.y=(32.494+26.832)/2;panel.name='C mechanical enclosure cladding';
  panel.userData={sheet:ELEVATIONS[direction].sheet+' · PDF '+ELEVATIONS[direction].page,elevation:direction,materialCode:'C',reliefCategory:'panel',verification:'unverified',finishColor:materialColor('C',false),sourceStatus:'Cladding code confirmed; face registered to plan core. Local openings and exact panel joints unresolved.'};roof.add(panel);
  for(const px of cfg.columns)rect('L vertical panel edge',px-1.5,cfg.roof,px+1.5,cfg.ground-58,0xf1f0e9,'panel',true);
  if(direction==='north'){
   // A3.12 / PDF 29, 1888 x 1335 page reference: these are independent
   // traced regions, not a repeated-window rule. Keep the painted piers
   // between the upper wings and centre clear (no invented full-width band).
   const bands:[string,number,number,number,number][]=[
    ['continuous lower fascia',592,990,1038,1001],
    ['upper west wing fascia',595,582,705,590],
    ['upper east wing fascia',934,582,1044,590],
   ];
   for(const [top,bottom] of [[644,655],[701,712],[758,769],[815,826],[872,883],[929,940]]){
    bands.push(['west balcony return',639,top,664,bottom],['east balcony return',974,top,998,bottom]);
   }
   for(const [label,a,b,c,d] of bands){
    rect('L '+label,a,b,c,d,materialColor('L',false),'panel',true);
    const mesh=face.children[face.children.length-1] as THREE.Mesh;
    mesh.position.z=.09;
    mesh.userData.sourceRegion={page:29,referenceSize:[1888,1335],bounds:[a,b,c,d]};
    mesh.userData.sourceStatus='Individually traced yellow L region from A3.12 / PDF 29. Face extent visually checked; extrusion depth and cross-view registration remain provisional.';
   }
  }
 }
 return root;
}
export function facingElevation(x:number,z:number):Elevation{return Math.abs(x)>Math.abs(z)?x>0?'east':'west':z>0?'south':'north'}
export function applySourceMarkup(root:THREE.Group,takeoff:boolean,enabled:boolean){
 root.children.forEach(face=>{
  const ready=face.userData.maskReady===true;
  face.children.forEach(o=>{
   if(o.userData.sourceMask)o.visible=takeoff&&enabled&&ready;
   else if(o.userData.materialCode==='L'&&o.userData.reliefCategory==='panel')o.visible=enabled&&!(takeoff&&ready);
  });
 });
}
