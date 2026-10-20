"""Local drawing interpretation: positioned text, vector topology and raster linework.

No building profiles, sample recipes, source filenames, external inference or uploaded code.
Every generated parameter is measured, printed, or explicitly marked as an assumption.
"""
import argparse, collections, hashlib, json, math, re, statistics, sys
from pathlib import Path
import numpy as np
import pdfplumber
from shapely import affinity
from shapely.geometry import Polygon, LineString, Point, box
from shapely.ops import unary_union, polygonize
from building_recipe import Recipe
from recipe_generate import generate
from exterior_assessment import scale_bar

VERSION='drawing-interpreter-1.0.1'
MAX_PAGES=120

def rgb(value):
    """Normalize device colours; unsupported pattern/name values are not geometry evidence."""
    values=value if isinstance(value,(tuple,list)) else [value]
    if len(values) not in (1,3,4):return (1.,1.,1.)
    try:
        if any(isinstance(v,bool) or not isinstance(v,(int,float,str)) for v in values):return (1.,1.,1.)
        channels=tuple(float(v) for v in values)
    except (TypeError,ValueError,OverflowError):return (1.,1.,1.)
    if any(not math.isfinite(v) or not 0<=v<=1 for v in channels):return (1.,1.,1.)
    if len(channels)==1:return channels*3
    if len(channels)==4:
        c,m,y,k=channels;return (1-min(1,c+k),1-min(1,m+k),1-min(1,y+k))
    return channels

def polygons(shape):
    if isinstance(shape,Polygon):return [shape]
    return [p for p in getattr(shape,'geoms',[]) if isinstance(p,Polygon)]

def words_text(words):
    rows=[]
    for w in sorted(words,key=lambda w:(w['top']+w['bottom'])/2):
        y=(w['top']+w['bottom'])/2
        if rows and abs(rows[-1][0]-y)<4:rows[-1][1].append(w)
        else:rows.append((y,[w]))
    return '\n'.join(' '.join(w['text'] for w in sorted(row,key=lambda w:w['x0'])) for _,row in rows)

def metric_scale(words,text):
    bar=scale_bar(words)
    if bar:return {**bar,'method':'three-mark metric scale bar','confidence':'measured'}
    for zero in words:
        if zero['text'] not in ("0'",'0′'):continue
        row=sorted([w for w in words if abs(w['top']-zero['top'])<3 and w['x0']>=zero['x0'] and re.fullmatch(r"\d+(?:\.\d+)?['′]",w['text'])],key=lambda w:w['x0'])[:6]
        if len(row)<3:continue
        values=np.array([float(w['text'][:-1])*.3048 for w in row]);xs=np.array([(w['x0']+w['x1'])/2 for w in row])
        if np.any(np.diff(values)<=0) or np.any(np.diff(xs)<=5):continue
        ratios=np.diff(values)/np.diff(xs)
        if ratios.max()/ratios.min()>1.15:continue
        return {'metresPerPoint':float((values[-1]-values[0])/(xs[-1]-xs[0])),'method':'multi-mark feet scale bar converted to metres','confidence':'measured','text':' '.join(w['text'] for w in row),'bounds':[row[0]['x0'],row[0]['top'],row[-1]['x1'],row[-1]['bottom']]}
    # Printed paper scales are usable for native, unresized sheets, but flagged as such.
    ratios=re.findall(r'\b(?:SCALE\s*[:=]?\s*)?1\s*:\s*(\d{2,4})\b',text,re.I)
    ratios={int(n) for n in ratios if 10<=int(n)<=1000}
    if len(ratios)==1:return {'metresPerPoint':ratios.pop()*.0254/72,'method':'printed paper scale; PDF sheet size assumed original','confidence':'interpreted','text':'1:n paper scale'}
    return None

def ocr_words(path,index,width,height,engine):
    import pypdfium2
    doc=pypdfium2.PdfDocument(str(path));page=doc[index];scale=min(3,2400/max(width,height));bitmap=page.render(scale=scale)
    result,_=engine(np.asarray(bitmap.to_pil().convert('RGB')));bitmap.close();page.close();doc.close();words=[]
    for bounds,text,confidence in result or []:
        if confidence<.65:continue
        x0=min(p[0] for p in bounds)/scale;x1=max(p[0] for p in bounds)/scale;top=min(p[1] for p in bounds)/scale;bottom=max(p[1] for p in bounds)/scale
        # OCR may return a complete text line. Approximate token boxes explicitly.
        for match in re.finditer(r"\d+(?:\.\d+)?['′]?|[A-Za-z]+|[^\w\s]",text):words.append({'text':match[0],'x0':x0+(x1-x0)*match.start()/len(text),'x1':x0+(x1-x0)*match.end()/len(text),'top':top,'bottom':bottom,'ocr':True})
    return words

def level_numbers(text):
    upper=text.upper()
    multi=re.search(r'\b(?:FLOORS|LEVELS)\s+(-?\d+(?:\s*[,–—-]\s*-?\d+)*)',upper)
    if multi:
        token=multi[1];numbers=[int(n) for n in re.findall(r'(?<!\d)-?\d+',token.replace('–',' ').replace('—',' '))]
        if ',' not in token and len(numbers)==2 and numbers[1]>numbers[0]:numbers=list(range(numbers[0],numbers[1]+1))
        return sorted(set(n for n in numbers if 0<=n<=60))
    if re.search(r'\b(GROUND|GROUND-FLOOR|FIRST)\s+(?:FLOOR|LEVEL)',upper):return [0]
    m=re.search(r'\b(?:FLOOR|LEVEL)\s+(\d{1,2})\b',upper)
    if m:return [int(m[1])]
    m=re.search(r'\b(SECOND|THIRD|FOURTH|FIFTH)\s+FLOOR',upper)
    if m:return [{'SECOND':1,'THIRD':2,'FOURTH':3,'FIFTH':4}[m[1]]]
    return []

def height_evidence(page_number,text):
    found=[]
    for line in text.splitlines():
        for m in re.finditer(r'(\d+(?:\.\d+)?)\s*m\s+(GROUND\s+FLOOR|FLOOR\s+\d+)',line,re.I):
            h=float(m[1]);level=0 if 'GROUND' in m[2].upper() else int(re.search(r'\d+',m[2])[0])
            if 1.8<=h<=8:found.append({'floor':level,'height':h,'page':page_number,'text':m[0]})
    return found

def fill_shapes(page,scale):
    """Find floor-region fills by area/contrast; colours are not building-specific."""
    candidates=[]
    for obj in page.rects+page.curves:
        if not obj.get('fill') or len(obj.get('pts',[]))<3:continue
        color=rgb(obj.get('non_stroking_color'))
        if max(color)<.12 or min(color)>.97:continue
        if obj['width']>page.width*.9 and obj['height']>page.height*.8:continue
        if obj['top']<page.height*.03 or obj['bottom']>page.height*.96:continue
        shape=Polygon(obj['pts']).buffer(0)
        for poly in polygons(shape):
            if poly.area*scale**2<25 or poly.area>page.width*page.height*.45:continue
            if min(poly.bounds[2]-poly.bounds[0],poly.bounds[3]-poly.bounds[1])*scale<2:continue
            candidates.append((poly,color))
    # Page-background sheets and legend blocks have low contrast to the page background.
    backgrounds=[rgb(o.get('non_stroking_color')) for o in page.rects if o.get('fill') and o['width']*o['height']>page.width*page.height*.4]
    candidates=[(p,c) for p,c in candidates if not any(math.dist(c,b)<.08 for b in backgrounds)]
    if not candidates:return []
    biggest=max(p.area for p,_ in candidates)
    useful=[p for p,_ in candidates if p.area>=biggest*.015]
    union=unary_union(useful).buffer(.6).buffer(-.6)
    return sorted([p.simplify(.4,preserve_topology=True) for p in polygons(union) if p.area*scale**2>=25],key=lambda p:p.bounds)

def vector_walls(page,scale):
    result=[]
    for obj in page.rects:
        color=rgb(obj.get('non_stroking_color'))
        if not obj.get('fill') or max(color)>.6:continue
        w,h=obj['width']*scale,obj['height']*scale
        if .07<=min(w,h)<=.7 and max(w,h)>=.8 and max(w,h)/min(w,h)>4:
            result.append(box(obj['x0'],obj['top'],obj['x1'],obj['bottom']))
    return result

def raster_walls(path,index,page,scale):
    """Bounded classical CV fallback. Remove text-sized components before line closing."""
    import cv2, pypdfium2
    doc=pypdfium2.PdfDocument(str(path));p=doc[index];factor=min(2.5,2600/max(page.width,page.height));bitmap=p.render(scale=factor);image=np.asarray(bitmap.to_pil().convert('L'));bitmap.close();p.close();doc.close()
    mask=cv2.threshold(image,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    h,w=mask.shape;mask[:int(h*.05),:]=0;mask[int(h*.95):,:]=0;mask[:,:int(w*.04)]=0;mask[:,int(w*.96):]=0
    # Remove a labelled notes/legend column from recognition, preserving the original PDF.
    right_notes=[word['x0'] for word in page.extract_words() if word['text'].upper() in ('LEGEND','GENERAL') and word['x0']>page.width*.65]
    if right_notes:mask[:,max(int(w*.6),int(min(right_notes)*factor)-25):]=0
    # Separate long horizontal/vertical strokes; avoid treating text blobs as walls.
    length=max(12,int(.8/max(scale,.001)*factor))
    horizontal=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(length,1)))
    vertical=cv2.morphologyEx(mask,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,length)))
    lines=cv2.bitwise_or(horizontal,vertical);lines=cv2.morphologyEx(lines,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    sheet_lines=cv2.bitwise_or(cv2.morphologyEx(lines,cv2.MORPH_OPEN,np.ones((1,max(10,int(w*.7))),np.uint8)),cv2.morphologyEx(lines,cv2.MORPH_OPEN,np.ones((max(10,int(h*.75)),1),np.uint8)))
    lines=cv2.subtract(lines,cv2.dilate(sheet_lines,np.ones((3,3),np.uint8)))
    contours,_=cv2.findContours(lines,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    regions=[]
    for contour in contours:
        if cv2.contourArea(contour)<40:continue
        pts=cv2.approxPolyDP(contour,1.2,True).reshape(-1,2)/factor
        poly=Polygon(pts).buffer(0) if len(pts)>=3 else Polygon()
        regions.extend(p for p in polygons(poly) if p.area*scale**2>.1 and not(p.bounds[2]-p.bounds[0]>page.width*.8 and p.bounds[3]-p.bounds[1]>page.height*.7))
    return regions

def columns(page,scale):
    seen=set();points=[]
    for r in page.rects:
        w,h=r['width']*scale,r['height']*scale
        if r.get('fill') and max(rgb(r.get('non_stroking_color')))<.2 and .2<w<1.0 and .2<h<1.0 and .7<w/h<1.4:
            pt=((r['x0']+r['x1'])/2,(r['top']+r['bottom'])/2);key=tuple(round(v,1) for v in pt)
            if key not in seen:points.append((pt,w,h));seen.add(key)
    return points

def register(current,reference):
    """Translation registration from repeated column centres, with an explicit residual."""
    a=np.array([p[0] for p in current['columns']],float)*current['scale']['metresPerPoint']
    b=np.array([p[0] for p in reference['columns']],float)*reference['scale']['metresPerPoint']
    if len(a)<6 or len(b)<6:return None
    differences=(b[None,:,:]-a[:,None,:]).reshape(-1,2)
    bins=collections.Counter(map(tuple,np.round(differences/.25).astype(int)))
    offsets=[np.array(k)*.25 for k,_ in bins.most_common(24)]+[np.zeros(2)]
    def score(offset):
        distance=np.linalg.norm(b[None,:,:]-(a[:,None,:]+offset),axis=2).min(axis=1)
        return (int((distance<.5).sum()),-float(np.minimum(distance,.5).mean()),-float(np.linalg.norm(offset)))
    offset=max(offsets,key=score)
    for _ in range(3):
        delta=b[None,:,:]-(a[:,None,:]+offset);dist=(delta**2).sum(axis=2);nearest=dist.argmin(axis=1);res=b[nearest]-(a+offset);keep=np.linalg.norm(res,axis=1)<1.5
        if keep.sum()<6:return None
        offset+=np.median(res[keep],axis=0)
    distances=np.linalg.norm(b[nearest]-(a+offset),axis=1);keep=distances<.5
    if keep.sum()<6 or keep.mean()<.4:return None
    return {'offset':offset.tolist(),'matchedColumns':int(keep.sum()),'rmsMetres':float(np.sqrt(np.mean(distances[keep]**2))),'method':'repeated column centres; translation only'}

def facade_module(pages,heights):
    """Measure repeated elevation linework using labelled floor spacing, not a sample pattern."""
    options=[]
    for data in pages:
        if not re.search(r'FACADE|ELEVATION',data['text'],re.I):continue
        labels=[];words=data['words']
        for i,w in enumerate(words):
            if w['text'].upper()!='FLOOR':continue
            tail=[t for t in words if abs(t['top']-w['top'])<2 and 0<t['x0']-w['x1']<12 and t['text'].isdigit()]
            if tail:labels.append((int(tail[0]['text']),w['top'],w['x0']))
        scales=[]
        for n,y,x in labels:
            for n2,y2,x2 in labels:
                if n2==n+1 and abs(x-x2)<5 and y-y2>8 and n in heights:scales.append(heights[n]['height']/(y-y2))
        if len(scales)<2:continue
        scale=statistics.median(scales)
        lines=[l for l in data['lines'] if abs(l['x0']-l['x1'])<.1 and .4<l['height']*scale<3 and 0<=l['top']<data['height'] and l['x0']>=0]
        groups=collections.defaultdict(list)
        for l in lines:groups[(round(l['top'],0),round(l['height'],0))].append(l)
        gaps=[];line_heights=[]
        for group in groups.values():
            xs=sorted(set(round(l['x0'],1) for l in group))
            local=[(b-a)*scale for a,b in zip(xs,xs[1:]) if .6<(b-a)*scale<2.5]
            if len(local)>=8:gaps.extend(local);line_heights.extend([l['height']*scale for l in group])
        if len(gaps)>=16:options.append({'page':data['page'],'pitch':round(statistics.median(gaps),3),'height':round(statistics.median(line_heights),3),'observations':len(gaps),'method':'repeated facade line spacing calibrated against labelled floor heights'})
    return max(options,key=lambda o:o['observations']) if options else None

def interpret(path,output):
    source_hash=hashlib.sha256(Path(path).read_bytes()).hexdigest();report={'version':VERSION,'sourceDocumentHash':source_hash,'status':'needs-review','pages':[],'issues':[],'registrations':[],'measurements':[]}
    pages=[];heights={};plans=[];ocr=None;ocr_pages=0
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages)>MAX_PAGES:raise ValueError(f'Document exceeds {MAX_PAGES} page interpretation limit')
        for index,original in enumerate(pdf.pages):
            page=original.crop((0,0,original.width,original.height));words=page.extract_words()
            if len(words)<4 and ocr_pages<24:
                if ocr is None:
                    from rapidocr_onnxruntime import RapidOCR
                    ocr=RapidOCR()
                words=ocr_words(path,index,page.width,page.height,ocr);ocr_pages+=1
                report['issues'].append(f'Page {index+1}: raster OCR/token locations are approximate and require review.')
            text=words_text(words)
            data={'page':index+1,'width':page.width,'height':page.height,'words':words,'text':text,'lines':page.lines}
            pages.append(data)
            for h in height_evidence(index+1,text):
                if h['floor'] in heights and abs(heights[h['floor']]['height']-h['height'])>.05:report['issues'].append(f"Conflicting height for floor {h['floor']}; first section reading retained for review.")
                else:heights[h['floor']]=h
            is_plan=bool(re.search(r'FLOOR\s+PLAN|GROUND\s+FLOOR|TYPICAL\s+FLOOR|SMALL\s+BUSINESS\s+FLOOR|\bLEVEL\s+\d+.*PLAN',text,re.I)) and not bool(re.search(r'ELEVATION\s+VIEW|FACADE\s+VIEW',text,re.I))
            levels=level_numbers('\n'.join(text.splitlines()[:15])) if is_plan else []
            scale=metric_scale(words,text) if is_plan else None
            entry={'page':index+1,'role':'plan' if is_plan else 'section/elevation' if re.search('SECTION|ELEVATION|FACADE',text,re.I) else 'other','levels':levels,'scale':scale}
            report['pages'].append(entry)
            if not is_plan:original.close();continue
            if not levels:
                levels=level_numbers(text)
                if not levels and re.search(r'\bFLOOR\s+PLAN\b',text,re.I):levels=[0];entry['levelAssumption']='Unnumbered floor plan treated as ground floor; review required.'
                entry['levels']=levels
            # Store native geometry only for potential plans; rendered fallbacks stay bounded.
            data.update(scale=scale,levels=levels,columns=[],fills=[],wallPolygons=[],entry=entry)
            if scale:
                s=scale['metresPerPoint'];data['fills']=fill_shapes(page,s);data['columns']=columns(page,s);data['wallPolygons']=vector_walls(page,s)
                if not data['fills'] and len(data['wallPolygons'])<4:
                    data['wallPolygons']=raster_walls(path,index,page,s);entry['geometryMethod']='raster long-stroke segmentation'
                else:entry['geometryMethod']='native vector fills/walls'
            else:entry['issue']='No calibrated scale; geometry omitted unless registration establishes one.'
            plans.append(data);original.close()
    # Section dimensions define floor bases; do not mistake floor-area table values for heights.
    if not heights:report['issues'].append('No linked floor-to-floor heights found. A 3 m draft storey is an explicit estimate, not an extracted dimension.')
    calibrated=[p for p in plans if p['scale'] and (p['fills'] or p['wallPolygons']) and p['levels']]
    if not calibrated:
        report['status']='needs-input';report['issues'].append('No scaled plan geometry could be established from this document.');Path(output).mkdir(parents=True,exist_ok=True);Path(output,'interpretation.json').write_text(json.dumps(report,indent=2));return None,report
    reference=max(calibrated,key=lambda p:len(p['columns']));sref=reference['scale']['metresPerPoint'];allref=unary_union(reference['fills'] or reference['wallPolygons']);origin=np.array(allref.bounds[:2])*sref
    # A missing scale can be transferred only when an independently repeated column grid registers.
    with pdfplumber.open(path) as pdf:
        for p in plans:
            if p['scale'] or not p['levels'] or abs(p['width']-reference['width'])>1 or abs(p['height']-reference['height'])>1:continue
            page=pdf.pages[p['page']-1];p['scale']={**reference['scale'],'method':f"scale transferred from page {reference['page']} through registered column grid",'confidence':'interpreted'};p['columns']=columns(page,sref)
            registration=register(p,reference)
            if registration is None:p['scale']=None;continue
            p['fills']=fill_shapes(page,sref);p['wallPolygons']=vector_walls(page,sref);p['entry'].update(scale=p['scale'],geometryMethod='native vector fills/walls; registered scale transfer');p['entry'].pop('issue',None);calibrated.append(p)
    for p in calibrated:
        registration={'offset':[0,0],'method':'reference plan','rmsMetres':0} if p is reference else register(p,reference)
        if registration is None:
            # Single-plan documents need no registration. Cross-page stacking requires evidence.
            p['entry']['issue']='Could not register this plan to shared column/grid coordinates; omitted.';p['registered']=False;continue
        p['registered']=True;p['offset']=np.array(registration['offset'])-origin;p['entry']['registration']=registration;report['registrations'].append({'page':p['page'],**registration})
    calibrated=[p for p in calibrated if p.get('registered')]
    module=facade_module(pages,heights);report['facadeModule']=module
    levels=sorted(set(n for p in calibrated for n in p['levels']))
    maxlevel=max(levels);base={0:0}
    for n in range(maxlevel+1):base[n+1]=base[n]+heights.get(n,{'height':3.0})['height']
    for n in range(maxlevel+1):
        if n not in heights:report['issues'].append(f'Floor {n}: 3 m storey height is estimated; no linked section dimension was found.')
    for p in pages:
        if re.search(r'FACADE|ELEVATION',p['text'],re.I):
            for value in set(float(m) for m in re.findall(r'\b(\d+(?:\.\d+)?)\s+m\b',p['text'])):
                if base[maxlevel+1]+.5<value<base[maxlevel+1]*1.5:report['issues'].append(f'Page {p["page"]}: elevation dimension {value:g} m differs from section-derived top {base[maxlevel+1]:g} m; not reconciled.')
    recipe={'schemaVersion':'1.0','label':'Automatically interpreted PDF draft','interpretation':'automatically-interpreted','units':'metres','axes':'X-right,Y-up,Z-plan-down','sourceDocumentHash':source_hash,'materials':[{'id':'wall','color':[.72,.73,.71,1]},{'id':'glass','color':[.24,.4,.46,1]},{'id':'frame','color':[.25,.28,.29,1]},{'id':'slab','color':[.62,.65,.63,1]}],'levels':[{'id':f'level-{n}','elevation':base[n]} for n in range(maxlevel+2)],'volumes':[],'walls':[],'boxes':[],'roofs':[],'groups':[],'assumptions':['Automatic local interpretation; all geometry and classifications require review.','Wall thickness 0.20 m, slab thickness 0.20 m and frame thickness 0.04 m are estimated where not dimensioned.','Facade repetition is propagated only when repeated elevation linework is detected; face correspondence and window sill placement are inferred.','No roof pitch is invented; top slabs are floor-envelope caps and are not certified roof geometry.'],'unresolved':report['issues']}
    if module:recipe['assumptions'].append(f"Facade bay pitch {module['pitch']} m and glazing line height {module['height']} m measured on page {module['page']}; applying this module to plan perimeter is an unverified facade correspondence assumption.")
    occupied={};feature_count=0
    def ev(p,kind,reference):return {'pages':[p],'status':kind,'reference':reference[:1000]}
    for p in calibrated:
        scale=p['scale']['metresPerPoint'];offset=p['offset'];geometry=p['fills']
        if not geometry:
            # Use closed linework areas; an open drawing does not become a convex-hull building.
            merged=unary_union(p['wallPolygons']);closed=merged.buffer(.15/scale).buffer(-.15/scale)
            geometry=[Polygon(q.exterior) for q in polygons(closed) if Polygon(q.exterior).area*scale**2>25]
        if not geometry:report['issues'].append(f"Page {p['page']}: open wall network has no defensible floor boundary.");continue
        for floor in p['levels']:
            if floor in occupied:report['issues'].append(f'Alternative plan for floor {floor} on page {p["page"]} omitted; first registered plan retained.');continue
            occupied[floor]=p['page'];height=heights.get(floor,{'height':3.0})['height'];floor_shapes=[]
            for pi,poly in enumerate(geometry):
                metric=affinity.translate(affinity.scale(poly,xfact=scale,yfact=scale,origin=(0,0)),xoff=offset[0],yoff=offset[1]).simplify(.025,preserve_topology=True)
                if len(metric.exterior.coords)>129:metric=metric.simplify(.08,preserve_topology=True)
                points=[[round(x,5),round(z,5)] for x,z in list(metric.exterior.coords)[:-1]]
                if len(points)>128:report['issues'].append(f'Page {p["page"]}: complex footprint omitted.');continue
                tag=f'auto/level-{floor}/volume-{pi}';evidence=ev(p['page'],'measured',f"{p['entry']['geometryMethod']}; {p['scale']['method']}; PDF bounds {list(poly.bounds)}; registered plan perimeter")
                recipe['volumes'].append({'id':tag+'/slab','material':'slab','evidence':evidence,'footprint':points,'level':f'level-{floor}','height':height,'slabThickness':.2});floor_shapes.append(metric)
                for edge,(a,b) in enumerate(zip(points,points[1:]+points[:1])):
                    length=math.dist(a,b)
                    if length<.1:continue
                    # Split into bounded host bays, so a window correction cannot alter other bays.
                    count=max(1,round(length/module['pitch'])) if module and length>module['pitch']*.8 else 1
                    if feature_count+count>4400:raise ValueError('Detected perimeter exceeds bounded assembly count')
                    for bay in range(count):
                        start=[a[k]+(b[k]-a[k])*bay/count for k in (0,1)];end=[a[k]+(b[k]-a[k])*(bay+1)/count for k in (0,1)];w=length/count;id=f'{tag}/edge-{edge}/bay-{bay}';openings=[]
                        if module and w>.5:
                            oh=min(module['height'],height*.75);sill=(height-oh)/2
                            openings=[{'id':id+'/window','kind':'window','offset':w/2,'sill':sill,'width':w-.12,'height':oh,'frame':.04,'material':'glass','frameMaterial':'frame','evidence':ev(module['page'],'interpreted',module['method']+'; perimeter correspondence and sill inferred; review required')}]
                        recipe['walls'].append({'id':id+'/wall','start':start,'end':end,'base':base[floor],'height':height,'thickness':.2,'material':'wall','evidence':evidence,'openings':openings});feature_count+=1
                if metric.interiors:recipe['unresolved'].append(f'Floor {floor}: internal courtyard/shaft holes need review; slab holes are not represented in recipe v1.')
            for ci,(center,w,d) in enumerate(p['columns']):
                x,z=np.array(center)*scale+offset
                if any(shape.buffer(.3).covers(Point(x,z)) for shape in floor_shapes):recipe['boxes'].append({'id':f'auto/level-{floor}/column-{ci}','kind':'column','material':'wall','evidence':ev(p['page'],'interpreted','Repeated filled square plan symbol classified as column; height uses storey evidence'),'center':[x,base[floor]+height/2,z],'size':[w,height,d]})
            report['measurements'].append({'page':p['page'],'floor':floor,'baseMetres':base[floor],'heightMetres':height,'heightEvidence':heights.get(floor),'footprints':len(floor_shapes),'areaSquareMetres':sum(g.area for g in floor_shapes)})
    missing=[n for n in range(maxlevel+1) if n not in occupied]
    if missing:recipe['unresolved'].append('No registered plan geometry for floors '+', '.join(map(str,missing))+'. These floors are omitted, not cloned.')
    if not module:recipe['unresolved'].append('No repeated facade glazing module detected; window geometry omitted.')
    if not recipe['volumes']:report['status']='needs-input';return None,report
    # Cap each exposed storey area, including setbacks, using the same measured plan.
    by_floor=collections.defaultdict(list)
    for volume in recipe['volumes']:by_floor[int(volume['level'].split('-')[1])].append(Polygon(volume['footprint']))
    for volume in list(recipe['volumes']):
        floor=int(volume['level'].split('-')[1]);next_floor=floor+1;exposed=Polygon(volume['footprint']).difference(unary_union(by_floor[next_floor]))
        for i,part in enumerate(polygons(exposed)):
            if part.area<.1:continue
            points=list(part.simplify(.03,preserve_topology=True).exterior.coords)[:-1]
            if len(points)<=128:recipe['volumes'].append({**volume,'id':volume['id']+f'/top-{i}','level':f'level-{next_floor}','footprint':points})
    if any(p.get('entry',{}).get('geometryMethod')=='raster long-stroke segmentation' for p in calibrated):recipe['unresolved'].append('Raster linework can include annotation or dimension strokes; inspect the recovered boundary before relying on measurements.')
    report['issues']=list(dict.fromkeys(recipe['unresolved']));recipe['unresolved']=report['issues'][:100]
    report['status']='generated-with-review';report['counts']={'storeys':len(occupied),'slabs':len(recipe['volumes']),'walls':len(recipe['walls']),'columns':len(recipe['boxes']),'windows':sum(len(w['openings']) for w in recipe['walls'])}
    report['assumptions']=recipe['assumptions']
    result=Recipe.model_validate(recipe);Path(output).mkdir(parents=True,exist_ok=True);Path(output,'interpretation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');return result,report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pdf',required=True);parser.add_argument('--output',required=True);a=parser.parse_args()
    try:
        recipe,report=interpret(a.pdf,a.output)
        if recipe is None:
            Path(a.output).mkdir(parents=True,exist_ok=True);Path(a.output,'interpretation.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({'error':'; '.join(report['issues'])[:1800]}));sys.exit(3)
        generate(recipe,a.output);print(json.dumps({'status':report['status'],'counts':report['counts']}))
    except (ValueError,RuntimeError) as e:print(json.dumps({'error':str(e)[:1800]}));sys.exit(2)
