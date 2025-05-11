#!/usr/bin/env python

from typing import *
import argparse
import pathlib
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .lib import project, magic
from .lib.svg_builder import *
from .lib.pos import *
from .lib import svg, browser, normalize, action
from .lib import keyboard_builder
from .lib.config import *
from .lib.utils import *
from .lib.error import *
from .lib.color import *
from .lib.generation_metadata import *

def normalize_keyboard_for_texture(keyboard: svg.MaybeElementTree, config: Config) -> None:
    keyboard = svg.resolve_element_tree(keyboard)
    view_box_str = keyboard.attrib.get("viewBox", None)
    if view_box_str == None:
        panic(f"Expected svg element {keyboard} to have a view box")
    match svg.ViewBox.parse_svg_value(view_box_str):
        case Ok(view_box):
            pass
        case Error(msg):
            panic(f"Expected svg element {keyboard}'s view box '{view_box_str}': {msg}")
    
    # Remove embedded fonts
    svg.tree_remove_by_id(keyboard, "fonts")
    
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
    for mask in masks:
        size_u = mask.attrib["id"].removeprefix("_").removesuffix("-base")
        new_mask = keyboard_builder.create_keycap_mask(
            size_u,
            config.unit_size + config.icon_margin * 2,
            config,
        )
        # Replace the mask's children
        mask[:] = new_mask[:]
    
    # Remove all elements with visibility: hidden
    def is_hidden(element: ET.Element) -> bool:
        return (svg.get_css_property(element, "visibility") or "") == "hidden"
    svg.tree_remove_by(keyboard, is_hidden)
    
    # Replace palette color references with literal srgb hex color codes.
    normalize.palette_color_references(keyboard, config)
    
    # Remove all uses of transform-origin
    normalize.reduce_transform_origin(keyboard)

def normalize_text_actions(path: Path) -> None:
    tree = ET.parse(path)
    
    # Convert all text to paths.
    action.log_action(
        f"Converting all text to paths in {path.name}",
        lambda _: normalize.convert_text_to_paths(tree)
    )
    
    tree.write(path, encoding="unicode", xml_declaration=True)

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
    parser.add_argument(
        "--scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution of all of the generated images by this factor. Uses value from layout if not given.",
    )
    parser.add_argument(
        "--preview-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution the output preview.png by this factor. Overrides use of --scale.",
    )
    parser.add_argument(
        "--texture-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution the output texture.png by this factor. Overrides use of --scale.",
    )
    parser.add_argument(
        "--print-outlined-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution the output print-outlined.png by this factor. Overrides use of --scale.",
    )
    parser.add_argument(
        "--print-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution the output print.png by this factor. Overrides use of --scale.",
    )
    
    args = parser.parse_args()
    
    layout_path: pathlib.Path = args.layout
    theme_path: pathlib.Path = args.theme
    template_path: pathlib.Path = args.templates
    out: pathlib.Path = args.out
    scale: float | None = args.scale
    preview_scale: float | None = args.preview_scale
    texture_scale: float | None = args.texture_scale
    print_outlined_scale: float | None = args.print_outlined_scale
    print_scale: float | None = args.print_scale

    args = Args(
        preview_scale=scale if preview_scale is None else preview_scale,
        texture_scale=scale if texture_scale is None else texture_scale,
        print_outlined_scale=scale if print_outlined_scale is None else print_outlined_scale,
        print_scale=scale if print_scale is None else print_scale,
        overview_scale=scale
    )

    metadata = GenerationMetadata(
        layout_path=layout_path,
        theme_path=theme_path,
        args=args,
    )

    timer = action.Timer()

    layout, theme = metadata.load()

    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))

    result = action.log_action(
        "Building keyboard SVG",
        lambda _: keyboard_builder.build_keyboard_svg(layout, theme, key_templates),
    )
    
    out.mkdir(parents=True, exist_ok=True)
    
    with open(out / "preview.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    action.log_action(
        "Normalizing texture.svg",
        lambda _: normalize_keyboard_for_texture(result, theme),
    )
    
    # Remove icon outlines
    svg.tree_remove_by_class(result, "outline")
    
    with open(out / "texture.svg", "w") as file:
        result.write(file, encoding="unicode", xml_declaration=True)
    
    normalize_text_actions(out / "texture.svg")
    
    print_layout = keyboard_builder.pack_keys_for_print(layout)
    
    print_result = action.log_action(
        "Building keyboard print SVG",
        lambda _: keyboard_builder.build_keyboard_svg(print_layout, theme, key_templates),
    )
    
    # Show icon outlines
    for outline in svg.tree_find_by_class(print_result, "outline"):
        outline.set("visibility", "visible")
    
    action.log_action(
        "Normalizing print.svg",
        lambda _: normalize_keyboard_for_texture(print_result, theme),
    )

    with open(out / "print-outlined.svg", "w") as file:
        print_result.write(file, encoding="unicode", xml_declaration=True)
    
    normalize_text_actions(out / "print-outlined.svg")
    
    # Remove icon outlines
    svg.tree_remove_by_class(print_result, "outline")
    
    with open(out / "print.svg", "w") as file:
        print_result.write(file, encoding="unicode", xml_declaration=True)
    
    normalize_text_actions(out / "print.svg")
    
    browser_timer = action.StartedTimedAction("Opening browser")
    with browser.create_page() as page:
        browser_timer.done()
        
        tiles = action.log_action(
            "Generating preview.png",
            lambda _: svg.render_file_as_png(
                page,
                out / "preview.svg",
                out / "preview.png",
                theme.preview_scale,
                magic.max_tile_size,
            )
        )
        action.log_action(
            "Stiching together preview.png",
            lambda _: tiles.stich_together(),
        )
    
    tiles = action.log_action(
        "Generating texture.png's",
        lambda handler: svg.render_file_as_png_segmented_resvg(
            out / "texture.svg",
            out / "texture.png",
            theme.texture_scale,
            magic.max_tile_size,
            progress_handler=handler
        )
    )
    action.log_action(
        "Stiching together texture.png",
        lambda _: tiles.stich_together(),
    )
    
    tiles = action.log_action(
        "Generating print-outlined.png's",
        lambda handler: svg.render_file_as_png_segmented_resvg(
            out / "print-outlined.svg",
            out / "print-outlined.png",
            theme.print_outlined_scale,
            magic.max_tile_size,
            progress_handler=handler
        )
    )
    action.log_action(
        "Stiching together print-outlined.png",
        lambda _: tiles.stich_together(),
    )
    
    tiles = action.log_action(
        "Generating print.png's",
        lambda handler: svg.render_file_as_png_segmented_resvg(
            out / "print.svg",
            out / "print.png",
            theme.print_scale,
            magic.max_tile_size,
            progress_handler=handler
        )
    )
    action.log_action(
        "Stiching together print.png",
        lambda _: tiles.stich_together(),
    )
    
    metadata.store_at(out / "metadata.json5")
    
    print(f"\nDone in {timer.get_pretty()}")
    

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
