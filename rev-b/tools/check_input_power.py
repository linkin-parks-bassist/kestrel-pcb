#!/usr/bin/env python3
"""Check integrated jack/protection polarity and conditional loss calculations.

No fuse/TVS fault coordination or system protection rating is established here.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def review():
    tree = ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets = {(p.get('ref'),p.get('pin')):net.get('name')
            for net in tree.find('nets') for p in net.findall('node')}
    parts = {p.get('ref'):p for p in tree.find('components')}

    def same(*pins):
        assert len({nets[p] for p in pins})==1,pins

    same(('J401','1'),('R401','2'),('D401','2'),('C401','2'),('C402','2'),
         ('U101','1'),('U204','3'))  # Centre pin stays system ground.
    same(('J401','2'),('F401','1'),('TP401','1'))
    assert nets['J401','3'].startswith('unconnected-'), 'Unused sleeve-normal switch must stay NC'
    same(('F401','2'),*(("Q401",str(n)) for n in (5,6,7,8)))  # All drains face input.
    same(*(("Q401",str(n)) for n in (1,2,3)),('D401','1'),('C401','1'),('C402','1'),
         ('TP402','1'),('U101','3'),('U102','3'),('U204','4'),('U203','8'))
    same(('Q401','4'),('R401','1'))
    assert len({nets[p] for p in (('J401','2'),('F401','2'),('Q401','1'),('Q401','4'),('J401','1'))})==5
    for ref,value,foot in (
        ('J401','PJ-102AH','Connector_BarrelJack:BarrelJack_CUI_PJ-102AH_Horizontal'),
        ('F401','1812L200/16DR','Fuse:Fuse_1812_4532Metric'),
        ('Q401','AO4407A','Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'),
        ('D401','SMAJ9.0A','Diode_SMD:D_SMA')):
        assert parts[ref].findtext('value')==value
        assert parts[ref].findtext('footprint')==foot
    libparts = {(p.find('libsource').get('lib'),p.find('libsource').get('part')):p
                for p in tree.find('components')}
    assert ('Device','D_Zener') in libparts, 'Unidirectional TVS must use a K/A symbol'
    assert parts['R401'].findtext('value')=='100k'
    for ref,rating in (('R401','100k / 1%'),('C401','10uF / 35V X7R'),('C402','100nF / 50V X7R')):
        assert parts[ref].find('fields').find("field[@name='Rating']").text==rating
    # Conditional room-temperature component-limit estimate: AO4407A maximum
    # RDS(ON) at -6-V VGS and 10-A ID; PTC post-trip/reflow R1max at 20 C.
    # Neither is an all-temperature system loss bound. Jack/contact/copper
    # resistance and source regulation are excluded.
    r_fet=.017; r_ptc=.070
    cases=[{'input_current_a':i,'fet_drop_v':i*r_fet,'fet_loss_w':i*i*r_fet,
            'ptc_drop_v':i*r_ptc,'ptc_loss_w':i*i*r_ptc,
            'total_series_drop_v':i*(r_fet+r_ptc)} for i in (.5,1,1.5,2)]
    # Healthy 9-V +/-5% allocation, before connector and trace losses.
    lowest_protected=9*.95-cases[-1]['total_series_drop_v']
    assert lowest_protected>6, 'Conditional operating VGS remains beyond -6 V'
    assert 15.4<18  # TVS table value vs TLV767 absolute max; overshoot/temp pending.
    report={
        'status':'conditional schematic engineering review; not system protection validation',
        'connectivity_and_polarity_checked':True,
        'nominal_supply_v':9,'polarity':'centre negative',
        'pmos_body_diode_direction':'fused input drain to protected output source',
        'ptc_20c_hold_a':2,'ptc_20c_trip_a':3.5,'ptc_voltage_rating_v':16,
        'ptc_trip_example':'2 s maximum at 8 A in datasheet; not at 3.5 A',
        'conditional_room_temperature_loss_cases':cases,
        'protected_min_at_2a_v_excluding_connector_and_copper':lowest_protected,
        'tvs_25c_standoff_v':9,'tvs_breakdown_at_1ma_v':[10,11.1],
        'tvs_table_clamp_v':15.4,'tvs_clamp_test_current_a':26,
        'tvs_clamp_waveform':'10/1000 us; pulse derating/layout limitations apply',
        'continuous_overvoltage_protection_established':False,
        'reverse_current_isolation_present':False,
        'remaining_checks':[
            'Complete actual load budget and source/cable requirements; apply PTC hot derating',
            'Qualify TVS residual overshoot/leakage/temperature and PTC/MOSFET fault coordination',
            'Verify reverse-polarity hot-plug, body-diode inrush and reservoir charging',
            'Resolve USB/JTAG/other-source backfeed and negative input leakage',
            'Verify connector mating, retention, case placement and all footprints/stencil',
        ],
    }
    path=ROOT/'generated/input-power-review.json'
    path.write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: centre-negative jack, fused drain/source orientation, K/A TVS and integrated supply nets')
    print(path)


if __name__=='__main__': review()
