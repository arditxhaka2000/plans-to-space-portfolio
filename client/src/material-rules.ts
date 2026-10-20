// Semantic material codes are separate from takeoff markup colours.
// Finish RGB values are visual approximations, not manufacturer colour calibration.
export const MATERIALS:Record<string,{name:string;finish:number;markup?:number}>={
 A1:{name:'White painted concrete',finish:0xe7e5df},A2:{name:'Pink painted concrete',finish:0xc3aaac},A3:{name:'Silver painted concrete',finish:0xb6b7b4},A4:{name:'Charcoal painted concrete',finish:0x51565a},
 C:{name:'ACM · slate grey',finish:0x52565b,markup:0xad63b4},L:{name:'Cementitious panel · white',finish:0xf1f0e9,markup:0xf4e34a},
 D1:{name:'White-framed glazing',finish:0xe9e8e3},E1:{name:'White glass guard',finish:0xe9e8e3},E2:{name:'Charcoal glass guard',finish:0x51565a},E3:{name:'Existing guard',finish:0x888e8b},
 F:{name:'Metal door',finish:0x888e8b},G:{name:'White metal grating',finish:0xf1f0e9},H:{name:'White painted existing brick',finish:0xe7e5df},I:{name:'Overhead garage door',finish:0x888e8b},J:{name:'Metal planter',finish:0x888e8b},K1:{name:'Louvered HVAC vent',finish:0x888e8b},K2:{name:'Vent termination cap',finish:0x888e8b},M:{name:'Metal rainwater leader',finish:0x888e8b},FS:{name:'Fire shutter',finish:0x888e8b}
};
export function materialColor(code:string,takeoff:boolean){const m=MATERIALS[code];if(!m)throw new Error('Unmapped material code: '+code);return takeoff&&m.markup!==undefined?m.markup:m.finish}
