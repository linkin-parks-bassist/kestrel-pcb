#!/usr/bin/env python3
"""Guarded MCU SPI endpoint branches; no return/current/assembly qualification."""
import argparse
import json
import uuid
from pathlib import Path
import pcbnew
from build_hp_ground import ident as hp_ident
from owned_route_replacement import replace_owned_routes
ROOT=Path(__file__).resolve().parents[1]
def ident(kind,index):return str(uuid.uuid5(uuid.NAMESPACE_URL,f'kestrel/rev-b/spi-mcu-endpoints/{kind}/{index}'))
def vec(xy):return pcbnew.VECTOR2I(*(pcbnew.FromMM(v)for v in xy))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--board',type=Path);parser.add_argument('--trial-output',type=Path);parser.add_argument('--replace-from',type=Path);args=parser.parse_args()
    path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(args.board or path));d=json.loads((ROOT/'electrical/spi-mcu-endpoints-routes.json').read_text())
    assert b.GetCopperLayerCount()==4
    fps={f.GetReference():f for f in b.GetFootprints()};net=b.FindNet(d['net']);existing={t.m_Uuid.AsString():t for t in b.GetTracks()};pending=[];ids=[];vids=[]
    for name,xy in d['anchors'].items():
        ref,num=name.split('.');pad=next(p for p in fps[ref].Pads()if p.GetNumber()==num)
        assert pad.GetNetname()==d.get('anchor_nets',{}).get(name,d['net']) and (pad.GetPosition()-vec(xy)).EuclideanNorm()<=2,name
    for guard in d['additional_anchors']:
        assert any(p.GetNumber()==guard['pad'] and p.GetNetname()==guard['net'] and (p.GetPosition()-vec(guard['xy'])).EuclideanNorm()<=2 for p in fps[guard['ref']].Pads()),guard
    if args.replace_from:
        old=json.loads(args.replace_from.read_text());report=json.loads((ROOT/'generated/pcb-import-review.json').read_text())
        existing,detached=replace_owned_routes(b,existing,old,ident,vec,report,'provisional_spi_mcu_endpoints')
    index=0
    for route in d['paths']:
        layer={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}[route['layer']]
        route_net=route.get('net',d['net']);net=b.FindNet(route_net)
        for a,c in zip(route['points'],route['points'][1:]):
            key=ident('track',index);index+=1;ids.append(key);width=pcbnew.FromMM(route['width_mm'])
            if key in existing:
                t=existing[key];assert not isinstance(t,pcbnew.PCB_VIA)
                assert t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetLayer()==layer and t.GetWidth()==width and t.GetNetname()==route_net,key
            else:
                t=pcbnew.PCB_TRACK(b);t.SetUuid(pcbnew.KIID(key));t.SetStart(vec(a));t.SetEnd(vec(c));t.SetWidth(width);t.SetLayer(layer);t.SetNetCode(net.GetNetCode());pending.append(t)
    for i,xy in enumerate(d['via_positions']):
        key=ident('via',i);vids.append(key)
        diameter=d.get('via_diameters_mm',[d['via_diameter_mm']]*len(d['via_positions']))[i]
        via_net=d.get('via_net_names',[d['net']]*len(d['via_positions']))[i];net=b.FindNet(via_net)
        if key in existing:
            v=existing[key];assert isinstance(v,pcbnew.PCB_VIA)
            assert v.GetPosition()==vec(xy) and v.GetNetname()==via_net and v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(diameter) and v.GetDrillValue()==pcbnew.FromMM(d['via_drill_mm'])
            assert v.TopLayer()==pcbnew.F_Cu and v.BottomLayer()==pcbnew.B_Cu
        else:
            v=pcbnew.PCB_VIA(b);v.SetUuid(pcbnew.KIID(key));v.SetPosition(vec(xy));v.SetWidth(pcbnew.FromMM(diameter));v.SetDrill(pcbnew.FromMM(d['via_drill_mm']));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNetCode(net.GetNetCode());pending.append(v)
    for t in pending:b.Add(t)
    z=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert z.GetLayer()==pcbnew.In1_Cu and z.GetNetname()=='/GND'
    filler=pcbnew.ZONE_FILLER(b);assert filler.Fill(b.Zones()) and z.HasFilledPolysForLayer(pcbnew.In1_Cu)
    pcbnew.SaveBoard(str(args.trial_output or path),b)
    if not args.trial_output:
        p=ROOT/'generated/pcb-import-review.json';r=json.loads(p.read_text());r['provisional_spi_mcu_endpoints_track_ids']=ids;r['provisional_spi_mcu_endpoints_via_ids']=vids
        r['status']='partial-placement-local-supply-ground-and-buck-copper-engineering-draft';p.write_text(json.dumps(r,indent=2)+'\n')
    print(f'Added {len(pending)} items; verified {len(ids)} MCU SPI endpoints segments and {len(vids)} through vias; electrical qualification incomplete.')
if __name__=='__main__':main()
