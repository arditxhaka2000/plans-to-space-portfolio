"""Reproducible read-only geometry audit and orthographic renders of a GLB.
Coordinates remain unchanged; projections use X/Y/Z axes, not inferred north.
"""
import argparse, collections, hashlib, json, struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

def read(path):
    raw=Path(path).read_bytes();size=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+size]);binary=raw[28+size:]
    def accessor(index):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']];n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']];dtype=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]);offset=v.get('byteOffset',0)+a.get('byteOffset',0);return np.ndarray((a['count'],n),dtype=dtype,buffer=binary,offset=offset,strides=(v.get('byteStride',dtype.itemsize*n),dtype.itemsize)).copy()
    meshes=[]
    def walk(i,parent):
        node=doc['nodes'][i];m=np.eye(4)
        if 'matrix' in node:m=np.array(node['matrix']).reshape(4,4).T
        else:
            x,y,z,w=node.get('rotation',[0,0,0,1]);m[:3,:3]=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])@np.diag(node.get('scale',[1,1,1]));m[:3,3]=node.get('translation',[0,0,0])
        m=parent@m
        if 'mesh' in node:
            for primitive in doc['meshes'][node['mesh']]['primitives']:
                if primitive.get('mode',4)!=4:continue
                v=accessor(primitive['attributes']['POSITION']);v=(np.c_[v,np.ones(len(v))]@m.T)[:,:3];f=accessor(primitive['indices']).reshape(-1,3) if 'indices' in primitive else np.arange(len(v)).reshape(-1,3)
                mat=doc.get('materials',[])[primitive['material']] if 'material' in primitive else {};color=mat.get('pbrMetallicRoughness',{}).get('baseColorFactor',[.7,.7,.7,1]);meshes.append({'index':i,'name':node.get('name',''),'vertices':v,'faces':f,'color':color})
        for child in node.get('children',[]):walk(child,m)
    for i in doc['scenes'][doc.get('scene',0)]['nodes']:walk(i,np.eye(4))
    return doc,meshes

def main():
    p=argparse.ArgumentParser();p.add_argument('glb');p.add_argument('--output',required=True);p.add_argument('--pdf');a=p.parse_args();out=Path(a.output);out.mkdir(parents=True,exist_ok=True);doc,meshes=read(a.glb)
    vertices=np.concatenate([m['vertices'] for m in meshes]);lo,hi=vertices.min(0),vertices.max(0)
    fingerprints=collections.defaultdict(list)
    components=[]
    for m in meshes:
        v=m['vertices'];tri=v[m['faces']];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)/2
        fingerprint=hashlib.sha256(v.tobytes()+m['faces'].tobytes()).hexdigest();fingerprints[fingerprint].append(m['index'])
        components.append({'node':m['index'],'name':m['name'],'min':v.min(0).tolist(),'max':v.max(0).tolist(),'degenerateTriangles':int((area<1e-12).sum())})
    report={'sourceSha256':hashlib.sha256(Path(a.glb).read_bytes()).hexdigest(),'nodes':len(doc['nodes']),'meshComponents':len(meshes),'boundsMeters':[lo.tolist(),hi.tolist()],'extentMeters':(hi-lo).tolist(),'duplicateGeometryCandidates':[ids for ids in fingerprints.values() if len(ids)>1],'components':components,'warning':'Coordinate bounds are model-calculated, not drawing-verified dimensions. Coincident pieces need semantic review before deletion.'}
    (out/'geometry-audit.json').write_text(json.dumps(report,indent=2))
    for name,horizontal,vertical,depth,sign in [('top',0,2,1,1),('minus-z',0,1,2,-1),('plus-z',0,1,2,1),('minus-x',2,1,0,-1),('plus-x',2,1,0,1)]:
        image=Image.new('RGB',(1800,1100),'#eef1ec');draw=ImageDraw.Draw(image);scale=min(1640/(hi[horizontal]-lo[horizontal]),940/(hi[vertical]-lo[vertical]));cx=(hi[horizontal]+lo[horizontal])/2;cy=(hi[vertical]+lo[vertical])/2
        triangles=[]
        for m in meshes:
            for triangle in m['vertices'][m['faces']]:triangles.append((triangle[:,depth].mean()*sign,triangle,m['color']))
        for _,tri,color in sorted(triangles,key=lambda t:t[0]):
            hs=-1 if name in ('minus-z','plus-x') else 1;vs=-1 if name=='top' else 1
            pts=[(900+hs*(v[horizontal]-cx)*scale,570-vs*(v[vertical]-cy)*scale) for v in tri];rgb=tuple(int(255*max(0,min(1,x))) for x in color[:3]);draw.polygon(pts,fill=rgb,outline=tuple(int(x*.85) for x in rgb))
        draw.text((35,25),f'{name} orthographic | original GLB | metres, Y up | NOT dimensionally verified',fill='black');image.save(out/f'{name}.png')
    if a.pdf:
        import pypdfium2 as pdfium
        pdf=pdfium.PdfDocument(a.pdf)
        for n in [7,9,12,13]:pdf[n-1].render(scale=1.5).to_pil().save(out/f'pdf-{n}.png')
    print(json.dumps({k:v for k,v in report.items() if k!='components'},indent=2))
if __name__=='__main__':main()
