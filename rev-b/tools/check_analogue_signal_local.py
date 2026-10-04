#!/usr/bin/env python3
"""Verify complete analogue nets, protected supply branch and sixteen ground returns; operation unqualified."""
import argparse
import json
import pcbnew
from build_analogue_signal_local import ROOT,ident,vec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/analogue-signal-local-routes.json').read_text())
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
        ref,num=name.split('.');pad=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(d['anchors'][name])).EuclideanNorm()<=2)
        assert (pad.GetPosition()-vec(d['anchors'][name])).EuclideanNorm()<=2
        vip_uids[xy]={p.m_Uuid.AsString()for p in fps[ref].Pads()if p.GetNumber()==num and p.IsOnLayer(pcbnew.F_Cu)}
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
                if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD or not pad.IsOnLayer(pcbnew.F_Cu):continue
                q=pad.GetBoundingBox()
                dx=max(q.GetLeft()-pos.x,0,pos.x-q.GetRight())
                dy=max(q.GetTop()-pos.y,0,pos.y-q.GetBottom())
                name=fp.GetReference()+'.'+pad.GetNumber()
                if pad.m_Uuid.AsString()in vip_uids.get(tuple(d['via_positions'][i]),set()):continue
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
    expected={'/Hardware ADC and DAC/ADC_AC_L': {'R201.1', 'C201.2'}, '/Hardware ADC and DAC/ADC_IN_L': {'U201.13', 'C202.1', 'R201.2'}, '/Hardware ADC and DAC/ADC_IN_R': {'C203.2', 'U201.14'}, '/Hardware ADC and DAC/AFE_OUT': {'C201.1', 'R210.2', 'R211.1'}, '/Hardware ADC and DAC/AUDIO_IN': {'R207.1', 'C221.1', 'D201.1', 'J201.T'}, '/Hardware ADC and DAC/AUDIO_OUT': {'R206.2', 'C220.1', 'D203.1', 'J202.T'}, '/Hardware ADC and DAC/BIAS_BUF': {'U203.7', 'U203.6', 'R214.1'}, '/Hardware ADC and DAC/BIAS_RAW': {'U203.5', 'C222.1', 'R212.2', 'R213.1'}, '/Hardware ADC and DAC/DAC_OUT_L': {'R206.1', 'U202.6'}, '/Hardware ADC and DAC/INPUT_AC': {'R208.1', 'C221.2'}, '/Hardware ADC and DAC/IN_BIAS': {'R209.1', 'R208.2', 'D202.3', 'U203.3'}, '/Hardware ADC and DAC/IN_BUF': {'R210.1', 'U203.2', 'U203.1'}, '/Hardware ADC and DAC/VMID': {'R214.2', 'R209.2', 'R211.2', 'C223.1'}, '/9V_PROTECTED': {'R212.1', 'U203.8', 'C224.1', 'C225.1', 'D202.2', 'C226.1'}}
    assert {n:set(v)for n,v in d["expected_nets"].items()}==expected
    lengths={}
    for net,names in expected.items():
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names<=connected_names,(net,names-connected_names)
        if net!='/9V_PROTECTED':assert names==connected_names,(net,connected_names-names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    from build_hp_ground import ident as hp_ident
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    ground_seen,ground_names=connected(zone)
    assert set(d['ground_anchors'])<=ground_names,set(d['ground_anchors'])-ground_names
    assert all(ident('via',i)in ground_seen for i,n in enumerate(d['via_net_names'])if n=='/GND')
    ground_refs=['U203','R207','R213','C202','C203','C220','C222','C223','C224','C225','D201','D202','D203','J201','J202']
    ground_pads=[p for ref in ground_refs for p in fps[ref].Pads()if p.GetNetname()=='/GND']
    assert len(ground_pads)==16 and all(p.m_Uuid.AsString()in ground_seen for p in ground_pads)
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    for net,names in expected.items():
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')}
        assert names<=xml_names,(net,xml_names,names)
        if net!='/9V_PROTECTED':assert xml_names==names,(net,xml_names,names)
    audio_refs={c.attrib['ref']for c in xml.findall('.//components/comp')if c.find('sheetpath').attrib['names']=='/Hardware ADC and DAC/'}
    assert len(audio_refs)==68 and audio_refs<=set(fps)
    audio_ground_pads=[p for ref in audio_refs for p in fps[ref].Pads()if p.GetNetname()=='/GND'and (p.IsOnLayer(pcbnew.F_Cu)or p.IsOnLayer(pcbnew.B_Cu))]
    xml_grounds={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']=='/GND'for node in n.findall('node')if node.attrib['ref']in audio_refs}
    physical_grounds={p.GetParentFootprint().GetReference()+'.'+p.GetNumber()for p in audio_ground_pads}
    assert physical_grounds==xml_grounds and len(audio_ground_pads)==65
    assert all(p.m_Uuid.AsString()in ground_seen for p in audio_ground_pads)
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_analogue_signal_local_track_ids']==[ident('track',i)for i in range(idx)]
        assert report['provisional_analogue_signal_local_via_ids']==[ident('via',i)for i in range(len(d['via_positions']))]
    result={'status':'PASS thirteen complete analogue signal/bias nets, protected supply branch and sixteen ground returns',
            'track_segments':idx,'vias':len(d['via_positions']),'via_in_pad_sites':d.get('via_in_pad_anchors',[]),'routed_planar_length_mm':lengths,'complete_local_nets':{net:sorted(names)for net,names in expected.items()},'ground_anchors':d['ground_anchors'],'complete_audio_sheet_ground_copper_shapes':65,'complete_audio_sheet_ground_pads':sorted(physical_grounds),
            'limits':['Other main power and remaining board placement/routing are unfinished.','Physical topology only; analogue feedback/bias stability, effective bypass/return impedance, rail drop/current/thermal, protection/transients, coupling/noise, sequencing/backfeed and audio performance and via-in-pad fabrication/assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/analogue-signal-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} analogue segments, {len(d["via_positions"])} vias; thirteen complete analogue signal/bias nets, protected source branch and sixteen ground returns; qualification unfinished.')
    print(lengths)
if __name__=='__main__':main()
