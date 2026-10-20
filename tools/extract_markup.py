"""Extract source-colour masks; calibration is project data, never inferred geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import fitz
import numpy as np
from PIL import Image

def yellow_mask(rgb):
    # Yellow highlighter may be translucent over grey drawings. Preserve RGB,
    # not a replacement yellow; do not close holes or drop small components.
    a = rgb.astype(np.int16)
    r, g, b = a[:,:,0], a[:,:,1], a[:,:,2]
    return (r > 105) & (g > 105) & (np.abs(r-g) < 85) & (np.minimum(r,g)-b > 55)

def extract(pdf, recipe, output):
    output.mkdir(parents=True, exist_ok=True)
    report = {'sourceSha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
              'method':'yellow RGB segmentation v1; no gap filling', 'faces':[]}
    with fitz.open(pdf) as doc:
        for face in recipe['faces']:
            page = doc[face['page']-1]
            pix = page.get_pixmap(matrix=fitz.Matrix(2,2), alpha=False)
            img = Image.frombytes('RGB',[pix.width,pix.height],pix.samples).resize(tuple(recipe['referenceSize']))
            crop = np.array(img.crop(tuple(face['bounds'])))
            mask = yellow_mask(crop)
            rgba = np.dstack([crop, mask.astype(np.uint8)*255])
            name = face['direction']+'-yellow-mask.png'
            Image.fromarray(rgba).save(output/name)
            saved = np.array(Image.open(output/name))
            assert np.array_equal(saved[:,:,3]>0,mask)
            assert np.array_equal(saved[:,:,:3][mask],crop[mask])
            report['faces'].append({**face,'asset':name,'selectedPixels':int(mask.sum()),
                'exportedPixels':int((saved[:,:,3]>0).sum()),'lostSelectedPixels':0,
                'status':'PIXEL_EXPORT_VERIFIED_GEOMETRY_UNVERIFIED'})
    (output/'markup-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--pdf',type=Path,required=True)
    p.add_argument('--recipe',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    extract(args.pdf,json.loads(args.recipe.read_text()),args.output)
