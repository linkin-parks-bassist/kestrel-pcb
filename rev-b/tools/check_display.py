#!/usr/bin/env python3
"""Check reference-panel pinout and actual QFN GPIO routing from integrated XML."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]

def review():
    tree=ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets={(p.get('ref'),p.get('pin')):n.get('name') for n in tree.find('nets') for p in n.findall('node')}
    parts={p.get('ref'):p for p in tree.find('components')}
    def same(*pins):assert len({nets[p] for p in pins})==1,pins
    # Independent expected QFN pad / panel pin map from Espressif Table 2-1 and
    # DM-TFT50-404 section 3.1. Do not import generator's GPIO contract here.
    data=[(80,24),(81,25),(82,26),(83,27),(84,28),
          (86,15),(87,16),(88,17),(89,18),(63,19),(92,20),
          (55,8),(94,9),(57,10),(97,11),(60,12)]
    timing=[(10,30),(11,32),(12,33),(13,34),(14,31)]
    for i,(mcu,panel) in enumerate(data+timing):
        ref=f'R{1001+i}'
        same(('U701',str(mcu)),(ref,'1'));same((ref,'2'),('J1001',str(panel)))
        assert nets[ref,'1']!=nets[ref,'2']
        assert parts[ref].findtext('value')=='33ohm'
        if i < 16:
            assert parts[ref].findtext('footprint')=='Resistor_SMD:R_0402_1005Metric',ref
            fields={f.get('name'):f.text for f in parts[ref].findall('fields/field')}
            assert fields['Manufacturer']=='YAGEO' and fields['MPN']=='RC0402FR-0733RL' and fields['LCSC']=='C138002',ref
    for i,(mcu,panel) in enumerate(((16,4),(17,5),(18,6),(19,7)),22):
        ref=f'R{1000+i}'
        same(('U701',str(mcu)),(ref,'1'));same((ref,'2'),('J1002',str(panel)))
        assert nets[ref,'1']!=nets[ref,'2'] and parts[ref].findtext('value')=='33ohm'
    same(('U903','1'),('J1001','4'),('C1001','1'),('C1002','1'))
    same(('U904','1'),('J1002','2'),('J1002','3'),('C1003','1'),('C1004','1'),('R1026','1'),('R1027','1'))
    same(('J1002','4'),('R1026','2'));same(('J1002','5'),('R1027','2'))
    same(('J1001','31'),('R1028','1'));same(('J1002','7'),('R1029','1'));same(('J1002','6'),('R1030','1'))
    ground=[('U701','105'),('J1002','1'),('J1002','8'),('R1028','2'),('R1029','2'),('R1030','2')]
    ground += [('J1001',str(n)) for n in (3,5,6,7,13,14,21,22,23,29,36)]
    ground += [(f'C{n}','2') for n in range(1001,1005)]
    same(*ground)
    for ref in ('R1026','R1027'):assert parts[ref].findtext('value')=='4.7k'
    for ref in ('R1028','R1029'):assert parts[ref].findtext('value')=='10k'
    assert parts['R1030'].findtext('value')=='100k'
    same(('J1001','1'),('U901','3'));same(('J1001','2'),('D901','1'))
    assert nets['J1001','1']!=nets['U701','105'], 'LED cathode must retain current-sense return'
    for pin in (35,37,38,39,40):
        net=nets.get(('J1001',str(pin)))
        if net:
            assert sum(1 for v in nets.values() if v==net)==1, ('unused panel pin',pin)
    assert len({nets['U701',str(n)] for n,_ in data+timing})==21
    result={'status':'reference pinout/connectivity review, not display operation or contact qualification',
            'rgb565_data_bits':16,'lcd_timing_control_lines':5,'touch_lines':4,
            'physical_components':len(parts),
            'remaining':['panel procurement/Sydney cost','FPC contact side/numbering/thickness and actual tail bends',
                         'bus timing/source damping and capacitive load','I2C rise/sink and GT911 reset/address firmware',
                         'rail ramps, unpowered input backfeed and EMI/physical qualification']}
    (ROOT/'generated/display-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'PASS: RGB565/touch reference pinout and QFN GPIO routes; {len(parts)} integrated components')

if __name__=='__main__':review()
