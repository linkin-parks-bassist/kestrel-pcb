#!/usr/bin/env python3
"""Verify all SPI-sheet ground pads reach the plane, not electrical performance."""
import argparse
import json
import pcbnew
from build_spi_support_ground import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/spi-support-ground.json').read_text())
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
    zone=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0))
    assert zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    seen,names=connected(zone)
    # Independent whole-sheet inventory, including the fixed-low translator direction pin.
    refs={'U801','U802','U803'}|{f'C{i}'for i in range(801,806)}|{f'R{i}'for i in range(801,812)}
    ground_pads=[p for ref in refs for p in fps[ref].Pads()if p.GetNetname()=='/GND']
    assert len(ground_pads)==11,len(ground_pads)
    assert all(p.m_Uuid.AsString()in seen for p in ground_pads)
    assert all(ident('via',i)in seen for i in range(11))
    assert len(d['ground_returns'])==11
    sites=d.get('via_in_pad_anchors',[])
    assert sites in [[],[{'pad':'R811.2','position':[114.825,87.8],'via_index':10}]],sites
    vip={site['via_index']:site for site in sites}
    for guard in d['ground_returns']:
        p=next(p for p in fps[guard['ref']].Pads()if p.GetNumber()==guard['pad'] and (p.GetPosition()-vec(guard['xy'])).EuclideanNorm()<=2)
        assert p.GetNetname()=='/GND'
        i=guard['via_index'];box=p.GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        if i in vip:
            assert guard['ref']+'.'+guard['pad']==vip[i]['pad'] and pos==p.GetPosition()==vec(vip[i]['position'])
            assert p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD
            poly=p.GetEffectivePolygon(pcbnew.F_Cu);radius=pcbnew.FromMM(.3)//2
            assert poly.Contains(pos) and not poly.CollideEdge(pos,None,radius)
        else:assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,(guard,dx,dy)
    for i,xy in enumerate(d['via_positions']):
        pos=vec(xy);radius=pcbnew.FromMM(.3)//2
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD or not any(p.IsOnLayer(layer)for layer in [pcbnew.F_Cu,pcbnew.B_Cu]):continue
                if i in vip and fp.GetReference()+'.'+p.GetNumber()==vip[i]['pad']:continue
                box=p.GetBoundingBox();dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
                assert dx*dx+dy*dy>radius*radius,(i,fp.GetReference(),p.GetNumber())
    result={'status':'PASS all 11 SPI support-sheet ground pads reach the filled plane, including translator direction pin and all five capacitor returns',
            'via_in_pad_sites':sites,'track_segments':idx,'vias':11,'new_ground_pad_returns':11,'all_sheet_ground_pads':11,
            'limits':['Supply/control continuity is checked separately by check_spi_support_supply.py and check_spi_control_local.py; return impedance, effective decoupling, current/thermal and via-in-pad fabrication/assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/spi-support-ground-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} support ground segments, 11 vias, all 11 SPI-sheet ground pads reach the plane; qualification unfinished.')
if __name__=='__main__':main()
