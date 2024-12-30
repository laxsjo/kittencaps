#!/usr/bin/env python

from typing import *
import json5
import argparse
import pathlib
import xml.etree.ElementTree as ET
import damsenviet.kle as kle

from .lib import project, svg
from .lib.svg_builder import *
from .lib.keyboard_builder import build_keyboard_svg
from .lib.theme import *
from .lib.utils import *

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble the keycap set images using a specific keymap and theme.",
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
        metavar="DIRECTORY",
        type=pathlib.Path,
        required=True,
        help="Write the generated images to this directory."
    )
    
    args = parser.parse_args()
    
    
    layout_path: pathlib.Path = args.layout
    theme_path: pathlib.Path = args.theme
    template_path: pathlib.Path = args.templates
    out: pathlib.Path = args.out

    theme = Theme.load_file(theme_path)

    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))
        
    with open(layout_path, "r") as file:
        layout = kle.Keyboard.from_json(
            json5.load(file)
        )

    result = build_keyboard_svg(layout, theme, key_templates)
    
    out.mkdir(parents=True, exist_ok=True)
    
    with open(out / "preview.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    png_blob = svg.convert_tree_to_png(result)
    (out / "preview.png").write_bytes(png_blob)
    
    # Remove filter effect
    match tree_get_id(result, "sideShading"):
        case None:
            panic("Tree did not have id ")
        case shading_filter:
            shading_filter[:] = []
    
    with open(out / "texture.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    png_blob = svg.convert_tree_to_png(result)
    (out / "texture.png").write_bytes(png_blob)

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
