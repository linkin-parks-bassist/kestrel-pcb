#!/usr/bin/env python3
"""Check underside RGB damping identities/nets and bounded source-pad proximity, not SI."""
import argparse,json,xml.etree.ElementTree as ET
import pcbnew
from place_display_rgb_damping import ROOT
p=argparse.ArgumentParser();p.add_argument('--board');p.add_argument('--trial',action='store_true');args=p.parse_args()
b=pcbnew.LoadBoard(args.board or str(ROOT/'electrical/kestrel-revb.kicad_pcb'));d=json.loads((ROOT/'electrical/display-rgb-damping-placement.json').read_text());fps={f.GetReference():f for f in b.GetFootprints()};xml=ET.parse(ROOT/'generated/revb-netlist.xml')
assert d['layer']=='B.Cu' and set(d['poses'])=={f'R{i}'for i in range(1001,1017)}
pins=[80,81,82,83,84,86,87,88,89,90,92,93,94,95,97,98]
mpads={p.GetNumber():p for p in fps['U701'].Pads()};checked={}
for i,(ref,(x,y,a))in enumerate(sorted(d['poses'].items())):
 f=fps[ref];assert f.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(100+x),pcbnew.FromMM(100-y)) and abs((f.GetOrientationDegrees()-a+180)%360-180)<.001 and f.GetLayer()==pcbnew.B_Cu,ref
 assert f'{f.GetFPID().GetLibNickname()}:{f.GetFPID().GetLibItemName()}'=='Resistor_SMD:R_0603_1608Metric' and f.GetValue()=='33ohm',ref
 assert f.GetField('AssemblySide').GetText()=='B.Cu / source damping passives; assembly qualification pending',ref
 pads={p.GetNumber():p for p in f.Pads()};nets={n:p.GetNetname()for n,p in pads.items()};expected={node.attrib['pin']:n.attrib['name']for n in xml.findall('.//nets/net')for node in n.findall('node')if node.attrib['ref']==ref};assert nets==expected,(ref,nets,expected)
 source=mpads[str(pins[i])];assert source.GetNetname()==nets['1'] and nets['1']!=nets['2'],ref
 distance=pcbnew.ToMM((pads['1'].GetPosition()-source.GetPosition()).EuclideanNorm());assert distance<=6.5,(ref,distance)
 checked[ref]={'pad_nets':nets,'mcu_source_pad':str(pins[i]),'source_pad_distance_mm':distance}
electrical=[f for f in b.GetFootprints()if not f.GetReference().startswith('H')];placed=sum(pcbnew.ToMM(f.GetPosition().x)<190 for f in electrical)
result={'status':'PASS sixteen underside RGB damping poses, exact XML pad nets, independent MCU pad mapping and bounded source proximity','placed_electrical_parts':placed,'staged_electrical_parts':len(electrical)-placed,'allocations':checked,'limits':['6.5 mm straight-line pad-centre allocation is an engineering placement bound, not routed source-stub length or loaded SI/timing qualification.','Source/FPC routes remain unfinished; placement establishes no legal via sites.','Dual-side passive assembly, solder access, enclosure clearance, exact parts, source damping, return paths and loaded RGB timings remain unqualified.']}
if not args.trial:(ROOT/'generated/display-rgb-damping-placement-review.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS sixteen underside RGB damping poses; source-pad distance range',min(v['source_pad_distance_mm']for v in checked.values()),max(v['source_pad_distance_mm']for v in checked.values()))
