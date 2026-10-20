import sqlite3
from pathlib import Path
root=Path(__file__).resolve().parents[1]
db=sqlite3.connect(root/'server/App_Data/saas/jobs/70dd38c388ee41c386acd80298427e06/evidence.sqlite')
for page in (20,22,24):
 print('PAGE',page)
 print(db.execute("select id,round(x0,2),round(y0,2),round(x1,2),round(y1,2) from observation where page=? and kind='line' and abs(x1-x0)<.05 and x0 between 230 and 430 and y1-y0>60 and y0 between 400 and 1100 order by x0,y0",(page,)).fetchall())
 print('horizontal',db.execute("select id,round(x0,2),round(y0,2),round(x1,2),round(y1,2) from observation where page=? and kind='line' and abs(y1-y0)<.05 and x0 between 230 and 335 and x1 between 300 and 370 and y0 between 400 and 1100 order by y0,x0",(page,)).fetchall())
