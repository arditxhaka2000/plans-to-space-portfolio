// Written dimensions do not certify the manually traced positions.
export const PARKING_EVIDENCE={
 propertyWidth:{metres:(99+1/12)*.3048,raw:`99'-1"`,sheet:'A2.11 / A3.11'},
 propertyDepth:{metres:(130+9.25/12)*.3048,raw:`130'-9 1/4"`,sheet:'A3.13'},
 standard:{width:2.5,length:5.5,source:'A2.11, PDF 3'},
 small:{width:2.3,length:4.6,source:'A2.11, PDF 3'},
 existing:{width:(8+2/12)*.3048,length:18*.3048,source:'A2.11, PDF 3'},
 clearHeight:{level1:2,level2:2.3,source:'A2.11/A2.12 parking notes'},
};
export const SOURCE_FRAME={west:566,east:1217,north:199,south:1057};
export const SCALE_X=PARKING_EVIDENCE.propertyWidth.metres/(SOURCE_FRAME.east-SOURCE_FRAME.west);
export const SCALE_Z=PARKING_EVIDENCE.propertyDepth.metres/(SOURCE_FRAME.south-SOURCE_FRAME.north);
export const CALIBRATION_CHECK={writtenGridCD:17*.3048,tracedGridCD:(1020-910)*SCALE_X,get gridResidual(){return this.tracedGridCD-this.writtenGridCD}};
