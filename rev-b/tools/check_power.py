#!/usr/bin/env python3
"""Review exported buck connectivity and conditional DC/loop calculations.

This is engineering evidence; it does not certify rail capacity or stability.
"""
import itertools
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def review():
    tree = ET.parse(ROOT / "generated/revb-netlist.xml").getroot()
    nets = {(p.get("ref"), p.get("pin")): net.get("name")
            for net in tree.find("nets") for p in net.findall("node")}
    parts = {p.get("ref"): p for p in tree.find("components")}

    def same(*pins):
        assert len({nets[p] for p in pins}) == 1, pins

    for u, l, boot, upper, lower, series, cff, en_top, en_bottom, caps in (
        ("U101", "L101", "C103", "R102", "R103", "R101", "C106", "R104", "R105", ("C104", "C105")),
        ("U102", "L102", "C109", "R107", "R108", "R106", "C112", "R109", "R110", ("C110", "C111", "C113")),
    ):
        assert parts[u].findtext("value") == "TPS54302DDCR"
        same((u, "6"), (boot, "1"))
        same((u, "2"), (boot, "2"), (l, "1"))
        same((u, "3"), (en_top, "1"), ("U204", "4"))
        same((u, "1"), (lower, "2"), (en_bottom, "2"), ("U201", "2"))
        same((u, "5"), (en_top, "2"), (en_bottom, "1"))
        same((u, "4"), (upper, "2"), (lower, "1"), (cff, "2"))
        same((upper, "1"), (series, "2"), (cff, "1"))
        same((l, "2"), (series, "1"), *((c, "1") for c in caps))
        same((u, "1"), *((c, "2") for c in caps))
        assert nets[(boot, "1")] != nets[(u, "1")]
        assert nets[(u, "2")] != nets[(l, "2")]
    same(("L102", "2"), ("U201", "4"), ("C206", "1"), ("C207", "1"))
    assert nets[("L101", "2")] != nets[("L102", "2")]
    assert nets[("U101", "2")] != nets[("U102", "2")]
    assert nets[("U101", "4")] != nets[("U102", "4")]
    assert nets[("L102", "2")] != nets[("U202", "20")]
    assert parts["R107"].findtext("value") == "100k"
    assert parts["R108"].findtext("value") == "22.1k"
    for ref, rating in (("R107", "100k / 0.1%"), ("R108", "22.1k / 0.1%"), ("R106", "49.9 / 1%")):
        assert parts[ref].find("fields").find("field[@name='Rating']").text == rating
    # VFB min/max are TI's VIN=12-V test-condition limits. Series feedback
    # resistor participates in the DC divider, but not the Cff parallel pair.
    corners = [vfb * (1 + (top + series) / bottom)
               for vfb, top, bottom, series in itertools.product(
                   (.581, .611), (100000*.999, 100000*1.001),
                   (22100*.999, 22100*1.001), (49.9*.99, 49.9*1.01))]
    nominal = .596 * (1 + (100000 + 49.9) / 22100)
    assert min(corners) > 3.135 and max(corners) < 3.465
    min_effective_cap = 40e-6  # Allocation, pending selected capacitor curves.
    estimated_crossover = 5.1 / (min(corners) * min_effective_cap)
    assert estimated_crossover < 40000
    report = {
        "status": "conditional engineering review; not hardware validation",
        "connectivity_checked": True,
        "digital_3v3_nominal_v": nominal,
        "digital_3v3_dc_corners_v": [min(corners), max(corners)],
        "vfb_limits_test_condition": "TI VIN=12 V; input/line/load/transients still to verify",
        "digital_feedback_resistor_tolerance": .001,
        "digital_output_nominal_cap_f": 3 * 22e-6,
        "required_effective_cap_allocation_f": min_effective_cap,
        "estimated_crossover_upper_hz": estimated_crossover,
        "remaining_checks": [
            "Select inductor MPN/footprint and verify DC-bias/fault-current and thermal margins",
            "Select ceramic capacitor MPNs and verify effective capacitance, ageing and temperature",
            "Derive actual rail loads and validate ripple, transients, startup, noise and loop phase margin",
            "Validate input protection and fixed FPGA core/IO circuit; qualify connected separate MCU HP rail and onboard backlight boost",
        ],
    }
    path = ROOT / "generated/power-review.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: independent buck nets; 3.3-V DC corners {min(corners):.4f}–{max(corners):.4f} V")
    print(path)


if __name__ == "__main__":
    review()
