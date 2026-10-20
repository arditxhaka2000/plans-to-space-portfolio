"""Conservative exterior massing reader. No filename profiles or invented dimensions.

Supports a single filled vector footprint, a metric three-mark scale bar,
explicit floor-to-floor heights, four named elevations, and an explicit flat roof.
Everything else is reported as insufficient/unsupported, never guessed.
"""
import re,math
from shapely.geometry import Polygon
VERSION='exterior-evidence-1'

def scale_bar(words):
    candidates=[]
    for zero in words:
        if zero['text']!='0':continue
        row=sorted([w for w in words if abs(w['top']-zero['top'])<2 and w['x0']>=zero['x0']],key=lambda w:w['x0'])
        if len(row)<4:continue
        a,b,c,unit=row[:4]
        if not re.fullmatch(r'\d+(?:\.\d+)?',b['text']) or not re.fullmatch(r'\d+(?:\.\d+)?',c['text']) or unit['text'].lower()!='m':continue
        bv,cv=float(b['text']),float(c['text'])
        x=lambda w:(w['x0']+w['x1'])/2
        if not 0<bv<cv or x(b)-x(a)<10 or x(c)-x(b)<10:continue
        s1=bv/(x(b)-x(a));s2=(cv-bv)/(x(c)-x(b))
        if abs(s1-s2)/max(s1,s2)>.06:continue
        candidates.append({'metresPerPoint':cv/(x(c)-x(a)),'bounds':[a['x0'],min(w['top'] for w in row[:4]),unit['x1'],max(w['bottom'] for w in row[:4])],'text':' '.join(w['text'] for w in row[:4])})
    if not candidates:return None
    if max(c['metresPerPoint'] for c in candidates)/min(c['metresPerPoint'] for c in candidates)>1.03:return None
    return candidates[0]

def footprint(page):
    candidates=[]
    for obj in page.curves+page.rects:
        color=obj.get('non_stroking_color')
        if not obj.get('fill') or not isinstance(color,(list,tuple)) or len(color)!=3:continue
        # Coloured floor fills only; grayscale linework and scans are unsupported.
        if max(color)-min(color)<.15 or obj['width']<50 or obj['height']<50:continue
        if obj['width']>page.width*.96 or obj['height']>page.height*.9:continue
        if obj['object_type']=='rect':pts=[(obj['x0'],obj['top']),(obj['x1'],obj['top']),(obj['x1'],obj['bottom']),(obj['x0'],obj['bottom'])]
        else:
            if any(command[0] not in ('m','l','h') for command in obj.get('path',[])):continue
            pts=obj['pts']
            if len(pts)<4 or math.dist(pts[0],pts[-1])>.1:continue
        poly=Polygon(pts)
        if not poly.is_valid or poly.area<2500:continue
        # Ignore inset/outset duplicates of the same fill, not distinct buildings.
        if any(poly.intersection(q).area/min(poly.area,q.area)>.95 for q in candidates):continue
        candidates.append(poly)
    if len(candidates)!=1:return None,('No unique filled vector footprint' if not candidates else 'Multiple separate floor fills/buildings require registration')
    if len(candidates[0].exterior.coords)>41:return None,'Footprint has more vertices than the validated draft limit'
    return candidates[0],None

def page_evidence(page,data):
    text=data.get('text','');native=page.extract_text() or '';words=page.extract_words();upper=native.upper()
    directions=sorted(set(re.findall(r'\b(NORTH|SOUTH|EAST|WEST)\s+(?:BUILDING\s+)?ELEVATION\b',text.upper())))
    floor_heights=[]
    # Explicit height and floor label on the same extracted line only.
    for line in native.splitlines():
        match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*m\s+(GROUND FLOOR|FLOOR\s+\d+)\s*',line,re.I)
        if match and 1<=float(match[1])<=10:floor_heights.append({'floor':0 if match[2].upper()=='GROUND FLOOR' else int(re.search(r'\d+',match[2])[0]),'height':float(match[1]),'text':line.strip()})
    result={'page':data['page'],'directions':directions,'heights':floor_heights,'flatRoof':bool(re.search(r'\bFLAT ROOF\b',upper)),'plan':None,'issue':None}
    if re.search(r'\b(?:FLOOR PLAN|GROUND FLOOR PLAN|ROOF PLAN)\b',upper):
        poly,issue=footprint(page);scale=scale_bar(words)
        if poly is not None and scale:
            result['plan']={'points':[[round(x,5),round(y,5)] for x,y in list(poly.exterior.coords)[:-1]],'scale':scale,'bounds':list(poly.bounds),'areaSquareMetres':poly.area*scale['metresPerPoint']**2}
        else:result['issue']=issue or 'No unambiguous metric scale bar'
    return result

def assess(pages,source_hash):
    evidence=[{'page':p['page'],'directions':p['directions'],'heights':p['heights'],'flatRoof':p['flatRoof'],'planFound':bool(p['plan']),'issue':p['issue']} for p in pages]
    missing=[];directions=set(d for p in pages for d in p['directions'])
    if directions!=set(['NORTH','SOUTH','EAST','WEST']):missing.append('Unresolved named elevations: '+', '.join(sorted(set(['NORTH','SOUTH','EAST','WEST'])-directions)))
    plans=[p for p in pages if p['plan']]
    if len(plans)!=1:missing.append('Need one uniquely scaled footprint; multiple floor plans/setbacks are not yet registered reliably.')
    if not any(p['flatRoof'] for p in pages):missing.append('Roof form not established: this reader supports explicitly labelled flat roofs only.')
    heights={};conflict=False
    for p in pages:
        for h in p['heights']:
            if h['floor'] in heights and abs(heights[h['floor']]['height']-h['height'])>.01:conflict=True
            heights[h['floor']]={**h,'page':p['page']}
    if conflict:missing.append('Conflicting floor heights.')
    if not heights or sorted(heights)!=list(range(max(heights,default=-1)+1)):missing.append('Explicit contiguous ground/upper-floor heights could not be linked.')
    if heights and max(heights)>30:missing.append('More than 31 floors are outside this reader limit.')
    # This narrow automatic mode needs explicit repetition, avoiding reuse of a
    # ground plan for towers with unseen setbacks.
    # A single-storey building needs no repetition assumption.
    if len(heights)>1:missing.append('Multi-storey plan registration is not yet validated; use a GLB for this building.')
    limits=['Exterior massing only; window/door openings and facade materials are not reconstructed.','Drawing classification is heuristic, not proof of architectural completeness.','Native filled-vector metric plans only; image/scanned and grayscale plans can supply context but not geometry in this version.']
    report={'version':VERSION,'sourceSha256':source_hash,'status':'insufficient' if missing else 'ready','scope':'exterior-massing','missing':missing,'limitations':limits,'evidence':evidence,'geometry':None}
    if not missing:
        plan=plans[0];points=plan['plan']['points'];scale=plan['plan']['scale']['metresPerPoint'];x0=min(p[0] for p in points);z0=min(p[1] for p in points)
        report['geometry']={'points':[[(x-x0)*scale,(z-z0)*scale] for x,z in points],'heights':[heights[i]['height'] for i in sorted(heights)],'sourcePage':plan['page'],'sourceBounds':plan['plan']['bounds'],'scaleEvidence':plan['plan']['scale'],'heightEvidence':list(heights.values())}
    return report
