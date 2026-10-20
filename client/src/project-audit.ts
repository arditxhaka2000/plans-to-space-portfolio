import * as THREE from 'three';
import {MATERIALS} from './material-rules';
export function auditModel(root:THREE.Object3D){
 const entries:Record<string,{count:number;unverified:number;codes:Set<string>}>=Object.fromEntries(['south','north','east','west'].map(d=>[d,{count:0,unverified:0,codes:new Set<string>()}]));
 root.traverse(o=>{if(!(o instanceof THREE.Mesh))return;const d=o.userData.elevation??(String(o.userData.sheet).includes('A3.11')?'south':null);if(!d||!entries[d])return;const e=entries[d];e.count++;if(o.userData.verification!=='verified')e.unverified++;const code=o.userData.materialCode??o.userData.southCode;if(code)e.codes.add(code)});
 return Object.entries(entries).map(([direction,e])=>({direction,components:e.count,unverified:e.unverified,missingCodes:Object.keys(MATERIALS).filter(c=>!e.codes.has(c)),unknownCodes:[...e.codes].filter(c=>!MATERIALS[c]),status:'REVIEW REQUIRED'}));
}
