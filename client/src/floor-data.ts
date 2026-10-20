// Coordinates are manually traced in the 1888 x 1335 sheet reference frame.
// Overall dimensions calibrate the axes; interior grid discrepancies are reported.
// Do not use the 30.2 m property width as the tower width.
export type Pt = [number, number];
export type Run = [number, number, number, number];
export type Opening = {line: Run; kind: 'door'|'window'|'gate'; label: string};
export type Floor = {level:number; sheet:string; page:number; datum:number; height:number; footprint:Pt[]; walls:Run[]; openings:Opening[]; rails:Run[]; balconies:Pt[][]; labels:[string,number,number][]; notes:string[]};
import {SCALE_X} from './parking-evidence';
export const SCALE=SCALE_X;
const rect=(x:number,y:number,w:number,h:number):Pt[]=>[[x,y],[x+w,y],[x+w,y+h],[x,y+h]];
const perimeter=(p:Pt[]):Run[]=>p.map((a,i)=>[...a,...p[(i+1)%p.length]] as Run);
const core:Run[]=[ [836,655,979,655],[836,655,836,708],[836,708,951,708], [979,655,979,708], [866,708,866,750],[866,750,951,750],[951,708,951,750], [895,710,895,748], [866,681,952,681] ];
const residential:Run[]=[...core,
 [785,520,785,589],[785,589,830,589],[830,589,830,613],[878,520,878,654],
 [954,520,954,590],[969,520,969,576],[954,590,995,590],[995,576,995,615],
 [1039,520,1039,590],[969,576,995,576], [799,612,1046,612], [799,612,799,680],
 [879,614,879,653],[895,615,895,653],[936,615,936,653],[982,613,982,651],
 [684,680,808,680],[808,680,808,746],[808,746,836,746],
 [1010,680,1133,680],[1010,680,1010,746],[980,746,1010,746],
 [773,695,773,771],[773,714,808,714],[684,771,773,771],[773,771,773,861],
 [684,833,773,833],[730,833,730,861],[730,861,773,861],
 [799,780,799,835],[773,780,799,780],[799,835,831,835],[831,781,831,955],
 [831,781,904,781],[904,781,904,807],[904,807,955,807],[955,786,955,807],
 [839,832,867,832],[867,784,867,861],[839,858,910,858],[910,858,910,955],
 [980,782,980,955],[955,782,980,782], [1046,771,1133,771],[1046,714,1046,861],
 [1010,714,1046,714],[1046,833,1133,833],[1046,861,1090,861],[1090,833,1090,861],
 [1020,782,1020,835],[980,782,1020,782],[980,835,1020,835], [933,808,933,835]
];

const openings=(kind:Opening['kind'],lines:Run[],label:string):Opening[]=>lines.map((line,i)=>({line,kind,label:`${label} ${i+1}`}));
const residentialDoors:Run[]=[ [785,565,785,586],[812,589,830,589],[858,613,878,613],[916,613,936,613],[977,590,995,590],[1039,568,1039,589],
 [799,618,799,639],[836,683,836,705],[979,683,979,705],[911,750,933,750],
 [815,746,835,746],[980,746,1000,746],[773,726,773,746],[1046,726,1046,746],
 [773,794,773,814],[1046,794,1046,814],[799,786,799,806],[867,837,867,857],
 [887,858,907,858],[980,811,980,831],[1020,805,1020,825],[933,812,933,832],
 [707,520,730,520],[1088,520,1111,520],[704,955,727,955],[842,955,863,955],[952,955,974,955],[1091,955,1113,955] ];
const residentialWindows:Run[]=[ [735,520,756,520],[800,520,820,520],[822,520,842,520],[884,520,903,520],[914,520,934,520],[983,520,1000,520],[1002,520,1020,520],
 [684,536,684,558],[684,578,684,604],[684,621,684,649],[684,706,684,728],[684,739,684,760],[684,791,684,814],[684,873,684,895],[684,918,684,943],
 [1133,536,1133,558],[1133,578,1133,604],[1133,621,1133,649],[1133,706,1133,728],[1133,739,1133,760],[1133,791,1133,814],[1133,873,1133,895],[1133,918,1133,943],
 [735,955,756,955],[758,955,779,955],[781,955,801,955],[864,955,886,955],[887,955,907,955],[914,955,934,955],[936,955,951,955],[1000,955,1021,955],[1023,955,1044,955],[1046,955,1067,955] ];
// L-shaped balcony footprints follow the corner returns in the plans.
const balconies:Pt[][]=[ [[657,507],[671,507],[671,492],[731,492],[731,520],[684,520],[684,563],[657,563]], [[1087,492],[1148,492],[1148,507],[1161,507],[1161,563],[1133,563],[1133,520],[1087,520]], [[657,914],[684,914],[684,955],[732,955],[732,985],[670,985],[670,971],[657,971]], [[1087,955],[1133,955],[1133,914],[1161,914],[1161,971],[1148,971],[1148,985],[1087,985]], rect(841,955,137,30) ];
const residentialRails:Run[]=[ [657,507,657,563],[657,507,671,507],[671,507,671,492],[671,492,731,492],[731,492,731,520],[657,563,684,563], [1087,492,1148,492],[1087,492,1087,520],[1148,492,1148,507],[1148,507,1161,507],[1161,507,1161,563],[1133,563,1161,563], [657,914,657,971],[657,914,684,914],[657,971,670,971],[670,971,670,985],[670,985,732,985],[732,955,732,985], [1087,955,1087,985],[1087,985,1148,985],[1148,971,1148,985],[1148,971,1161,971],[1161,914,1161,971],[1133,914,1161,914], [841,955,841,985],[841,985,978,985],[978,955,978,985] ];
const footprint1:Pt[]=[[570,255],[1215,255],[1215,565],[1133,565],[1133,955],[980,955],[980,858],[837,858],[837,955],[600,955],[600,640],[570,640]];
const footprint2:Pt[]=[[570,255],[1215,255],[1215,560],[1133,560],[1133,955],[980,955],[980,781],[837,781],[837,955],[684,955],[684,642],[570,642]];
const commonNotes=['Overall written dimensions calibrate both axes. Internal grid/room positions remain unverified; see the dimension-check residual.', 'Door/window locations are traced; leaf thickness, jamb profiles, sill heights and guard height are provisional visualization values.', 'Original plan and RCP remain available at full image resolution. Visible source detail is not automatically a separately modeled component.'];
export const FLOORS:Floor[]=[
 {level:1,sheet:'A2.11',page:3,datum:0,height:3.048,footprint:footprint1,
 walls:[...perimeter(footprint1),...core, [600,517,600,640],[600,517,734,517],[686,517,686,640],[734,517,734,640],[600,640,837,640],[1013,645,1133,645],
 [686,640,686,680],[600,680,733,680],[686,680,686,709],[600,757,686,757],[600,816,686,816],[600,870,686,870],[686,739,686,888],
 [734,704,734,955],[734,704,810,704],[780,704,780,750],[780,750,837,750],[837,750,837,858], [734,790,837,790],[800,750,800,790],
 [838,805,910,805],[910,805,910,858],[980,750,980,858],[838,858,980,858], [978,613,1013,613],[978,613,978,656],[1013,517,1013,714],
 [1013,714,1133,714],[1047,714,1047,836],[1047,771,1133,771],[1047,836,1133,836],[1074,836,1074,861], [994,780,994,955],[994,780,1047,780],[994,836,1047,836],[994,861,1090,861],
 [980,517,980,613],[980,517,1013,517],[600,995,838,995],[980,995,1133,995] ],
 openings:[...openings('door',[[600,619,600,638],[616,517,637,517],[712,517,733,517],[981,613,1002,613],[686,701,686,722],[686,764,686,785],[686,826,686,847],[734,723,734,744],[800,768,800,789],[837,683,837,705],[979,683,979,705],[910,750,932,750],[858,805,880,805],[854,858,880,858],[1013,688,1013,709],[1047,729,1047,750],[1047,794,1047,815],[994,813,994,834],[1074,839,1074,860],[624,955,646,955],[773,955,795,955],[1091,955,1113,955]],'Door / source-plan opening'),
 ...openings('gate',[[1133,568,1133,612]],'G · east metal grating / A3.13; not a garage door'),
 ...openings('window',[[600,698,600,731],[600,775,600,802],[600,832,600,858],[600,886,600,919],[651,955,678,955],[738,955,765,955],[802,955,832,955],[881,858,908,858],[911,858,942,858],[944,858,976,858],[1000,955,1030,955],[1034,955,1064,955],[1068,955,1090,955],[1133,670,1133,699],[1133,728,1133,755],[1133,789,1133,816],[1133,879,1133,907],[1133,920,1133,941]],'D1 glazing')],
 rails:[[600,995,838,995],[600,955,600,995],[838,955,838,995],[980,995,1133,995],[980,955,980,995],[1133,974,1133,995]],balconies:[rect(600,955,238,40),rect(980,955,153,40)],
 labels:[['Parking 01–17',880,425],['Electrical room',648,566],['Unit 102 · 3 bedrooms',662,908],['Amenity room',783,904],['Lobby / vestibule',909,782],['Recessed entrance',911,923],['Unit 101 · 3 bedrooms',1085,906]],
 notes:['Standard parking clearance note reads MIN. 2.0 m (not centimetres). Infrastructure is to be at least 2.0 m A.F.F.','Main entrance is recessed between the amenity room and Unit 101; the parking entrance is on the east side.',...commonNotes]},
 {level:2,sheet:'A2.12',page:4,datum:3.048,height:2.643,footprint:footprint2,
 walls:[...perimeter(footprint2),...core,[570,445,655,445],[655,445,655,641],[684,520,837,520],[684,520,684,643],[684,643,837,643],[837,630,873,630],[873,630,873,655], [1019,520,1019,654],[1019,520,1133,520],[1113,439,1215,439],[1113,439,1113,517],[1113,517,1215,517],
 [684,678,837,678],[760,678,760,707],[760,707,837,707],[760,740,837,740],[760,740,760,904],[684,838,760,838],[724,838,724,904],[684,904,760,904],[797,741,797,839],[797,839,837,839],[837,741,837,781],
 [1013,655,1013,741],[1013,714,1133,714],[1047,714,1047,836],[1047,771,1133,771],[1047,836,1133,836],[1074,836,1074,866],[1020,781,1020,836],[980,781,1047,781],[980,836,1020,836],[980,866,1090,866] ],
 openings:[...openings('door',[[570,323,570,350],[1113,467,1113,489],[684,526,684,549],[684,605,684,626],[765,520,787,520],[821,520,842,520],[1020,520,1041,520],[655,553,655,575],[655,590,655,612],[836,683,836,705],[979,683,979,705],[911,750,933,750],[808,678,830,678],[837,752,837,775],[797,798,797,819],[724,859,724,880],[1013,688,1013,709],[1047,728,1047,749],[1047,794,1047,815],[1020,811,1020,832],[704,955,727,955],[1091,955,1113,955],[684,721,684,742]],'Door / source-plan opening'),
 ...openings('window',[[684,766,684,791],[684,809,684,831],[735,955,756,955],[758,955,779,955],[781,955,810,955],[844,858,870,858],[874,858,900,858],[904,858,930,858],[934,858,960,858],[1000,955,1021,955],[1023,955,1044,955],[1046,955,1067,955],[1133,670,1133,696],[1133,728,1133,750],[1133,789,1133,815],[1133,875,1133,901],[1133,920,1133,941]],'D1 glazing')],
 rails:residentialRails.slice(12,24).concat([[639,708,639,770],[639,708,684,708],[639,770,684,770]]),balconies:[balconies[2],balconies[3],rect(639,708,45,62)],
 labels:[['Parking / accessible spaces',865,411],['Bicycle storage',764,576],['Bicycle storage',1072,591],['Garbage / recycling',1165,480],['Studio 203',723,764],['Studio 202',786,918],['Unit 201 · 3 bedrooms',1081,912],['OPEN TO BELOW',909,819],['Entry canopy / soffit',909,909]],
 notes:['Contains studios 202/203 and three-bedroom Unit 201, plus bicycle storage and parking.','The central lobby void is open to below; it must not be filled with an apartment or floor slab.','Parking infrastructure clearance is noted as MIN. 2.3 m A.F.F. Ramp and bicycle-room elevations need separate slope coordination.',...commonNotes]},
 ...[3,4].map(level=>({level,sheet:`A2.${level+10}`,page:level+2,datum:level===3?5.691:8.334,height:2.643,footprint:rect(684,520,449,435),walls:[...perimeter(rect(684,520,449,435)),...residential],openings:[...openings('door',residentialDoors,'Door / source-plan opening'),...openings('window',residentialWindows,'D1 glazing')],rails:residentialRails,balconies,labels:[[`Unit ${level}05 · 1 bedroom`,739,634],[`Unit ${level}01 · 2 bedrooms`,1080,636],[`Unit ${level}04 · 2 bedrooms`,743,906],[`Unit ${level}03 · 1 bedroom`,903,918],[`Unit ${level}02 · 2 bedrooms`,1080,906],['Stairs 1 / 2',910,681],['Elevator',925,730]] as [string,number,number][],notes:[level===3?'West metal roof over bicycle parking is shown only on Level 3.':'Fourth-floor revision clouds mark southwest/central facade junctions; preserved on source sheet.','Five distinct apartments surround two stair flights and an elevator. Corner balconies have 90-degree returns.',...commonNotes]}))
];
// Upper residential floors retain their own source and review status.
for(let level=5;level<=9;level++){
 const f=structuredClone(FLOORS[3]);f.level=level;f.page=level+2;f.sheet=`A2.${level+10}`;f.datum=3.048+(level-2)*2.643;
 f.labels=f.labels.map(([name,x,y])=>[name.replace(/Unit 4/g,`Unit ${level}`),x,y]);
 f.notes=[`Plan ${f.sheet} reviewed: general apartment arrangement repeats. Local partition and door differences have not been dimensionally reconciled.`,...(level===6||level===9?['Crossover level identified by the elevations; detailed stair/corridor changes remain under review.']:[]),...commonNotes];FLOORS.push(f);
}
const tenthOutline:Pt[]=[[684,568],[798,568],[798,520],[1020,520],[1020,568],[1133,568],[1133,858],[986,858],[986,955],[831,955],[831,858],[684,858]];
FLOORS.push({level:10,sheet:'A2.20',page:12,datum:24.192,height:2.64,footprint:rect(684,520,449,435),
 walls:[...perimeter(tenthOutline),...core,[684,678,801,678],[1014,678,1133,678],[801,613,801,740],[1014,613,1014,740],[801,740,837,740],[980,740,1014,740],[684,758,770,758],[1047,758,1133,758],[770,678,770,795],[1047,678,1047,795],[770,795,837,795],[980,795,1047,795],[866,520,866,592],[948,520,948,614],[798,592,907,592],[907,592,907,614],[801,614,1014,614],[837,782,903,782],[903,782,903,809],[903,809,955,809],[955,782,955,809],[866,809,866,873],[866,873,831,873],[910,809,910,955],[950,809,950,873],[950,873,986,873],[831,890,986,890]],
 openings:[...openings('door',[[836,683,836,705],[979,683,979,705],[911,750,933,750],[801,639,801,660],[1014,639,1014,660],[837,765,837,785],[980,765,980,785],[866,846,866,867],[950,846,950,867],[798,541,798,563],[1020,541,1020,563],[713,568,735,568],[1086,568,1108,568],[713,858,735,858],[1086,858,1108,858]],'Level 10 opening trace'),...openings('window',[[813,520,840,520],[885,520,925,520],[970,520,1000,520],[684,590,684,638],[1133,590,1133,638],[684,698,684,731],[1133,698,1133,731],[684,787,684,833],[1133,787,1133,833],[753,858,797,858],[1025,858,1070,858],[845,955,890,955],[931,955,973,955]],'Level 10 glazing trace')],
 rails:residentialRails,balconies,labels:[['Unit 1004 · 2 bedrooms',740,638],['Unit 1001 · 1 bedroom',1080,638],['Unit 1003 · 2 bedrooms',750,816],['Unit 1002 · 2 bedrooms',1070,816],['Private patios',747,913]],notes:['Four apartments with recessed corner patios; separately traced from A2.20. Interior thicknesses and detailed openings remain provisional.',...commonNotes]});
FLOORS.push({level:11,sheet:'A2.21',page:13,datum:26.832,height:2.615,footprint:rect(684,520,449,435),walls:[...perimeter(rect(836,655,145,136)),[836,709,981,709],[895,709,895,751],[950,709,950,751],[895,751,981,751],[915,751,915,791]],openings:openings('door',[[836,658,836,680],[836,752,836,775],[938,791,958,791],[981,721,981,742]],'Roof access / source trace'),rails:[[684,568,684,955],[684,955,1133,955],[1133,568,1133,955],[684,520,1133,520],[798,614,798,740],[1020,614,1020,740]],balconies:[],labels:[['Main roof terrace · Level 11',909,851],['Core / WC / mechanical',910,759],['Gravel ballast',741,662]],notes:['Main roof is not an extra apartment floor. Deck levels, furniture, planters and privacy screens are not fully modeled.',...commonNotes]});
FLOORS.push({level:12,sheet:'A2.22',page:14,datum:29.447,height:2.59,footprint:rect(836,655,145,136),walls:[...perimeter(rect(836,655,145,136)),[836,709,981,709],[895,709,895,751],[950,709,950,751]],openings:openings('door',[[950,791,973,791],[836,720,836,741]],'Mechanical access / source trace'),rails:[],balconies:[],labels:[['Mechanical room / elevator overrun',910,755]],notes:['Mechanical enclosure outline traced from A2.22; equipment and roof ladder not fully modeled.',...commonNotes]});
FLOORS.push({level:13,sheet:'A2.23',page:15,datum:32.037,height:.457,footprint:rect(836,655,145,136),walls:[],openings:[],rails:[],balconies:[],labels:[['Mechanical room roof',910,725]],notes:['Top roof plane at elevation datum; drainage and flashing details unresolved.',...commonNotes]});
