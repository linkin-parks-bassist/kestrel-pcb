#!/usr/bin/env python3
"""Generate SDRAM QN88 symbol/lands from checked primary-source pin data.

Run after build_audio.py, which recreates the library tables. This adds library
artifacts only; it does not instantiate the bare FPGA in the integrated schematic.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from utils.sexpr_format import dumps

S = sx.Symbol


def node(text): return sx.loads(text)
def child(item, key):
    return next(x for x in item if isinstance(x, list) and x and x[0] == S(key))


def build():
    data = json.loads((ROOT/'tools/data/gw2ar18_qn88.json').read_text())
    pins = data['pins']
    assert {p['number'] for p in pins} == set(range(1, 90))
    folder = ROOT/'electrical'
    name = 'GW2AR-LV18QN88'
    effect = '(effects (font (size 1.0 1.0)))'
    symbol = node(f'(symbol "{name}" (pin_names (offset 0.508)) '
                  '(in_bom yes) (on_board yes) '
                  f'(property "Reference" "U" (at 0 0 0) {effect}) '
                  f'(property "Value" "{name}" (at 0 0 0) {effect}) '
                  '(property "Footprint" "KestrelFPGA:GW2AR_QN88_10x10_P0.4_EP6.8" '
                  '(at 0 0 0) (effects (font (size 1 1)) (hide yes))) '
                  '(property "Datasheet" "https://cdn.gowinsemi.com.cn/UG115E.pdf" '
                  '(at 0 0 0) (effects (font (size 1 1)) (hide yes))))')
    # Power and EXTR in unit 1; individual banks in units 2–9.
    groups = [[p for p in pins if p['bank'] is None]]
    groups += [[p for p in pins if p['bank'] == bank] for bank in range(8)]
    for unit, group in enumerate(groups, 1):
        height = (len(group)+1)*2.54
        section = node(f'(symbol "{name}_{unit}_1" '
                       f'(rectangle (start -24.13 {height/2}) (end 24.13 {-height/2}) '
                       '(stroke (width 0.254) (type default)) (fill (type background))))')
        for i, pin in enumerate(group):
            # General I/O stays bidirectional in the library. Instantiated
            # operating roles and configuration straps need separate review.
            kind = 'bidirectional' if pin['function'] == 'I/O' else 'power_in'
            if pin['name'] == 'EXTR': kind = 'passive'
            y = round(height/2 - (i+1)*2.54, 2)
            section.append(node(f'(pin {kind} line (at -26.67 {y} 0) (length 2.54) '
                                f'(name "{pin["name"]}" {effect}) '
                                f'(number "{pin["number"]}" {effect}))'))
        symbol.append(section)
    library = node('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor"))')
    library.append(symbol)
    (folder/'KestrelFPGA.kicad_sym').write_text(dumps(library)+'\n')

    source = Path('/usr/share/kicad/footprints/Package_DFN_QFN.pretty/'
                  'ArtInChip_QFN-88-1EP_10x10mm_P0.4mm_EP6.74x6.74mm.kicad_mod')
    footprint = sx.loads(source.read_text())
    footprint[1] = 'GW2AR_QN88_10x10_P0.4_EP6.8'
    # Do not represent an unrelated stock STEP model as a verified FPGA body.
    footprint[:] = [e for e in footprint if not (isinstance(e, list) and e and
                    (e[0] == S('model') or (e[0] == S('fp_line') and child(e, 'layer')[1] == 'F.SilkS')))]
    child(footprint, 'descr')[1] = 'Gowin UG229-1.6.5E Fig 4-2 metal lands; stock paste windows; stencil/thermal review pending'
    child(footprint, 'tags')[1] = 'Gowin QN88 SDRAM FPGA'
    for element in footprint:
        if not isinstance(element, list) or not element: continue
        if element[0] == S('property') and element[1] == 'Value': element[2] = footprint[1]
        if element[0] != S('pad') or not str(element[1]).isdigit(): continue
        number = int(element[1])
        if number == 89:
            child(element, 'size')[1:] = [6.8, 6.8]
            continue
        at = child(element, 'at')
        x, y = at[1:3]
        if abs(x) > abs(y):
            at[1] = 4.95 if x > 0 else -4.95
            child(element, 'size')[1:] = [.85, .20]
        else:
            at[2] = 4.95 if y > 0 else -4.95
            child(element, 'size')[1:] = [.20, .85]
    footprint.append(node('(fp_circle (center -5.7 -4.7) (end -5.55 -4.7) '
                          '(stroke (width 0.12) (type solid)) (fill solid) (layer "F.SilkS"))'))
    # Replace stock segmented courtyard with bounds for enlarged metal lands
    # and the external pin-one mark.
    footprint[:] = [e for e in footprint if not (isinstance(e, list) and e and
                    e[0] in (S('fp_line'), S('fp_rect'), S('fp_arc')) and
                    child(e, 'layer')[1] == 'F.CrtYd')]
    footprint.append(node('(fp_rect (start -6.1 -5.65) (end 5.65 5.65) '
                          '(stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))'))
    pretty = folder/'KestrelFPGA.pretty'
    pretty.mkdir(exist_ok=True)
    (pretty/(footprint[1]+'.kicad_mod')).write_text(dumps(footprint)+'\n')
    for file, kind, uri in [('sym-lib-table','KiCad','${KIPRJMOD}/KestrelFPGA.kicad_sym'),
                            ('fp-lib-table','KiCad','${KIPRJMOD}/KestrelFPGA.pretty')]:
        table = sx.loads((folder/file).read_text())
        table[:] = [e for e in table if not (isinstance(e, list) and e and e[0] == S('lib') and child(e, 'name')[1] == 'KestrelFPGA')]
        table.append(node(f'(lib (name "KestrelFPGA") (type "{kind}") (uri "{uri}") '
                          '(options "") (descr "Gowin QN88 SDRAM verified pin data; layout review pending"))'))
        (folder/file).write_text(dumps(table)+'\n')
    print(folder/'KestrelFPGA.kicad_sym')
    print(pretty/(footprint[1]+'.kicad_mod'))


if __name__ == '__main__': build()
