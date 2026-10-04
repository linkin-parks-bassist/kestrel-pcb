#!/usr/bin/env python3
"""Verify local buck copper continuity, not load, loop or thermal qualification."""
import argparse
import json
import pcbnew
from build_fpga_main_feeds import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/fpga-main-feeds.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==2
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
    groups=[{'L101.2','C104.1','C105.1','C301.1','U301.1','U301.4','C308.1','U303.4'},
            {'L102.2','C110.1','C111.1','C113.1','C307.1','U303.1','U303.2','C306.1','U302.1','U302.6','R305.1'}]
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0))
    assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    for expected in groups:
        ref,num=sorted(expected)[0].split('.');seen,names=connected(pads[ref][num])
        assert expected<=names,expected-names
        net=pads[ref][num].GetNetname()
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        if net=='/GND':assert zone.m_Uuid.AsString()in seen
    result={'status':'PASS main-buck source-to-FPGA core/bias and supervisor/I-O supply groups physically connected',
            'track_segments':idx,'vias':2,'limits':['Local core/sequencing continuity is checked separately; FPGA core distribution is checked separately by check_fpga_core_distribution.py; FPGA I/O pin/bulk and assigned support continuity are checked separately by check_fpga_io_distribution.py; remaining switched support supplies are checked separately by check_fpga_support_supply.py; SPI supply continuity is checked separately by check_spi_support_supply.py; local held-DAC buffer supply continuity is checked separately by check_fpga_audio_local.py; other main loads remain unfinished; voltage drop, source/load budget, return impedance, current/thermal, sequence and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/fpga-main-feeds-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} FPGA main-feed segments, two vias and both buck-to-FPGA supply groups; electrical qualification unfinished.')
if __name__=='__main__':main()
