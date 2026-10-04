#!/usr/bin/env python3
"""Native HP source-to-four-MCU-pin continuity and bulk ground, not load/loop proof."""
import argparse
import json
import pcbnew
from build_mcu_hp_distribution import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/mcu-hp-distribution.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
        if route['layer']=='In2.Cu':assert route['width_mm']>=.508
    assert len(d['via_positions'])==8
    for i,xy in enumerate(d['via_positions']):
        v=tracks[ident('via',i)];assert isinstance(v,pcbnew.PCB_VIA) and v.GetPosition()==vec(xy)
        assert v.GetNetname()==d['via_net_names'][i] and v.GetDrillValue()==pcbnew.FromMM(.3) and v.GetViaType()==pcbnew.VIATYPE_THROUGH
        assert v.TopLayer()==pcbnew.F_Cu and v.BottomLayer()==pcbnew.B_Cu
        assert all(v.IsOnLayer(layer) and v.GetWidth(layer)==pcbnew.FromMM(d['via_diameters_mm'][i])for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu])
    conn=b.GetConnectivity();conn.Build(b)
    def connected(seed):
        pending=[seed];seen=set();names=set()
        while pending:
            item=pending.pop();uid=item.m_Uuid.AsString()
            if uid in seen:continue
            seen.add(uid)
            if isinstance(item,pcbnew.PAD):names.add(item.GetParentFootprint().GetReference()+'.'+item.GetNumber())
            pending.extend(conn.GetConnectedItems(item))
        return seen,names
    seen,names=connected(pads['L601']['2']);expected={'U701.26','U701.54','U701.76','U701.91','C710.1','C711.1','C712.1','C713.1','C721.1','C603.1','C604.1','R601.1','C605.1'}
    assert expected<=names,expected-names
    assert all(ident('via',i)in seen for i in range(7))
    seen_ground,_=connected(pads['C721']['2']);assert ident('via',7)in seen_ground and hp_ident('zone',0)in seen_ground
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    result={'status':'PASS HP regulator output physically reaches all four MCU HP inputs, local bypasses and C721; C721 ground reaches inner plane',
            'connected_hp_pads':sorted(expected),'added_track_segments':idx,'added_hp_vias':7,'added_bulk_ground_vias':1,
            'inner_power_layer':'In2.Cu','inner_branch_minimum_width_mm':.508,
            'limits':['HP regulator input remains incomplete; EN/FB continuity is checked separately by check_mcu_hp_controls.py; current silicon startup/controlled loop behavior is unverified.',
                      'Existing 0.127-mm terminal/bypass escapes remain provisional; wider distribution alone does not qualify current, voltage drop, transient/decoupling, stackup or assembly.']}
    if not args.trial:(ROOT/'generated/mcu-hp-distribution-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} distribution/return segments, seven HP vias and one bulk ground via; L601 output reaches all four MCU HP pins and C721; qualification incomplete.')
if __name__=='__main__':main()
