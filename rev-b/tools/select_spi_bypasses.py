#!/usr/bin/env python3
"""Replace two unrouted translator capacitors with selected 0402 lands, preserving identities/nets."""
import argparse
from pathlib import Path
import pcbnew
from spi_bypass import REFS,CAP_FOOTPRINT,FIELDS
ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--trial-output',type=Path);args=parser.parse_args()
    path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(path));fps={f.GetReference():f for f in b.GetFootprints()};conn=b.GetConnectivity();conn.Build(b)
    for ref in sorted(REFS):
        old=fps[ref];fid=old.GetFPID();library,name=CAP_FOOTPRINT.split(':')
        if str(fid.GetLibNickname())+':'+str(fid.GetLibItemName())==CAP_FOOTPRINT:
            assert all(old.GetField(k).GetText()==v for k,v in FIELDS.items()),ref;continue
        assert str(fid.GetLibNickname())+':'+str(fid.GetLibItemName())=='Capacitor_SMD:C_0603_1608Metric',ref
        assert all(all(item.m_Uuid.AsString()==p.m_Uuid.AsString()for item in conn.GetConnectedItems(p))for p in old.Pads()),f'{ref} already routed'
        new=pcbnew.FootprintLoad('/usr/share/kicad/footprints/'+library+'.pretty',name);assert new
        for field in old.GetFields():new.SetField(field.GetName(),field.GetText());new.GetField(field.GetName()).SetVisible(field.IsVisible())
        new.SetUuid(pcbnew.KIID(old.m_Uuid.AsString()));new.SetPath(old.GetPath());new.SetFPID(pcbnew.LIB_ID(library,name));new.SetPosition(old.GetPosition());new.SetOrientationDegrees(old.GetOrientationDegrees())
        old_pads={p.GetNumber():p for p in old.Pads()};assert set(old_pads)=={'1','2'}
        for p in new.Pads():p.SetUuid(pcbnew.KIID(old_pads[p.GetNumber()].m_Uuid.AsString()));p.SetNet(old_pads[p.GetNumber()].GetNet())
        for key,value in FIELDS.items():new.SetField(key,value);new.GetField(key).SetVisible(False)
        b.Remove(old);b.Add(new)
    pcbnew.SaveBoard(str(args.trial_output or path),b)
    print('Selected C801/C802 0402 bypasses; footprint/pad identities, nets and hierarchy preserved.')
if __name__=='__main__':main()
