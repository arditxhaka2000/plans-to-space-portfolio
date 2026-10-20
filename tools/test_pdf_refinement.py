"""Actual UMD seam recognition, coordinate and cache regression; no database writes."""
import hashlib,json,sys,tempfile,copy
from pathlib import Path
import pypdfium2
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'worker'))
import pipeline
source=next((root/'work/chatgpt-glb-handoff/pdf-to-glb-handoff/source-pdfs').glob('UMD*'))
data=json.loads((root/'work/context-benchmark/umd.json').read_text(encoding='utf-8'))
records=[r for r in data['observations'] if not r.get('variant')]
original_text=[r['text'] for r in records]
cache=Path(tempfile.mkdtemp(prefix='pdf-refinement-test-',dir=root/'work'))
with pypdfium2.PdfDocument(source) as pdf:
    page=pdf[8];digest=hashlib.sha256(source.read_bytes()).hexdigest()
    first=pipeline.refine_crop_seams(page,records,cache,digest,9)
    label=next(r for r in first if r['text']=='SOLAR PV ARRAY - SPEC# 263100')
    assert 'alternative-reading-review' in label['reviewFlags']
    assert 1550<label['bounds'][0]<1560 and 1775<label['bounds'][2]<1790,label
    assert 482<label['bounds'][1]<490 and 494<label['bounds'][3]<502,label
    assert label['pixelsPerPoint']==6 and label['words']
    assert [r['text'] for r in records]==original_text,'Source OCR was overwritten'
    class NoInference:
        def __call__(self,*args,**kwargs):raise AssertionError('Cache hit reran OCR')
    pipeline._ocr=NoInference()
    second=pipeline.refine_crop_seams(page,records,cache,digest,9)
    assert second==first,'Cached observations differ'
    lone=copy.deepcopy(records[0]);lone['crop']=[0,0,480,480]
    assert pipeline.refine_crop_seams(page,[lone],cache,digest,9)==[]
print('PASS actual seam-label recovery, PDF coordinates, retained source readings, review flags and zero-inference cache reuse')
print('Artifacts:',cache)
