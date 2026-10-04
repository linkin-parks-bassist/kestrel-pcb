#!/usr/bin/env python3
"""Verify every FPGA-sheet switched-supply pad reaches U303 output, not electrical performance."""
import argparse
import json
import pcbnew
from build_fpga_support_supply import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/fpga-support-supply.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==6
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
    refs={'U501','U502','U503','U504','Y501','SW501','J501','L501','L502'}|{f'C{i}'for i in range(501,528)}|{f'R{i}'for i in range(501,520)}
    supply_pads=[p for ref in refs for p in fps[ref].Pads()if p.GetNetname()=='/+3V3_FPGA']
    assert len(supply_pads)==32,len(supply_pads)
    seen,names=connected(pads['U303']['7'])
    assert all(p.m_Uuid.AsString()in seen for p in supply_pads)
    assert all(ident('via',i)in seen for i in range(6))
    assert {'U303.7','U303.8','C310.1'}<=names
    for i,name in enumerate(['C523.1','R505.1','R507.1','R508.1','R510.1','R511.1']):
        ref,num=name.split('.');box=pads[ref][num].GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,name
    result={'status':'PASS all 32 switched-supply pads on the FPGA support sheet physically reach U303 output',
            'track_segments':idx,'vias':6,'all_sheet_switched_supply_pads':32,
            'limits':['SPI-sheet supply continuity is checked separately by check_spi_support_supply.py; Configuration/JTAG/clock and audio signal continuity are checked by their endpoint checkers; Mute-control/sense-net and supervisor-supply continuity is checked by check_audio_mute_local.py; LDO/held-supply and sensed-rail source continuity is checked by check_analogue_power_local.py; DAC supply/pump and full held-rail continuity is checked by check_dac_support_local.py; ADC supply/bypass continuity is checked by check_adc_power_local.py; voltage drop, PDN/noise, effective bypass, current/thermal, intermediate-rail/backfeed and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/fpga-support-supply-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} support supply segments, six vias, all 32 FPGA-sheet switched-supply pads connected; qualification unfinished.')
if __name__=='__main__':main()
