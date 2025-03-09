#!/usr/bin/env python

from __future__ import annotations
from typing import *
import pathlib
import sys
import argparse
import xml.etree.ElementTree as ET
import re

from fontTools import ttLib

from .lib.utils import *
from .lib import font as Font
from .lib.svg_builder import *
from .lib import svg
from .lib.keyboard_builder import *
from .lib.pos import *
from .lib.theme import *
from .lib.color import *
from .lib import project
from .lib.error import *

def parse_size(size: str) -> Ok[Vec2]|Error[str]:
    if not size.endswith("u"):
        return Error(f"The given keycap size '{size}' is not valid: it must be suffixed with a 'u'.")
    
    size = size.removesuffix("u")
    if len(size) == 0:
        return Error(f"The given keycap size '{size}' is not valid: no size was given.")
    
    
    components = size.split("x")
    try:
        components = tuple(map(float, components))
    except ValueError:
        return Error(f"The given keycap size '{size}' does not contain valid numbers.")
    
    # The zero check is to make type inference happy :)
    if len(components) > 2 or len(components) == 0:
        return Error(f"The given keycap size '{size}' is not valid: you can not specify more than two dimensions.")
    
    if len(components) == 1:
        components += (1.0,)
    
    if components[0] != 1 and components[1] != 1:
        return Error(f"The given keycap size '{size}' is not valid: neither of it's dimensions are 1u.")
    
    return Ok(Vec2(*components))

def generate_svg(size: Vec2, bg_color: str|None, margin: float, font_paths: list[pathlib.Path], theme: Theme, templates: SvgSymbolSet, out_file: TextIO) -> None:
    font = Font.FontDefinition(font_paths[0])
    font_rules = (Font.generate_css_rule(Font.FontDefinition(path)) for path in font_paths)
    
    builder = SvgDocumentBuilder()\
        .set_viewbox(svg.ViewBox(Vec2(-margin, -margin), (size * 100 + Vec2.promote_float(margin * 2)).as_scaling()))\
        .palette(theme.colors)
    
    style = SvgStyleBuilder()\
        .attributes({
            "id": "font_style",
        })\
        .statement(*font_rules)\
        .indentation(1, "  ")\
        .build()

    builder.add_element(style)
        
    key_size = KeycapGeometry.from_dimensions(size)
    if key_size == None:
        panic(f"Icon was not 1u in either width or height, given key dimensions: ({size.x}, {size.y})")
    
    center_pos = Vec2(50, 50) * size
    surface_scaling = Scaling(theme.top_size / theme.unit_size)
    match key_size.orientation:
        case Orientation.HORIZONTAL:
            surface_rotation = Rotation(0)
        case Orientation.VERTICAL:
            surface_rotation = Rotation(90)
            
    surface_id = f"_{key_size.size_u()}-top"
    # A surface symbol is assumed to have a "-50 -50 100 100" viewbox
    surface_symbol = templates[surface_id]
    if isinstance(surface_symbol, Error):
        panic(f"Given icon size did not have a corresponding entry in the templates file: could not find symbol element with id '{surface_id}'.")
    surface_path = surface_symbol.source.element.find(".//path")
    if surface_path == None:
        panic(f"Found symbol with id {surface_id} did not have required path child element")
    element_apply_transform(surface_path, Transform(
        translate=center_pos,
        scale=surface_scaling,
        rotate=surface_rotation,
    ))
    surface_path.set("stroke", "black")
    surface_path.set("stroke-opacity", "0.5")
    surface_path.set("fill", "none")
    surface_path.set("style", "pointer-events: none;")
    svg.remove_css_properties(surface_path, {"fill"})
    try:
        del surface_path.attrib["class"]
    except:
        pass
    element_add_label(surface_path, "Outline")
    
    bounds_rect = make_element("rect", {
        "width": number_to_str(size.x * 100),
        "height": number_to_str(size.y * 100),
        "fill": "none",
        "stroke": "black",
        "stroke-opacity": "0.5",
        # This approximates the correct width given the standard themes top size
        # TODO: This is very ugly, should instead apply the transform of the top
        #       surface path, so that its stroke width isn't scaled.
        "stroke-width": "0.65",
        "style": "pointer-events: none;",
    })
    element_add_label(bounds_rect, "Bounds")
    
    # Margin adjusted to match if unit_size was 100 px. 
    
    bg_element = make_element("rect", {
        "class": "icon-bg",
        "x": number_to_str(-margin) if margin != 0 else None,
        "y": number_to_str(-margin) if margin != 0 else None,
        "width": number_to_str(size.x * 100 + margin * 2),
        "height": number_to_str(size.y * 100 + margin * 2),
        "fill": f"url(#{bg_color or "bg_main"})",
    })
    if bg_color is None:
        bg_element.set("visibility", "hidden")
    element_add_label(bg_element, "BG")
    
    icon = create_text_icon_svg("_", "", size, font, theme.font_size_px, None)
    
    builder.add_element(bg_element)
    builder.add_element(icon.element)
    builder.add_element(surface_path)
    builder.add_element(bounds_rect)
    
    tree = builder.build()
    tree.write(out_file, encoding="unicode", xml_declaration=True)

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an empty SVG with the given font embedded.")

    parser.add_argument(
        "--size",
        metavar="SIZE",
        required=True,
        help="The size of the keycap in u. You may specify a width and height separated by an 'x', which allows you to create a vertical keycap. If not the height is assumed to be 1. One of the lengths must be equal to 1. Ex: 1u, 1x1.5u",
    )
    parser.add_argument(
        "--bg-color",
        metavar="COLOR",
        default="",
        help="The background color of the keycap. The value must be a valid name present in the theme, or an empty string. The created element is set to hidden if empty or not given. It's purely to help while designing and is removed before the icon is inserted into the assembled keymap.",
    )
    parser.add_argument(
        "--margin",
        metavar="COLOR",
        type=float,
        default=0,
        help="Margin to extend the icon viewbox in pixels. Assuming a 1u keycap, setting a margin of 100 would make the generated SVG 300 pixels wide.  Changing this setting produces no difference in how the placed icon appears, unless `iconMargin` is configured for the given layout.",
    )
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
        "--templates",
        metavar="KEYCAP_TEMPLATES",
        type=pathlib.Path,
        default=project.path_to_absolute("assets/templates/frame-templates.svg"),
        help="Path to an SVG file with TODO: figure out semantics of frame-templates.svg",
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=None,
        help="The filepath to save the generated SVG to. If not given, output to stdout.",
    )

    args = parser.parse_args()

    match parse_size(args.size):
        case Ok(size):
            size = size
        case Error(msg):
            panic(msg)
    
    fonts = args.font
    
    theme_path = args.theme
    theme = Theme.load_file(theme_path)
    template_path = args.templates
    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))
    
    bg_color = cast(str, args.bg_color)
    if bg_color == "":
        bg_color = None
    elif bg_color not in theme.colors:
        panic(f"The specified background color '{bg_color}' could not be found in the theme.")
    
    margin: float = args.margin
    
    out: pathlib.Path | None = args.out

    if out == None:
        generate_svg(size, bg_color, margin, fonts, theme, key_templates, sys.stdout)
    else:
        with open(out, "w") as out_file:
            generate_svg(size, bg_color, margin, fonts, theme, key_templates, out_file)

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
