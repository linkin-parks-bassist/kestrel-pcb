#!/usr/bin/env python3
"""Apply initial IC/connector placement without resetting unrelated PCB work.

Re-running requires each selected part to be staged or already at its specified
pose; manually moved parts cause a refusal. Positions remain provisional.
"""
import json
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    poses = json.loads((ROOT/'electrical/placement-draft.json').read_text())['poses']
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    for ref, (x, y, angle) in poses.items():
        fp = fps[ref]
        target = pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y))
        old = fp.GetPosition()
        if pcbnew.ToMM(old.x) < 190 and (old != target or abs(fp.GetOrientationDegrees()-angle) > .001):
            raise ValueError(f'Refusing to reset manually changed {ref}')
    for ref, (x, y, angle) in poses.items():
        fp = fps[ref]
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y)))
        fp.SetOrientationDegrees(angle)
    pcbnew.SaveBoard(str(path), board)
    report_path = ROOT/'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    report['provisional_major_references'] = list(poses)
    if not report.get('provisional_fpga_bypass_references'):
        report['status'] = 'provisional-major-placement-unrouted-engineering-draft'
        report['limits'] = ['Mechanical boundary is the provisional notched 1590XX candidate.',
                            'Jack/reservoir anchors and major devices are placed; most passives remain staged.',
                            'Power/clock/analogue placement, full routing, FPC/connector fit and assembly are unqualified.']
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'Placed {len(poses)} provisional major devices; other footprints/nets preserved.')


if __name__ == '__main__':
    main()
