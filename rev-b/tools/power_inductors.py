"""Selected regulator inductors; primary catalog values are at 20 C ambient.

Selection does not qualify thermal behavior or regulator fault current. Sunlord
labels its 20%-L-drop current 'Isat(Max)' and 30%-drop current 'Isat(Typ)'.
These are different operating points, not min/max production limits.
"""
DATASHEET = 'https://www.sunlordinc.com/uploads/files/20230303/MWSA-S%C2%A0series%C2%A0of%C2%A0SMD%C2%A0Power%C2%A0Inductor.pdf'
PARTS = {
    'L101': ('MWSA0603S-100MT', 'C132141', 'L_Sunlord_MWSA0603S', '20%-drop 4.4A; 30%-drop 5.5A; DCR max68mOhm'),
    'L102': ('MWSA0603S-6R8MT', 'C408449', 'L_Sunlord_MWSA0603S', '20%-drop 4.8A; 30%-drop 6A; DCR max48mOhm'),
    'L301': ('MWSA0402S-2R2MT', 'C408335', 'L_Sunlord_MWSA0402S', '20%-drop 4A; 30%-drop 5A; DCR max58mOhm'),
    'L601': ('MWSA0402S-2R2MT', 'C408335', 'L_Sunlord_MWSA0402S', '20%-drop 4A; 30%-drop 5A; DCR max58mOhm'),
}


def annotate(tree):
    """Set selection fields on existing connected symbols without altering nets."""
    import sexpdata as sx
    symbol, prop = sx.Symbol('symbol'), sx.Symbol('property')
    for item in tree:
        if not isinstance(item, list) or not item or item[0] != symbol:
            continue
        fields = {p[1]: p for p in item if isinstance(p, list) and p and p[0] == prop}
        ref = fields['Reference'][2]
        if ref not in PARTS:
            continue
        mpn, code, footprint, current = PARTS[ref]
        values = {'MPN': mpn, 'Manufacturer': 'Sunlord', 'LCSC': code,
                  'Footprint': 'Inductor_SMD:' + footprint, 'Datasheet': DATASHEET,
                  'CurrentReview': current + '; catalog at20C; not full-temperature/fault qualification'}
        for name, value in values.items():
            if name in fields:
                fields[name][2] = value
            else:
                item.append(sx.loads(f'(property "{name}" "{value}" (at 0 0 0) '
                                     '(effects (font (size 1 1)) (hide yes)))'))
