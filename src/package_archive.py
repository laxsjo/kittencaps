from typing import *
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

from .lib import project, action
from .lib.svg_builder import *
from .lib.pos import *
from .lib import archive, keyboard_builder
from .lib.config import *
from .lib.utils import *
from .lib.error import *
from .lib.color import *
from .lib.generation_metadata import *

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an archive with the keycap icons as individual images. The print and print_outlined variants are rendered.",
    )
    parser.add_argument(
        "out",
        metavar="OUT",
        type=Path,
        help="Path which the ZIP archive will be written to."
    )
    parser.add_argument(
        "--layout",
        metavar="LAYOUT",
        type=Path,
        help="Path to a json file containing a KLE layout definition."
    )
    parser.add_argument(
        "--theme",
        metavar="THEME",
        type=Path,
        default=project.path_to_absolute("assets/themes/standard.json"),
        help="Path to a JSON file describing the fonts and colors to use in the generated SVG. Must follow the schema 'assets/themes/theme-schema.json'.",
    )
    parser.add_argument(
        "--templates",
        metavar="KEYCAP_TEMPLATES",
        type=Path,
        default=project.path_to_absolute("assets/templates/frame-templates.svg"),
        help="Path to an SVG containing the keycap frame template symbols.",
    )
    parser.add_argument(
        "--scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution of all of the generated images by this factor. Uses value from layout if not given.",
    )
    parser.add_argument(
        "--print-outlined-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution of the print-outlined images by this factor. Overrides use of --scale.",
    )
    parser.add_argument(
        "--print-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution of the print images by this factor. Overrides use of --scale.",
    )
    parser.add_argument(
        "--overview-scale",
        metavar="SCALE",
        type=float,
        default=None,
        help="Scale the resolution of the overview.png image by this factor. Overrides use of --scale.",
    )
    
    args = parser.parse_args()
    
    out: Path = args.out
    layout_path: Path = args.layout
    theme_path: Path = args.theme
    template_path: Path = args.templates
    scale: float | None = args.scale
    print_outlined_scale: float | None = args.print_outlined_scale
    print_scale: float | None = args.print_scale
    overview_scale: float | None = args.overview_scale

    args = Args(
        preview_scale=scale,
        texture_scale=scale,
        print_outlined_scale=scale if print_outlined_scale is None else print_outlined_scale,
        print_scale=scale if print_scale is None else print_scale,
        overview_scale=scale if overview_scale is None else overview_scale,
    )

    metadata = GenerationMetadata(
        layout_path=layout_path,
        theme_path=theme_path,
        args=args,
    )

    timer = action.Timer()

    layout, config = metadata.load()
    
    with open(template_path, "r") as file:
        key_templates = SvgSymbolSet(ET.parse(file))
    
    layout = keyboard_builder.pack_keys_for_print(layout)
    
    file = action.log_action(
        "Generating ZIP archive",
        lambda handler: archive.package_keycap_icons_archive(
            layout,
            config,
            key_templates,
            progress_handler=handler,
        ),
    )
    
    out.write_bytes(file.getbuffer())
    
    print(f"\nDone in {timer.get_pretty()}")

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
