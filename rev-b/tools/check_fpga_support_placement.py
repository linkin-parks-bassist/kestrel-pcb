#!/usr/bin/env python3
"""Bounded support-pose and local source/bypass allocation review.

Distance targets are provisional engineering placement bounds, not electrical
guarantees. Routes, ground loops, SI and mechanical assembly remain unqualified.
"""
import json
import math
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def main():
    board = pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    data = json.loads((ROOT/'electrical/fpga-support-placement.json').read_text())
    for ref, (x, y, angle) in data['poses'].items():
        fp = fps[ref]
        pos = fp.GetPosition()
        assert abs(pcbnew.ToMM(pos.x)-(100+x)) < .00001, ref
        assert abs(pcbnew.ToMM(pos.y)-(100-y)) < .00001, ref
        assert abs((fp.GetOrientationDegrees()-angle+180) % 360 - 180) < .001, ref
        assert fp.GetLayer() == pcbnew.F_Cu, ref
    pads = {ref: {p.GetNumber(): p for p in fp.Pads()} for ref, fp in fps.items()}
    targets = [('C523', 'U502', '8', 2.5), ('C524', 'Y501', '1', 2.5),
               ('C525', 'J501', '6', 5.0), ('C526', 'U503', '5', 2.5),
               ('C527', 'U504', '5', 2.5), ('R512', 'Y501', '3', 3.0),
               ('R513', 'U501', '25', 4.5), ('R514', 'U501', '29', 4.5),
               ('R515', 'U501', '26', 4.5), ('R516', 'U501', '31', 4.5),
               ('R519', 'U503', '4', 2.5)]
    review = {}
    for ref, owner, pin, bound in targets:
        source = pads[owner][pin]
        target = pads[ref]['1']
        assert target.GetNetname() == source.GetNetname(), ref
        if ref.startswith('C'):
            assert pads[ref]['2'].GetNetname() == '/GND', ref
        delta = target.GetPosition()-source.GetPosition()
        distance = math.hypot(pcbnew.ToMM(delta.x), pcbnew.ToMM(delta.y))
        assert distance <= bound, (ref, distance, bound)
        review[ref] = {'assigned_pin': f'{owner}.{pin}', 'pad_centre_distance_mm': round(distance, 4),
                       'engineering_target_mm': bound}
    result = {'status': 'PASS bounded pose/net/proximity review; routing/performance unqualified',
              'placed_references': list(data['poses']), 'local_allocations': review,
              'limits': ['Routes, ground returns, signal integrity, manufacturing and mechanical assembly remain unqualified.']}
    (ROOT/'generated/fpga-support-placement-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: 24 FPGA support poses, five local bypass allocations and six source-resistor allocations.')


if __name__ == '__main__':
    main()
