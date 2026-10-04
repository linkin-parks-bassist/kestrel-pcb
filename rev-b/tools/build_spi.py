#!/usr/bin/env python3
"""Generate supervised, default-off SPI bridge. Run after MCU, before project."""
import math
import sys
import uuid
from spi_bypass import CAP_FOOTPRINT, annotate
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
def uid(text):return str(uuid.uuid5(uuid.NAMESPACE_URL,'kestrel/rev-b/spi/'+text))

def library(folder):
    name='SN74AXC4T774PW'
    effects='(effects (font (size 0.8 0.8)))'
    sym=node(f'(symbol "{name}" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) '
             f'(property "Reference" "U" (at 0 0 0) {effects}) '
             f'(property "Value" "{name}" (at 0 0 0) {effects}) '
             f'(property "Footprint" "Package_SO:TSSOP-16_4.4x5mm_P0.65mm" (at 0 0 0) {effects}) '
             f'(property "Datasheet" "https://www.ti.com/lit/ds/symlink/sn74axc4t774.pdf" (at 0 0 0) {effects}))')
    section=node(f'(symbol "{name}_1_1" (rectangle (start -12.7 21.59) (end 12.7 -21.59) (stroke (width 0.254) (type default)) (fill (type background))))')
    # TI Rev C Table 4-1, PW16 only. All pins displayed for explicit domain review.
    names=['DIR1','DIR2','A1_CS','A2_CLK','A3_MOSI','A4_MISO','DIR3','DIR4','OE_N','GND','B4_MISO','B3_MOSI','B2_CLK','B1_CS','VCCB','VCCA']
    for n,name in enumerate(names,1):
        kind='bidirectional' if n in (3,4,5,6,11,12,13,14) else 'power_in' if n in (10,15,16) else 'input'
        section.append(node(f'(pin {kind} line (at -15.24 {round(21.59-n*2.54,2)} 0) (length 2.54) (name "{name}" {effects}) (number "{n}" {effects}))'))
    sym.append(section)
    lib=node('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor"))');lib.append(sym)
    (folder/'KestrelSPI.kicad_sym').write_text(dumps(lib)+'\n')
    table=sx.loads((folder/'sym-lib-table').read_text())
    table[:]=[e for e in table if not (isinstance(e,list) and any(isinstance(p,list) and p[:2]==[S('name'),'KestrelSPI'] for p in e))]
    table.append(node('(lib (name "KestrelSPI") (type "KiCad") (uri "${KIPRJMOD}/KestrelSPI.kicad_sym") (options "") (descr "SPI bridge PW16 primary pin map"))'))
    (folder/'sym-lib-table').write_text(dumps(table)+'\n')

def build():
    folder=ROOT/'electrical';library(folder)
    path=folder/'kestrel-revb-spi.kicad_sch'
    path.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") (generator_version "10.0") (uuid "{uid("sheet")}") (paper "A3") (lib_symbols) (sheet_instances (path "/" (page "1"))))')
    res='Resistor_SMD:R_0603_1608Metric';cap='Capacitor_SMD:C_0603_1608Metric'
    parts=[]
    def add(ref,lib,value,foot,x,y,nets,angle=0,unit=1):
        parts.append((ref,lib,value,foot,round(x/GRID),round(y/GRID),angle,nets,unit))
    add('U801','KestrelSPI:SN74AXC4T774PW','SN74AXC4T774PWR','Package_SO:TSSOP-16_4.4x5mm_P0.65mm',80,65,
        {'1':'+3V3_D','2':'+3V3_D','3':'MCU_RAW_CS','4':'MCU_RAW_CLK','5':'MCU_RAW_MOSI','6':'SPI_MISO_A',
         '7':'+3V3_D','8':'GND','9':'SPI_OE_N','10':'GND','11':'MCU_SPI_MISO','12':'SPI_MOSI_B','13':'SPI_CLK_B','14':'SPI_CS_B','15':'+3V3_FPGA','16':'+3V3_D'})
    add('U802','KestrelAudio:TPS3808G01','TPS3808G01DBVR','Package_TO_SOT_SMD:SOT-23-6',210,65,
        {'1':'SPI_RAIL_RELEASE','2':'GND','3':'MCU_RESET_N','4':None,'5':'SPI_SENSE','6':'+3V3_D'})
    add('U803','74xGxx:SN74LVC1G00DCK','SN74LVC1G00DCKR','Package_TO_SOT_SMD:Texas_R-PDSO-G5_DCK-5',325,65,
        {'1':'MCU_SPI_ENABLE','2':'SPI_RAIL_RELEASE','3':'GND','4':'SPI_OE_N','5':'+3V3_D'})
    for i,(a,b) in enumerate((('SPI_CS_B','MCU_SPI_CS'),('SPI_CLK_B','MCU_SPI_CLK'),('SPI_MOSI_B','MCU_SPI_MOSI'),('SPI_MISO_A','MCU_RAW_MISO'))):
        add(f'R{801+i}','Device:R','33ohm / output damping / tune on PCB',res,40+i*85,115,{'1':a,'2':b},angle=90)
    rows=[('R805','4.7k / 1% / FPGA CS idle','+3V3_FPGA','MCU_SPI_CS',40,150),
          ('R806','4.7k / 1% / MCU CS idle','+3V3_D','MCU_RAW_CS',110,150),
          ('R807','10k / 1% / OE default disabled','+3V3_D','SPI_OE_N',180,150),
          ('R808','10k / 1% / firmware enable default off','MCU_SPI_ENABLE','GND',250,150),
          ('R809','10k / 1% / open drain release pullup','+3V3_D','SPI_RAIL_RELEASE',320,150),
          ('R810','63.4k / 0.1% / IO monitor high','+3V3_FPGA','SPI_SENSE',40,190),
          ('R811','10k / 0.1% / IO monitor low','SPI_SENSE','GND',110,190)]
    for ref,val,a,b,x,y in rows:add(ref,'Device:R',val,res,x,y,{'1':a,'2':b})
    for i,(net,x) in enumerate((('+3V3_D',40),('+3V3_FPGA',110),('+3V3_D',180),('+3V3_D',250))):
        add(f'C{801+i}','Device:C','100nF / 16V X7R / local bypass',CAP_FOOTPRINT if i<2 else cap,x,230,{'1':net,'2':'GND'})
    add('C805','Device:C','1nF / 25V C0G / SENSE filter',cap,180,190,{'1':'SPI_SENSE','2':'GND'})
    loader=DynamicSymbolLoader(folder)
    for ref,lib,val,foot,x,y,angle,nets,unit in parts:
        family,name=lib.split(':'); loader.inject_symbol_into_schematic(path,family,name)
        assert loader.create_component_instance(path,family,name,ref,val,foot,x*GRID,y*GRID,unit=unit,angle=angle),ref
    tree=sx.loads(path.read_text()); symbols={e[1]:e for e in child(tree,'lib_symbols')[1:]}
    boundary={'+3V3_D':'input','+3V3_FPGA':'input','GND':'bidirectional','MCU_SPI_ENABLE':'input','MCU_RESET_N':'input',
              'MCU_RAW_CS':'input','MCU_RAW_CLK':'input','MCU_RAW_MOSI':'input','MCU_RAW_MISO':'output',
              'MCU_SPI_CS':'output','MCU_SPI_CLK':'output','MCU_SPI_MOSI':'output','MCU_SPI_MISO':'input'}
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
                if ref.startswith('U'):
                    xx,yy=x*GRID-13,(y-(24 if ref=='U801' else 14)+(0 if is_ref else 2))*GRID
                else:xx,yy=(x+3)*GRID,(y+(-1 if is_ref else 1))*GRID
                child(e,'at')[1:]=[round(xx,2),round(yy,2),angle]
                child(e,'effects')[1:]=node('(effects (font (size 0.8 0.8)) (justify left))')[1:]
        if ref.startswith(('R','C','L')):
            inst.append(node(f'(property "Rating" "{val}" (at {x*GRID} {y*GRID} 0) (effects (font (size 1 1)) (hide yes)))'))
    notes=[(20,15,'SPI POWER-DOMAIN BRIDGE - ENGINEERING DRAFT'),
           (20,255,'GPIO7 enable defaults low. OE = NOT(enable AND rail release). MCU reset restarts supervisor delay.'),
           (20,262,'63.4k/10k divider: nominal falling trip 2.9727V; CT open 12-28ms release. This is an isolation guard, not FPGA-valid proof.'),
           (20,269,'Firmware must set CS high / CLK low before enabling, await FPGA configuration, and disable before controlled shutdown.'),
           (20,276,'Ioff / VCC<100mV isolation; arbitrary ramps, 10MHz timing, pullup margins and Sydney sourcing remain to qualify.')]
    for x,y,text in notes:tree.append(node(f'(text "{text}" (at {x} {y} 0) (effects (font (size 1 1)) (justify left)) (uuid "{uid(text)}"))'))
    annotate(tree)
    path.write_text(dumps(tree)+'\n');print(path)
if __name__=='__main__':build()
