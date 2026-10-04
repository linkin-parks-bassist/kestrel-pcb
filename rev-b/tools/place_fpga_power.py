#!/usr/bin/env python3
"""Guarded FPGA power placement; preserve existing copper and unrelated poses."""
import pcbnew
from place_fpga_bypass import ROOT,main

def run():
    path=ROOT/'electrical/kestrel-revb.kicad_pcb'; b=pcbnew.LoadBoard(str(path));fs={f.GetReference():f for f in b.GetFootprints()}
    c=b.GetConnectivity();c.Build(b)
    def v(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
    targets={'U302':((76,90),(65,87)),'U303':((80,90),(60,87))}
    for ref,(old,new)in targets.items():
        f=fs[ref];assert f.GetPosition()in [v(*old),v(*new)] and f.GetOrientationDegrees()==0 and f.GetLayer()==pcbnew.F_Cu,ref
        if f.GetPosition()!=v(*new):assert all(not list(c.GetConnectedTracks(p))for p in f.Pads()),ref+' already routed'
    main('fpga-power-placement.json','provisional_fpga_power_references')
    b=pcbnew.LoadBoard(str(path));fs={f.GetReference():f for f in b.GetFootprints()}
    for ref,(_,new)in targets.items():fs[ref].SetPosition(v(*new))
    filler=pcbnew.ZONE_FILLER(b);assert filler.Fill(b.Zones());pcbnew.SaveBoard(str(path),b)
if __name__=='__main__':run()
