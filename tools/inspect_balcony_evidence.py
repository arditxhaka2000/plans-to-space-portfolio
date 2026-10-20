"""Read-only balcony evidence diagnostic."""
import sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
db=sqlite3.connect(root/'server/App_Data/saas/jobs/70dd38c388ee41c386acd80298427e06/evidence.sqlite')
for page in (20,22,24):
    print('PAGE',page)
    for region in ((420,500),(1040,1145)):
        print(region,db.execute("select round(x0,2),round(y0,2),round(x1,2),round(y1,2) from observation where page=? and kind='line' and abs(y1-y0)<.1 and y0 between ? and ? and x1-x0>60 order by y0,x0",(page,*region)).fetchall())
print(db.execute('select full_text from page where number=84').fetchone()[0].encode('ascii','replace').decode())
