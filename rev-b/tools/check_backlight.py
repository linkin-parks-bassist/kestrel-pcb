#!/usr/bin/env python3
"""Review actual backlight topology and bounded component allocation, not performance."""
import itertools
import json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]

def review():
    tree=ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets={(p.get('ref'),p.get('pin')):n.get('name') for n in tree.find('nets') for p in n.findall('node')}
    parts={p.get('ref'):p for p in tree.find('components')}
    def same(*pins):assert len({nets[p] for p in pins})==1,pins
    def val(ref):return parts[ref].findtext('value')
    assert val('U901')=='TPS61169DCKR' and val('D901')=='SS16-E3/61T'
    same(('U901','5'),('L901','1'),('L101','2'),('C901','1'),('C902','1'),('U902','5'),('C904','1'))
    same(('U901','1'),('L901','2'),('D901','2'))
    same(('D901','1'),('C903','1'),('R904','1'),('TP901','1'))
    same(('U901','3'),('R901','1'),('TP902','1'))
    same(('J1001','1'),('TP902','1'));same(('J1001','2'),('TP901','1'))
    same(('U901','2'),('R901','2'),('U902','1'),('U902','3'),('R902','2'),('R904','2'),('R905','2'),
         *((f'C{n}','2') for n in (901,902,903,904)))
    assert len({nets['U901','5'],nets['U901','1'],nets['TP901','1'],nets['TP902','1'],nets['U901','2']})==5
    same(('U701','8'),('U902','2'),('R902','1'))
    same(('U902','4'),('R903','1'));same(('R903','2'),('U901','4'),('R905','1'))
    assert nets['U701','8']!=nets['U901','4'], 'control crosses through powered-domain buffer'
    assert val('R901')=='5.62ohm' and val('R902')=='10k' and val('R903')=='1k'
    assert val('R904')=='1M' and val('R905')=='100k' and val('L901')=='10uH'
    assert val('C903')=='2.2uF'
    rating=parts['C903'].find('fields').find("field[@name='Rating']").text
    assert '50V' in rating and 'effective >=1uF at 39V' in rating
    currents=[v/r for v,r in itertools.product((.188,.220),(5.62*.99,5.62*1.01))]
    assert max(currents)<.040 and min(currents)>.030
    # Allocation: actual LED forward voltage may differ; efficiency and retained
    # inductance are assumptions to qualify, not guaranteed converter parameters.
    vin=(4.8,5.2);vout=30;iled=.04;eff=.7;l_effective=10e-6*.8*.8;fs=750000
    peaks=[vout*iled/(v*eff)+v*(1-v/vout)/(2*l_effective*fs) for v in vin]
    assert max(peaks)<1.2, 'conditional run current below minimum TI current limit at <=85C'
    report={'status':'connectivity and conditional engineering allocation; not hardware qualification',
            'current_nominal_a':.204/5.62,'current_conditional_corners_a':[min(currents),max(currents)],
            'current_limit_conditions':'TI VIN=3.6V/100% duty/TA>=25C; cold temperature and bias still unverified',
            'inductor_peak_allocated_a':max(peaks),'input_window_allocated_v':vin,'output_voltage_allocated_v':vout,
            'efficiency_assumed':eff,'retained_inductance_assumed_h':l_effective,
            'remaining':['final panel/LED limits and Sydney landed cost','LCD/touch supply qualification and FPC contact fit',
                         'inductor/ceramic MPNs, DC bias and fault/startup limits','GPIO8 PWM firmware',
                         'cold-temperature regulation, EMI/audio noise and thermal/bench validation']}
    (ROOT/'generated/backlight-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: backlight boost polarity/sense/control; conditional full-brightness current below 40mA')
if __name__=='__main__':review()
