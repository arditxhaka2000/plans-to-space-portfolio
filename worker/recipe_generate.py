"""Deterministic recipe compiler. Only this trusted entrypoint is executed by the server."""
import argparse, hashlib, json, math, struct
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import triangulate
from building_recipe import read_recipe

VERSION='recipe-1.1.0'

def generate(recipe, output):
    data=recipe.model_dump(mode='json'); canonical=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
    recipe_hash=hashlib.sha256(canonical).hexdigest()
    nodes=[];meshes=[];views=[];accessors=[];binary=bytearray();components=[];expanded={}
    mats={m.id:i for i,m in enumerate(recipe.materials)}
    def accessor(values):
        a=np.asarray(values,dtype='<f4').reshape(-1,3)
        if not np.isfinite(a).all() or np.abs(a).max()>20000: raise ValueError('Nonfinite or out-of-bounds geometry')
        idx=len(accessors); views.append({'buffer':0,'byteOffset':len(binary),'byteLength':a.nbytes});binary.extend(a.tobytes())
        accessors.append({'bufferView':len(views)-1,'componentType':5126,'count':len(a),'type':'VEC3','min':a.min(axis=0).tolist(),'max':a.max(axis=0).tolist()});return idx
    def mesh(points,material):
        p=np.asarray(points).reshape(-1,3,3);n=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);lens=np.linalg.norm(n,axis=1)
        if (lens<1e-10).any(): raise ValueError('Degenerate triangle')
        normals=np.repeat(n/lens[:,None],3,axis=0)
        i=len(meshes);meshes.append({'primitives':[{'attributes':{'POSITION':accessor(p),'NORMAL':accessor(normals)},'material':mats[material]}]});return i
    cube=np.array([[-.5,-.5,-.5],[.5,-.5,-.5],[.5,.5,-.5],[-.5,.5,-.5],[-.5,-.5,.5],[.5,-.5,.5],[.5,.5,.5],[-.5,.5,.5]])
    faces=[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[3,7,6],[3,6,2],[0,4,7],[0,7,3],[1,2,6],[1,6,5]]
    cubes={m.id:mesh(cube[faces],m.id) for m in recipe.materials}
    def node(id,kind,mi,evidence,owner=None,**transform):
        if any(not math.isfinite(x) or abs(x)>20000 for a in transform.values() for x in a): raise ValueError('Invalid transform')
        nodes.append({'name':id,'mesh':mi,'extras':{'componentId':id,'elementType':kind,'recipeElementId':owner or id,'evidence':evidence.model_dump(),'reviewed':False},**transform})
        components.append({'id':id,'nodeIndex':len(nodes)-1,'kind':kind,'recipeElementId':owner or id,'evidence':evidence.model_dump()});expanded.setdefault(owner or id,[]).append(id)
    def box(id,c,s,m,kind,e,owner=None,angle=0):
        if min(s)<=1e-7:return
        node(id,kind,cubes[m],e,owner,translation=list(c),scale=list(s),rotation=[0,math.sin(angle/2),0,math.cos(angle/2)])
    for b in recipe.boxes:box(b.id,b.center,b.size,b.material,b.kind,b.evidence)
    for w in recipe.walls:
        dx=w.end[0]-w.start[0];dz=w.end[1]-w.start[1];length=math.hypot(dx,dz);angle=-math.atan2(dz,dx)
        def part(id,x,y,width,height,mat,kind,ev,owner):
            box(id,[w.start[0]+dx*x/length,w.base+y,w.start[1]+dz*x/length],[width,height,w.thickness],mat,kind,ev,owner,angle)
        xs=sorted({0,length,*[x for o in w.openings for x in [o.offset-o.width/2,o.offset+o.width/2]]});ys=[]
        for i,(a,b) in enumerate(zip(xs,xs[1:])):
            ys=sorted({0,w.height,*[y for o in w.openings if o.offset-o.width/2<(a+b)/2<o.offset+o.width/2 for y in [o.sill,o.sill+o.height]]})
            for j,(c,d) in enumerate(zip(ys,ys[1:])):
                x=(a+b)/2;y=(c+d)/2
                if not any(abs(x-o.offset)<o.width/2 and o.sill<y<o.sill+o.height for o in w.openings):part(f'{w.id}/cell/{i}/{j}',x,y,b-a,d-c,w.material,'wall',w.evidence,w.id)
        for o in w.openings:
            part(o.id,o.offset,o.sill+o.height/2,o.width-2*o.frame,o.height-2*o.frame,o.material,o.kind,o.evidence,o.id)
            for suffix,x,y,ww,hh in [('left',o.offset-o.width/2+o.frame/2,o.sill+o.height/2,o.frame,o.height),('right',o.offset+o.width/2-o.frame/2,o.sill+o.height/2,o.frame,o.height),('bottom',o.offset,o.sill+o.frame/2,o.width-2*o.frame,o.frame),('top',o.offset,o.sill+o.height-o.frame/2,o.width-2*o.frame,o.frame)]:part(f'{o.id}/frame/{suffix}',x,y,ww,hh,o.frameMaterial,o.kind,o.evidence,o.id)
    levels={l.id:l.elevation for l in recipe.levels}
    for v in recipe.volumes:
        p=Polygon(v.footprint);y=levels[v.level];points=[]
        for t in triangulate(p):
            if p.covers(t):
                coords=list(t.exterior.coords)[:3];points.extend([[x,y,z] for x,z in coords]);points.extend([[x,y-v.slabThickness,z] for x,z in reversed(coords)])
        for a,b in zip(v.footprint,v.footprint[1:]+v.footprint[:1]):
            points.extend([[a[0],y,a[1]],[b[0],y,b[1]],[b[0],y-v.slabThickness,b[1]],[a[0],y,a[1]],[b[0],y-v.slabThickness,b[1]],[a[0],y-v.slabThickness,a[1]]])
        node(v.id,'slab',mesh(points,v.material),v.evidence)
    for r in recipe.roofs:
        a,b,c=np.array(r.vertices[:3]);n=np.cross(b-a,c-a);p=Polygon([(v[0],v[2]) for v in r.vertices]);points=[]
        for t in triangulate(p):
            if p.covers(t):
                for x,z in list(t.exterior.coords)[:3]:points.append([x,a[1]-(n[0]*(x-a[0])+n[2]*(z-a[2]))/n[1],z])
        node(r.id,'roof',mesh(points,r.material),r.evidence)
    if not nodes or len(nodes)>45000 or len({n['name'] for n in nodes})!=len(nodes):raise ValueError('Empty model, generated ID collision or excessive output')
    groups=[{'id':g.id,'name':g.name,'members':[i for m in g.members for i in expanded.get(m,[])]} for g in recipe.groups]
    grouped={m for g in recipe.groups for m in g.members}
    groups += [{'id':o.id,'name':o.id,'members':expanded[o.id]} for w in recipe.walls for o in w.openings if o.id not in grouped]
    if sum(len(g['members']) for g in groups)>100000 or any(len(g['members'])>10000 for g in groups):raise ValueError('Expanded group membership exceeds limits')
    manifest={'generatorVersion':VERSION,'recipeHash':recipe_hash,'sourceDocumentHash':recipe.sourceDocumentHash.lower(),'interpretation':recipe.interpretation,'units':recipe.units,'axes':recipe.axes,'assumptions':recipe.assumptions,'unresolved':recipe.unresolved,'components':components,'groups':groups}
    gltf={'asset':{'version':'2.0','generator':VERSION,'extras':{'recipeHash':recipe_hash,'interpretation':recipe.interpretation}},'scene':0,'scenes':[{'nodes':list(range(len(nodes)))}],'nodes':nodes,'meshes':meshes,'materials':[{'name':m.id,'doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':m.color,'metallicFactor':.25,'roughnessFactor':.5}} for m in recipe.materials],'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors}
    raw=json.dumps(gltf,separators=(',',':')).encode();raw+=b' '*(-len(raw)%4);binary+=b'\0'*(-len(binary)%4)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'model.glb').write_bytes(struct.pack('<III',0x46546c67,2,28+len(raw)+len(binary))+struct.pack('<II',len(raw),0x4e4f534a)+raw+struct.pack('<II',len(binary),0x004e4942)+binary)
    (output/'evidence.json').write_text(json.dumps(manifest,separators=(',',':')),encoding='utf-8')
    (output/'recipe.json').write_bytes(canonical)
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--recipe',required=True);parser.add_argument('--output');parser.add_argument('--validate',action='store_true');args=parser.parse_args()
    try:
        recipe=read_recipe(args.recipe)
        if args.validate:print(json.dumps(recipe.model_dump(mode='json'),sort_keys=True,separators=(',',':')))
        else:print(json.dumps({'components':len(generate(recipe,args.output)['components']),'version':VERSION}))
    except ValueError as error:
        import sys
        if hasattr(error,'errors'):
            message='; '.join('.'.join(map(str,e['loc']))+': '+e['msg'] for e in error.errors(include_input=False,include_url=False)[:6])
        else:message=str(error)
        print(json.dumps({'error':message[:2000]}));sys.exit(2)
