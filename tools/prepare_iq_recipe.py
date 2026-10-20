"""Offline, explicit conversion of the reviewed IQ attachment geometry to recipe data.

Reads only ZIP JSON/GLB data; never imports or runs attached Python. Not used by PDF processing.
"""
import argparse, hashlib, json, struct, sys, zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from building_recipe import Recipe

def convert(archive,pdf):
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist()
        if any(i.file_size>10_000_000 or i.filename.startswith(('/', '\\')) or '..' in Path(i.filename).parts for i in entries):raise ValueError('Unsafe archive')
        raw=z.read('IQ-Buildings-draft.glb');g=json.loads(raw[20:20+struct.unpack_from('<I',raw,12)[0]])
        evidence=json.loads(z.read('components.json'));by_name={c['name']:c for c in evidence['components']}
    materials=[{'id':f'm{i}','color':m['pbrMetallicRoughness']['baseColorFactor']} for i,m in enumerate(g['materials'])]
    recipe={'schemaVersion':'1.0','label':'IQ Buildings — manually interpreted exterior example','interpretation':'manually-interpreted','units':'metres','axes':'X-right,Y-up,Z-plan-down','sourceDocumentHash':hashlib.sha256(Path(pdf).read_bytes()).hexdigest(),'assumptions':evidence['limitations']+['Reproduces supplied source tower/slab geometry. Facade bays are rebuilt as walls with actual hosted openings and four-sided frames; this changes original spandrel/head/mullion detailing slightly.','Source geometry was read as data from the supplied GLB after inspecting generate.py; no automatic PDF interpretation occurs.','Volume footprints describe floor slabs; envelope walls are explicitly listed. Roof planes are surfaces.'], 'unresolved':['32.8 m section roof versus 36.57 m facade dimension remains unresolved.','Geographic orientation, entrances, basements and tenant fitouts are unverified or absent.'],'materials':materials,'levels':[{'id':f'L{i}','elevation':y} for i,y in enumerate([0,4]+[7.6+3.6*k for k in range(8)])], 'boxes':[],'volumes':[],'walls':[],'roofs':[],'groups':[]}
    nodes={n['name']:n for n in g['nodes']}
    def ev(name):
        c=by_name[name];return {'pages':c['sourcePages'],'status':'estimated' if c['evidenceStatus'].startswith('estimated') else 'interpreted','reference':'Supplied authored IQ draft; pages indicate drawing inputs, not verified per-element matches.'}
    for name,n in nodes.items():
        c=n['translation'];s=n['scale'];typ=n['extras']['elementType'];id=n['extras']['componentId'];material=f"m{g['meshes'][n['mesh']]['primitives'][0]['material']}"
        if name.endswith(('/spandrel','/head','/mullion')):continue
        if name.endswith('/glass'):
            stem=name[:-6];recipe['groups'].append({'id':stem,'name':stem,'members':[id]});ground=nodes[stem+'/spandrel'];mullion=nodes[stem+'/mullion'];height=mullion['scale'][1];base=mullion['translation'][1]-height/2;horizontal=s[0]>.1;width=(s[0] if horizontal else s[2])+.08
            start=[c[0]-width/2,c[2]] if horizontal else [c[0],c[2]-width/2];end=[c[0]+width/2,c[2]] if horizontal else [c[0],c[2]+width/2]
            recipe['walls'].append({'id':stem+'/host','material':f"m{ground['mesh']}",'evidence':ev(name),'start':start,'end':end,'base':base,'height':height,'thickness':.1,'openings':[{'id':id,'kind':'window','offset':width/2,'sill':height*.27,'width':width-.04,'height':height*.62,'frame':.02,'material':material,'frameMaterial':'m2','evidence':ev(name)}]})
        elif typ=='slab':
            x,y,z=c;w,t,d=s;level=int(name.split('/level')[1].split('/')[0]);recipe['volumes'].append({'id':id,'material':material,'evidence':ev(name),'footprint':[[x-w/2,z-d/2],[x+w/2,z-d/2],[x+w/2,z+d/2],[x-w/2,z+d/2]],'level':f'L{level}','height':4 if level==0 else 3.6,'slabThickness':t})
        else:recipe['boxes'].append({'id':id,'kind':typ,'center':c,'size':s,'material':material,'evidence':ev(name)})
    return Recipe.model_validate(recipe)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--zip',required=True);p.add_argument('--pdf',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=convert(a.zip,a.pdf);out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(r.model_dump_json(indent=2),encoding='utf-8');print(len(r.walls),'facade bays;',len(r.volumes),'floor footprints')
