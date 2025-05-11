from typing import *
from pathlib import Path
import itertools
import re
import xml.etree.ElementTree as ET
import subprocess
import tempfile
from coloraide import Color

from .svg_builder import *
from .pos import *
from . import svg
from .config import *
from .utils import *
from .error import *
from .color import *


def palette_color_references(document: svg.MaybeElementTree, config: Config) -> None:
    """
        Replaces palette color references with their literal srgb hex color
        codes. Removes palette-colors element.
    """
    document = svg.resolve_element_tree(document)
    # 
    def create_color_mappings(pair: tuple[str, HideableColor]) -> Iterable[tuple[str, str]]:
        name, color = pair
        color_str = color.convert("srgb").to_string(hex=True)
        return [
            (f"url(\"#{name}\")", color_str),
            (f"url(#{name})", color_str),
        ]
    svg.tree_replace_in_attributes(
        document,
        dict(
            itertools.chain.from_iterable(
                map(create_color_mappings, config.colors.items())
            )
        ),
    )
    if not svg.tree_remove_by_id(document, "palette-colors"):
        panic("Could not find #palette-colors")

def convert_text_to_paths(document: svg.ElementTree):
    with open("/dev/null") as null, \
            tempfile.NamedTemporaryFile(suffix=".svg", delete_on_close=False) as temp_file:
        document.write(temp_file)
        temp_file.close()
        
        
        subprocess.check_call(
            [
                "inkscape",
                temp_file.name,
                "--export-text-to-path",
                "--export-plain-svg",
                "-o", temp_file.name
            ],
            # Since inkscape is a fragile shitty program it generates a billion
            # warnings if you look at it wrong. Therefore we need to throw
            # away all warnings and errors.
            stderr=null,
        )
        
        with open(temp_file.name, "r") as file:
            document.parse(file)
        
    # Why does inkscape have to be so hard to work with...
    svg.tree_remove_unreferenced_ids(document)
    
def reduce_transform_origin(document: svg.MaybeElementTree):
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
    for element, view_box in iter_with_viewbox(svg.resolve_element_tree(document), svg.tree_get_viewbox(document)):
        svg.apply_transform_origin(document, element, view_box)

def reduce_color_spaces_to_srgb(document: svg.MaybeElementTree):
    # Yes, this only detects a small subset of supported CSS colors... 
    color_functions = ["oklab", "oklch", "lab", "lch"]
    pattern = re.compile(
        r"\b(?:"
        + "|".join(color_functions)
        + r")\(\d+(?:\.\d+)?(?: \d+(?:\.\d+)?){2}(?: / \d+(?:\.\d+)?)?\)",
    )
    def reduce_colors(_, value: str) -> str:
        return re.sub(
            pattern,
            lambda match: Color(match.group(0)).convert("srgb").to_string(hex=True),
            value,
        )
    
    svg.tree_map_attributes(document, reduce_colors)
