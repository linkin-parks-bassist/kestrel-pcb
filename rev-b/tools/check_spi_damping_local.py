#!/usr/bin/env python3
"""Verify local translator/damping groups; full SPI endpoints and performance remain unqualified."""
import argparse
import json
import pcbnew
from build_spi_damping_local import ROOT,ident,vec
from build_hp_ground import ident as hp_ident

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board');parser.add_argument('--trial',action='store_true');args=parser.parse_args()
    b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/spi-damping-local-routes.json').read_text())
    fps={f.GetReference():f for f in b.GetFootprints()};pads={r:{p.GetNumber():p for p in f.Pads()}for r,f in fps.items()};tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');p=next(p for p in fps[ref].Pads()if p.GetNumber()==num and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2);assert p.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (p.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    idx=0;layers={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}
    for route in d['paths']:
        for a,c in zip(route['points'],route['points'][1:]):
            t=tracks[ident('track',idx)];idx+=1;assert not isinstance(t,pcbnew.PCB_VIA)
            assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetNetname()==route.get('net',d['net']) and t.GetLayer()==layers[route['layer']] and t.GetWidth()==pcbnew.FromMM(route['width_mm'])
    assert len(d['via_positions'])==4
    for i,xy in enumerate(d['via_positions']):
        v=tracks[ident('via',i)];assert isinstance(v,pcbnew.PCB_VIA) and v.GetPosition()==vec(xy)
        assert v.GetNetname()==d['via_net_names'][i] and v.GetDrillValue()==pcbnew.FromMM(.3) and v.GetViaType()==pcbnew.VIATYPE_THROUGH
        assert v.TopLayer()==pcbnew.F_Cu and v.BottomLayer()==pcbnew.B_Cu
        assert all(v.IsOnLayer(layer) and v.GetWidth(layer)==pcbnew.FromMM(d['via_diameters_mm'][i])for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu])
    minimum_land_clearance=float('inf')
    for i,xy in enumerate(d['via_positions']):
        pos=vec(xy);radius=pcbnew.FromMM(d['via_diameters_mm'][i])/2
        for f in b.GetFootprints():
            for p in f.Pads():
                if not p.IsOnLayer(pcbnew.F_Cu):continue
                box=p.GetBoundingBox();dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
                clearance=(dx*dx+dy*dy)**.5-radius
                assert clearance>=pcbnew.FromMM(.2),(i,f.GetReference(),p.GetNumber(),pcbnew.ToMM(clearance))
                minimum_land_clearance=min(minimum_land_clearance,pcbnew.ToMM(clearance))
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
      '/Power-domain SPI isolation/SPI_CS_B':{'U801.14','R801.1'},
      '/Power-domain SPI isolation/SPI_CLK_B':{'U801.13','R802.1'},
      '/Power-domain SPI isolation/SPI_MOSI_B':{'U801.12','R803.1'},
      '/Power-domain SPI isolation/SPI_MISO_A':{'U801.6','R804.1'},
      '/MCU_RAW_CS':{'U801.3','R806.2'},
    }
    lengths={}
    for net,names in expected.items():
        ref,num=sorted(names)[0].split('.');seen,connected_names=connected(pads[ref][num])
        assert names<=connected_names,(net,names-connected_names)
        assert all(pads[r][n].GetNetname()==net for r,n in [name.split('.')for name in names])
        assert all(ident('via',i)in seen for i,n in enumerate(d['via_net_names'])if n==net)
        lengths[net]=sum(pcbnew.ToMM(tracks[ident('track',i)].GetLength())for i in range(idx)if tracks[ident('track',i)].GetNetname()==net)
    assert len(d['via_returns'])==4
    for guard in d['via_returns']:
        ref,num=guard['anchor'].split('.');p=pads[ref][num];i=guard['via_index']
        assert p.GetNetname()==d['via_net_names'][i]
        box=p.GetBoundingBox();pos=vec(d['via_positions'][i])
        dx=max(box.GetLeft()-pos.x,0,pos.x-box.GetRight());dy=max(box.GetTop()-pos.y,0,pos.y-box.GetBottom())
        assert (dx*dx+dy*dy)**.5>pcbnew.FromMM(.3)/2,guard
    # Check every serial-resistor half against actual XML independently of the manifest.
    import xml.etree.ElementTree as ET
    xml=ET.parse(ROOT/'generated/revb-netlist.xml')
    actual={}
    for net in xml.findall('.//nets/net'):
        for node in net.findall('node'):actual[node.attrib['ref']+'.'+node.attrib['pin']]=net.attrib['name']
    for ref in ['R801','R802','R803','R804']:
        assert actual[ref+'.1']!=actual[ref+'.2']
        assert pads[ref]['1'].GetNetname()==actual[ref+'.1'] and pads[ref]['2'].GetNetname()==actual[ref+'.2']
        assert pads[ref]['2'].m_Uuid.AsString()not in connected(pads[ref]['1'])[0]
    if not args.trial:
        report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        assert report['provisional_spi_damping_local_track_ids']==[ident('track',i)for i in range(idx)]
    result={'status':'PASS four translator-to-series branches and MCU-side CS pullup stub have physical continuity; resistor halves remain separate',
            'track_segments':idx,'vias':4,'minimum_owned_via_annulus_to_front_pad_bbox_mm':minimum_land_clearance,'routed_planar_length_mm':lengths,
            'limits':['Lengths exclude via depth and are observations, not SI limits; CS/clock detours require qualification.','FPGA CS/pullup, MISO, clock and MOSI continuity are checked separately by check_spi_fpga_endpoints.py; MCU signal continuity is checked separately by check_spi_mcu_endpoints.py; firmware, SI/damping, timing, loaded coupling, backfeed and assembly remain unqualified.']}
    if not args.trial:(ROOT/'generated/spi-damping-local-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: {idx} damping segments, four vias, five local groups; complete endpoint continuity checked separately; firmware and SI/timing unfinished.')
    print(lengths)
if __name__=='__main__':main()
