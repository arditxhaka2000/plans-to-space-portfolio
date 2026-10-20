"""PDF context only. Native positions first; cached overlapping OCR crops for missing text."""
from __future__ import annotations
import argparse, hashlib, json, re, sys, shutil
from pathlib import Path
from importlib.metadata import version
import numpy as np
import pdfplumber
import pypdfium2 as pdfium
from pdf_labels import sheet_info, material_observations, level_observations
VERSION='context-4'
CONFIG={'version':VERSION,'dpi':216,'cropPoints':480,'overlapPoints':60,'rotations':[0,90],'nativeMinimum':40}
OCR_CONFIG={k:v for k,v in CONFIG.items() if k not in ('version','nativeMinimum')}|{'engine':version('rapidocr-onnxruntime'),'renderer':version('pypdfium2'),'detectorLimit':1440,'detectorLimitType':'max'}
REFINEMENT_CONFIG={'version':1,'dpi':432,'paddingPoints':2,'maxLines':24,'wordGapHeightRatio':.35,'erosionPixels':5}
PAGE_CONFIG={**CONFIG,'refinement':REFINEMENT_CONFIG,'ocr':OCR_CONFIG,'nativeEngine':version('pdfplumber')}
_ocr=None

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');temp.replace(path)

def emit(stage,current,total):print(json.dumps(dict(stage=stage,current=current,total=total)),flush=True)

def key(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def uncertain(text,confidence=1):
    flags=[]
    if confidence<.9:flags.append('low-confidence')
    if re.search(r'\d.*[\'"′″’”/¼½¾]|\b[A-Z]{1,3}[- ]?\d{2,6}\b',text):flags.append('dimension-or-code-review')
    if re.search(r'\d\s*[-−]\s*\d|^[A-Z]\d?$',text):flags.append('ambiguous-dimension-or-material-code')
    if '\ufffd' in text or '(cid:' in text:flags.append('unusable-text')
    return flags

def intersection(a,b):return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
def area(a):return max(0,a[2]-a[0])*max(0,a[3]-a[1])
def dedup(records):
    result=[]
    for r in sorted(records,key=lambda r:(r['method']!='native',-r['confidence'])):
        same=lambda x: re.sub(r'\s+','',x).casefold()
        if any(same(r['text'])==same(q['text']) and intersection(r['bounds'],q['bounds'])/max(1,min(area(r['bounds']),area(q['bounds'])))>.45 for q in result):continue
        result.append(r)
    return sorted(result,key=lambda r:(round(r['bounds'][1]/3),r['bounds'][0]))

def ocr_crop(page,bounds,cache,document_hash,number):
    global _ocr
    cache_file=cache/(key([document_hash,number,bounds,OCR_CONFIG])+'.json')
    if cache_file.exists():return json.loads(cache_file.read_text(encoding='utf-8'))
    # Context 2/3 used the same OCR settings but coupled its cache to native-text
    # changes. Reuse those exact crops without rerunning inference. Only migrate
    # the engine/renderer versions actually used to create that legacy cache.
    if OCR_CONFIG['engine']=='1.4.4' and OCR_CONFIG['renderer']=='5.13.0':
        for old_version in ('context-2','context-3'):
            old_config={**CONFIG,'version':old_version};old_name=key([document_hash,number,bounds,old_config])+'.json'
            for old_file in (cache/old_name,cache.parent/key(old_config)/'crops'/old_name):
                if old_file.exists():
                    records=json.loads(old_file.read_text(encoding='utf-8'))
                    for record in records:record['reviewFlags']=uncertain(record['text'],record['confidence'])
                    write_json(cache_file,records);return records
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr=RapidOCR(det_limit_side_len=1440,det_limit_type="max",max_side_len=1440,intra_op_num_threads=2,inter_op_num_threads=2)
    x0,y0,x1,y1=bounds;w,h=page.get_size();scale=CONFIG['dpi']/72
    bitmap=page.render(scale=scale,crop=(x0,h-y1,w-x1,y0));image=bitmap.to_pil().convert('RGB');bitmap.close();records=[]
    for rotation in CONFIG['rotations']:
        rotated=image.rotate(rotation,expand=True)
        result,_=_ocr(np.asarray(rotated))
        # PIL rotations are counterclockwise. Transform back into original crop pixels,
        # then PDF top-left points. Store the transform evidence with each observation.
        for polygon,text,confidence in result or []:
            points=[]
            for x,y in polygon:
                if rotation==90:x,y=image.width-y,x
                elif rotation==270:x,y=y,image.height-x
                points.append([x0+x/scale,y0+y/scale])
            box=[min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]
            records.append(dict(text=text,bounds=box,polygon=points,confidence=float(confidence),method='ocr',rotation=rotation,crop=bounds,pixelsPerPoint=scale,reviewFlags=uncertain(text,float(confidence))))
        rotated.close()
    image.close();records=dedup(records);write_json(cache_file,records);return records

def refine_crop_seams(page, records, cache, document_hash, number):
    """Read overlapping horizontal fragments together; retain alternatives as unreviewed.

    No vocabulary or benchmark coordinates are used. Word-level recognition of a
    lightly thinned render can recover lettering joined by heavy architectural fonts.
    Original observations remain available when this alternative disagrees.
    """
    from PIL import Image, ImageFilter, ImageOps
    candidates=[]
    horizontal=[r for r in records if r['method']=='ocr' and
                r['bounds'][2]-r['bounds'][0]>3*(r['bounds'][3]-r['bounds'][1])]
    for i,a in enumerate(horizontal):
        for b in horizontal[i+1:]:
            if a.get('crop')==b.get('crop'):continue
            aa,bb=a['bounds'],b['bounds'];ha=aa[3]-aa[1];hb=bb[3]-bb[1]
            if min(ha,hb)<=0 or max(ha,hb)>2*min(ha,hb):continue
            if abs((aa[1]+aa[3]-bb[1]-bb[3])/2)>min(ha,hb)*.4:continue
            overlap=min(aa[2],bb[2])-max(aa[0],bb[0])
            if overlap<=0 or overlap>=.8*min(aa[2]-aa[0],bb[2]-bb[0]):continue
            box=[min(aa[0],bb[0]),min(aa[1],bb[1]),max(aa[2],bb[2]),max(aa[3],bb[3])]
            if box[2]-box[0]>600:continue
            for fragment in (a,b):
                if 'crop-boundary-review' not in fragment['reviewFlags']:fragment['reviewFlags'].append('crop-boundary-review')
            if not any(intersection(box,q)/max(1,min(area(box),area(q)))>.8 for q in candidates):candidates.append(box)
    output=[]
    for bounds in candidates[:REFINEMENT_CONFIG['maxLines']]:
        cache_file=cache/(key([document_hash,number,bounds,OCR_CONFIG,REFINEMENT_CONFIG])+'.json')
        if cache_file.exists():output+=json.loads(cache_file.read_text(encoding='utf-8'));continue
        # Ensure the ordinary recognizer is initialized even when all base crops were cached.
        global _ocr
        if _ocr is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr=RapidOCR(det_limit_side_len=1440,det_limit_type='max',max_side_len=1440,intra_op_num_threads=2,inter_op_num_threads=2)
        w,h=page.get_size();pad=REFINEMENT_CONFIG['paddingPoints'];scale=REFINEMENT_CONFIG['dpi']/72
        crop=[max(0,bounds[0]-pad),max(0,bounds[1]-pad),min(w,bounds[2]+pad),min(h,bounds[3]+pad)]
        bitmap=page.render(scale=scale,crop=(crop[0],h-crop[3],w-crop[2],crop[1]));im=bitmap.to_pil().convert('RGB');bitmap.close()
        pixels=np.asarray(im);ink=pixels.min(axis=2)<120;ys,xs=np.where(ink);refined=[]
        if len(xs):
            left,right,top,bottom=int(xs.min()),int(xs.max()+1),int(ys.min()),int(ys.max()+1)
            strip=ink[top:bottom,left:right];columns=strip.any(axis=0);gaps=[];start=0
            for x,value in enumerate(columns):
                if value:
                    if x-start>(bottom-top)*REFINEMENT_CONFIG['wordGapHeightRatio']:gaps.append((start+x)//2)
                    start=x+1
            edges=[0]+gaps+[right-left];words=[];scores=[];word_evidence=[]
            for x1,x2 in zip(edges,edges[1:]):
                piece=im.crop((left+x1,top,left+x2,bottom));mask=np.asarray(piece).min(axis=2)<120;yy,xx=np.where(mask)
                if not len(xx):continue
                iw,ih=int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)
                # A single solid short horizontal stroke between words is a printed dash.
                solid=mask[yy.min():yy.max()+1,xx.min():xx.max()+1].mean()
                if ih<(bottom-top)*.3 and iw>ih*2.5 and solid>.85 and len(words) and x2<right-left:
                    text,score='-',.8
                else:
                    thinned=piece.filter(ImageFilter.MaxFilter(REFINEMENT_CONFIG['erosionPixels']))
                    padded=ImageOps.expand(thinned,border=8,fill='white')
                    result,_=_ocr(np.asarray(padded),use_det=False,use_cls=False)
                    text,score=result[0][:2] if result else ('',0)
                    text=text.strip();padded.close();thinned.close()
                piece.close()
                if not text or score<.65:words=[];break
                words.append(text);scores.append(float(score));word_evidence.append({'text':text,'confidence':float(score),'bounds':[crop[0]+(left+x1)/scale,crop[1]+top/scale,crop[0]+(left+x2)/scale,crop[1]+bottom/scale]})
            if len(words)>=2:
                text=' '.join(words);box=[crop[0]+left/scale,crop[1]+top/scale,crop[0]+right/scale,crop[1]+bottom/scale]
                refined.append(dict(text=text,bounds=box,confidence=min(scores),method='ocr',rotation=0,crop=crop,pixelsPerPoint=scale,variant='seam-word-refinement',words=word_evidence,reviewFlags=uncertain(text,min(scores))+['alternative-reading-review']))
        im.close();write_json(cache_file,refined);output+=refined
    return output


def extract_page(native,page,number,document_hash,cache,force_ocr=False):
    if native.cropbox and native.cropbox!=native.bbox:native=native.crop(native.cropbox)
    w,h=page.get_size();records=[];rotated_words=[]
    if abs(native.width-w)>1 or abs(native.height-h)>1:raise ValueError('PDF display and extraction coordinate boxes disagree; manual review required.')
    # pdfplumber supplies coordinates in the displayed page's top-left system.
    for word in native.extract_words(x_tolerance=2,y_tolerance=2,return_chars=True):
        text=word['text'];box=[float(word['x0']-native.bbox[0]),float(word['top']-native.bbox[1]),float(word['x1']-native.bbox[0]),float(word['bottom']-native.bbox[1])]
        if not word.get('upright',True) and word.get('direction')=='ttb' and word['chars'][0]['matrix'][1]>0:
            rotated_words.append((text,text[::-1]));text=text[::-1]
        if text.strip() and not ('\ufffd' in text or '(cid:' in text):records.append(dict(text=text,bounds=box,confidence=1,method='native',rotation=0 if word.get('upright',True) else 90,reviewFlags=uncertain(text)))
    good=sum(len(r['text']) for r in records)>=CONFIG['nativeMinimum']
    crops=[];size=CONFIG['cropPoints'];step=size-CONFIG['overlapPoints']
    # Mixed pages: inspect embedded raster areas even when a native title block exists.
    images=[[float(i['x0']-native.bbox[0]),float(i['top']-native.bbox[1]),float(i['x1']-native.bbox[0]),float(i['bottom']-native.bbox[1])] for i in native.images]
    bitmap=page.render(scale=.25);thumbnail=bitmap.to_pil().convert('L');bitmap.close()
    for y in range(0,int(h),step):
        for x in range(0,int(w),step):
            box=[x,y,min(x+size,w),min(y+size,h)]
            local=[r for r in records if intersection(box,r['bounds'])>0]
            raster=any(intersection(box,i)>area(box)*.15 for i in images)
            sample=np.asarray(thumbnail.crop(tuple(v*.25 for v in box)))
            ink=float(np.mean(sample<180)) if sample.size else 0
            # Outlined lettering is vector ink, not native text or an embedded image.
            # Sparse native coverage over nonblank ink needs OCR as well.
            sparse=sum(len(r['text']) for r in local)<80
            if force_ocr or (ink>.003 and (not good or sparse)) or (raster and sparse):crops.append(box)
    thumbnail.close()
    for crop in crops:records+=ocr_crop(page,crop,cache,document_hash,number)
    records=dedup(records)
    records+=refine_crop_seams(page,records,cache,document_hash,number)
    text='\n'.join(r['text'] for r in records)
    # Native layout text retains line structure useful for drawing titles/material legends.
    layout=native.extract_text(x_tolerance=2,y_tolerance=2) or ''
    for raw,corrected in rotated_words:layout=re.sub(r'(?<!\w)'+re.escape(raw)+r'(?!\w)',lambda _:corrected,layout)
    if good:text=layout+ ('\n'+'\n'.join(r['text'] for r in records if r['method']=='ocr') if crops else '')
    titleblock=native.crop((native.bbox[0]+w*.88,native.bbox[1],native.bbox[2],native.bbox[3])).extract_text(x_tolerance=2,y_tolerance=2) or ''
    if len(titleblock)<40:titleblock='\n'.join(r['text'] for r in records if r['bounds'][0]>w*.88)
    code,title,role=sheet_info(text,titleblock)
    return dict(page=number,pageSize=[w,h],coordinateSystem='top-left PDF points; displayed page rotation applied',code=code,title=title,role=role,text=text,titleBlockText=titleblock,observations=records,textMethod='native+ocr' if crops and good else 'ocr' if crops else 'native',ocrCrops=len(crops),reviewStatus='extracted-not-reviewed')

def run(source,out):
    if source.stat().st_size>100_000_000:raise ValueError('PDF exceeds worker limit.')
    digest=hashlib.sha256(source.read_bytes()).hexdigest();cache=out.parent.parent/'pdf-context-cache'/digest/key(PAGE_CONFIG);cache.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=False)
    manifest=dict(schemaVersion=2,pipelineVersion=VERSION,sourceSha256=digest,sheets=[],materials=[],levels=[],issues=[],status='NeedsReview')
    from exterior_assessment import page_evidence, assess
    exterior_pages=[]
    with pdfplumber.open(source) as native, pdfium.PdfDocument(source) as pdf:
        if not 0<len(pdf)<=250:raise ValueError('Supported size is 1–250 pages.')
        for i in range(len(pdf)):
            emit('Extracting PDF context',i,len(pdf));cached=cache/f'page-{i+1}.json';preview=cache/f'page-{i+1}.png';page=pdf[i]
            if cached.exists():data=json.loads(cached.read_text(encoding='utf-8'))
            else:data=extract_page(native.pages[i],page,i+1,digest,cache.parent/'ocr');write_json(cached,data)
            if not preview.exists():
                bitmap=page.render(scale=min(1600/max(page.get_size()),1));bitmap.to_pil().save(preview);bitmap.close()
            folder=out/'pages';folder.mkdir(exist_ok=True)
            # Cached source payload exists once. Hard links reuse it without duplicate bytes.
            for src,dst in [(cached,folder/f'{i+1:03}.json'),(preview,folder/f'{i+1:03}.png')]:
                if not dst.exists():
                    try:dst.hardlink_to(src)
                    except OSError:shutil.copyfile(src,dst)
            manifest['sheets'].append({k:data[k] for k in ['page','pageSize','code','title','role','textMethod']}|dict(evidence=f'pages/{i+1:03}.json',preview=f'pages/{i+1:03}.png'))
            manifest['materials']+=material_observations(data['text'],i+1);manifest['levels']+=level_observations(data['text'],i+1)
            exterior_pages.append(page_evidence(native.pages[i],data))
            page.close();native.pages[i].close()
    emit('Assessing exterior evidence',len(exterior_pages),len(exterior_pages))
    write_json(out/'exterior-assessment.json',assess(exterior_pages,digest))
    manifest['exteriorAssessment']='exterior-assessment.json'
    manifest['summary']={'pageCount':len(manifest['sheets'])};write_json(out/'manifest.json',manifest);emit('PDF context ready',len(manifest['sheets']),len(manifest['sheets']));return manifest

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');parser=argparse.ArgumentParser();parser.add_argument('--pdf',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.pdf,args.output)
