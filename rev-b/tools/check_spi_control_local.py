#!/usr/bin/env python3
"""Verify SPI control physical groups, not firmware, timing or operating isolation."""
import argparse
import json
import pcbnew
from build_spi_control_local import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/spi-control-local-routes.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2);assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==9
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
    expected={
      '/Power-domain SPI isolation/SPI_SENSE':{'U802.5','C805.1','R810.2','R811.1'},
      '/Power-domain SPI isolation/SPI_RAIL_RELEASE':{'U802.1','R809.2','U803.2'},
      '/MCU_SPI_ENABLE':{'U803.1','R808.1','U701.7'},
      '/MCU_RESET_N':{'U802.3','U701.103','C732.1'},
      '/Power-domain SPI isolation/SPI_OE_N':{'U803.4','R807.2','U801.9'},
    }
    refs={'U801','U802','U803'}|{f'C{i}'for i in range(801,806)}|{f'R{i}'for i in range(801,812)}
    counts={}
    for net,names in expected.items():
        actual_sheet={f'{ref}.{p.GetNumber()}'for ref in refs for p in fps[ref].Pads()if p.GetNetname()==net}
        assert actual_sheet=={name for name in names if name.split('.')[0]in refs},(net,actual_sheet)
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names<=connected_names,(net,names-connected_names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        counts[net]=len(names)
    assert len(d['via_returns'])==9
    for guard in d['via_returns']:
        ref,num=guard['anchor'].split('.');p=pads[ref][num];i=guard['via_index']
        assert p.GetNetname()==d['via_net_names'][i]
        box=p.GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,guard
    ct=pads['U802']['4'];assert ct.GetNetname().startswith('unconnected-')
    assert all(item.m_Uuid.AsString()==ct.m_Uuid.AsString()for item in conn.GetConnectedItems(ct))
    report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
    if not args.trial:
        # Separate owned report fields must not overwrite the FPGA ground inventory.
        from build_spi_support_ground import ident as ground_ident
        from build_spi_support_supply import ident as supply_ident
        from build_fpga_support_ground import ident as fpga_ground_ident
        assert report['provisional_spi_support_ground_track_ids']==[ground_ident('track',i)for i in range(13)]
        assert report['provisional_spi_support_supply_track_ids']==[supply_ident('track',i)for i in range(51)]
        assert report['provisional_fpga_support_ground_track_ids']==[fpga_ground_ident('track',i)for i in range(22)]
        assert report['provisional_spi_control_local_track_ids']==[ident('track',i)for i in range(idx)]
    result={'status':'PASS five SPI control groups reach their required pads, including MCU enable/reset; supervisor CT remains open',
            'track_segments':idx,'vias':9,'physical_groups':counts,
            'limits':['SPI data/clock/CS paths remain unfinished; firmware, loaded timing, noise/coupling, intermediate rails/backfeed and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/spi-control-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} control segments, nine vias, five physical groups; CT open; qualification unfinished.')
if __name__=='__main__':main()
