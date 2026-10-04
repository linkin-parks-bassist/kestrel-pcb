#!/usr/bin/env python3
"""Verify all FPGA-sheet ground pads reach the plane, not electrical performance."""
import argparse
import json
import pcbnew
from build_fpga_support_ground import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/fpga-support-ground.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2);assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==19
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
    # Independent whole-sheet inventory, including repeated switch pads and JTAG PTH grounds.
    refs={'U501','U502','U503','U504','Y501','SW501','J501','L501','L502'}|{f'C{i}'for i in range(501,528)}|{f'R{i}'for i in range(501,519)}
    ground_pads=[p for ref in refs for p in fps[ref].Pads()if p.GetNetname()=='/GND']
    assert len(ground_pads)==51,len(ground_pads)
    assert all(p.m_Uuid.AsString()in seen for p in ground_pads)
    assert all(ident('via',i)in seen for i in range(19))
    assert len(d['ground_returns'])==19
    for guard in d['ground_returns']:
        p=next(p for p in fps[guard['ref']].Pads()if p.GetNumber()==guard['pad'] and (p.GetPosition()-vec(guard['xy'])).EuclideanNorm()<=2)
        assert p.GetNetname()=='/GND'
        i=guard['via_index'];box=p.GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,(guard,dx,dy)
    result={'status':'PASS all 51 FPGA support-sheet ground pads reach the filled plane, including both duplicated switch ground pads and JTAG PTH pads',
            'track_segments':idx,'vias':19,'new_ground_pad_returns':19,'all_sheet_ground_pads':51,
            'limits':['Supply and signal routing remain unfinished; return impedance, effective decoupling, current/thermal and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/fpga-support-ground-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} support ground segments, 19 vias, all 51 FPGA-sheet ground pads reach the plane; qualification unfinished.')
if __name__=='__main__':main()
