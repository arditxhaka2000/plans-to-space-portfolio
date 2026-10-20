import re
from fractions import Fraction
def clean(text):
    return re.sub(r'\n+', '\n', text.replace('\r','\n').replace('\ufffe','-')).strip()

def sheet_info(text, titleblock):
    candidates = re.findall(r'(?m)^\s*([A-Z]{1,3}-?\d{1,3}(?:\.\d+)?)\s*$',titleblock)
    code = candidates[-1] if candidates else None
    lines = [line.strip() for line in titleblock.splitlines() if line.strip()]
    title = 'Unclassified sheet'
    if code and code in lines:
        i=lines.index(code)+1
        named=list(dict.fromkeys(line for line in lines if len(line)<100 and re.search(r'PLAN|ELEVATION|SECTION|DETAIL|SCHEDULE|ROOF|FLOOR',line,re.I) and line!=code))
        title=' '.join(named) if named else ' '.join(lines[i:i+2]) or 'Unclassified sheet'
        title=re.split('MIXED-USE|PROJECT NUMBER',title,flags=re.I)[0].strip()
    upper=title.upper()
    role=next((r for needle,r in [('REFLECTED','ceiling-plan'),('SLAB','slab-plan'),('ELEVATION','elevation'),('SCHEDULE','schedule'),('ASSEMBL','assembly'),('SECTION','section'),('DETAIL','detail'),('SITE PLAN','site-plan'),('COVER','cover'),('PLAN','plan')] if needle in upper),'unclassified')
    return code,title,role

def scale_from_text(text):
    values=set()
    for raw in re.findall(r'(\d+(?:/\d+)?)\s*["”]\s*=\s*1\s*[\'’]\s*-?\s*0\s*["”]',text):
        f=Fraction(raw)
        if f>0:values.add(round(.3048/(72*float(f)),10))
    return next(iter(values)) if len(values)==1 else None

def level_observations(text,page):
    result=[]
    pattern=r'\b(LEVEL\s+\d+(?:\s+MEZ\.?)?|ROOF|P[12])\s*\n\s*(\d+)\s*[\'’]\s*-\s*(\d+(?:\s+\d+/\d+)?)\s*["”]'
    for m in re.finditer(pattern,text,re.I):
        inches=sum(float(Fraction(x)) for x in m[3].split())
        result.append({'name':re.sub(r'\s+',' ',m[1].upper()),'elevationMeters':round(int(m[2])*.3048+inches*.0254,5),'sourcePage':page,'sourceText':m[0]})
    return result

def material_observations(text,page):
    if 'MATERIAL LEGEND' not in text.upper():return []
    section=re.split(r'MATERIAL LEGEND\s*:',text,flags=re.I)[-1]
    records=[]
    # Handles both same-line and separate-line code/description layout.
    for m in re.finditer(r'(?m)^([A-Z]\d?)\s+(?=[A-Z])([^\n]+)',section):
        description=m[2].strip()
        if len(description)<12:continue
        records.append({'code':m[1],'description':description,'sourcePage':page,'verification':'extracted-not-verified'})
    return records

