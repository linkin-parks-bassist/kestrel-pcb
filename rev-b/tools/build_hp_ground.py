#!/usr/bin/env python3
"""Add guarded HP ground escapes and an In1.Cu ground zone, then fill it.

Existing owned geometry must match; unrelated work is preserved. Filling clips
the rectangular zone envelope to the actual notched board outline. Four copper
layers already exist; no stackup/current/thermal qualification is implied.
"""
import json
import uuid
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def ident(kind, index):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'kestrel/rev-b/hp-ground/{kind}/{index}'))


def vec(xy):
    return pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in xy))


def main():
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    assert board.GetCopperLayerCount() == 4
    data = json.loads((ROOT/'electrical/mcu-hp-ground.json').read_text())
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    existing = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    net = board.FindNet('/GND')
    pending, track_ids, via_ids = [], [], []
    for i, row in enumerate(data['returns']):
        ref, number = row['pad'].split('.')
        pad = next(p for p in fps[ref].Pads() if p.GetNumber() == number)
        assert pad.GetNetname() == '/GND', row['pad']
        assert (pad.GetPosition()-vec(row['pad_position'])).EuclideanNorm() <= 2, row['pad']
        tid, vid = ident('track', i), ident('via', i)
        track_ids.append(tid); via_ids.append(vid)
        if tid in existing:
            t = existing[tid]
            assert (t.GetStart() == vec(row['pad_position']) and t.GetEnd() == vec(row['via_position'])
                    and t.GetWidth() == pcbnew.FromMM(row['track_width_mm'])
                    and t.GetNetname() == '/GND' and t.GetLayer() == pcbnew.F_Cu), tid
        else:
            t = pcbnew.PCB_TRACK(board); t.SetUuid(pcbnew.KIID(tid))
            t.SetStart(vec(row['pad_position'])); t.SetEnd(vec(row['via_position']))
            t.SetWidth(pcbnew.FromMM(row['track_width_mm'])); t.SetLayer(pcbnew.F_Cu)
            t.SetNetCode(net.GetNetCode()); pending.append(t)
        if vid in existing:
            v = existing[vid]
            assert isinstance(v, pcbnew.PCB_VIA), vid
            assert (v.GetPosition() == vec(row['via_position']) and v.GetNetname() == '/GND'
                    and v.GetWidth(pcbnew.F_Cu) == pcbnew.FromMM(data['via_diameter_mm'])
                    and v.GetDrillValue() == pcbnew.FromMM(data['via_drill_mm'])
                    and v.TopLayer() == pcbnew.F_Cu and v.BottomLayer() == pcbnew.B_Cu), vid
        else:
            v = pcbnew.PCB_VIA(board); v.SetUuid(pcbnew.KIID(vid))
            v.SetPosition(vec(row['via_position'])); v.SetWidth(pcbnew.FromMM(data['via_diameter_mm']))
            v.SetDrill(pcbnew.FromMM(data['via_drill_mm'])); v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNetCode(net.GetNetCode()); pending.append(v)
    cfg = data['plane']; zid = ident('zone', 0)
    zones = {z.m_Uuid.AsString(): z for z in board.Zones()}
    if zid in zones:
        z = zones[zid]
        assert z.GetLayer() == pcbnew.In1_Cu and z.GetNetname() == '/GND', zid
        polygon = z.Outline().COutline(0)
        assert polygon.PointCount() == len(cfg['outline']), zid
        assert all(polygon.CPoint(i) == vec(p) for i, p in enumerate(cfg['outline'])), zid
        assert z.GetOwnClearance(pcbnew.In1_Cu) == pcbnew.FromMM(cfg['clearance_mm']), zid
        assert z.GetMinThickness() == pcbnew.FromMM(cfg['min_thickness_mm']), zid
        assert z.GetPadConnection() == pcbnew.ZONE_CONNECTION_THT_THERMAL, zid
        assert z.GetThermalReliefGap() == pcbnew.FromMM(cfg['thermal_gap_mm']), zid
        assert z.GetThermalReliefSpokeWidth() == pcbnew.FromMM(cfg['thermal_spoke_mm']), zid
        assert z.GetZoneName() == cfg['name'], zid
    else:
        z = pcbnew.ZONE(board); z.SetUuid(pcbnew.KIID(zid)); z.SetLayer(pcbnew.In1_Cu)
        z.SetNetCode(net.GetNetCode()); z.SetZoneName(cfg['name'])
        z.SetLocalClearance(pcbnew.FromMM(cfg['clearance_mm']))
        z.SetMinThickness(pcbnew.FromMM(cfg['min_thickness_mm']))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(pcbnew.FromMM(cfg['thermal_gap_mm']))
        z.SetThermalReliefSpokeWidth(pcbnew.FromMM(cfg['thermal_spoke_mm']))
        outline = z.Outline(); outline.NewOutline()
        for p in cfg['outline']:
            outline.Append(vec(p).x, vec(p).y)
        pending.append(z)
    for item in pending:
        board.Add(item)
    filler = pcbnew.ZONE_FILLER(board)
    assert filler.Fill(board.Zones()), 'Zone fill failed'
    assert z.HasFilledPolysForLayer(pcbnew.In1_Cu), 'Ground zone has no fill'
    pcbnew.SaveBoard(str(path), board)
    report_path = ROOT/'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    report['provisional_hp_ground_track_ids'] = track_ids
    report['provisional_hp_ground_via_ids'] = via_ids
    report['provisional_ground_zone_id'] = zid
    report['status'] = 'partial-placement-local-hp-copper-and-ground-plane-engineering-draft'
    report['limits'][-1] = 'HP returns/inner ground plane are provisional; stackup, current, stability, P4 connections, full routing and assembly remain unqualified.'
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('Added/verified six HP ground escapes and six through vias; filled one In1.Cu GND zone.')


if __name__ == '__main__':
    main()
