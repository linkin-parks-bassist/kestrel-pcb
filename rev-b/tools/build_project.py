#!/usr/bin/env python3
"""Assemble implemented Rev-B sheets into one reviewable KiCad project.

Run after build_power.py, build_audio.py, build_fpga_power.py, build_input_power.py,
build_fpga_library.py, build_fpga.py, build_mcu_library.py, build_mcu_power.py
build_mcu.py, build_spi.py, build_backlight.py, build_display.py and build_footswitch.py in the KiCad MCP venv. Signals for
unimplemented circuitry stay visibly unconnected; this does not fake a complete
FPGA, MCU, analogue or power design.
"""
import json
import sys
import uuid
from pathlib import Path
from display_pins import MCU_PORTS, DISPLAY_PORTS

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path.home()/".local/share/kicad-mcp/python"))
import sexpdata as sx
from utils.sexpr_format import dumps


def uid(name): return str(uuid.uuid5(uuid.NAMESPACE_URL,"kestrel/rev-b/project/"+name))
def node(text): return sx.loads(text)
def child(tree,key): return next(x for x in tree if isinstance(x,list) and x and x[0]==sx.Symbol(key))


def main():
    folder=ROOT/"electrical"; path=folder/"kestrel-revb.kicad_sch"
    project="kestrel-revb"; root_id=uid("root")
    tree=node(f'(kicad_sch (version 20260101) (generator "eeschema") '
              f'(generator_version "10.0") (uuid "{root_id}") (paper "A2") '
              '(lib_symbols) (sheet_instances (path "/" (page "1"))))')
    sheet_specs=[
        ("Centre-negative 9 V input","kestrel-revb-input-power.kicad_sch",35,55,75,25,
         [("9V_PROTECTED","output"),("GND","bidirectional")]),
        ("Onboard 5 V and 3.3 V bucks","kestrel-revb-power.kicad_sch",150,50,90,35,
         [("9V_PROTECTED","input"),("+5V_DIG","output"),("+3V3_D","output"),("GND","bidirectional")]),
        ("Hardware ADC and DAC","kestrel-revb-audio.kicad_sch",150,130,90,65,
         [("AUDIO_MCLK","input"),("AUDIO_BCLK","input"),
          ("AUDIO_LRCLK","input"),("DAC_DIN","input"),("AUDIO_ENABLE","input"),
          ("ADC_DOUT","output"),("9V_PROTECTED","input"),
          ("+3V3_D","input"),("+5V_DIG","input"),("GND","bidirectional"),("+3V3_A","output")]),
        ("FPGA core and I/O sequencing","kestrel-revb-fpga-power.kicad_sch",35,100,80,40,
         [("+5V_DIG","input"),("+3V3_D","input"),("GND","bidirectional"),
          ("+1V0_FPGA","output"),("+3V3_FPGA","output")]),
        ("P4 controlled HP regulator","kestrel-revb-mcu-power.kicad_sch",35,175,80,30,
         [("+3V3_D","input"),("GND","bidirectional"),("ESP_VDD_HP","output"),
          ("MCU_EN_DCDC","input"),("MCU_FB_DCDC","bidirectional")]),
        ("Bare ESP32-P4 support","kestrel-revb-mcu.kicad_sch",450,50,90,210,
         [("+3V3_D","input"),("GND","bidirectional"),("ESP_VDD_HP","input"),
          ("MCU_EN_DCDC","output"),("MCU_FB_DCDC","bidirectional"),
          ("MCU_BL_PWM","output"),("MCU_SPI_ENABLE","output"),("MCU_RESET_N","output"),("MCU_RAW_CS","output"),("MCU_RAW_CLK","output"),("MCU_RAW_MOSI","output"),("MCU_RAW_MISO","input")]+MCU_PORTS+[("MCU_FOOT0_N","input"),("MCU_FOOT1_N","input")]),
        ("Bare GW2AR-18 support","kestrel-revb-fpga.kicad_sch",300,115,75,95,
         [("+1V0_FPGA","input"),("+3V3_FPGA","input"),("+3V3_A","input"),("GND","bidirectional"),
          ("AUDIO_MCLK","output"),("AUDIO_BCLK","output"),("AUDIO_LRCLK","output"),
          ("DAC_DIN","output"),("AUDIO_ENABLE","output"),("ADC_DOUT","input"),
          ("MCU_SPI_MOSI","input"),("MCU_SPI_CS","input"),("MCU_SPI_CLK","input"),("MCU_SPI_MISO","output")]),
        ("Power-domain SPI isolation","kestrel-revb-spi.kicad_sch",450,280,90,80,
         [("+3V3_D","input"),("+3V3_FPGA","input"),("GND","bidirectional"),
          ("MCU_SPI_ENABLE","input"),("MCU_RESET_N","input"),
          ("MCU_RAW_CS","input"),("MCU_RAW_CLK","input"),("MCU_RAW_MOSI","input"),("MCU_RAW_MISO","output"),
          ("MCU_SPI_CS","output"),("MCU_SPI_CLK","output"),("MCU_SPI_MOSI","output"),("MCU_SPI_MISO","input")]),
        ("Backlight and display supplies","kestrel-revb-backlight.kicad_sch",300,260,85,50,
         [("+5V_DIG","input"),("GND","bidirectional"),("MCU_BL_PWM","input"),
          ("LCD_VDD","output"),("TOUCH_VDD","output"),("BL_LED_A","output"),("BL_LED_K","bidirectional")]),
        ("RGB565 and capacitive touch","kestrel-revb-display.kicad_sch",150,245,110,160, DISPLAY_PORTS),
        ("Two momentary footswitch inputs","kestrel-revb-footswitch.kicad_sch",300,340,85,30,
         [("+3V3_D","input"),("GND","bidirectional"),("MCU_FOOT0_N","output"),("MCU_FOOT1_N","output")]),
    ]
    for title,filename,x,y,w,h,ports in sheet_specs:
        # Sheet bounds and pin positions use 50 mil connection grid.
        x,y,w,h=[round(round(v/1.27)*1.27,2) for v in (x,y,w,h)]
        sid=uid(filename)
        sheet=node(f'(sheet (at {x} {y}) (size {w} {h}) (stroke (width 0) (type default)) '
                   f'(fill (color 0 0 0 0)) (uuid "{sid}") '
                   f'(property "Sheetname" "{title}" (at {x} {y-2.54} 0) '
                   '(effects (font (size 1.27 1.27)) (justify left bottom))) '
                   f'(property "Sheetfile" "{filename}" (at {x} {y+h+2.54} 0) '
                   '(effects (font (size 1.27 1.27)) (justify left top))))')
        subpath=folder/filename; sub=sx.loads(subpath.read_text())
        # The power generator initially emits local port labels; promote one
        # instance of each interface to a hierarchical label without new nets.
        seen={e[1] for e in sub if isinstance(e,list) and e and e[0]==sx.Symbol("hierarchical_label")}
        for element in sub:
            if isinstance(element,list) and element and element[0]==sx.Symbol("label") and element[1] in dict(ports) and element[1] not in seen:
                name=element[1]; seen.add(name)
                if filename.endswith("power.kicad_sch"):
                    element[0]=sx.Symbol("hierarchical_label")
                    element.insert(2,node(f'(shape {dict(ports)[name]})'))
        for i,(name,kind) in enumerate(ports):
            right=kind=="output"; px=round(x+w if right else x,2); py=round(y+6.35+i*5.08,2)
            angle=0 if right else 180
            sheet.append(node(f'(pin "{name}" {kind} (at {px} {py} {angle}) '
                              '(effects (font (size 1.27 1.27))) '
                              f'(uuid "{uid(filename+name)}"))'))
            end=round(px+(15.24 if right else -15.24),2)
            tree.append(node(f'(wire (pts (xy {px} {py}) (xy {end} {py})) '
                             f'(stroke (width 0) (type default)) (uuid "{uid(filename+name+"wire")}"))'))
            justify="left bottom" if right else "right bottom"
            tree.append(node(f'(label "{name}" (at {end} {py} 0) '
                             f'(effects (font (size 1.0 1.0)) (justify {justify})) '
                             f'(uuid "{uid(filename+name+"label")}"))'))
        tree.append(sheet)
        for element in sub:
            if not isinstance(element,list) or not element or element[0]!=sx.Symbol("symbol"): continue
            ref=next(p[2] for p in element if isinstance(p,list) and p and p[0]==sx.Symbol("property") and p[1]=="Reference")
            unit=child(element,"unit")[1]
            instances=child(element,"instances")
            instances[1:]=[node(f'(project "{project}" (path "/{root_id}/{sid}" '
                               f'(reference "{ref}") (unit {unit})))')]
        subpath.write_text(dumps(sub)+"\n")
    notes=[
      (20,20,"KESTREL REV B - INTEGRATED BOARD - ENGINEERING DRAFT"),
      (20,27,"Implemented: input/bucks, bare FPGA/P4, HP, ADC/DAC/mute, SPI, backlight, LCD/touch supplies, RGB565/I2C and two footswitches."),
      (20,220,"Remaining: protection/power validation, panel contact/part qualification, physical placement and analogue validation."),
      (20,227,"Remaining: MCU crystal/parts, SPI/display timing/sequencing, panel procurement, oscillator and clock/enable RTL migration."),
      (20,234,"ERC checks connectivity; pending firmware, qualification and physical design prevent fabrication release."),
    ]
    for x,y,t in notes:
        tree.append(node(f'(text "{t}" (at {x} {y} 0) (effects (font (size 1.27 1.27)) '
                         f'(justify left)) (uuid "{uid(t)}"))'))
    path.write_text(dumps(tree)+"\n")
    pro=path.with_suffix(".kicad_pro")
    if not pro.exists(): pro.write_text(json.dumps({"meta":{"filename":pro.name,"version":1}},indent=2)+"\n")
    print(path)


if __name__=="__main__": main()
