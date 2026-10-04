#!/usr/bin/env python3
"""Apply guarded FPGA configuration/clock/audio support placement."""
from place_fpga_bypass import main

if __name__ == '__main__':
    main('fpga-support-placement.json', 'provisional_fpga_support_references')
