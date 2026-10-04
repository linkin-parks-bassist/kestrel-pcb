#!/usr/bin/env python3
"""Generate hardware-strapped converters, SMD input buffer and analogue LDOs.

Run with the KiCad MCP venv. Datasheet-derived symbols are embedded; the local
reservoir footprint uses Panasonic's standard FK size-G recommended lands.
"""
import argparse
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRID = 1.27


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "kestrel/rev-b/audio/"+name))


def adc_library():
    """PCM1808 pin table from TI SLES177B p3; no inherited approximated part."""
    pins = [
        (1,"VREF","passive",10,8,180),
        (2,"AGND","power_in",2,-14,90),
        (3,"VCC","power_in",-2,14,270),
        (4,"VDD","power_in",2,14,270),
        (5,"DGND","power_in",-2,-14,90),
        (6,"SCKI","input",-10,-2,0),
        (7,"LRCK","bidirectional",-10,2,0),
        (8,"BCK","bidirectional",-10,0,0),
        (9,"DOUT","output",10,4,180),
        (10,"MD0","input",-10,-8,0),
        (11,"MD1","input",-10,-10,0),
        (12,"FMT","input",-10,-6,0),
        (13,"VINL","input",-10,10,0),
        (14,"VINR","input",-10,8,0),
    ]
    effects = '(effects (font (size 1.27 1.27)))'
    body = ''.join(f'(pin {kind} line (at {x*GRID} {y*GRID} {angle}) (length 2.54) '
                   f'(name "{name}" {effects}) (number "{num}" {effects}))'
                   for num,name,kind,x,y,angle in pins)
    return ('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '
            '(symbol "PCM1808" (pin_names (offset 0.508)) (in_bom yes) (on_board yes) '
            f'(property "Reference" "U" (at -10.16 17.78 0) {effects}) '
            f'(property "Value" "PCM1808" (at 2.54 17.78 0) {effects}) '
            '(property "Footprint" "Package_SO:TSSOP-14_4.4x5mm_P0.65mm" (at 0 0 0) '
            f'{effects[:-1]} (hide yes))) '
            '(property "Datasheet" "https://www.ti.com/lit/ds/symlink/pcm1808.pdf" (at 0 0 0) '
            f'{effects[:-1]} (hide yes))) '
            '(symbol "PCM1808_0_1" (rectangle (start -10.16 15.24) (end 10.16 -15.24) '
            '(stroke (width 0.254) (type default)) (fill (type background)))) '
            f'(symbol "PCM1808_1_1" {body})))\n')


def build(mcp_dir):
    sys.path.insert(0,str(mcp_dir))
    import sexpdata as sx
    from commands.dynamic_symbol_loader import DynamicSymbolLoader
    from utils.sexpr_format import dumps
    folder = ROOT/"electrical"
    folder.mkdir(exist_ok=True)
    loader=DynamicSymbolLoader(folder)
    library=sx.loads(adc_library())
    # Same series-diode drawing as BAV99, with BAV199 pin names/specification.
    diode=sx.loads(loader.extract_symbol_from_library("Diode","BAV99"))
    diode[1]="BAV199"
    S=sx.Symbol
    # Derive the body/courtyard from KiCad's generic 10-mm capacitor; use
    # Panasonic FK standard size G lands (gap 4.6, length 4.1, width 2.0 mm).
    footprint=sx.loads(Path("/usr/share/kicad/footprints/Capacitor_SMD.pretty/CP_Elec_10x10.5.kicad_mod").read_text())
    footprint[1]="CP_Elec_Panasonic_FK_G_10x10.2"
    for item in footprint:
        if not isinstance(item,list) or not item: continue
        if item[0]==S("descr"):
            item[1]="Panasonic FK standard size G; 10.2 +/-0.3 mm height, 10 mm diameter; manufacturer 4.6 mm gap / 4.1x2 mm lands; KiCad generic body/model"
        if item[0]==S("property") and item[1]=="Value": item[2]=footprint[1]
        if item[0]==S("pad"):
            item[3]=S("rect")
            next(x for x in item if isinstance(x,list) and x and x[0]==S("at"))[1]=(-4.35 if item[1]=="1" else 4.35)
            next(x for x in item if isinstance(x,list) and x and x[0]==S("size"))[1:]=[4.1,2.0]
            item[:]=[x for x in item if not (isinstance(x,list) and x and x[0]==S("roundrect_rratio"))]
    pretty=folder/"KestrelAudio.pretty"
    pretty.mkdir(exist_ok=True)
    (pretty/(footprint[1]+".kicad_mod")).write_text(dumps(footprint)+"\n")
    (folder/"fp-lib-table").write_text('(fp_lib_table (version 7) (lib (name "KestrelAudio") '
        '(type "KiCad") (uri "${KIPRJMOD}/KestrelAudio.pretty") (options "") '
        '(descr "Manufacturer land patterns for Rev-B audio")))\n')
    for item in diode:
        if not isinstance(item,list) or not item: continue
        if item[0]==S("property"):
            values={"Value":"BAV199","Datasheet":"https://assets.nexperia.com/documents/data-sheet/BAV199.pdf",
                    "Description":"Nexperia low-leakage series double diode, SOT23"}
            if item[1] in values: item[2]=values[item[1]]
        if item[0]==S("symbol"):
            item[1]=str(item[1]).replace("BAV99_","BAV199_")
            for pin in item:
                if not isinstance(pin,list) or not pin or pin[0]!=S("pin"): continue
                number=next(v[1] for v in pin if isinstance(v,list) and v and v[0]==S("number"))
                next(v for v in pin if isinstance(v,list) and v and v[0]==S("name"))[1]={"1":"A1","2":"K2","3":"K1/A2"}[str(number)]
    library.append(diode)
    supervisor=sx.loads(loader.extract_symbol_from_library("Power_Supervisor","TPS3808DBV"))
    supervisor[1]="TPS3808G01"
    for item in supervisor:
        if not isinstance(item,list) or not item: continue
        if item[0]==S("property") and item[1]=="Value": item[2]="TPS3808G01"
        if item[0]==S("property") and item[1]=="Datasheet": item[2]="https://www.ti.com/lit/ds/symlink/tps3808.pdf"
        if item[0]==S("symbol"):
            item[1]=str(item[1]).replace("TPS3808DBV_","TPS3808G01_")
            for pin in item:
                if not isinstance(pin,list) or not pin or pin[0]!=S("pin"): continue
                number=next(v[1] for v in pin if isinstance(v,list) and v and v[0]==S("number"))
                if str(number)=="1": pin[1]=S("open_collector")
    library.append(supervisor)
    (folder/"KestrelAudio.kicad_sym").write_text(dumps(library)+"\n")
    (folder/"sym-lib-table").write_text('(sym_lib_table (version 7) '
        '(lib (name "KestrelAudio") (type "KiCad") '
        '(uri "${KIPRJMOD}/KestrelAudio.kicad_sym") (options "") '
        '(descr "Datasheet-checked audio converter, protection and supervisor symbols")))\n')
    out=folder/"kestrel-revb-audio.kicad_sch"
    out.write_text(f'(kicad_sch (version 20260101) (generator "eeschema") '
                   f'(generator_version "10.0") (uuid "{uid("sheet")}") '
                   '(paper "A2") (lib_symbols) (sheet_instances (path "/" (page "1"))))\n')
    cap = "Capacitor_SMD:C_0603_1608Metric"
    bulk = "Capacitor_SMD:C_0805_2012Metric"
    res = "Resistor_SMD:R_0603_1608Metric"
    # Each connection is a datasheet/design net, separate from its visual placement.
    parts = [
      ("U201","KestrelAudio:PCM1808","PCM1808PWR","Package_SO:TSSOP-14_4.4x5mm_P0.65mm",75,55,0,
       {"1":"ADC_VREF","2":"GND","3":"+5V_A","4":"+3V3_D","5":"GND",
        "6":"AUDIO_MCLK","7":"AUDIO_LRCLK","8":"AUDIO_BCLK","9":"ADC_DOUT",
        "10":"ADC_MD0","11":"ADC_MD1","12":"ADC_FMT","13":"ADC_IN_L","14":"ADC_IN_R"}),
      ("U202","Audio:PCM5102A","PCM5102APWR","Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",195,55,0,
       {"1":"+3V3_A","2":"DAC_CAPP","3":"GND","4":"DAC_CAPM","5":"DAC_VNEG",
        "6":"DAC_OUT_L","7":None,"8":"+3V3_A","9":"GND","10":"GND","11":"+3V3_A",
        "12":"GND","13":"AUDIO_BCLK","14":"DAC_DIN","15":"AUDIO_LRCLK","16":"GND",
        "17":"AUDIO_RUN","18":"DAC_LDOO","19":"GND","20":"+3V3_A"}),
      ("C201","Device:C","1uF",bulk,36,45,90,{"1":"AFE_OUT","2":"ADC_AC_L"}),
      ("R201","Device:R","100",res,49,45,90,{"1":"ADC_AC_L","2":"ADC_IN_L"}),
      ("C202","Device:C","10nF",cap,25,53,0,{"1":"ADC_IN_L","2":"GND"}),
      ("C203","Device:C","1uF",bulk,36,62,90,{"1":"GND","2":"ADC_IN_R"}),
      ("R202","Device:R","10k",res,46,86,0,{"1":"ADC_FMT","2":"GND"}),
      ("R203","Device:R","10k",res,60,86,0,{"1":"ADC_MD0","2":"GND"}),
      ("R204","Device:R","10k",res,74,86,0,{"1":"ADC_MD1","2":"GND"}),
      ("R205","Device:R","100k",res,175,86,0,{"1":"AUDIO_RUN","2":"GND"}),
      ("C204","Device:C","10uF",bulk,32,113,0,{"1":"+5V_A","2":"GND"}),
      ("C205","Device:C","100nF",cap,46,113,0,{"1":"+5V_A","2":"GND"}),
      ("C206","Device:C","10uF",bulk,64,113,0,{"1":"+3V3_D","2":"GND"}),
      ("C207","Device:C","100nF",cap,78,113,0,{"1":"+3V3_D","2":"GND"}),
      ("C208","Device:C","10uF",bulk,96,113,0,{"1":"ADC_VREF","2":"GND"}),
      ("C209","Device:C","100nF",cap,110,113,0,{"1":"ADC_VREF","2":"GND"}),
      ("C210","Device:C","10uF",bulk,152,113,0,{"1":"+3V3_A","2":"GND"}),
      ("C211","Device:C","100nF",cap,166,113,0,{"1":"+3V3_A","2":"GND"}),
      ("C212","Device:C","10uF",bulk,184,113,0,{"1":"+3V3_A","2":"GND"}),
      ("C213","Device:C","100nF",cap,198,113,0,{"1":"+3V3_A","2":"GND"}),
      ("C214","Device:C","10uF",bulk,216,113,0,{"1":"+3V3_A","2":"GND"}),
      ("C215","Device:C","100nF",cap,230,113,0,{"1":"+3V3_A","2":"GND"}),
      ("C216","Device:C","10uF",bulk,226,85,0,{"1":"DAC_LDOO","2":"GND"}),
      ("C217","Device:C","100nF",cap,240,85,0,{"1":"DAC_LDOO","2":"GND"}),
      ("C218","Device:C","2.2uF",bulk,228,52,0,{"1":"DAC_CAPP","2":"DAC_CAPM"}),
      ("C219","Device:C","2.2uF",bulk,250,72,0,{"1":"GND","2":"DAC_VNEG"}),
      ("R206","Device:R","470",res,240,37,90,{"1":"DAC_OUT_L","2":"AUDIO_OUT"}),
      ("C220","Device:C","2.2nF C0G",cap,256,45,0,{"1":"AUDIO_OUT","2":"GND"}),
      # FET input buffer and separate buffered bias; the ADC keeps its own bias.
      ("U203","Amplifier_Operational:OPA1656ID","OPA1656IDR","Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",70,164,0,
       {"1":"INPUT_BUFFER","2":"INPUT_BUFFER","3":"INPUT_BIASED"},1),
      ("U203","Amplifier_Operational:OPA1656ID","OPA1656IDR","Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",135,164,0,
       {"5":"BIAS_RAW","6":"VMID_BUF","7":"VMID_BUF"},2),
      ("U203","Amplifier_Operational:OPA1656ID","OPA1656IDR","Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",135,194,0,
       {"4":"GND","8":"9V_PROTECTED"},3),
      ("R207","Device:R","10M",res,25,183,0,{"1":"AUDIO_IN","2":"GND"}),
      ("C221","Device:C","47nF C0G","Capacitor_SMD:C_1206_3216Metric",25,164,90,{"1":"AUDIO_IN","2":"INPUT_AC"}),
      ("R208","Device:R","4.7k","Resistor_SMD:R_1206_3216Metric",45,164,90,{"1":"INPUT_AC","2":"INPUT_BIASED"}),
      ("R209","Device:R","1M",res,52,183,0,{"1":"INPUT_BIASED","2":"VMID"}),
      ("R210","Device:R","1k",res,100,164,90,{"1":"INPUT_BUFFER","2":"AFE_OUT"}),
      ("R211","Device:R","1k",res,90,183,0,{"1":"AFE_OUT","2":"VMID"}),
      ("R212","Device:R","17.4k",res,112,151,0,{"1":"9V_PROTECTED","2":"BIAS_RAW"}),
      ("R213","Device:R","10k",res,112,177,0,{"1":"BIAS_RAW","2":"GND"}),
      ("C222","Device:C","10uF",bulk,112,199,0,{"1":"BIAS_RAW","2":"GND"}),
      # Isolation from capacitive load on the unity-gain bias buffer.
      ("R214","Device:R","47",res,172,164,90,{"1":"VMID_BUF","2":"VMID"}),
      ("C223","Device:C","10uF",bulk,178,183,0,{"1":"VMID","2":"GND"}),
      ("C224","Device:C","100nF",cap,153,194,0,{"1":"9V_PROTECTED","2":"GND"}),
      ("C225","Device:C","10uF",bulk,168,194,0,{"1":"9V_PROTECTED","2":"GND"}),
      # ADC analogue rail is linear from 9 V: a 5 V buck cannot feed a 5 V LDO.
      ("U204","Regulator_Linear:TLV76750DRVx","TLV76750DRVR","Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm_ThermalVias",221,158,0,
       {"1":"+5V_A","2":"+5V_A","3":"GND","4":"9V_PROTECTED","5":"GND","6":"9V_PROTECTED","7":"GND"}),
      ("C226","Device:C","2.2uF",bulk,196,158,0,{"1":"9V_PROTECTED","2":"GND"}),
      ("C227","Device:C","2.2uF",bulk,248,158,0,{"1":"+5V_A","2":"GND"}),
      ("U205","Regulator_Linear:TLV75533PDBV","TLV75533PDBVR","Package_TO_SOT_SMD:SOT-23-5",221,188,0,
       {"1":"+5V_DAC_HOLD","2":"GND","3":"+5V_DAC_HOLD","4":None,"5":"+3V3_A"}),
      ("C228","Device:C","2.2uF",bulk,196,188,0,{"1":"+5V_DAC_HOLD","2":"GND"}),
      ("C229","Device:C","2.2uF",bulk,248,188,0,{"1":"+3V3_A","2":"GND"}),
      # Switched mono sockets: actual footprint pads are T/TN/S/SN, not T/R/S/G.
      # Input TN grounds the tip while unplugged; output TN must not short the DAC.
      ("J201","Connector_Audio:AudioJack2_Switch","NMJ4HCD2 INPUT",
       "Connector_Audio:Jack_6.35mm_Neutrik_NMJ4HCD2_Horizontal",290,45,0,
       {"T":"AUDIO_IN","TN":"GND","S":"GND","SN":None}),
      ("J202","Connector_Audio:AudioJack2_Switch","NMJ4HCD2 OUTPUT",
       "Connector_Audio:Jack_6.35mm_Neutrik_NMJ4HCD2_Horizontal",290,85,0,
       {"T":"AUDIO_OUT","TN":None,"S":"GND","SN":None}),
      # First-stage jack ESD clamps are bipolar; they do not certify IC immunity.
      ("D201","Device:D_TVS","PESD5V0U1BA,115","Diode_SMD:D_SOD-323",290,115,90,
       {"1":"AUDIO_IN","2":"GND"}),
      ("D202","KestrelAudio:BAV199","BAV199,215","Package_TO_SOT_SMD:SOT-23",45,199,0,
       {"1":"GND","2":"9V_PROTECTED","3":"INPUT_BIASED"}),
      ("D203","Device:D_TVS","PESD5V0U1BA,115","Diode_SMD:D_SOD-323",290,160,90,
       {"1":"AUDIO_OUT","2":"GND"}),
      # Isolate DAC energy storage from the buck and all main digital loads.
      ("D204","Diode:SS14","SS14-E3/61T","Diode_SMD:D_SMA",220,250,180,
       {"1":"+5V_DAC_HOLD","2":"+5V_DIG"}),
      ("C230","Device:C_Polarized","1000uF EEEFK1A102P","KestrelAudio:CP_Elec_Panasonic_FK_G_10x10.2",246,270,0,
       {"1":"+5V_DAC_HOLD","2":"GND"}),
      ("C235","Device:C_Polarized","1000uF EEEFK1A102P","KestrelAudio:CP_Elec_Panasonic_FK_G_10x10.2",276,270,0,
       {"1":"+5V_DAC_HOLD","2":"GND"}),
      ("U206","KestrelAudio:TPS3808G01","TPS3808G01DBVR","Package_TO_SOT_SMD:SOT-23-6",70,280,0,
       {"1":"AUDIO_RUN","2":"GND","3":"AUDIO_ENABLE","4":None,"5":"SENSE_ADC_5V","6":"+3V3_A"}),
      ("U207","KestrelAudio:TPS3808G01","TPS3808G01DBVR","Package_TO_SOT_SMD:SOT-23-6",165,280,0,
       {"1":"AUDIO_RUN","2":"GND","3":"AUDIO_ENABLE","4":None,"5":"SENSE_BUCK_5V","6":"+3V3_A"}),
      ("R215","Device:R","105k 0.1%",res,40,269,0,{"1":"+5V_A","2":"SENSE_ADC_5V"}),
      ("R216","Device:R","10k 0.1%",res,40,294,0,{"1":"SENSE_ADC_5V","2":"GND"}),
      ("R217","Device:R","105k 0.1%",res,135,269,0,{"1":"+5V_DIG","2":"SENSE_BUCK_5V"}),
      ("R218","Device:R","10k 0.1%",res,135,294,0,{"1":"SENSE_BUCK_5V","2":"GND"}),
      ("R219","Device:R","1k",res,110,280,0,{"1":"AUDIO_ENABLE","2":"GND"}),
      ("R220","Device:R","10k",res,205,280,0,{"1":"+3V3_A","2":"AUDIO_RUN"}),
      ("C231","Device:C","1nF C0G",cap,55,305,0,{"1":"SENSE_ADC_5V","2":"GND"}),
      ("C232","Device:C","1nF C0G",cap,150,305,0,{"1":"SENSE_BUCK_5V","2":"GND"}),
      ("C233","Device:C","100nF",cap,85,305,0,{"1":"+3V3_A","2":"GND"}),
      ("C234","Device:C","100nF",cap,180,305,0,{"1":"+3V3_A","2":"GND"}),
      ("#FLG0205","power:PWR_FLAG","PWR_FLAG","",246,245,0,{"1":"+5V_DAC_HOLD"}),
    ]
    shorter={"INPUT_BUFFER":"IN_BUF","INPUT_BIASED":"IN_BIAS","VMID_BUF":"BIAS_BUF"}
    parts=[(*p[:7],{pin:shorter.get(net,net) for pin,net in p[7].items()},p[8] if len(p)==9 else 1) for p in parts]
    for ref,lib,value,foot,x,y,angle,nets,unit in parts:
        library,name=lib.split(":")
        loader.inject_symbol_into_schematic(out,library,name)
        if not loader.create_component_instance(out,library,name,ref,value,foot,x*GRID,y*GRID,angle=angle,unit=unit):
            raise RuntimeError(ref)
    tree=sx.loads(out.read_text()); S=sx.Symbol

    def node(s): return sx.loads(s)
    def prop(item,key): return next(x for x in item if isinstance(x,list) and x and x[0]==S(key))
    symbols={str(x[1]):x for x in prop(tree,"lib_symbols")[1:]}
    exposed=set()
    def definitions(lib):
        symbol=symbols[lib]
        ext=next((x[1] for x in symbol if isinstance(x,list) and x and x[0]==S("extends")),None)
        return definitions(lib.split(":")[0]+":"+ext) if ext else symbol
    def pin_coordinates(lib,x,y,angle,selected_unit):
        coords={}; rad=math.radians(angle)
        for unit in definitions(lib):
            if not isinstance(unit,list) or not unit or unit[0]!=S("symbol"): continue
            if int(str(unit[1]).rsplit("_",2)[1]) not in (0,selected_unit): continue
            for pin in unit:
                if not isinstance(pin,list) or not pin or pin[0]!=S("pin"): continue
                px,py,pangle=prop(pin,"at")[1:]
                # KiCad library Y is up, schematic Y down; rotation is CCW.
                tx=px*math.cos(rad)-py*math.sin(rad)
                ty=-px*math.sin(rad)-py*math.cos(rad)
                coords[str(prop(pin,"number")[1])]=(round(x*GRID+tx,2),round(y*GRID+ty,2),(pangle+angle)%360)
        return coords
    def stub(net,px,py,pangle,tag):
        vx,vy={0:(-5.08,0),90:(0,5.08),180:(5.08,0),270:(0,-5.08)}[pangle]
        ex,ey=round(px+vx,2),round(py+vy,2)
        tree.append(node(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) '
                         f'(stroke (width 0) (type default)) (uuid "{uid(tag+"wire")}"))'))
        justify='right bottom' if vx<0 else 'left bottom'
        text_angle=90 if vy else 0
        # Hierarchical boundaries distinguish unimplemented drivers from local nets.
        boundary={"9V_PROTECTED":"input","+5V_DIG":"input","AUDIO_MCLK":"input","AUDIO_BCLK":"input",
                  "AUDIO_LRCLK":"input","DAC_DIN":"input","ADC_DOUT":"output",
                  "AUDIO_ENABLE":"input","GND":"bidirectional",
                  "+3V3_D":"input","+3V3_A":"output"}
        is_boundary=net in boundary and net not in exposed
        kind='hierarchical_label' if is_boundary else 'label'
        shape=f'(shape {boundary[net]})' if is_boundary else ''
        if is_boundary: exposed.add(net)
        tree.append(node(f'({kind} "{net}" {shape} (at {ex} {ey} {text_angle}) '
                         f'(effects (font (size 0.9 0.9)) (justify {justify})) (uuid "{uid(tag+"label")}"))'))
    for ref,lib,value,foot,x,y,angle,nets,unit in parts:
        coords=pin_coordinates(lib,x,y,angle,unit)
        if set(coords)!=set(nets): raise ValueError(f'{ref} pins differ: {coords.keys()} {nets.keys()}')
        for pin,net in nets.items():
            px,py,pa=coords[pin]; tag=ref+"/"+str(unit)+"/"+pin
            if net is None:
                tree.append(node(f'(no_connect (at {px} {py}) (uuid "{uid(tag)}"))'))
            else: stub(net,px,py,pa,tag)
    # Stable UUIDs and horizontal, legible fields for passive parts.
    by_ref={(p[0],p[8]):p for p in parts}
    for inst in tree:
        if not isinstance(inst,list) or not inst or inst[0]!=S("symbol"): continue
        ref=next(p[2] for p in inst if isinstance(p,list) and p and p[0]==S("property") and p[1]=="Reference")
        unit=prop(inst,"unit")[1]
        _,lib,value,foot,x,y,angle,_,_=by_ref[ref,unit]
        prop(inst,"uuid")[1]=uid(ref+"/"+str(unit))
        for child in inst:
            if not isinstance(child,list) or not child: continue
            if child[0]==S("pin"): prop(child,"uuid")[1]=uid(ref+"pin"+str(child[1]))
            if child[0]==S("property") and child[1] in ("Reference","Value") and not ref.startswith("#"):
                is_ref=child[1]=="Reference"
                if ref.startswith(("U","J")):
                    fx,fy=x-8,y-(18 if is_ref else 16)
                    if ref=="U203" and unit==3: fx,fy=x-16,y-(8 if is_ref else 6)
                elif angle==90:
                    fx,fy=x-2,y-(6 if is_ref else 4)
                else:
                    fx,fy=x+3,y+(-1 if is_ref else 1)
                if ref=="D202": fx,fy=x-7,y-(6 if is_ref else 4)
                if ref=="D204": fx,fy=x-6,y-(6 if is_ref else 4)
                field_angle=0 if ref=="D204" else angle
                prop(child,"at")[1:]=[round(fx*GRID,2),round(fy*GRID,2),field_angle]
                prop(child,"effects")[1:]=node('(effects (font (size 0.9 0.9)) (justify left))')[1:]
        if ref.startswith("C"):
            rating="50 V C0G; input transient barrier" if ref=="C221" else "16 V minimum; bulk effective capacitance to verify"
            if ref in ("C230","C235"): rating="10 V; +/-20 percent at 20 C; 2000 h at 105 C; ageing/temp/pulse impedance/inrush validation pending"
            inst.append(node(f'(property "Rating" "{rating}" '
                             f'(at {x*GRID} {y*GRID} 0) (effects (font (size 1.27 1.27)) (hide yes)))'))
        if ref=="R208":
            inst.append(node(f'(property "Rating" "1 percent; 0.25 W minimum; pulse rating to verify" '
                             f'(at {x*GRID} {y*GRID} 0) (effects (font (size 1.27 1.27)) (hide yes)))'))
        if ref in ("D201","D203"):
            for item in inst:
                if isinstance(item,list) and item and item[0]==S("property") and item[1]=="Datasheet":
                    item[2]="https://assets.nexperia.com/documents/data-sheet/PESD5V0U1BA.pdf"
        if ref=="D204":
            for item in inst:
                if isinstance(item,list) and item and item[0]==S("property") and item[1]=="Datasheet":
                    item[2]="https://www.vishay.com/docs/88746/ss12.pdf"
        if ref in ("C230","C235"):
            for item in inst:
                if isinstance(item,list) and item and item[0]==S("property") and item[1]=="Datasheet":
                    item[2]="https://industrial.panasonic.com/cdbs/www-data/pdf/RDE0000/ABA0000C1181.pdf"
            for key,value in (("Manufacturer","Panasonic"),("MPN","EEEFK1A102P"),("LCSC","C278397")):
                inst.append(node(f'(property "{key}" "{value}" (at {x*GRID} {y*GRID} 0) '
                                 '(effects (font (size 1.27 1.27)) (hide yes)))'))
        if ref.startswith("J"):
            inst.append(node(f'(property "AssemblySide" "B.Cu; underside through-hole post assembly" '
                             f'(at {x*GRID} {y*GRID} 0) (effects (font (size 1.27 1.27)) (hide yes)))'))
    texts=[
      (20,16,"KESTREL REV B - HARDWARE-CONFIGURED ADC/DAC - ENGINEERING DRAFT"),
      (20,22,"No audio I2C. Mono left channel. Protection and supervisor mute included; layout, rail hold-up and backend validation pending."),
      (20,28,"Clock target: synchronous 48 kHz LRCLK / 3.072 MHz BCLK / 12.288 MHz ADC MCLK. Current RTL must be migrated."),
      (20,264,"Input: approx 0.91 Mohm, bias 3.285 V at 9 V; 1:2 AC attenuation. Headroom/protection need tolerance review and bench tests."),
      (20,270,"ADC VREF is decoupling only. VINR AC grounded. DAC charge-pump/bypass returns must be short; use one common ground plane."),
      (20,276,"DAC low-latency filter; supervisor AUDIO_RUN defaults muted. Protection/hold-up validation, sourcing and thermal checks remain."),
      (20,282,"Source: TI PCM1808, PCM510xA, OPA1656, TLV767 and TLV755P datasheets. Do not fabricate this partial design."),
      (350,224,"D201/D203: bipolar ESD clamps",0.9),
      (350,228,"Place at jacks; short ground return",0.9),
      (350,235,"D202: low-leakage input steering",0.9),
      (350,239,"Backfeed/fault tests remain",0.9),
      (20,305,"DAC HOLD-UP / SUPERVISOR MUTE - ENGINEERING DRAFT"),
      (20,311,"DAC AVDD/CPVDD/DVDD share held 3.3 V. ADC 5 V and buck 5 V monitored; either low asserts XSMT."),
      (20,317,"AUDIO_ENABLE must be driven HIGH only after FPGA clocks/data are stable. CT open: 20 ms release delay; default enable LOW."),
      (20,405,"C230/C235 Panasonic FK 2x1000 uF: verify inrush/pulse impedance/temp/age/load and >= 150/fs + 0.2 ms mute hold-up on hardware."),
    ]
    for x,y,t,*font in texts:
        size=font[0] if font else 1.27
        tree.append(node(f'(text "{t}" (at {x} {y} 0) (effects (font (size {size} {size})) '
                         f'(justify left)) (uuid "{uid(t)}"))'))
    out.write_text(dumps(tree)+"\n"); print(out)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--mcp-python-dir",type=Path,default=Path.home()/".local/share/kicad-mcp/python")
    build(parser.parse_args().mcp_python_dir)
