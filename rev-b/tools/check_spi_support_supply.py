#!/usr/bin/env python3
"""Verify every SPI-sheet supply pad reaches its actual source, not electrical performance."""
import argparse
import json
import pcbnew
from build_spi_support_supply import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/spi-support-supply.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2);assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==11
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
    refs={'U801','U802','U803'}|{f'C{i}'for i in range(801,806)}|{f'R{i}'for i in range(801,812)}
    counts={}
    for net,source,expected in [('/+3V3_D',pads['L102']['2'],12),('/+3V3_FPGA',pads['U303']['7'],4)]:
        supply_pads=[p for ref in refs for p in fps[ref].Pads()if p.GetNetname()==net]
        assert len(supply_pads)==expected,(net,len(supply_pads))
        seen,names=connected(source)
        assert all(p.m_Uuid.AsString()in seen for p in supply_pads),(net,names)
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        counts[net]=len(supply_pads)
    assert {'L102.2','C110.1'}<=connected(pads['U801']['16'])[1]
    assert {'U303.7','U303.8','C310.1'}<=connected(pads['U801']['15'])[1]
    assert len(d['supply_returns'])==11
    for guard in d['supply_returns']:
        ref,num=guard['anchor'].split('.');p=pads[ref][num];i=guard['via_index']
        assert p.GetNetname()==d['via_net_names'][i]
        box=p.GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,guard
    result={'status':'PASS all 12 main and four switched SPI-sheet supply pads physically reach their proper sources',
            'track_segments':idx,'vias':11,'sheet_supply_pads':counts,
            'limits':['Control routing is checked separately by check_spi_control_local.py; SPI data/clock/CS routes remain unfinished; voltage drop, PDN/noise, effective bypass, intermediate-rail/backfeed, SI/timing and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/spi-support-supply-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} supply segments, 11 vias, all 16 SPI-sheet supply pads reach their proper sources; qualification unfinished.')
if __name__=='__main__':main()
