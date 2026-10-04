#!/usr/bin/env python3
"""Review SPI power separation, fixed directions and default-off control nets."""
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
    assert val('U801')=='SN74AXC4T774PWR'
    assert val('U802')=='TPS3808G01DBVR'
    assert val('U803')=='SN74LVC1G00DCKR'
    same(('U801','16'),('U801','1'),('U801','2'),('U801','7'),('U701','9'),('U802','6'),('U803','5'),('R807','1'),('R806','1'),('R809','1'))
    same(('U801','15'),('U501','3'),('R805','1'),('R810','1'))
    same(('U801','10'),('U801','8'),('U701','105'),('U802','2'),('U803','3'),('R808','2'),('R811','2'))
    assert nets['U801','15']!=nets['U801','16']
    for a,b,r,m,f in ((3,14,'R801',4,49),(4,13,'R802',5,55),(5,12,'R803',6,48)):
        same(('U801',str(a)),('U701',str(m)))
        same(('U801',str(b)),(r,'1'));same((r,'2'),('U501',str(f)))
        assert len({nets['U801',str(a)],nets[r,'1'],nets[r,'2']})==3
        assert val(r)=='33ohm'
    same(('U801','11'),('U501','51'));same(('U801','6'),('R804','1'))
    same(('R804','2'),('U701','15'));assert val('R804')=='33ohm'
    same(('R805','2'),('U501','49'));same(('R806','2'),('U701','4'))
    assert val('R805')==val('R806')=='4.7k'
    same(('U801','9'),('U803','4'),('R807','2'))
    same(('U803','1'),('U701','7'),('R808','1'))
    same(('U803','2'),('U802','1'),('R809','2'))
    same(('U802','3'),('U701','103'))
    same(('U802','5'),('R810','2'),('R811','1'),('C805','1'))
    assert sum(name==nets['U802','4'] for name in nets.values())==1, 'CT intentionally open for fixed release delay'
    for c,pin in (('C801',('U801','16')),('C802',('U801','15')),('C803',('U802','6')),('C804',('U803','5'))):
        same((c,'1'),pin);same((c,'2'),('U701','105'));assert val(c)=='100nF'
    for ref in ['C801','C802']:
        assert parts[ref].findtext('footprint')=='Capacitor_SMD:C_0402_1005Metric'
        fields={f.get('name'):f.text for f in parts[ref].findall('./fields/field')}
        assert fields['MPN']=='CL05B104KO5NNNC' and fields['LCSC']=='C1525'
    same(('C805','2'),('U701','105'))
    assert val('R810')=='63.4k' and val('R811')=='10k'
    # TPS3808G01 Rev N full-temperature falling threshold +/-2%, sense +/-25nA;
    # resistor values +/-0.1%. This is deliberately a shutdown isolation guard.
    trip=[v*(1+top/bottom)+i*top for v,top,bottom,i in itertools.product(
        (.405*.98,.405*1.02),(63400*.999,63400*1.001),(10000*.999,10000*1.001),(-25e-9,25e-9))]
    assert max(trip)<3.135
    report={'status':'connectivity and conditional calculation; no hardware qualification',
            'physical_components':len(parts),'falling_trip_nominal_v':.405*7.34,
            'falling_trip_corners_v':[min(trip),max(trip)],'release_delay_ms':[12,28],
            'enable_logic':'OE_N = NOT(GPIO7_enable AND supervised_IO_release)',
            'qualification_pending':['rail ramp/fall and supervisor filter/delay behavior',
                                    'guard is not FPGA minimum-voltage guarantee',
                                    'GPIO7 firmware startup and disable sequence',
                                    '10MHz SPI round-trip timing including FPGA CDC/IO and PCB loads',
                                    'Sydney sourcing, routing and physical assembly/placement qualification']}
    (ROOT/'generated/spi-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: SPI bridge directions, domain separation and default-off control; {len(parts)} integrated components')
if __name__=='__main__':review()
