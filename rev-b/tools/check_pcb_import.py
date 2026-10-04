#!/usr/bin/env python3
"""Compare serialized PCB pads/identity with the independently exported schematic.

Checks import fidelity, not placement, electrical performance or fabrication.
Run with KiCad's system Python. Staging position is deliberately not prescribed.
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    board = pcbnew.LoadBoard(str(ROOT / 'electrical/kestrel-revb.kicad_pcb'))
    xml = ET.parse(ROOT / 'generated/revb-netlist.xml')
    report = json.loads((ROOT / 'generated/pcb-import-review.json').read_text())
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    assert len(fps) == len(list(board.GetFootprints())), 'Duplicate references'
    components = {c.get('ref'): c for c in xml.findall('./components/comp')}
    excluded = {ref for ref, c in components.items()
                if any(p.get('name') == 'exclude_from_board' for p in c.findall('property'))}
    missing = {ref for ref, c in components.items()
               if ref not in excluded and not c.findtext('footprint')}
    assert excluded == set(report['excluded_panel_components'])
    assert missing == {m['ref'] for m in report['missing_footprints']}
    assert set(fps) == (set(components) - excluded - missing) | {'H1', 'H2', 'H3', 'H4'}
    expected = {(n.get('ref'), n.get('pin')): net.get('name')
                for net in xml.findall('./nets/net') for n in net.findall('node')}
    checked = 0
    for ref in set(components) - excluded - missing:
        fp, comp = fps[ref], components[ref]
        assert fp.GetValue() == comp.findtext('value'), ref
        fid = fp.GetFPID()
        assert f'{fid.GetLibNickname()}:{fid.GetLibItemName()}' == comp.findtext('footprint'), ref
        assert fp.GetPath().AsString() == comp.find('sheetpath').get('tstamps') + comp.findtext('tstamps').split()[0], ref
        side = next((p.get('value', '') for p in comp.findall('property')
                     if p.get('name') == 'AssemblySide'), '')
        assert fp.GetLayer() == (pcbnew.B_Cu if side.startswith('B.Cu') else pcbnew.F_Cu), ref
        numbers = {p.GetNumber() for p in fp.Pads()}
        assert {pin for owner, pin in expected if owner == ref} <= numbers, ref
        for pad in fp.Pads():
            assert pad.GetNetname() == expected.get((ref, pad.GetNumber()), ''), (ref, pad.GetNumber())
            checked += 1
    assert board.GetCopperLayerCount() == 4
    assert report['imported_count'] == len(components) - len(excluded) - len(missing)
    print(f'PASS: {report["imported_count"]} electrical footprints, {checked} pads, hierarchy paths and assembly sides match schematic; {len(missing)} missing footprints explicit; {len(excluded)} panel parts excluded.')


if __name__ == '__main__':
    main()
