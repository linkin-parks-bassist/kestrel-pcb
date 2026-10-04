#!/usr/bin/env python3
"""Verify twelve audio physical nets and local held-domain buffer branch; operation/timing/performance unqualified."""
import argparse
import json
import pcbnew
from build_fpga_audio_local import ROOT,ident,vec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/fpga-audio-local-routes.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2);assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
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
    # Permit only named, guarded via-in-pad sites; reject all other SMT intersections.
    vip={tuple(site['position']):site['pad'] for site in d.get('via_in_pad_anchors',[])}
    assert len(vip)==len(d.get('via_in_pad_anchors',[]))
    assert set(vip)<=set(map(tuple,d['via_positions']))
    vip_uids={}
    for xy,name in vip.items():
        ref,num=name.split('.');pad=pads[ref][num]
        assert (pad.GetPosition()-vec(d['anchors'][name])).EuclideanNorm()<=2
        vip_uids[xy]=pad.m_Uuid.AsString()
        assert pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD
        v=tracks[ident('via',d['via_positions'].index(list(xy)))];assert v.GetNetname()==pad.GetNetname()
        q=pad.GetBoundingBox();pos=v.GetPosition();r=v.GetDrillValue()/2
        assert q.GetLeft()+r<=pos.x<=q.GetRight()-r and q.GetTop()+r<=pos.y<=q.GetBottom()-r,name
        poly=pad.GetEffectivePolygon(pcbnew.F_Cu)
        assert poly.Contains(pos) and not poly.CollideEdge(pos,None,int(r)),name
    for i in range(len(d['via_positions'])):
        v=tracks[ident('via',i)];pos=v.GetPosition();radius=v.GetDrillValue()/2
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:continue
                q=pad.GetBoundingBox()
                dx=max(q.GetLeft()-pos.x,0,pos.x-q.GetRight())
                dy=max(q.GetTop()-pos.y,0,pos.y-q.GetBottom())
                name=fp.GetReference()+'.'+pad.GetNumber()
                if vip_uids.get(tuple(d['via_positions'][i]))==pad.m_Uuid.AsString():continue
                assert dx*dx+dy*dy>radius*radius,(i,name)
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
    expected={
      '/Bare GW2AR-18 support/MCLK_FPGA':{'U501.25','R513.1'},
      '/Bare GW2AR-18 support/LRCLK_FPGA':{'U501.26','R515.1'},
      '/Bare GW2AR-18 support/BCLK_FPGA':{'U501.29','R514.1'},
      '/Bare GW2AR-18 support/DAC_FPGA':{'U501.31','R516.1'},
      '/Bare GW2AR-18 support/ADC_BUF_RAW':{'U503.4','R519.1'},
      '/Bare GW2AR-18 support/ADC_BUF':{'R519.2','U501.30'},
      '/Bare GW2AR-18 support/ENABLE_FPGA':{'U501.20','R517.1','U504.2'},
      '/ADC_DOUT':{'U201.9','R518.1','U503.2'},
      '/AUDIO_MCLK':{'R513.2','U201.6'},
      '/AUDIO_BCLK':{'R514.2','U201.8','U202.13'},
      '/AUDIO_LRCLK':{'R515.2','U201.7','U202.15'},
      '/DAC_DIN':{'R516.2','U202.14'},
    }
    lengths={}
    for net,names in expected.items():
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names==connected_names,(net,names-connected_names,connected_names-names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    # Only this local held-domain branch is claimed: other DAC/LDO/mute loads remain unrouted.
    held={'U205.5','C527.1','U504.5'};seen,held_names=connected(pads['U205']['5'])
    assert held<=held_names,held-held_names
    assert all(pads[r][n].GetNetname()=='/+3V3_A'for r,n in [name.split('.')for name in held])
    assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n=='/+3V3_A')
    lengths['/+3V3_A local U504 branch']=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()=='/+3V3_A')
    for ref in ['R513','R514','R515','R516','R519']:
        first,_=connected(pads[ref]['1']);second,_=connected(pads[ref]['2']);assert not first&second,ref
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    for net,names in expected.items():
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')}
        assert xml_names==names,(net,xml_names,names)
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_fpga_audio_local_track_ids']==[ident('track',i)for i in range(idx)]
        assert report['provisional_fpga_audio_local_via_ids']==[ident('via',i)for i in range(len(d['via_positions']))]
    result={'status':'PASS twelve FPGA/converter audio signal nets and local held-DAC buffer supply have physical continuity',
            'track_segments':idx,'vias':len(d['via_positions']),'via_in_pad_sites':d.get('via_in_pad_anchors',[]),'routed_planar_length_mm':lengths,
            'limits':['Planar branch lengths exclude via depth and do not establish timing, source damping or return behavior.','Mute-control/sense-net and supervisor-supply continuity is checked by check_audio_mute_local.py; LDO/held-supply and sensed-rail source continuity is checked by check_analogue_power_local.py; DAC supply/pump and full held-rail continuity is checked by check_dac_support_local.py; ADC supply/bypass continuity is checked by check_adc_power_local.py; Analogue signal/bias, protected supply and ground continuity is checked by check_analogue_signal_local.py. Powered source/LDO behavior remains unqualified. Clock/backend RTL migration, converter mode setup, audio quality/latency, power sequencing/backfeed, loaded timing/noise/returns and via-in-pad fabrication/assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/fpga-audio-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} endpoint segments, {len(d["via_positions"])} vias; complete FPGA/converter signal nets and local U504 held supply; qualification unfinished.')
    print(lengths)
if __name__=='__main__':main()
