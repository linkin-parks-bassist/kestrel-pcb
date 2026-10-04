#!/usr/bin/env python3
"""Check the isolated partial timing/touch trial; never modifies the electrical board."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import tempfile
import uuid

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
PINS = [94, 97, 12, 13, 14, 16, 17, 18, 19]
NETS = ['/MCU_LCD_' + n for n in ['PCLK', 'HSYNC', 'VSYNC', 'DE', 'DISP']]
NETS += ['/MCU_TOUCH_' + n for n in ['SCL', 'SDA', 'INT', 'RST_N']]

def ident(kind, index):
    return str(uuid.uuid5(uuid.NAMESPACE_URL,
                         f'kestrel/rev-b/display-timing-source-routes/{kind}/{index}'))

def vec(xy):
    return pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in xy))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--board', type=Path, default=ROOT/'generated/trials/display-timing.kicad_pcb')
    parser.add_argument('--manifest', type=Path, default=ROOT/'generated/trials/display-timing-source.json')
    parser.add_argument('--report', type=Path, default=ROOT/'generated/display-timing-fanout-review.json')
    args = parser.parse_args()
    authority = ROOT/'electrical/kestrel-revb.kicad_pcb'
    assert args.board.resolve() != authority.resolve(), 'This checker is for the isolated trial only'
    assert sha(authority) == 'd9ab775ac875b05810398540a1a2c6c7df1320830a34a818935166dabb698db7', 'Trial baseline changed'
    assert sha(args.board.with_suffix('.kicad_pro')) == sha(authority.with_suffix('.kicad_pro')), 'Manufacturing profile changed'
    d = json.loads(args.manifest.read_text())
    b = pcbnew.LoadBoard(str(args.board))
    pads = {f.GetReference()+'.'+p.GetNumber():p for f in b.GetFootprints() for p in f.Pads()}
    tracks = {t.m_Uuid.AsString():t for t in b.GetTracks()}
    conn = b.GetConnectivity()
    conn.Build(b)
    groups = {}
    for i, (pin, net) in enumerate(zip(PINS, NETS)):
        names = [f'U701.{pin}', f'R{1017+i}.1']
        assert all(pads[n].GetNetname() == net for n in names), names
        for n in names:
            assert pads[n].GetPosition() == vec(d['anchors'][n]), n
        pending, seen, actual = [pads[names[0]]], set(), set()
        while pending:
            it = pending.pop()
            key = it.m_Uuid.AsString()
            if key in seen:
                continue
            seen.add(key)
            if isinstance(it, pcbnew.PAD):
                actual.add(it.GetParentFootprint().GetReference()+'.'+it.GetNumber())
            pending.extend(conn.GetConnectedItems(it))
        expected = set(names if net in d['complete_nets'] else names[:1])
        assert actual == expected, (net, actual, expected)
        groups[net] = sorted(actual)
    fps = {f.GetReference():f for f in b.GetFootprints()}
    for i in range(1017, 1026):
        f = fps[f'R{i}']
        fid = f.GetFPID()
        assert f'{fid.GetLibNickname()}:{fid.GetLibItemName()}' == 'Resistor_SMD:R_0402_1005Metric'
        assert f.GetLayer() == pcbnew.B_Cu and f.GetValue() == '33ohm'
        assert f.GetField('MPN').GetText() == 'RC0402FR-0733RL' and f.GetField('LCSC').GetText() == 'C138002'
    assert pads['U701.10'].GetNetname() == 'unconnected-(U701B-GPIO9-Pad10)'
    assert pads['U701.11'].GetNetname() == 'unconnected-(U701B-GPIO10-Pad11)'
    index = 0
    for route in d['paths']:
        for a, c in zip(route['points'], route['points'][1:]):
            t = tracks[ident('track', index)]
            assert not isinstance(t, pcbnew.PCB_VIA)
            assert (t.GetStart(), t.GetEnd()) == (vec(a), vec(c))
            assert t.GetLayerName() == route['layer'] and t.GetNetname() == route['net']
            assert t.GetWidth() == pcbnew.FromMM(.127) == pcbnew.FromMM(route['width_mm'])
            index += 1
    vip = set()
    for i, xy in enumerate(d['via_positions']):
        v = tracks[ident('via', i)]
        assert isinstance(v, pcbnew.PCB_VIA) and v.GetPosition() == vec(xy)
        assert v.GetNetname() == d['via_net_names'][i]
        assert v.GetWidth(pcbnew.F_Cu) == pcbnew.FromMM(.5) and v.GetDrillValue() == pcbnew.FromMM(.3)
        assert (v.TopLayer(), v.BottomLayer()) == (pcbnew.F_Cu, pcbnew.B_Cu)
        for name, pad in pads.items():
            if pad.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            layer = pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
            poly = pad.GetEffectivePolygon(layer)
            center, radius = v.GetPosition(), pcbnew.FromMM(.15)
            if not (poly.Contains(center) or poly.CollideEdge(center, None, radius)):
                continue
            assert name in d['via_in_pad_anchors'] and pad.GetNetname() == v.GetNetname(), name
            assert poly.Contains(center) and not poly.CollideEdge(center, None, radius), name
            vip.add(name)
    assert vip == set(d['via_in_pad_anchors']), vip
    with tempfile.TemporaryDirectory(prefix='kestrel-timing-drc-') as tmp:
        out = Path(tmp)/'drc.json'
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', str(out), str(args.board)], check=True, stdout=subprocess.DEVNULL)
        drc = json.loads(out.read_text())
    residual = {'silk_overlap', 'silk_over_copper', 'silk_edge_clearance', 'drill_out_of_range', 'lib_footprint_issues', 'track_dangling', 'via_dangling'}
    assert not [v for v in drc['violations'] if v['type'] not in residual]
    counts = Counter(v['type'] for v in drc['violations'])
    assert counts['drill_out_of_range'] == 6, 'Unexpected manufacturing-profile drill residual'
    library_items = {it['description'] for v in drc['violations'] if v['type'] == 'lib_footprint_issues' for it in v['items']}
    assert library_items == {'Footprint '+ref for ref in ['U303', 'U501', 'U701', 'C230', 'C235']}
    for kind, seeds in [('track', d['seed_track_indices']), ('via', d['seed_via_indices'])]:
        expected = {ident(kind, i) for start, i in seeds.items() if d['anchor_nets'][start] not in d['complete_nets']}
        actual = {it['uuid'] for v in drc['violations'] if v['type'] == kind+'_dangling' for it in v['items']}
        assert actual == expected, (kind, actual, expected)
    allocations = {}
    for ref, pin in [('C701', 9), ('C702', 21)]:
        delta = pads[ref+'.1'].GetPosition() - pads[f'U701.{pin}'].GetPosition()
        allocations[ref] = dict(source_pad=f'U701.{pin}', distance_mm=math.hypot(pcbnew.ToMM(delta.x), pcbnew.ToMM(delta.y)), maintained_bound_mm=2.5)
    lengths = {net:sum(math.dist(a, c) for r in d['paths'] if r['net'] == net for a, c in zip(r['points'], r['points'][1:])) for net in NETS}
    report = dict(status='Unadopted partial trial; authoritative schematic and PCB unchanged',
                  baseline_sha256=sha(authority), trial_sha256=sha(args.board),
                  manufacturing_profile_sha256=sha(authority.with_suffix('.kicad_pro')),
                  complete_source_nets=d['complete_nets'], pending_source_nets=[n for n in NETS if n not in d['complete_nets']],
                  physical_source_groups=groups, source_segments=index, source_vias=len(d['via_positions']),
                  source_via_in_pad=sorted(vip), native_critical_violations=0,
                  source_planar_length_mm=lengths, bypass_source_allocations=allocations,
                  native_residual_counts=dict(counts),
                  unconnected_report_entries=len(drc['unconnected_items']),
                  limits=['PCLK/HSYNC trial uses GPIO51/pad94 and GPIO53/pad97; no schematic remap is adopted.',
                          'Nine trial 0402 damping selections/poses, C701/C702 underside bypass, MISO detour and R5 output reroute are unadopted.',
                          'C701/C702 source-pad allocations exceed the maintained 2.5-mm bound; revise them before adoption.',
                          'All nine resistor output escapes and complete source group remain to be proved; native-clear partial input groups are insufficient.',
                          'Schematic/PCB matching, guarded replay, preservation and affected complete-group checks remain required before adoption.',
                          'Loaded timing/skew, long VSYNC/R5 detours, PDN/returns/coupling, via-in-pad processing and assembly remain unqualified.',
                          'Unconnected entries are capped native output, not the exact count of unfinished connections.'])
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(f"Trial: {len(d['complete_nets'])}/9 source groups, {index} segments, {len(d['via_positions'])} vias; zero native critical violations")

if __name__ == '__main__':
    main()
