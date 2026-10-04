#!/usr/bin/env python3
"""Guarded P4 EP vias and coordinated paste; assembly qualification separate."""
import argparse
import json
import uuid
from pathlib import Path
import pcbnew
from build_hp_ground import ident as hp_ident
ROOT = Path(__file__).resolve().parents[1]
def ident(kind, index):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'kestrel/rev-b/mcu-exposed-ground/{kind}/{index}'))
def vec(xy):
    return pcbnew.VECTOR2I(*(pcbnew.FromMM(v) for v in xy))
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--trial-output',type=Path);args=parser.parse_args()
    path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(path))
    d=json.loads((ROOT/'electrical/mcu-exposed-ground.json').read_text())
    fp=next(f for f in b.GetFootprints() if f.GetReference()==d['footprint'])
    pad=next(p for p in fp.Pads() if p.GetNumber()==d['pad'])
    assert fp.GetOrientationDegrees()==0 and fp.GetLayer()==pcbnew.F_Cu
    assert pad.GetNetname()=='/GND' and pad.GetPosition()==vec(d['pad_position']) and pad.GetSize()==vec(d['pad_size_mm'])
    paste=[p for p in fp.Pads() if not p.GetNumber()]
    target={tuple(v) for v in d['paste_centres_local_mm']}
    def local(p):
        v=p.GetPosition()-pad.GetPosition();return (round(pcbnew.ToMM(v.x),6),round(pcbnew.ToMM(v.y),6))
    old={(x,y) for x in range(-3,4) for y in range(-3,4)}
    if len(paste)==49:
        assert {local(p) for p in paste}==old and all(p.GetSize()==vec([.85,.85]) and list(p.GetLayerSet().Seq())==[pcbnew.F_Paste] for p in paste)
        for p in paste:fp.Remove(p)
        layer=pcbnew.LSET();layer.AddLayer(pcbnew.F_Paste)
        for i,xy in enumerate(d['paste_centres_local_mm']):
            p=pcbnew.PAD(fp);p.SetUuid(pcbnew.KIID(ident('paste',i)));p.SetNumber('');p.SetAttribute(pcbnew.PAD_ATTRIB_SMD);p.SetShape(pcbnew.PAD_SHAPE_RECT)
            p.SetPosition(pad.GetPosition()+vec(xy));p.SetSize(vec([d['paste_window_mm']]*2));p.SetLayerSet(layer);fp.Add(p)
    else:
        assert len(paste)==36 and {local(p) for p in paste}==target
        assert all(p.GetSize()==vec([d['paste_window_mm']]*2) and list(p.GetLayerSet().Seq())==[pcbnew.F_Paste] for p in paste)
    existing={t.m_Uuid.AsString():t for t in b.GetTracks()};pending=[];ids=[]
    for i,xy in enumerate(d['via_positions']):
        key=ident('via',i);ids.append(key)
        if key in existing:
            v=existing[key];assert isinstance(v,pcbnew.PCB_VIA)
            assert v.GetPosition()==vec(xy) and v.GetNetname()=='/GND'
            assert v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(d['via_diameter_mm']) and v.GetDrillValue()==pcbnew.FromMM(d['via_drill_mm'])
            assert v.TopLayer()==pcbnew.F_Cu and v.BottomLayer()==pcbnew.B_Cu
            assert v.GetBackTentingMode()==pcbnew.TENTING_MODE_TENTED and v.GetFrontTentingMode()==pcbnew.TENTING_MODE_NOT_TENTED
        else:
            v=pcbnew.PCB_VIA(b);v.SetUuid(pcbnew.KIID(key));v.SetPosition(vec(xy));v.SetWidth(pcbnew.FromMM(d['via_diameter_mm']));v.SetDrill(pcbnew.FromMM(d['via_drill_mm']))
            v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(pad.GetNetCode())
            v.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED);v.SetFrontTentingMode(pcbnew.TENTING_MODE_NOT_TENTED);pending.append(v)
    for v in pending:b.Add(v)
    zone=next(z for z in b.Zones() if z.m_Uuid.AsString()==hp_ident('zone',0));assert zone.GetLayer()==pcbnew.In1_Cu and zone.GetNetname()=='/GND'
    filler=pcbnew.ZONE_FILLER(b);assert filler.Fill(b.Zones()) and zone.HasFilledPolysForLayer(pcbnew.In1_Cu)
    pcbnew.SaveBoard(str(args.trial_output or path),b)
    if not args.trial_output:
        p=ROOT/'generated/pcb-import-review.json';r=json.loads(p.read_text());r['provisional_mcu_exposed_ground_via_ids']=ids
        r['status']='partial-placement-local-supply-ground-and-EP-vias-engineering-draft'
        r['limits'][-1]='EP and bypass ground continuity is provisional; main rails, complete routing, tenting/stencil, thermal and assembly remain unqualified.'
        p.write_text(json.dumps(r,indent=2)+'\n')
    print(f'Added {len(pending)} EP vias; verified 36 coordinated paste windows; tenting/assembly unqualified.')
if __name__=='__main__':main()
