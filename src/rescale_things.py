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
from .lib.keyboard_builder import create_text_icon_svg
from .lib.pos import *
from .lib.theme import *
from .lib.color import *
from .lib import project
from .lib.error import *

parser = argparse.ArgumentParser(description="temp")
parser.add_argument(
    "file",
    metavar="FILE",
    type=pathlib.Path,
    help="hello :3",
)

args = parser.parse_args()


def split_components(path_value) -> list[str]:
    return re.findall(r"[a-z]|-?[0-9]+(?:\.[0-9]+)?|,|[^a-z0-9\-.,]+", path_value, re.IGNORECASE)

def scale_attribute(element: ET.Element, attribute: str, factor: float) -> None:
    def scale_component(component: str) -> str:
        try:
            value = float(component)
            return f"{value * factor:g}"
        except ValueError:
            return component
    
    components = split_components(element.attrib[attribute])
    
    element.attrib[attribute] = "".join(map(scale_component, components))

with open(args.file, "r") as f:
    factor: float = 100/36
    
    document = ET.parse(f)
    tree_resolve_namespaces(document)
    
    symbols = []
    for symbol in document.findall(".//symbol"):
        path = symbol.find("./path")
        if path is None or "viewBox" not in symbol.attrib or "d" not in path.attrib:
            continue
        
        scale_attribute(symbol, "viewBox", factor)
        scale_attribute(path, "d", factor)
        
        tree = ET.ElementTree(symbol)
        ET.indent(tree, space="  ")
        tree.write(sys.stdout, encoding="unicode")
        
