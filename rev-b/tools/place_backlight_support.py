#!/usr/bin/env python3
"""Apply provisional backlight/LCD/touch supply support placement using system KiCad Python.

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
    data_file='backlight-support-placement.json';report_key='provisional_backlight_support_references'
    data = json.loads((ROOT/'electrical'/data_file).read_text())
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, (x, y, angle) in {**data['poses'], **data['major_poses']}.items():
        fp = fps[ref]
        target = pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y))
        delta = (fp.GetOrientationDegrees()-angle+180) % 360 - 180
        if pcbnew.ToMM(fp.GetPosition().x) < 190 and (fp.GetPosition() != target or abs(delta) > .001):
            original = data['original_major_poses'].get(ref)
            if original is None or fp.GetPosition() != pcbnew.VECTOR2I(pcbnew.FromMM(100+original[0]), pcbnew.FromMM(100-original[1])) or abs(fp.GetOrientationDegrees()-original[2]) > .001:
                raise ValueError(f'Refusing to reset manually changed {ref}')
            assert not any(board.GetConnectivity().GetConnectedTracks(pad) for pad in fp.Pads()), f'{ref} is already routed'
        assert fp.GetLayer() == pcbnew.F_Cu, ref
    for ref, (x, y, angle) in {**data['poses'], **data['major_poses']}.items():
        fps[ref].SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y)))
        fps[ref].SetOrientationDegrees(angle)
    assert pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(args.trial_output or path), board)
    if args.trial_output:
        print(f'Trial placed {len(data["poses"])} backlight support parts');return
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
