#!/usr/bin/env python3
"""Apply guarded provisional P4 HP regulator passive placement."""
from place_fpga_bypass import main

if __name__ == '__main__':
    main('mcu-hp-placement.json', 'provisional_mcu_hp_references')
