"""Selected RGB source damping lands; loaded SI, pulse and assembly remain unqualified."""
REFS={f'R{i}' for i in range(1001,1017)}
FOOTPRINT='Resistor_SMD:R_0402_1005Metric'
FIELDS={'Manufacturer':'YAGEO','MPN':'RC0402FR-0733RL','LCSC':'C138002','Datasheet':'https://www.yageogroup.com/component-documentation/download/specsheet/RC0402FR-0733RL','Rating':'33ohm / 1% / 0.063W at 70C / 50V limiting voltage / GPIO source damping starting value'}
def annotate(tree):
 import sexpdata as sx
 for inst in tree:
  if not isinstance(inst,list) or not inst or inst[0]!=sx.Symbol('symbol'):continue
  fields={e[1]:e for e in inst if isinstance(e,list)and e and e[0]==sx.Symbol('property')}
  if fields['Reference'][2]not in REFS:continue
  fields['Footprint'][2]=FOOTPRINT
  for name,value in FIELDS.items():
   if name in fields:fields[name][2]=value
   else:inst.append([sx.Symbol('property'),name,value,[sx.Symbol('at'),0,0,0],sx.loads('(effects (font (size 1 1)) (hide yes))')])
