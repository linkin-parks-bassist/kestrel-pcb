#!/usr/bin/env python3
"""Import the electrical draft into an unrouted PCB staging area.

Run with KiCad's system Python after exporting revb-netlist.xml. This creates
the board once; it refuses to overwrite subsequent manual placement/routing.
The mechanical boundary is provisional. Missing footprints are reported, never
replaced with invented lands. Panel-mounted components stay off the PCB.
"""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def point(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def natural(ref):
    return tuple(int(s) if s.isdigit() else s for s in re.split(r'(\d+)', ref))


def main():
    target = ROOT / 'electrical/kestrel-revb.kicad_pcb'
    if target.exists():
        raise SystemExit(f'Refusing to overwrite electrical PCB: {target}')
    source = ET.parse(ROOT / 'generated/revb-netlist.xml').getroot()
    board = pcbnew.LoadBoard(str(ROOT / 'generated/kestrel-revb-boundary.kicad_pcb'))
    for drawing in list(board.GetDrawings()):
        if isinstance(drawing, pcbnew.PCB_TEXT):
            board.Remove(drawing)
    nets = {}
    assignments = {}
    for item in source.findall('./nets/net'):
        name = item.get('name')
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        nets[name] = net
        for node in item.findall('node'):
            key = (node.get('ref'), node.get('pin'))
            if key in assignments:
                raise ValueError(f'Duplicate net assignment: {key}')
            assignments[key] = name
    missing, excluded, imported = [], [], []
    groups = {}
    for comp in source.findall('./components/comp'):
        ref = comp.get('ref')
        if any(p.get('name') == 'exclude_from_board' for p in comp.findall('property')):
            excluded.append(ref)
            continue
        footprint = comp.findtext('footprint')
        if not footprint:
            missing.append({'ref': ref, 'value': comp.findtext('value'), 'reason': 'No assigned footprint'})
            continue
        sheet = comp.find('sheetpath').get('names')
        groups.setdefault(sheet, []).append(comp)
    # Sheet groups occupy separate rows outside the board. Parts remain visibly
    # unplaced; generous grid spacing prevents staging courtyard collisions.
    y = 45.0
    for sheet, components in groups.items():
        text = pcbnew.PCB_TEXT(board)
        text.SetText('UNPLACED ' + sheet)
        text.SetPosition(point(195, y - 8))
        text.SetLayer(pcbnew.Dwgs_User)
        text.SetTextSize(point(1, 1))
        board.Add(text)
        for i, comp in enumerate(sorted(components, key=lambda c: natural(c.get('ref')))):
            ref = comp.get('ref')
            library, name = comp.findtext('footprint').split(':', 1)
            folder = ROOT / 'electrical' / (library + '.pretty')
            if not folder.is_dir():
                folder = Path('/usr/share/kicad/footprints') / (library + '.pretty')
            fp = pcbnew.FootprintLoad(str(folder), name)
            if fp is None:
                raise ValueError(f'Cannot load {ref}: {library}:{name}')
            fp.SetReference(ref)
            fp.SetValue(comp.findtext('value'))
            for field in comp.findall('./fields/field'):
                name = field.get('name')
                if name not in ('Reference', 'Value', 'Footprint'):
                    fp.SetField(name, field.text or '')
                    fp.GetField(name).SetVisible(False)
            fp.SetFPID(pcbnew.LIB_ID(library, name))
            path = comp.find('sheetpath').get('tstamps') + comp.findtext('tstamps').split()[0]
            fp.SetPath(pcbnew.KIID_PATH(path))
            fp.SetPosition(point(195 + (i % 12) * 32, y + (i // 12) * 32))
            board.Add(fp)
            side = next((p.get('value', '') for p in comp.findall('property')
                         if p.get('name') == 'AssemblySide'), '')
            if side.startswith('B.Cu'):
                fp.Flip(fp.GetPosition(), False)
            pad_numbers = {pad.GetNumber() for pad in fp.Pads()}
            required = {pin for (owner, pin) in assignments if owner == ref}
            absent = required - pad_numbers
            if absent:
                raise ValueError(f'{ref} footprint lacks connected pads: {sorted(absent)}')
            for pad in fp.Pads():
                name = assignments.get((ref, pad.GetNumber()))
                if name is not None:
                    pad.SetNet(nets[name])
            imported.append(ref)
        y += ((len(components) + 11) // 12) * 32 + 20
    note = pcbnew.PCB_TEXT(board)
    note.SetText('REV B: PROVISIONAL BOUNDARY / ELECTRICAL PARTS UNPLACED / NO ROUTING')
    note.SetPosition(point(100, 100))
    note.SetLayer(pcbnew.Dwgs_User)
    note.SetTextSize(point(1, 1))
    board.Add(note)
    pcbnew.SaveBoard(str(target), board)
    report = {'status': 'unplaced-unrouted-engineering-draft',
              'board': str(target.relative_to(ROOT)), 'imported_count': len(imported),
              'net_count': len(nets), 'excluded_panel_components': excluded,
              'missing_footprints': missing,
              'limits': ['Mechanical boundary remains provisional.',
                         'All electrical footprints are staged outside the board.',
                         'No placement, routing, manufacturing or electrical function is qualified.']}
    (ROOT / 'generated/pcb-import-review.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
