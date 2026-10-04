#!/usr/bin/env python3
"""Generate the nominal 9-V centre-negative pedal power input.

Run after audio/FPGA power generators, before build_project.py, in the KiCad
MCP venv. Component protection ratings still require layout/bench qualification.
"""
import copy
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27
sys.path.insert(0, str(Path.home()/".local/share/kicad-mcp/python"))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps
S = sx.Symbol


def uid(name): return str(uuid.uuid5(uuid.NAMESPACE_URL,"kestrel/rev-b/input-power/"+name))
def node(text): return sx.loads(text)
def child(tree,key): return next(x for x in tree if isinstance(x,list) and x and x[0]==S(key))


def build():
    folder = ROOT/"electrical"
    stock = sx.loads(Path('/usr/share/kicad/symbols/Transistor_FET.kicad_sym').read_text())
    symbol = copy.deepcopy(next(x for x in stock if isinstance(x,list) and x and x[0]==S('symbol') and x[1]=='IRF7404'))
    symbol[1] = 'AO4407A'
    for x in symbol:
        if not isinstance(x,list) or not x: continue
        if x[0]==S('symbol'): x[1]=str(x[1]).replace('IRF7404','AO4407A')
        if x[0]==S('property'):
            if x[1]=='Value': x[2]='AO4407A'
            if x[1]=='Datasheet': x[2]='https://www.aosmd.com/sites/default/files/res/datasheets/AO4407A.pdf'
            if x[1]=='Description': x[2]='AOS AO4407A, 30-V P-channel SOIC-8; checked S1/2/3 G4 D5/6/7/8'
    pins = {str(child(p,'number')[1]):str(child(p,'name')[1])
            for u in symbol if isinstance(u,list) and u and u[0]==S('symbol')
            for p in u if isinstance(p,list) and p and p[0]==S('pin')}
    assert pins=={**{str(n):'S' for n in (1,2,3)},'4':'G',**{str(n):'D' for n in (5,6,7,8)}}
    library = node('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor"))')
    library.append(symbol)
    (folder/'KestrelInput.kicad_sym').write_text(dumps(library)+'\n')
    table = sx.loads((folder/'sym-lib-table').read_text())
    table[:]=[x for x in table if not (isinstance(x,list) and x and x[0]==S('lib') and child(x,'name')[1]=='KestrelInput')]
    table.append(node('(lib (name "KestrelInput") (type "KiCad") (uri "${KIPRJMOD}/KestrelInput.kicad_sym") (options "") (descr "Checked pedal input MOSFET"))'))
    (folder/'sym-lib-table').write_text(dumps(table)+'\n')
    out=folder/'kestrel-revb-input-power.kicad_sch'
    out.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") '
                   f'(uuid "{uid("sheet")}") (paper "A4") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    cap='Capacitor_SMD:C_0603_1608Metric'
    testpoint='TestPoint:TestPoint_Pad_D1.0mm'
    parts=[
        ('J401','Connector:Barrel_Jack_Switch','PJ-102AH','Connector_BarrelJack:BarrelJack_CUI_PJ-102AH_Horizontal',30,55,0,{'1':'GND','2':'9V_RAW','3':None}),
        ('F401','Device:Polyfuse','1812L200/16DR','Fuse:Fuse_1812_4532Metric',75,55,90,{'1':'9V_RAW','2':'9V_FUSED'}),
        ('Q401','KestrelInput:AO4407A','AO4407A','Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',110,55,90,{**{str(n):'9V_PROTECTED' for n in (1,2,3)},'4':'INPUT_GATE',**{str(n):'9V_FUSED' for n in (5,6,7,8)}}),
        ('R401','Device:R','100k / 1%','Resistor_SMD:R_0603_1608Metric',110,82,0,{'1':'INPUT_GATE','2':'GND'}),
        ('D401','Device:D_Zener','SMAJ9.0A','Diode_SMD:D_SMA',150,82,270,{'1':'9V_PROTECTED','2':'GND'}),
        ('C401','Device:C','10uF / 35V X7R','Capacitor_SMD:C_1210_3225Metric',182,82,0,{'1':'9V_PROTECTED','2':'GND'}),
        ('C402','Device:C','100nF / 50V X7R',cap,202,82,0,{'1':'9V_PROTECTED','2':'GND'}),
        ('TP401','Connector:TestPoint','9V_RAW',testpoint,75,38,0,{'1':'9V_RAW'}),
        ('TP402','Connector:TestPoint','9V_PROTECTED',testpoint,182,38,0,{'1':'9V_PROTECTED'}),
        ('TP403','Connector:TestPoint','GND',testpoint,202,106,0,{'1':'GND'}),
    ]
    loader=DynamicSymbolLoader(folder)
    for ref,lib,value,foot,x,y,angle,nets in parts:
        family,name=lib.split(':'); loader.inject_symbol_into_schematic(out,family,name)
        assert loader.create_component_instance(out,family,name,ref,value,foot,x*GRID,y*GRID,angle=angle),ref
    tree=sx.loads(out.read_text())
    definitions={str(x[1]):x for x in child(tree,'lib_symbols')[1:]}
    boundary={'9V_PROTECTED':'output','GND':'bidirectional'}; seen=set()
    datasheets={
        'J401':'https://www.sameskydevices.com/product/resource/pj-102ah.pdf',
        'Q401':'https://www.aosmd.com/sites/default/files/res/datasheets/AO4407A.pdf',
        'F401':'https://www.littelfuse.com/~/media/electronics/datasheets/resettable_ptcs/littelfuse_ptc_1812l_datasheet.pdf.pdf',
        'D401':'https://www.littelfuse.com/~/media/electronics/datasheets/tvs_diodes/littelfuse_tvs_diode_smaj_datasheet.pdf.pdf',
    }
    for inst in list(tree):
        if not isinstance(inst,list) or not inst or inst[0]!=S('symbol'): continue
        ref=next(p[2] for p in inst if isinstance(p,list) and p and p[0]==S('property') and p[1]=='Reference')
        _,lib,value,foot,x,y,angle,nets=next(p for p in parts if p[0]==ref)
        for field in inst:
            if not isinstance(field,list) or not field: continue
            if field[0]==S('uuid'): field[1]=uid(ref)
            if field[0]==S('pin'): child(field,'uuid')[1]=uid(ref+'pin'+str(field[1]))
            if field[0]==S('property') and field[1]=='Datasheet' and ref in datasheets:
                field[2]=datasheets[ref]
            if field[0]==S('property') and field[1] in ('Reference','Value'):
                is_ref=field[1]=='Reference'
                if not is_ref and ref.startswith(('R','C')): field[2]=value.split(' / ')[0]
                if ref.startswith(('J','Q')): fx,fy=x-4,y-(16 if is_ref else 14)
                elif angle==90: fx,fy=x-5,y-(8 if is_ref else 6)
                else: fx,fy=x+3,y+(-1 if is_ref else 1)
                child(field,'at')[1:]=[round(fx*GRID,2),round(fy*GRID,2),90 if angle%180==90 else 0]
                child(field,'effects')[1:]=node('(effects (font (size 1 1)) (justify left))')[1:]
        if ref.startswith(('R','C')):
            inst.append(node(f'(property "Rating" "{value}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1.27 1.27)) (hide yes)))'))
        if ref=='J401':
            inst.append(node(f'(property "AssemblySide" "B.Cu / through-hole post assembly" (at {x*GRID} {y*GRID} 0) (effects (font (size 1.27 1.27)) (hide yes)))'))
        emitted=set()
        for unit in definitions[lib]:
            if not isinstance(unit,list) or not unit or unit[0]!=S('symbol'): continue
            for pin in unit:
                if not isinstance(pin,list) or not pin or pin[0]!=S('pin'): continue
                num=str(child(pin,'number')[1]); net=nets[num]
                px,py,a=child(pin,'at')[1:]; rad=math.radians(angle)
                px,py=round(x*GRID+px*math.cos(rad)-py*math.sin(rad),2),round(y*GRID-px*math.sin(rad)-py*math.cos(rad),2)
                if net is None:
                    tree.append(node(f'(no_connect (at {px} {py}) (uuid "{uid(ref+num+"nc")}"))')); continue
                if (px,py,net) in emitted: continue  # Stacked SOIC source/drain pins.
                emitted.add((px,py,net))
                vx,vy={0:(-5.08,0),90:(0,5.08),180:(5.08,0),270:(0,-5.08)}[(a+angle)%360]
                ex,ey=round(px+vx,2),round(py+vy,2)
                tree.append(node(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid "{uid(ref+num+"wire")}"))'))
                kind='hierarchical_label' if net in boundary and net not in seen else 'label'
                seen.add(net); shape=f'(shape {boundary[net]})' if kind=='hierarchical_label' else ''
                tree.append(node(f'({kind} "{net}" {shape} (at {ex} {ey} {90 if vy<0 else 0}) (effects (font (size 1 1)) (justify {"right" if vx<0 else "left"} bottom)) (uuid "{uid(ref+num+"label")}"))'))
    notes=[
        (20,20,'KESTREL REV B - NOMINAL 9 V CENTRE-NEGATIVE INPUT - ENGINEERING DRAFT'),
        (20,27,'PJ-102AH pin1 = centre/GND; pin2 = sleeve/positive; pin3 = sleeve switch, NC. Check plug fit/case datums.'),
        (20,150,'Q401 drain faces fused jack input; source feeds protected rail. Body diode conducts input-to-output on startup.'),
        (20,157,'F401: 2 A hold / 3.5 A trip at 20 C; 16 V rated. Full load, hot derating, inrush and fault coordination pending.'),
        (20,164,'SMAJ9.0A: 9 V standoff, 10-11.1 V breakdown, 15.4 V clamp at 26 A / 10-1000 us / 25 C.'),
        (20,171,'Transient clamp ratings do not establish continuous overvoltage tolerance. Use a regulated nominal 9 V supply.'),
        (20,178,'Place TVS and bypass at entry, with short return to jack ground. Verify overshoot, leakage, ESD and current loops.'),
        (20,185,'Single PMOS does not provide reverse-current isolation for USB/other powered domains. Resolve power-source backfeed.'),
    ]
    for x,y,text in notes:
        tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(text)}"))'))
    out.write_text(dumps(tree)+'\n'); print(out)


if __name__=='__main__': build()
