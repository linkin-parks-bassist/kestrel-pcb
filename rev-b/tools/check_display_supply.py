#!/usr/bin/env python3
"""Check instantiated LCD regulator and conditional DC bounds, not ramp behavior."""
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
    assert parts['U903'].findtext('value') == 'TLV76701DRVR'
    same(('U903','6'), ('U903','4'), ('C905','1'), ('U901','5'))
    same(('U903','1'), ('R906','1'), ('C906','1'), ('C907','1'), ('TP903','1'))
    same(('U903','2'), ('R906','2'), ('R907','1'), ('C907','2'))
    same(('U903','3'), ('U903','5'), ('U903','7'), ('R907','2'),
         ('C905','2'), ('C906','2'), ('U901','2'))
    assert len({nets['U903','6'],nets['U903','1'],nets['U903','2'],nets['U903','3']}) == 4
    assert nets['U903','1'] != nets['U701','21'], 'LCD supply must not tie to main MCU rail'
    assert parts['R906'].findtext('value') == '33.2k'
    assert parts['R907'].findtext('value') == '10k'
    for ref in ('R906','R907'):
        assert '0.1%' in parts[ref].find('fields').find("field[@name='Rating']").text
    for ref in ('C905','C906'):
        assert 'effective >=1uF' in parts[ref].find('fields').find("field[@name='Rating']").text
    upper, lower, tolerance, ref_tolerance, ibias = 33200, 10000, .001, .01, 50e-9
    lo = .8*(1-ref_tolerance)*(1+upper*(1-tolerance)/(lower*(1+tolerance)))-ibias*upper*(1+tolerance)
    hi = .8*(1+ref_tolerance)*(1+upper*(1+tolerance)/(lower*(1-tolerance)))+ibias*upper*(1+tolerance)
    assert 3.3 < lo < hi < 3.6
    # P4 VOH/VOL specification is for high-impedance loads. These static margins
    # do not cover series-resistor drop, settling, unpowered inputs or rail ramps.
    high_margin = .8*3.2060-.7*hi
    low_margin = .3*lo-.1*3.3826
    assert high_margin > 0 and low_margin > 0
    assert parts['U904'].findtext('value') == 'TLV76701DRVR'
    same(('U904','6'),('U904','4'),('C908','1'),('U901','5'))
    same(('U904','1'),('R908','1'),('C909','1'),('C910','1'),('TP904','1'),('J1002','2'),('J1002','3'))
    same(('U904','2'),('R908','2'),('R909','1'),('C910','2'))
    same(('U904','3'),('U904','5'),('U904','7'),('R909','2'),('C908','2'),('C909','2'),('U901','2'))
    assert len({nets['U904','1'],nets['U903','1'],nets['U701','21']}) == 3
    assert parts['R908'].findtext('value') == '30k' and parts['R909'].findtext('value') == '10k'
    for ref in ('R908','R909'):
        assert '0.1%' in parts[ref].find('fields').find("field[@name='Rating']").text
    for ref in ('C908','C909'):
        assert 'effective >=1uF' in parts[ref].find('fields').find("field[@name='Rating']").text
    touch_lo=.8*.99*(1+30000*.999/(10000*1.001))-50e-9*30000*1.001
    touch_hi=.8*1.01*(1+30000*1.001/(10000*.999))+50e-9*30000*1.001
    assert 2.8 < touch_lo < touch_hi < 3.3, 'GT911 recommended range, not absolute max'
    touch_margins={'mcu_to_touch_high':.8*3.2060-.75*touch_hi,
                   'mcu_to_touch_low':.25*touch_lo-.1*3.3826,
                   'touch_to_mcu_high':.85*touch_lo-.75*3.3826,
                   'touch_to_mcu_low':.25*3.2060-.15*touch_hi,
                   'mcu_high_vs_touch_input_ceiling':touch_lo+.3-3.3826}
    assert min(touch_margins.values()) > 0
    result = {'status':'topology and conditional static allocation; not hardware qualification',
              'nominal_v':.8*(1+upper/lower), 'conditional_dc_bounds_v':[lo,hi],
              'static_high_margin_v':high_margin,'static_low_margin_v':low_margin,
              'touch_nominal_v':3.2,'touch_conditional_dc_bounds_v':[touch_lo,touch_hi],
              'touch_static_margins_v':touch_margins,
              'conditions':'TI reference +/-1%, divider +/-0.1%, feedback current magnitude <=50nA; regulated operation and sufficient input headroom assumed',
              'remaining':['effective capacitance and exact parts','panel maximum load and thermal budget',
                           '5V headroom/load-line qualification','FPC contact fit and touch reset/address firmware',
                           'loaded GPIO timing and power-off/backfeed qualification']}
    (ROOT/'generated/display-supply-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: separate LCD/touch supplies; conditional DC bounds within recommended ranges')

if __name__ == '__main__':
    review()
