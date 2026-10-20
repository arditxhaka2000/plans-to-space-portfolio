"""Apply checksum-bound duplicate-instance corrections without rewriting geometry.

Retains the original node array and binary chunk. Removed instances become empty
nodes. The remapping manifest is explicit evidence, never an index-based guess
between unrelated files. No CAD parameters are inferred.
"""
import argparse, hashlib, json, struct
from pathlib import Path
import numpy as np
from inspect_glb import read

p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('corrections');p.add_argument('output');args=p.parse_args()
source=Path(args.source);output=Path(args.output)
if source.resolve()==output.resolve():raise ValueError('Preserve the original GLB; choose a new output path')
raw=source.read_bytes();corrections=json.loads(Path(args.corrections).read_text());assert hashlib.sha256(raw).hexdigest()==corrections['sourceSha256'],'Source checksum mismatch'
doc,meshes=read(source);by_node={m['index']:m for m in meshes};remaps={}
for removed,kept in corrections['mergeDuplicates']:
    a,b=by_node[removed],by_node[kept]
    assert a['name']==b['name'] and a['color']==b['color'] and np.array_equal(a['vertices'],b['vertices']) and np.array_equal(a['faces'],b['faces']),'Not an exact duplicate'
    assert not doc['nodes'][removed].get('children'),'Cannot remove a parent assembly'
    del doc['nodes'][removed]['mesh'];remaps[removed]=kept
old_length=struct.unpack_from('<I',raw,12)[0];tail=raw[20+old_length:];encoded=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode();encoded+=b' '*((-len(encoded))%4)
result=struct.pack('<III',0x46546c67,2,20+len(encoded)+len(tail))+struct.pack('<II',len(encoded),0x4e4f534a)+encoded+tail
output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(result)
_,reloaded=read(output);assert len(reloaded)==len(meshes)-len(remaps)
remaining={m['index']:m for m in reloaded}
for m in meshes:
    counterpart=remaining[remaps.get(m['index'],m['index'])]
    assert np.array_equal(m['vertices'],counterpart['vertices']) and np.array_equal(m['faces'],counterpart['faces'])
manifest={'sourceSha256':corrections['sourceSha256'],'revisionSha256':hashlib.sha256(result).hexdigest(),'description':corrections['description'],'sourcePages':corrections['sourcePages'],'nodeRemaps':[{'oldNode':m['index'],'newNode':remaps.get(m['index'],m['index']),'kind':'duplicate-merged' if m['index'] in remaps else 'unchanged-verified'} for m in meshes],'unresolved':corrections['unresolved']}
output.with_suffix('.remap.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'output':str(output),'meshComponents':len(reloaded),'removedDuplicateInstances':len(remaps),'allSurvivingGeometryUnchanged':True,'revisionSha256':manifest['revisionSha256']}))
