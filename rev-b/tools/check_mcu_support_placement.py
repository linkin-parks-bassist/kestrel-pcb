#!/usr/bin/env python3
"""Bounded partial MCU support-pose and local net/proximity allocation review.

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
    data = json.loads((ROOT/'electrical/mcu-support-placement.json').read_text())
    for ref, (x, y, angle) in data['poses'].items():
        fp = fps[ref]
        pos = fp.GetPosition()
        assert abs(pcbnew.ToMM(pos.x)-(100+x)) < .00001, ref
        assert abs(pcbnew.ToMM(pos.y)-(100-y)) < .00001, ref
        assert abs((fp.GetOrientationDegrees()-angle+180) % 360 - 180) < .001, ref
        assert fp.GetLayer() == pcbnew.F_Cu, ref
    pads = {ref: {p.GetNumber(): p for p in fp.Pads()} for ref, fp in fps.items()}
    for i in range(701, 717):
        fp = fps[f'C{i}']
        assert fp.GetFPID().GetLibItemName() == 'C_0402_1005Metric'
        assert fp.GetFieldText('MPN') == 'CL05B104KO5NNNC'
        assert fp.GetFieldText('LCSC') == 'C1525'
    for ref in ['R708', 'R709']:
        assert fps[ref].GetFPID().GetLibItemName() == 'R_0402_1005Metric'
    targets = [('C701', 'U701', '9', 2.5), ('C702', 'U701', '21', 2.5),
               ('C704', 'U701', '85', 2.5), ('C705', 'U701', '96', 2.5), ('C703', 'U701', '62', 2.5),
               ('C711', 'U701', '54', 2.5), ('C716', 'U701', '67', 2.5),
               ('C706', 'U701', '101', 2.5), ('C707', 'U701', '102', 2.5),
               ('C708', 'U701', '75', 2.5), ('C709', 'U701', '77', 2.5),
               ('C712', 'U701', '76', 2.5), ('C713', 'U701', '91', 2.5),
               ('C714', 'U701', '30', 2.5), ('C715', 'U701', '59', 2.5),
               ('C710', 'U701', '26', 2.5), ('C729', 'U702', '8', 2.5),
               ('C730', 'Y701', '1', 2.5), ('C731', 'Y701', '3', 2.5),
               ('C732', 'U701', '103', 2.5), ('R708', 'U701', '100', 3.0),
               ('R709', 'U701', '99', 3.0)]
    targets += [(f'R{701+i}', 'U701', str(pin), 8.0)
                for i, pin in enumerate([27, 28, 29, 31, 32, 33])]
    bulk_pins = [9, 102, 75, 77, 26, 30, 59, 67, 71, 72, 73, 74]
    bulk_targets = [(f'C{717+i}', 'U701', str(pin), None)
                    for i, pin in enumerate(bulk_pins)]
    bulk_targets[4] = ('C721', 'L601', '2', None)  # HP bulk relative to regulator output
    targets += bulk_targets
    review = {}
    for ref, owner, pin, bound in targets:
        source = pads[owner][pin]
        target = pads[ref]['1']
        assert target.GetNetname() == source.GetNetname(), ref
        if ref.startswith('C'):
            assert pads[ref]['2'].GetNetname() == '/GND', ref
        delta = target.GetPosition()-source.GetPosition()
        distance = math.hypot(pcbnew.ToMM(delta.x), pcbnew.ToMM(delta.y))
        if bound is not None:
            assert distance <= bound, (ref, distance, bound)
        review[ref] = {'assigned_pin': f'{owner}.{pin}', 'pad_centre_distance_mm': round(distance, 4),
                       'engineering_target_mm': bound,
                       'distance_qualified': False}
    result = {'status': 'PASS poses/nets and 28 bounded proximity allocations; 12 bulk distances observed; routing/performance unqualified',
              'placed_references': list(data['poses']), 'local_allocations': review,
              'limits': ['Bulk capacitor distances are observations without an acceptance bound; effective decoupling and routing remain unqualified.',
                         'Routes, ground returns, signal integrity, manufacturing and mechanical assembly remain unqualified.']}
    (ROOT/'generated/mcu-support-placement-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print('PASS: 45 MCU support poses; 28 bounded local allocations and 12 bulk-net allocations with measured distances; routes and crystal values unqualified.')


if __name__ == '__main__':
    main()
