#!/usr/bin/env python3
"""Check actual dual footswitch nets and bounded DC/RC allocation."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]

def review():
    tree=ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets={(p.get('ref'),p.get('pin')):n.get('name') for n in tree.find('nets') for p in n.findall('node')}
    parts={p.get('ref'):p for p in tree.find('components')}
    def same(*pins):assert len({nets[p] for p in pins})==1,pins
    for i,pad in enumerate((22,23)):
        j,u,d,sw=(f'{p}{1101+i}' for p in ('J','U','D','SW'))
        series,pull,out=(f'R{1101+3*i+k}' for k in range(3))
        rc,bypass=(f'C{1101+2*i+k}' for k in range(2))
        same((j,'1'),(sw,'1'),(d,'1'),(series,'1'))
        same((series,'2'),(pull,'2'),(rc,'1'),(u,'2'))
        same((pull,'1'),(bypass,'1'),(u,'5'),('U701','21'))
        same((u,'3'),(rc,'2'),(bypass,'2'),(j,'2'),(sw,'2'),(d,'2'),('U701','105'))
        same((u,'4'),(out,'1'));same((out,'2'),('U701',str(pad)))
        assert len({nets[j,'1'],nets[u,'2'],nets[u,'4'],nets[out,'2'],nets[u,'3'],nets[u,'5']})==6
        assert parts[series].findtext('value')=='1k' and parts[pull].findtext('value')=='10k'
        assert parts[out].findtext('value')=='33ohm' and parts[u].findtext('value')=='SN74LVC1G17DCKR'
        assert parts[d].findtext('value')=='PESD5V0U1BA,115'
        assert parts[sw].find("property[@name='exclude_from_board']") is not None
        assert not parts[sw].findtext('footprint'), 'panel switch must not import onto PCB'
        rating=parts[rc].find('fields').find("field[@name='Rating']").text
        assert 'effective 80..120nF' in rating
    assert nets['U701','22']!=nets['U701','23']
    # Leakage allocation: TI input <=5uA plus an additional assumed 5uA for
    # board/capacitor contamination. Selected parts and temperature must verify it.
    vin_lo,vin_hi=3.2060,3.3826
    high_lo=vin_lo-10e-6*10100
    low_hi=vin_hi*1010/(9900+1010)+10e-6*(1010*9900/(1010+9900))
    assert high_lo>2.74 and low_hi<.89
    close_current=(vin_lo/11110,vin_hi/10890)
    rise_tau=(9900*80e-9,10100*120e-9)
    fall_tau=(990*9900/(990+9900)*80e-9,1010*10100/(1010+10100)*120e-9)
    result={'status':'connectivity/DC allocation, not contact debounce or hardware validation',
            'inactive_input_lowest_allocated_v':high_lo,'pressed_input_highest_allocated_v':low_hi,
            'contact_current_a':close_current,'rise_rc_s':rise_tau,'fall_rc_s':fall_tau,
            'threshold_comparison':'TI 3V/4.5V tabulated extremes .89V negative minimum and 2.74V positive maximum; not a guaranteed interpolation over the main rail',
            'assumed_total_leakage_a':10e-6,
            'remaining':['dry-contact reliability and exact switch/geometry/Sydney quote',
                         'rail/temperature threshold and RC component qualification',
                         'ESD residual/input stress and wiring/enclosure grounding',
                         'firmware edge/debounce semantics and pressed-at-boot behavior','physical loads and bench tests']}
    (ROOT/'generated/footswitch-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS: two active-low GPIO20/21 footswitch inputs, RC/Schmitt topology and conditional DC allocation')

if __name__=='__main__':review()
