#!/usr/bin/env python3
"""Guarded provisional 5 V buck support and unrouted regulator placement."""
import pcbnew
from place_fpga_bypass import ROOT,main
if __name__=='__main__':
    path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(path))
    f=next(f for f in b.GetFootprints()if f.GetReference()=='U101')
    def v(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
    assert (f.GetPosition()==v(52,78)and f.GetOrientationDegrees()==0)or(f.GetPosition()==v(53,78)and f.GetOrientationDegrees()==180)
    c=b.GetConnectivity();c.Build(b)
    assert all(not list(c.GetConnectedTracks(p))for p in f.Pads()),'Regulator already routed'
    main('buck5v-placement.json','provisional_buck5v_references')
    b=pcbnew.LoadBoard(str(path));f=next(f for f in b.GetFootprints()if f.GetReference()=='U101')
    f.SetPosition(v(53,78));f.SetOrientationDegrees(180);pcbnew.SaveBoard(str(path),b)
