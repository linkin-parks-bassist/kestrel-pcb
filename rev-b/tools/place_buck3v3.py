#!/usr/bin/env python3
"""Apply guarded provisional 3.3 V buck support placement."""
from place_fpga_bypass import main
if __name__ == '__main__': main('buck3v3-placement.json', 'provisional_buck3v3_references')
