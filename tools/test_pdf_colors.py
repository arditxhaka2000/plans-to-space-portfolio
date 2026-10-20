"""Regression for nonnumeric PDF colour operands, without reading a source PDF."""
import sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from pdf_interpret import rgb, fill_shapes, vector_walls, columns

class Colors(unittest.TestCase):
    def test_device_colors(self):
        for value,expected in [(0,(0,0,0)),('0.5',(.5,.5,.5)),(['.2','.4','.6'],(.2,.4,.6)),((.2,),(.2,.2,.2)),((0,1,1,0),(1,0,0))]:
            with self.subTest(value=value):self.assertEqual(rgb(value),expected)

    def test_unsupported_colors_are_ignored_by_geometry(self):
        for value in ['PatternName',('PatternName',),[.5,'PatternName'],None,[],[0,0],{},float('nan'),float('inf'),[-1,0,0],[1,2,0],True]:
            with self.subTest(value=value):
                self.assertEqual(rgb(value),(1,1,1))
                def rect(x,y,w,h):return dict(fill=True,non_stroking_color=value,x0=x,x1=x+w,top=y,bottom=y+h,width=w,height=h,pts=[(x,y),(x+w,y),(x+w,y+h),(x,y+h)])
                page=SimpleNamespace(width=100,height=100,curves=[],rects=[rect(10,10,10,10),rect(25,10,.2,5),rect(30,10,.5,.5),rect(0,0,100,100)])
                self.assertEqual(fill_shapes(page,1),[])
                self.assertEqual(vector_walls(page,1),[])
                self.assertEqual(columns(page,1),[])

if __name__=='__main__':unittest.main()
