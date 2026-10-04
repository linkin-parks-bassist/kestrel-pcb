#!/usr/bin/env python3
"""Native copper review of RGB resistor-to-FPC routing; loaded timing is unqualified."""
from pathlib import Path
import argparse,subprocess,tempfile,xml.etree.ElementTree as ET
import cairo,gi
gi.require_version('Rsvg','2.0')
from gi.repository import Rsvg
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--board',type=Path,default=ROOT/'electrical/kestrel-revb.kicad_pcb');p.add_argument('--output-dir',type=Path,default=ROOT/'generated');args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory(prefix='kestrel-rgb-output-view-') as temp:
 native=Path(temp)/'native.svg'
 subprocess.run(['kicad-cli','pcb','export','svg','--mode-single','--layers','F.Cu,In2.Cu,B.Cu,Edge.Cuts','--exclude-drawing-sheet','--page-size-mode','2','-o',str(native),str(args.board)],check=True)
 for name,(x,y,w,h,scale) in {'pcb-display-rgb-output':(108,48,28,47,30),'pcb-display-rgb-output-escape':(115,72,21,22,60)}.items():
  tree=ET.parse(native);r=tree.getroot();r.set('viewBox',f'{x-32} {y-47} {w} {h}');r.set('width',str(w*scale));r.set('height',str(h*scale));out=args.output_dir/(name+'.svg');tree.write(out)
  s=cairo.ImageSurface(cairo.FORMAT_ARGB32,w*scale,h*scale);ctx=cairo.Context(s);ctx.set_source_rgb(1,1,1);ctx.paint();handle=Rsvg.Handle.new_from_file(str(out));rect=Rsvg.Rectangle();rect.x=0;rect.y=0;rect.width=w*scale;rect.height=h*scale;handle.render_document(ctx,rect);s.write_to_png(str(out.with_suffix('.png')))
  print('Refreshed',name)
