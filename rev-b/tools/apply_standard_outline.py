#!/usr/bin/env python3
"""Apply CAD outer wire/mounts to the electrical PCB without touching its nets.

The standard-case candidate remains provisional; this does not certify assembly.
Run after build_standard_case_study.py with the KiCad MCP Python environment.
"""
import json
import sys
import uuid
from pathlib import Path
import sexpdata as sx

ROOT = Path(__file__).resolve().parents[1]


def point(xy):
    return round(100+xy[0], 6), round(100-xy[1], 6)


def main():
    config = json.loads((ROOT/'mechanical/standard-case.json').read_text())
    data = json.loads((ROOT/'generated/1590xx-pcb-outline.json').read_text())
    path = ROOT/'electrical/kestrel-revb.kicad_pcb'
    sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
    from utils.sexpr_format import dumps
    S = sx.Symbol
    board = sx.loads(path.read_text())
    def field(item, name):
        return next(e for e in item if isinstance(e, list) and e and e[0] == S(name))
    board[:] = [e for e in board if not (isinstance(e, list) and e and str(e[0]).startswith('gr_')
                                       and any(isinstance(f, list) and f[:2] == [S('layer'), 'Edge.Cuts'] for f in e))]
    for item in board:
        if isinstance(item, list) and item and item[0] == S('gr_text') and item[1].startswith('REV B:'):
            item[1] = 'REV B: PROVISIONAL 1590XX CANDIDATE / PLACEMENT AND ROUTING DRAFT'
    for i, curve in enumerate(data['curves']):
        start, mid, end = (point(curve[k]) for k in ('start', 'mid', 'end'))
        if curve['kind'] == 'LINE':
            geometry = f'(gr_line (start {start[0]} {start[1]}) (end {end[0]} {end[1]})'
        else:
            geometry = f'(gr_arc (start {start[0]} {start[1]}) (mid {mid[0]} {mid[1]}) (end {end[0]} {end[1]})'
        uid = uuid.uuid5(uuid.NAMESPACE_URL, f'kestrel/rev-b/1590xx/edge/{i}')
        board.append(sx.loads(geometry + f' (stroke (width 0.05) (type default)) (layer "Edge.Cuts") (uuid "{uid}"))'))
    fps = {next(f[2] for f in e if isinstance(f, list) and f[:2] == [S('property'), 'Reference']): e
           for e in board if isinstance(e, list) and e and e[0] == S('footprint')}
    for i, xy in enumerate(config['pcb']['mounts'], 1):
        field(fps[f'H{i}'], 'at')[1:3] = list(point(xy))
    temporary = path.with_suffix('.kicad_pcb.tmp')
    temporary.write_text(dumps(board)+'\n')
    temporary.replace(path)
    report_path = ROOT/'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    report['outline_source'] = 'generated/1590xx-pcb-outline.json'
    report['limits'][0] = 'Mechanical boundary is the provisional notched 1590XX candidate.'
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(f'Applied {len(data["curves"])} CAD line/arc edges and four provisional mounts; electrical placement/nets preserved.')


if __name__ == '__main__':
    main()
