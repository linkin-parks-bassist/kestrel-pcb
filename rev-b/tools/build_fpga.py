#!/usr/bin/env python3
"""Generate bare QN88 FPGA support; engineering draft, no hardware validation.

Run after build_audio.py and build_fpga_library.py, before build_project.py.
"""
import json
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27
sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps

S = sx.Symbol
def node(text): return sx.loads(text)
def child(e, key): return next(x for x in e if isinstance(x,list) and x and x[0]==S(key))
def uid(text): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'kestrel/rev-b/fpga/'+text))


def build():
    folder = ROOT/'electrical'
    path = folder/'kestrel-revb-fpga.kicad_sch'
    path.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") '
                   f'(generator_version "10.0") (uuid "{uid("sheet")}") (paper "A2") '
                   '(lib_symbols) (sheet_instances (path "/" (page "1"))))')
    data = json.loads((ROOT/'tools/data/gw2ar18_qn88.json').read_text())
    part = data['part']
    # Preserve carrier audio, clock and control SPI assignments. Serial signal
    # role changes and boot defaults must be implemented in the Rev-B bitstream.
    assigned = {4:'FPGA_CLK',5:'JTAG_TMS',6:'JTAG_TCK',7:'JTAG_TDI',8:'JTAG_TDO',
                9:'RECONFIG_N',20:'ENABLE_FPGA',25:'MCLK_FPGA',26:'LRCLK_FPGA',
                29:'BCLK_FPGA',30:'ADC_BUF',31:'DAC_FPGA',
                48:'MCU_SPI_MOSI',49:'MCU_SPI_CS',51:'MCU_SPI_MISO',55:'MCU_SPI_CLK',
                59:'CONFIG_CLK',60:'FLASH_CS',61:'FLASH_DI',62:'FLASH_DO',
                87:'MODE1',88:'MODE0',47:'EXTR'}
    fpga_nets = {}
    for p in data['pins']:
        n=p['number']; name=p['name']
        if n in assigned: net=assigned[n]
        elif name=='VCC': net='+1V0_FPGA'
        elif name=='VCCPLLL1': net='PLL_L_1V0'
        elif name=='VCCPLLR1': net='PLL_R_1V0'
        elif name.startswith('VCC'): net='+3V3_FPGA'
        elif name in ('VSS','EPAD'): net='GND'
        else: net=None
        fpga_nets[str(n)]=net
    cap='Capacitor_SMD:C_0603_1608Metric'; res='Resistor_SMD:R_0603_1608Metric'
    parts=[]
    def add(ref,lib,value,foot,x,y,nets,angle=0,unit=1):
        parts.append((ref,lib,value,foot,round(x/GRID),round(y/GRID),angle,nets,unit))
    positions=[(70,75),(160,50),(235,55),(315,50),(420,65),
               (70,170),(160,170),(255,170),(345,165)]
    for unit,(x,y) in enumerate(positions,1):
        group=[p for p in data['pins'] if p['bank']==(None if unit==1 else unit-2)]
        add('U501','KestrelFPGA:GW2AR-LV18QN88',part,
            'KestrelFPGA:GW2AR_QN88_10x10_P0.4_EP6.8',x,y,
            {str(p['number']):fpga_nets[str(p['number'])] for p in group},unit=unit)
    # Separate PLL filters. Bead impedance/DC resistance and capacitors remain
    # procurement constraints rather than unverified orderable part numbers.
    for i,label in enumerate(('L','R')):
        add(f'L{501+i}','Device:FerriteBead','220ohm@100MHz / DCR <=0.1ohm / MPN pending',
            'Inductor_SMD:L_0603_1608Metric',65+75*i,245,{'1':'+1V0_FPGA','2':f'PLL_{label}_1V0'},angle=90)
        for j,(value,xx) in enumerate([('4.7uF / 16V X7R',80),('100nF / 16V X7R',100),('10nF / 16V X7R',120)]):
            add(f'C{515+i*3+j}','Device:C',value,cap,xx+75*i,265,
                {'1':f'PLL_{label}_1V0','2':'GND'})
        add(f'#FLG05{1+i:02}','power:PWR_FLAG','PWR_FLAG','',88+75*i,235,{'1':f'PLL_{label}_1V0'})
    supply_pins=[1,3,12,14,22,23,44,45,50,58,64,66,67,78]
    for i,n in enumerate(supply_pins):
        add(f'C{501+i}','Device:C',f'100nF / 16V X7R / at U501 pin {n}',cap,
            35+(i%7)*25,320+(i//7)*25,{'1':fpga_nets[str(n)],'2':'GND'})
    add('C521','Device:C','4.7uF / 16V X7R / local core bulk',cap,225,320,{'1':'+1V0_FPGA','2':'GND'})
    add('C522','Device:C','4.7uF / 16V X7R / local IO bulk',cap,245,320,{'1':'+3V3_FPGA','2':'GND'})
    # Standard 03h Read mode, leave FASTRD_N57 floating, MSPI MODE000.
    add('U502','Memory_Flash:W25Q32JVSS','GD25Q32ESIGR','Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',
        290,250,{'1':'FLASH_CS','2':'FLASH_DO','3':'FLASH_WP','4':'GND',
                 '5':'FLASH_DI','6':'CONFIG_CLK','7':'FLASH_HOLD','8':'+3V3_FPGA'})
    resistor_defs=[('R501','10k / 1%','EXTR','GND',220,245),
                  ('R502','1k / 1%','MODE0','GND',445,140),
                  ('R503','1k / 1%','MODE1','GND',465,140),
                  ('R504','1k / 1%','CONFIG_CLK','GND',325,280),
                  ('R505','4.7k / 1%','+3V3_FPGA','FLASH_CS',275,280),
                  ('R506','4.7k / 1%','+3V3_FPGA','FLASH_WP',295,280),
                  ('R507','4.7k / 1%','+3V3_FPGA','FLASH_HOLD',315,315),
                  ('R508','4.7k / 1%','+3V3_FPGA','RECONFIG_N',395,280),
                  ('R509','4.7k / 1%','JTAG_TCK','GND',365,280),
                  ('R510','10k / 1%','+3V3_FPGA','JTAG_TMS',345,315),
                  ('R511','10k / 1%','+3V3_FPGA','JTAG_TDI',365,315),
                  ('R512','33ohm / 1%','XO_CLK','FPGA_CLK',415,235),
                  ('R513','33ohm / 1%','MCLK_FPGA','AUDIO_MCLK',440,210),
                  ('R514','33ohm / 1%','BCLK_FPGA','AUDIO_BCLK',465,210),
                  ('R515','33ohm / 1%','LRCLK_FPGA','AUDIO_LRCLK',490,210),
                  ('R516','33ohm / 1%','DAC_FPGA','DAC_DIN',515,210),
                  ('R517','10k / 1%','ENABLE_FPGA','GND',485,270),
                  ('R518','100k / 1%','ADC_DOUT','GND',435,340),
                  ('R519','33ohm / 1%','ADC_BUF_RAW','ADC_BUF',485,340)]
    for ref,val,a,b,x,y in resistor_defs:add(ref,'Device:R',val,res,x,y,{'1':a,'2':b})
    add('C523','Device:C','100nF / 16V X7R',cap,290,315,{'1':'+3V3_FPGA','2':'GND'})
    # Generic pin-compatible oscillator footprint, pending exact procurement
    # tolerance/land-pattern review. Not a passive two-pin crystal.
    add('Y501','Oscillator:ASE-xxxMHz','24.576MHz / 3.3V CMOS XO / MPN pending',
        'Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm',385,235,
        {'1':'+3V3_FPGA','2':'GND','3':'XO_CLK','4':'+3V3_FPGA'})
    add('C524','Device:C','100nF / 16V X7R',cap,385,275,{'1':'+3V3_FPGA','2':'GND'})
    # Gowin 10-pin service assignment, not ARM SWD. Pin6 is target VREF.
    add('J501','Connector_Generic:Conn_02x05_Odd_Even','GOWIN JTAG / target VREF only',
        'Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical',350,250,
        {'1':'JTAG_TCK','2':'GND','3':'JTAG_TDI','4':None,'5':'JTAG_TDO',
         '6':'+3V3_FPGA','7':None,'8':None,'9':'JTAG_TMS','10':'GND'})
    add('SW501','Switch:SW_Push','RECONFIG / MPN pending',
        'Button_Switch_SMD:SW_SPST_TL3342',405,315,{'1':'RECONFIG_N','2':'GND'})
    add('C525','Device:C','100nF / 16V X7R / JTAG VREF',cap,385,340,{'1':'+3V3_FPGA','2':'GND'})
    # ADC DVDD stays on main 3.3 V; isolate its output from switched FPGA bank5.
    add('U503','74xGxx:74LVC1G125','SN74LVC1G125DCKR','Package_TO_SOT_SMD:SOT-353_SC-70-5',
        455,315,{'1':'GND','2':'ADC_DOUT','3':'GND','4':'ADC_BUF_RAW','5':'+3V3_FPGA'})
    add('C526','Device:C','100nF / 16V X7R',cap,465,360,{'1':'+3V3_FPGA','2':'GND'})
    # Buffer input has no positive rail clamp; hold-powered output drives mute
    # MR actively high while FPGA is alive, with default-low input otherwise.
    add('U504','74xGxx:74LVC1G17','SN74LVC1G17DCKR','Package_TO_SOT_SMD:SOT-353_SC-70-5',
        495,250,{'1':None,'2':'ENABLE_FPGA','3':'GND','4':'AUDIO_ENABLE','5':'+3V3_A'})
    add('C527','Device:C','100nF / 16V X7R',cap,515,270,{'1':'+3V3_A','2':'GND'})
    loader=DynamicSymbolLoader(folder)
    for ref,lib,val,foot,x,y,angle,nets,unit in parts:
        family,name=lib.split(':'); loader.inject_symbol_into_schematic(path,family,name)
        assert loader.create_component_instance(path,family,name,ref,val,foot,x*GRID,y*GRID,unit=unit,angle=angle),ref
    tree=sx.loads(path.read_text()); symbols={e[1]:e for e in child(tree,'lib_symbols')[1:]}
    boundary={'+1V0_FPGA':'input','+3V3_FPGA':'input','+3V3_A':'input','GND':'bidirectional',
              'AUDIO_MCLK':'output','AUDIO_BCLK':'output','AUDIO_LRCLK':'output',
              'DAC_DIN':'output','AUDIO_ENABLE':'output','ADC_DOUT':'input',
              'MCU_SPI_MOSI':'input','MCU_SPI_CS':'input','MCU_SPI_CLK':'input','MCU_SPI_MISO':'output'}
    exposed=set()
    by_instance={(p[0],p[8]):p for p in parts}
    def definition(lib):
        sym=symbols[lib]
        ext=next((e[1] for e in sym if isinstance(e,list) and e and e[0]==S('extends')),None)
        return definition(lib.split(':')[0]+':'+ext) if ext else sym
    for inst in tree:
        if not isinstance(inst,list) or not inst or inst[0]!=S('symbol'):continue
        ref=next(e[2] for e in inst if isinstance(e,list) and e and e[0]==S('property') and e[1]=='Reference')
        unit=child(inst,'unit')[1]; _,lib,val,foot,x,y,angle,nets,_=by_instance[ref,unit]
        child(inst,'uuid')[1]=uid(ref+'/'+str(unit))
        coords={};rad=math.radians(angle)
        for section in definition(lib):
            if not isinstance(section,list) or not section or section[0]!=S('symbol'):continue
            if int(str(section[1]).rsplit('_',2)[1]) not in (0,unit):continue
            for pin in section:
                if not isinstance(pin,list) or not pin or pin[0]!=S('pin'):continue
                n=str(child(pin,'number')[1]);px,py,a=child(pin,'at')[1:]
                coords[n]=(round(x*GRID+px*math.cos(rad)-py*math.sin(rad),2),
                           round(y*GRID-px*math.sin(rad)-py*math.cos(rad),2),(a+angle)%360)
        assert set(coords)==set(nets),(ref,unit,coords,nets)
        for n,net in nets.items():
            px,py,a=coords[n];tag=ref+'/'+str(unit)+'/'+n
            if net is None:
                tree.append(node(f'(no_connect (at {px} {py}) (uuid "{uid(tag+"nc")}"))'));continue
            vx,vy={0:(-5.08,0),90:(0,5.08),180:(5.08,0),270:(0,-5.08)}[a]
            ex,ey=round(px+vx,2),round(py+vy,2)
            tree.append(node(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid "{uid(tag+"wire")}"))'))
            is_boundary=net in boundary and net not in exposed
            if is_boundary:exposed.add(net)
            kind='hierarchical_label' if is_boundary else 'label'; shape=f'(shape {boundary[net]})' if is_boundary else ''
            tree.append(node(f'({kind} "{net}" {shape} (at {ex} {ey} {90 if vy else 0}) '
                             f'(effects (font (size 0.8 0.8)) (justify {"right" if vx<0 else "left"} bottom)) (uuid "{uid(tag+"label")}"))'))
        for e in inst:
            if not isinstance(e,list) or not e:continue
            if e[0]==S('pin'):child(e,'uuid')[1]=uid(ref+'pin'+str(e[1]))
            if e[0]==S('property') and e[1] in ('Reference','Value'):
                is_ref=e[1]=='Reference'
                if not is_ref and ref.startswith(('R','C','L')):e[2]=val.split(' / ')[0]
                if ref=='U501':
                    top=max(py for px,py,a in coords.values())-len(coords)*2.54
                    xx,yy=x*GRID-24.13,top-(4 if is_ref else 2)
                    if not is_ref:e[2]=part
                elif ref.startswith(('U','J','Y')):
                    xx,yy=x*GRID-(28 if ref.startswith('Y') else 20),(y-(15 if is_ref else 13))*GRID
                else:xx,yy=(x+3)*GRID,(y+(-1 if is_ref else 1))*GRID
                child(e,'at')[1:]=[round(xx,2),round(yy,2),angle]
                child(e,'effects')[1:]=node('(effects (font (size 0.8 0.8)) (justify left))')[1:]
        if ref.startswith(('R','C','L')):
            inst.append(node(f'(property "Rating" "{val}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
        if ref=='U502':
            next(e for e in inst if isinstance(e,list) and e[:2]==[S('property'),'Datasheet'])[2]='https://www.mouser.com/datasheet/2/870/gd25q32e_v1.1_20200415-1825518.pdf'
    notes=[(20,15,'BARE GW2AR-18 SDRAM QN88 - ENGINEERING DRAFT - NO DEV BOARD'),
           (20,23,'U501: primary UG115-1.7.2E pinout; all VCCX and IO banks use switched +3V3_FPGA. Ground EP89.'),
           (20,285,'PER-PIN BYPASS: place each C501-C514 adjacent to the U501 supply pin named in its Rating field.'),
           (20,292,'PLL beads: 220ohm@100MHz, DCR <=0.1ohm; exact MPN/load/ripple review required. Core supply directly from regulator.'),
           (20,370,'MODE0/1 1k low + internal MODE2 low = MSPI 000. FASTRD_N57 floats for normal read <30MHz; set bitstream config clock accordingly.'),
           (20,378,'J501: 1TCK 2GND 3TDI 4NC 5TDO 6TARGET VREF 7NC 8NC 9TMS 10GND; powered target only. Reserve JTAG in bitstream.'),
           (20,386,'24.576MHz oscillator candidate needs exact MPN/lands/supply review; requires PLL/RTL migration for 48kHz. Current bitstream is not compatible.'),
           (20,394,'U503 isolates ADC output at VCC=0; U504 held-supply Schmitt buffer defaults AUDIO_ENABLE low. Intermediate-rail/backfeed/timing review pending.'),
           (20,402,'MCU SPI boundaries have no buffers yet; complete MCU-domain isolation/boot-state review before layout. No READY/DONE/JTAGSEL_N pins bonded.')]
    for x,y,text in notes:tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1.0 1.0)) (justify left)) (uuid "{uid(text)}"))'))
    path.write_text(dumps(tree)+'\n');print(path)


if __name__=='__main__':build()
