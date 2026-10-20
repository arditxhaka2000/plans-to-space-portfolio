import * as THREE from 'three';

export type ModelPart = THREE.Object3D & { userData: { partId?: string; label?: string; system?: string; floor?: number; quantity?: string } };
const C = { concrete:0xd8d5cd, white:0xeeeae0, silver:0xb8bab7, charcoal:0x373b3e, pink:0xd7a4a0, glass:0x536a70, rail:0xcbd9dc, acm:0x4a4f52, cement:0xe8e6df, shaft:0xd3d1ca, shaft12:0x777c80, trim:0x8a8d8d, flashing:0x6e7477, soffit:0xe9e7e1, cap:0x5f6466, corners:0x676c6e, podium:0x918d85, planting:0x5c715f };
const material = (color:number, roughness=.72, metalness=.05, transparent=false, opacity=1) => new THREE.MeshStandardMaterial({color,roughness,metalness,transparent,opacity});

// Metres above Main Floor. Datums transcribed from A3.11 and checked against A4.11.
const LEVELS:Record<number,number>={1:0,2:3.048,3:5.691,4:8.334,5:10.977,6:13.620,7:16.263,8:18.906,9:21.549,10:24.192,11:26.832,12:29.447};
const MACHINE_ROOF=32.037;

export function createFlamingoModel():{root:THREE.Group;parts:ModelPart[]}{
  const root=new THREE.Group(); root.name='Flamingo Tower / evidence model'; const parts:ModelPart[]=[];
  const m={concrete:material(C.concrete),white:material(C.white),silver:material(C.silver),charcoal:material(C.charcoal,.38,.2),pink:material(C.pink),glass:material(C.glass,.16,.28,true,.75),rail:material(C.rail,.12,.32,true,.34),acm:material(C.acm,.26,.48),cement:material(C.cement,.58),shaft:material(C.shaft,.34,.2),shaft12:material(C.shaft12,.32,.25),trim:material(C.trim,.3,.5),flashing:material(C.flashing,.3,.55),soffit:material(C.soffit),cap:material(C.cap,.3,.55),corners:material(C.corners,.3,.45),podium:material(C.podium),planting:material(C.planting)};
  const box=(name:string,size:[number,number,number],pos:[number,number,number],mat:THREE.Material,data:ModelPart['userData']={},parent=root)=>{const mesh=new THREE.Mesh(new THREE.BoxGeometry(...size),mat) as ModelPart;mesh.name=name;mesh.position.set(...pos);mesh.castShadow=true;mesh.receiveShadow=true;mesh.userData=data;parent.add(mesh);if(data.partId)parts.push(mesh);return mesh};
  const palm=(name:string,x:number,z:number,height:number)=>{const g=new THREE.Group();g.name=name;g.position.set(x,-3.02,z);root.add(g);const trunk=new THREE.Mesh(new THREE.CylinderGeometry(.16,.28,height,9),material(0x76604a));trunk.position.y=height/2;trunk.castShadow=true;g.add(trunk);for(let i=0;i<9;i++){const frond=new THREE.Mesh(new THREE.ConeGeometry(.18,3.4,5),m.planting);frond.position.y=height;frond.rotation.z=Math.PI/2.5;frond.rotation.y=i*Math.PI*2/9;frond.translateY(1.15);frond.castShadow=true;g.add(frond)}};
  const width=30.2,depth=23.6;

  // B1 and the irregular Level 1 podium visible in plan and all four elevations.
  box('B1 below grade',[34.5,3.05,27.5],[0,-1.53,0],m.podium,{label:'Below Grade B1',floor:1});
  box('Level 1 tower base',[30.2,3.05,23.6],[0,1.52,0],m.white,{label:'Level 1 tower base',floor:1});
  box('West podium wing',[13.4,3.05,19.5],[-21.7,1.52,1.8],m.white,{label:'West podium / existing context',floor:1});
  box('East podium wing',[11.8,3.05,17.2],[21,1.52,3],m.white,{label:'East podium / service wing',floor:1});
  box('West podium terrace',[13.2,.28,19.2],[-21.7,3.12,1.8],m.concrete,{label:'Podium roof terrace',floor:2});
  box('East podium terrace',[11.6,.28,17],[21,3.12,3],m.concrete,{label:'Podium roof terrace',floor:2});
  box('Lobby glazing',[9.4,2.5,.16],[0,1.4,depth/2+.1],m.glass,{label:'D1 lobby glazing',floor:1});
  [-3.7,-2.45,-1.2,0,1.2,2.45,3.7].forEach((x,i)=>box(`Lobby mullion ${i}`,[.09,2.65,.24],[x,1.4,depth/2+.18],m.charcoal,{label:'Lobby glazing mullion',floor:1}));
  box('Entry canopy',[10.8,.22,3.4],[0,3,depth/2+1.5],m.charcoal,{label:'Main entry canopy',floor:1});
  box('West garage grille',[7,2.3,.18],[-10.9,1.35,depth/2+.1],m.charcoal,{label:'G metal bar grating / garage',floor:1});
  box('East garage grille',[7,2.3,.18],[10.9,1.35,depth/2+.1],m.charcoal,{label:'G metal bar grating / garage',floor:1});
  // Level 1 plan organization: central lobby/core, service rooms, and the two
  // parking/vehicle bays. These remain visible in plan when Level 1 is isolated.
  box('L1 core west wall',[.24,2.75,7.6],[-4.5,1.48,0],m.silver,{label:'Level 1 central core west wall',floor:1});
  box('L1 core east wall',[.24,2.75,7.6],[4.5,1.48,0],m.silver,{label:'Level 1 central core east wall',floor:1});
  box('L1 core north wall',[9.2,2.75,.24],[0,1.48,-3.7],m.silver,{label:'Level 1 central core north wall',floor:1});
  box('L1 elevator bank',[3.2,2.75,3.5],[0,1.48,0],m.charcoal,{label:'Level 1 elevator bank',floor:1});
  box('L1 lobby west wall',[.16,2.75,7.2],[-5.8,1.48,7.7],m.white,{label:'Level 1 lobby west partition',floor:1});
  box('L1 lobby east wall',[.16,2.75,7.2],[5.8,1.48,7.7],m.white,{label:'Level 1 lobby east partition',floor:1});
  [-11.2,11.2].forEach((x,i)=>box(`L1 parking bay division ${i}`,[.16,2.75,13.5],[x,1.48,-1.8],m.white,{label:'Level 1 parking/service bay division',floor:1}));
  box('L1 north service spine',[22.5,2.75,.16],[0,1.48,-7.6],m.white,{label:'Level 1 north service-room spine',floor:1});

  const glazing=(name:string,pos:[number,number,number],size:[number,number,number],floor:number,parent:THREE.Group)=>box(name,size,pos,m.glass,{label:`D1 aluminum window wall / Level ${floor}`,floor},parent);
  const balcony=(name:string,x:number,y:number,z:number,side:'south'|'north'|'east'|'west',floor:number,parent:THREE.Group,span=4.6)=>{
    const alongX=side==='south'||side==='north'; const slab:[number,number,number]=alongX?[span,.18,2.1]:[2.1,.18,span];
    box(`${name} slab`,slab,[x,y+.1,z],m.concrete,{label:`Balcony slab / Level ${floor}`,floor},parent);
    box(`${name} F05 soffit`,[slab[0]-.18,.07,slab[2]-.18],[x,y-.02,z],m.soffit,{partId:`soffit-${side}-${floor}-${name}`,label:'F05 - metal soffit / white finish',system:'soffit',floor,quantity:'430.3 sq ft stated on A2.32'},parent);
    const gp:[number,number,number]=alongX?[x,y+.68,z+(side==='south'?1:-1)]:[x+(side==='east'?1:-1),y+.68,z]; const gs:[number,number,number]=alongX?[span,1.05,.09]:[.09,1.05,span];
    box(`${name} glass guard`,gs,gp,m.rail,{label:`E1/E3 glass guard / Level ${floor}`,floor},parent);
  };
  const wrapBalcony=(corner:'sw'|'se'|'nw'|'ne',y:number,floor:number,parent:THREE.Group)=>{
    const east=corner.includes('e'),south=corner.includes('s'),sx=east?1:-1,sz=south?1:-1;
    const x=sx*(width/2-2),z=sz*(depth/2+.85);
    box(`${corner} wrap front slab`,[4.4,.18,2],[x,y+.1,z],m.concrete,{label:`90-degree wraparound corner balcony / Level ${floor}`,floor},parent);
    box(`${corner} wrap side slab`,[2,.18,4.4],[sx*(width/2+.85),y+.1,sz*(depth/2-2)],m.concrete,{label:`90-degree wraparound corner balcony / Level ${floor}`,floor},parent);
    box(`${corner} front soffit`,[4.2,.07,1.8],[x,y-.02,z],m.soffit,{partId:`soffit-${corner}-front-${floor}`,label:'F05 wrap balcony soffit',system:'soffit',floor,quantity:'430.3 sq ft stated total'},parent);
    box(`${corner} side soffit`,[1.8,.07,4.2],[sx*(width/2+.85),y-.02,sz*(depth/2-2)],m.soffit,{partId:`soffit-${corner}-side-${floor}`,label:'F05 wrap balcony soffit',system:'soffit',floor,quantity:'430.3 sq ft stated total'},parent);
    box(`${corner} front glass guard`,[4.4,1.05,.09],[x,y+.68,sz*(depth/2+1.82)],m.rail,{label:`E1/E3 corner glass guard / Level ${floor}`,floor},parent);
    box(`${corner} side glass guard`,[.09,1.05,4.4],[sx*(width/2+1.82),y+.68,sz*(depth/2-2)],m.rail,{label:`E1/E3 corner glass guard / Level ${floor}`,floor},parent);
  };

  for(let floor=2;floor<=11;floor++){
    const y=LEVELS[floor],next=floor===11?LEVELS[12]:LEVELS[floor+1],clear=next-y-.28,mid=y+.28+clear/2;
    const level=new THREE.Group();level.name=`Level ${floor}`;level.userData.floor=floor;root.add(level);
    box(`L${floor} floor plate`,[width,.28,depth],[0,y+.14,0],m.concrete,{label:`Level ${floor} concrete floor plate`,floor},level);
    // Repeated core and principal partition geometry follows the residential plans A2.12-A2.20.
    box(`L${floor} core west wall`,[.24,clear,7.4],[-4.5,mid,0],m.silver,{label:`Central core wall / Level ${floor}`,floor},level);
    box(`L${floor} core east wall`,[.24,clear,7.4],[4.5,mid,0],m.silver,{label:`Central core wall / Level ${floor}`,floor},level);
    box(`L${floor} core north wall`,[9.2,clear,.24],[0,mid,-3.6],m.silver,{label:`Central core wall / Level ${floor}`,floor},level);
    box(`L${floor} core south wall`,[9.2,clear,.24],[0,mid,3.6],m.silver,{label:`Central core wall / Level ${floor}`,floor},level);
    box(`L${floor} elevator shaft`,[3.2,clear,3.4],[0,mid,0],m.charcoal,{label:`Elevator shaft / Level ${floor}`,floor},level);
    box(`L${floor} west corridor wall`,[6.2,clear,.16],[-8,mid,0],m.white,{label:`Principal suite/corridor partition / Level ${floor}`,floor},level);
    box(`L${floor} east corridor wall`,[6.2,clear,.16],[8,mid,0],m.white,{label:`Principal suite/corridor partition / Level ${floor}`,floor},level);
    // Floor-plan partitions: Level 2 has a looser service/parking layout; Levels 3-9
    // repeat the residential unit matrix; Levels 10-11 step back around roof terraces.
    if(floor===2){
      [-10,10].forEach((x,i)=>box(`L2 service division ${i}`,[.16,clear,13],[x,mid,-2],m.white,{label:'Level 2 parking/service division',floor},level));
      box('L2 north service wall',[20,clear,.16],[0,mid,-7.2],m.white,{label:'Level 2 parking/service wall',floor},level);
    }else{
      const unitXs=floor>=10?[-8.8,-4.5,4.5,8.8]:[-11,-7,-3.8,3.8,7,11];
      unitXs.forEach((x,i)=>box(`L${floor} suite separation ${i}`,[.14,clear,7.5],[x,mid,x<0?-7.4:7.4],m.white,{label:`Suite separation wall / Level ${floor}`,floor},level));
      box(`L${floor} north unit spine`,[width-3,clear,.14],[0,mid,-7.2],m.white,{label:`North suite partition spine / Level ${floor}`,floor},level);
      box(`L${floor} south unit spine`,[width-3,clear,.14],[0,mid,7.2],m.white,{label:`South suite partition spine / Level ${floor}`,floor},level);
      if(floor===6||floor===9)box(`L${floor} crossover corridor`,[12,clear,.18],[0,mid,0],m.pink,{label:`Crossover corridor / Level ${floor}`,floor},level);
    }
    box(`L${floor} north spandrel`,[width,.42,.5],[0,y+.48,-depth/2],floor%3===0?m.silver:m.white,{label:'A1/A3 north spandrel',floor},level);
    box(`L${floor} south spandrel`,[width,.42,.5],[0,y+.48,depth/2],floor%4===0?m.pink:m.white,{label:'A1/A2 south spandrel',floor},level);
    box(`L${floor} west spandrel`,[.5,.42,depth],[-width/2,y+.48,0],m.white,{label:'A1 west spandrel',floor},level);
    box(`L${floor} east spandrel`,[.5,.42,depth],[width/2,y+.48,0],m.white,{label:'A1 east spandrel',floor},level);
    [-11.8,-6.9,-2.3,2.3,6.9,11.8].forEach((x,i)=>{glazing(`L${floor} south glazing ${i}`,[x,mid,depth/2+.02],[3.75,clear-.22,.16],floor,level);glazing(`L${floor} north glazing ${i}`,[x,mid,-depth/2-.02],[3.75,clear-.22,.16],floor,level)});
    [-8.6,-2.9,2.9,8.6].forEach((z,i)=>{glazing(`L${floor} east glazing ${i}`,[width/2+.02,mid,z],[.16,clear-.22,4.45],floor,level);glazing(`L${floor} west glazing ${i}`,[-width/2-.02,mid,z],[.16,clear-.22,4.45],floor,level)});
    [['south',depth/2+.28],['north',-depth/2-.28]].forEach(v=>box(`L${floor} ${v[0]} cementitious band`,[width,.25,.3],[0,y+.28,v[1] as number],m.cement,{partId:`cement-${v[0]}-${floor}`,label:'L - high density cementitious panel / white',system:'cement',floor,quantity:'3,090.3 sq ft stated total'},level));
    box(`L${floor} east cementitious band`,[.3,.25,depth],[width/2+.28,y+.28,0],m.cement,{partId:`cement-east-${floor}`,label:'L - high density cementitious panel / white',system:'cement',floor,quantity:'3,090.3 sq ft stated total'},level);
    box(`L${floor} west cementitious band`,[.3,.25,depth],[-width/2-.28,y+.28,0],m.cement,{partId:`cement-west-${floor}`,label:'L - high density cementitious panel / white',system:'cement',floor,quantity:'3,090.3 sq ft stated total'},level);
    wrapBalcony('sw',y,floor,level);wrapBalcony('se',y,floor,level);wrapBalcony('nw',y,floor,level);wrapBalcony('ne',y,floor,level);
    balcony('south-centre',0,y,depth/2+1.05,'south',floor,level,5.8);
    [-8.8,-3,3,8.8].forEach((x,i)=>{box(`L${floor} panel trim ${i}`,[.18,clear,.3],[x,mid,depth/2+.36],m.trim,{partId:`panel-trim-south-${floor}-${i}`,label:'Vertical trim at panel',system:'trim',floor,quantity:'376.8 ft stated total'},level);box(`L${floor} ACM trim ${i}`,[.12,clear,.34],[x+.55,mid,depth/2+.4],m.flashing,{partId:`acm-trim-south-${floor}-${i}`,label:'Vertical ACM trim',system:'acmtrim',floor,quantity:'429.9 ft stated total'},level)});
    box(`L${floor} through-wall flashing`,[width-1,.08,.38],[0,y+.43,depth/2+.4],m.flashing,{partId:`flashing-south-${floor}`,label:'Through-wall flashing',system:'flashing',floor,quantity:'89.4 ft stated total'},level);
    box(`L${floor} J channel`,[width-2,.07,.12],[0,y+.72,depth/2+.47],m.cement,{partId:`jchannel-south-${floor}`,label:'J Channel',system:'jchannel',floor,quantity:'130.3 ft stated on A2.32'},level);
  }

  // Paired south shaft zones and segmented folded fins.
  [-6.2,6.2].forEach((x,i)=>{
    box(`South We13 shaft ${i}`,[3.5,LEVELS[12]-2.6,.34],[x,(LEVELS[12]+2.6)/2,depth/2+.3],m.shaft,{partId:`shaft-south-${i}`,label:'We13 - exterior shaft wall / ACM metal panel',system:'shaft',quantity:'762.9 sq ft stated total'});
    box(`Continuous folded fin field ${i}`,[2.8,LEVELS[12]-2.8,.14],[x,(LEVELS[12]+2.8)/2,depth/2+.72],i===0?m.white:m.silver,{label:'A1/A3 continuous folded facade fin'});
    const points:number[]=[];for(let floor=2;floor<=10;floor++){const y=LEVELS[floor]+.12,next=LEVELS[floor+1]-.12,a=floor%2?-1.25:1.25,b=-a;points.push(x+a,y,depth/2+.81,x+b,next,depth/2+.81)}
    const seams=new THREE.BufferGeometry();seams.setAttribute('position',new THREE.Float32BufferAttribute(points,3));const lines=new THREE.LineSegments(seams,new THREE.LineBasicMaterial({color:0x626767}));lines.name=`Folded fin diagonal joints ${i}`;root.add(lines);
  });
  box('We12 insulated shaft panel',[7,4.6,.42],[0,4.1,-depth/2-.32],m.shaft12,{partId:'shaft12-level2',label:'We12 - MTL panel at shaft with 2 in R4.2 insulation',system:'shaft12',floor:2,quantity:'322.0 sq ft stated on A2.32'});
  box('Main roof slab',[width,.32,depth],[0,LEVELS[12]+.16,0],m.concrete,{label:'Main roof slab',floor:12});
  box('Mechanical penthouse',[8.6,MACHINE_ROOF-LEVELS[12],7.4],[0,(LEVELS[12]+MACHINE_ROOF)/2,-.4],m.acm,{partId:'acm-penthouse',label:'C - ACM panel / slate grey penthouse',system:'acm',floor:12,quantity:'1,543.1 sq ft stated total'});
  [-3.4,-1.7,0,1.7,3.4].forEach((x,i)=>box(`Penthouse ACM joint ${i}`,[.08,2.4,7.5],[x,30.74,-.4],m.flashing,{partId:`penthouse-trim-${i}`,label:'Vertical ACM trim',system:'acmtrim',floor:12,quantity:'included in 429.9 ft stated total'}));
  box('Penthouse cap flashing',[8.9,.11,7.7],[0,MACHINE_ROOF+.08,-.4],m.cap,{partId:'penthouse-cap',label:'Cap flashing',system:'cap',floor:12,quantity:'189.5 ft stated across A2.32/A2.41; overlap not proven'});
  box('Elevator overrun screen',[7.1,2.8,5.6],[0,MACHINE_ROOF+1.4,-.4],m.white,{label:'Elevator overrun / rooftop screen',floor:12});
  [-2.35,-1.18,0,1.18,2.35].forEach((x,i)=>box(`Overrun panel joint ${i}`,[.055,2.7,.08],[x,MACHINE_ROOF+1.4,2.43],m.silver,{label:'Rooftop screen panel joint',floor:12}));
  box('Roof access enclosure',[2.1,2.2,2.2],[2.6,LEVELS[12]+1.1,3.2],m.white,{label:'Roof access enclosure',floor:12});
  box('West roof planter',[7.2,.8,3],[-9.5,LEVELS[12]+.4,-8.7],m.planting,{label:'J metal planter / roof terrace',floor:12}); box('East roof planter',[7.2,.8,3],[9.5,LEVELS[12]+.4,-8.7],m.planting,{label:'J metal planter / roof terrace',floor:12});
  [-15.25,15.25].forEach((x,i)=>box(`South ACM outside corner ${i}`,[.12,21.8,.12],[x,14,depth/2+.42],m.corners,{partId:`corner-south-${i}`,label:'Outside corner at ACM panel',system:'corners',quantity:'74.4 ft stated on A3.11/A3.12'}));
  const ground=new THREE.Mesh(new THREE.PlaneGeometry(180,180),material(0xaaa79f));ground.rotation.x=-Math.PI/2;ground.position.y=-3.08;ground.receiveShadow=true;ground.name='Sloped site context';root.add(ground);root.rotation.y=-.04;
  box('Beach Avenue sidewalk',[58,.18,8],[0,-2.94,23],material(0xc8c5bc),{label:'Beach Avenue sidewalk / site context'});
  box('Beach Avenue road',[90,.12,16],[0,-3.05,35],material(0x55585a),{label:'Beach Avenue roadway / site context'});
  box('West landscape planter',[12,1.0,3.2],[-20,-2.5,15.2],m.planting,{label:'Landscape planter at podium'});
  box('East landscape planter',[11,1.0,3.2],[20,-2.5,15.2],m.planting,{label:'Landscape planter at podium'});
  palm('Beach Ave palm west',-8.5,15.4,3.8);palm('Beach Ave palm east',8.5,15.4,4.1);palm('Podium palm west',-20,12.8,3.5);
  return{root,parts};
}
