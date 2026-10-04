#!/usr/bin/env python3
"""Generate ESP32-P4 v3 controlled HP regulator; circuit qualification pending."""
import math
import sys
import uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27
sys.path.insert(0,str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps
S=sx.Symbol
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL,'kestrel/rev-b/mcu-power/'+s))
def node(s): return sx.loads(s)
def prop(item,key): return next(x for x in item if isinstance(x,list) and x and x[0]==S(key))
def build():
    folder=ROOT/'electrical'
    out=folder/'kestrel-revb-mcu-power.kicad_sch'
    out.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") (uuid "{uid("sheet")}") (paper "A4") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    cap='Capacitor_SMD:C_0603_1608Metric'; bulk='Capacitor_SMD:C_1210_3225Metric'; res='Resistor_SMD:R_0603_1608Metric'
    parts=[
      ('U601','Regulator_Switching:TLV62569DBV','TLV62569DBVR','Package_TO_SOT_SMD:SOT-23-5',65,55,0,{'1':'MCU_EN_DCDC','2':'GND','3':'MCU_HP_SW','4':'+3V3_D','5':'MCU_FB_DCDC'}),
      ('L601','Device:L','2.2uH / shielded / Isat >=3.5A','',100,55,90,{'1':'MCU_HP_SW','2':'ESP_VDD_HP'}),
      ('C601','Device:C','4.7uF / 16V X7R',bulk,30,75,0,{'1':'+3V3_D','2':'GND'}),
      ('C602','Device:C','100nF / 16V X7R',cap,45,75,0,{'1':'+3V3_D','2':'GND'}),
      ('C603','Device:C','22uF / 16V X7R',bulk,100,85,0,{'1':'ESP_VDD_HP','2':'GND'}),
      ('C604','Device:C','22uF / 16V X7R',bulk,115,85,0,{'1':'ESP_VDD_HP','2':'GND'}),
      ('R601','Device:R','499k / 1%',res,145,65,0,{'1':'ESP_VDD_HP','2':'MCU_FB_DCDC'}),
      ('R602','Device:R','499k / 1%',res,145,90,0,{'1':'MCU_FB_DCDC','2':'GND'}),
      ('C605','Device:C','22pF / 25V C0G',cap,165,65,0,{'1':'ESP_VDD_HP','2':'MCU_FB_DCDC'}),
      ('#FLG0601','power:PWR_FLAG','PWR_FLAG','',190,85,0,{'1':'ESP_VDD_HP'}),
    ]
    loader=DynamicSymbolLoader(folder)
    for ref,lib,value,foot,x,y,angle,nets in parts:
        family,name=lib.split(":"); loader.inject_symbol_into_schematic(out,family,name)
        assert loader.create_component_instance(out,family,name,ref,value,foot,x*GRID,y*GRID,angle=angle),ref
    tree=sx.loads(out.read_text())
    definitions={str(x[1]):x for x in prop(tree,"lib_symbols")[1:]}
    boundary={"+3V3_D":"input","GND":"bidirectional","ESP_VDD_HP":"output","MCU_EN_DCDC":"input","MCU_FB_DCDC":"bidirectional"}
    seen=set()
    for inst in tree:
        if not isinstance(inst,list) or not inst or inst[0]!=S("symbol"): continue
        ref=next(x[2] for x in inst if isinstance(x,list) and x and x[0]==S("property") and x[1]=="Reference")
        _,lib,value,foot,x,y,angle,nets=next(p for p in parts if p[0]==ref)
        for field in inst:
            if not isinstance(field,list) or not field: continue
            if field[0]==S("uuid"): field[1]=uid(ref)
            if field[0]==S("pin"): prop(field,"uuid")[1]=uid(ref+"pin"+str(field[1]))
            if field[0]==S("property") and field[1] in ("Reference","Value") and not ref.startswith("#"):
                is_ref=field[1]=="Reference"
                if not is_ref and ref.startswith(("R","C","L")): field[2]=value.split(" / ")[0]
                fx,fy=(x-8,y-(28 if is_ref else 26)) if ref.startswith("U") else ((x-3,y-(6 if is_ref else 4)) if angle==90 else (x+3,y+(-1 if is_ref else 1)))
                prop(field,"at")[1:]=[round(fx*GRID,2),round(fy*GRID,2),0]
                prop(field,"effects")[1:]=node('(effects (font (size 0.9 0.9)) (justify left))')[1:]
        if ref.startswith('#'):
            for field in inst:
                if isinstance(field,list) and field[:2]==[S('property'),'Value']:
                    prop(field,'effects').append(node('(hide yes)'))
        if ref.startswith(("R","C","L")):
            inst.append(node(f'(property "Rating" "{value}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1.27 1.27)) (hide yes)))'))
        symbol=definitions[lib]
        ext=next((z[1] for z in symbol if isinstance(z,list) and z and z[0]==S("extends")),None)
        if ext: symbol=definitions[lib.split(":")[0]+":"+ext]
        for unit in symbol:
            if not isinstance(unit,list) or not unit or unit[0]!=S("symbol"): continue
            for pin in unit:
                if not isinstance(pin,list) or not pin or pin[0]!=S("pin"): continue
                num=str(prop(pin,"number")[1]); net=nets[num]
                px,py,a=prop(pin,"at")[1:]; rad=math.radians(angle)
                px,py=round(x*GRID+px*math.cos(rad)-py*math.sin(rad),2),round(y*GRID-px*math.sin(rad)-py*math.cos(rad),2)
                if net is None:
                    tree.append(node(f'(no_connect (at {px} {py}) (uuid "{uid(ref+num+"nc")}"))')); continue
                vx,vy={0:(-5.08,0),90:(0,5.08),180:(5.08,0),270:(0,-5.08)}[(a+angle)%360]
                ex,ey=round(px+vx,2),round(py+vy,2)
                tree.append(node(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid "{uid(ref+num+"wire")}"))'))
                label_type="hierarchical_label" if net in boundary and net not in seen else "label"
                seen.add(net); shape=f'(shape {boundary[net]})' if label_type=="hierarchical_label" else ""
                tree.append(node(f'({label_type} "{net}" {shape} (at {ex} {ey} 0) (effects (font (size 0.9 0.9)) (justify {"right" if vx<0 else "left"} bottom)) (uuid "{uid(ref+num+"label")}"))'))
    notes=[(20,18,'ESP32-P4 V3 CONTROLLED HP CORE SUPPLY - ENGINEERING DRAFT'),
           (20,26,'EN_DCDC and FB_DCDC connect to P4 pins 79 and 78. Not a fixed FPGA core supply.'),
           (20,145,'Populate both 499k resistors and 22pF for v3.x. P4 controls HP voltage and enable internally.'),
           (20,153,'2.2uH + 2x22uF covers TI low-voltage LC recommendation; effective capacitance/load/loop validation pending.'),
           (20,161,'Place regulator beside P4. Verify 0.99-1.30V HP behavior, boot/sleep and source current in hardware.'),
           (20,169,'MCU controls/HP are connected. PWR_FLAG declares regulator source, not qualified voltage or operation.')]
    for x,y,t in notes:
        tree.append(node(f'(text "{t}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(t)}"))'))
    from power_inductors import annotate
    annotate(tree)
    out.write_text(dumps(tree)+'\n'); print(out)
if __name__=='__main__': build()
