from typing import *
from pathlib import Path
import re
import xml.etree.ElementTree as ET 
from playwright.sync_api import sync_playwright
import io


from . import svg_builder
from .utils import *
from .error import *
from .color import *

# TODO: Should probably move a lot of the basic SVG utils from svg_builder.py
# into here. Or rename this module to something more specific like converting
# formats.

__all__ = [
    "MaybeElementTree",
    "resolve_element_tree",
    "tree_replace_in_attributes",
    "tree_to_str",
    "render_many_files_as_png",
]

type MaybeElementTree = ET.Element | ET.ElementTree
def resolve_element_tree(tree: MaybeElementTree) -> ET.Element:
    return tree.getroot() if isinstance(tree, ET.ElementTree) else tree

def string_replace_mappings(string: str, mappings: Dict[str, str]) -> str:
    if len(mappings) == 0:
        # Exit early to avoid having to compile and use regex. IDK if this
        # actually does anything, but I don't care :)
        return string
    
    pattern = "|".join(map(re.escape, mappings.keys()))
    return re.sub(pattern, lambda match: mappings[match.group(0)], string)

# Replace all matches of the keys in mappings in any attribute values of the specified element or
# its decendants with new.
def tree_replace_in_attributes(tree: MaybeElementTree, mappings: Dict[str, str]) -> None:
    """
    Replaces all matches of the keys in mappings with their corresponding values
    in any attribute values of the specified element or its decendants. The
    replacements are done in place, meaning that later mappings won't replace
    the values inserted by earlier mappings.
    """
    def replace(attribute: Tuple[str, str]) -> Tuple[str, str]:
        name, value = attribute
        
        return (name, string_replace_mappings(value, mappings))
    
    tree = resolve_element_tree(tree)
    for element in tree.iter():
        element.attrib = dict(map(replace, element.attrib.items()))

def tree_to_str(tree: ET.Element|ET.ElementTree) -> str:
    tree = tree if isinstance(tree, ET.ElementTree) else ET.ElementTree(tree)
    
    output = io.StringIO()
    tree.write(output, encoding="unicode")
    return output.getvalue()

def render_many_files_as_png(in_out_path_pairs: Iterable[tuple[Path, Path]]):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        for svg_path, out_path in in_out_path_pairs:
            with open(svg_path, "r") as file:
                svg = ET.parse(svg_path)
            view_box = svg_builder.tree_get_viewbox(svg)
            
            page.set_viewport_size({
                'width': int(view_box.size.get_x()),
                'height': int(view_box.size.get_y()),
            })
            
            page.goto(f'file://{str(svg_path.absolute())}')
            
            page.screenshot(path=out_path, omit_background=True)
        
        browser.close()
