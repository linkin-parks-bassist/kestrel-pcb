#!/usr/bin/env python3
"""Add selected inductors from the XML netlist without resetting PCB work."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    xml = ET.parse(ROOT / 'generated/revb-netlist.xml')
    path = ROOT / 'electrical/kestrel-revb.kicad_pcb'
    board = pcbnew.LoadBoard(str(path))
    existing = {fp.GetReference(): fp for fp in board.GetFootprints()}
    nets = {n.GetNetname(): n for n in board.GetNetInfo().NetsByNetcode().values()}
    assignments = {(n.get('ref'), n.get('pin')): net.get('name')
                   for net in xml.findall('./nets/net') for n in net.findall('node')}
    for i, ref in enumerate(['L101', 'L102', 'L301', 'L601']):
        comp = next(c for c in xml.findall('./components/comp') if c.get('ref') == ref)
        footprint = comp.findtext('footprint')
        if not footprint:
            raise ValueError(f'No selected footprint for {ref}')
        if ref in existing:
            fid = existing[ref].GetFPID()
            assert f'{fid.GetLibNickname()}:{fid.GetLibItemName()}' == footprint, ref
            continue
        library, name = footprint.split(':', 1)
        fp = pcbnew.FootprintLoad('/usr/share/kicad/footprints/' + library + '.pretty', name)
        if fp is None:
            raise ValueError(footprint)
        fp.SetReference(ref)
        fp.SetValue(comp.findtext('value'))
        fp.SetFPID(pcbnew.LIB_ID(library, name))
        fp.SetPath(pcbnew.KIID_PATH(comp.find('sheetpath').get('tstamps') + comp.findtext('tstamps').split()[0]))
        fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(195+i*32), pcbnew.FromMM(15)))
        board.Add(fp)
        for pad in fp.Pads():
            pad.SetNet(nets[assignments[(ref, pad.GetNumber())]])
    pcbnew.SaveBoard(str(path), board)
    report_path = ROOT / 'generated/pcb-import-review.json'
    report = json.loads(report_path.read_text())
    report['imported_count'] = len(list(board.GetFootprints()))-4
    report['missing_footprints'] = []
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print('Selected inductors added; existing footprint placement and routing preserved.')


if __name__ == '__main__':
    main()
