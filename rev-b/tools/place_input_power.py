#!/usr/bin/env python3
"""Guarded input-protection placement; underside DC jack is mechanically provisional."""
import json
import pcbnew
from place_fpga_bypass import ROOT, main
if __name__=='__main__':
    d=json.loads((ROOT/'electrical/input-power-placement.json').read_text());path=ROOT/'electrical/kestrel-revb.kicad_pcb'
    b=pcbnew.LoadBoard(str(path));f=next(f for f in b.GetFootprints()if f.GetReference()=='J401')
    x,y,a=d['jack_pose_pcb_mm'];target=pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
    assert pcbnew.ToMM(f.GetPosition().x)>=190 or (f.GetPosition()==target and f.GetLayer()==pcbnew.B_Cu and f.GetOrientationDegrees()==a),'Unexpected manual jack pose'
    c=b.GetConnectivity();c.Build(b);assert all(not list(c.GetConnectedTracks(p))for p in f.Pads()),'Jack already routed'
    main('input-power-placement.json','provisional_input_power_references')
    b=pcbnew.LoadBoard(str(path));f=next(f for f in b.GetFootprints()if f.GetReference()=='J401')
    if f.GetLayer()!=pcbnew.B_Cu:f.Flip(f.GetPosition(),pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetPosition(target);f.SetOrientationDegrees(a)
    for field in f.GetFields():
        if field.GetName()=='AssemblySide':field.SetText('B.Cu / through-hole post assembly')
    filler=pcbnew.ZONE_FILLER(b);assert filler.Fill(b.Zones())
    pcbnew.SaveBoard(str(path),b)
    p=ROOT/'generated/pcb-import-review.json';r=json.loads(p.read_text());r['provisional_input_power_references']=list(d['poses'])+['J401'];p.write_text(json.dumps(r,indent=2)+'\n')
    print('Placed nine front-side input-protection parts and underside J401; fit/protection unqualified.')
