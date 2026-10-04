#!/usr/bin/env python3
"""Generate reference-panel RGB565/touch connectors; engineering draft.

Run after MCU/backlight generation, before build_project.py.
"""
import json
import math
import sys
import uuid
from pathlib import Path
from display_pins import RGB_SIGNALS, TIMING_SIGNALS, TOUCH_SIGNALS, DISPLAY_PORTS

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27
sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps

S = sx.Symbol
def node(text): return sx.loads(text)
def child(e, key): return next(x for x in e if isinstance(x,list) and x and x[0]==S(key))
def uid(text): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'kestrel/rev-b/display/'+text))


def build():
    folder=ROOT/'electrical'
    path=folder/'kestrel-revb-display.kicad_sch'
    path.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") (uuid "{uid("sheet")}") (paper "A2") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    res='Resistor_SMD:R_0603_1608Metric';cap='Capacitor_SMD:C_0603_1608Metric'
    parts=[]
    def add(ref,lib,value,foot,x,y,nets,angle=0,unit=1):
        parts.append((ref,lib,value,foot,round(x/GRID),round(y/GRID),angle,nets,unit))
    lcd={'1':'BL_LED_K','2':'BL_LED_A','3':'GND','4':'LCD_VDD','29':'GND','30':'LCD_PCLK',
         '31':'LCD_DISP','32':'LCD_HSYNC','33':'LCD_VSYNC','34':'LCD_DE','35':None,'36':'GND',
         '37':None,'38':None,'39':None,'40':None}
    for color,start,first in [('R',5,3),('G',13,2),('B',21,3)]:
        lcd.update({str(start+i):f'LCD_{color}{i}' if i>=first else 'GND' for i in range(8)})
    add('J1001','Connector_Generic:Conn_01x40','DM-TFT50-404 LCD / FH12-40S-0.5SH(55) / contact fit pending',
        'Connector_FFC-FPC:Hirose_FH12-40S-0.5SH_1x40-1MP_P0.50mm_Horizontal',150,85,lcd)
    add('J1002','Connector_Generic:Conn_01x08','DM-TFT50-404 CTP / FH12-8S-0.5SH(55) / contact fit pending',
        'Connector_FFC-FPC:Hirose_FH12-8S-0.5SH_1x08-1MP_P0.50mm_Horizontal',350,65,
        {'1':'GND','2':'TOUCH_VDD','3':'TOUCH_VDD','4':'TOUCH_SCL','5':'TOUCH_SDA',
         '6':'TOUCH_INT','7':'TOUCH_RST_N','8':'GND'})
    signals=RGB_SIGNALS+TIMING_SIGNALS+TOUCH_SIGNALS
    for i,signal in enumerate(signals):
        add(f'R{1001+i}','Device:R','33ohm / 1% / GPIO source damping starting value',res,
            35+(i%6)*90,185+(i//6)*40,{'1':'MCU_'+signal,'2':signal},angle=90)
    for ref,net,x in [('R1026','TOUCH_SCL',260),('R1027','TOUCH_SDA',330)]:
        add(ref,'Device:R','4.7k / 1% / I2C pullup to touch rail',res,x,120,{'1':'TOUCH_VDD','2':net})
    for ref,net,value,x in [('R1028','LCD_DISP','10k',400),('R1029','TOUCH_RST_N','10k',470),('R1030','TOUCH_INT','100k',540)]:
        add(ref,'Device:R',value+' / 1% / default low',res,x,120,{'1':net,'2':'GND'})
    for i,(rail,x,y) in enumerate([('LCD_VDD',260,155),('LCD_VDD',330,155),('TOUCH_VDD',400,155),('TOUCH_VDD',470,155)]):
        add(f'C{1001+i}','Device:C','100nF / 16V X7R / FPC supply bypass',cap,x,y,{'1':rail,'2':'GND'})
    boundary=dict(DISPLAY_PORTS)
    loader=DynamicSymbolLoader(folder)
    for ref,lib,val,foot,x,y,angle,nets,unit in parts:
        family,name=lib.split(':'); loader.inject_symbol_into_schematic(path,family,name)
        assert loader.create_component_instance(path,family,name,ref,val,foot,x*GRID,y*GRID,unit=unit,angle=angle),ref
    tree=sx.loads(path.read_text()); symbols={e[1]:e for e in child(tree,'lib_symbols')[1:]}
    exposed=set()
    by_instance={(p[0],p[8]):p for p in parts}
    def definition(lib):
        sym=symbols[lib]
        ext=next((e[1] for e in sym if isinstance(e,list) and e and e[0]==S('extends')),None)
        return definition(lib.split(':')[0]+':'+ext) if ext else sym
    for inst in tree:
        if not isinstance(inst,list) or not inst or inst[0]!=S('symbol'):continue
        ref=next(e[2] for e in inst if isinstance(e,list) and e and e[0]==S('property') and e[1]=='Reference')
        unit=child(inst,'unit')[1]; _,lib,val,foot,x,y,angle,nets,_=by_instance[ref,unit]
        child(inst,'uuid')[1]=uid(ref+'/'+str(unit))
        coords={};rad=math.radians(angle)
        for section in definition(lib):
            if not isinstance(section,list) or not section or section[0]!=S('symbol'):continue
            if int(str(section[1]).rsplit('_',2)[1]) not in (0,unit):continue
            for pin in section:
                if not isinstance(pin,list) or not pin or pin[0]!=S('pin'):continue
                n=str(child(pin,'number')[1]);px,py,a=child(pin,'at')[1:]
                coords[n]=(round(x*GRID+px*math.cos(rad)-py*math.sin(rad),2),
                           round(y*GRID-px*math.sin(rad)-py*math.cos(rad),2),(a+angle)%360)
        assert set(coords)==set(nets),(ref,unit,coords,nets)
        for n,net in nets.items():
            px,py,a=coords[n];tag=ref+'/'+str(unit)+'/'+n
            if net is None:
                tree.append(node(f'(no_connect (at {px} {py}) (uuid "{uid(tag+"nc")}"))'));continue
            vx,vy={0:(-5.08,0),90:(0,5.08),180:(5.08,0),270:(0,-5.08)}[a]
            ex,ey=round(px+vx,2),round(py+vy,2)
            tree.append(node(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid "{uid(tag+"wire")}"))'))
            is_boundary=net in boundary and net not in exposed
            if is_boundary:exposed.add(net)
            kind='hierarchical_label' if is_boundary else 'label'; shape=f'(shape {boundary[net]})' if is_boundary else ''
            tree.append(node(f'({kind} "{net}" {shape} (at {ex} {ey} 0) '
                             f'(effects (font (size 0.8 0.8)) (justify {"right" if vx<0 else "left"} bottom)) (uuid "{uid(tag+"label")}"))'))
        for e in inst:
            if not isinstance(e,list) or not e:continue
            if e[0]==S('pin'):child(e,'uuid')[1]=uid(ref+'pin'+str(e[1]))
            if e[0]==S('property') and e[1] in ('Reference','Value'):
                is_ref=e[1]=='Reference'
                if not is_ref and ref.startswith(('R','C','L')):e[2]=val.split(' / ')[0]
                if ref.startswith('J'):
                    xx,yy=x*GRID-25,y*GRID-(65 if ref=='J1001' else 20)+(0 if is_ref else 2)
                    if not is_ref:e[2]='LCD RGB / contact fit pending' if ref=='J1001' else 'CAP TOUCH / contact fit pending'
                else:xx,yy=(x+3)*GRID,(y+(-1 if is_ref else 1))*GRID
                if angle==90:xx,yy=x*GRID-3,y*GRID-(8 if is_ref else 6)
                child(e,'at')[1:]=[round(xx,2),round(yy,2),90 if angle==90 else 0]
                child(e,'effects')[1:]=node('(effects (font (size 0.8 0.8)) (justify left))')[1:]
        if ref.startswith(('R','C','L')):
            inst.append(node(f'(property "Rating" "{val}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
        if ref.startswith('R') and 1001 <= int(ref[1:]) <= 1016:
            inst.append(node(f'(property "AssemblySide" "B.Cu / source damping passives; assembly qualification pending" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
        if ref.startswith('J'):
            inst.append(node(f'(property "Qualification" "Bottom-contact footprint provisional; verify flex exposed side, numbering, 0.3mm tail thickness and bends with sample before placement/fabrication" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
    notes=[(20,15,'RGB565 / CAPACITIVE TOUCH - DM-TFT50-404 REFERENCE - ENGINEERING DRAFT'),
           (20,375,'RGB565: GPIO39..43 -> B3..7; GPIO44/45/46/47/32/49 -> G2..7; GPIO26/51/28/53/30 -> R3..7. Low panel data bits grounded.'),
           (20,382,'GPIO9 PCLK / 10 HSYNC / 11 VSYNC / 12 DE / 13 DISP. GPIO15 SCL / 16 SDA / 17 INT / 18 RESET.'),
           (20,389,'LCD power 3.456V; GT911 VDD/VDDIO 3.2V. 4.7k I2C pullups to TOUCH_VDD. INT is bidirectional during reset/address selection.'),
           (20,396,'FPC contact side/numbering/thickness, exact parts, loaded signal timing, reset/address sequence and power-off/backfeed pending.'),
           (20,403,'R1001..R1025 are source-damping starting values; place appropriately near drivers. No external hot-plug or EMC rating established.')]
    for x,y,text in notes:tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(text)}"))'))
    from display_rgb_damping import annotate
    annotate(tree)
    path.write_text(dumps(tree)+'\n');print(path)
if __name__=='__main__':build()
