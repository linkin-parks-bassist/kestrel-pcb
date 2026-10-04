#!/usr/bin/env python3
"""Generate two active-low panel-mount footswitch inputs; engineering draft.

Run after MCU/backlight generation, before build_project.py.
"""
import json
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27
sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps

S = sx.Symbol
def node(text): return sx.loads(text)
def child(e, key): return next(x for x in e if isinstance(x,list) and x and x[0]==S(key))
def uid(text): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'kestrel/rev-b/footswitch/'+text))


def build():
    folder=ROOT/'electrical';path=folder/'kestrel-revb-footswitch.kicad_sch'
    path.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") (uuid "{uid("sheet")}") (paper "A3") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    res='Resistor_SMD:R_0603_1608Metric';cap='Capacitor_SMD:C_0603_1608Metric'
    parts=[]
    def add(ref,lib,value,foot,x,y,nets,angle=0,unit=1):
        parts.append((ref,lib,value,foot,round(x/GRID),round(y/GRID),angle,nets,unit))
    for i,dy in enumerate((0,135)):
        raw=f'FOOT_RAW_{i}';filt=f'FOOT_RC_{i}';out=f'FOOT_BUF_{i}';mcu=f'MCU_FOOT{i}_N'
        add(f'J{1101+i}','Connector_Generic:Conn_01x02','FOOT WIRE / 1SIGNAL 2GND',
            'Connector_Wire:SolderWire-0.127sqmm_1x02_P3.7mm_D0.48mm_OD1mm_Relief2x',40,55+dy,{'1':raw,'2':'GND'})
        add(f'SW{1101+i}','Switch:SW_Push','SWFS0013 / silent momentary NO / candidate','',40,110+dy,{'1':raw,'2':'GND'})
        add(f'U{1101+i}','74xGxx:74LVC1G17','SN74LVC1G17DCKR',
            'Package_TO_SOT_SMD:Texas_R-PDSO-G5_DCK-5',165,65+dy,{'1':None,'2':filt,'3':'GND','4':out,'5':'+3V3_D'})
        add(f'R{1101+3*i}','Device:R','1k / 1% / wire input series',res,100,45+dy,{'1':raw,'2':filt},angle=90)
        add(f'R{1102+3*i}','Device:R','10k / 1% / input pullup',res,245,45+dy,{'1':'+3V3_D','2':filt})
        add(f'R{1103+3*i}','Device:R','33ohm / 1% / GPIO source damping',res,300,65+dy,{'1':out,'2':mcu},angle=90)
        add(f'C{1101+2*i}','Device:C','100nF / 16V X7R / RC filter / effective 80..120nF',cap,100,100+dy,{'1':filt,'2':'GND'})
        add(f'C{1102+2*i}','Device:C','100nF / 16V X7R / buffer bypass',cap,245,100+dy,{'1':'+3V3_D','2':'GND'})
        add(f'D{1101+i}','Device:D_TVS','PESD5V0U1BA,115','Diode_SMD:D_SOD-323',320,110+dy,{'1':raw,'2':'GND'})
    boundary={'+3V3_D':'input','GND':'bidirectional','MCU_FOOT0_N':'output','MCU_FOOT1_N':'output'}
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
                    xx,yy=x*GRID-20,y*GRID-20+(0 if is_ref else 2)
                    if not is_ref:e[2]='FOOT WIRE: 1SIGNAL 2GND'
                elif ref.startswith('U'):xx,yy=x*GRID-15,y*GRID-20+(0 if is_ref else 2)
                elif ref.startswith('SW'):xx,yy=x*GRID-20,y*GRID-10+(0 if is_ref else 2)
                else:xx,yy=(x+3)*GRID,(y+(-1 if is_ref else 1))*GRID
                if angle==90:xx,yy=x*GRID-3,y*GRID-(8 if is_ref else 6)
                if ref.startswith('D'):xx,yy=x*GRID-4,y*GRID-(8 if is_ref else 6)
                child(e,'at')[1:]=[round(xx,2),round(yy,2),90 if angle==90 else 0]
                child(e,'effects')[1:]=node('(effects (font (size 0.8 0.8)) (justify left))')[1:]
        if ref.startswith(('R','C','L')):
            inst.append(node(f'(property "Rating" "{val}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
        if ref.startswith('SW'):
            child(inst,'on_board')[1]=S('no')
            inst.append(node(f'(property "Assembly" "Panel mounted; 2 wires to J1101/J1102; no board footprint; foot loads supported by enclosure; supplier candidate to qualify" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
            next(e for e in inst if isinstance(e,list) and e[:2]==[S('property'),'Datasheet'])[2]='https://www.pedalpartsaustralia.com/index.php?main_page=product_info&products_id=1203'
        if ref.startswith('D'):
            next(e for e in inst if isinstance(e,list) and e[:2]==[S('property'),'Datasheet'])[2]='https://assets.nexperia.com/documents/data-sheet/PESD5V0U1BA.pdf'
    notes=[(20,15,'TWO PANEL-MOUNT MOMENTARY FOOTSWITCHES - ACTIVE LOW - ENGINEERING DRAFT'),
           (20,260,'GPIO20 pad22 = left / GPIO21 pad23 = right. Switches close signal to ground; mount loads on enclosure, not PCB.'),
           (20,267,'10k pullup / 1k series / 100nF RC / Schmitt buffer. Short interference filtering is not complete contact debounce.'),
           (20,274,'SWFS0013 is a local A$5 silent SPST candidate: manufacturer/current rating, dry-contact life and exact geometry unqualified.'),
           (20,281,'PESD wire shunts do not establish system ESD/fault rating. Qualify residual stress, firmware edges, wiring and physical loads.')]
    for x,y,text in notes:tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(text)}"))'))
    path.write_text(dumps(tree)+'\n');print(path)
if __name__=='__main__':build()
