#!/usr/bin/env python3
"""Verify regulator-to-FPGA core rail physical continuity, not electrical performance."""
import argparse
import json
import pcbnew
from build_fpga_core_distribution import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/fpga-core-distribution.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==7
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
    expected={'L301.2','C302.1','C303.1','C521.1','L501.1','L502.1','C501.1','C505.1','C508.1','C512.1','U501.1','U501.22','U501.45','U501.66'}
    seen,names=connected(pads['L301']['2'])
    assert expected<=names,expected-names
    assert all(pads[ref][num].GetNetname()=='/+1V0_FPGA'for ref,num in (name.split('.')for name in expected))
    assert all(ident('via',i)in seen for i in range(7))
    # Distribution vias are outside the supplied SMT lands.
    for i,name in enumerate(['C501.1','C505.1','C508.1','C512.1','C521.1','L501.1','L502.1']):
        ref,num=name.split('.');box=pads[ref][num].GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,name
    result={'status':'PASS L301 output physically reaches all four U501 core pins, their bypasses, C521 bulk and both PLL bead inputs',
            'track_segments':idx,'vias':7,'limits':['FPGA I/O pin/bulk and assigned support continuity are checked separately by check_fpga_io_distribution.py; remaining switched support supplies are checked separately by check_fpga_support_supply.py; SPI supply continuity is checked separately by check_spi_support_supply.py; local held-DAC buffer supply continuity is checked separately by check_fpga_audio_local.py; other main loads remain unfinished; voltage drop, current, PDN/PLL noise, effective capacitance, thermal and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/fpga-core-distribution-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} core distribution segments, seven vias; regulator output reaches four core pins, bulk and both bead inputs; qualification unfinished.')
if __name__=='__main__':main()
