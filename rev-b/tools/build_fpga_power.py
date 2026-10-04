#!/usr/bin/env python3
"""Generate fixed FPGA core power and supervised auxiliary/I/O sequencing.

Run after build_audio.py, then build_project.py. This is an engineering draft.
"""
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


def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL, "kestrel/rev-b/fpga-power/"+s))
def node(s): return sx.loads(s)
def prop(item, key): return next(x for x in item if isinstance(x,list) and x and x[0]==S(key))


def build():
    folder = ROOT/"electrical"
    effect = '(effects (font (size 1.27 1.27)))'
    pins = [(1,"VIN","power_in",-8,6,0),(2,"VIN","passive",-8,4,0),
            (3,"ON","input",-8,0,0),(4,"VBIAS","power_in",-2,10,270),
            (5,"GND","power_in",-2,-10,90),(6,"CT","passive",2,-10,90),
            (7,"VOUT","power_out",8,6,180),(8,"VOUT","passive",8,4,180),
            (9,"EP","power_in",0,-10,90)]
    body = ''.join(f'(pin {kind} line (at {x*GRID} {y*GRID} {a}) (length 2.54) '
                   f'(name "{name}" {effect}) (number "{n}" {effect}))'
                   for n,name,kind,x,y,a in pins)
    lib = node('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '
        '(symbol "TPS22965" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) '
        f'(property "Reference" "U" (at -5.08 15.24 0) {effect}) '
        f'(property "Value" "TPS22965" (at -5.08 12.7 0) {effect}) '
        '(property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps22965.pdf" (at 0 0 0) '
        '(effects (font (size 1.27 1.27)) (hide yes))) '
        '(symbol "TPS22965_0_1" (rectangle (start -7.62 10.16) (end 7.62 -10.16) '
        '(stroke (width 0.254) (type default)) (fill (type background)))) '
        f'(symbol "TPS22965_1_1" {body})))')
    supervisor_pins = [(1,"ENABLE","input",-8,4,0),(2,"GND","power_in",0,-10,90),
                       (3,"SENSE","input",-8,0,0),(4,"SENSE_OUT","open_collector",8,0,180),
                       (5,"CT","passive",3,-10,90),(6,"VCC","power_in",0,10,270)]
    supervisor_body = ''.join(f'(pin {kind} line (at {x*GRID} {y*GRID} {a}) (length 2.54) '
                              f'(name "{name}" (effects (font (size 0.9 0.9)))) (number "{n}" {effect}))'
                              for n,name,kind,x,y,a in supervisor_pins)
    lib.append(node('(symbol "TPS3897A" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) '
        f'(property "Reference" "U" (at -5.08 15.24 0) {effect}) '
        f'(property "Value" "TPS3897A" (at -5.08 12.7 0) {effect}) '
        '(property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps3895.pdf" (at 0 0 0) '
        '(effects (font (size 1.27 1.27)) (hide yes))) '
        '(symbol "TPS3897A_0_1" (rectangle (start -7.62 10.16) (end 7.62 -10.16) '
        '(stroke (width 0.254) (type default)) (fill (type background)))) '
        f'(symbol "TPS3897A_1_1" {supervisor_body}))'))
    (folder/"KestrelPower.kicad_sym").write_text(dumps(lib)+"\n")
    table=sx.loads((folder/"sym-lib-table").read_text())
    table[:]=[x for x in table if not (isinstance(x,list) and x and x[0]==S("lib") and prop(x,"name")[1]=="KestrelPower")]
    table.append(node('(lib (name "KestrelPower") (type "KiCad") (uri "${KIPRJMOD}/KestrelPower.kicad_sym") (options "") (descr "Checked FPGA power switch pinout"))'))
    (folder/"sym-lib-table").write_text(dumps(table)+"\n")
    footprint=sx.loads(Path('/usr/share/kicad/footprints/Package_DFN_QFN.pretty/DFN-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm.kicad_mod').read_text())
    footprint[1]="TPS22965_DSG8_2x2"
    for item in footprint:
        if not isinstance(item,list) or not item: continue
        if item[0]==S("descr"): item[1]="TI TPS22965 DSG0008A metal lands; KiCad body/courtyard/EP paste/model; assembler stencil review pending"
        if item[0]==S("property") and item[1]=="Value": item[2]=footprint[1]
        if item[0]==S("pad") and str(item[1]) in map(str,range(1,9)):
            pos=prop(item,"at"); pos[1]=(-.95 if float(pos[1])<0 else .95)
            prop(item,"size")[1:]=[.5,.25]
            prop(item,"roundrect_rratio")[1]=.2
    pretty=folder/"KestrelPower.pretty"; pretty.mkdir(exist_ok=True)
    (pretty/(footprint[1]+".kicad_mod")).write_text(dumps(footprint)+"\n")
    fp_table=sx.loads((folder/"fp-lib-table").read_text())
    fp_table[:]=[x for x in fp_table if not (isinstance(x,list) and x and x[0]==S("lib") and prop(x,"name")[1]=="KestrelPower")]
    fp_table.append(node('(lib (name "KestrelPower") (type "KiCad") (uri "${KIPRJMOD}/KestrelPower.pretty") (options "") (descr "TI power switch lands"))'))
    (folder/"fp-lib-table").write_text(dumps(fp_table)+"\n")
    out=folder/"kestrel-revb-fpga-power.kicad_sch"
    out.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") '
                   f'(uuid "{uid("sheet")}") (paper "A3") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    cap="Capacitor_SMD:C_0603_1608Metric"; bulk="Capacitor_SMD:C_1210_3225Metric"; res="Resistor_SMD:R_0603_1608Metric"
    parts=[
      ("U301","Regulator_Switching:TLV62569DBV","TLV62569DBVR","Package_TO_SOT_SMD:SOT-23-5",65,55,0,{"1":"+5V_DIG","2":"GND","3":"CORE_SW","4":"+5V_DIG","5":"CORE_FB"}),
      ("L301","Device:L","2.2uH / shielded / Isat >=3.5A","",95,55,90,{"1":"CORE_SW","2":"+1V0_FPGA"}),
      ("C301","Device:C","10uF / 16V X7R",bulk,35,70,0,{"1":"+5V_DIG","2":"GND"}),
      ("C302","Device:C","22uF / 16V X7R",bulk,105,75,0,{"1":"+1V0_FPGA","2":"GND"}),
      ("C303","Device:C","22uF / 16V X7R",bulk,120,75,0,{"1":"+1V0_FPGA","2":"GND"}),
      ("R301","Device:R","68.1k / 0.1%",res,150,62,0,{"1":"+1V0_FPGA","2":"CORE_FB"}),
      ("R302","Device:R","100k / 0.1%",res,150,80,0,{"1":"CORE_FB","2":"GND"}),
      ("C304","Device:C","6.8pF / C0G",cap,135,62,0,{"1":"+1V0_FPGA","2":"CORE_FB"}),
      ("U302","KestrelPower:TPS3897A","TPS3897ADRYR","Package_SON:Texas_USON-6_1x1.45mm_P0.5mm_SMD",65,145,0,{"1":"+3V3_D","2":"GND","3":"CORE_SENSE","4":"FPGA_IO_EN","5":"CORE_DELAY","6":"+3V3_D"}),
      ("R303","Device:R","9.31k / 0.1%",res,35,134,0,{"1":"+1V0_FPGA","2":"CORE_SENSE"}),
      ("R304","Device:R","10k / 0.1%",res,35,158,0,{"1":"CORE_SENSE","2":"GND"}),
      ("R305","Device:R","10k / 1%",res,100,140,0,{"1":"+3V3_D","2":"FPGA_IO_EN"}),
      ("R306","Device:R","10k / 1%",res,100,160,0,{"1":"FPGA_IO_EN","2":"GND"}),
      ("C305","Device:C","1nF / C0G",cap,50,175,0,{"1":"CORE_SENSE","2":"GND"}),
      ("C306","Device:C","100nF / 16V",cap,80,175,0,{"1":"+3V3_D","2":"GND"}),
      ("U303","KestrelPower:TPS22965","TPS22965DSGR","KestrelPower:TPS22965_DSG8_2x2",195,145,0,{"1":"+3V3_D","2":"+3V3_D","3":"FPGA_IO_EN","4":"+5V_DIG","5":"GND","6":"IO_RAMP","7":"+3V3_FPGA","8":"+3V3_FPGA","9":"GND"}),
      ("C307","Device:C","10uF / 16V X7R",bulk,170,175,0,{"1":"+3V3_D","2":"GND"}),
      ("C308","Device:C","100nF / 16V",cap,185,175,0,{"1":"+5V_DIG","2":"GND"}),
      ("C309","Device:C","470pF / 25V C0G",cap,210,175,0,{"1":"IO_RAMP","2":"GND"}),
      ("C310","Device:C","4.7uF / 16V X7R",bulk,225,175,0,{"1":"+3V3_FPGA","2":"GND"}),
      ("C311","Device:C","4.7nF / 5% / 25V C0G",cap,65,190,0,{"1":"CORE_DELAY","2":"GND"}),
      ("#FLG0301","power:PWR_FLAG","PWR_FLAG","",115,48,0,{"1":"+1V0_FPGA"}),
    ]
    loader=DynamicSymbolLoader(folder)
    for ref,lib,value,foot,x,y,angle,nets in parts:
        family,name=lib.split(":"); loader.inject_symbol_into_schematic(out,family,name)
        assert loader.create_component_instance(out,family,name,ref,value,foot,x*GRID,y*GRID,angle=angle),ref
    tree=sx.loads(out.read_text())
    definitions={str(x[1]):x for x in prop(tree,"lib_symbols")[1:]}
    boundary={"+5V_DIG":"input","+3V3_D":"input","GND":"bidirectional","+1V0_FPGA":"output","+3V3_FPGA":"output"}
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
                tree.append(node(f'({label_type} "{net}" {shape} (at {ex} {ey} {90 if vy else 0}) (effects (font (size 0.9 0.9)) (justify {"right" if vx<0 else "left"} bottom)) (uuid "{uid(ref+num+"label")}"))'))
    for x,y,t in [(20,18,"FPGA FIXED CORE / SEQUENCED AUXILIARY AND I/O - ENGINEERING DRAFT"),
      (20,26,"TLV62569DBVR from 5 V; nominal core 1.0086 V. Never connect this rail to ESP32-P4 variable HP core."),
      (20,117,"Chosen core-first qualification; VCCX/IO share switched rail. UG206-1.9.3E: core first for >10 ms rail ramps."),
      (20,125,"FPGA_IO_EN uses equal 10k pullup/pulldown for ~1.65 V HIGH; assert only after core sense release and delay."),
      (20,255,"TPS22965 CT 470 pF / 25 V gives about 0.65 ms typical 3.3 V rise at 5 V bias; not a guaranteed timing bound."),
      (20,263,"FPGA VCCX, all banks, flash and oscillator use switched +3V3_FPGA; per-pin and PLL bypass are on the bare FPGA sheet."),
      (20,271,"Verify load/ramp/dropout, low-power reset, shutdown and MCU/JTAG backfeed. Falling hysteresis has no guaranteed bound.")]:
        tree.append(node(f'(text "{t}" (at {x} {y} 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid "{uid(t)}"))'))
    from power_inductors import annotate
    annotate(tree)
    out.write_text(dumps(tree)+"\n"); print(out)


if __name__=="__main__": build()
