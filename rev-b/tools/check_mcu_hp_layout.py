#!/usr/bin/env python3
"""Check provisional HP poses and physical local copper connectivity.

Does not certify ground returns, current capacity, loop stability, P4 operation
or assembly. Run with system KiCad Python.
"""
import json
import uuid
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def vec(xy):
    return pcbnew.VECTOR2I(*(pcbnew.FromMM(x) for x in xy))


def main():
    board = pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    poses = json.loads((ROOT/'electrical/mcu-hp-placement.json').read_text())['poses']
    for ref, (x, y, angle) in poses.items():
        fp = fps[ref]
        assert (fp.GetPosition()-vec([100+x, 100-y])).EuclideanNorm() <= 2, ref
        assert abs((fp.GetOrientationDegrees()-angle+180) % 360 - 180) < .001, ref
        assert fp.GetLayer() == pcbnew.F_Cu, ref
    for ref in ['U601', 'L601', 'U904']:
        x, y, angle = json.loads((ROOT/'electrical/placement-draft.json').read_text())['poses'][ref]
        fp = fps[ref]
        assert (fp.GetPosition()-vec([100+x, 100-y])).EuclideanNorm() <= 2, ref
        assert abs((fp.GetOrientationDegrees()-angle+180) % 360 - 180) < .001, ref
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    data = json.loads((ROOT/'electrical/mcu-hp-local-routes.json').read_text())
    checked = []
    for i, path in enumerate(data['paths']):
        for j, (a, b) in enumerate(zip(path['points'], path['points'][1:])):
            ident = str(uuid.uuid5(uuid.NAMESPACE_URL, f'kestrel/rev-b/hp-route/{i}/{j}'))
            t = tracks[ident]
            assert t.GetStart() == vec(a) and t.GetEnd() == vec(b), ident
            assert t.GetLayer() == pcbnew.F_Cu and t.GetNetname() == path['net'], ident
            assert t.GetWidth() == pcbnew.FromMM(path['width_mm']), ident
            checked.append(ident)
    conn = board.GetConnectivity()
    conn.Build(board)
    groups = {
        '/+3V3_D': {'U601.4', 'C601.1', 'C602.1'},
        '/P4 controlled HP regulator/MCU_HP_SW': {'U601.3', 'L601.1'},
        '/ESP_VDD_HP': {'L601.2', 'C603.1', 'C604.1', 'R601.1', 'C605.1'},
        '/MCU_FB_DCDC': {'U601.5', 'R601.2', 'R602.1', 'C605.2'},
    }
    for net, expected in groups.items():
        # Separate islands can share a net while the board remains partially routed.
        ref, pin = sorted(expected)[0].split('.')
        anchor = next(p for fp in board.GetFootprints() if fp.GetReference() == ref
                      for p in fp.Pads() if p.GetNumber() == pin)
        assert anchor.GetNetname() == net
        pending, visited, pads = [anchor], set(), set()
        while pending:
            item = pending.pop()
            ident = item.m_Uuid.AsString()
            if ident in visited:
                continue
            visited.add(ident)
            if isinstance(item, pcbnew.PAD):
                pads.add(item.GetParentFootprint().GetReference()+'.'+item.GetNumber())
            else:
                pending.extend(conn.GetConnectedPads(item))
            pending.extend(conn.GetConnectedTracks(item))
        assert expected <= pads, (net, expected-pads)
    result = {'status': 'PASS bounded local pose/copper check; incomplete power circuit',
              'track_count': len(checked), 'connected_local_groups': {k: sorted(v) for k, v in groups.items()},
              'limits': ['Ground returns, planes, P4 connections, current/thermal/stability and assembly remain unqualified.']}
    (ROOT/'generated/mcu-hp-layout-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'PASS: seven HP passive poses, revised major poses, {len(checked)} local segments and four physical copper-connected pad groups; power/MCU qualification unfinished.')


if __name__ == '__main__':
    main()
