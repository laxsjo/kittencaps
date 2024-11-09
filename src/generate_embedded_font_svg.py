#!/usr/bin/env python

from __future__ import annotations
from typing import *
import pathlib
import sys
import argparse
import xml.etree.ElementTree as ET

from fontTools import ttLib

from .lib.utils import *
from .lib import font as Font
from .lib.svg_builder import *
from .lib.keyboard_builder import create_text_icon_svg
from .lib.pos import *
from .lib.theme import *
from .lib.color import *
from .lib import project

def generate_svg(font_paths: list[pathlib.Path], theme: Theme, out_file: TextIO) -> None:
    font = Font.FontDefinition(font_paths[0])
    font_rules = (Font.generate_css_rule(Font.FontDefinition(path)) for path in font_paths)
    
    builder = SvgDocumentBuilder()\
        .set_viewbox(ViewBox(Pos(0, 0), Scaling(100, 100)))\
        .palette(theme.colors)
    
    style = SvgStyleBuilder()\
        .attributes({
            "id": "font_style",
        })\
        .statement(*font_rules)\
        .indentation(1, "  ")\
        .build()

    builder.add_element(style)
    
    icon = create_text_icon_svg("_", "", font, theme.font_size_px)

    builder.add_element(icon.element)
    
    tree = builder.build()
    tree.write(out_file, encoding="unicode", xml_declaration=True)

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an empty SVG with the given font embedded.")

    parser.add_argument(
        "--font",
        metavar="FILE",
        type=pathlib.Path,
        action='append',
        required=True,
        help="Font file to embed into the SVG. Multiple may be specified. Family name and weight is queried using `fc-query`.",
    )
    parser.add_argument(
        "--theme",
        metavar="THEME",
        type=pathlib.Path,
        default=project.path_to_absolute("assets/themes/standard.json"),
        help="Path to a JSON file describing the fonts and colors to use in the generated SVG. Must follow the schema 'assets/themes/theme-schema.json'. (Note that this is only useful to set when editing the individual icon. The theme information is stripped out when it's inserted into the full keycap set SVG.)",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="The filepath to save the generated SVG to. If not given, output to stdout.",
    )

    args = parser.parse_args()

    fonts = args.font
    
    theme_path = args.theme
    theme = Theme.load_file(theme_path)

    out: pathlib.Path | None = args.out

    if out == None:
        generate_svg(fonts, theme, sys.stdout)
    else:
        with open(out, "w") as out_file:
            generate_svg(fonts, theme, out_file)

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
