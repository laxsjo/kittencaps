from typing import *
from pathlib import Path
import xml.etree.ElementTree as ET 
from playwright.sync_api import sync_playwright
from . import svg_builder
from .utils import *
from .error import *
import io

# TODO: Should probably move a lot of the basic SVG utils from svg_builder.py
# into here. Or rename this module to something more specific like converting
# formats.

__all__ = [
    "tree_to_str",
    "render_many_files_as_png",
]

import xml.dom.minidom as minidom

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
