#!/usr/bin/env python3
"""Add guarded provisional HP local routes; does not establish ground loops.

Stable segment IDs allow idempotence. Changed owned segments cause refusal;
unrelated tracks are preserved. Run with system KiCad Python.
"""
import json
import uuid
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def vec(xy):
    return pcbnew.VECTOR2I(*(pcbnew.FromMM(x) for x in xy))


def main():
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    data = json.loads((ROOT/'electrical/mcu-hp-local-routes.json').read_text())
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    poses = json.loads((ROOT/'electrical/mcu-hp-placement.json').read_text())['poses']
    major = json.loads((ROOT/'electrical/placement-draft.json').read_text())['poses']
    poses.update({ref: major[ref] for ref in ['U601', 'L601', 'U904']})
    for ref, (x, y, angle) in poses.items():
        fp = fps[ref]
        assert (fp.GetPosition()-vec([100+x, 100-y])).EuclideanNorm() <= 2, f'Moved route anchor {ref}'
        assert abs((fp.GetOrientationDegrees()-angle+180) % 360 - 180) < .001, ref
    known = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    pending, owned = [], []
    for i, route in enumerate(data['paths']):
        net = board.FindNet(route['net'])
        assert net and net.GetNetCode() > 0, route['net']
        for j, (start, end) in enumerate(zip(route['points'], route['points'][1:])):
            ident = str(uuid.uuid5(uuid.NAMESPACE_URL, f'kestrel/rev-b/hp-route/{i}/{j}'))
            owned.append(ident)
            width = pcbnew.FromMM(route['width_mm'])
            if ident in known:
                t = known[ident]
                assert (t.GetStart() == vec(start) and t.GetEnd() == vec(end)
                        and t.GetWidth() == width and t.GetLayer() == pcbnew.F_Cu
                        and t.GetNetCode() == net.GetNetCode()), f'Manually changed route {ident}'
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetUuid(pcbnew.KIID(ident))
            t.SetStart(vec(start)); t.SetEnd(vec(end))
            t.SetWidth(width); t.SetLayer(pcbnew.F_Cu); t.SetNetCode(net.GetNetCode())
            pending.append(t)
    for t in pending:
        board.Add(t)
    for item in board.GetDrawings():
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetText().startswith('REV B:'):
            item.SetText('REV B: PROVISIONAL 1590XX / PARTIAL PLACEMENT AND LOCAL HP ROUTES')
    pcbnew.SaveBoard(str(path), board)
    report_path = ROOT/'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    report['provisional_hp_track_ids'] = owned
    if not report.get('provisional_ground_zone_id'):
        report['status'] = 'partial-placement-and-local-hp-routes-engineering-draft'
        report['limits'][-1] = 'Local HP routes are partial: ground returns, planes, MCU connections and all remaining routing/assembly are unqualified.'
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'Added {len(pending)} of {len(owned)} owned local HP segments; P4/main-supply connections and qualification unfinished.')


if __name__ == '__main__':
    main()
