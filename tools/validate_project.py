"""Fail-closed checks for the project-neutral evidence manifest."""
import json
import sys
from pathlib import Path

def validate(project):
    issues=[]
    if project.get('schemaVersion')!=1: issues.append('Unsupported schema version')
    sheets=project.get('sheets',[])
    if len(sheets)!=project.get('source',{}).get('pageCount'): issues.append('Page inventory incomplete')
    if not sheets: issues.append('No source pages')
    for sheet in sheets:
        prefix=str(sheet.get('id','unnamed'))
        if sheet.get('textStatus')!='verified': issues.append(prefix+': text not verified')
        if sheet.get('visualReview')!='verified': issues.append(prefix+': visual review incomplete')
        if sheet.get('classification') in (None,'unassigned'): issues.append(prefix+': sheet role unassigned')
        if sheet.get('classification') in ('plan','elevation','section') and not sheet.get('scaleCalibration'): issues.append(prefix+': missing calibration')
        for region in sheet.get('regions',[]):
            if region.get('status') not in ('modeled-verified','not-applicable-verified'): issues.append(prefix+': unresolved region '+str(region.get('id')))
    ids={s.get('id') for s in sheets}
    materials=project.get('materials',{})
    components=project.get('components',[])
    if not components: issues.append('No geometry components')
    for c in components:
        if c.get('sourceSheet') not in ids: issues.append('Component missing valid source sheet')
        if c.get('materialCode') not in materials: issues.append('Component has unmapped material')
        if c.get('verification')!='verified': issues.append('Component geometry unverified')
    if not project.get('levels'): issues.append('No levels')
    if not project.get('crossViewVerified'): issues.append('Cross-view reconciliation incomplete')
    return {'status':'BLOCKED' if issues else 'CHECKS_PASSED_NOT_CERTIFIED','issues':issues}

if __name__=='__main__':
    result=validate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    print(json.dumps(result,indent=2))
    sys.exit(1 if result['issues'] else 0)
