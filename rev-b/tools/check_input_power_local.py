#!/usr/bin/env python3
"""Verify input copper and both protected buck feeds, not fault/current/thermal qualification."""
import argparse
import json
import pcbnew
from build_input_power_local import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/input-power-local-routes.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==9
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
    groups=[{'J401.2','F401.1','TP401.1'},
            {'F401.2','Q401.5','Q401.6','Q401.7','Q401.8'},
            {'Q401.1','Q401.2','Q401.3','D401.1','C401.1','C402.1','TP402.1','C101.1','C107.1','U101.3','U102.3'},
            {'Q401.4','R401.1'},
            {'J401.1','D401.2','C401.2','C402.2','R401.2','TP403.1'}]
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0))
    assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    for expected in groups:
        ref,num=sorted(expected)[0].split('.');seen,names=connected(pads[ref][num])
        assert expected<=names,expected-names
        net=pads[ref][num].GetNetname()
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        if net=='/GND':assert zone.m_Uuid.AsString()in seen
    # Ground-return drill circles remain outside their associated SMT lands.
    ground_names=['D401.2','C401.2','C402.2','R401.2','TP403.1']
    ground_vias=[i for i,n in enumerate(d['via_net_names'])if n=='/GND']
    assert len(ground_vias)==len(ground_names)==5
    for name,i in zip(ground_names,ground_vias):
        ref,num=name.split('.');box=pads[ref][num].GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,name
    result={'status':'PASS five local input net groups physically connected; five new ground returns and jack ground reach filled plane',
            'track_segments':idx,'vias':9,'limits':['Other protected loads and main output distribution remain unfinished; effective capacitance, source/load/current/fault/thermal and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/input-power-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} input segments, nine vias, five input net groups and ground plane continuity; electrical qualification unfinished.')
if __name__=='__main__':main()
