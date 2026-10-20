"""Versioned, source-linked evidence store. Observations are not approved geometry."""
import json,sqlite3,re,hashlib,argparse
from pathlib import Path
import pdfplumber

def pack(value):return json.dumps(value,ensure_ascii=False,default=str)

def collect(source,out,manifest,progress=lambda *a:None):
    target=out/'evidence.sqlite'
    if target.exists():raise ValueError('Evidence database already exists; create a new version')
    db=sqlite3.connect(target)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE document(id INTEGER PRIMARY KEY,sha256 TEXT,filename TEXT,version TEXT);
    CREATE TABLE page(number INTEGER PRIMARY KEY,sheet_code TEXT,title TEXT,role TEXT,width REAL,height REAL,origin_x REAL,origin_top REAL,rotation INTEGER,full_text TEXT,text_method TEXT);
    CREATE TABLE observation(id INTEGER PRIMARY KEY,page INTEGER REFERENCES page(number),kind TEXT,x0 REAL,y0 REAL,x1 REAL,y1 REAL,text TEXT,payload TEXT,verification TEXT DEFAULT 'unverified');
    CREATE INDEX obs_page_kind ON observation(page,kind);
    CREATE TABLE fact(id INTEGER PRIMARY KEY,page INTEGER REFERENCES page(number),kind TEXT,code TEXT,value TEXT,verification TEXT DEFAULT 'unverified');
    CREATE TABLE sheet_reference(id INTEGER PRIMARY KEY,source_page INTEGER REFERENCES page(number),target_code TEXT,target_pages TEXT,status TEXT);
    CREATE TABLE extracted_table(id INTEGER PRIMARY KEY,page INTEGER REFERENCES page(number),bounds TEXT,cells TEXT,verification TEXT DEFAULT 'table-detection-unverified');
    CREATE TABLE issue(id INTEGER PRIMARY KEY,page INTEGER,code TEXT,message TEXT);
    CREATE TABLE coverage(page INTEGER PRIMARY KEY REFERENCES page(number),characters INTEGER,words INTEGER,lines INTEGER,rectangles INTEGER,curves INTEGER,images INTEGER,annotations INTEGER,table_count INTEGER);
    ''')
    db.execute('INSERT INTO document VALUES(1,?,?,?)',(manifest['sourceSha256'],source.name,'evidence-1'))
    codes={}
    for s in manifest['sheets']:
        if s['code']:codes.setdefault(s['code'],[]).append(s['page'])
    with pdfplumber.open(source) as pdf:
        if len(pdf.pages)!=len(manifest['sheets']):raise ValueError('Page inventory mismatch')
        for p,s in zip(pdf.pages,manifest['sheets']):
            n=s['page'];progress('Indexing detailed evidence',n,len(pdf.pages))
            bx,by,_,_=p.bbox
            evidence=json.loads((out/s['evidence']).read_text(encoding='utf-8'))
            db.execute('INSERT INTO page VALUES(?,?,?,?,?,?,?,?,?,?,?)',(n,s['code'],s['title'],s['role'],p.width,p.height,bx,by,p.rotation,evidence['text'],s['textMethod']))
            def insert(kind,objects):
                rows=[]
                for obj in objects:
                    rows.append((n,kind,obj.get('x0',bx)-bx,obj.get('top',by)-by,obj.get('x1',bx)-bx,obj.get('bottom',by)-by,obj.get('text'),pack({k:v for k,v in obj.items() if k not in ('stream','data')})))
                db.executemany('INSERT INTO observation(page,kind,x0,y0,x1,y1,text,payload) VALUES(?,?,?,?,?,?,?,?)',rows)
            words=p.extract_words(extra_attrs=['fontname','size'])
            insert('word',words);insert('character',p.chars)
            for kind,objects in [('line',p.lines),('rectangle',p.rects),('curve',p.curves),('image',p.images),('annotation',p.annots or [])]:insert(kind,objects)
            # Keep positioned dimension-like text without inventing its target element.
            dimensions=[w for w in words if re.search(r'\d',w['text']) and re.search(r'[\'"′″]|\b(?:mm|cm|m)\b',w['text'])]
            insert('dimension-token',dimensions)
            for box in evidence.get('ocrBoxes',[]):
                db.execute('INSERT INTO observation(page,kind,text,payload) VALUES(?,?,?,?)',(n,'ocr-preview-pixels',box['text'],pack(box)))
            count=0
            if s['role']=='schedule':
                try:
                    for table in p.find_tables():
                        x0,y0,x1,y1=table.bbox
                        db.execute('INSERT INTO extracted_table(page,bounds,cells) VALUES(?,?,?)',(n,pack([x0-bx,y0-by,x1-bx,y1-by]),pack(table.extract())));count+=1
                except Exception as exc:db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(n,'TABLE_EXTRACTION',str(exc)[:500]))
                if not count:db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(n,'TABLE_NOT_RECOGNIZED','Schedule text retained, but table structure was not recognized.'))
            for ref in s['references']:
                targets=codes.get(ref,[])
                db.execute('INSERT INTO sheet_reference(source_page,target_code,target_pages,status) VALUES(?,?,?,?)',(n,ref,pack(targets),'unique-sheet-match' if len(targets)==1 else 'ambiguous' if targets else 'unresolved-or-non-sheet-tag'))
            db.execute('INSERT INTO coverage VALUES(?,?,?,?,?,?,?,?,?)',(n,len(p.chars),len(words),len(p.lines),len(p.rects),len(p.curves),len(p.images),len(p.annots or []),count))
            if not words:db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(n,'NO_POSITIONED_TEXT','Embedded words absent; OCR observations, if available, use preview pixels.'))
            if s['code'] is None or s['role']=='unclassified':db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(n,'PAGE_CLASSIFICATION','Page identity or role requires review.'))
            if s['role'] in ('plan','slab-plan','elevation','section') and not s['metersPerPoint']:db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(n,'SCALE_UNRESOLVED','Missing or ambiguous printed scale; geometry must not assume calibration.'))
            if not evidence['text'].strip():db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(n,'UNREADABLE_TEXT','Neither embedded extraction nor OCR produced text. Original page retained.'))
            db.commit();p.close()
    for kind in ('materials','levels'):
        for f in manifest[kind]:db.execute('INSERT INTO fact(page,kind,code,value) VALUES(?,?,?,?)',(f['sourcePage'],kind,f.get('code',f.get('name')),pack(f)))
    for issue in manifest['issues']:db.execute('INSERT INTO issue(page,code,message) VALUES(?,?,?)',(issue.get('page'),issue['code'],issue['message']))
    db.commit()
    integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
    fk=db.execute('PRAGMA foreign_key_check').fetchall()
    summary={'schemaVersion':1,'sourceSha256':manifest['sourceSha256'],'integrity':integrity,'foreignKeyErrors':len(fk),'pages':db.execute('SELECT COUNT(*) FROM page').fetchone()[0],'observations':dict(db.execute('SELECT kind,COUNT(*) FROM observation GROUP BY kind')),'facts':db.execute('SELECT COUNT(*) FROM fact').fetchone()[0],'references':db.execute('SELECT COUNT(*) FROM sheet_reference').fetchone()[0],'tables':db.execute('SELECT COUNT(*) FROM extracted_table').fetchone()[0],'issues':db.execute('SELECT COUNT(*) FROM issue').fetchone()[0],'limitations':['Raw drawing primitives are not semantic walls or openings.','Table detection is limited to recognized schedule sheets.','Dimension tokens have no verified element association.','Embedded image bytes remain in the original PDF; image metadata is indexed.','Original coordinates remain in payload; bounding boxes are normalized top-left PDF points.']}
    summary['coverageWarnings']=[{'page':p,'code':c,'message':m} for p,c,m in db.execute('SELECT page,code,message FROM issue ORDER BY page,id')]
    db.close()
    if integrity!='ok' or fk:raise ValueError('Evidence database integrity failed')
    (out/'evidence-summary.json').write_text(pack(summary),encoding='utf-8')
    return summary

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pdf',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    m=json.loads((a.output/'manifest.json').read_text(encoding='utf-8'))
    if hashlib.sha256(a.pdf.read_bytes()).hexdigest()!=m['sourceSha256']:raise ValueError('Source hash mismatch')
    print(pack(collect(a.pdf,a.output,m,lambda stage,n,total:print(f'{stage}: {n}/{total}',flush=True))))
