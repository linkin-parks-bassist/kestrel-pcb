#!/usr/bin/env python3
"""Check exported mute connectivity and conditional hold-up design corners.

This is schematic/design evidence, not a physical power-loss or pop-free test.
Run after exporting the integrated project as KiCad XML.
"""
import itertools
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def review():
    tree = ET.parse(ROOT / "generated/revb-netlist.xml").getroot()
    nets = {(pin.get("ref"), pin.get("pin")): net.get("name")
            for net in tree.find("nets") for pin in net.findall("node")}
    components = {part.get("ref"): part for part in tree.find("components")}

    def same(*pins):
        assert len({nets[pin] for pin in pins}) == 1, pins

    # Hardware-strapped I2S slave ADC; DAC is a slave using its BCLK PLL.
    for pin, resistor in (("10", "R203"), ("11", "R204"), ("12", "R202")):
        same(("U201", pin), (resistor, "1"))
        same((resistor, "2"), ("U201", "2"))
        assert components[resistor].findtext("value") == "10k"
    same(("U201", "8"), ("U202", "13"))  # FPGA BCLK input.
    same(("U201", "7"), ("U202", "15"))  # FPGA LRCLK input.
    same(("U202", "12"), ("U202", "19"))  # SCK grounded for BCLK PLL.
    assert nets["U201", "6"].endswith("AUDIO_MCLK")

    same(("D204", "2"), ("R217", "1"), ("L101", "2"))
    same(("D204", "1"), ("C230", "1"), ("U205", "1"), ("U205", "3"))
    same(("C230", "1"), ("C235", "1"))
    same(("C230", "2"), ("C235", "2"), ("U205", "2"))
    same(("U205", "5"), ("U202", "1"), ("U202", "8"), ("U202", "20"),
         ("U202", "11"), ("U206", "6"), ("U207", "6"), ("R220", "1"))
    same(("U206", "1"), ("U207", "1"), ("U202", "17"), ("R220", "2"), ("R205", "1"))
    same(("U206", "3"), ("U207", "3"), ("R219", "1"))
    same(("U204", "1"), ("R215", "1"), ("U201", "3"))
    same(("U206", "5"), ("R215", "2"), ("R216", "1"), ("C231", "1"))
    same(("U207", "5"), ("R217", "2"), ("R218", "1"), ("C232", "1"))
    same(("U206", "2"), ("U207", "2"), ("R219", "2"), ("R205", "2"),
         ("C230", "2"), ("U202", "19"))
    assert nets["U201", "4"] != nets["U202", "20"], "DAC must not feed main digital domain"
    for ref in ("U206", "U207"):
        assert nets[ref, "4"].startswith("unconnected-"), "CT open sets fixed release delay"
        assert components[ref].findtext("value") == "TPS3808G01DBVR"
    for ref in ("R215", "R217"):
        assert components[ref].findtext("value") == "105k 0.1%"
    for ref in ("R216", "R218"):
        assert components[ref].findtext("value") == "10k 0.1%"
    assert components["R219"].findtext("value") == "1k"
    assert components["R220"].findtext("value") == "10k"
    for ref in ("C230", "C235"):
        assert components[ref].findtext("value") == "1000uF EEEFK1A102P"
        assert components[ref].findtext("footprint") == "KestrelAudio:CP_Elec_Panasonic_FK_G_10x10.2"

    # TI TPS3808 G01 full-temperature threshold accuracy +/-2%, SENSE +/-25 nA.
    thresholds = [vit * (1 + top / bottom) + bias * top
                  for vit, top, bottom, bias in itertools.product(
                      (.405 * .98, .405 * 1.02),
                      (105000 * .999, 105000 * 1.001),
                      (10000 * .999, 10000 * 1.001), (-25e-9, 25e-9))]
    low, high = min(thresholds), max(thresholds)
    release_high = high * 1.03  # Conservative maximum hysteresis on whole threshold.
    assumptions = {
        "sample_rate_hz": 48000,
        "reservoir_min_f": 2 * .001 * .8,
        # Previous 60-mA allocation plus 5 mA for U504, MR pulldown load
        # and added buffer bypass/leakage. Actual rail load still needs testing.
        "held_load_a": .065,
        "diode_drop_v": .5,
        "reservoir_esr_ohm": .1,
        "ldo_input_min_v": 3.6,
        "additional_detection_allowance_s": .0001,
        "temperature_leakage_and_load_budget_not_yet_verified": True,
    }
    start = low - assumptions["diode_drop_v"] - assumptions["held_load_a"] * assumptions["reservoir_esr_ohm"]
    hold = assumptions["reservoir_min_f"] * (start - assumptions["ldo_input_min_v"]) / assumptions["held_load_a"]
    required = 150 / assumptions["sample_rate_hz"] + .0002
    assert hold > required + assumptions["additional_detection_allowance_s"]
    # Panasonic FK endurance permits -30% relative to the initial value,
    # measured after stabilization at +20 C. This is an aged room-temp case,
    # not a temperature qualification or a guaranteed transient ESR limit.
    aged_min_f = assumptions["reservoir_min_f"] * .7
    aged_hold = aged_min_f * (start - assumptions["ldo_input_min_v"]) / assumptions["held_load_a"]
    assert aged_hold > required + assumptions["additional_detection_allowance_s"]
    # Extra conservative sensitivity case: apply a further 10% capacitance
    # reduction, allow 70 mA load, 0.6 V diode drop and 0.4 ohm total pulse
    # impedance. These are allocations to verify, not manufacturer bounds.
    stress_f = aged_min_f * .9
    stress_hold = stress_f * (low - .6 - .070 * .4 - 3.6) / .070
    assert stress_hold > required + assumptions["additional_detection_allowance_s"]
    # Both internal MR pullups are >=70k; external 1k has +/-1% allowance.
    mr_low = 3.333 * 1010 / (35000 + 1010)
    assert mr_low < .3 * 3.267
    report = {
        "status": "conditional engineering calculation; not hardware validation",
        "connectivity_checked": True,
        "trip_min_v": low, "trip_max_v": high, "release_upper_bound_v": release_high,
        "hold_up_s": hold, "required_mute_s": required,
        "remaining_margin_s": hold - required - assumptions["additional_detection_allowance_s"],
        "aged_room_temperature_min_f": aged_min_f,
        "aged_room_temperature_hold_s": aged_hold,
        "aged_room_temperature_margin_s": aged_hold - required - assumptions["additional_detection_allowance_s"],
        "extra_sensitivity_case": {
            "conditional_only": True, "reservoir_f": stress_f,
            "held_load_a": .070, "diode_drop_v": .6,
            "total_reservoir_pulse_impedance_ohm": .4,
            "hold_s": stress_hold,
            "margin_s": stress_hold - required - assumptions["additional_detection_allowance_s"],
        },
        "mr_default_low_v_without_fpga_drive": mr_low,
        "release_delay_s_range": [.012, .028],
        "assumptions": assumptions,
        "remaining_checks": [
            "Verify selected capacitor pulse impedance, capacitance/leakage over temperature, reflow and life",
            "Verify diode forward drop/leakage, LDO behavior, DAC load and startup inrush",
            "Verify FPGA GPIO boot state, current/logic levels and AUDIO_ENABLE sequencing",
            "Measure rail removal/brownout/shutdown, including supervisor timing and audio output",
        ],
    }
    path = ROOT / "generated/audio-mute-review.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: mute nets; conditional hold {hold*1000:.3f} ms / required {required*1000:.3f} ms")
    print(path)


if __name__ == "__main__":
    review()
