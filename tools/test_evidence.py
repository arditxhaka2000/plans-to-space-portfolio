import sqlite3,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with sqlite3.connect(f"file:{root/'work/multifloor-v2/evidence.sqlite'}?mode=ro",uri=True) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not db.execute('PRAGMA foreign_key_check').fetchall()
    assert db.execute('SELECT COUNT(*) FROM page').fetchone()[0]==84
    assert db.execute('SELECT COUNT(*) FROM coverage').fetchone()[0]==84
    for kind,column in [('character','characters'),('word','words'),('line','lines'),('rectangle','rectangles'),('curve','curves')]:
        observed=db.execute('SELECT COUNT(*) FROM observation WHERE kind=?',(kind,)).fetchone()[0]
        expected=db.execute(f'SELECT SUM({column}) FROM coverage').fetchone()[0]
        assert observed==expected,(kind,observed,expected)
    # Negative media origin is normalized to the visible page, not silently left negative.
    words=db.execute("SELECT COUNT(*) FROM observation WHERE page=24 AND kind='word' AND x0>=0 AND y0>=0").fetchone()[0]
    assert words>100
    assert db.execute("SELECT COUNT(*) FROM observation WHERE kind='dimension-token'").fetchone()[0]>0
    assert db.execute('SELECT COUNT(*) FROM fact').fetchone()[0]>0
    print('PASS database integrity, 84-page coverage, primitive-count reconciliation, normalized coordinates, dimension and fact evidence')
