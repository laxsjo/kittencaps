#!/usr/bin/env python

from typing import *
import json5
import argparse
import pathlib
import re
import xml.etree.ElementTree as ET

from .lib import project, svg
from .lib.svg_builder import *
from .lib.keyboard_builder import build_keyboard_svg, create_keycap_mask
from .lib.theme import *
from .lib.utils import *
from .lib.generation_metadata import *

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
        help="Write the generated files to this directory."
    )
    
    args = parser.parse_args()
    
    
    layout_path: pathlib.Path = args.layout
    theme_path: pathlib.Path = args.theme
    template_path: pathlib.Path = args.templates
    out: pathlib.Path = args.out

    metadata = GenerationMetadata(
        layout_path=layout_path,
        theme_path=theme_path
    )

    theme = metadata.load_theme()
    layout = metadata.load_layout()

    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))

    result = build_keyboard_svg(layout, theme, key_templates)
    
    out.mkdir(parents=True, exist_ok=True)
    
    with open(out / "preview.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    # Remove shading effect
    match tree_get_id(result, "sideShading"):
        case None:
            panic("Tree did not have id ")
        case shading_filter:
            shading_filter[:] = []
    
    # Make keycap masks cover entire 1u square
    masks = filter(
        lambda element: \
            re.match(r"^[0-9]+(\.[0-9]+)?u-base$", element.attrib.get("id", "")),
        result.findall(".//mask")
    )
    theme.base_size = theme.unit_size
    for mask in masks:
        size_u = mask.attrib["id"].removesuffix("-base")
        new_mask = create_keycap_mask(size_u, theme)
        mask[:] = new_mask[:]
    
    with open(out / "texture.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    svg.render_many_files_as_png((
        (out / "preview.svg", out / "preview.png"),
        (out / "texture.svg", out / "texture.png"),
    ))
    
    metadata.store_at(out / "metadata.json5")

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
