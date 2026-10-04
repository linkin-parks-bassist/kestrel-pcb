#!/usr/bin/env python3
"""Generate bare ESP32-P4 v3 support; engineering draft, no hardware validation.

Run after build_audio.py and build_mcu_library.py, before build_project.py.
"""
import json
import math
import sys
import uuid
from pathlib import Path
from display_pins import GPIO_SIGNALS, MCU_PORTS
from mcu_bypass import CAP_FOOTPRINT, RES_FOOTPRINT, annotate

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27
sys.path.insert(0, str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps

S = sx.Symbol
def node(text): return sx.loads(text)
def child(e, key): return next(x for x in e if isinstance(x,list) and x and x[0]==S(key))
def uid(text): return str(uuid.uuid5(uuid.NAMESPACE_URL, 'kestrel/rev-b/mcu/'+text))


def build():
    folder = ROOT/'electrical'
    path = folder/'kestrel-revb-mcu.kicad_sch'
    path.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") (uuid "{uid("sheet")}") (paper "A2") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    data=json.loads((ROOT/'tools/data/esp32_p4_qfn104_v3.json').read_text())
    part=data['part']
    mcu_nets={str(p['number']):None for p in data['pins']}
    supply={9:'+3V3_D',21:'+3V3_D',62:'+3V3_D',85:'+3V3_D',96:'+3V3_D',101:'+3V3_D',102:'+3V3_D',75:'+3V3_D',77:'+3V3_D',
            26:'ESP_VDD_HP',54:'ESP_VDD_HP',76:'ESP_VDD_HP',91:'ESP_VDD_HP',30:'MCU_FLASH_VDD',71:'MCU_FLASH_VDD',
            59:'MCU_PSRAM_VDD',67:'MCU_PSRAM_VDD',72:'MCU_PSRAM_VDD',73:'MCU_LDO3',74:'MCU_LDO4',105:'GND'}
    assigned={8:'MCU_BL_PWM',7:'MCU_SPI_ENABLE',4:'MCU_RAW_CS',5:'MCU_RAW_CLK',6:'MCU_RAW_MOSI',15:'MCU_RAW_MISO',
              22:'MCU_FOOT0_N',23:'MCU_FOOT1_N',
              27:'MCU_FLASH_CS0',28:'MCU_FLASH_Q0',29:'MCU_FLASH_WP0',31:'MCU_FLASH_HD0',32:'MCU_FLASH_CK0',33:'MCU_FLASH_D0',
              78:'MCU_FB_DCDC',79:'MCU_EN_DCDC',99:'MCU_XTAL_N',100:'MCU_XTAL_P',103:'MCU_RESET_N',
              65:'MCU_JTAG_SEL',66:'MCU_BOOT35',68:'MCU_BOOT36',69:'MCU_UART_TX',70:'MCU_UART_RX',52:'MCU_USB_DM',53:'MCU_USB_DP'}
    for gpio,signal in GPIO_SIGNALS.items():
        pin=next(p['number'] for p in data['pins'] if p['name']==f'GPIO{gpio}')
        assert pin not in assigned and pin not in supply, (gpio,pin)
        assigned[pin]='MCU_'+signal
    for n,net in {**supply,**assigned}.items():mcu_nets[str(n)]=net
    cap='Capacitor_SMD:C_0603_1608Metric';res='Resistor_SMD:R_0603_1608Metric';bulk='Capacitor_SMD:C_0805_2012Metric'
    parts=[]
    def add(ref,lib,value,foot,x,y,nets,angle=0,unit=1):
        parts.append((ref,lib,value,foot,round(x/GRID),round(y/GRID),angle,nets,unit))
    gpio=[p for p in data['pins'] if p['name'].startswith('GPIO')]
    groups=[[p for p in data['pins'] if p not in gpio]]+[gpio[i:i+16] for i in range(0,len(gpio),16)]
    for unit,(x,y) in enumerate([(70,100),(180,65),(280,65),(380,65),(480,65)],1):
        add('U701','KestrelMCU:ESP32-P4NRW16X',part,'KestrelMCU:ESP32_P4_QFN104_10x10_P0.35_EP7.5',x,y,{str(p['number']):mcu_nets[str(p['number'])] for p in groups[unit-1]},unit=unit)
    # Physical bypass per required input; each Rating names its placement pin.
    for i,n in enumerate([9,21,62,85,96,101,102,75,77,26,54,76,91,30,59,67]):
        add(f'C{701+i}','Device:C',f'100nF / 16V X7R +/-10% / at U701 pin {n}',CAP_FOOTPRINT,35+(i%8)*55,200+(i//8)*25,{'1':mcu_nets[str(n)],'2':'GND'})
    caps=[('C717','10uF / 16V X7R','+3V3_D'),('C718','10uF / 16V X7R / near VDD_BAT102','+3V3_D'),
          ('C719','10uF / 16V X7R / near VDD_LDO75','+3V3_D'),('C720','10uF / 16V X7R / near VDD_DCDCC77','+3V3_D'),
          ('C721','10uF / 16V X7R / local HP bulk','ESP_VDD_HP'),('C722','1uF / 16V X7R / at FLASHIO30','MCU_FLASH_VDD'),
          ('C723','1uF / 16V X7R / at PSRAM59','MCU_PSRAM_VDD'),('C724','1uF / 16V X7R / at PSRAM67','MCU_PSRAM_VDD'),
          ('C725','1uF / 16V X7R / at VDDO_FLASH71','MCU_FLASH_VDD'),('C726','1uF / 16V X7R / at VDDO_PSRAM72','MCU_PSRAM_VDD'),
          ('C727','1uF / 16V X7R / at VDDO3_73','MCU_LDO3'),('C728','1uF / 16V X7R / at VDDO4_74','MCU_LDO4')]
    for i,(ref,value,net) in enumerate(caps):add(ref,'Device:C',value,bulk,35+(i%6)*65,250+(i//6)*25,{'1':net,'2':'GND'})
    add('U702','Memory_Flash:W25Q32JVSS','GD25Q32ESIGR','Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',180,320,
        {'1':'MCU_FLASH_CS','2':'MCU_FLASH_Q','3':'MCU_FLASH_WP','4':'GND','5':'MCU_FLASH_D','6':'MCU_FLASH_CK','7':'MCU_FLASH_HD','8':'MCU_FLASH_VDD'})
    for i,name in enumerate(('CS','Q','WP','HD','CK','D')):
        add(f'R{701+i}','Device:R','0ohm / flash tuning footprint',res,40+i*50,300,{'1':f'MCU_FLASH_{name}0','2':f'MCU_FLASH_{name}'},angle=90)
    add('R707','Device:R','10k / 1% / flash CS pullup',res,245,310,{'1':'MCU_FLASH_VDD','2':'MCU_FLASH_CS'})
    add('C729','Device:C','100nF / 16V X7R / at flash VCC',cap,245,340,{'1':'MCU_FLASH_VDD','2':'GND'})
    add('Y701','Device:Crystal_GND24','40MHz / +/-10ppm / MPN and CL pending','Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm',70,340,
        {'1':'MCU_XTAL_P0','2':'GND','3':'MCU_XTAL_N0','4':'GND'})
    for ref,net,x in [('R708','P',35),('R709','N',110)]:add(ref,'Device:R','0ohm / crystal tuning',RES_FOOTPRINT,x,330,{'1':f'MCU_XTAL_{net}','2':f'MCU_XTAL_{net}0'},angle=90)
    for ref,net,x in [('C730','P',35),('C731','N',110)]:add(ref,'Device:C','TBD / crystal CL and stray / C0G',cap,x,355,{'1':f'MCU_XTAL_{net}0','2':'GND'})
    resistors=[('R710','10k / 1%','+3V3_D','MCU_RESET_N',315,310),('R711','10k / 1%','+3V3_D','MCU_BOOT35',350,310),
               ('R712','10k / 1%','+3V3_D','MCU_BOOT36',385,310),('R713','10k / 1%','+3V3_D','MCU_JTAG_SEL',420,310)]
    for ref,val,a,b,x,y in resistors:add(ref,'Device:R',val,res,x,y,{'1':a,'2':b})
    add('C732','Device:C','1uF / 16V X7R / reset RC starting point',cap,315,340,{'1':'MCU_RESET_N','2':'GND'})
    add('SW701','Switch:SW_Push','RESET / SMD button MPN pending','Button_Switch_SMD:SW_SPST_TL3342',300,355,{'1':'MCU_RESET_N','2':'GND'})
    add('SW702','Switch:SW_Push','BOOT / SMD button MPN pending','Button_Switch_SMD:SW_SPST_TL3342',355,350,{'1':'MCU_BOOT35','2':'GND'})
    add('J701','Connector_Generic:Conn_01x06','UART / POWERED TARGET ONLY','Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical',470,320,
        {'1':'GND','2':'+3V3_D','3':'MCU_UART_TX','4':'MCU_UART_RX','5':'MCU_RESET_N','6':'MCU_BOOT35'})
    # USB Serial/JTAG service pads; connector/protection/backfeed work remains.
    for ref,net,y in [('TP701','MCU_USB_DM',355),('TP702','MCU_USB_DP',370)]:add(ref,'Connector:TestPoint',net,'TestPoint:TestPoint_Pad_D1.0mm',460,y,{'1':net})
    loader=DynamicSymbolLoader(folder)
    for ref,lib,val,foot,x,y,angle,nets,unit in parts:
        family,name=lib.split(':'); loader.inject_symbol_into_schematic(path,family,name)
        assert loader.create_component_instance(path,family,name,ref,val,foot,x*GRID,y*GRID,unit=unit,angle=angle),ref
    tree=sx.loads(path.read_text()); symbols={e[1]:e for e in child(tree,'lib_symbols')[1:]}
    boundary={'+3V3_D':'input','GND':'bidirectional','ESP_VDD_HP':'input','MCU_EN_DCDC':'output','MCU_FB_DCDC':'bidirectional',
              'MCU_BL_PWM':'output','MCU_SPI_ENABLE':'output','MCU_RESET_N':'output','MCU_RAW_CS':'output','MCU_RAW_CLK':'output','MCU_RAW_MOSI':'output','MCU_RAW_MISO':'input'}
    boundary.update(dict(MCU_PORTS))
    boundary.update({'MCU_FOOT0_N':'input','MCU_FOOT1_N':'input'})
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
            tree.append(node(f'({kind} "{net}" {shape} (at {ex} {ey} 0) '
                             f'(effects (font (size 0.8 0.8)) (justify {"right" if vx<0 else "left"} bottom)) (uuid "{uid(tag+"label")}"))'))
        for e in inst:
            if not isinstance(e,list) or not e:continue
            if e[0]==S('pin'):child(e,'uuid')[1]=uid(ref+'pin'+str(e[1]))
            if e[0]==S('property') and e[1] in ('Reference','Value'):
                is_ref=e[1]=='Reference'
                if not is_ref and ref.startswith(('R','C','L')):e[2]=val.split(' / ')[0]
                if ref=='U701':
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
        if ref=='U702':
            next(e for e in inst if isinstance(e,list) and e[:2]==[S('property'),'Datasheet'])[2]='https://www.mouser.com/datasheet/2/870/gd25q32e_v1.1_20200415-1825518.pdf'
    notes=[(20,15,'BARE ESP32-P4NRW16X V3 - ENGINEERING DRAFT - NO DEV BOARD'),
           (20,180,'MIPI, HS USB and unused GPIOs are NC. GPIO24/25 USB Serial/JTAG service pads only; USB connector/protection pending.'),
           (20,380,'J701: 1GND 2TARGET3V3 3MCU_TX 4MCU_RX 5RESET 6BOOT35. Powered target only; no programmer-powered rail.'),
           (20,387,'BOOT35=1 SPI boot; hold BOOT35 low with BOOT36 high during reset for UART download. Keep straps stable >=3ms after reset.'),
           (20,394,'Flash 4MB requires matching firmware partitions/driver validation. PSRAM LDO requires software configuration; unused LDO3/4 remain unloaded.'),
           (20,401,'Crystal +/-10ppm, load capacitors, reset timing, GPIO allocation, SPI timing/sequencing, USB backfeed and source budget remain to qualify.')]
    for x,y,text in notes:tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(text)}"))'))
    annotate(tree)
    path.write_text(dumps(tree)+'\n');print(path)
if __name__=='__main__':build()
