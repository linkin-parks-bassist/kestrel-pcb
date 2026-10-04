#!/usr/bin/env python3
"""Verify analogue LDO/isolated held-supply physical topology and plane grounds; operation unqualified."""
import argparse
import json
import pcbnew
from build_analogue_power_local import ROOT,ident,vec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/analogue-power-local-routes.json').read_text())
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
    expected={
      '/Hardware ADC and DAC/+5V_DAC_HOLD':{'D204.1','C230.1','C235.1','C228.1','U205.1','U205.3'},
    }
    lengths={}
    for net,names in expected.items():
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names==connected_names,(net,names-connected_names,connected_names-names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    # Other rails are declared source/load subsets; converter loads remain separate.
    groups={
      '/9V_PROTECTED':{'Q401.1','C226.1','U204.4','U204.6'},
      '/+5V_DIG':{'L101.2','D204.2','R217.1'},
      '/Hardware ADC and DAC/+5V_A':{'U204.1','U204.2','C227.1','R215.1'},
      '/+3V3_A':{'U205.5','C229.1','C527.1','U504.5'},
    }
    for net,names in groups.items():
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names<=connected_names,(net,names-connected_names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    from build_hp_ground import ident as hp_ident
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    ground_seen,ground_names=connected(zone)
    assert set(d['ground_anchors'])<=ground_names,set(d['ground_anchors'])-ground_names
    assert all(ident('via',i)in ground_seen for i,n in enumerate(d['via_net_names'])if n=='/GND')
    # EP7 repeats in the thermal footprint: every actual ground land must reach the plane.
    ground_pads=[p for ref in ['U204','U205','C226','C227','C228','C229','C230','C235']for p in fps[ref].Pads()if p.GetNetname()=='/GND']
    assert all(p.m_Uuid.AsString()in ground_seen for p in ground_pads)
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    for net,names in expected.items():
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')}
        assert xml_names==names,(net,xml_names,names)
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_analogue_power_local_track_ids']==[ident('track',i)for i in range(idx)]
        assert report['provisional_analogue_power_local_via_ids']==[ident('via',i)for i in range(len(d['via_positions']))]
    result={'status':'PASS isolated DAC held net, both LDO source/output subsets, divider source feeds and declared plane grounds',
            'track_segments':idx,'vias':len(d['via_positions']),'via_in_pad_sites':d.get('via_in_pad_anchors',[]),'routed_planar_length_mm':lengths,'source_load_subsets':{k:sorted(v)for k,v in groups.items()},'ground_anchors':d['ground_anchors'],'actual_ground_lands':len(ground_pads),
            'limits':['DAC supply/pump and complete held-rail continuity is checked separately by check_dac_support_local.py; ADC reference/mode/ground continuity is checked by check_adc_support_local.py; ADC supply/bypass continuity is checked by check_adc_power_local.py; Analogue signal/bias, protected supply and ground continuity is checked by check_analogue_signal_local.py. Physical topology is not powered LDO, converter or mute qualification.','Rail drop/current/thermal, effective ceramics/stability, sense noise/transient response, reservoir inrush/hold-up/backfeed and via-in-pad/EP fabrication/assembly are unqualified.']}
    if not args.trial:(ROOT/'generated/analogue-power-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} analogue-power segments, {len(d["via_positions"])} vias; complete held net, LDO/divider source/output subsets and {len(ground_pads)} ground lands; qualification unfinished.')
    print(lengths)
if __name__=='__main__':main()
