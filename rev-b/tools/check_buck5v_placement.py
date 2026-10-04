#!/usr/bin/env python3
"""Native 5 V buck pose and local net/proximity review, not loop performance."""
import json
import math
import pcbnew
from place_fpga_bypass import ROOT

def main():
    b=pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()};d=json.loads((ROOT/'electrical/buck5v-placement.json').read_text())
    assert len(d['poses'])==11 and set(d['poses'])=={f'C{i}'for i in range(101,107)}|{f'R{i}'for i in range(101,106)}
    for ref,(x,y,a)in d['poses'].items():
        f=fps[ref];assert (f.GetPosition()-pcbnew.VECTOR2I(pcbnew.FromMM(100+x),pcbnew.FromMM(100-y))).EuclideanNorm()<=2,ref
        assert abs((f.GetOrientationDegrees()-a+180)%360-180)<.001 and f.GetLayer()==pcbnew.F_Cu,ref
    u=fps['U101'];assert u.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(53),pcbnew.FromMM(78)) and u.GetOrientationDegrees()==180
    pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};review={}
    targets=[('C102','1','U101','3',2),('C101','1','U101','3',6),('C103','1','U101','6',2),('C104','1','L101','2',3),('C105','1','L101','2',10),('R103','1','U101','4',5),('R104','2','U101','5',5)]
    for ref,num,owner,pin,bound in targets:
        p,q=pads[ref][num],pads[owner][pin];assert p.GetNetname()==q.GetNetname(),ref
        delta=p.GetPosition()-q.GetPosition();distance=math.hypot(pcbnew.ToMM(delta.x),pcbnew.ToMM(delta.y));assert distance<=bound,(ref,distance,bound)
        review[ref]={'assigned_pad':owner+'.'+pin,'distance_mm':round(distance,4),'provisional_bound_mm':bound}
    assert pads['C103']['2'].GetNetname()==pads['U101']['2'].GetNetname()
    for ref in ['C101','C102','C104','C105']:assert pads[ref]['2'].GetNetname()=='/GND'
    assert pads['R103']['2'].GetNetname()=='/GND' and pads['R105']['2'].GetNetname()=='/GND'
    result={'status':'PASS eleven buck support poses and seven bounded local net/proximity allocations','placed_references':sorted(d['poses']),'local_allocations':review,'limits':['Local copper continuity is checked separately by check_buck5v_local.py; protected-input feed continuity is checked by check_input_power_local.py; output distribution remains unfinished; capacitor effective values, loop/noise, current/thermal and operation remain unqualified.']}
    (ROOT/'generated/buck5v-placement-review.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: 11 buck support poses, regulator rotation and 7 bounded net/proximity allocations; routing/performance unqualified.')
if __name__=='__main__':main()
