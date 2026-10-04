#!/usr/bin/env python3
"""Check provisional SPI poses and bounded pad allocations, not electrical performance."""
import argparse
import json
import math
import pcbnew
from place_spi_support import ROOT,at

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));fps={f.GetReference():f for f in b.GetFootprints()};d=json.loads((ROOT/'electrical/spi-support-placement.json').read_text())
    assert len(d['poses'])==16
    for ref,pose in (d['poses']|d['major_poses']).items():assert at(fps[ref],pose) and fps[ref].GetLayer()==pcbnew.F_Cu,ref
    pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()}
    assert pads['U801']['15'].GetPosition().x<pads['U801']['3'].GetPosition().x
    assert pads['U801']['15'].GetNetname()=='/+3V3_FPGA' and pads['U801']['16'].GetNetname()=='/+3V3_D'
    for ref in ['C801','C802']:
        assert fps[ref].GetFPID().GetLibItemName()=='C_0402_1005Metric'
        assert fps[ref].GetField('MPN').GetText()=='CL05B104KO5NNNC'
    allocations=[('C801.1','U801.16',2.5),('C802.1','U801.15',2.5),('C803.1','U802.6',2.5),('C804.1','U803.5',2.5),('C805.1','U802.5',4),
                 ('R801.1','U801.14',4.5),('R802.1','U801.13',4.5),('R803.1','U801.12',4.5),('R804.1','U801.6',3),
                 ('R805.2','R801.2',4.5),('R806.2','U801.3',4.5),('R807.2','U803.4',4.5),('R808.1','U803.1',5),('R809.2','U802.1',5),('R810.2','U802.5',6),('R811.1','U802.5',6)]
    review={}
    for name,target,bound in allocations:
        ref,num=name.split('.');owner,pin=target.split('.');p=pads[ref][num];q=pads[owner][pin];assert p.GetNetname()==q.GetNetname(),name
        delta=p.GetPosition()-q.GetPosition();distance=math.hypot(pcbnew.ToMM(delta.x),pcbnew.ToMM(delta.y));assert distance<=bound,(name,distance,bound)
        if ref.startswith('C'):assert pads[ref]['2'].GetNetname()=='/GND'
        review[name]={'assigned_pad':target,'pad_centre_distance_mm':round(distance,4),'engineering_target_mm':bound}
    result={'status':'PASS sixteen SPI support poses, translator orientation and sixteen bounded net/proximity allocations','placed_references':sorted(d['poses']),'local_allocations':review,
            'limits':['These distances are engineering placement allocations, not vendor loop/damping guarantees; local supply/control/ground/SPI routing, SI/timing, rail shutdown/backfeed, current/thermal and assembly remain unfinished or unqualified.']}
    if not args.trial:(ROOT/'generated/spi-support-placement-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: sixteen SPI support poses, U801 B-side facing FPGA and sixteen bounded pad allocations; routing/performance unfinished.')
if __name__=='__main__':main()
