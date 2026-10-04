#!/usr/bin/env python3
"""Select sixteen unrouted RGB damping 0402 lands, retaining side/identity/hierarchy/nets."""
import argparse
from pathlib import Path
import pcbnew
from display_rgb_damping import REFS,FOOTPRINT,FIELDS
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--trial-output',type=Path);args=p.parse_args();path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(path));fps={f.GetReference():f for f in b.GetFootprints()};conn=b.GetConnectivity();conn.Build(b);detached=[]
 for ref in sorted(REFS):
  old=fps[ref];fid=old.GetFPID();library,name=FOOTPRINT.split(':')
  if f'{fid.GetLibNickname()}:{fid.GetLibItemName()}'==FOOTPRINT:
   assert all(old.GetField(k).GetText()==v for k,v in FIELDS.items()),ref;continue
  assert f'{fid.GetLibNickname()}:{fid.GetLibItemName()}'=='Resistor_SMD:R_0603_1608Metric',ref
  assert all(all(item.m_Uuid.AsString()==pad.m_Uuid.AsString()for item in conn.GetConnectedItems(pad))for pad in old.Pads()),f'{ref} already routed'
  new=pcbnew.FootprintLoad('/usr/share/kicad/footprints/'+library+'.pretty',name);assert new
  # Flip needs a board parent; detach old identities before rebinding UUIDs.
  b.Remove(old);detached.append(old)
  b.Add(new)
  if old.GetLayer()==pcbnew.B_Cu:new.Flip(new.GetPosition(),False)
  for field in old.GetFields():new.SetField(field.GetName(),field.GetText());new.GetField(field.GetName()).SetVisible(field.IsVisible())
  new.SetUuid(pcbnew.KIID(old.m_Uuid.AsString()));new.SetPath(old.GetPath());new.SetFPID(pcbnew.LIB_ID(library,name));new.SetPosition(old.GetPosition());new.SetOrientationDegrees(old.GetOrientationDegrees())
  op={pad.GetNumber():pad for pad in old.Pads()};assert set(op)=={'1','2'}
  for pad in new.Pads():pad.SetUuid(pcbnew.KIID(op[pad.GetNumber()].m_Uuid.AsString()));pad.SetNet(op[pad.GetNumber()].GetNet())
  for key,value in FIELDS.items():new.SetField(key,value);new.GetField(key).SetVisible(False)
 pcbnew.SaveBoard(str(args.trial_output or path),b);print('Selected sixteen RGB 0402 lands; identities/nets, hierarchy and sides preserved.')
if __name__=='__main__':main()
