#!/usr/bin/env python3
"""Verify footswitch physical nets, supply branch and ten ground returns; operation unqualified."""
import argparse
import json
import pcbnew
from build_footswitch_local import ROOT,ident,vec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/footswitch-local-routes.json').read_text())
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
    expected={'/Two momentary footswitch inputs/FOOT_RAW_0': {'J1101.1', 'R1101.1', 'D1101.1'}, '/Two momentary footswitch inputs/FOOT_RC_0': {'R1101.2', 'U1101.2', 'R1102.2', 'C1101.1'}, '/Two momentary footswitch inputs/FOOT_BUF_0': {'U1101.4', 'R1103.1'}, '/MCU_FOOT0_N': {'U701.22', 'R1103.2'}, '/Two momentary footswitch inputs/FOOT_RAW_1': {'R1104.1', 'J1102.1', 'D1102.1'}, '/Two momentary footswitch inputs/FOOT_RC_1': {'C1103.1', 'R1105.2', 'R1104.2', 'U1102.2'}, '/Two momentary footswitch inputs/FOOT_BUF_1': {'U1102.4', 'R1106.1'}, '/MCU_FOOT1_N': {'U701.23', 'R1106.2'}, '/+3V3_D': {'R1105.1', 'R1102.1', 'U1101.5', 'L102.2', 'U1102.5', 'C1102.1', 'C1104.1'}}
    lengths={}
    for net,names in expected.items():
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names<=connected_names,(net,names-connected_names)
        if net!="/+3V3_D":assert names==connected_names,(net,connected_names-names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        if net=='/+3V3_D':
            source=[t for t in b.GetTracks()if isinstance(t,pcbnew.PCB_VIA)and t.GetPosition()==vec(d['source_via'])and t.GetNetname()==net]
            assert len(source)==1 and source[0].m_Uuid.AsString()==d['source_via_id']and source[0].m_Uuid.AsString()in seen
        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    from build_hp_ground import ident as hp_ident
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    ground_seen,ground_names=connected(zone)
    assert set(d['ground_anchors'])<=ground_names,set(d['ground_anchors'])-ground_names
    assert all(ident('via',i)in ground_seen for i,n in enumerate(d['via_net_names'])if n=='/GND')
    foot_refs=['J1101','J1102','D1101','D1102','R1101','R1102','R1103','R1104','R1105','R1106','C1101','C1102','C1103','C1104','U1101','U1102']
    ground_pads=[p for ref in foot_refs for p in fps[ref].Pads()if p.GetNetname()=='/GND']
    assert len(ground_pads)==10 and all(p.m_Uuid.AsString()in ground_seen for p in ground_pads)
    assert set(d['ground_anchors'])=={p.GetParentFootprint().GetReference()+'.'+p.GetNumber()for p in ground_pads}
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    for net,names in expected.items():
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')if node.attrib['ref']not in ['SW1101','SW1102']}
        assert names<=xml_names,(net,xml_names,names)
        if net!="/+3V3_D":assert xml_names==names,(net,xml_names,names)
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_footswitch_local_track_ids']==[ident('track',i)for i in range(idx)]
        assert report['provisional_footswitch_local_via_ids']==[ident('via',i)for i in range(len(d['via_positions']))]
    result={'status':'PASS eight complete footswitch signal nets, source-to-load supply branch and ten plane-ground returns',
            'track_segments':idx,'vias':len(d['via_positions']),'via_in_pad_sites':d.get('via_in_pad_anchors',[]),'routed_planar_length_mm':lengths,'complete_signal_nets':{net:sorted(names)for net,names in expected.items()if net!='/+3V3_D'},'supply_pad_subset':sorted(expected['/+3V3_D']),'source_via':d['source_via'],'ground_anchors':d['ground_anchors'],
            'limits':['Supply checks cover only the declared footswitch branch; other main loads remain unfinished.','Physical topology only; contact reliability/debounce, effective RC/bypass, noise/coupling/returns, ESD/transients, loaded timing, rail drop/current/thermal, firmware and via-in-pad fabrication/assembly remain unqualified.']}

    if not args.trial:(ROOT/'generated/footswitch-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} footswitch segments, {len(d["via_positions"])} vias; eight signal nets, supply branch and ten plane-ground returns; qualification unfinished.')
    print(lengths)
if __name__=='__main__':main()
