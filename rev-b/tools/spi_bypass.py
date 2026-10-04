"""SPI translator 0402 bypass selection; DC bias, PDN and assembly unqualified."""
from mcu_bypass import CAP_FOOTPRINT,FIELDS
REFS={'C801','C802'}
def annotate(tree):
    import sexpdata as sx
    for inst in tree:
        if not isinstance(inst,list) or not inst or inst[0]!=sx.Symbol('symbol'):continue
        fields={e[1]:e for e in inst if isinstance(e,list) and e and e[0]==sx.Symbol('property')}
        if fields['Reference'][2]not in REFS:continue
        for name,value in FIELDS.items():
            if name in fields:fields[name][2]=value
            else:inst.append([sx.Symbol('property'),name,value,[sx.Symbol('at'),0,0,0],sx.loads('(effects (font (size 1 1)) (hide yes))')])
