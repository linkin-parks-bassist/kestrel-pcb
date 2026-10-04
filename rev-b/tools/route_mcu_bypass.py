#!/usr/bin/env python3
"""Guarded local P4 bypass supply routes; ground/PDN qualification is separate."""
import json
import uuid
from pathlib import Path
import pcbnew
ROOT = Path(__file__).resolve().parents[1]
def vec(xy): return pcbnew.VECTOR2I(*(pcbnew.FromMM(x) for x in xy))
def ident(ref, index): return str(uuid.uuid5(uuid.NAMESPACE_URL, f'kestrel/rev-b/mcu-bypass/{ref}/{index}'))
def main():
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    data = json.loads((ROOT/'electrical/mcu-bypass-local-routes.json').read_text())
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    pads = {r: {p.GetNumber(): p for p in f.Pads()} for r, f in fps.items()}
    tracks = {t.m_Uuid.AsString(): t for t in board.GetTracks()}
    assert fps['U701'].GetLocalClearance() == pcbnew.FromMM(.127)
    pending, owned = [], []
    for route in data['paths']:
        ref = route['ref']; src = pads['U701'][route['source_pin']]; dst = pads[ref]['1']
        assert (src.GetPosition()-vec(route['points'][0])).EuclideanNorm() <= 2 and (dst.GetPosition()-vec(route['points'][-1])).EuclideanNorm() <= 2, ref
        assert src.GetNetname() == dst.GetNetname() == route['net'], ref
        for i, (a, b) in enumerate(zip(route['points'], route['points'][1:])):
            key = ident(ref, i); owned.append(key); width = pcbnew.FromMM(route['width_mm'])
            if key in tracks:
                t = tracks[key]
                assert (t.GetStart() == vec(a) and t.GetEnd() == vec(b) and t.GetWidth() == width
                        and t.GetLayer() == pcbnew.F_Cu and t.GetNetname() == route['net']), key
                continue
            t = pcbnew.PCB_TRACK(board); t.SetUuid(pcbnew.KIID(key))
            t.SetStart(vec(a)); t.SetEnd(vec(b)); t.SetWidth(width); t.SetLayer(pcbnew.F_Cu); t.SetNetCode(src.GetNetCode())
            pending.append(t)
    for t in pending: board.Add(t)
    pcbnew.SaveBoard(str(path), board)
    p = ROOT/'generated/pcb-import-review.json'; d = json.loads(p.read_text())
    d['provisional_mcu_bypass_track_ids'] = owned
    d['status'] = 'partial-placement-and-local-supply-routes-engineering-draft'
    p.write_text(json.dumps(d, indent=2)+'\n')
    print(f'Added {len(pending)} of {len(owned)} local P4 bypass supply segments; ground returns/full supply routing unqualified.')
if __name__ == '__main__': main()
