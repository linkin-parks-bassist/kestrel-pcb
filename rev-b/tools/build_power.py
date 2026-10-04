#!/usr/bin/env python3
"""Generate the first integrated power sheet using the installed KiCad libraries.

Run in the KiCad MCP venv. The schematic is an incomplete engineering draft;
the input protection and FPGA core supplies are on separate sheets.
"""
import argparse
import copy
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "kestrel/rev-b/power/" + name))


def build(mcp_dir):
    sys.path.insert(0, str(mcp_dir))
    import sexpdata as sx
    from commands.dynamic_symbol_loader import DynamicSymbolLoader
    from utils.sexpr_format import dumps

    out = ROOT / "electrical" / "kestrel-revb-power.kicad_sch"
    out.parent.mkdir(exist_ok=True)
    out.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") '
                   f'(generator_version "10.0") (uuid "{uid("sheet")}") '
                   '(paper "A3") (lib_symbols) '
                   '(sheet_instances (path "/" (page "1"))))\n')
    loader = DynamicSymbolLoader(out.parent)
    resistor = "Resistor_SMD:R_0603_1608Metric"
    capacitor = "Capacitor_SMD:C_0603_1608Metric"
    bulk = "Capacitor_SMD:C_1210_3225Metric"
    tp = "TestPoint:TestPoint_Pad_D1.0mm"
    # Positions are in 50 mil grid units. Values follow TI SLVSDG6C Fig 7-1.
    parts = [
        ("U101", "Regulator_Switching:TPS54302", "TPS54302DDCR", "Package_TO_SOT_SMD:SOT-23-6", 80, 60, 0),
        ("L101", "Device:L", "10uH / Isat >= 4.3A / shielded", "", 100, 60, 90),
        ("C101", "Device:C", "10uF / 35V X7R", bulk, 42, 66, 0),
        ("C102", "Device:C", "100nF / 25V", capacitor, 52, 66, 0),
        ("C103", "Device:C", "100nF / 25V", capacitor, 92, 54, 90),
        ("C104", "Device:C", "22uF / 25V X7R", bulk, 110, 69, 0),
        ("C105", "Device:C", "22uF / 25V X7R", bulk, 122, 69, 0),
        ("C106", "Device:C", "75pF / C0G", capacitor, 134, 80, 0),
        ("R101", "Device:R", "49.9 / 1%", resistor, 145, 68, 0),
        ("R102", "Device:R", "100k / 1%", resistor, 145, 80, 0),
        ("R103", "Device:R", "13.3k / 1%", resistor, 145, 92, 0),
        ("R104", "Device:R", "511k / 1%", resistor, 65, 50, 0),
        ("R105", "Device:R", "105k / 1%", resistor, 65, 69, 0),
        ("TP101", "Connector:TestPoint", "9V_PROTECTED", tp, 30, 58, 0),
        ("TP102", "Connector:TestPoint", "GND", tp, 30, 76, 0),
        ("TP103", "Connector:TestPoint", "+5V_DIG", tp, 157, 60, 0),
        ("#FLG0101", "power:PWR_FLAG", "PWR_FLAG", "", 42, 58, 0),
        ("#FLG0102", "power:PWR_FLAG", "PWR_FLAG", "", 42, 76, 0),
        ("#FLG0103", "power:PWR_FLAG", "PWR_FLAG", "", 157, 60, 0),
    ]
    # Second regulator: TI Table 7-2 3.3-V starting values, with a third
    # output capacitor to allow derating before the loop/current review.
    refmap={"U101":"U102","L101":"L102","C101":"C107","C102":"C108",
            "C103":"C109","C104":"C110","C105":"C111","C106":"C112",
            "R101":"R106","R102":"R107","R103":"R108","R104":"R109",
            "R105":"R110","TP103":"TP104","#FLG0103":"#FLG0104"}
    for ref,lib,value,footprint,x,y,angle in list(parts):
        if ref not in refmap: continue
        if ref=="L101": value="6.8uH / Isat >= 4.3A / shielded"
        if ref=="C106": value="47pF / C0G"
        if ref=="R102": value="100k / 0.1%"
        if ref=="R103": value="22.1k / 0.1%"
        if ref=="TP103": value="+3V3_D"
        parts.append((refmap[ref],lib,value,footprint,x,y+80,angle))
    parts.append(("C113","Device:C","22uF / 25V X7R",bulk,42,176,0))
    for ref, lib, value, footprint, x, y, angle in parts:
        library, symbol = lib.split(":")
        loader.inject_symbol_into_schematic(out, library, symbol)
        if not loader.create_component_instance(out, library, symbol, ref, value,
                                                 footprint, x*GRID, y*GRID, angle=angle):
            raise RuntimeError(f"Cannot place {ref}")
    tree = sx.loads(out.read_text())
    S = sx.Symbol

    def parse(s):
        return sx.loads(s)

    def wire(*points):
        for a, b in zip(points, points[1:]):
            x1, y1, x2, y2 = [round(v*GRID, 2) for v in (*a, *b)]
            if a == b:
                continue
            tree.append(parse(f'(wire (pts (xy {x1} {y1}) (xy {x2} {y2})) '
                              f'(stroke (width 0) (type default)) (uuid "{uid(str((a,b)))}"))'))

    def label(name, x, y):
        tree.append(parse(f'(label "{name}" (at {round(x*GRID,2)} {round(y*GRID,2)} 0) '
                          f'(effects (font (size 1.27 1.27)) (justify left bottom)) '
                          f'(uuid "{uid("label"+name+str((x,y)))}"))'))

    def junction(x, y):
        tree.append(parse(f'(junction (at {round(x*GRID,2)} {round(y*GRID,2)}) '
                          f'(diameter 0) (color 0 0 0 0) (uuid "{uid("junction"+str((x,y)))}"))'))

    # Positive input, two input capacitors and separately wired enable divider.
    wire((30,58),(42,58),(52,58),(72,58))
    wire((42,58),(42,63)); wire((52,58),(52,63))
    wire((65,47),(65,44)); label("9V_PROTECTED",65,44)
    wire((65,53),(65,62),(72,62)); wire((65,62),(65,66))
    # All ground branches return to one logical ground; physical return routing
    # must keep switching currents out of analog paths in the PCB.
    wire((30,76),(42,76),(52,76),(65,76),(80,76))
    wire((42,69),(42,76)); wire((52,69),(52,76))
    wire((65,72),(65,76)); wire((80,66),(80,76))
    # BOOT capacitor to SW, never ground.
    wire((88,58),(88,54),(89,54))
    wire((95,54),(95,60)); wire((88,60),(95,60),(97,60))
    # Output filter and feed-forward/feedback network.
    wire((103,60),(110,60),(122,60),(145,60),(157,60))
    wire((110,60),(110,66)); wire((122,60),(122,66))
    wire((145,60),(145,65)); wire((145,71),(145,74),(145,77))
    wire((134,77),(134,74),(145,74))
    wire((145,83),(145,86),(145,89))
    wire((134,83),(134,86),(145,86))
    wire((88,62),(91,62),(91,86),(134,86))
    for x, y in ((110,72),(122,72),(145,95)):
        wire((x,y),(x,y+3)); label("GND",x,y+3)
    label("9V_PROTECTED",30,58); label("GND",30,76); label("+5V_DIG",157,60)
    label("BUCK5_SW",95,60); label("BUCK5_FB",91,86)
    for x,y in ((42,58),(52,58),(42,76),(52,76),(65,76),(65,62),
                (95,60),(110,60),(122,60),(145,60),(145,74),(134,86),(145,86)):
        junction(x,y)
    # Stamp the same connected buck topology below the 5-V stage. Shared
    # input/ground labels connect electrically, but SW/FB/output nets differ.
    for element in list(tree):
        if not isinstance(element,list) or not element or element[0] not in (S("wire"),S("label"),S("junction")): continue
        duplicate=copy.deepcopy(element)
        def translate(item):
            if not isinstance(item,list) or not item: return
            if item[0] in (S("at"),S("xy")): item[2]=round(float(item[2])+80*GRID,2)
            elif item[0]==S("uuid"): item[1]=uid("3v3"+str(item[1]))
            else:
                for sub in item: translate(sub)
        translate(duplicate)
        if duplicate[0]==S("label"):
            duplicate[1]={"+5V_DIG":"+3V3_D","BUCK5_SW":"BUCK3V3_SW","BUCK5_FB":"BUCK3V3_FB"}.get(duplicate[1],duplicate[1])
        tree.append(duplicate)
    wire((42,173),(42,170)); label("+3V3_D",42,170)
    wire((42,179),(42,182)); label("GND",42,182)
    notes = [
        (25,25,"KESTREL REV B - ONBOARD 5 V / 3.3 V BUCKS - ENGINEERING DRAFT"),
        (25,31,"Nominal 9 V input AFTER protection; input circuit is on its own sheet. Load/ripple/thermal validation pending."),
        (25,37,"TI TPS54302 SLVSDG6C Fig 7-1 starting topology; current/thermal/noise budget pending."),
        (25,111,"5 V is for downstream supplies. Do not tie the FPGA 1 V core to ESP32-P4 HP power."),
        (25,117,"Sunlord inductors selected; load/fault/thermal, effective capacitance and Sydney total cost remain to verify."),
        (25,123,"PCB: minimize VIN-CIN-GND and SW/BOOT loops; sense output after L101; quiet FB return."),
        (25,145,"3.3 V digital: independent buck from protected 9 V; TI Table 7-2 6.8 uH / 100k / 22.1k / 47 pF starting values."),
        (25,249,"3.3 V output C110/C111/C113: 3x22 uF nominal; verify effective total >=40 uF, load steps, ripple and phase margin."),
        (25,255,"3 A is the IC rating, not a verified board capacity. Inductor current, fault behavior, thermal and load budgets pending."),
        (25,261,"FPGA core/IO and input circuits are on separate sheets. MCU HP and screen backlight have separate sheets; power qualification remains unfinished."),
    ]
    for x,y,t in notes:
        tree.append(parse(f'(text "{t}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) '
                          f'(justify left)) (uuid "{uid(t)}"))'))
    # Stable symbol/pin UUIDs keep regenerated files reviewable.
    for item in tree:
        if isinstance(item,list) and item and item[0] == S("symbol"):
            props = {p[1]:p[2] for p in item if isinstance(p,list) and p and p[0] == S("property")}
            ref = props["Reference"]
            spec = next(p for p in parts if p[0] == ref)
            _, lib, full_value, _, gx, gy, angle = spec
            if not ref.startswith("#"):
                # Library defaults rotate some fields into wires. Place short,
                # horizontal values and retain procurement ratings separately.
                for child in item:
                    if not isinstance(child,list) or not child or child[0] != S("property"):
                        continue
                    if child[1] not in ("Reference", "Value"):
                        continue
                    is_ref = child[1] == "Reference"
                    if not is_ref and ref[0] in "RCL":
                        child[2] = full_value.split(" / ")[0]
                    if ref.startswith("U"):
                        fx,fy = gx-5,gy-(10 if is_ref else 8)
                    elif angle == 90:
                        fx,fy = gx-2,gy-(6 if is_ref else 4)
                    elif ref.startswith("TP"):
                        fx,fy = gx-2,gy-(8 if is_ref else 6)
                    else:
                        fx,fy = gx+3,gy+(-1 if is_ref else 1)
                    for field in child:
                        if isinstance(field,list) and field:
                            if field[0] == S("at"):
                                field[1:] = [round(fx*GRID,2),round(fy*GRID,2),angle]
                            elif field[0] == S("effects"):
                                field[1:] = parse('(effects (font (size 0.9 0.9)) (justify left))')[1:]
                if ref[0] in "RCL":
                    item.append(parse(f'(property "Rating" "{full_value}" (at {gx*GRID} {gy*GRID} 0) '
                                      '(effects (font (size 1.27 1.27)) (hide yes)))'))
            for child in item:
                if isinstance(child,list) and child:
                    if child[0] == S("uuid"):
                        child[1] = uid(ref)
                    if child[0] == S("pin"):
                        child[2][1] = uid(ref+"pin"+str(child[1]))
    from power_inductors import annotate
    annotate(tree)
    out.write_text(dumps(tree)+"\n")
    print(out)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--mcp-python-dir",type=Path,
                   default=Path.home()/".local/share/kicad-mcp/python")
    build(p.parse_args().mcp_python_dir)
