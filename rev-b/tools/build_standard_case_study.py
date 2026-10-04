#!/usr/bin/env python3
"""Measure reference bodies against the actual 1590XX casting with jack holes.

Run with CadQuery Python. This keeps the older custom case/PCB separate; it
does not quietly replace the electrical board outline with an unqualified fit.
"""
import hashlib
import json
from pathlib import Path
import cadquery as cq

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / 'mechanical/standard-case.json').read_text())
    original = json.loads((ROOT / 'mechanical/dimensions.json').read_text())
    path = ROOT / 'mechanical' / config['vendor_model']
    # Supplier axes: X=145.2 width, Y=height, Z=121.2 depth. Map the lid
    # underside to Z=0 and the pedal top to Z=39.3, foot end at negative Y.
    parts = [s.rotate((0, 0, 0), (1, 0, 0), -90).translate((0, 0, 4.1))
             for s in cq.importers.importStep(str(path)).solids().vals()]
    assert len(parts) == 6, 'Expected body, lid and four screws'
    j = config['audio_jacks']
    axis_z = config['pcb']['bottom_z'] - j['axis_above_component_plane']
    # Nominal drawing cutouts for the underside jacks only. Aperture fit and
    # ferrule/nut engagement require tolerances and assembly qualification.
    holes = (cq.Workplane('YZ').center(j['centre_y'], axis_z)
             .circle(j['hole_diameter']/2).extrude(80, both=True))
    parts[0] = parts[0].cut(holes.val())
    assembly = cq.Assembly(name='1590XX_reference_fit_UNQUALIFIED')
    volumes = {}
    for i, part in enumerate(parts):
        name = ['casting', 'lid', 'screw_1', 'screw_2', 'screw_3', 'screw_4'][i]
        assembly.add(part, name=name, color=cq.Color(.45, .47, .5, .45))
        if i < 2:
            volumes[name] = part
    d = original['display']
    display = (cq.Workplane('XY').box(d['body_width'], d['body_depth'], d['body_thickness'])
               .translate((*config['display_centre'], config['display_top_z'] - d['body_thickness']/2)).val())
    volumes['reference_display'] = display
    assembly.add(display, name='reference_display', color=cq.Color(.1, .4, .7, .7))
    f = original['footswitches']
    for i, (x, y) in enumerate(config['switch_centres'], 1):
        switch = (cq.Workplane('XY').center(x, y).circle(f['body_diameter']/2)
                  .extrude(f['body_depth']).translate((0, 0, config['switch_top_z'] - f['body_depth'])).val())
        name = f'switch_{i}_conservative_envelope'
        volumes[name] = switch
        assembly.add(switch, name=name, color=cq.Color(.7, .45, .1, .7))
    b = config['pcb']
    rectangular = (cq.Workplane('XY').box(b['width'], b['depth'], b['thickness'])
                   .translate((0, 0, b['bottom_z'] + b['thickness']/2)))
    pcb = rectangular
    for x, y in b['boss_centres']:
        cutter = cq.Workplane('XY').center(x, y).circle(b['boss_keepout_radius']).extrude(45)
        pcb = pcb.cut(cutter)
    for x, y in config['switch_centres']:
        cutter = cq.Workplane('XY').center(x, y).circle(f['body_diameter']/2 + b['switch_clearance']).extrude(45)
        pcb = pcb.cut(cutter)
    for sign in (-1, 1):
        for dx in j['pin_panel_offsets']:
            for dy in j['pin_row_offsets']:
                drill = (cq.Workplane('XY').center(sign*(j['panel_datum_x']+dx), j['centre_y']+dy)
                         .circle(j['pcb_drill']/2).extrude(45))
                pcb = pcb.cut(drill)
    for x, y in b['mounts']:
        drill = cq.Workplane('XY').center(x, y).circle(b['mount_hole_diameter']/2).extrude(45)
        pcb = pcb.cut(drill)
    pcb = pcb.val()
    volumes['candidate_notched_pcb'] = pcb
    assembly.add(pcb, name='candidate_notched_pcb', color=cq.Color(.1, .5, .2, .65))
    jack_path = ROOT / 'mechanical' / j['vendor_model']
    jack = cq.importers.importStep(str(jack_path)).val()
    for name, sign in [('input', -1), ('output', 1)]:
        solid = (jack.rotate((0, 0, 0), (1, 0, 0), -90)
                 .rotate((0, 0, 0), (0, 0, 1), -90*sign)
                 .translate((sign*j['panel_datum_x'], j['centre_y'], b['bottom_z'])))
        label = name + '_vendor_jack_body'
        volumes[label] = solid
        assembly.add(solid, name=label, color=cq.Color(.25, .25, .25))
    caps = config['reservoirs']
    for ref, (x, y) in zip(caps['references'], caps['centres']):
        solid = (cq.Workplane('XY').box(caps['body_width'], caps['body_width'], caps['max_height'])
                 .translate((x, y, b['bottom_z'] + b['thickness'] + caps['max_height']/2)).val())
        volumes[ref + '_maximum_body_envelope'] = solid
        assembly.add(solid, name=ref + '_maximum_body_envelope', color=cq.Color(.6, .1, .2))
    for name, solid in volumes.items():
        assert solid.isValid(), name
    intersections = []
    for i, (name, solid) in enumerate(volumes.items()):
        for other, second in list(volumes.items())[i+1:]:
            intersections.append({'a': name, 'b': other,
                                  'intersection_mm3': round(solid.intersect(second).Volume(), 6)})
    out = ROOT / 'generated'
    assembly.export(str(out / '1590xx-reference-fit.step'))
    cq.exporters.export(pcb, str(out / '1590xx-pcb-candidate.step'))
    # Transfer exact outer wire geometry, without reinterpreting notch angles.
    # Through holes belong to KiCad pads rather than Edge.Cuts circles.
    face = max((face for face in pcb.Faces() if face.normalAt().z > .99), key=lambda face: face.Area())
    curves = []
    for edge in face.outerWire().Edges():
        kind = edge.geomType()
        if kind not in ('LINE', 'CIRCLE'):
            raise ValueError(f'Unsupported PCB edge: {kind}')
        def xy(vector):
            return [round(vector.x, 8), round(vector.y, 8)]
        curves.append({'kind': kind, 'start': xy(edge.startPoint()),
                       'mid': xy(edge.positionAt(.5)), 'end': xy(edge.endPoint())})
    (out / '1590xx-pcb-outline.json').write_text(json.dumps({'curves': curves}, indent=2)+'\n')
    uncut_clashes = [{'a': name, 'b': 'uncut_rectangular_pcb',
                     'intersection_mm3': round(solid.intersect(rectangular.val()).Volume(), 6)}
                    for name, solid in volumes.items() if name != 'candidate_notched_pcb']
    report = {'status': config['status'], 'vendor_step_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'jack_step_sha256': hashlib.sha256(jack_path.read_bytes()).hexdigest(),
              'jack_axis_z': axis_z,
              'solids_valid': True, 'intersections': intersections,
              'uncut_rectangular_comparison': uncut_clashes,
              'candidate_pcb_area_mm2': round(pcb.Volume()/b['thickness'], 3),
              'limits': ['Casting has nominal jack holes only: no screen aperture, switch or other connector holes.',
                         'Display and switches are envelopes, not complete qualified mechanical models.',
                         'Candidate outline is available for provisional electrical placement, not manufacturing approval.',
                         'Jack ferrules/nuts, contacts, assembly tolerances and electrical footprint orientation remain unqualified.',
                         'Capacitors are maximum body envelopes; reflow/service clearance is unqualified.',
                         'Other connectors, FPC bends, supports and assembly access are not modeled here.']}
    (out / '1590xx-fit-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
