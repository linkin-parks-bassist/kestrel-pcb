#!/usr/bin/env python3
"""One dimension model produces the enclosure, fit volumes and PCB boundary.

Run with the CadQuery environment. Run --pcb with KiCad's system Python.
All coordinates are mm: origin at enclosure floor centre, foot end is -Y.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rounded_box(cq, w, d, h, z, radius):
    return (cq.Workplane("XY").box(w, d, h, centered=(True, True, False))
            .edges("|Z").fillet(radius).translate((0, 0, z)))


def cylinder(cq, x, y, z, radius, height):
    return cq.Workplane("XY").center(x, y).circle(radius).extrude(height).translate((0, 0, z))


def build_cad(p, out):
    import cadquery as cq
    c, b, d, f, a = (p[k] for k in ("case", "pcb", "display", "footswitches", "audio_jacks"))
    w, depth, height, wall = (c[k] for k in ("width", "depth", "height", "wall"))
    shell = rounded_box(cq, w, depth, height-wall, wall, c["corner_radius"])
    cavity = rounded_box(cq, w-2*wall, depth-2*wall, height-2*wall+0.1, wall-0.1, c["corner_radius"]-wall)
    shell = shell.cut(cavity)
    window = cq.Workplane("XY").center(*d["centre"]).rect(d["window_width"], d["window_depth"]).extrude(height+1)
    shell = shell.cut(window)
    for x, y in f["centres"]:
        shell = shell.cut(cylinder(cq, x, y, 0, f["hole_diameter"]/2, height+1))
    # Left/right audio holes are coaxial with underside jack envelope volumes.
    hole = cq.Workplane("YZ").center(a["y"], a["axis_z"]).circle(a["hole_diameter"]/2).extrude(w, both=True)
    shell = shell.cut(hole)
    dc = p["dc_jack"]
    hole = cq.Workplane("XZ").center(0, dc["axis_z"]).circle(dc["hole_diameter"]/2).extrude(depth, both=True)
    # Restrict rear openings to the rear wall (not the foot end).
    rear = cq.Workplane("XY").box(w, 2*wall+2, height+2).translate((0, depth/2, height/2))
    shell = shell.cut(hole.intersect(rear))
    u = p["usb"]
    hole = cq.Workplane("XZ").center(u["x"], u["axis_z"]).rect(u["opening_width"], u["opening_height"]).extrude(depth, both=True)
    shell = shell.cut(hole.intersect(rear))
    lid = rounded_box(cq, w, depth, wall, 0, c["corner_radius"])
    screws = p["lid_screws"]
    for x, y in screws["centres"]:
        boss = cylinder(cq, x, y, wall, screws["boss_diameter"]/2, height-2*wall)
        bore = cylinder(cq, x, y, 0, screws["hole_diameter"]/2, height+1)
        shell = shell.union(boss).cut(bore)
        lid = lid.cut(bore)
    # PCB supports are on the removable base; through bores are provisional M3.
    for x, y in b["mounts"]:
        stand = cylinder(cq, x, y, wall, 3.5, b["bottom_z"]-wall)
        bore = cylinder(cq, x, y, 0, b["hole_diameter"]/2, b["bottom_z"]+1)
        lid = lid.union(stand).cut(bore)
    pcb = rounded_box(cq, b["width"], b["depth"], b["thickness"], b["bottom_z"], 3)
    for x, y in b["mounts"]:
        pcb = pcb.cut(cylinder(cq, x, y, b["bottom_z"]-1, b["hole_diameter"]/2, b["thickness"]+2))
    display = cq.Workplane("XY").box(d["body_width"], d["body_depth"], d["body_thickness"]).translate((*d["centre"], d["top_z"]-d["body_thickness"]/2))
    assembly = cq.Assembly(name="Kestrel_RevB_packaging_study")
    assembly.add(shell, name="upper_shell", color=cq.Color(0.14, 0.16, 0.19, 0.55))
    assembly.add(lid, name="removable_base", color=cq.Color(0.25, 0.27, 0.30))
    assembly.add(pcb, name="PCB_boundary_only", color=cq.Color(0.07, 0.35, 0.24))
    assembly.add(display, name="display_envelope_REFERENCE", color=cq.Color(0.1, 0.4, 0.65, 0.7))
    volumes = {"shell": shell.val(), "base": lid.val(), "pcb": pcb.val(), "display_envelope": display.val()}
    for i, (x,y) in enumerate(f["centres"]):
        body = cylinder(cq, x,y,height-wall-f["body_depth"], f["body_diameter"]/2, f["body_depth"])
        actuator = cylinder(cq,x,y,height-wall,f["hole_diameter"]/2,13)
        assembly.add(body.union(actuator), name=f"switch_{i+1}_envelope_UNSELECTED", color=cq.Color(0.65,0.65,0.67))
        volumes[f"switch_{i+1}_body"] = body.val()
    for side, sign in (("input",-1),("output",1)):
        x = sign*(w/2-wall-a["body_length"]/2)
        jack = cq.Workplane("XY").box(a["body_length"],a["body_width"],a["body_height"]).translate((x,a["y"],a["axis_z"]))
        assembly.add(jack,name=f"{side}_jack_envelope_UNVERIFIED",color=cq.Color(0.3,0.3,0.3))
        volumes[f"{side}_jack"] = jack.val()
    for name, solid in volumes.items():
        if not solid.isValid():
            raise ValueError(f"Invalid BREP: {name}")
    # Intersections of reference envelopes are measured, not ignored.
    checks = []
    names = list(volumes)
    for i, name in enumerate(names):
        for other in names[i+1:]:
            volume = volumes[name].intersect(volumes[other]).Volume()
            checks.append({"a":name,"b":other,"intersection_mm3":round(volume,6)})
    report = {"status":p["status"],"solids_valid":True,"intersections":checks,
              "limits":["Display, switch and jack bodies are unverified envelopes.","PCB has no electrical components or copper.","Fasteners, display retention, FPC bend and cable paths are not yet validated."]}
    (out/"fit-report.json").write_text(json.dumps(report,indent=2)+"\n")
    assembly.export(str(out/"packaging-study.step"))
    for name,part in (("upper-shell",shell),("base",lid),("pcb-boundary",pcb)):
        cq.exporters.export(part,str(out/f"{name}.step"))
        cq.exporters.export(part,str(out/f"{name}.stl"))
    cq.exporters.export(shell,str(out/"upper-shell.svg"),opt={"width":900,"height":750,"projectionDir":(1,-1,1),"showHidden":False})
    print('Valid solids exported; intersection report:', out/'fit-report.json')


def build_pcb(p, out):
    import pcbnew
    b = p["pcb"]
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    x0,y0 = 100-b["width"]/2,100-b["depth"]/2
    pts = [(x0,y0),(x0+b["width"],y0),(x0+b["width"],y0+b["depth"]),(x0,y0+b["depth"])]
    # Rounded rectangle agrees with the CAD PCB (radius 3 mm).
    radius=3
    corners=[(x0+radius,y0+radius),(x0+b["width"]-radius,y0+radius),(x0+b["width"]-radius,y0+b["depth"]-radius),(x0+radius,y0+b["depth"]-radius)]
    def point(x,y): return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
    def line(start,end):
        s=pcbnew.PCB_SHAPE();s.SetShape(pcbnew.SHAPE_T_SEGMENT);s.SetStart(point(*start));s.SetEnd(point(*end));s.SetLayer(pcbnew.Edge_Cuts);s.SetWidth(pcbnew.FromMM(.05));board.Add(s)
    line((x0+radius,y0),(x0+b["width"]-radius,y0))
    line((x0+b["width"],y0+radius),(x0+b["width"],y0+b["depth"]-radius))
    line((x0+b["width"]-radius,y0+b["depth"]),(x0+radius,y0+b["depth"]))
    line((x0,y0+b["depth"]-radius),(x0,y0+radius))
    import math
    for (cx,cy),angles in zip(corners,[(180,225,270),(270,315,360),(0,45,90),(90,135,180)]):
        points=[point(cx+radius*math.cos(math.radians(t)),cy+radius*math.sin(math.radians(t))) for t in angles]
        arc=pcbnew.PCB_SHAPE();arc.SetShape(pcbnew.SHAPE_T_ARC);arc.SetArcGeometry(*points);arc.SetLayer(pcbnew.Edge_Cuts);arc.SetWidth(pcbnew.FromMM(.05));board.Add(arc)
    for i,(x,y) in enumerate(b["mounts"],1):
        fp=pcbnew.FootprintLoad('/usr/share/kicad/footprints/MountingHole.pretty','MountingHole_3.2mm_M3')
        fp.SetReference(f'H{i}');fp.SetPosition(point(100+x,100-y));board.Add(fp)
    note=pcbnew.PCB_TEXT(board);note.SetText('REV B PACKAGING STUDY - NO ELECTRICAL DESIGN');note.SetPosition(point(100,100));note.SetLayer(pcbnew.Dwgs_User);note.SetTextSize(point(1.5,1.5));board.Add(note)
    pcbnew.SaveBoard(str(out/'kestrel-revb-boundary.kicad_pcb'),board)
    print('PCB boundary saved; no electrical content claimed')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pcb',action='store_true');args=parser.parse_args()
    p=json.loads((ROOT/'mechanical/dimensions.json').read_text());out=ROOT/'generated';out.mkdir(exist_ok=True)
    if args.pcb: build_pcb(p,out)
    else: build_cad(p,out)


if __name__=='__main__': main()
