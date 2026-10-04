#!/usr/bin/env python3
"""Apply guarded partial MCU support placement using system KiCad Python."""
from place_fpga_bypass import main

if __name__ == '__main__':
    main('mcu-support-placement.json', 'provisional_mcu_support_references')
