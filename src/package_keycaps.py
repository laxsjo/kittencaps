#!/usr/bin/env python

from typing import *
import sys
import json5
import argparse
import pathlib
import xml.etree.ElementTree as ET
import damsenviet.kle as kle

from .lib import project
from .lib.svg_builder import *
from .lib.keyboard_builder import build_keyboard_svg
from .lib.theme import *

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an SVG from a keymap and theme",
    )
    parser.add_argument(
        "layout",
        metavar="LAYOUT",
        type=pathlib.Path,
        help="Path to a json file containing a KLE layout definition."
    )
    parser.add_argument(
        "--theme",
        metavar="THEME",
        type=pathlib.Path,
        default=project.path_to_absolute("assets/themes/standard.json"),
        help="Path to a JSON file describing the fonts and colors to use in the generated SVG. Must follow the schema 'assets/themes/theme-schema.json'.",
    )
    parser.add_argument(
        "--templates",
        metavar="KEYCAP_TEMPLATES",
        type=pathlib.Path,
        default=project.path_to_absolute("assets/templates/frame-templates.svg"),
        help="Path to an SVG containing the keycap frame template symbols.",
    )
    parser.add_argument(
        "--out",
        metavar="PATH",
        type=pathlib.Path,
        default=None,
        help="Write the generated file to this path. If not given write to stdout."
    )
    
    args = parser.parse_args()
    
    
    layout_path: pathlib.Path = args.layout
    theme_path: pathlib.Path = args.theme
    template_path: pathlib.Path = args.templates
    out: pathlib.Path | None = args.out

    theme = Theme.load_file(theme_path)

    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))
        
    with open(layout_path, "r") as file:
        layout = kle.Keyboard.from_json(
            json5.load(file)
        )

    # Magic Number: Size of single keycap in pixels
    unit_px = 50

    result = build_keyboard_svg(layout, unit_px, theme, key_templates)
    
    with open(out, "w") if out != None else sys.stdout as file:
        result.write(file, encoding="unicode", xml_declaration=True)

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
