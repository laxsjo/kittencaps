from __future__ import annotations
from typing import *
from dataclasses import dataclass, field
from copy import copy, deepcopy
import re
import xml.etree.ElementTree as ET
import itertools

from .error import *
from .utils import *
from .pos import *
from .theme import *
from .color import *
from . import svg 

__all__ = [
    "get_unique_id",
    "element_resolve_namespaces",
    "tree_resolve_namespaces",
    "make_element",
    "untangle_gradient_links",
    "tree_get_viewbox",
    "DefsSet",
    "element_add_label",
    "tree_remove_indentation",
    "tree_filtered_indent",
    "Transform",
    "Placement",
    "element_apply_transform",
    "SizedElement",
    "SvgElement",
    "SvgSymbol",
    "SvgSymbolSet",
    "SvgStyleBuilder",
    "build_palette_def",
    "SvgDocumentBuilder",
]

NS = {
    "": "http://www.w3.org/2000/svg",
    "xlink": "http://www.w3.org/1999/xlink",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "bx": "https://boxy-svg.com",
}

for namespace, url in NS.items():
    ET.register_namespace(namespace, url)

_id_highest_indices: dict[str, int] = dict()
def get_unique_id(prefix: str) -> str:
    global _id_highest_indices
    if prefix not in _id_highest_indices:
        _id_highest_indices[prefix] = 0
    
    result = f"{prefix}-{_id_highest_indices[prefix]}"
    _id_highest_indices[prefix] += 1
    return result

def get_similar_unique_ids(id: str, existing_ids: set[str]) -> str:
    current_suffix = 0
    while True:
        current_id = f"{id}-{current_suffix}"
        if current_id not in existing_ids:
            return current_id
        current_suffix += 1

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

def make_element(tag: str, attributes: dict[str, str|None], children: Iterable[ET.Element] = []) -> ET.Element:
    """
    Sane element initializer that can add child elements.
    Attributes set to `None` won't be set in the final element.
    """
    
    result = ET.Element(tag, {
        name: value
        for name, value in attributes.items()
        if value is not None
    })
    result.extend(children)
    return result

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

# Remove all <linearGradient> elements which link to another with an href, and updated all
# references to this element.
def untangle_gradient_links(tree: ET.ElementTree|ET.Element) -> None:
    def update_all_refs(root: ET.Element, old_id: str, new_id: str) -> None:
        for child in root.iter():
            child.attrib = dict((name, value.replace(f"url(#{old_id})", f"url(#{new_id})")) for name, value in child.attrib.items())
    
    root = tree.getroot() if isinstance(tree, ET.ElementTree) else tree
    
    gradients = dict((gradient.get("id", None), gradient) for gradient in tree.findall(".//linearGradient"))
    
    for gradient in gradients.values():
        if "xlink:href" in gradient.attrib:
            value = gradient.attrib["xlink:href"] 
        elif "href" in gradient.attrib:
            value = gradient.attrib["href"]
        else:
            continue
        
        if "id" not in gradient.attrib:
            # Element is not possible to reference
            continue
        
        id = gradient.attrib["id"]
        
        parent_id = value.removeprefix("#")
        
        update_all_refs(root, id, parent_id)
        svg.tree_remove_element(tree, gradient)

# Get a list of all ids which are somehow referenced by element, or one of its
# children.
def element_get_outgoing_ids(element: ET.Element) -> Iterable[str]:
    def get_single_element_ids(element: ET.Element):        
        attrib = copy(element.attrib)
        
        if "style" in attrib:
            styles = CssStyles.from_style(attrib["style"])
            for value in styles.values():
                url = css_parse_url(value)
                if url is None or not url.startswith("#"):
                    continue
                yield url.removeprefix("#")
        
            del attrib["style"]
        
        for value in attrib.values():
            if value.startswith("#"):
                yield value.removeprefix("#")
    
    yielded_ids = set()
    for child in element.iter():
        for id in get_single_element_ids(child):
            if id not in yielded_ids:
                yielded_ids.add(id)
                yield id

def element_update_outgoing_id(element: ET.Element, old_id: str, new_id: str):
    def update_single_element_id(element: ET.Element, old_id: str, new_id: str):        
        attrib = element.attrib
        
        for name, value in attrib.items():
            if name == "style":
                styles = CssStyles.from_style(value)
                for property, value in styles.items():
                    url = css_parse_url(value)
                    if url is None or not url.startswith("#"):
                        continue
                    
                    id = url.removeprefix("#")
                    if id == old_id:
                        # TODO: This will break if new_id requires escaping...
                        styles[property] = f"url(#{new_id})"
                attrib["style"] = styles.to_style()
            else:
                if value.startswith("#") and value == f"#{old_id}":
                    attrib[name] = f"#{new_id}"
    
    for child in element.iter():
        update_single_element_id(child, old_id, new_id)

def tree_get_viewbox(tree: svg.MaybeElementTree) -> svg.ViewBox:
    root = svg.resolve_element_tree(tree)
    
    match svg.ViewBox.parse_svg_value(root.attrib["viewBox"]):
        case Ok(value):
            return value
        case Error(reason):
            panic(f"Tree svg element contained invalid viewBox '{root.attrib["viewBox"]}': {reason}")

# class DefsSet(list[ET.Element]):
#     def append(self, object):
#         if object not in self:
#             super().append(object)
@dataclass
class DefsSet():
    skipped_ids: set[str]
    defs: list[ET.Element] = field(default_factory=lambda: [])
    
    # Get a list of elements from `tree` which `element` refer to. The return list
    # of elements are deep copies of the elements in tree.
    # 
    # Referred to elements which have an id in `self.skiped_ids` are
    # ignored, i.e. they are not returned and the corresponding attribute in element
    # is not changed.
    # 
    # `self.defs` contains a list of elements previously returned from
    # this function. If any of the returned element ids conflict the ids in the
    # return list are updated, and `element` is mutated to match this new list of elements.
    def extract_references_from_element_in_tree(self, element: ET.Element, tree: svg.MaybeElementTree):
        def extract_uncopied(element: ET.Element):
            nonlocal tree
            tree = svg.resolve_element_tree(tree)
            
            # We don't use a set because we'd like to maintain element order.
            found_referents: list[ET.Element] = []
            
            # To avoid infinite recursion due to cyclic trees
            encountered_elements: set[ET.Element] = {element}
            
            for id in element_get_outgoing_ids(element):
                if id in self.skipped_ids:
                    continue
                
                referent = svg.tree_get_id(tree, id)
                if referent is None or referent in encountered_elements:
                    continue
                encountered_elements.add(referent)
                
                found_referents.append(referent)
                found_referents.extend(extract_uncopied(referent))
            
            # Remove duplicates
            # Unsure if necessary...
            return dict.fromkeys(found_referents).keys()
        
        referents = list(map(deepcopy, extract_uncopied(element)))
        
        existing_ids = {element.get("id", "") for element in self.defs}
        
        for referent in referents:
            id = referent.get("id", "")
            if id in existing_ids:
                new_id = get_similar_unique_ids(id, existing_ids)
                
                referent.set("id", new_id)
                for element in (element, *referents):
                    element_update_outgoing_id(element, id, new_id)
        
        self.defs += referents
            

# Add label to element in a way which is understood by inkscape and boxy-svg
def element_add_label(element: ET.Element, label: str) -> None:
    s = list(element)
    if (title := element.find("./title")) is None:
        title = ET.Element("title")
        element.insert(0, title)
    
    element.set("inkscape:label", label)
    title.text = label

def tree_remove_indentation(tree: ET.ElementTree|ET.Element) -> None:
    root = tree.getroot() if isinstance(tree, ET.ElementTree) else tree
    
    for child in root.iter():
        if child.tail and not child.tail.strip():
            child.tail = ""
        if child.text and not child.text.strip():
            child.text = ""

def tree_filtered_indent(
        tree: ET.Element|ET.ElementTree,
        predicate: Callable[[ET.Element], bool] = lambda element: element.tag not in ["text"],
        space: str="  ",
        level: int=0,
        add_to_existing: bool = False) -> None:
    """Indent an XML document by inserting newlines and indentation space
    after elements.

    *tree* is the ElementTree or Element to modify.  The (root) element
    itself will not be changed, but the tail text of all elements in its
    subtree will be adapted.
    
    *predicate* is a function which is called for every element in the tree (including the
    root). If this function returns false, it's content isn't indented. 

    *space* is the whitespace to insert for each indentation level, two
    space characters by default.

    *level* is the initial indentation level. Setting this to a higher
    value than 0 can be used for indenting subtrees that are more deeply
    nested inside of a document.
    
    *add_to_existing* specifies if the indentation white space should be added
    onto any existing whitespace. If false this operation
    is idempotent. (default is False)
    """
    root = tree.getroot() if isinstance(tree, ET.ElementTree) else tree
    
    if level < 0:
        raise ValueError(f"Initial indentation level must be >= 0, got {level}")
    if not len(root):
        return

    # Reduce the memory consumption by reusing indentation strings.
    indentations = ["\n" + level * space]

    def _indent_children(elem: ET.Element, level: int):
        if not predicate(elem):
            return
        
        # Start a new indentation level for the first child.
        child_level = level + 1
        try:
            child_indentation = indentations[child_level]
        except IndexError:
            child_indentation = indentations[level] + space
            indentations.append(child_indentation)

        if not elem.text or not elem.text.strip():
            elem.text = child_indentation

        child = None
        for i, child in enumerate(elem):
            if len(child):
                _indent_children(child, child_level)
            if not child.tail or not child.tail.strip():
                if not add_to_existing:
                    child.tail = ""
                
                if i == len(elem) - 1:
                    child.tail = (child.tail or "") + indentations[level]
                else:
                    child.tail = (child.tail or "") + child_indentation

    _indent_children(root, 0)

@dataclass
class Transform:
    translate: Vec2 | None = None
    rotate: Rotation | None = None
    scale: Scaling | None  = None
    
    def get_translation(self) -> Vec2:
        return self.translate or Vec2.identity()
        
    def get_rotation(self) -> Rotation:
        return self.rotate or Rotation.identity()
        
    def get_scaling(self) -> Scaling:
        return self.scale or Scaling.identity()
    
    def to_svg_value(self) -> str:
        transforms: list[str] = []
        if self.translate != None and not self.translate.is_identity():
            transforms.append(f"translate({", ".join(map(number_to_str, self.translate))})")
        if self.rotate != None and not self.rotate.is_identity():
            transforms.append(f"rotate({self.rotate.deg:g})")
        if self.scale != None and not self.scale.is_identity():
            transforms.append(f"scale({", ".join(map(number_to_str, self.scale))})")
        return " ".join(transforms)
        
    @classmethod
    def identity(cls) -> Self:
        return cls()

class Placement(Transform):
    def __init__(self, translate: Vec2|None = None, rotate: Rotation|None = None):
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
    
    new_style = previous_style + " ".join(style_statements)
    if new_style != "":
        element.attrib["style"] = previous_style + " ".join(style_statements)

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
    def set_scale(self, size: Scaling):
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
    # TODO: Wow this is ugly...
    other_elements: list[ET.Element]
    
    def __init__(self, source: ET.ElementTree) -> None:
        tree_resolve_namespaces(source)
        
        elements = source.findall("symbol")
        for element in elements:
            tree_remove_indentation(element)
        self.symbols = dict(map(lambda icon: (icon.id, icon), map(SvgSymbol, elements)))
        
        self.other_elements = []
        style = source.find("style")
        if style is not None:
            self.other_elements.append(style)
        self.other_elements.extend(source.findall("clipPath"))
        self.other_elements.extend(source.findall("filter"))
    
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
    def indentation(self, indent_level: int, space: str = "  ") -> SvgStyleBuilder:
        self._indent_depth = indent_level
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
        title = ET.Element("title")
        title.text = name
        stop = ET.Element("stop", {
            "style": f"stop-color:{color};"
        })
        
        gradient = ET.Element("linearGradient", {
            "id": name,
            # To make Inkscape happy
            "inkscape:swatch": "solid",
            # To make BoxySVG happy
            "bx:pinned": "true",
            "gradientUnits": "userSpaceOnUse",
        })
        gradient.append(title)
        gradient.append(stop)
        
        def_element.append(gradient)
    
    return def_element

class SvgDocumentBuilder:
    elements: list[ET.Element]
    _root_styles: CssStyles
    _palette: Palette|None = None
    viewbox: svg.ViewBox|None = None
    
    def __init__(self) -> None:
        self.elements = []
        self._root_styles = CssStyles()
        pass
    
    def add_element(self, element: ET.Element) -> Self:
        self.elements.append(element)
        return self
    def add_elements(self, elements: Iterable[ET.Element]) -> Self:
        for element in elements:
            self.add_element(element)
        return self
    
    def add_icon_set(self, icon_set: SvgSymbolSet) -> Self:
        self.elements.extend(icon_set.other_elements)
        for icon in icon_set.symbols.values():
            self.elements.append(icon.source.element)
        return self
    
    def root_styles(self, styles: CssStyles) -> Self:
        self._root_styles |= styles
        return self
    
    def palette(self, palette: Palette) -> Self:
        self._palette = palette
        return self
    
    def set_viewbox(self, viewbox: svg.ViewBox) -> Self:
        self.viewbox = viewbox
        return self
    
    def build(self) -> ET.ElementTree:
        if self.viewbox == None:
            panic("You must set a viewbox!")
        viewbox_str = f"{self.viewbox.pos.x:g} {self.viewbox.pos.y:g} {self.viewbox.size.x:g} {self.viewbox.size.y:g}"
        
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
        tree_filtered_indent(tree, lambda element: element.tag not in ["text"], "  ")
        
        return tree
