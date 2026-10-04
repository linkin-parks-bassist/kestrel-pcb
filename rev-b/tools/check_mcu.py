#!/usr/bin/env python3
"""Review bare P4 supply, boot and service nets against primary pin tables."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def review():
    tree = ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets = {(p.get('ref'),p.get('pin')):n.get('name')
            for n in tree.find('nets') for p in n.findall('node')}
    parts = {p.get('ref'):p for p in tree.find('components')}
    def same(*pins):
        assert len({nets[p] for p in pins}) == 1, pins
    same(*(('U701',str(n)) for n in (9,21,62,85,96,101,102,75,77)),('L102','2'))
    same(*(('U701',str(n)) for n in (26,54,76,91)),('L601','2'))
    same(('U701','30'),('U701','71'),('U702','8'))
    same(('U701','59'),('U701','67'),('U701','72'))
    same(('U701','105'),('U702','4'),('U601','2'))
    assert len({nets['U701',str(n)] for n in (9,26,30,59,73,74,105)}) == 7
    for i,n in enumerate((9,21,62,85,96,101,102,75,77,26,54,76,91,30,59,67)):
        ref = f'C{701+i}'
        same(('U701',str(n)),(ref,'1'));same((ref,'2'),('U701','105'))
        assert parts[ref].findtext('value') == '100nF'
        assert parts[ref].findtext('footprint') == 'Capacitor_SMD:C_0402_1005Metric'
        fields = {f.get('name'): f.text for f in parts[ref].findall('./fields/field')}
        assert fields['MPN'] == 'CL05B104KO5NNNC' and fields['LCSC'] == 'C1525'
    for i,(a,b) in enumerate(((27,1),(28,2),(29,3),(31,7),(32,6),(33,5))):
        ref = f'R{701+i}'
        same(('U701',str(a)),(ref,'1'));same(('U702',str(b)),(ref,'2'))
        assert nets[ref,'1'] != nets[ref,'2']
    same(('U702','1'),('R707','2'));same(('U702','8'),('R707','1'),('C729','1'))
    same(('U701','103'),('R710','2'),('C732','1'),('SW701','1'),('J701','5'))
    same(('U701','66'),('R711','2'),('SW702','1'),('J701','6'))
    same(('U701','68'),('R712','2'));same(('U701','65'),('R713','2'))
    for ref in ('R710','R711','R712','R713'):
        same((ref,'1'),('U701','9'));assert parts[ref].findtext('value') == '10k'
    same(('SW701','2'),('SW702','2'),('C732','2'),('J701','1'),('U701','105'))
    same(('J701','2'),('U701','9'));same(('J701','3'),('U701','69'));same(('J701','4'),('U701','70'))
    same(('Y701','2'),('Y701','4'),('U701','105'))
    for n,r,y,c in ((100,'R708',1,'C730'),(99,'R709',3,'C731')):
        same(('U701',str(n)),(r,'1'));same((r,'2'),('Y701',str(y)),(c,'1'))
        same((c,'2'),('U701','105'))
        assert parts[c].findtext('value') == 'TBD'
    same(('U701','52'),('TP701','1'));same(('U701','53'),('TP702','1'))
    for n,a in ((4,49),(5,55),(6,48),(15,51)):
        assert nets['U701',str(n)] != nets['U501',str(a)], 'MCU and FPGA pin domains must remain physically separate'
    report = {'status':'connectivity review, not operation or manufacturing qualification',
              'physical_components':len(parts),'local_input_bypasses':16,
              'remaining':['exact crystal/load capacitors, flash/part sourcing and supply margin',
                           'reset/brownout and boot/programming validation',
                           'RGB/I2C and two-footswitch firmware/timing qualification',
                           'SPI timing/sequencing, USB connector/protection and backfeed',
                           'v3 firmware/toolchain and PCB/assembly qualification']}
    (ROOT/'generated/mcu-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: bare P4 support nets; {len(parts)} integrated components; functional qualification pending')


if __name__ == '__main__':
    review()
