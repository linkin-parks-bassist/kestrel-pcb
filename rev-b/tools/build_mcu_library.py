#!/usr/bin/env python3
"""Generate P4 v3 symbol and engineering lands from primary package data.

Run after build_audio.py recreates the tables; build_mcu.py instantiates support.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from utils.sexpr_format import dumps

S = sx.Symbol


def footprint(folder):
    """Engineering land extension; source package Fig 6-1 is not a land pattern."""
    name = 'ESP32_P4_QFN104_10x10_P0.35_EP7.5'
    lines = [f'(footprint "{name}" (version 20241229) (generator "pcbnew")',
             '(layer "F.Cu") (attr smd) (clearance 0.127)',
             '(descr "ESP32-P4 v0.7 Fig 6-1 package; engineering lands/paste; assembly review pending")',
             '(property "Reference" "REF**" (at 0 -6.1 0) (layer "F.SilkS") '
             '(effects (font (size 1 1) (thickness 0.15))))',
             f'(property "Value" "{name}" (at 0 6.1 0) (layer "F.Fab") '
             '(effects (font (size 1 1) (thickness 0.15))))',
             '(fp_rect (start -5 -5) (end 5 5) (stroke (width 0.1) (type default)) '
             '(fill none) (layer "F.Fab"))',
             '(fp_line (start -5 -4) (end -4 -5) (stroke (width 0.1) (type default)) '
             '(layer "F.Fab"))',
             '(fp_rect (start -5.45 -5.45) (end 5.45 5.45) '
             '(stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
             '(fp_circle (center -5.3 -5.3) (end -5.22 -5.3) '
             '(stroke (width 0.1) (type solid)) (fill solid) (layer "F.SilkS"))']
    # Top-view counterclockwise numbering: 1 upper left, 26 lower left,
    # 27 lower left on bottom, 52 lower right, 53 lower right on right.
    for number in range(1, 105):
        side, pos = divmod(number-1, 26)
        along = round(-4.375+pos*0.35, 6)
        if side == 0: x, y, angle = -4.9, along, 0
        elif side == 1: x, y, angle = along, 4.9, 90
        elif side == 2: x, y, angle = 4.9, -along, 0
        else: x, y, angle = -along, -4.9, 90
        lines.append(f'(pad "{number}" smd roundrect (at {x} {y} {angle}) '
                     '(size 0.6 0.18) (layers "F.Cu" "F.Paste" "F.Mask") '
                     '(roundrect_rratio 0.2) (solder_mask_margin 0.025))')
    lines.append('(pad "105" smd rect (at 0 0) (size 7.5 7.5) '
                 '(layers "F.Cu" "F.Mask") (solder_mask_margin 0.025))')
    # 36 windows provide 51.84% coverage; 0.3-mm gaps keep the board's
    # 5x5 thermal drill array out of printed paste. Tenting/stencil need review.
    for ix in range(6):
        for iy in range(6):
            x, y = round(-3+ix*1.2,6), round(-3+iy*1.2,6)
            lines.append(f'(pad "" smd rect (at {x} {y}) (size 0.9 0.9) '
                         '(layers "F.Paste"))')
    lines.append(')')
    pretty = folder/'KestrelMCU.pretty'
    pretty.mkdir(exist_ok=True)
    (pretty/(name+'.kicad_mod')).write_text('\n'.join(lines)+'\n')
    table = sx.loads((folder/'fp-lib-table').read_text())
    table[:] = [e for e in table if not (isinstance(e,list) and e and
        e[0] == S('lib') and any(isinstance(x,list) and x[:2] ==
        [S('name'),'KestrelMCU'] for x in e))]
    table.append(sx.loads('(lib (name "KestrelMCU") (type "KiCad") '
                         '(uri "${KIPRJMOD}/KestrelMCU.pretty") (options "") '
                         '(descr "P4 engineering lands; stencil review pending"))'))
    (folder/'fp-lib-table').write_text(dumps(table)+'\n')
    return 'KestrelMCU:'+name


def build():
    data = json.loads((ROOT/'tools/data/esp32_p4_qfn104_v3.json').read_text())
    pins = data['pins']
    assert [p['number'] for p in pins] == list(range(1, 106))
    assert pins[53]['name'] == 'VDD_HP_1'
    name = 'ESP32-P4NRW16X'
    folder = ROOT/'electrical'
    land = footprint(folder)
    effect = '(effects (font (size 1 1)))'
    symbol = sx.loads(f'(symbol "{name}" (pin_names (offset 0.508)) '
                      '(in_bom yes) (on_board yes) '
                      f'(property "Reference" "U" (at 0 0 0) {effect}) '
                      f'(property "Value" "{name}" (at 0 0 0) {effect}) '
                      f'(property "Footprint" "{land}" (at 0 0 0) '
                      '(effects (font (size 1 1)) (hide yes))) '
                      f'(property "Datasheet" "{data["source"]}" (at 0 0 0) '
                      '(effects (font (size 1 1)) (hide yes))))')
    # Separate GPIO groups from power, flash and unused high-speed interfaces.
    gpio = [p for p in pins if p['name'].startswith('GPIO')]
    groups = [[p for p in pins if p not in gpio]]
    groups += [gpio[i:i+16] for i in range(0, len(gpio), 16)]
    output_power = {'VDDO_FLASH', 'VDDO_PSRAM', 'VDDO_3', 'VDDO_4'}
    for unit, group in enumerate(groups, 1):
        height = (len(group)+1)*2.54
        section = sx.loads(f'(symbol "{name}_{unit}_1" '
                           f'(rectangle (start -24.13 {height/2}) '
                           f'(end 24.13 {-height/2}) (stroke (width 0.254) '
                           '(type default)) (fill (type background))))')
        for i, pin in enumerate(group):
            # Analog control/crystal and dedicated interfaces remain passive
            # until their operating roles are assigned in the circuit.
            kind = 'output' if pin['name'] == 'EN_DCDC' else 'passive'
            if pin['type'] == 'IO': kind = 'bidirectional'
            if pin['type'] == 'Dedicated Output': kind = 'output'
            if pin['type'] == 'Dedicated IO': kind = 'bidirectional'
            if pin['type'] == 'Power':
                kind = 'power_out' if pin['name'] in output_power else 'power_in'
            y = round(height/2-(i+1)*2.54, 2)
            section.append(sx.loads(f'(pin {kind} line (at -26.67 {y} 0) '
                                    f'(length 2.54) (name "{pin["name"]}" {effect}) '
                                    f'(number "{pin["number"]}" {effect}))'))
        symbol.append(section)
    library = sx.loads('(kicad_symbol_lib (version 20241209) '
                       '(generator "kicad_symbol_editor"))')
    library.append(symbol)
    (folder/'KestrelMCU.kicad_sym').write_text(dumps(library)+'\n')
    table = sx.loads((folder/'sym-lib-table').read_text())
    def is_mcu(e):
        return (isinstance(e, list) and e and e[0] == S('lib') and
                any(isinstance(x, list) and x[:2] == [S('name'), 'KestrelMCU'] for x in e))
    table[:] = [e for e in table if not is_mcu(e)]
    table.append(sx.loads('(lib (name "KestrelMCU") (type "KiCad") '
                         '(uri "${KIPRJMOD}/KestrelMCU.kicad_sym") (options "") '
                         '(descr "P4 v3 pin table; engineering lands; circuit pending"))'))
    (folder/'sym-lib-table').write_text(dumps(table)+'\n')
    print(folder/'KestrelMCU.kicad_sym')


if __name__ == '__main__':
    build()
