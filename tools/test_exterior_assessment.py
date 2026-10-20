"""Executable native-vector reader tests; fixtures stay outside application storage."""
import sys,tempfile,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'worker'))
from exterior_assessment import assess,page_evidence
import pdfplumber
try:
 from reportlab.pdfgen import canvas
except ModuleNotFoundError:
 sys.path.append(str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages'))
 from reportlab.pdfgen import canvas
folder=Path(tempfile.mkdtemp(prefix='exterior-reader-test-',dir=root/'work'))
def fixture(path,omit=False):
 c=canvas.Canvas(str(path),pagesize=(800,800));c.setFont('Helvetica',12)
 c.drawString(50,760,'GROUND FLOOR PLAN');c.setFillColorRGB(.8,.7,.2);c.rect(100,400,240,160,fill=1,stroke=1);c.setFillColorRGB(0,0,0)
 # Exact tick-centred metric scale, independent of font width.
 for x,t in [(100,'0'),(150,'5'),(200,'10')]:c.drawCentredString(x,350,t)
 c.drawString(215,350,'m');c.drawString(50,300,'3 m GROUND FLOOR');c.drawString(50,280,'FLAT ROOF')
 for i,d in enumerate(['NORTH','SOUTH','EAST']+([] if omit else ['WEST'])):
  c.drawString(400,700-i*140,d+' ELEVATION');c.rect(400,620-i*140,120,60,fill=0)
 c.save()
for missing in [False,True]:
 path=folder/('missing.pdf' if missing else 'complete.pdf');fixture(path,missing)
 with pdfplumber.open(path) as pdf:
  evidence=[page_evidence(p,{'page':i+1,'text':p.extract_text()}) for i,p in enumerate(pdf.pages)]
 result=assess(evidence,hashlib.sha256(path.read_bytes()).hexdigest())
 assert result['status']==('insufficient' if missing else 'ready'),result
 if not missing:
  assert result['geometry']['heights']==[3]
  pts=result['geometry']['points'];assert abs(max(x for x,z in pts)-24)<.01 and abs(max(z for x,z in pts)-16)<.01
  source=evidence[0];source['heights'].append({'floor':0,'height':4,'text':'4 m GROUND FLOOR'})
  assert assess([source],'test')['status']=='insufficient'
 print('PASS',path.name,result['status'])
print('Fixtures retained:',folder)
