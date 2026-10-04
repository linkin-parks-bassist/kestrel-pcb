#!/usr/bin/env python3
"""Native 3.3 V buck pose and local net/proximity review, not loop performance."""
import json
import math
import pcbnew
from place_fpga_bypass import ROOT

def main():
    b=pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()};d=json.loads((ROOT/'electrical/buck3v3-placement.json').read_text())
    assert len(d['poses'])==12 and set(d['poses'])=={f'C{i}'for i in range(107,114)}|{f'R{i}'for i in range(106,111)}
    for ref,(x,y,a)in d['poses'].items():
        f=fps[ref];assert (f.GetPosition()-pcbnew.VECTOR2I(pcbnew.FromMM(100+x),pcbnew.FromMM(100-y))).EuclideanNorm()<=2,ref
        assert abs((f.GetOrientationDegrees()-a+180)%360-180)<.001 and f.GetLayer()==pcbnew.F_Cu,ref
    u=fps['U102'];assert u.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(76),pcbnew.FromMM(62)) and u.GetOrientationDegrees()==180
    pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};review={}
    targets=[('C108','1','U102','3',2),('C107','1','U102','3',6),('C109','1','U102','6',2),('C110','1','L102','2',3),('C111','1','L102','2',6),('C113','1','L102','2',10),('R108','1','U102','4',5),('R109','2','U102','5',5)]
    for ref,num,owner,pin,bound in targets:
        p,q=pads[ref][num],pads[owner][pin];assert p.GetNetname()==q.GetNetname(),ref
        delta=p.GetPosition()-q.GetPosition();distance=math.hypot(pcbnew.ToMM(delta.x),pcbnew.ToMM(delta.y));assert distance<=bound,(ref,distance,bound)
        review[ref]={'assigned_pad':owner+'.'+pin,'distance_mm':round(distance,4),'provisional_bound_mm':bound}
    assert pads['C109']['2'].GetNetname()==pads['U102']['2'].GetNetname()
    for ref in ['C107','C108','C110','C111','C113']:assert pads[ref]['2'].GetNetname()=='/GND'
    assert pads['R108']['2'].GetNetname()=='/GND' and pads['R110']['2'].GetNetname()=='/GND'
    result={'status':'PASS twelve buck support poses and eight bounded local net/proximity allocations','placed_references':sorted(d['poses']),'local_allocations':review,'limits':['Local copper continuity is checked separately by check_buck3v3_local.py; protected-input feed continuity is checked by check_input_power_local.py; output distribution remains unfinished; capacitor effective values, loop/noise, current/thermal and operation remain unqualified.']}
    (ROOT/'generated/buck3v3-placement-review.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS: 12 buck support poses, regulator rotation and 8 bounded net/proximity allocations; routing/performance unqualified.')
if __name__=='__main__':main()
