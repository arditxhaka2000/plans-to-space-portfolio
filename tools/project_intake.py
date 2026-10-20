"""Project-neutral PDF evidence intake. Never generates guessed building geometry.

Usage: python tools/project_intake.py drawing.pdf --output projects/new-project
Output directory must not exist, preventing accidental overwrite of a project.
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
import pymupdf

def intake(source: Path, output: Path):
    if not source.is_file():
        raise ValueError('Source PDF does not exist')
    if output.exists():
        raise ValueError('Output already exists; choose a new project directory')
    doc=pymupdf.open(source)
    if doc.needs_pass:
        raise ValueError('Encrypted PDF requires an unlocked source copy')
    output.mkdir(parents=True)
    (output/'pages').mkdir()
    shutil.copy2(source,output/'source.pdf')
    sheets=[]
    for index,page in enumerate(doc):
        text=page.get_text()
        words=page.get_text('words')
        number=index+1
        preview=f'pages/{number:03d}.png'
        page.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(output/preview)
        annotations=[]
        for annotation in page.annots() or []:
            annotations.append({'type':annotation.type[1],'rect':list(annotation.rect),'info':annotation.info})
        sheets.append({'id':f'page-{number}','page':number,'preview':preview,'sizePoints':[page.rect.width,page.rect.height],
          'text':text,'words':words,'annotations':annotations,'sheetCandidates':sorted(set(re.findall(r'\bA\d+\.\d+\b',text))),
          'textStatus':'embedded-text-unverified' if text.strip() else 'OCR_REQUIRED',
          'visualReview':'not-reviewed','classification':'unassigned','scaleCalibration':None,'regions':[]})
    manifest={'schemaVersion':1,'name':source.stem,'source':{'file':'source.pdf','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'pageCount':len(sheets)},
      'sheets':sheets,'materials':{},'levels':[],'elevations':{},'components':[],
      'release':{'status':'BLOCKED','reasons':['Sheet roles not assigned','Scale and units not calibrated','Geometry not extracted','Material regions not mapped','Cross-view reconciliation not performed','Visual review incomplete']}}
    (output/'project.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summary={'pageCount':len(sheets),'ocrRequired':sum(p['textStatus']=='OCR_REQUIRED' for p in sheets),'geometryComponents':0,'status':'BLOCKED'}
    (output/'intake-report.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary))
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('pdf',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    intake(args.pdf.resolve(),args.output.resolve())
