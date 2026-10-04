#!/usr/bin/env python3
"""Generate onboard backlight boost and LCD logic supply. Run before project."""
import math
import sys
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GRID=1.27
sys.path.insert(0,str(Path.home()/'.local/share/kicad-mcp/python'))
import sexpdata as sx
from commands.dynamic_symbol_loader import DynamicSymbolLoader
from utils.sexpr_format import dumps
S=sx.Symbol
def node(text):return sx.loads(text)
def child(e,key):return next(x for x in e if isinstance(x,list) and x and x[0]==S(key))
def uid(text):return str(uuid.uuid5(uuid.NAMESPACE_URL,'kestrel/rev-b/backlight/'+text))

def library(folder):
    name='TPS61169DCK'
    effect='(effects (font (size 0.8 0.8)))'
    sym=node(f'(symbol "{name}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) '
        f'(property "Reference" "U" (at 0 0 0) {effect}) (property "Value" "{name}" (at 0 0 0) {effect}) '
        f'(property "Footprint" "Package_TO_SOT_SMD:Texas_R-PDSO-G5_DCK-5" (at 0 0 0) {effect}) '
        f'(property "Datasheet" "https://www.ti.com/lit/ds/symlink/tps61169.pdf" (at 0 0 0) {effect}))')
    body=node(f'(symbol "{name}_1_1" (rectangle (start -8.89 8.89) (end 8.89 -8.89) (stroke (width 0.254) (type default)) (fill (type background))))')
    for n,name,kind in ((1,'SW','passive'),(2,'GND','power_in'),(3,'FB','input'),(4,'CTRL','input'),(5,'VIN','power_in')):
        body.append(node(f'(pin {kind} line (at -11.43 {round(8.89-n*2.54,2)} 0) (length 2.54) (name "{name}" {effect}) (number "{n}" {effect}))'))
    sym.append(body);library=node('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor"))');library.append(sym)
    (folder/'KestrelDisplay.kicad_sym').write_text(dumps(library)+'\n')
    table=sx.loads((folder/'sym-lib-table').read_text())
    table[:]=[e for e in table if not (isinstance(e,list) and any(isinstance(p,list) and p[:2]==[S('name'),'KestrelDisplay'] for p in e))]
    table.append(node('(lib (name "KestrelDisplay") (type "KiCad") (uri "${KIPRJMOD}/KestrelDisplay.kicad_sym") (options "") (descr "Backlight primary DCK5 pin table"))'))
    (folder/'sym-lib-table').write_text(dumps(table)+'\n')

def build():
    folder=ROOT/'electrical';library(folder)
    path=folder/'kestrel-revb-backlight.kicad_sch'
    path.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") (uuid "{uid("sheet")}") (paper "A2") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    res='Resistor_SMD:R_0603_1608Metric';cap='Capacitor_SMD:C_0603_1608Metric'
    parts=[]
    def add(ref,lib,value,foot,x,y,nets,angle=0,unit=1):
        parts.append((ref,lib,value,foot,round(x/GRID),round(y/GRID),angle,nets,unit))
    add('U901','KestrelDisplay:TPS61169DCK','TPS61169DCKR','Package_TO_SOT_SMD:Texas_R-PDSO-G5_DCK-5',80,65,
        {'1':'BL_SW','2':'GND','3':'BL_LED_K','4':'BL_CTRL','5':'+5V_DIG'})
    add('L901','Device:L','10uH / shielded / Isat >=3A / MPN and lands pending','Inductor_SMD:L_Sunlord_MWSA0603S',170,55,{'1':'+5V_DIG','2':'BL_SW'},angle=90)
    add('D901','Diode:SS16','SS16-E3/61T','Diode_SMD:D_SMA',265,55,{'1':'BL_LED_A','2':'BL_SW'},angle=180)
    add('U902','74xGxx:SN74LVC1G125DCK','SN74LVC1G125DCKR','Package_TO_SOT_SMD:Texas_R-PDSO-G5_DCK-5',320,110,
        {'1':'GND','2':'MCU_BL_PWM','3':'GND','4':'BL_CTRL_BUFFER','5':'+5V_DIG'})
    add('R901','Device:R','5.62ohm / 1% / >=0.125W / Kelvin sense','Resistor_SMD:R_0805_2012Metric',70,125,{'1':'BL_LED_K','2':'GND'})
    add('R902','Device:R','10k / 1% / MCU PWM default off',res,170,125,{'1':'MCU_BL_PWM','2':'GND'})
    add('R903','Device:R','1k / 1% / control series',res,265,165,{'1':'BL_CTRL_BUFFER','2':'BL_CTRL'},angle=90)
    add('R904','Device:R','1M / 1% / 1206 / output bleed','Resistor_SMD:R_1206_3216Metric',170,180,{'1':'BL_LED_A','2':'GND'})
    add('R905','Device:R','100k / 1% / CTRL default off',res,70,180,{'1':'BL_CTRL','2':'GND'})
    add('C901','Device:C','4.7uF / 25V X7R / input local','Capacitor_SMD:C_0805_2012Metric',70,230,{'1':'+5V_DIG','2':'GND'})
    add('C902','Device:C','100nF / 16V X7R / VIN bypass',cap,150,230,{'1':'+5V_DIG','2':'GND'})
    add('C903','Device:C','2.2uF / 50V X7R / effective >=1uF at 39V','Capacitor_SMD:C_1210_3225Metric',240,230,{'1':'BL_LED_A','2':'GND'})
    add('C904','Device:C','100nF / 16V X7R / buffer bypass',cap,330,230,{'1':'+5V_DIG','2':'GND'})
    for ref,net,x in [('TP901','BL_LED_A',265),('TP902','BL_LED_K',330)]:
        add(ref,'Connector:TestPoint',net,'TestPoint:TestPoint_Pad_D1.0mm',x,180,{'1':net})
    add('U903','Regulator_Linear:TLV76701DRVx','TLV76701DRVR',
        'Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm_ThermalVias',465,65,
        {'1':'LCD_VDD','2':'LCD_FB','3':'GND','4':'+5V_DIG','5':'GND','6':'+5V_DIG','7':'GND'})
    add('R906','Device:R','33.2k / 0.1% / LCD upper feedback',res,435,230,{'1':'LCD_VDD','2':'LCD_FB'})
    add('R907','Device:R','10k / 0.1% / LCD lower feedback',res,515,230,{'1':'LCD_FB','2':'GND'})
    add('C905','Device:C','4.7uF / 16V X7R / effective >=1uF / LCD input','Capacitor_SMD:C_0805_2012Metric',435,170,{'1':'+5V_DIG','2':'GND'})
    add('C906','Device:C','4.7uF / 16V X7R / effective >=1uF / LCD output','Capacitor_SMD:C_0805_2012Metric',515,170,{'1':'LCD_VDD','2':'GND'})
    add('C907','Device:C','10pF / 25V C0G / LCD feedforward',cap,475,280,{'1':'LCD_VDD','2':'LCD_FB'},angle=90)
    add('TP903','Connector:TestPoint','LCD_VDD','TestPoint:TestPoint_Pad_D1.0mm',515,120,{'1':'LCD_VDD'})
    add('U904','Regulator_Linear:TLV76701DRVx','TLV76701DRVR',
        'Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm_ThermalVias',465,355,
        {'1':'TOUCH_VDD','2':'TOUCH_FB','3':'GND','4':'+5V_DIG','5':'GND','6':'+5V_DIG','7':'GND'})
    add('R908','Device:R','30k / 0.1% / touch upper feedback',res,350,355,{'1':'TOUCH_VDD','2':'TOUCH_FB'})
    add('R909','Device:R','10k / 0.1% / touch lower feedback',res,390,355,{'1':'TOUCH_FB','2':'GND'})
    add('C908','Device:C','4.7uF / 16V X7R / effective >=1uF / touch input','Capacitor_SMD:C_0805_2012Metric',35,355,{'1':'+5V_DIG','2':'GND'})
    add('C909','Device:C','4.7uF / 16V X7R / effective >=1uF / touch output','Capacitor_SMD:C_0805_2012Metric',125,355,{'1':'TOUCH_VDD','2':'GND'})
    add('C910','Device:C','10pF / 25V C0G / touch feedforward',cap,225,355,{'1':'TOUCH_VDD','2':'TOUCH_FB'},angle=90)
    add('TP904','Connector:TestPoint','TOUCH_VDD','TestPoint:TestPoint_Pad_D1.0mm',540,355,{'1':'TOUCH_VDD'})
    loader=DynamicSymbolLoader(folder)
    for ref,lib,val,foot,x,y,angle,nets,unit in parts:
        family,name=lib.split(':'); loader.inject_symbol_into_schematic(path,family,name)
        assert loader.create_component_instance(path,family,name,ref,val,foot,x*GRID,y*GRID,unit=unit,angle=angle),ref
    tree=sx.loads(path.read_text()); symbols={e[1]:e for e in child(tree,'lib_symbols')[1:]}
    boundary={'+5V_DIG':'input','GND':'bidirectional','MCU_BL_PWM':'input','LCD_VDD':'output',
              'TOUCH_VDD':'output','BL_LED_A':'output','BL_LED_K':'bidirectional'}
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
            if ref in ('U903','U904') and n=='5':
                continue  # Hidden ground pin coincides with pin 3.
            if net is None:
                tree.append(node(f'(no_connect (at {px} {py}) (uuid "{uid(tag+"nc")}"))'));continue
            vx,vy={0:(-5.08,0),90:(0,5.08),180:(5.08,0),270:(0,-5.08)}[a]
            ex,ey=round(px+vx,2),round(py+vy,2)
            tree.append(node(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid "{uid(tag+"wire")}"))'))
            if ref in ('U903','U904') and n=='7':
                gx,gy,_=coords['3'];gy=round(gy+5.08,2)
                tree.append(node(f'(wire (pts (xy {ex} {ey}) (xy {gx} {gy})) (stroke (width 0) (type default)) (uuid "{uid(tag+"groundbar")}"))'))
                continue
            is_boundary=net in boundary and net not in exposed
            if is_boundary:exposed.add(net)
            kind='hierarchical_label' if is_boundary else 'label'; shape=f'(shape {boundary[net]})' if is_boundary else ''
            tree.append(node(f'({kind} "{net}" {shape} (at {ex} {ey} 0) '
                             f'(effects (font (size 0.8 0.8)) (justify {"right" if vx<0 or (ref=="U902" and n=="5") else "left"} bottom)) (uuid "{uid(tag+"label")}"))'))
        for e in inst:
            if not isinstance(e,list) or not e:continue
            if e[0]==S('pin'):child(e,'uuid')[1]=uid(ref+'pin'+str(e[1]))
            if e[0]==S('property') and e[1] in ('Reference','Value'):
                is_ref=e[1]=='Reference'
                if not is_ref and ref.startswith(('R','C','L')):e[2]=val.split(' / ')[0]
                if ref.startswith('U'):
                    xx,yy=x*GRID-13,(y-14+(0 if is_ref else 2))*GRID
                else:xx,yy=(x+3)*GRID,(y+(-1 if is_ref else 1))*GRID
                if ref=='U902':xx,yy=x*GRID-13,80+(0 if is_ref else 2)
                if ref=='D901':xx,yy=x*GRID-3,y*GRID-(8 if is_ref else 6)
                if angle==90:xx,yy=x*GRID-3,y*GRID-(8 if is_ref else 6)
                child(e,'at')[1:]=[round(xx,2),round(yy,2),90 if angle==90 else 0]
                child(e,'effects')[1:]=node('(effects (font (size 0.8 0.8)) (justify left))')[1:]
        if ref.startswith(('R','C','L')):
            inst.append(node(f'(property "Rating" "{val}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
    notes=[(20,15,'ONBOARD BACKLIGHT BOOST - REFERENCE PANEL - ENGINEERING DRAFT'),
           (20,255,'GPIO8 PWM defaults low. Use 5-100kHz; buffered on 5V domain with Ioff; controlled by firmware.'),
           (20,262,'5.62ohm sets 36.30mA nominal / <=39.55mA conditional TA>=25C limits. Cold-temperature regulation remains to qualify.'),
           (20,269,'J1001: pin2 anode / pin1 cathode. Never ground LED cathode; Kelvin route to FB and R901.'),
           (20,276,'Disabled boost retains VIN-to-output passive path. Panel Vf must exceed VIN; no hard output disconnect or hot-plug claim.'),
           (20,248,'LCD and touch supplies onboard. Panel contact orientation, exact parts/effective capacitance and qualification pending.'),
           (20,310,'LCD LOGIC: TLV76701 / 33.2k:10k 0.1% / 3.456V nominal. Conditional DC corners 3.414..3.498V; not touch VDD.'),
           (20,317,'Panel VDD 3.3..3.6V. 5V source headroom, load/thermal, effective capacitors, bus levels and ramp/backfeed require qualification.'),
           (20,324,'TI adjustable DRV pins: 1 OUT, 2 FB, 3/5/EP GND, 4 EN, 6 IN. TP903 probes LCD power; J1001 is the LCD connector.'),
           (20,385,'TOUCH: 30k:10k 0.1% / 3.2V nominal. GT911 recommended supply max3.3V, absolute max3.47V. Do not use LCD_VDD.'),
           (20,392,'Touch load, exact capacitors, reset/address timing, rail-ramp/backfeed and GPIO/I2C behavior require qualification.')]
    for x,y,text in notes:tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(text)}"))'))
    path.write_text(dumps(tree)+'\n');print(path)
if __name__=='__main__':build()
