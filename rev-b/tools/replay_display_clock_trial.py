#!/usr/bin/env python3
"""Replay one isolated clock/RGB coordination experiment and check its bounded groups."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import uuid
import xml.etree.ElementTree as ET
import pcbnew

ROOT = Path(__file__).resolve().parents[1]

def vec(xy):
    return pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in xy))

def pos(v):
    return [pcbnew.ToMM(v.x), pcbnew.ToMM(v.y)]

def geometry(t):
    d = dict(uuid=t.m_Uuid.AsString(), net=t.GetNetname(), start=pos(t.GetStart()), end=pos(t.GetEnd()), layer=t.GetLayerName())
    if isinstance(t, pcbnew.PCB_VIA):
        d.update(diameter_mm=pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu)), drill_mm=pcbnew.ToMM(t.GetDrillValue()), span=[t.TopLayer(), t.BottomLayer()])
    else:
        d['width_mm'] = pcbnew.ToMM(t.GetWidth())
    return d

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--variant', required=True, choices=['paired_rgb', 'dual_clock_rgb'])
    p.add_argument('--output', required=True, type=Path, help='New trial board in a new directory')
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--verify-snapshot', type=Path, help='Require byte-identical replay of a saved trial board')
    a = p.parse_args()
    assert not a.output.exists() and not a.output.parent.exists(), 'Use a new isolated output directory'
    d = json.loads((ROOT/'generated/trials/display-clock-coordination.json').read_text())
    baseline = ROOT/'generated/trials/display-timing.kicad_pcb'
    assert hashlib.sha256(baseline.read_bytes()).hexdigest() == d['baseline_trial_sha256']
    profile_sha = hashlib.sha256(baseline.with_suffix('.kicad_pro').read_bytes()).hexdigest()
    assert profile_sha == 'd8cd8096a998bb6577948be69a5f9bcb244f0e77d4c978c0243dbf85f5cef905'
    assert profile_sha == hashlib.sha256((ROOT/'electrical/kestrel-revb.kicad_pro').read_bytes()).hexdigest()
    b = pcbnew.LoadBoard(str(baseline))
    tracks = {t.m_Uuid.AsString():t for t in b.GetTracks()}
    before = {u:geometry(t) for u,t in tracks.items()}
    det = []
    v = d['variants'][a.variant]
    removals = d['removed'] + v.get('extra_removed', [])
    assert len({g['uuid'] for g in removals}) == len(removals)
    for g in removals:
        t = tracks[g['uuid']]
        assert geometry(t) == g, 'Removal geometry changed'
        b.Remove(t)
        det.append(t)
    fps = {f.GetReference():f for f in b.GetFootprints()}
    original = {r:(f.GetPosition(),f.GetOrientationDegrees()) for r,f in fps.items()}
    for ref, (x,y,angle) in v['poses'].items():
        old_xy = {'R1017':[122.65,81.3], 'R1018':[121.7,81.34], 'R1011':[121.9,77.7]}
        assert original[ref] == (vec(old_xy[ref]),90)
        fps[ref].SetOrientationDegrees(angle)
        fps[ref].SetPosition(vec([x,y]))
    added = set()
    for route in v['routes']:
        q = route['proposal']
        assert q['via_diameter_mm'] == .5 and q['via_drill_mm'] == .3
        def ident(kind, i):
            return str(uuid.uuid5(uuid.NAMESPACE_URL, f"kestrel/rev-b/{route['namespace']}/{kind}/{i}"))
        i = 0
        for path in q['paths']:
            assert path['width_mm'] == .127 and path['net'] == q['net']
            for start,end in zip(path['points'], path['points'][1:]):
                t = pcbnew.PCB_TRACK(b)
                t.SetUuid(pcbnew.KIID(ident('track',i)))
                i += 1
                t.SetStart(vec(start)); t.SetEnd(vec(end)); t.SetWidth(pcbnew.FromMM(.127))
                t.SetLayer(b.GetLayerID(path['layer'])); t.SetNetCode(b.FindNet(q['net']).GetNetCode())
                assert t.m_Uuid.AsString() not in before
                b.Add(t); added.add(t.m_Uuid.AsString())
        for i,xy in enumerate(q['via_positions']):
            t = pcbnew.PCB_VIA(b)
            t.SetUuid(pcbnew.KIID(ident('via',i))); t.SetPosition(vec(xy))
            t.SetWidth(pcbnew.FromMM(.5)); t.SetDrill(pcbnew.FromMM(.3))
            t.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu); t.SetViaType(pcbnew.VIATYPE_THROUGH)
            t.SetNetCode(b.FindNet(q['net']).GetNetCode())
            assert t.m_Uuid.AsString() not in before
            b.Add(t); added.add(t.m_Uuid.AsString())
    remaining = {u:g for u,g in before.items() if u not in {r['uuid'] for r in removals}}
    assert {t.m_Uuid.AsString():geometry(t) for t in b.GetTracks() if t.m_Uuid.AsString() not in added} == remaining
    assert all((f.GetPosition(),f.GetOrientationDegrees()) == original[r] for r,f in fps.items() if r not in v['poses'])
    assert pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    a.output.parent.mkdir(parents=True)
    pcbnew.SaveBoard(str(a.output),b)
    shutil.copyfile(baseline.with_suffix('.kicad_pro'),a.output.with_suffix('.kicad_pro'))
    shutil.copytree(baseline.parent/'KestrelTiming.pretty',a.output.parent/'KestrelTiming.pretty')
    table = (baseline.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}/../../electrical/',str(ROOT/'electrical')+'/')
    (a.output.parent/'fp-lib-table').write_text(table)
    drc_path = a.output.parent/'drc.json'
    subprocess.run(['kicad-cli','pcb','drc','--format','json','-o',str(drc_path),str(a.output)],check=True,stdout=subprocess.DEVNULL)
    drc = json.loads(drc_path.read_text())
    residual = {'silk_overlap','silk_over_copper','silk_edge_clearance','drill_out_of_range','track_dangling','via_dangling'}
    assert not [r for r in drc['violations'] if r['type'] not in residual]
    assert sum(r['type']=='drill_out_of_range' for r in drc['violations']) == 6
    for kind,index in [('track',19),('via',7)]:
        pending_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL,f'kestrel/rev-b/display-timing-source-routes/{kind}/{index}'))
        actual = {it['uuid'] for r in drc['violations'] if r['type']==kind+'_dangling' for it in r['items']}
        assert actual == {pending_uuid}, (kind,actual)
    b = pcbnew.LoadBoard(str(a.output)); conn = b.GetConnectivity(); conn.Build(b)
    pads = {f.GetReference()+'.'+p.GetNumber():p for f in b.GetFootprints() for p in f.Pads()}
    via_margins = {}
    for via in b.GetTracks():
        if not isinstance(via,pcbnew.PCB_VIA) or via.m_Uuid.AsString() not in added:
            continue
        nearest = None
        for f in b.GetFootprints():
            for pad in f.Pads():
                if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:
                    continue
                q = pad.GetBoundingBox(); center = via.GetPosition()
                distance = pcbnew.ToMM(round(math.hypot(max(q.GetLeft()-center.x,center.x-q.GetRight(),0),max(q.GetTop()-center.y,center.y-q.GetBottom(),0))))
                own = pad.GetLocalClearance()
                own = f.GetLocalClearance() if own is None else own
                copper_rule = pcbnew.ToMM(own) if own is not None else .2
                copper = distance - .25; hole = distance - .15
                assert copper >= copper_rule-1e-6 and hole >= .25-1e-6, (via.m_Uuid.AsString(),f.GetReference(),pad.GetNumber(),copper,hole)
                if nearest is None or distance < nearest['distance_to_land_mm']:
                    nearest = dict(pad=f.GetReference()+'.'+pad.GetNumber(),distance_to_land_mm=distance,annulus_clearance_mm=copper,required_copper_clearance_mm=copper_rule,hole_clearance_mm=hole,required_hole_clearance_mm=.25)
        via_margins[via.m_Uuid.AsString()] = dict(position_mm=pos(via.GetPosition()),nearest_smd_land=nearest)
    def connected(name):
        todo,seen,names = [pads[name]],set(),set()
        while todo:
            it = todo.pop(); u = it.m_Uuid.AsString()
            if u in seen: continue
            seen.add(u)
            if isinstance(it,pcbnew.PAD): names.add(it.GetParentFootprint().GetReference()+'.'+it.GetNumber())
            todo.extend(conn.GetConnectedItems(it))
        return names
    xml = ET.parse(ROOT/'generated/revb-netlist.xml')
    groups = {}
    for half in ['source','output']:
        rgb = json.loads((ROOT/f'electrical/display-rgb-{half}-routes.json').read_text())
        for key,names in rgb['expected_groups'].items():
            net = key.rsplit(':',1)[0]; label = half+':'+net
            xml_names = {n.attrib['ref']+'.'+n.attrib['pin'] for e in xml.findall('.//nets/net') if e.attrib['name']==net for n in e.findall('node')}
            assert xml_names == set(names) and all(pads[n].GetNetname()==net for n in names)
            seed = 'U701.92' if label=='source:/MCU_LCD_G7' else 'R1010.2' if label=='output:/RGB565 and capacitive touch/LCD_G6' else names[0]
            expected = {seed} if label in v['pending_rgb_groups'] else xml_names
            assert connected(seed) == expected, label
            groups[label] = sorted(expected)
    timing = json.loads((baseline.parent/'display-timing-source.json').read_text())
    for name in timing['via_in_pad_anchors'] + v.get('additional_source_via_in_pad', []):
        pad = pads[name]
        net = pad.GetNetname()
        candidates = [t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()==net]
        assert len(candidates)==1
        via = candidates[0]; poly = pad.GetEffectivePolygon(pcbnew.B_Cu)
        assert poly.Contains(via.GetPosition()) and not poly.CollideEdge(via.GetPosition(),None,pcbnew.FromMM(.15)), name
    source_groups = {}
    for pin,ref in zip([94,97,12,13,14,16,17,18,19],range(1017,1026)):
        name=f'U701.{pin}'; net=pads[name].GetNetname(); target=f'R{ref}.1'
        assert net==timing['anchor_nets'][name] and pads[target].GetNetname()==net
        expected={name,target} if net in timing['complete_nets'] else {name}
        assert connected(name)==expected, net
        source_groups[net]=sorted(expected)
    clock_groups={}
    for signal,ref,pin in [('PCLK',1017,30),('HSYNC',1018,32)]:
        seed=f'R{ref}.2'; expected={seed,f'J1001.{pin}'} if signal in v['complete_clock_outputs'] else {seed}
        assert connected(seed)==expected, signal
        clock_groups[signal]=sorted(expected)
    result=dict(variant=a.variant,baseline_sha256=d['baseline_trial_sha256'],trial_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),native_critical_violations=0,native_residual_counts=dict(Counter(r['type'] for r in drc['violations'])),preserved_copper_items=len(remaining),removed_copper_items=len(det),added_copper_items=len(added),physical_rgb_groups=groups,physical_timing_source_groups=source_groups,physical_clock_output_groups=clock_groups,limits=d['limits'])
    result['route_planar_length_mm'] = {r['proposal']['net']:sum(math.dist(x,y) for path in r['proposal']['paths'] for x,y in zip(path['points'],path['points'][1:])) for r in v['routes']}
    result['manufacturing_profile_sha256'] = profile_sha
    result['new_via_smd_margins'] = via_margins
    if a.verify_snapshot:
        assert hashlib.sha256(a.verify_snapshot.read_bytes()).hexdigest() == result['trial_sha256'], 'Saved trial differs from guarded replay'
    a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(a.variant, 'native-clear; pending RGB halves:',v['pending_rgb_groups'],'complete clock outputs:',v['complete_clock_outputs'])

if __name__=='__main__':
    main()
