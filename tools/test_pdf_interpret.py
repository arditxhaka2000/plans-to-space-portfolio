"""Independent and metamorphic drawing fixtures; no building-specific source input."""
import json,sys,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'worker'))
try:from reportlab.pdfgen.canvas import Canvas
except ModuleNotFoundError:
    sys.path.append(str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages'))
    from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
import pypdfium2
from pdf_interpret import interpret

out=Path(tempfile.mkdtemp(prefix='interpret-fixtures-',dir=root/'work'))
def fixture(path,height=3.4,factor=1,translate=0):
    c=Canvas(str(path),pagesize=(800,650))
    for floor in [0,1]:
        c.drawString(30,620,'FLOOR PLAN');c.drawString(30,602,'GROUND FLOOR' if floor==0 else 'FLOOR 1');c.saveState();c.translate(translate,translate);c.scale(factor,factor)
        c.setFillColorRGB(.7,.7,.7)
        for x in [70,310]:c.rect(x,170,120,200,fill=1,stroke=0)
        c.setFillColorRGB(0,0,0)
        for x in [70,130,190,310,370,430]:
            for y in [170,270,370]:c.rect(x-2,y-2,4,4,fill=1,stroke=0)
        for text,x in [('0',70),('5',120),('10',170)]:c.drawCentredString(x,70,text)
        c.drawString(190,70,'m');c.restoreState();c.showPage()
    c.drawString(30,620,'SECTION');c.drawString(30,560,f'{height} m GROUND FLOOR');c.drawString(30,540,'2.8 m FLOOR 1');c.save()

results=[]
for name,height,factor,translate in [('baseline',3.4,1,0),('unrelated-name',4.1,1.1,17)]:
    pdf=out/(name+'.pdf');fixture(pdf,height,factor,translate);recipe,report=interpret(pdf,out/name)
    assert recipe is not None and report['counts']['storeys']==2 and report['counts']['walls']==16
    assert all(abs(m['areaSquareMetres']-480)<.1 for m in report['measurements'])
    assert report['measurements'][0]['heightMetres']==height and report['measurements'][1]['baseMetres']==height
    assert len(recipe.volumes)==6
    results.append({'fixture':name,'counts':report['counts'],'area':report['measurements'][0]['areaSquareMetres'],'groundHeight':height})

native=out/'scan-source.pdf';c=Canvas(str(native),pagesize=(800,650));c.setFont('Helvetica',16);c.drawString(40,600,'GROUND FLOOR PLAN');c.drawString(40,565,'3.2 m GROUND FLOOR');c.setFillColorRGB(.6,.6,.6);c.rect(120,230,240,180,fill=1,stroke=1);c.setFillColorRGB(0,0,0)
for text,x in [('0',120),('5',170),('10',220)]:c.drawCentredString(x,180,text)
c.drawString(250,180,'m');c.save()
pdf=pypdfium2.PdfDocument(str(native));image=pdf[0].render(scale=2).to_pil();scanned=out/'raster-only.pdf';c=Canvas(str(scanned),pagesize=(800,650));c.drawImage(ImageReader(image),0,0,width=800,height=650);c.save();pdf.close()
recipe,report=interpret(scanned,out/'raster')
assert recipe is not None,report
assert report['counts']['storeys']==1 and any('OCR' in s for s in report['issues'])
assert abs(report['measurements'][0]['heightMetres']-3.2)<.001
assert abs(report['measurements'][0]['areaSquareMetres']-432)/432<.12,report['measurements']
results.append({'fixture':'raster-only','counts':report['counts'],'area':report['measurements'][0]['areaSquareMetres']})
empty=out/'not-a-drawing.pdf';c=Canvas(str(empty));c.drawString(40,700,'This document contains prose, not a scaled architectural plan.');c.save();recipe,report=interpret(empty,out/'empty');assert recipe is None and report['status']=='needs-input'
result={'passed':True,'fixtures':results,'unrelatedDocumentRejected':True,'checks':['arbitrary filenames','two disconnected footprints','two registered storeys','changed height follows printed dimension','page scaling and translation preserve metric area','raster OCR and linework fallback','non-drawing does not create geometry']};(root/'evidence/pdf-interpret-fixtures.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
