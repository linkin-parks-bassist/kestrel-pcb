#!/usr/bin/env python3
"""Verify local buck copper continuity, not load, loop or thermal qualification."""
import argparse
import json
import pcbnew
from build_buck5v_local import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/buck5v-local-routes.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==13
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
    groups=[{'U101.3','C101.1','C102.1','R104.1'},
            {'U101.2','L101.1','C103.2'}, {'U101.6','C103.1'},
            {'L101.2','C104.1','C105.1','R101.1'},
            {'R101.2','R102.1','C106.1'},
            {'U101.4','R103.1','R102.2','C106.2'},
            {'U101.5','R104.2','R105.1'},
            {'U101.1','C101.2','C102.2','C104.2','C105.2','R103.2','R105.2'}]
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0))
    assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    for expected in groups:
        ref,num=sorted(expected)[0].split('.');seen,names=connected(pads[ref][num])
        assert expected<=names,expected-names
        net=pads[ref][num].GetNetname()
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        if net=='/GND':assert zone.m_Uuid.AsString()in seen
    # Ground-return drill circles remain outside their associated SMT lands.
    ground_names=['C101.2','C102.2','U101.1','C104.2','C105.2','R103.2','R105.2']
    ground_vias=[i for i,n in enumerate(d['via_net_names'])if n=='/GND']
    assert len(ground_vias)==len(ground_names)==7
    for name,i in zip(ground_names,ground_vias):
        ref,num=name.split('.');box=pads[ref][num].GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,name
    result={'status':'PASS eight local buck net groups physically connected; all seven ground returns reach filled plane',
            'track_segments':idx,'vias':13,'limits':['Protected-input feed continuity is checked by check_input_power_local.py; FPGA feed continuity is checked by check_fpga_main_feeds.py; other output distribution is unfinished; effective capacitance, loop, current/thermal and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/buck5v-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} buck segments, 13 vias, eight local net groups and ground plane continuity; electrical qualification unfinished.')
if __name__=='__main__':main()
