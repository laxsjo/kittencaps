from __future__ import annotations
from typing import *
from dataclasses import dataclass
import re
import xml.etree.ElementTree as ET
import itertools

from .error import *
from .utils import *
from .pos import *
from .theme import *
from .color import *

__all__ = [
    "element_resolve_namespaces",
    "remove_element_in_tree",
    "Transform",
    "Placement",
    "element_apply_transform",
    "ViewBox",
    "SizedElement",
    "SvgElement",
    "SvgSymbol",
    "SvgSymbolSet",
    "SvgStyleBuilder",
    "SvgDocumentBuilder",
]

NS = {
    "": "http://www.w3.org/2000/svg",
    "xlink": "http://www.w3.org/1999/xlink",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
}

for namespace, url in NS.items():
    ET.register_namespace(namespace, url)

# label_raw can either be a tag name or attribute name. If it has a namespace it should be
# in the form '{namespace_url}label'.
def resolve_label(label_raw: str) -> str:
    namespaces = NS
    
    result = re.search(r"^(?:\{(.*)\})?(.*)$", label_raw)
    if result == None:
        raise Exception(f"Expected regex to match on '{label_raw}'")
    url = result.group(1)
    name = result.group(2)
    if url == None:
        return name
    
    url_namespaces = dict(map(lambda pair: (pair[1], pair[0]), namespaces.items()))
    
    if url not in url_namespaces:
        # It's better to preserve any unknown namespaces.
        return label_raw
    
    if url_namespaces[url] == "":
        return name
    else:
        return f"{url_namespaces[url]}:{name}"

def element_resolve_namespaces(element: ET.Element) -> None:
    element.tag = resolve_label(element.tag)
    element.attrib = dict((resolve_label(name), value) for name, value in element.attrib.items())

def tree_resolve_namespaces(tree: ET.ElementTree|ET.Element) -> None:
    root = tree.getroot() if isinstance(tree, ET.ElementTree) else tree
    
    element_resolve_namespaces(root)
    for child in root.findall(".//*"):
        element_resolve_namespaces(child)



def element_depth_in_tree(element: ET.Element, tree: ET.ElementTree|ET.Element) -> int | Error[str]:
    root = tree.getroot() if isinstance(tree, ET.ElementTree) else tree
    if element == root:
        return 0
    
    parent_map: dict[ET.Element, ET.Element] = dict()
    for parent in tree.iter():
        for child in parent:
            parent_map[child] = parent
    for child in root:
        parent_map[child] = root
    
    depth = 0
    current_element = element
    
    if current_element not in parent_map:
        return Error(f"Given element not in tree")
    
    while current_element != root:
        if current_element not in parent_map:
            # Should be impossible
            panic(f"Encountered orphaned element {current_element} at depth {depth}")
        
        current_element = parent_map[current_element]
        depth += 1
    
    return depth

def remove_element_in_tree(element: ET.Element, tree: ET.ElementTree|ET.Element):
    for parent in tree.iter():
        # Removes element it if it's a child of parent 
        parent.remove(element)
    

@dataclass
class Transform:
    translate: Pos | None = None
    rotate: Rotation | None = None
    scale: Scaling | None  = None
    
    def get_translation(self) -> Pos:
        return self.translate or Pos.identity()
        
    def get_rotation(self) -> Rotation:
        return self.rotate or Rotation.identity()
        
    def get_scaling(self) -> Scaling:
        return self.scale or Scaling.identity()
    
    def to_svg_value(self) -> str:
        transforms: list[str] = []
        if self.translate != None and not self.translate.is_identity():
            transforms.append(f"translate({", ".join(map(str, self.translate))})")
        if self.rotate != None and not self.rotate.is_identity():
            transforms.append(f"rotate({self.rotate.deg})")
        if self.scale != None and not self.scale.is_identity():
            transforms.append(f"scale({", ".join(map(str, self.scale))})")
        return " ".join(transforms)
        
    @classmethod
    def identity(cls) -> Self:
        return cls()

class Placement(Transform):
    def __init__(self, translate: Pos|None = None, rotate: Rotation|None = None):
        super().__init__(translate, rotate, None)
    

def element_apply_transform(element: ET.Element, transform: Transform) -> None:
    element.attrib["transform"] = (
        transform.to_svg_value()
        + " "
        + element.attrib.get("transform", "")
    ).removesuffix(" ")

def element_apply_style(element: ET.Element, styles: CssStyles) -> None:
    style_statements = [
        f"{name}: {color};" for (name, color) in styles.items()
    ]
    previous_style = element.attrib.get("styles", "")
    if len(previous_style) > 0 and not previous_style.endswith(";"):
        previous_style += ";"
    
    element.attrib["style"] = previous_style + " ".join(style_statements)

@dataclass
class ViewBox:
    pos: Pos
    size: Scaling
    
    def add_padding(self, padding: float) -> ViewBox:
        return ViewBox(
            pos=self.pos - Pos(padding, padding),
            size=self.size + Scaling(padding) * 2
        )
    
    @classmethod
    def from_bounds(cls, bounds: Bounds) -> Self:
        delta = bounds.max - bounds.min
        
        # TODO: Does this really work?
        return cls(
            pos=bounds.min,
            size=delta.as_scaling()
        )

@dataclass
class SizedElement:
    element: ET.Element
    size: Scaling

class SvgElement(SizedElement):
    element: ET.Element
    size: Scaling
    
    def __init__(self, element: ET.Element) -> None:
        if "viewBox" not in element.attrib:
            panic("SizedElement: Element did not have 'viewBox' attribute", 1)
        size = tuple(itertools.islice(map(float, element.attrib["viewBox"].split(" ")), 2, 4))
        if len(size) != 2:
            panic(f"SizedElement: Expected parsed size from viewBox '{element.attrib["viewBox"]}' to be of length 2", 1)
        self.size = Scaling(*size)
        self.element = element
    
    # TODO: Super ugly name and everything
    def set_size(self, size: Scaling):
        view_box_size = Scaling(*itertools.islice(map(float, self.element.attrib["viewBox"].split(" ")), 2, 4))
        
        size *= view_box_size
        
        self.size = size
        size = size.promote_to_pair()
        self.element.attrib["width"] = str(size.x)
        self.element.attrib["height"] = str(size.y)

class SvgSymbol:
    id: str
    source: SvgElement
    
    def __init__(self, icon_element: ET.Element):
        if resolve_label(icon_element.tag) != "symbol":
            raise Exception(f"Icon source element was not an 'symbol' tag, '{resolve_label(icon_element.tag)}' found")
        if "id" not in icon_element.attrib:
            raise Exception(f"Icon source element did not have 'id' attribute")
        
        self.id = icon_element.attrib["id"]
        self.source = SvgElement(icon_element)
        tree_resolve_namespaces(icon_element)

class SvgSymbolSet:
    symbols: dict[str,SvgSymbol]
    style: ET.Element|None
    
    def __init__(self, source: ET.ElementTree) -> None:
        elements = source.findall("symbol", NS)
        self.symbols = dict(map(lambda icon: (icon.id, icon), map(SvgSymbol, elements)))
        
        self.style = source.find("style", NS)
        if self.style != None:
            element_resolve_namespaces(self.style)
        
        
    
    def __contains__(self, id: str) -> bool:
        return id in self.symbols
    
    def __getitem__(self, id: str) -> SvgSymbol|Error[str]:
        if id in self:
            return self.symbols[id]
        else:
            return Error(f"Icon set did not contain id '{id}'")
    
    def create_symbol_element(self, id: str, placement: Placement, dimensions: tuple[float, float] = (1.0, 1.0)) -> ET.Element|Error[str]:
        symbol = self[id]
        if isinstance(symbol, Error):
            return symbol
        
        return ET.Element("use", attrib={
            "xlink:href": f"#{symbol.id}",
            "width": str(dimensions[0]),
            "height": str(dimensions[1]),
            "transform": placement.to_svg_value(),
            "style": "overflow:visible;",
        })
        
class SvgStyleBuilder:
    _attributes: dict[str, str]
    _statements: list[CssStatement|CssRule]
    # The indentation level the generated style tag would have, as determined by
    # add_indentation
    _indent_depth: int|None = None
    _indent_space: str = ""
    
    def __init__(self):
        self._attributes = dict()
        self._statements = []

    def statement(self, *statements: CssStatement) -> SvgStyleBuilder:
        self._statements.extend(statements)
        return self
    
    def rule(self, *rules: CssRule) -> SvgStyleBuilder:
        self._statements.extend(rules)
        return self
    
    def attributes(self, attributes: dict[str, str]) -> Self:
        self._attributes |= attributes
        return self
    
    # Make sure that the generated element content is indented as if the style element was
    # at indent depth in the element tree.
    def indentation(self, indent: int, space: str = "  ") -> SvgStyleBuilder:
        self._indent_depth = indent
        self._indent_space = space
        return self
    
    # Indent content properly when inserted under the given parent in it's tree.
    def calculate_indentation(self, parent: ET.Element, tree: ET.ElementTree|ET.ElementTree, space: str = "  ") -> SvgStyleBuilder:
        parent_depth = element_depth_in_tree(parent, tree)
        if isinstance(parent_depth, Error):
            panic(f"Given parent element {parent} is not part of the tree {tree}")
        
        self._indent_depth = parent_depth + 1
        self._indent_space = space
        return self
    
    def build(self) -> ET.Element:
        depth = self._indent_depth if self._indent_depth != None else 0
        def indent_statement(statement: CssStatement|CssRule) -> str:
            return "\n".join(map(
                lambda line: (self._indent_space * (depth + 1)) + line,
                statement.realize().split("\n")
            ))
        css_text = ""
        if self._indent_depth != None:
            css_text += "\n"
        css_text += "\n".join(map(indent_statement, self._statements))
        if self._indent_depth != None:
            # Account for whitespace in front of closing tag
            css_text += "\n" + self._indent_space * depth
        
        element = ET.Element("style", {
            "type": "text/css",
        } | self._attributes)
        element.text = css_text
        
        return element

# Create def element containing linear gradient symbols of palette colors
def build_palette_def(palette: Palette) -> ET.Element:
    def_element = ET.Element("defs", {
        "id": "palette-colors",
    })
    
    for name, color in palette.css_colors().items():
        stop = ET.Element("stop", {
            "style": f"stop-color:{color};"
        })
        
        gradient = ET.Element("linearGradient", {
            "id": name,
            "inkscape:swatch": "solid",
        })
        gradient.append(stop)
        
        def_element.append(gradient)
    
    return def_element
        
        

class SvgDocumentBuilder:
    elements: list[ET.Element]
    _root_styles: CssStyles
    _palette: Palette|None = None
    viewbox: ViewBox|None = None
    
    def __init__(self) -> None:
        self.elements = []
        self._root_styles = dict()
        pass
    
    def add_element(self, element: ET.Element) -> Self:
        self.elements.append(element)
        return self
    def add_elements(self, elements: Iterable[ET.Element]) -> Self:
        for element in elements:
            self.add_element(element)
        return self
    
    def add_icon_set(self, icon_set: SvgSymbolSet) -> Self:
        if icon_set.style != None:
            self.elements.append(icon_set.style)
        for icon in icon_set.symbols.values():
            self.elements.append(icon.source.element)
        return self
    
    def root_styles(self, styles: CssStyles) -> Self:
        self._root_styles |= styles
        return self
    
    def palette(self, palette: Palette) -> Self:
        self._palette = palette
        return self
    
    def set_viewbox(self, viewbox: ViewBox) -> Self:
        self.viewbox = viewbox
        return self
    
    def build(self) -> ET.ElementTree:
        if self.viewbox == None:
            panic("You must set a viewbox!")
        viewbox_str = f"{self.viewbox.pos.x} {self.viewbox.pos.y} {self.viewbox.size.x} {self.viewbox.size.y}"
        
        def transform_namespace(pair: tuple[str, str]) -> tuple[str, str]:
            namespace, url = pair
            if namespace == "":
                return ("xmlns", url)
            else:
                return (f"xmlns:{namespace}", url)
        namespace_attrs = dict(map(transform_namespace, NS.items()))
        
        root = ET.Element('svg', {
            "version": "1.1",
            "viewBox": viewbox_str,
        } | namespace_attrs)
        element_apply_style(root, self._root_styles)
        
        if self._palette != None:
            root.append(build_palette_def(self._palette))
        
        for element in self.elements:
            root.append(element)
        
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        
        return tree
