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
 p=argparse.ArgumentParser();p.add_argument('--board',default=str(ROOT/'electrical/kestrel-revb.kicad_pcb'));p.add_argument('--start',required=True);p.add_argument('--end',required=True);p.add_argument('--bounds',nargs=4,type=float,required=True,metavar=('XMIN','YMIN','XMAX','YMAX'));p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 b=pcbnew.LoadBoard(args.board);assert b.GetCopperLayerCount()==4 and len(b.Zones())==1 and b.Zones()[0].GetLayer()==pcbnew.In1_Cu and b.Zones()[0].GetNetname()=='/GND','Only current four-layer/single-ground-plane topology is modeled'
 pads={f.GetReference()+'.'+s.GetNumber():s for f in b.GetFootprints()for s in f.Pads()};start,end=[pads[x]for x in [args.start,args.end]];net=start.GetNetname();assert net and end.GetNetname()==net and start.IsOnLayer(pcbnew.F_Cu)and end.IsOnLayer(pcbnew.F_Cu)
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
 def node(pad):
  x,y=pos(pad.GetPosition());ix,iy=round((x-xmin)/step),round((y-ymin)/step)
  q=pad.GetBoundingBox();bounds=[pcbnew.ToMM(v)for v in [q.GetLeft(),q.GetTop(),q.GetRight(),q.GetBottom()]]
  candidates=[(math.hypot(xs[nx]-x,ys[ny]-y),nx,ny,0)for nx in range(ix-1,ix+2)for ny in range(iy-1,iy+2)if 0<=nx<len(xs)and 0<=ny<len(ys)and free[0][ny,nx]and bounds[0]<=xs[nx]<=bounds[2]and bounds[1]<=ys[ny]<=bounds[3]]
  assert candidates,'Pad cannot reach grid'
  _,nx,ny,l=min(candidates);return nx,ny,l
 a,z=node(start),node(end);assert free[0][a[1],a[0]]and free[0][z[1],z[0]],'Pad cannot reach grid'
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
  if vf[y,x]:
   for nl in range(3):
    if nl!=l and free[nl][y,x]:neighbors.append(((x,y,nl,8),3))
  for m,c in neighbors:
   nc=cost+c
   if nc<dist.get(m,float('inf')):dist[m]=nc;prev[m]=n;heapq.heappush(heap,(nc+h(m),nc,m))
 assert found,'No route within bounds; reassess placement rather than expanding without review'
 chain=[found]
 while chain[-1]!=init:chain.append(prev[chain[-1]])
 chain.reverse();paths=[];vias=[];layer=0;points=[pos(start.GetPosition())]
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
 result=dict(status='Candidate only: native DRC, geometry/endpoint and SI/return-path review required',net=net,start=args.start,end=args.end,bounds=args.bounds,paths=paths,via_positions=vias,via_diameter_mm=via_diameter,via_drill_mm=drill,limits=['Conservative pad bounding boxes; pad/footprint local clearance when present, otherwise .2mm, plus .01mm search margin. Vias keep .2mm annulus clearance from every pad land, including their own net.','No board-edge/keepout/custom-rule/return-current/impedance model; reviewed bounds and native DRC required.'])
 args.output.write_text(json.dumps(result,indent=2)+'\n');print(f'Candidate: {len(paths)} paths, {len(vias)} vias; {len(dist)} search states; cost {dist[found]:.3f}')
if __name__=='__main__':main()
