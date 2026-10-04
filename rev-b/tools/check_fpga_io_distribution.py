#!/usr/bin/env python3
"""Verify switched I/O rail reaches FPGA pins, bulk and connected support, not power performance."""
import argparse
import json
import pcbnew
from build_fpga_io_distribution import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/fpga-io-distribution.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=pads[ref][num];assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==len(d['via_net_names'])==len(d['via_diameters_mm'])
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
    expected={'U303.7','U303.8','C310.1','C522.1','C525.1','C524.1','Y501.1','Y501.4','U503.5','C526.1','J501.6'}|{f'U501.{i}'for i in [3,12,23,44,58,64,67,78]}|{f'C{i}.1'for i in [502,503,506,507,510,511,513,514]}
    seen,names=connected(pads['U303']['7'])
    assert expected<=names,expected-names
    assert all(pads[ref][num].GetNetname()=='/+3V3_FPGA'for ref,num in (name.split('.')for name in expected))
    assert all(ident('via',i)in seen for i in range(len(d['via_positions'])))
    # Every owned through-via drill lies outside every SMT land.
    for i in range(len(d['via_positions'])):
        pos=tracks[ident('via',i)].GetPosition();radius=pcbnew.FromMM(.3)/2
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:continue
                q=pad.GetBoundingBox();dx=max(q.GetLeft()-pos.x,0,pos.x-q.GetRight());dy=max(q.GetTop()-pos.y,0,pos.y-q.GetBottom())
                assert dx*dx+dy*dy>radius*radius,(i,fp.GetReference(),pad.GetNumber())
    result={'status':'PASS U303 switched output physically reaches all eight FPGA I/O pins/bypasses, C522 bulk, C525, oscillator, ADC buffer and JTAG VREF',
            'track_segments':idx,'vias':len(d['via_positions']),'limits':['Flash/pullup continuity is checked separately by check_fpga_support_supply.py; SPI supply continuity is checked separately by check_spi_support_supply.py; local held-DAC buffer supply and audio signals are checked separately by check_fpga_audio_local.py; Mute-control/sense-net and supervisor-supply continuity is checked by check_audio_mute_local.py; LDO/held-supply and sensed-rail source continuity is checked by check_analogue_power_local.py; DAC supply/pump and full held-rail continuity is checked by check_dac_support_local.py; ADC supply/bypass continuity is checked by check_adc_power_local.py; Analogue signal/bias, protected supply and ground continuity is checked by check_analogue_signal_local.py; rail drop, transient PDN/noise, effective capacitance, current/thermal, power-off/backfeed and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/fpga-io-distribution-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} I/O distribution segments, {len(d["via_positions"])} vias; switched output reaches eight FPGA I/O pins, bulk and assigned support supplies; qualification unfinished.')
if __name__=='__main__':main()
