#!/usr/bin/env python3
"""Check exported FPGA rail topology and conditional regulator/sequencer corners.

This review does not validate ramps, stability, shutdown or hardware operation.
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

    def rating(ref):
        return parts[ref].find("fields").find("field[@name='Rating']").text

    assert parts["U301"].findtext("value") == "TLV62569DBVR"
    assert parts["U302"].findtext("value") == "TPS3897ADRYR"
    assert parts["U303"].findtext("value") == "TPS22965DSGR"
    same(("U301", "1"), ("U301", "4"), ("L101", "2"), ("C301", "1"),
         ("U303", "4"), ("C308", "1"))
    same(("U301", "3"), ("L301", "1"))
    same(("L301", "2"), ("C302", "1"), ("C303", "1"),
         ("R301", "1"), ("C304", "1"), ("R303", "1"))
    same(("U301", "5"), ("R301", "2"), ("R302", "1"), ("C304", "2"))
    same(("U302", "1"), ("U302", "6"), ("L102", "2"), ("R305", "1"),
         ("C306", "1"), ("U303", "1"), ("U303", "2"), ("C307", "1"))
    same(("U302", "3"), ("R303", "2"), ("R304", "1"), ("C305", "1"))
    same(("U302", "4"), ("U303", "3"), ("R305", "2"), ("R306", "1"))
    same(("U302", "5"), ("C311", "1"))
    same(("U303", "6"), ("C309", "1"))
    same(("U303", "7"), ("U303", "8"), ("C310", "1"))
    same(("U301", "2"), ("U302", "2"), ("U303", "5"), ("U303", "9"),
         ("R302", "2"), ("R304", "2"), ("R306", "2"),
         *((f"C{n}", "2") for n in (301,302,303,305,306,307,308,309,310,311)))
    assert len({nets[p] for p in (("L301","2"),("L102","2"),("U303","7"),
                                  ("U202","20"))}) == 4, "core, main, FPGA IO and held DAC rails distinct"
    for ref, text in (("R301","68.1k / 0.1%"),("R302","100k / 0.1%"),
                      ("R303","9.31k / 0.1%"),("R304","10k / 0.1%"),
                      ("R305","10k / 1%"),("R306","10k / 1%"),
                      ("C309","470pF / 25V C0G"),("C311","4.7nF / 5% / 25V C0G")):
        assert rating(ref) == text, ref
    assert parts["L301"].findtext("value") == "2.2uH"
    for ref in ("C302", "C303"):
        assert rating(ref) == "22uF / 16V X7R"

    # TI TLV62569 VFB limits: VIN=5 V, TJ=25 C unless otherwise noted.
    core = [vfb * (1 + top / bottom)
            for vfb, top, bottom in itertools.product(
                (.588, .612), (68100*.999,68100*1.001),
                (100000*.999,100000*1.001))]
    assert .95 < min(core) < max(core) < 1.05
    # TPS3897 positive-going threshold, full-temperature limits and +/-15 nA.
    release = [vit * (1 + top / bottom) + bias * top
               for vit, top, bottom, bias in itertools.product(
                   (.495,.505), (9310*.999,9310*1.001),
                   (10000*.999,10000*1.001), (-15e-9,15e-9))]
    assert min(release) > .95
    assert max(release) < min(core)
    # External CT charging interval only; excludes internal overhead, leakage,
    # filter settling and parasitics. This is not a guaranteed total delay bound.
    delay = [cap * vct / current
             for cap, vct, current in itertools.product(
                 (4.7e-9*.95,4.7e-9*1.05), (1.18,1.299), (260e-9,360e-9))]
    # Chosen core qualification allocation; distinct from Gowin's rail ramp time.
    assert min(delay) > .010
    # Main 3.3-V window, equal 10k +/-1%, supervisor + ON leakage allowance.
    high = [vdd * lower/(upper+lower) - .8e-6 * upper*lower/(upper+lower)
            for vdd, upper, lower in itertools.product(
                (3.135,3.465), (9900,10100), (9900,10100))]
    assert min(high) > 1.1  # TPS22965 ON guaranteed high input level.
    low_below_por = .8 * 10100 / (9900+10100) + .5e-6*5000
    assert low_below_por < .5
    report = {
        "status": "conditional engineering review; not hardware validation",
        "connectivity_checked": True,
        "core_nominal_v": .6 * (1 + 68100/100000),
        "core_dc_corners_v": [min(core),max(core)],
        "core_vfb_test_condition": "VIN=5 V, TJ=25 C; line/load/temperature/ripple still to verify",
        "sequencer_rising_threshold_v": [min(release),max(release)],
        "core_to_release_dc_margin_v": min(core)-max(release),
        "ct_nominal_delay_s": 4.7e-3*4 + 40e-6,
        "ct_external_charge_interval_corners_s": [min(delay),max(delay)],
        "ct_delay_caveat": "Component-limit calculation, not guaranteed total propagation-delay bounds",
        "ct_charge_minimum_allocation_s": .010,
        "gowin_power_guidance": "UG206-1.9.3E: 0.1–10 ms reference rail rise; core first above 10 ms; VCCX always >= VCCIO",
        "io_enable_high_min_v": min(high),
        "io_enable_below_por_allocated_max_v": low_below_por,
        "io_switch_typical_rise_s": .000654,
        "falling_hysteresis_v_typical": .005,
        "falling_hysteresis_limits_unspecified": True,
        "remaining_checks": [
            "Select core inductor MPN/footprint, capacitor MPNs and verify bias/fault/thermal margins",
            "Complete load budget; validate regulator loop/ripple/transients and sequencer ramps",
            "Verify low-supply startup/shutdown, switch bias relationship, brownout and MCU/JTAG backfeed",
            "Validate bare FPGA per-pin bypass, PLL isolation, switched configuration flash and oscillator",
            "Check supervisor/layout/stencil and use hardware tests for sequence and operating margins",
        ],
    }
    path = ROOT / "generated/fpga-power-review.json"
    path.write_text(json.dumps(report,indent=2)+"\n")
    print(f"PASS: FPGA rail nets; conditional core {min(core):.4f}–{max(core):.4f} V")
    print(f"Rising release {min(release):.4f}–{max(release):.4f} V; CT charge {min(delay)*1000:.2f}–{max(delay)*1000:.2f} ms")
    print(path)


if __name__ == "__main__":
    review()
