#!/usr/bin/env python3
"""Review native FPGA power poses and bounded pad allocations, not power loops."""
import json,math
import pcbnew
from place_fpga_bypass import ROOT

def main():
    b=pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'));fs={f.GetReference():f for f in b.GetFootprints()};d=json.loads((ROOT/'electrical/fpga-power-placement.json').read_text())
    assert len(d['poses'])==17 and set(d['poses'])=={f'C{i}'for i in range(301,312)}|{f'R{i}'for i in range(301,307)}
    for ref,(x,y,a)in d['poses'].items():
        f=fs[ref];assert f.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(100+x),pcbnew.FromMM(100-y)),ref
        assert abs((f.GetOrientationDegrees()-a+180)%360-180)<.001 and f.GetLayer()==pcbnew.F_Cu,ref
    for ref,(x,y)in {'U301':(72.5,99),'L301':(75,105),'U302':(65,87),'U303':(60,87)}.items():
        f=fs[ref];assert f.GetPosition()==pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y)) and f.GetOrientationDegrees()==0,ref
    ps={r:{p.GetNumber():p for p in f.Pads()}for r,f in fs.items()}
    def net(r,n):return ps[r][n].GetNetname()
    groups={'C301':('/+5V_DIG','/GND'),'C302':('/+1V0_FPGA','/GND'),'C303':('/+1V0_FPGA','/GND'),'R301':('/+1V0_FPGA','CORE_FB'),'R302':('CORE_FB','/GND'),'C304':('/+1V0_FPGA','CORE_FB'),'R303':('/+1V0_FPGA','CORE_SENSE'),'R304':('CORE_SENSE','/GND'),'R305':('/+3V3_D','FPGA_IO_EN'),'R306':('FPGA_IO_EN','/GND'),'C305':('CORE_SENSE','/GND'),'C306':('/+3V3_D','/GND'),'C307':('/+3V3_D','/GND'),'C308':('/+5V_DIG','/GND'),'C309':('IO_RAMP','/GND'),'C310':('/+3V3_FPGA','/GND'),'C311':('CORE_DELAY','/GND')}
    for ref,nets in groups.items():
        for pin,expected in zip(['1','2'],nets):assert net(ref,pin)==(expected if expected.startswith('/')else '/FPGA core and I/O sequencing/'+expected),(ref,pin)
    allocations=[('C301','1','U301','1',5),('C302','1','L301','2',3),('C303','1','L301','2',7),('R301','2','U301','5',4),('R302','1','U301','5',10),('C304','2','U301','5',5),('R303','2','U302','3',6),('R304','1','U302','3',7),('C305','1','U302','3',4),('C306','1','U302','6',5),('C311','1','U302','5',4),('R305','2','U303','3',5),('R306','1','U303','3',6),('C307','1','U303','1',5),('C308','1','U303','4',5),('C309','1','U303','6',8),('C310','1','U303','7',6)]
    review=[]
    for ref,pin,owner,num,bound in allocations:
        p,q=ps[ref][pin],ps[owner][num];assert p.GetNetname()==q.GetNetname(),ref
        v=p.GetPosition()-q.GetPosition();distance=math.hypot(pcbnew.ToMM(v.x),pcbnew.ToMM(v.y));assert distance<=bound,(ref,distance,bound)
        review.append({'pad':ref+'.'+pin,'assigned_pad':owner+'.'+num,'distance_mm':round(distance,4),'provisional_bound_mm':bound})
    result={'status':'PASS seventeen FPGA power support poses, four major poses, 34 passive pad nets and seventeen bounded allocations','placed_references':sorted(d['poses']),'local_allocations':review,'limits':['Pad-centre bounds are provisional placement allocations, not vendor loop limits; core and sequencing local continuity are checked separately by check_fpga_core_local.py and check_fpga_sequence_local.py; main rail feeds are checked by check_fpga_main_feeds.py; FPGA core distribution is checked separately by check_fpga_core_distribution.py; FPGA I/O pin/bulk and assigned support continuity are checked separately by check_fpga_io_distribution.py; remaining switched support supplies are checked separately by check_fpga_support_supply.py; SPI supply continuity is checked separately by check_spi_support_supply.py; local held-DAC buffer supply continuity is checked separately by check_fpga_audio_local.py; DAC supply/pump and full held-rail continuity is checked by check_dac_support_local.py; ADC supply/bypass continuity is checked by check_adc_power_local.py; Analogue signal/bias, protected supply and ground continuity is checked by check_analogue_signal_local.py.','Sequencing circuit relocated into open space left of FPGA to avoid placed flash/bypass parts; qualify actual return paths and distribution.','Effective ceramics, feedback noise, loop stability, current/thermal, ramp/sequence and hardware operation remain unqualified.']}
    (ROOT/'generated/fpga-power-placement-review.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'])
if __name__=='__main__':main()
