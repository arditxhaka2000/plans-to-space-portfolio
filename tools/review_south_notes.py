"""Preserve page 28 reference crops; no alteration of drawing content."""
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
im=Image.open(ROOT/'document/pages/sheet-28.jpg')
out=ROOT/'client/public/floors'
regions={'facade':(515,340,1190,1080),'fields':(745,440,995,1070),'schedule':(1390,65,1705,460),'general':(1700,65,1870,135),'revisions':(1700,300,1870,490),'callouts':(1080,930,1425,1110),'datums':(120,330,335,1090),'grids':(520,205,1190,335),'title':(1700,990,1870,1280)}
for name,bounds in regions.items():
    box=tuple(round(v*(im.width/1888 if i%2==0 else im.height/1335)) for i,v in enumerate(bounds))
    im.crop(box).resize(((bounds[2]-bounds[0])*3,(bounds[3]-bounds[1])*3)).save(out/f'south-{name}.jpg',quality=97)
