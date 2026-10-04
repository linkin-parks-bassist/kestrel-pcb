#!/usr/bin/env python3
"""Verify probe-pad poses and USB nets without claiming routed USB function."""
import json
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1]
def main():
    b=pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    f={x.GetReference():x for x in b.GetFootprints()}
    d=json.loads((ROOT/'electrical/mcu-usb-service-placement.json').read_text())
    for ref,(x,y,a) in d['poses'].items():
        fp=f[ref];assert fp.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(100+x),pcbnew.FromMM(100-y))
        assert fp.GetOrientationDegrees()==a and fp.GetLayer()==pcbnew.F_Cu
        assert fp.GetFPID().GetLibItemName()=='TestPoint_Pad_D1.0mm'
    for ref,xy in d['reference_positions_pcb_mm'].items():
        assert f[ref].Reference().GetPosition()==pcbnew.VECTOR2I(*(pcbnew.FromMM(v)for v in xy))
    for ref,pin,net in [('TP701','52','MCU_USB_DM'),('TP702','53','MCU_USB_DP')]:
        p=next(p for p in f[ref].Pads()if p.GetNumber()=='1')
        q=next(p for p in f['U701'].Pads()if p.GetNumber()==pin)
        assert p.GetNetname()==q.GetNetname()=='/Bare ESP32-P4 support/'+net
    result={'status':'PASS two provisional USB probe poses and GPIO24/25 net assignments',
            'placed_references':sorted(d['poses']),
            'limits':['Pads remain unrouted; connector/protection, controlled impedance, fixture access, assembly and backfeed remain unqualified.']}
    (ROOT/'generated/mcu-usb-service-placement-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS two USB probe-pad poses and GPIO24/25 net assignments; USB interface unfinished.')
if __name__=='__main__':main()
