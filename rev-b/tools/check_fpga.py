#!/usr/bin/env python3
"""Review assembled bare FPGA nets against primary pinout and carrier assignments.

This does not establish timing, programmer compatibility or hardware operation.
"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def review():
    tree=ET.parse(ROOT/'generated/revb-netlist.xml').getroot()
    nets={(p.get('ref'),p.get('pin')):n.get('name') for n in tree.find('nets') for p in n.findall('node')}
    parts={p.get('ref'):p for p in tree.find('components')}
    def same(*pins): assert len({nets[p] for p in pins})==1,pins
    same(*(('U501',str(n)) for n in (1,22,45,66)),('L301','2'))
    same(*(('U501',str(n)) for n in (3,12,23,44,58,64,67,78)),('U303','7'),('U502','8'),('Y501','4'))
    same(*(('U501',str(n)) for n in (2,21,24,43,46,65,68,89)),('U301','2'))
    same(('U501','14'),('L501','2'),('C515','1'),('C516','1'),('C517','1'))
    same(('U501','50'),('L502','2'),('C518','1'),('C519','1'),('C520','1'))
    assert len({nets['U501',str(n)] for n in (1,3,14,50,89)})==5,'core, IO, PLL filters and ground must be separate'
    # All physical supplies receive independent local 100-nF bypass.
    for i,n in enumerate((1,3,12,14,22,23,44,45,50,58,64,66,67,78)):
        ref=f'C{501+i}';same(('U501',str(n)),(ref,'1'));same((ref,'2'),('U501','89'))
        assert parts[ref].findtext('value')=='100nF'
    same(('U501','47'),('R501','1'));same(('R501','2'),('U501','89'))
    assert parts['R501'].findtext('value')=='10k'
    for n,r in ((88,'R502'),(87,'R503')):
        same(('U501',str(n)),(r,'1'));same((r,'2'),('U501','89'))
        assert parts[r].findtext('value')=='1k'
    # Primary flash pin functions + Gowin MSPI interface; 03h read mode.
    for a,b in ((59,6),(60,1),(61,5),(62,2)):same(('U501',str(a)),('U502',str(b)))
    assert parts['U502'].findtext('value')=='GD25Q32ESIGR'
    same(('U502','4'),('U501','89'),('R504','2'))
    same(('U502','6'),('R504','1'))
    for r,n in (('R505',1),('R506',3),('R507',7)):
        same((r,'1'),('U502','8'));same((r,'2'),('U502',str(n)))
    for a,b in ((6,1),(7,3),(8,5),(5,9)):same(('U501',str(a)),('J501',str(b)))
    same(('J501','6'),('U501','3'));same(('J501','2'),('J501','10'),('U501','89'))
    same(('U501','9'),('SW501','1'),('R508','2'))
    same(('SW501','2'),('U501','89'))
    # FPGA remains the clock/data source through series damping resistors.
    for a,r,target in ((25,'R513',('U201','6')),(29,'R514',('U201','8')),
                       (26,'R515',('U201','7')),(31,'R516',('U202','14'))):
        same(('U501',str(a)),(r,'1'));same((r,'2'),target)
        assert nets[r,'1']!=nets[r,'2']
    same(('Y501','3'),('R512','1'));same(('R512','2'),('U501','4'))
    # ADC output does not directly feed a switched FPGA input.
    same(('U201','9'),('U503','2'));same(('U503','4'),('R519','1'))
    same(('R519','2'),('U501','30'));same(('U503','5'),('U501','3'))
    same(('U503','1'),('U503','3'),('R518','2'),('U501','89'))
    same(('R518','1'),('U503','2'))
    assert nets['U201','9']!=nets['U501','30']
    same(('U501','20'),('U504','2'),('R517','1'))
    same(('U504','4'),('U206','3'),('U207','3'))
    same(('U504','5'),('U202','20'));same(('R517','2'),('U504','3'),('U501','89'))
    assert nets['U504','2']!=nets['U504','4']
    report={'status':'connectivity review; not hardware validation','physical_components':len([r for r in parts if not r.startswith('#')]),
            'fpga_supplies_and_14_local_bypasses_checked':True,'mspi_flash_checked':True,
            'audio_source_pins_checked':True,'audio_power_domain_buffers_checked':True,
            'remaining':['Exact oscillator/bead/passive selection and Sydney sourcing','PLL/RTL 48kHz and AUDIO_ENABLE migration',
                         'MCU SPI bridge timing/sequencing and intermediate-rail/backfeed qualification','JTAG/flash programming and startup timing validation',
                         'Layout/stencil/thermal and bench validation']}
    (ROOT/'generated/fpga-review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'PASS: bare FPGA power/configuration/audio nets; {report["physical_components"]} integrated components')


if __name__=='__main__':review()
