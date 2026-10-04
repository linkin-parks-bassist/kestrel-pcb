#!/usr/bin/env python3
"""Replay an isolated reset/CS reservation; C701 and preferred board stay unchanged."""
import argparse,hashlib,json,math,os,shutil,subprocess,uuid
from collections import Counter
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'generated/trials/display-clock-rgb.kicad_pcb'
SHA='036c4a8d87f217ec4c4210d9ab375a1933b7777803e1d6b6883fa96f954d8b9a'
REMOVED=['6065f052-7599-5df0-8a51-3d453789fe23','73602276-be25-5f3b-898f-df68f3dfe40e','b792dd7c-a9b9-59c7-af7f-925dc7fbb044','0bc26b99-5acc-500a-afe1-bbf2cd7429db']
REVISED={
 'e5c2d408-e9cb-5c18-b9f7-ac39f5c59c4c':[[116.8,82.5],[119.875,81.95]],
 '30feee23-66ae-5fcb-889a-74090d84384b':[[120.95,81.95],[120.95,89]],
}
ROUTES=[
 ('/MCU_RESET_N','In2.Cu',[[119.875,81.95],[120.95,81.95]]),
 ('/MCU_RESET_N','In2.Cu',[[120.95,89],[119.875,89]]),
 ('/MCU_RAW_CS','F.Cu',[[119.1,82.675],[119.825,82.675]]),
 ('/MCU_RAW_CS','In2.Cu',[[119.825,82.675],[120.35,83.2],[120.35,87.45],[119.825,87.975]]),
 ('/MCU_RAW_CS','F.Cu',[[119.825,87.975],[119.825,90],[119.95,90.125]]),
]
VIAS=[[119.825,82.675],[119.825,87.975]]
def xy(p):return [pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)]
def vec(a):return pcbnew.VECTOR2I(*(pcbnew.FromMM(x)for x in a))
def geometry(t):
 return [t.GetNetname(),t.GetLayer(),t.GetWidth(pcbnew.F_Cu),t.GetDrillValue(),xy(t.GetPosition())] if isinstance(t,pcbnew.PCB_VIA) else [t.GetNetname(),t.GetLayer(),t.GetWidth(),xy(t.GetStart()),xy(t.GetEnd())]
def groups(b):
 c=b.GetConnectivity();c.Build(b);pads={f.GetReference()+'.'+p.GetNumber():p for f in b.GetFootprints()for p in f.Pads()};out={}
 for name,pad in pads.items():
  if name in out:continue
  seen=set();names=set();todo=[pad]
  while todo:
   t=todo.pop();u=t.m_Uuid.AsString()
   if u in seen:continue
   seen.add(u)
   if isinstance(t,pcbnew.PAD):names.add(t.GetParentFootprint().GetReference()+'.'+t.GetNumber())
   todo.extend(c.GetConnectedItems(t))
  for reached in names:out[reached]=sorted(names)
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA
 assert not a.output.exists(),'Use a fresh isolated output'
 a.output.parent.mkdir(parents=True,exist_ok=True)
 b=pcbnew.LoadBoard(str(SOURCE));before_groups=groups(b);tracks={t.m_Uuid.AsString():t for t in b.GetTracks()};original={u:geometry(t)for u,t in tracks.items()};det=[];added=set()
 for u in REMOVED:det.append(tracks[u]);b.Remove(tracks[u])
 for u,(start,end) in REVISED.items():tracks[u].SetStart(vec(start));tracks[u].SetEnd(vec(end))
 def ident(kind,i):return str(uuid.uuid5(uuid.NAMESPACE_URL,'kestrel-revb-reset-cs-reservation:'+kind+':'+str(i)))
 i=0
 for net,layer,pts in ROUTES:
  for start,end in zip(pts,pts[1:]):
   t=pcbnew.PCB_TRACK(b);t.SetUuid(pcbnew.KIID(ident('track',i)));i+=1;t.SetStart(vec(start));t.SetEnd(vec(end));t.SetWidth(pcbnew.FromMM(.127));t.SetLayer(b.GetLayerID(layer));t.SetNetCode(b.FindNet(net).GetNetCode());b.Add(t);added.add(t.m_Uuid.AsString())
 for i,pt in enumerate(VIAS):
  t=pcbnew.PCB_VIA(b);t.SetUuid(pcbnew.KIID(ident('via',i)));t.SetPosition(vec(pt));t.SetWidth(pcbnew.FromMM(.5));t.SetDrill(pcbnew.FromMM(.3));t.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);t.SetViaType(pcbnew.VIATYPE_THROUGH);t.SetNetCode(b.FindNet('/MCU_RAW_CS').GetNetCode());b.Add(t);added.add(t.m_Uuid.AsString())
 assert pcbnew.ZONE_FILLER(b).Fill(b.Zones())
 pcbnew.SaveBoard(str(a.output),b)
 shutil.copy(SOURCE.with_suffix('.kicad_pro'),a.output.with_suffix('.kicad_pro'))
 shutil.copytree(SOURCE.parent/'KestrelTiming.pretty',a.output.parent/'KestrelTiming.pretty',dirs_exist_ok=True)
 (a.output.parent/'fp-lib-table').write_text((SOURCE.parent/'fp-lib-table').read_text().replace('${KIPRJMOD}/../../electrical/','${KIPRJMOD}/'+os.path.relpath(ROOT/'electrical',a.output.parent)+'/'))
 saved=pcbnew.LoadBoard(str(a.output));now={t.m_Uuid.AsString():geometry(t)for t in saved.GetTracks()}
 assert set(now)==(set(original)-set(REMOVED))|added
 assert all(now[u]==g for u,g in original.items()if u not in REMOVED and u not in REVISED)
 # Every pad's previously reached physical pad set must be preserved, including
 # all complete RGB/timing/touch/MISO and reset/CS groups and incomplete groups.
 after=groups(saved);assert before_groups==after,[(k,before_groups[k],after[k])for k in before_groups if before_groups[k]!=after[k]]
 assert after['U701.4']==['R806.2','U701.4','U801.3']
 via_margins={}
 for t in saved.GetTracks():
  if not isinstance(t,pcbnew.PCB_VIA)or t.m_Uuid.AsString()not in added:continue
  nearest=None
  for f in saved.GetFootprints():
   for pad in f.Pads():
    if pad.GetAttribute()!=pcbnew.PAD_ATTRIB_SMD:continue
    q=pad.GetBoundingBox();c=t.GetPosition();dist=pcbnew.ToMM(round(math.hypot(max(q.GetLeft()-c.x,c.x-q.GetRight(),0),max(q.GetTop()-c.y,c.y-q.GetBottom(),0))))
    local=pad.GetLocalClearance();local=f.GetLocalClearance()if local is None else local;rule=.2 if local is None else pcbnew.ToMM(local)
    assert dist-.25>=rule-1e-6 and dist-.15>=.25-1e-6,(f.GetReference(),pad.GetNumber(),dist)
    if nearest is None or dist<nearest['distance_mm']:nearest=dict(pad=f.GetReference()+'.'+pad.GetNumber(),distance_mm=dist,copper_mm=dist-.25,hole_mm=dist-.15)
  via_margins[t.m_Uuid.AsString()]=nearest
 drc=a.output.with_suffix('.drc.json');subprocess.run(['kicad-cli','pcb','drc','--format','json','--output',str(drc),str(a.output)],check=True)
 d=json.loads(drc.read_text());residual={'silk_overlap','silk_over_copper','silk_edge_clearance','drill_out_of_range'};critical=[v for v in d['violations']if v['type']not in residual];assert not critical,critical
 report=dict(source_sha256=SHA,trial_sha256=hashlib.sha256(a.output.read_bytes()).hexdigest(),removed_uuids=REMOVED,revised_geometry=REVISED,added_uuids=sorted(added),unchanged_copper_count=len(original)-len(REMOVED)-len(REVISED),checked_pad_groups=len(after),cs_group=after['U701.4'],reset_group=after['U701.103'],native_critical=0,native_residual_counts=dict(Counter(v['type']for v in d['violations'])),new_via_smd_margins=via_margins,limits=['Isolated reservation; neither preferred coordinated snapshot nor authoritative schematic/board is changed.','C701 remains at its old out-of-bound pose; supply/ground revision is still required.','Topology and native clearance do not qualify loaded SPI/reset timing, returns, PDN, manufacturing or assembly.'])
 a.report.write_text(json.dumps(report,indent=2)+'\n');print('Native-clear reset/CS reservation; all prior pad groups preserved')
if __name__=='__main__':main()
