#!/usr/bin/env python3
"""Check serialized local geometry and physical supply continuity, not a PDN."""
import json
import pcbnew
from route_mcu_bypass import ROOT, vec, ident

def main():
    board = pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    paths = json.loads((ROOT/'electrical/mcu-bypass-local-routes.json').read_text())['paths']
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    pads = {r: {p.GetNumber(): p for p in f.Pads()} for r, f in fps.items()}
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    assert {p['ref'] for p in paths} == {f'C{i}' for i in range(701,717)} and len(paths)==16
    assert fps['U701'].GetLocalClearance() == pcbnew.FromMM(.127)
    project = json.loads((ROOT/'electrical/kestrel-revb.kicad_pro').read_text())
    assert project['board']['design_settings']['rules']['min_track_width'] == .127
    assert next(c for c in project['net_settings']['classes'] if c['name']=='Default')['clearance'] == .2
    # Check nominal SMD pad spacing independently of the footprint clearance override.
    gaps = []
    for start in [1, 27, 53, 79]:
        for pin in range(start, start+25):
            a = pads['U701'][str(pin)].GetBoundingBox()
            b = pads['U701'][str(pin+1)].GetBoundingBox()
            dx = max(0, a.GetLeft()-b.GetRight(), b.GetLeft()-a.GetRight())
            dy = max(0, a.GetTop()-b.GetBottom(), b.GetTop()-a.GetBottom())
            gap = (dx*dx+dy*dy)**.5
            assert gap >= pcbnew.FromMM(.15), (pin, gap)
            gaps.append(pcbnew.ToMM(gap))
    conn = board.GetConnectivity(); conn.Build(board); checked = []
    for route in paths:
        ref = route['ref']; source = pads['U701'][route['source_pin']]; target = pads[ref]['1']
        assert (source.GetPosition()-vec(route['points'][0])).EuclideanNorm() <= 2 and (target.GetPosition()-vec(route['points'][-1])).EuclideanNorm() <= 2, ref
        assert source.GetNetname()==target.GetNetname()==route['net'], ref
        for i, (a,b) in enumerate(zip(route['points'], route['points'][1:])):
            key=ident(ref,i); t=tracks[key]
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(b) and t.GetLayer()==pcbnew.F_Cu and t.GetWidth()==pcbnew.FromMM(.127) and t.GetNetname()==route['net'],key
            checked.append(key)
        pending, visited = [source], set()
        while pending:
            item=pending.pop(); key=item.m_Uuid.AsString()
            if key in visited: continue
            visited.add(key)
            pending.extend(conn.GetConnectedPads(item)); pending.extend(conn.GetConnectedTracks(item))
        assert target.m_Uuid.AsString() in visited, ref
    result={'status':'PASS sixteen physical local supply connections; incomplete supply and ground network',
            'track_count':len(checked),'minimum_adjacent_pad_gap_mm':min(gaps),'connected_bypasses':[p['ref'] for p in paths],
            'limits':['This supply checker does not verify bypass grounds; use check_mcu_bypass_ground.py. EP continuity and tenting are checked separately by check_mcu_exposed_ground.py; thermal/assembly qualification remains open.',
                      'Main/HP/LDO rail distribution, effective decoupling, current/thermal, stackup, assembly and operation remain unqualified.']}
    (ROOT/'generated/mcu-bypass-layout-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: 16 local supply connections and {len(checked)} serialized segments; ground/PDN qualification unfinished.')
if __name__ == '__main__': main()
