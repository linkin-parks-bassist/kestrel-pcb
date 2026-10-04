#!/usr/bin/env python3
"""Native HP source-to-four-MCU-pin continuity and bulk ground, not load/loop proof."""
import argparse
import json
import pcbnew
from build_mcu_hp_controls import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/mcu-hp-controls.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
        if route['layer']=='In2.Cu':assert route['width_mm']>=.508
    assert len(d['via_positions'])==4
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
    for seed, expected, vias in [('79', {'U701.79','U601.1'},[0,1]), ('78',{'U701.78','U601.5','R601.2','R602.1','C605.2'},[2,3])]:
        seen,names=connected(pads['U701'][seed]);assert expected<=names,expected-names
        assert all(ident('via',i)in seen for i in vias)
    result={'status':'PASS MCU enable and feedback pads physically connected to HP regulator and feedback divider',
            'track_segments':idx,'vias':4,'limits':['Regulator input and controlled-loop/noise/assembly qualification remain incomplete.']}
    if not args.trial:(ROOT/'generated/mcu-hp-controls-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} control segments and four vias; MCU EN/FB reach regulator and feedback divider; loop qualification unfinished.')
if __name__=='__main__':main()
