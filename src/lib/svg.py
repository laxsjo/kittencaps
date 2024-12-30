from typing import *
import os
import tempfile
import pathlib
import xml.etree.ElementTree as ET 
from playwright.sync_api import sync_playwright

from . import svg_builder

# TODO: Should probably move a lot of the basic SVG utils from svg_builder.py
# into here. Or rename this module to something more specific like converting
# formats.

__all__ = [
    "convert_tree_to_png",
]

def convert_tree_to_png(svg: ET.ElementTree) -> bytes:
    with sync_playwright() as p, tempfile.TemporaryDirectory() as dir_str:
        dir = pathlib.Path(dir_str)
        in_path = dir / "in.svg"
        out_path = dir / "out.png"
        
        with open(in_path, "w") as file:
            svg.write(file, encoding="unicode", xml_declaration=True)
        
        browser = p.chromium.launch()
        page = browser.new_page()
        
        view_box = svg_builder.tree_get_viewbox(svg)
        
        page.set_viewport_size({
            'width': int(view_box.size.get_x()),
            'height': int(view_box.size.get_y()),
        })
        
        page.goto(f'file://{str(in_path)}')
        
        page.wait_for_selector('svg')
        
        page.screenshot(path=out_path, omit_background=True)
        
        browser.close()
        
        with open(out_path, "rb") as file:
            return file.read()
