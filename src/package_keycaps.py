#!/usr/bin/env python

from typing import *
import json5
import argparse
import pathlib
from pathlib import Path
import itertools
import subprocess
import re
import xml.etree.ElementTree as ET

from .lib import project
from .lib.svg_builder import *
from .lib import svg
from .lib.keyboard_builder import build_keyboard_svg, create_keycap_mask
from .lib.theme import *
from .lib.utils import *
from .lib.error import *
from .lib.color import *
from .lib.generation_metadata import *

def normalize_keyboard_for_texture(keyboard: svg.MaybeElementTree, theme: Theme) -> None:
    keyboard = svg.resolve_element_tree(keyboard)
    view_box_str = keyboard.attrib.get("viewBox", None)
    if view_box_str == None:
        panic(f"Expected svg element {keyboard} to have a view box")
    match svg.ViewBox.parse_svg_value(view_box_str):
        case Ok(view_box):
            pass
        case Error(msg):
            panic(f"Expected svg element {keyboard}'s view box '{view_box_str}': {msg}")
    
    # Remove elements responsible for the shading effect
    svg.tree_remove_by(
        keyboard,
        lambda element: element.attrib.get("filter") == "url(#sideShading)",
    )
    
    # Make keycap masks cover entire 1u square
    masks = filter(
        lambda element: \
            re.match(r"^_[0-9]+(\.[0-9]+)?u-base$", element.attrib.get("id", "")),
        keyboard.findall(".//mask")
    )
    theme.base_size = theme.unit_size + theme.icon_margin * 2
    for mask in masks:
        size_u = mask.attrib["id"].removeprefix("_").removesuffix("-base")
        new_mask = create_keycap_mask(size_u, theme)
        # Replace the mask's children
        mask[:] = new_mask[:]
    
    # Remove all elements with visibility: hidden
    def is_hidden(element: ET.Element) -> bool:
        return (svg.get_css_property(element, "visibility") or "") == "hidden"
    svg.tree_remove_by(keyboard, is_hidden)
    
    # Replace palette color references with literal srgb hex color codes.
    def create_color_mappings(pair: tuple[str, HideableColor]) -> Iterable[tuple[str, str]]:
        name, color = pair
        color_str = color.convert("srgb").to_string(hex=True)
        return [
            (f"url(\"#{name}\")", color_str),
            (f"url(#{name})", color_str),
        ]
    svg.tree_replace_in_attributes(
        keyboard,
        dict(
            itertools.chain.from_iterable(
                map(create_color_mappings, theme.colors.items())
            )
        ),
    )
    if not svg.tree_remove_by_id(keyboard, "palette-colors"):
        panic("Could not find #palette-colors")
    
    # Remove fonts
    if not svg.tree_remove_by_id(keyboard, "fonts"):
        panic("Could not find #fonts")
    
    # Set fill color of background rect manually that would otherwise be set via
    # css.
    for name, color in theme.colors.items():
        for element in svg.tree_get_by_class(keyboard, f"keycap-color-{name}"):
            rect = element.find("./g/rect")
            if rect is None:
                print(f"Warning: Could not find rect element for {element}")
                continue
            rect.attrib["fill"] = color.convert("srgb").to_string(hex=True)
    svg.tree_remove_by_id(keyboard, "surface-colors")
    
    # Remove all uses of transform-origin
    def iter_with_viewbox(element: ET.Element, view_box: svg.ViewBox) -> Iterable[tuple[ET.Element, svg.ViewBox]]:
        yield (element, view_box)
        for child in element:
            # svg.ViewBox.parse_svg_value()
            if (value := child.attrib.get("viewBox", None)) is not None:
                match svg.ViewBox.parse_svg_value(value):
                    case Ok(view_box):
                        pass
                    case Error(msg):
                        panic(f"Could not parse viewBox value '{value}' in {child}: {msg}")
            yield from iter_with_viewbox(child, view_box)
    for element, view_box in iter_with_viewbox(keyboard, view_box):
        svg.apply_transform_origin(keyboard, element, view_box)

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

    layout, theme = metadata.load()

    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))

    result = build_keyboard_svg(layout, theme, key_templates)
    
    out.mkdir(parents=True, exist_ok=True)
    
    with open(out / "preview.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    log_action_time(
        "Normalizing texture.svg",
        lambda: normalize_keyboard_for_texture(result, theme),
    )
    
    with open(out / "texture.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    with open("/dev/null") as null:
        # Convert all text to paths.
        log_action_time("Converting all text to paths", lambda: subprocess.check_call(
            [
                "inkscape",
                str(out / "texture.svg"),
                "--export-text-to-path",
                "--export-plain-svg",
                "-o", str(out / "texture.svg")
            ],
            # Since inkscape is a fragile shitty program it generates a billion
            # warnings if you look at it wrong. Therefore we need to throw
            # away all warnings and errors.
            stderr=null,
        ))
        
        def clean_up_inkscape(path: Path):
            with open(path, "r") as file:
                tree = ET.parse(file)
            # Remove unnecessary IDs added by Inkscape.
            svg.tree_remove_unreferenced_ids(tree)
            tree.write(path)
        
        # Why does inkscape have to be so hard to work with...
        log_action_time(
            "Cleaning up after Inkscape",
            lambda: clean_up_inkscape(out / "texture.svg"),
        )
        
        log_action_time(
            "Generating texture.pdf",
            lambda: subprocess.check_call(
                ["inkscape", str(out / "texture.svg"), "-o", str(out / "texture.pdf")],
                stderr=null,
            ),
        )
    log_action_time("Generating PNGs", lambda: svg.render_many_files_as_png((
        (out / "preview.svg", out / "preview.png"),
        (out / "texture.svg", out / "texture.png"),
    )))
    
    metadata.store_at(out / "metadata.json5")

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
