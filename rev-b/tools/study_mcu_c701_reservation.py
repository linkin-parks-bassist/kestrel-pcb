#!/usr/bin/env python3
"""Read-only bounded C701 pose study; route/native/PDN qualification remains required."""
import pcbnew,math,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
source=ROOT/'generated/trials/display-clock-rgb.kicad_pcb'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='036c4a8d87f217ec4c4210d9ab375a1933b7777803e1d6b6883fa96f954d8b9a', 'Reassess the study after preferred geometry changes'
b=pcbnew.LoadBoard(str(source));fs={f.GetReference():f for f in b.GetFootprints()};obs=[];holes=[];courts=[]
def xy(p):return (pcbnew.ToMM(p.x),pcbnew.ToMM(p.y))
exclude={'1f0bf071-ef25-5601-982c-3345f628d269'}
for t in b.GetTracks():
 if t.m_Uuid.AsString() in exclude:continue
 if isinstance(t,pcbnew.PCB_VIA):g=Point(xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.B_Cu))/2);holes.append(Point(xy(t.GetPosition())).buffer(pcbnew.ToMM(t.GetDrillValue())/2))
 else:g=LineString([xy(t.GetStart()),xy(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2)
 if t.IsOnLayer(pcbnew.B_Cu):obs.append((t.GetNetname(),g.buffer(.2)))
for f in b.GetFootprints():
 if f.GetReference()=='C701':continue
 for p in f.Pads():
  if p.IsOnLayer(pcbnew.B_Cu):
   q=p.GetBoundingBox();g=box(*[pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]]);obs.append((p.GetNetname(),g.buffer(.2)))
 for g in f.GraphicalItems():
  if g.GetLayer()==pcbnew.B_CrtYd:
   q=g.GetBoundingBox();courts.append(box(*[pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]]))
foreign={net:unary_union([g for n,g in obs if n!=net]) for net in ['/+3V3_D','/GND']};court=unary_union(courts);c=fs['C701'];out=[]
for angle in [0,90,180,270]:
 c.SetOrientationDegrees(angle)
 for xi in range(1160,1216):
  for yi in range(815,868):
   x,y=xi/10,yi/10;c.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)));pads=list(c.Pads());p1=next(p for p in pads if p.GetNumber()=='1');distance=math.dist(xy(p1.GetPosition()),(119.1,84.425))
   if distance>2.5:continue
   half=(.9,.45)if angle in [0,180]else(.45,.9)
   if court.intersects(box(x-half[0],y-half[1],x+half[0],y+half[1])):continue
   good=True
   for p in pads:
    q=p.GetBoundingBox();g=box(*[pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]])
    if foreign[p.GetNetname()].intersects(g):good=False;break
    for h in holes:
     if h.buffer(.25).intersects(g):good=False;break
    if not good:break
   if good:out.append([round(distance,4),x,y,angle])
out.sort()
report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),reference='C701',source_pad='U701.9',bound_mm=2.5,bounds_mm=[116,81.5,121.5,86.7],step_mm=.1,orientations_deg=[0,90,180,270],excluded_ground_via=list(exclude),candidate_poses=[dict(distance_mm=row[0],position_mm=row[1:3],orientation_deg=row[3]) for row in out],limits=['Prospective C701 move removes only its original ground via; other geometry is retained for the pose screen.', 'Conservative pad/track/via and courtyard bounding model; sampled survivors are candidates, not native-clear or routed placements.', 'Supply and ground continuity, manufacturing profile/native DRC, whole completed-group preservation, PDN/return behavior and assembly must be checked after coordinated routing.'])
(ROOT/'generated/mcu-c701-reservation-review.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(out)} bounded candidate poses; no placement or copper saved')
