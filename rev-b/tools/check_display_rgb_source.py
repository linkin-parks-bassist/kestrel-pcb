#!/usr/bin/env python3
"""Verify sixteen complete MCU-to-RGB-damping nets and physical separation from outputs."""
import argparse
import json
import pcbnew
from build_display_rgb_source import ROOT,ident,vec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/display-rgb-source-routes.json').read_text())
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
    assert all(site['pad'] in {f'R{i}.1' for i in range(1001,1017)} for site in d.get('via_in_pad_anchors',[])), 'Only guarded underside source lands permit via-in-pad'
    vip={tuple(site['position']):site['pad'] for site in d.get('via_in_pad_anchors',[])}
    assert len(vip)==len(d.get('via_in_pad_anchors',[]))
    assert set(vip)<=set(map(tuple,d['via_positions']))
    vip_uids={}
    for xy,name in vip.items():
        ref,num=name.split('.');pad=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(d['anchors'][name])).EuclideanNorm()<=2)
        assert (pad.GetPosition()-vec(d['anchors'][name])).EuclideanNorm()<=2
        vip_uids[xy]={p.m_Uuid.AsString()for p in fps[ref].Pads()if p.GetNumber()==num and any(p.IsOnLayer(layer) for layer in [pcbnew.F_Cu,pcbnew.B_Cu])}
        assert pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD
        v=tracks[ident('via',d['via_positions'].index(list(xy)))];assert v.GetNetname()==pad.GetNetname()
        q=pad.GetBoundingBox();pos=v.GetPosition();r=v.GetDrillValue()/2
        assert q.GetLeft()+r<=pos.x<=q.GetRight()-r and q.GetTop()+r<=pos.y<=q.GetBottom()-r,name
        poly=pad.GetEffectivePolygon(next(layer for layer in [pcbnew.F_Cu,pcbnew.B_Cu] if pad.IsOnLayer(layer)))
        assert poly.Contains(pos) and not poly.CollideEdge(pos,None,int(r)),name
    for i in range(len(d['via_positions'])):
        v=tracks[ident('via',i)];pos=v.GetPosition();radius=v.GetDrillValue()/2
        for fp in b.GetFootprints():
            for pad in fp.Pads():
                if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD or not any(pad.IsOnLayer(layer) for layer in [pcbnew.F_Cu,pcbnew.B_Cu]):continue
                q=pad.GetBoundingBox()
                dx=max(q.GetLeft()-pos.x,0,pos.x-q.GetRight())
                dy=max(q.GetTop()-pos.y,0,pos.y-q.GetBottom())
                name=fp.GetReference()+'.'+pad.GetNumber()
                if pad.m_Uuid.AsString()in vip_uids.get(tuple(d['via_positions'][i]),set()):continue
                assert dx*dx+dy*dy>radius*radius,(i,name)
    for uid,g in d['existing_via_anchors'].items():
        v=tracks[uid];assert isinstance(v,pcbnew.PCB_VIA)
        assert v.GetPosition()==vec(g['position']) and v.GetNetname()==g['net']
        assert v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(g['diameter_mm']) and v.GetDrillValue()==pcbnew.FromMM(g['drill_mm'])
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
    expected={key:set(names)for key,names in d['expected_groups'].items()}
    lengths={}
    all_seen=set()
    for key,names in expected.items():
        net=key.rsplit(':',1)[0]
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names<=connected_names,(net,names-connected_names)
        all_seen.update(seen)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])

        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    assert all(ident('via',i) in all_seen for i in range(len(d['via_positions'])))
    assert all(ident('track',i) in all_seen for i in range(idx)), 'Dangling owned RGB source copper'
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    for key,names in expected.items():
        net=key.rsplit(':',1)[0]
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')}
        assert names<=xml_names,(net,xml_names,names)
        if net in d['complete_nets']:assert names==xml_names,(net,xml_names,names)
    source_pins=[80,81,82,83,84,86,87,88,89,63,92,55,94,57,97,60]
    independent={}
    for i,pin in enumerate(source_pins):
        ref=f'R{1001+i}';net=pads['U701'][str(pin)].GetNetname()
        names={f'U701.{pin}',ref+'.1'};assert pads[ref]['1'].GetNetname()==net and pads[ref]['2'].GetNetname()!=net
        seen,actual=connected(pads['U701'][str(pin)]);assert names<=actual and pads[ref]['2'].m_Uuid.AsString() not in seen,ref
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')}
        assert xml_names==names,(net,xml_names,names);independent[net]=names
    assert set(d['complete_nets'])==set(independent) and {key.rsplit(':',1)[0]:names for key,names in expected.items()}==independent
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_display_rgb_source_track_ids']==[ident('track',i)for i in range(idx)]
        assert report['provisional_display_rgb_source_via_ids']==[ident('via',i)for i in range(len(d['via_positions']))]
    result={'status':'PASS sixteen complete RGB MCU-to-source-damping nets; output routing unfinished',
            'track_segments':idx,'vias':len(d['via_positions']),'via_in_pad_sites':d.get('via_in_pad_anchors',[]),'routed_planar_length_mm':lengths,'physically_connected_local_groups':{net:sorted(names)for net,names in expected.items()},
            'limits':d['limits']}
    if not args.trial:(ROOT/'generated/display-rgb-source-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} RGB-source segments, {len(d["via_positions"])} vias; sixteen complete source connections; outputs and electrical qualification unfinished.')
    print(lengths)
if __name__=='__main__':main()
