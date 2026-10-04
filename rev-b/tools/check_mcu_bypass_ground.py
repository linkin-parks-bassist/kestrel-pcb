#!/usr/bin/env python3
"""Verify all sixteen P4 bypass ground returns through filled In1.Cu.

This is copper continuity evidence, not impedance, stackup, load or thermal
qualification. The P4 and main supply connections remain unfinished.
"""
import json
from pathlib import Path
import pcbnew
from build_mcu_bypass_ground import ident, vec
from build_hp_ground import ident as hp_ident

ROOT = Path(__file__).resolve().parents[1]


def main():
    board = pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    data = json.loads((ROOT/'electrical/mcu-bypass-ground.json').read_text())
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    zones = {z.m_Uuid.AsString(): z for z in board.Zones()}
    zone = zones[hp_ident('zone', 0)]
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
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    assert len(data['returns']) == 16
    assert {r['pad'] for r in data['returns']} == {f'C{i}.2' for i in range(701,717)}
    for row in data['returns']:
        ref, number = row['pad'].split('.')
        pad = next(p for p in fps[ref].Pads() if p.GetNumber() == number)
        assert pad.GetNetname() == '/GND'
        assert (pad.GetPosition()-vec(row['pad_position'])).EuclideanNorm() <= 2, ref
        # The drill circle must remain outside the SMT capacitor land.
        box = pad.GetBoundingBox(); pos = vec(row['via_position'])
        dx = max(box.GetLeft()-pos.x, 0, pos.x-box.GetRight())
        dy = max(box.GetTop()-pos.y, 0, pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**0.5 > pcbnew.FromMM(data['via_drill_mm'])/2, ref
    pending = [next(p for p in fps['C701'].Pads() if p.GetNumber() == '2')]
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
    assert zone.m_Uuid.AsString() in visited, 'P4 bypass returns do not reach ground zone'
    result = {'status': 'PASS sixteen P4 bypass ground pads physically connected through filled inner zone',
              'mcu_bypass_ground_pads': sorted(expected), 'ground_vias': 16, 'ground_tracks': 16,
              'zone_layer': 'In1.Cu', 'other_reachable_pad_names': sorted(pads-expected),
              'limits': ['Main rails remain unfinished; EP continuity/tenting is checked separately by check_mcu_exposed_ground.py; stackup, return impedance, current/thermal and assembly remain unqualified.']}
    (ROOT/'generated/mcu-bypass-ground-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: sixteen P4 bypass ground pads, sixteen 0.6/0.3-mm through vias and filled In1.Cu GND physically connected; drills outside capacitor lands.')


if __name__ == '__main__':
    main()
