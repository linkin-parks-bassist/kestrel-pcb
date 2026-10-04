#!/usr/bin/env python3
"""Place provisional jack/reservoir anchors from the standard-case fit model.

Moves only these four parts, preserving nets and other placement. Refuses to
reset an anchor already moved elsewhere on the board. The existing boundary
remains provisional; this is not a manufacturing-qualified placement.
"""
import json
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = json.loads((ROOT / 'mechanical/standard-case.json').read_text())
    path = ROOT / 'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    j = p['audio_jacks']
    # Board XY has origin (100,100), +Y towards the foot end; CAD has +Y rear.
    x = j['panel_datum_x'] + j['pin_panel_offsets'][0]
    y = j['centre_y']
    half_grid = max(j['pin_row_offsets'])
    poses = {'J201': (-x, y+half_grid, 180), 'J202': (x, y-half_grid, 0)}
    poses.update({ref: (*centre, 0) for ref, centre in
                  zip(p['reservoirs']['references'], p['reservoirs']['centres'])})
    for ref, (x, y, angle) in poses.items():
        fp = fps[ref]
        target = pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y))
        old = fp.GetPosition()
        if pcbnew.ToMM(old.x) < 190 and (old != target or abs(fp.GetOrientationDegrees()-angle) > .001):
            raise ValueError(f'Refusing to reset manually changed anchor {ref}')
    for ref, (x, y, angle) in poses.items():
        fp = fps[ref]
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(100+x), pcbnew.FromMM(100-y)))
        fp.SetOrientationDegrees(angle)
    pcbnew.SaveBoard(str(path), board)
    report_path = ROOT / 'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    if not report.get('provisional_major_references'):
        report['status'] = 'provisional-mechanical-anchors-unrouted-engineering-draft'
    report['provisional_anchor_references'] = list(poses)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print('Placed J201/J202 underside and C230/C235 top as provisional mechanical anchors.')


if __name__ == '__main__':
    main()
