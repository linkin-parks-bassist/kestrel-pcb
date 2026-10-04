#!/usr/bin/env python3
"""Guarded provisional front-side USB probe-pad placement, not a USB interface."""
import json
import pcbnew
from place_fpga_bypass import main, ROOT
if __name__ == '__main__':
    main('mcu-usb-service-placement.json', 'provisional_mcu_usb_service_references')
    d=json.loads((ROOT/'electrical/mcu-usb-service-placement.json').read_text())
    path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(path))
    fps={f.GetReference():f for f in b.GetFootprints()}
    for ref,xy in d['reference_positions_pcb_mm'].items():
        text=fps[ref].Reference();text.SetPosition(pcbnew.VECTOR2I(*(pcbnew.FromMM(v)for v in xy)))
    pcbnew.SaveBoard(str(path),b)
