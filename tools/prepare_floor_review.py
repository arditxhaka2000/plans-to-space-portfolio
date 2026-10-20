"""Preserve source sheet images and produce readable plan crops for review."""
from pathlib import Path
from PIL import Image
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'client/public/floors'
OUT.mkdir(parents=True, exist_ok=True)
for level in range(1, 14):
    page = level + 2
    im = Image.open(ROOT / f'work/hires/plan-{page:02d}.jpg')
    sx, sy = im.width / 1888, im.height / 1335
    def crop(bounds):
        return im.crop(tuple(round(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(bounds)))
    im.save(OUT / f'level-{level}-sheet.jpg', quality=95)
    if level <= 10 or level == 12:
        rcp_page = level + 16 if level <= 10 else 27
        Image.open(ROOT / f'document/pages/sheet-{rcp_page:02d}.jpg').save(OUT / f'level-{level}-rcp.jpg', quality=95)
    crop((550, 150, 1255, 1175)).save(OUT / f'level-{level}-plan.jpg', quality=96)
    crop((640,480,1180,1005) if level>=3 else (550,240,1255,1070)).save(OUT / f'level-{level}-detail.jpg', quality=96)
    for name, bounds in [('north',(560,150,1235,650)),('south',(560,630,1170,1010)),('dimensions',(550,150,1235,260))]:
        crop(bounds).save(OUT / f'level-{level}-{name}.jpg', quality=97)
for name,page in [('south',28),('north',29),('east',30),('west',31),('section',32)]:
    Image.open(ROOT / f'document/pages/sheet-{page:02d}.jpg').save(OUT / f'{name}-elevation.jpg', quality=95)
print(OUT)
