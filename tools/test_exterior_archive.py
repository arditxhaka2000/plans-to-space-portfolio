"""Check archival integrity and retry behavior without requiring Supabase."""
import hashlib, json, sys, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'worker'))
from cloud_store import exterior_reference
out=Path(tempfile.mkdtemp(prefix='archive-test-',dir=root/'work'));(out/'pages').mkdir()
image=b'original appearance bytes';(out/'pages/012-appearance.png').write_bytes(image)
data=json.dumps({'sourceSha256':'source','rawLinework':[list(range(100))]*1000,'elevations':[{'page':12,'appearance':{'asset':'pages/012-appearance.png','sha256':hashlib.sha256(image).hexdigest()}}]}).encode()
reference=exterior_reference(out,data);assert len(json.dumps(reference))<2000
assert (out/reference['artifact']).read_bytes()==data
assert (out/reference['assets'][0]['artifact']).read_bytes()==image
assert exterior_reference(out,data)==reference and len(list((out/'artifacts').iterdir()))==2
# A later current-file change must not mutate the old checksum-addressed archive.
(out/'pages/012-appearance.png').write_bytes(b'later appearance')
assert (out/reference['assets'][0]['artifact']).read_bytes()==image
try:exterior_reference(out,data)
except ValueError:pass
else:raise AssertionError('Mismatched source bytes must be rejected')
print('PASS: lossless immutable JSON/image archives, small metadata, idempotent retry, historical preservation, checksum mismatch rejection.')
