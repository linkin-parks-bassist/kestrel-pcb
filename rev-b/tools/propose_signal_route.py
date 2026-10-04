#!/usr/bin/env python3
"""Propose bounded 0.127-mm signal copper; native DRC/review required before saving.

Uses conservative pad bounding boxes and existing copper, not an SI router.
Run with the KiCad MCP venv (pcbnew, numpy, shapely). Never modifies the board.
"""
import argparse,heapq,json,math
from pathlib import Path
import numpy as np
import pcbnew
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely import contains_xy
ROOT=Path(__file__).resolve().parents[1]
LAYERS=[pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]

def main():
 p=argparse.ArgumentParser();p.add_argument('--start-via',help='Existing through-via UUID already physically connected to the start pad');p.add_argument('--layers',nargs='+',choices=['F.Cu','In2.Cu','B.Cu'],default=['F.Cu','In2.Cu','B.Cu'],help='Limit candidate routing layers');p.add_argument('--via-in-pad',action='append',default=[],metavar='REF.PAD',help='Permit a through-via drill inside a named endpoint SMD land');p.add_argument('--board',default=str(ROOT/'electrical/kestrel-revb.kicad_pcb'));p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--bounds',nargs=4,type=float,required=True,metavar=('XMIN','YMIN','XMAX','YMAX'));p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 b=pcbnew.LoadBoard(args.board);assert b.GetCopperLayerCount()==4 and len(b.Zones())==1 and b.Zones()[0].GetLayer()==pcbnew.In1_Cu and b.Zones()[0].GetNetname()=='/GND','Only current four-layer/single-ground-plane topology is modeled'
 pads={f.GetReference()+'.'+s.GetNumber():s for f in b.GetFootprints()for s in f.Pads()};start,end=[pads[x]for x in [args.start,args.end]];net=start.GetNetname();assert net and end.GetNetname()==net and all(any(pad.IsOnLayer(l) for l in LAYERS) for pad in (start,end))
 assert set(args.via_in_pad)<={args.start,args.end}, 'Only named endpoint lands can permit via-in-pad'
 xmin,ymin,xmax,ymax=args.bounds;step=.05;width=.127;clearance=.2;via_diameter=.5;drill=.3;margin=.01
 xs=np.arange(xmin,xmax+step/2,step);ys=np.arange(ymin,ymax+step/2,step);xx,yy=np.meshgrid(xs,ys);obstacles=[[]for _ in LAYERS];via_obstacles=[];lands=[]
 def pos(v):return(pcbnew.ToMM(v.x),pcbnew.ToMM(v.y))
 for f in b.GetFootprints():
  for pad in f.Pads():
   q=pad.GetBoundingBox();g=box(*(pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]));lands.append(g)
   if pad.GetNetname()==net:continue
   for k,l in enumerate(LAYERS):
    if pad.IsOnLayer(l):
     own=pad.GetLocalClearance();own=f.GetLocalClearance()if own is None else own
     obstacles[k].append(g.buffer(pcbnew.ToMM(own)if own is not None else clearance))
   if any(pad.IsOnLayer(l)for l in LAYERS):via_obstacles.append(g)
 for t in b.GetTracks():
  if t.GetNetname()==net:continue
  if isinstance(t,pcbnew.PCB_VIA):g=Point(pos(t.GetPosition())).buffer(pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2);via_obstacles.append(g)
  else:g=LineString([pos(t.GetStart()),pos(t.GetEnd())]).buffer(pcbnew.ToMM(t.GetWidth())/2);via_obstacles.append(g)
  for k,l in enumerate(LAYERS):
   if t.IsOnLayer(l):obstacles[k].append(g.buffer(clearance))
 # In1 is reserved for the GND plane. The proposed through via creates native antipads.
 # Board edges/keepouts/custom rules are not modeled: bounds must be reviewed, then DRC.
 free=[~contains_xy(unary_union(gs).buffer(width/2+margin),xx,yy)for gs in obstacles]
 vf=~contains_xy(unary_union(via_obstacles).buffer(clearance+via_diameter/2+margin).union(unary_union(lands).buffer(clearance+via_diameter/2+margin)),xx,yy)
 # Named endpoint lands permit only native-contained drill circles. All other
 # pad lands and foreign-net copper still constrain every through-via layer.
 for name in args.via_in_pad:
  pad=pads[name];assert pad.GetAttribute()==pcbnew.PAD_ATTRIB_SMD,name
  q=pad.GetBoundingBox();bounds=[pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]]
  others=[g for f in b.GetFootprints()for other in f.Pads()if other.m_Uuid.AsString()!=pad.m_Uuid.AsString()for q in [other.GetBoundingBox()]for g in [box(*(pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]))]]
  possible=~contains_xy(unary_union(via_obstacles+others).buffer(clearance+via_diameter/2+margin),xx,yy)
  side=next(l for l in LAYERS if pad.IsOnLayer(l));poly=pad.GetEffectivePolygon(side)
  for iy in np.flatnonzero((ys>=bounds[1])&(ys<=bounds[3])):
   for ix in np.flatnonzero((xs>=bounds[0])&(xs<=bounds[2])):
    pt=pcbnew.VECTOR2I(pcbnew.FromMM(float(xs[ix])),pcbnew.FromMM(float(ys[iy])))
    if possible[iy,ix] and poly.Contains(pt) and not poly.CollideEdge(pt,None,pcbnew.FromMM(drill/2)):vf[iy,ix]=True
 def node(pad):
  x,y=pos(pad.GetPosition());ix,iy=round((x-xmin)/step),round((y-ymin)/step)
  q=pad.GetBoundingBox();bounds=[pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]]
  layers=[k for k,l in enumerate(LAYERS) if pad.IsOnLayer(l)]
  candidates=[(math.hypot(xs[nx]-x,ys[ny]-y),nx,ny,k)for k in layers for nx in range(ix-1,ix+2)for ny in range(iy-1,iy+2)if 0<=nx<len(xs)and 0<=ny<len(ys)and free[k][ny,nx]and bounds[0]<=xs[nx]<=bounds[2]and bounds[1]<=ys[ny]<=bounds[3]]
  assert candidates,'Pad cannot reach grid'
  _,nx,ny,l=min(candidates);return nx,ny,l
 existing_vias={}
 for t in b.GetTracks():
  if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()==net and t.TopLayer()==pcbnew.F_Cu and t.BottomLayer()==pcbnew.B_Cu:
   x,y=pos(t.GetPosition());ix,iy=round((x-xmin)/step),round((y-ymin)/step)
   if 0<=ix<len(xs) and 0<=iy<len(ys) and abs(xs[ix]-x)<1e-6 and abs(ys[iy]-y)<1e-6:existing_vias[ix,iy]=[round(x,5),round(y,5)]
 source_point=pos(start.GetPosition());source_via=None
 for k,l in enumerate(LAYERS):
  if b.GetLayerName(l) not in args.layers:free[k][:]=False
 if args.start_via:
  source_via=next(t for t in b.GetTracks()if t.m_Uuid.AsString()==args.start_via);assert isinstance(source_via,pcbnew.PCB_VIA) and source_via.GetNetname()==net and source_via.TopLayer()==pcbnew.F_Cu and source_via.BottomLayer()==pcbnew.B_Cu
  conn=b.GetConnectivity();conn.Build(b);pending=[start];seen=set()
  while pending:
   item=pending.pop();uid=item.m_Uuid.AsString()
   if uid not in seen:seen.add(uid);pending.extend(conn.GetConnectedItems(item))
  assert args.start_via in seen, 'Start via is not physically connected to source pad'
  source_point=pos(source_via.GetPosition());ix,iy=round((source_point[0]-xmin)/step),round((source_point[1]-ymin)/step)
  assert (ix,iy) in existing_vias and tuple(existing_vias[ix,iy])==tuple(round(v,5) for v in source_point), 'Start via must align exactly to the reviewed grid'
  a=(ix,iy,next(k for k in [2,1,0]if b.GetLayerName(LAYERS[k]) in args.layers and free[k][iy,ix]))
 else:a=node(start)
 z=node(end);assert free[a[2]][a[1],a[0]]and free[z[2]][z[1],z[0]],'Pad cannot reach grid'
 moves=[(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1)]
 def h(n):return math.hypot(n[0]-z[0],n[1]-z[1])*step+(0 if n[2]==z[2]else 3)
 # Search .05-mm steps; raster proposals need exact native DRC. Turn cost 0.02mm.
 init=(*a,8);dist={init:0};prev={};heap=[(h(a),0,init)];found=None
 while heap:
  _,cost,n=heapq.heappop(heap)
  if cost!=dist.get(n):continue
  x,y,l,d=n
  if (x,y,l)==z:found=n;break
  neighbors=[]
  for nd,(dx,dy)in enumerate(moves):
   nx,ny=x+dx,y+dy
   if not(0<=nx<len(xs)and 0<=ny<len(ys)):continue
   if free[l][ny,nx]and free[l][y+dy,x+dx]:neighbors.append(((nx,ny,l,nd),math.hypot(dx,dy)*step+(.02 if d!=nd else 0)))
  if vf[y,x] or (x,y) in existing_vias:
   for nl in range(3):
    if nl!=l and free[nl][y,x]:neighbors.append(((x,y,nl,8),3))
  for m,c in neighbors:
   nc=cost+c
   if nc<dist.get(m,float('inf')):dist[m]=nc;prev[m]=n;heapq.heappush(heap,(nc+h(m),nc,m))
 assert found,'No route within bounds; reassess placement rather than expanding without review'
 chain=[found]
 while chain[-1]!=init:chain.append(prev[chain[-1]])
 chain.reverse();paths=[];vias=[];layer=a[2];points=[source_point]
 def xy(n):return[round(float(xs[n[0]]),5),round(float(ys[n[1]]),5)]
 def finish():
  # Keep bends and layer endpoints; merging only collinear consecutive segments.
  out=[]
  for pt in points:
   if out and list(pt)==list(out[-1]):continue
   if len(out)>=2:
    a,c=out[-2:];cross=(c[0]-a[0])*(pt[1]-c[1])-(c[1]-a[1])*(pt[0]-c[0])
    if abs(cross)<1e-8:out.pop()
   out.append(list(pt))
  if len(out)>1:paths.append(dict(net=net,layer=b.GetLayerName(LAYERS[layer]),width_mm=width,points=out))
 for n in chain:
  if n[2]!=layer:finish();vias.append(xy(n));layer=n[2];points=[xy(n)]
  else:points.append(xy(n))
 points.append(pos(end.GetPosition()));finish()
 result=dict(start_pad_position=pos(start.GetPosition()),end_pad_position=pos(end.GetPosition()),status='Candidate only: native DRC, geometry/endpoint and SI/return-path review required',net=net,start=args.start,end=args.end,bounds=args.bounds,paths=paths,via_positions=vias,via_diameter_mm=via_diameter,via_drill_mm=drill,limits=['Conservative pad bounding boxes; pad/footprint local clearance when present, otherwise .2mm, plus .01mm search margin. Outside-land new vias keep .2mm annulus clearance from every pad land, including their own net; explicit endpoint via-in-pad permits only native-contained drills with other-pad/copper clearance; existing same-net through-vias can be reused at their exact aligned coordinates.','No board-edge/keepout/custom-rule/return-current/impedance model; reviewed bounds and native DRC required.'])
 reused=[xy for xy in vias if tuple(xy) in map(tuple,existing_vias.values())]
 if source_via is not None and list(source_point) not in reused:reused.append(list(source_point))
 result['existing_via_positions']=reused;result['via_positions']=[xy for xy in vias if xy not in reused]
 result['via_in_pad_anchors']=[{'pad':name,'position':xy} for name in args.via_in_pad for xy in result['via_positions'] if pads[name].GetEffectivePolygon(next(l for l in LAYERS if pads[name].IsOnLayer(l))).Contains(pcbnew.VECTOR2I(pcbnew.FromMM(xy[0]),pcbnew.FromMM(xy[1])))]
 args.output.write_text(json.dumps(result,indent=2)+'\n');print(f'Candidate: {len(paths)} paths, {len(result['via_positions'])} new vias, {len(reused)} reused vias; {len(dist)} search states; cost {dist[found]:.3f}')
if __name__=='__main__':main()
