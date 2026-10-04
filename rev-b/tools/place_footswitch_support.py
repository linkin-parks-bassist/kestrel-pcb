#!/usr/bin/env python3
"""Apply provisional footswitch support placement using system KiCad Python.

Preserves unrelated parts and rejects targets moved manually. This establishes
poses, not short routed loops, electrical performance or assembly clearance.
"""
import argparse
import json
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--trial-output',type=Path);args=p.parse_args()
    data_file='footswitch-support-placement.json';report_key='provisional_footswitch_support_references'
    data = json.loads((ROOT/'electrical'/data_file).read_text())
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, (x, y, angle) in data['poses'].items():
        fp = fps[ref]
        target = pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y))
        delta = (fp.GetOrientationDegrees()-angle+180) % 360 - 180
        if pcbnew.ToMM(fp.GetPosition().x) < 190 and (fp.GetPosition() != target or abs(delta) > .001):
            raise ValueError(f'Refusing to reset manually changed {ref}')
        assert fp.GetLayer() == pcbnew.F_Cu, ref
    detached=[]
    old_name='SolderWire-0.5sqmm_1x02_P4.8mm_D0.9mm_OD2.3mm_Relief2x'
    for ref in ['J1101','J1102']:
        old=fps[ref];current=str(old.GetFPID().GetLibItemName())
        if current==data['wire_footprint']:continue
        assert current==old_name and pcbnew.ToMM(old.GetPosition().x)>=190
        assert len(list(old.Pads()))==6
        assert not any(t.GetStart()==p.GetPosition()or t.GetEnd()==p.GetPosition()for t in board.GetTracks()for p in old.Pads())
        new=pcbnew.FootprintLoad('/usr/share/kicad/footprints/Connector_Wire.pretty',data['wire_footprint']);assert new is not None
        new.SetReference(ref);new.SetValue(old.GetValue());new.SetUuid(pcbnew.KIID(old.m_Uuid.AsString()));new.SetPath(old.GetPath());new.SetFPID(pcbnew.LIB_ID('Connector_Wire',data['wire_footprint']))
        old_pads={p.GetNumber():p for p in old.Pads()if p.GetNumber()};old_blank=[p for p in old.Pads()if not p.GetNumber()];blank=0
        for p in new.Pads():
            source=old_pads[p.GetNumber()]if p.GetNumber()else old_blank[blank]
            if not p.GetNumber():blank+=1
            p.SetUuid(pcbnew.KIID(source.m_Uuid.AsString()));p.SetNet(source.GetNet())
        board.Remove(old);detached.append(old);board.Add(new);fps[ref]=new
    for ref, (x, y, angle) in data['poses'].items():
        fps[ref].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y)))
        fps[ref].SetOrientationDegrees(angle)
    assert pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(args.trial_output or path), board)
    if args.trial_output:
        print(f'Trial placed {len(data["poses"])} footswitch support parts');return
    report_path = ROOT/'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    report[report_key] = list(data['poses'])
    report['status'] = ('partial-placement-and-local-routes-engineering-draft' if len(list(board.GetTracks()))
                        else 'provisional-device-and-support-placement-unrouted-engineering-draft')
    report['limits'] = [
        'Mechanical boundary is the provisional notched 1590XX candidate.',
        'Jack/reservoir anchors, major devices and parts listed in placement groups are provisionally placed; other passives remain staged.',
        'Bypass/PLL/configuration/clock/audio routes, power loops, full routing, FPC/connector fit and assembly are unqualified.',
    ]
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'Placed {len(data["poses"])} provisional parts from {data_file}; unrelated placement and nets preserved.')


if __name__ == '__main__':
    main()
