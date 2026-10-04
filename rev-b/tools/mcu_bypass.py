"""Engineering P4 bypass selection; DC-bias/assembly and routed PDN unqualified."""
REFS = {f'C{i}' for i in range(701, 717)}
CAP_FOOTPRINT = 'Capacitor_SMD:C_0402_1005Metric'
RES_FOOTPRINT = 'Resistor_SMD:R_0402_1005Metric'
FIELDS = {'MPN': 'CL05B104KO5NNNC', 'Manufacturer': 'Samsung Electro-Mechanics',
          'LCSC': 'C1525', 'Datasheet': 'https://product.samsungsem.com/mlcc/CL05B104KO5NNN.do'}


def annotate(tree):
    import sexpdata as sx
    for inst in tree:
        if not isinstance(inst, list) or not inst or inst[0] != sx.Symbol('symbol'):
            continue
        fields = {e[1]: e for e in inst if isinstance(e, list) and e and e[0] == sx.Symbol('property')}
        if fields['Reference'][2] not in REFS:
            continue
        for name, value in FIELDS.items():
            if name in fields:
                fields[name][2] = value
            else:
                inst.append([sx.Symbol('property'), name, value,
                             [sx.Symbol('at'), 0, 0, 0],
                             sx.loads('(effects (font (size 1 1)) (hide yes))')])
