#!/usr/bin/env python3
"""Export native review views for display feeds; geometry alone is not qualification."""
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import cairo
import gi
gi.require_version('Rsvg','2.0')
from gi.repository import Rsvg
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='kestrel-display-view-') as temp:
    native=Path(temp)/'native.svg'
    subprocess.run(['kicad-cli','pcb','export','svg','--mode-single','--layers','F.Cu,In2.Cu,B.Cu,F.Fab,Edge.Cuts','--exclude-drawing-sheet','--page-size-mode','2','-o',str(native),str(ROOT/'electrical/kestrel-revb.kicad_pcb')],check=True)
    for name,(x,y,w,h,scale) in {'pcb-display-feeds':(32,47,136,45,16),'pcb-backlight-pwm-escape':(115,82,8,5,160),'pcb-display-led-fpc':(104,50,10,8,100)}.items():
        tree=ET.parse(native);r=tree.getroot();r.set('viewBox',f'{x-32} {y-47} {w} {h}');r.set('width',str(w*scale));r.set('height',str(h*scale))
        out=ROOT/'generated'/f'{name}.svg';tree.write(out)
        surface=cairo.ImageSurface(cairo.FORMAT_ARGB32,w*scale,h*scale);ctx=cairo.Context(surface);ctx.set_source_rgb(1,1,1);ctx.paint()
        handle=Rsvg.Handle.new_from_file(str(out));rect=Rsvg.Rectangle();rect.x=0;rect.y=0;rect.width=w*scale;rect.height=h*scale
        handle.render_document(ctx,rect);surface.write_to_png(str(out.with_suffix('.png')))
        print('Refreshed',name)
