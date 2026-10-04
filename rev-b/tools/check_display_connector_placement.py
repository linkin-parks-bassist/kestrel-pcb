#!/usr/bin/env python3
"""Verify connector support poses/pad nets and bounded bypass proximity, not loops or fit."""
import argparse,json,xml.etree.ElementTree as ET
import pcbnew
from place_display_connector import ROOT
p=argparse.ArgumentParser();p.add_argument('--board');p.add_argument('--trial',action='store_true');args=p.parse_args()
b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/display-connector-placement.json').read_text());fps={f.GetReference():f for f in b.GetFootprints()};xml=ET.parse(ROOT/'generated/revb-netlist.xml')
assert set(d['poses'])=={f'C{i}'for i in range(1001,1005)}|{f'R{i}'for i in range(1026,1031)}
checked={}
for ref,(x,y,a)in d['poses'].items():
 f=fps[ref];assert f.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(100+x),pcbnew.FromMM(100-y)) and abs((f.GetOrientationDegrees()-a+180)%360-180)<.001 and f.GetLayer()==pcbnew.F_Cu
 nets={p.GetNumber():p.GetNetname()for p in f.Pads()};expected={node.attrib['pin']:n.attrib['name']for n in xml.findall('.//nets/net')for node in n.findall('node')if node.attrib['ref']==ref};assert nets==expected,(ref,nets,expected);checked[ref]=nets
pairs=[('C1001.1','J1001.4'),('C1002.2','J1001.29'),('C1003.1','J1002.2'),('C1004.1','J1002.3')]
pads={f.GetReference()+'.'+p.GetNumber():p for f in b.GetFootprints()for p in f.Pads()};dist={a+'→'+c:pcbnew.ToMM((pads[a].GetPosition()-pads[c].GetPosition()).EuclideanNorm())for a,c in pairs};assert all(x<=4 for x in dist.values()),dist
electrical=[f for f in b.GetFootprints()if not f.GetReference().startswith('H')];placed=sum(pcbnew.ToMM(f.GetPosition().x)<190 for f in electrical)
result={'placed_electrical_parts':placed,'staged_electrical_parts':len(electrical)-placed,'status':'PASS nine connector support poses, exact XML pad nets and four provisional bypass proximity bounds','pad_nets':checked,'bypass_pad_distance_mm':dist,'limits':['4 mm pad-centre allocation is an engineering target, not effective bypass/PDN or assembled flex/body-fit qualification.','C1002 is a distributed LCD-rail bypass near connector ground29; distance to the single LCD supply contact4 is not a near-pin check.','Loaded rail/noise, RGB/I2C timing, power-off/backfeed and manufacturing/assembly remain unqualified.']}
if not args.trial:(ROOT/'generated/display-connector-placement-review.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS nine display connector support poses, exact XML pad nets and four bounded bypass distances',dist)
