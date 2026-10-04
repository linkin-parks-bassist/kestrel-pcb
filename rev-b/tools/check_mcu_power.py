#!/usr/bin/env python3
"""Check HP regulator topology against P4 v3/TI pin tables, not operation."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def review():
    tree = ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets = {(p.get('ref'), p.get('pin')): n.get('name')
            for n in tree.find('nets') for p in n.findall('node')}
    parts = {p.get('ref'): p for p in tree.find('components')}
    def same(*pins):
        assert len({nets[p] for p in pins}) == 1, pins
    same(('U601','4'),('C601','1'),('C602','1'),('L102','2'))
    same(('U601','2'),('C601','2'),('C602','2'),('C603','2'),
         ('C604','2'),('R602','2'),('U501','89'))
    same(('U601','3'),('L601','1'))
    same(('L601','2'),('C603','1'),('C604','1'),('R601','1'),('C605','1'))
    same(('U601','5'),('R601','2'),('R602','1'),('C605','2'))
    same(('U601','1'),('U701','79'))
    same(('U601','5'),('U701','78'))
    same(('L601','2'),*(('U701',str(n)) for n in (26,54,76,91)))
    assert nets['U601','1'] == '/MCU_EN_DCDC'
    assert nets['U601','5'] == '/MCU_FB_DCDC'
    assert nets['L601','2'] == '/ESP_VDD_HP'
    # Separate enable, feedback, input, switch, HP and FPGA core domains.
    assert len({nets['U601',str(n)] for n in range(1,6)} |
               {nets['L601','2'],nets['U501','1']}) == 7
    assert parts['U601'].findtext('value') == 'TLV62569DBVR'
    for r in ('R601','R602'):
        assert parts[r].findtext('value') == '499k'
    assert parts['C605'].findtext('value') == '22pF'
    for c in ('C603','C604'):
        assert parts[c].findtext('value') == '22uF'
    report = {'status':'connectivity checked; hardware qualification pending',
              'physical_components':len(parts),
              'remaining':['source/load budget and exact L/C procurement',
                           'controlled feedback stability and boot/sleep/brownout validation']}
    (ROOT/'generated/mcu-power-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: P4 controlled HP topology and MCU connections, separate FPGA core')


if __name__ == '__main__':
    review()
