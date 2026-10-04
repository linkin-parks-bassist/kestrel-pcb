#!/usr/bin/env python3
"""Check the placed FPGA per-pin capacitor net, side and proximity allocation.

The 2.5 mm pad-centre bound is an engineering placement target, not a vendor
electrical guarantee. No routes, return loops, impedance or 3D fit are certified.
"""
import json
import math
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    board = pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    data = json.loads((ROOT/'electrical/fpga-bypass-placement.json').read_text())
    pins = {p.GetNumber(): p for p in fps['U501'].Pads()}
    distances = {}
    for ref, (x, y, angle) in data['poses'].items():
        fp = fps[ref]
        pos = fp.GetPosition()
        assert abs(pcbnew.ToMM(pos.x)-(100+x)) < .00001, ref
        assert abs(pcbnew.ToMM(pos.y)-(100-y)) < .00001, ref
        assert abs((fp.GetOrientationDegrees()-angle+180) % 360 - 180) < .001, ref
        assert fp.GetLayer() == pcbnew.F_Cu, ref
    for ref, number in data['supply_pins'].items():
        pads = {p.GetNumber(): p for p in fps[ref].Pads()}
        assert pads['1'].GetNetname() == pins[str(number)].GetNetname(), ref
        assert pads['2'].GetNetname() == '/GND', ref
        delta = pads['1'].GetPosition()-pins[str(number)].GetPosition()
        distance = math.hypot(pcbnew.ToMM(delta.x), pcbnew.ToMM(delta.y))
        assert distance <= 2.5, (ref, number, distance)
        distances[ref] = {'U501_pin': number, 'power_pad_centre_distance_mm': round(distance, 4)}
    for bead, caps, pin in [('L501', ['C515', 'C516', 'C517'], '14'),
                            ('L502', ['C518', 'C519', 'C520'], '50')]:
        pads = {p.GetNumber(): p for p in fps[bead].Pads()}
        assert pads['1'].GetNetname() == '/+1V0_FPGA', bead
        assert pads['2'].GetNetname() == pins[pin].GetNetname(), bead
        for ref in caps:
            pads = {p.GetNumber(): p for p in fps[ref].Pads()}
            assert pads['1'].GetNetname() == pins[pin].GetNetname(), ref
            assert pads['2'].GetNetname() == '/GND', ref
    result = {'status': 'PASS bounded pose/net/proximity review; no routing or performance qualification',
              'placed_references': list(data['poses']), 'supply_capacitors': distances,
              'limits': ['Per-pin bypass and plane-ground continuity are checked separately by check_fpga_bypass_local.py; PLL and FPGA core/I/O pin/bulk continuity are checked separately by check_fpga_pll_local.py, check_fpga_core_distribution.py and check_fpga_io_distribution.py; remaining switched support supplies are checked by check_fpga_support_supply.py; SPI supply continuity is checked separately by check_spi_support_supply.py; local held-DAC buffer supply and audio signal continuity are checked separately by check_fpga_audio_local.py; Mute-control/sense-net and supervisor-supply continuity is checked by check_audio_mute_local.py; LDO/held-supply and sensed-rail source continuity is checked by check_analogue_power_local.py; DAC supply/pump and full held-rail continuity is checked by check_dac_support_local.py; ADC supply/bypass continuity is checked by check_adc_power_local.py; return impedance, effective decoupling, thermal/assembly and performance remain unqualified.']}
    (ROOT/'generated/fpga-bypass-placement-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f'PASS: {len(data["poses"])} FPGA bypass/filter poses; 14 supply-pin net/ground assignments and <=2.5 mm pad-centre distances; two PLL filter net groups.')


if __name__ == '__main__':
    main()
