#!/usr/bin/env python

from __future__ import annotations
from typing import *
import pathlib
import sys
import argparse
import xml.etree.ElementTree as ET
from decimal import Decimal

# from fontTools import ttLib

from .lib.utils import *
# from .lib import font as Font
# from .lib.svg_builder import *
# from .lib.keyboard_builder import *
# from .lib.pos import *
# from .lib.theme import *
# from .lib.color import *
from .lib.error import *
from .lib.font import *

def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate the baseline offset from the top of a box with given height, such that the character 'H' is visually centered.")

    parser.add_argument(
        "--height",
        metavar="SIZE",
        type=int,
        required=True,
        help="The height of the box within which the text should be centered. In arbitrary units.",
    )
    parser.add_argument(
        "--font-size",
        metavar="SIZE",
        type=int,
        required=True,
        help="The font size in the same units as total-size.",
    )
    parser.add_argument(
        "--family",
        metavar="FAMILY",
        required=True,
        help="Name of the font family to render H with when centering. Is expected to be installed on your system.",
    )
    parser.add_argument(
        "--weight",
        metavar="WEIGHT",
        default=None,
        help="The font weight to render H with when centering. By default 400 is chosen, or if not installed, the first found weight.",
    )

    args = parser.parse_args()
    
    height= Decimal(args.height)
    font_size = Decimal(args.font_size)
    font_family: str = args.family
    font_weight_arg: str|None = args.weight
    
    match get_system_family(font_family):
        case Ok(available_fonts):
            pass
        case Error(_):
            panic(f"'{font_family}' is not installed on your system")
    
    font_weight = font_weight_arg if font_weight_arg is not None else "400" 
    
    font = next(
        (font for font in available_fonts if font.weight == font_weight),
        None
    )
    if font == None:
        if font_weight_arg == None:
            font = available_fonts[0]
        else:
            # TODO: Variable fonts are not supported.
            panic(f"There is no font with weight {font_weight} installed for the family '{font_family}'")
    
    centered_pos = height / 2 + (font_size * font.metrics.cap_center_offset())
    print(centered_pos)

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
