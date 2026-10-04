#!/usr/bin/env python3
"""Native EP via continuity, paste/drill geometry and tenting check; not thermal qualification."""
import argparse
import json
import math
import pcbnew
from build_mcu_exposed_ground import ROOT, ident, vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    d=json.loads((ROOT/'electrical/mcu-exposed-ground.json').read_text());fp=next(f for f in b.GetFootprints()if f.GetReference()=='U701')
    ep=next(p for p in fp.Pads()if p.GetNumber()=='105');assert ep.GetNetname()=='/GND' and ep.GetPosition()==vec(d['pad_position']) and ep.GetSize()==vec(d['pad_size_mm'])
    assert fp.GetOrientationDegrees()==0
    paste=[p for p in fp.Pads()if not p.GetNumber()];assert len(paste)==36
    expected={tuple(xy)for xy in d['paste_centres_local_mm']}
    positions={tuple(round(pcbnew.ToMM(v),6)for v in [p.GetPosition().x-ep.GetPosition().x,p.GetPosition().y-ep.GetPosition().y])for p in paste};assert positions==expected
    for p in paste:
        assert p.GetShape()==pcbnew.PAD_SHAPE_RECT and p.GetSize()==vec([.9,.9]) and list(p.GetLayerSet().Seq())==[pcbnew.F_Paste]
    tracks={t.m_Uuid.AsString():t for t in b.GetTracks()};conn=b.GetConnectivity();conn.Build(b);minimum=math.inf
    assert len(d['via_positions'])==25
    box=ep.GetBoundingBox()
    for i,xy in enumerate(d['via_positions']):
        v=tracks[ident('via',i)];assert isinstance(v,pcbnew.PCB_VIA) and v.GetPosition()==vec(xy) and v.GetNetname()=='/GND'
        assert v.GetViaType()==pcbnew.VIATYPE_THROUGH and v.TopLayer()==pcbnew.F_Cu and v.BottomLayer()==pcbnew.B_Cu
        assert v.GetDrillValue()==pcbnew.FromMM(.3)
        assert all(v.IsOnLayer(layer) and v.GetWidth(layer)==pcbnew.FromMM(.6)for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu])
        assert v.GetBackTentingMode()==pcbnew.TENTING_MODE_TENTED and v.GetFrontTentingMode()==pcbnew.TENTING_MODE_NOT_TENTED
        assert ep.m_Uuid.AsString() in {p.m_Uuid.AsString() for p in conn.GetConnectedPads(v)}, f'Via {i} not directly connected to EP'
        pos=v.GetPosition();radius=v.GetWidth(pcbnew.F_Cu)//2
        assert box.GetLeft()+radius <= pos.x <= box.GetRight()-radius and box.GetTop()+radius <= pos.y <= box.GetBottom()-radius
        for p in paste:
            rect=p.GetBoundingBox();dx=max(rect.GetLeft()-pos.x,0,pos.x-rect.GetRight());dy=max(rect.GetTop()-pos.y,0,pos.y-rect.GetBottom())
            clearance=math.hypot(dx,dy)-v.GetDrillValue()/2;minimum=min(minimum,pcbnew.ToMM(clearance));assert clearance>=pcbnew.FromMM(.05), (i,clearance)
    pending=[ep];visited=set()
    while pending:
        item=pending.pop();uid=item.m_Uuid.AsString()
        if uid in visited:continue
        visited.add(uid);pending.extend(conn.GetConnectedItems(item))
    assert hp_ident('zone',0) in visited and all(ident('via',i)in visited for i in range(25))
    coverage=36*.9*.9/(7.5*7.5)*100
    result={'status':'PASS EP directly connected to 25 thermal vias and filled In1.Cu ground; coordinated paste/drill geometry and bottom tenting serialized',
            'via_count':25,'via_diameter_mm':.6,'via_drill_mm':.3,'paste_windows':36,'paste_coverage_percent':round(coverage,2),
            'minimum_paste_to_drill_edge_mm':round(minimum,6),'bottom_tented':True,
            'limits':['Tenting is a fabrication request, not guaranteed hole sealing; solder wicking/voiding, stencil/reflow, finished holes and tolerances require assembler review.',
                      'No thermal/impedance performance or main rail continuity is established.']}
    if not args.trial:(ROOT/'generated/mcu-exposed-ground-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: 25 EP-to-plane vias, 36 paste windows ({coverage:.2f}%); minimum nominal paste/drill edge gap {minimum:.6f} mm; bottom tenting serialized.')
if __name__=='__main__':main()
