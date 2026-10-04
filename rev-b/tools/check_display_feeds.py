#!/usr/bin/env python3
"""Verify display source/PWM/LED feeds; operation unqualified."""
import argparse
import json
import pcbnew
from build_display_feeds import ROOT,ident,vec

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/display-feeds-routes.json').read_text())
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
    for uid,g in d['existing_via_anchors'].items():
        v=tracks[uid];assert isinstance(v,pcbnew.PCB_VIA)
        assert v.GetPosition()==vec(g['position']) and v.GetNetname()==g['net']
        assert v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(g['diameter_mm']) and v.GetDrillValue()==pcbnew.FromMM(g['drill_mm'])
    # LED current takes a separate branch from the R901 sense land.
    assert any(r['net']=='/BL_LED_K' and r['points']==[[58.9125,65.25],[59.5125,65.85],[62.25,65.85],[62.8,65.3]] for r in d['paths'])
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
    from build_hp_ground import ident as hp_ident
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    ground_seen,ground_names=connected(zone)
    assert set(d['ground_anchors'])<=ground_names,set(d['ground_anchors'])-ground_names
    assert all(ident('via',i)in ground_seen for i,n in enumerate(d['via_net_names'])if n=='/GND')
    assert all(ident('via',i)in all_seen|ground_seen for i in range(len(d['via_positions'])))
    source_seen,source_names=connected(pads['L101']['2'])
    assert all(uid in source_seen for uid,g in d['existing_via_anchors'].items() if g['net']=='/+5V_DIG')
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    for key,names in expected.items():
        net=key.rsplit(':',1)[0]
        xml_names={node.attrib['ref']+'.'+node.attrib['pin']for n in xml.findall('.//nets/net')if n.attrib['name']==net for node in n.findall('node')}
        assert names<=xml_names,(net,xml_names,names)
        if net in d['complete_nets']:assert names==xml_names,(net,xml_names,names)
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_display_feeds_track_ids']==[ident('track',i)for i in range(idx)]
        assert report['provisional_display_feeds_via_ids']==[ident('via',i)for i in range(len(d['via_positions']))]
    result={'status':'PASS main 5 V feeds, MCU PWM and FPC LED groups',
            'track_segments':idx,'vias':len(d['via_positions']),'via_in_pad_sites':d.get('via_in_pad_anchors',[]),'routed_planar_length_mm':lengths,'physically_connected_local_groups':{net:sorted(names)for net,names in expected.items()},'ground_anchors':d['ground_anchors'],
            'limits':['LCD/touch FPC supply and connector support remain unfinished.','Physical topology only; effective bypassing/switching/Kelvin sense, rail drop, coupling/noise, backlight regulation/startup/fault/PWM operation and via-in-pad fabrication/assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/display-feeds-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} display-feed segments, {len(d["via_positions"])} vias; main 5 V feeds, MCU PWM and FPC LED groups; qualification unfinished.')
    print(lengths)
if __name__=='__main__':main()
