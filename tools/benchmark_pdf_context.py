"""Evaluate actually extracted observations against visually transcribed references."""
import json,re,math,argparse,sys,hashlib,time
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
folder=root/'work/context-benchmark'
parser=argparse.ArgumentParser();parser.add_argument('--source-dir',type=Path);args=parser.parse_args()
if args.source_dir:
    sys.path.insert(0,str(root/'worker'))
    from pipeline import extract_page,write_json,PAGE_CONFIG
    import pdfplumber,pypdfium2
    folder.mkdir(parents=True,exist_ok=True)
    for name,pattern,number in [('umd','UMD*',9),('flamingo','1.*',4),('balaclava','2026*',36)]:
        source=next(args.source_dir.glob(pattern));started=time.monotonic()
        with pdfplumber.open(source) as native,pypdfium2.PdfDocument(source) as pdf:
            data=extract_page(native.pages[number-1],pdf[number-1],number,hashlib.sha256(source.read_bytes()).hexdigest(),folder/'cache')
            data['benchmarkSeconds']=time.monotonic()-started;data['processingConfiguration']=PAGE_CONFIG
            write_json(folder/(name+'.json'),data)
refs=json.loads((root/'evidence/pdf-context-reference.json').read_text())['references']
def norm(s):
    return re.sub(r'\s+','',s.translate(str.maketrans({'′':"'",'’':"'",'″':'"','”':'"','−':'-','–':'-','¼':'1/4','½':'1/2','¾':'3/4'})))
def center(b):return [(b[0]+b[2])/2,(b[1]+b[3])/2]
results=[]
for ref in refs:
    data=json.loads((folder/(ref['document']+'.json')).read_text(encoding='utf-8'))
    b=ref['bounds'];c=center(b)
    nearby=[r for r in data['observations'] if b[0]-12<center(r['bounds'])[0]<b[2]+12 and b[1]-5<center(r['bounds'])[1]<b[3]+5]
    # Try contiguous word sequences as native extraction returns individual words,
    # whereas OCR can return a whole label. No fuzzy spelling correction.
    candidates=[]
    for method in ['native','ocr']:
        words=sorted([r for r in nearby if r['method']==method],key=lambda r:r['bounds'][0])
        for i in range(len(words)):
            for j in range(i+1,min(len(words)+1,i+10)):
                group=words[i:j];text=' '.join(r['text'] for r in group)
                box=[min(r['bounds'][0] for r in group),min(r['bounds'][1] for r in group),max(r['bounds'][2] for r in group),max(r['bounds'][3] for r in group)]
                if norm(text)==norm(ref['text']):candidates.append((math.dist(c,center(box)),text,box,method))
    best=min(candidates) if candidates else None
    results.append({**ref,'exactMatch':bool(best),'literalExactMatch':bool(best and best[1]==ref['text']),'centerErrorPoints':round(best[0],3) if best else None,'actual':best[1] if best else [r['text'] for r in nearby],'actualBounds':best[2] if best else None,'method':best[3] if best else None})
report={'executedUtc':datetime.now(timezone.utc).isoformat(),'processingConfigurations':{name:json.loads((folder/(name+'.json')).read_text(encoding='utf-8')).get('processingConfiguration') for name in ['umd','flamingo','balaclava']},'normalization':'Whitespace removed; typographic quote/dash and Unicode fraction variants canonicalized. Case and characters otherwise exact.','coordinateMetric':'Euclidean center distance in PDF points (1/72 inch), only for exact matches. Manually measured bounds have approximately 1-5 point uncertainty.','references':results,'summary':{}}
for doc in ['umd','flamingo','balaclava']:
    rows=[r for r in results if r['document']==doc];errors=[r['centerErrorPoints'] for r in rows if r['exactMatch']]
    report['summary'][doc]={'matched':len(errors),'literalMatched':sum(r['literalExactMatch'] for r in rows),'total':len(rows),'meanCenterErrorPoints':round(sum(errors)/len(errors),3) if errors else None,'maxCenterErrorPoints':max(errors) if errors else None}
(root/'evidence/pdf-context-benchmark.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
