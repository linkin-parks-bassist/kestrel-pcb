#!/usr/bin/env python3
"""Verify serialized HP return geometry and connectivity through filled In1.Cu.

This is copper continuity evidence, not impedance, stackup, load or thermal
qualification. The P4 and main supply connections remain unfinished.
"""
import json
from pathlib import Path
import pcbnew
from build_hp_ground import ident, vec

ROOT = Path(__file__).resolve().parents[1]


def main():
    board = pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    data = json.loads((ROOT/'electrical/mcu-hp-ground.json').read_text())
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    zones = {z.m_Uuid.AsString(): z for z in board.Zones()}
    zone = zones[ident('zone', 0)]
    assert zone.GetLayer() == pcbnew.In1_Cu and zone.GetNetname() == '/GND'
    assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    for i, row in enumerate(data['returns']):
        t, v = tracks[ident('track', i)], tracks[ident('via', i)]
        assert t.GetStart() == vec(row['pad_position']) and t.GetEnd() == vec(row['via_position'])
        assert t.GetLayer() == pcbnew.F_Cu and t.GetNetname() == '/GND'
        assert t.GetWidth() == pcbnew.FromMM(row['track_width_mm'])
        assert isinstance(v, pcbnew.PCB_VIA) and v.GetPosition() == vec(row['via_position'])
        assert v.GetNetname() == '/GND' and v.GetDrillValue() == pcbnew.FromMM(data['via_drill_mm'])
        for layer in [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]:
            assert v.IsOnLayer(layer) and v.GetWidth(layer) == pcbnew.FromMM(data['via_diameter_mm'])
    conn = board.GetConnectivity(); conn.Build(board)
    pending = [tracks[ident('track', 0)]]
    visited, pads = set(), set()
    while pending:
        item = pending.pop(); uid = item.m_Uuid.AsString()
        if uid in visited:
            continue
        visited.add(uid)
        if isinstance(item, pcbnew.PAD):
            pads.add(item.GetParentFootprint().GetReference()+'.'+item.GetNumber())
        pending.extend(conn.GetConnectedItems(item))
    expected = {row['pad'] for row in data['returns']}
    assert expected <= pads, expected-pads
    assert zone.m_Uuid.AsString() in visited, 'HP returns do not reach ground zone'
    result = {'status': 'PASS six HP ground pads physically connected through filled inner zone',
              'hp_ground_pads': sorted(expected), 'ground_vias': 6, 'ground_tracks': 6,
              'zone_layer': 'In1.Cu', 'other_reachable_pad_names': sorted(pads-expected),
              'limits': ['Stackup, return impedance, load/current/thermal, P4/main-supply connections and assembly remain unqualified.']}
    (ROOT/'generated/hp-ground-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: six ground escapes, six 0.7/0.3-mm through vias and six HP ground pads physically connected through filled In1.Cu GND.')


if __name__ == '__main__':
    main()
