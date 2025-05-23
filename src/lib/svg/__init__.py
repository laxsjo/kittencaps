from __future__ import annotations
from typing import *
from pathlib import Path
from dataclasses import dataclass
import os
import sys
import io
import subprocess
import re
import itertools
import xml.etree.ElementTree as ET 
from playwright import sync_api as playwright

from .. import browser, render, shell
from ..utils import *
from ..error import *
from ..color import *
from ..pos import *
from ..default import *
from .. import iterator
from . import path

# TODO: Should probably move a lot of the basic SVG utils from svg_builder.py
# into here. Or rename this module to something more specific like converting
# formats.

__all__ = [
    "ElementTree",
    "MaybeElementTree",
    "resolve_element_tree",
    "tree_get_id",
    "tree_get_by",
    "tree_get_by_class",
    "tree_remove_by",
    "tree_remove_by_class",
    "tree_remove_by_id",
    "tree_remove_attributes_by",
    "tree_map_attributes",
    "tree_replace_in_attributes",
    "tree_remove_unreferenced_ids",
    "tree_remove_element",
    "tree_find_by_class",
    "get_css_property",
    "append_css_properties",
    "remove_css_properties",
    "is_basic_shape",
    "basic_shape_pre_transform_bounds",
    "apply_transform_origin",
    "tree_to_str",
    "render_file_as_png",
    "render_file_as_png_segmented_resvg",
]

@dataclass
class ViewBox:
    pos: Vec2[float]
    size: Scaling
    
    def add_padding(self, padding: float) -> ViewBox:
        return ViewBox(
            pos=self.pos - Vec2(padding, padding),
            size=self.size + Scaling(padding) * 2
        )
    
    @classmethod
    def parse_svg_value(cls, value: str) -> Result[Self, str]:
        try:
            components = tuple(map(float, re.sub(r"[\s,]+", " ", value).split(" ")))
        except ValueError as error:
            return Error(
                f"Value contained non-numeric component: {" ".join(error.args)}"
            )
        
        if len(components) != 4:
            return Error(f"Value did not contained 4 components: Got {len(components)}")
        
        x, y, width, height = components
        return Ok(cls(
            Vec2(x, y),
            Scaling(width, height),
        ))
    
    def as_svg_value(self) -> str:
        return " ".join(map(str, (*self.pos, *self.size.as_vec2())))
    
    @classmethod
    def from_bounds(cls, bounds: Bounds) -> Self:
        delta = bounds.max - bounds.min
        
        # TODO: Does this really work?
        return cls(
            pos=bounds.min,
            size=delta.as_scaling()
        )
    
    def bounds(self) -> Bounds:
        return Bounds.from_pos_size(self.pos, self.size.as_vec2())


type ElementTree = ET.ElementTree[ET.Element[str]]
type MaybeElementTree = ET.Element[str] | ET.ElementTree[ET.Element]
def resolve_element_tree(tree: MaybeElementTree) -> ET.Element:
    return tree.getroot() if isinstance(tree, ET.ElementTree) else tree

def string_replace_mappings(string: str, mappings: Dict[str, str]) -> str:
    if len(mappings) == 0:
        # Exit early to avoid having to compile and use regex. IDK if this
        # actually does anything, but I don't care :)
        return string
    
    pattern = "|".join(map(re.escape, mappings.keys()))
    return re.sub(pattern, lambda match: mappings[match.group(0)], string)

def tree_get_id(tree: MaybeElementTree, id: str) -> ET.Element|None:
    for element in resolve_element_tree(tree).iter():
        if element.get("id", None) == id:
            return element

def tree_get_by(tree: MaybeElementTree, predicate: Callable[[ET.Element], bool]) -> ET.Element|None:
    for element in resolve_element_tree(tree).iter():
        if predicate(element):
            return element
    return None


def tree_get_by_class(tree: MaybeElementTree, class_name: str) -> Iterable[ET.Element]:
    for element in tree.iter():
        if class_name in element.attrib.get("class", "").split(" "):
            yield element

def tree_remove_by(tree: MaybeElementTree, predicate: Callable[[ET.Element], bool]) -> bool:
    """
    Remove elements for which the provided predicate returns true. Can't remove
    the root node.
    Return true if any elements were removed, otherwise false.
    """
    found_any = False
    for parent in tree.iter():
        for child in tuple(parent):
            if predicate(child):
                found_any = True
                parent.remove(child)
    return found_any

def tree_remove_by_class(tree: MaybeElementTree, class_: str) -> bool:
    """
    Remove all elements in tree with the provided class.
    Return true if any elements were removed, otherwise false.
    """
    return tree_remove_by(tree, lambda element: element.get("class") == class_)

def tree_remove_by_id(tree: MaybeElementTree, id: str) -> bool:
    """
    Remove all elements with the provided id. Return true if any elements were
    removed, otherwise false.
    """
    return tree_remove_by(tree, lambda element: element.get("id") == id)

def tree_remove_attributes_by(tree: MaybeElementTree, predicate: Callable[[str, str], bool]) -> None:
    """
    Remove element attributes from all elements for which the provided predicate
    returns true.
    
    The predicate is called with the attribute name and value, in that order.
    """
    for element in tree.iter():
        element.attrib = dict(filter(lambda pair: not predicate(*pair), element.attrib.items()))

def tree_remove_element(tree: MaybeElementTree, element: ET.Element) -> bool:
    for parent in tree.iter():
        # Removes element it if it's a child of parent 
        if element in parent:
            parent.remove(element)
            return True
    return False

def tree_map_attributes(tree: MaybeElementTree, function: Callable[[str, str], str]) -> None:
    """
    Calls `function` with name and value for each attribute of every element in
    tree, replacing the value with the one returned by `function`.
    """
    
    def mapper(pair: Tuple[str, str]) -> Tuple[str, str]:
        return (pair[0], function(pair[0], pair[1]))
    
    tree = resolve_element_tree(tree)
    for element in tree.iter():
        element.attrib = dict(map(mapper, element.attrib.items()))

# Replace all matches of the keys in mappings in any attribute values of the specified element or
# its decendants with new.
def tree_replace_in_attributes(tree: MaybeElementTree, mappings: Dict[str, str]) -> None:
    """
    Replaces all matches of the keys in mappings with their corresponding values
    in any attribute values of the specified element or its decendants. The
    replacements are done in place, meaning that later mappings won't replace
    the values inserted by earlier mappings.
    """
    tree_map_attributes(
        tree,
        lambda _, value: string_replace_mappings(value, mappings)
    )

def tree_remove_unreferenced_ids(tree: MaybeElementTree) -> None:
    """
    Remove all id attributes which aren't referenced by any other elements. This
    operation should leave the output identical (although it is far from perfect
    unfortunately).
    
    This may be useful to apply since certain programs add unnecessary IDs
    (*cough* inkscape *cough*).
    """
    
    seen_ids = set()
    for element in tree.iter():
        # This will match some attributes with text which happen too look like
        # id references, but honestly I don't care...
        # Notably this includes RGB hex codes, but this is only a problem if the
        # tree contains any ids that happen to look like hex codes, which I
        # don't think will be a problem.
        for name, value in element.attrib.items():
            # Note: Apparently the world doesn't know what characters are
            # actually allowed in XML IDs, so I've decided to be very lenient,
            # only dissallowing what wouldn't make sense to parse and
            # whitespace.
            pattern = r"url\(#([^#\s\"\)]+)\)|url\(\"#([^\s\"]+)\"\)"
            if name != "style":
                pattern += r"|(?:[^\(\"]|^)#([^#\s\"]+)(?:[^\"\)]|$)"
            
            for match in re.finditer(pattern, value):
                groups = match.groups(None)
                id = groups[0] or groups[1] or groups[2] or panic(f"Somehow no groups matched for '{value}'")
                seen_ids.add(id)
    
    for element in tree.iter():
        if (id := element.get("id")) is not None\
                and id not in seen_ids:
            del element.attrib["id"]
                
    
    ref_attributes = [
        "href",
        "xlink:href",
        "clip-path",
        
        "use",
        ""
    ]
    """
    Attributes which may contain ids, either with the `#<id>` or `url(#<id>)`
    syntax.
    """

def tree_get_viewbox(tree: MaybeElementTree) -> ViewBox:
    root = resolve_element_tree(tree)
    
    match ViewBox.parse_svg_value(root.attrib["viewBox"]):
        case Ok(value):
            return value
        case Error(reason):
            panic(f"Tree svg element contained invalid viewBox '{root.attrib["viewBox"]}': {reason}")

def tree_set_viewbox(tree: MaybeElementTree, value: ViewBox) -> None:
    root = resolve_element_tree(tree)
    
    root.attrib["viewBox"] = value.as_svg_value()

@dataclass
class Percentage:
    amount: float
    """The percentage, from 0 to 100 (inclusive)."""

def parse_transform_origin(origin_str: str) -> Result[tuple[float | Percentage, float | Percentage], str]:
    components = cast(list[str], re.split(r"\s+", origin_str))
    match components:
        case (single,):
            components = (single, "center")
        case (x, y):
            components = (x, y)
        case _:
            return Error(f"Invalid transform origin value: '{origin_str}'. Component amounts above two not supported")
    
    x, y = components
    
    if x in ("top", "bottom"):
        if y in ("center", "left", "right"):
            components = (y, x)
        else:
            return Error(f"Invalid transform origin value: '{origin_str}'. The first component is '{x}' while the second isn't 'center', 'left', or 'right'.")
    if y in ("left", "right"):
        if x in ("center", "top", "bottom"):
            components = (y, x)
        else:
            return Error(f"Invalid transform origin value: '{origin_str}'. The first component is '{y}' while the second isn't 'center', 'top', or 'bottom'.")
    
    def parse_component(string: str) -> Result[float | Percentage, str]:
        # Assumption: The caller has already checked that a side string is in
        # a valid position
        if string in ("center", "left", "right", "top", "bottom"):
            return Ok(Percentage(50))
        elif match := re.match(r"^(-?[0-9]+(?:.[0-9]+)?)%$", string):
            return Ok(Percentage(float(match.group(1))))
        elif match := re.match(r"^(-?[0-9]+(?:.[0-9]+)?)(?:px)?", string):
            return Ok(float(match.group(1)))
        elif re.match(r"^-?[0-9]+.*$", string):
            return Error(f"Don't know how to handle length with unit: '{string}'")
        else:
            return Error(f"Invalid transform origin component: '{string}'")
    
    match collect_results(map(parse_component, components)):
        case Error(_) as error:
            return error
        case Ok(components):
            x, y = components
            return Ok((x, y))

def get_css_property(element: ET.Element, property: str) -> str | None:
    styles = CssStyles.from_style(element.get("style", ""))
    if property in styles:
        return styles[property]
    else:
        return None

def append_css_properties(element: ET.Element, properties: CssStyles) -> None:
    styles = CssStyles(CssStyles.from_style(element.get("style", "")) | properties)
    if styles != CssStyles():
        element.set("style", styles.to_style())

def remove_css_properties(element: ET.Element, properties: set[str]) -> None:
    if "style" not in element.attrib:
        return None
    styles = CssStyles.from_style(element.get("style", ""))
    for property in properties:
        try:
            del styles[property]
        except:
            pass
    if styles == CssStyles():
        try:
            del element.attrib["style"]
        except:
            pass
    else:
        element.set("style", styles.to_style())

def get_property[T](element: ET.Element, property: str, value_type: Callable[[str], T], default: T|NotSpecifiedType = NotSpecified) -> T:
    """
    Get SVG or CSS property (from the style property), depending on which is
    set for the given element.
    If it's set in both prefer the CSS value
    """
    
    if "style" in element.attrib:
        styles = CssStyles.from_style(element.attrib["style"])
        if property in styles:
            return value_type(styles[property])
    
    if property in element.attrib:
        return value_type(element.attrib[property])
    
    if default is NotSpecified:
        panic(f"I don't know how to handle the default for property '{property}'")
    
    return default

def remove_properties(element: ET.Element, properties: set[str]) -> None:
    """
    Remove SVG attribute and CSS property from the style attribute with the
    given name `property`.
    """
    
    remove_css_properties(element, properties)
    
    for property in properties:
        if property in element.attrib:
            del element.attrib[property]

def tree_remove_properties(tree: MaybeElementTree, properties: set[str]) -> None:
    """
    Remove all instances of SVG attributes and CSS properties whose name is in
    the given set.
    """
    
    for element in tree.iter():
        remove_properties(element, properties)

def tree_find_by_class(tree: MaybeElementTree, class_: str) -> Iterable[ET.Element]:
    """
    Return iterable of all elements in tree with class.
    """
    
    return filter(lambda element: element.get("class") == class_, tree.iter())

def resolve_transform_origin(tree: MaybeElementTree, element: ET.Element, view_box: ViewBox) -> Vec2 | None:
    """
    Calculate the absolute coordinates of the elements transform origin in its
    coordinate system if the `transform-origin` property is set, otherwise None.
    """
    
    origin_str = get_property(element, "transform-origin", str, None)
    if origin_str is None:
        return None
    reference_box = get_property(element, "transform-box", str, "view-box")
    
    if reference_box not in ("content-box", "border-box", "fill-box", "stroke-box", "view-box"):
        panic(f"Invalid transform-box value: '{reference_box}'")
    match reference_box:
        case "fill-box" | "stroke-box":
            if is_basic_shape(element):
                bounds = basic_shape_pre_transform_bounds(element)
            elif is_use(element):
                bounds = use_pre_transform_bounds(tree, element)
            else:
                panic(f"Don't know how to get bounds of element: {element}")
            
            if reference_box == "stroke-box":
                stroke_width_str = get_property(element, "stroke-width", str, "1")
                if stroke_width_str.endswith("px"):
                    stroke_width_str = stroke_width_str.removesuffix("px")
                
                if not re.match(r"[0-9]+", stroke_width_str):
                    if re.match(r"[0-9]+.*", stroke_width_str):
                        panic(f"I don't know how to handle stoke widths with unit: '{stroke_width_str}'")
                    else:
                        panic(f"Invalid stroke width '{stroke_width_str}'")
                stroke_width = float(stroke_width_str)
                
                bounds = bounds.with_margin(stroke_width / 2)
        case "view-box":
            bounds = view_box.bounds()
        case "content-box" | "border-box":
            panic(f"I don't know how to handle a '{reference_box}' reference box")
        case _:
            assert_never(reference_box)
    
    match parse_transform_origin(origin_str):
        case Ok(origin):
            pass
        case Error(msg):
            panic(f"Invalid transform-origin '{origin_str}': {msg}")
    
    def realize_component(component: float|Percentage, bound_size_component: float) -> float:
        match component:
            case Percentage(value):
                return bound_size_component * (value / 100)
            case length:
                return length
    origin_offset = Vec2(*map(
        realize_component,
        origin,
        bounds.size()
    ))
    
    computed_origin = bounds.min + origin_offset
    """The absolute coordinates of the transform origin"""
    
    return computed_origin

basic_shapes = ("rect", "circle", "ellipse", "line", "polyline", "polygon", "path")
def is_basic_shape(element: ET.Element) -> bool:
    return element.tag in basic_shapes

def basic_shape_pre_transform_bounds(shape: ET.Element) -> Bounds:
    """
    Get the bounding box of a basic shape in its coordinate system before any
    transformations have been applied.
    
    It's an error to call this function with any element that isn't a basic
    shape.
    """
    
    if shape.tag not in basic_shapes:
        panic(f"element wasn't a basic shape: {shape}")
    
    if shape.tag == "rect":
        return Bounds.from_pos_size(
            Vec2(
                get_property(shape, "x", float, 0),
                get_property(shape, "y", float, 0),
            ),
            Vec2(
                get_property(shape, "width", float),
                get_property(shape, "height", float),
            ),
        )
    elif shape.tag in ("circle", "ellipse"):
        match shape.tag:
            case "circle":
                radius = Vec2.promote(
                    get_property(shape, "r", float)
                )
            case "ellipse":
                radius = Vec2(
                    get_property(shape, "rx", float),
                    get_property(shape, "ry", float),
                )
            case _:
                assert_never(shape.tag)
        
        center = Vec2(
            get_property(shape, "cx", float, 0),
            get_property(shape, "cy", float, 0),
        )
        
        return Bounds.from_pos_size(
            center - radius,
            radius * 2,
        )
    elif shape.tag == "line":
        return Bounds.from_points(
            Vec2(
                get_property(shape, "x1", float, 0),
                get_property(shape, "y1", float, 0),
            ),
            Vec2(
                get_property(shape, "x2", float, 0),
                get_property(shape, "y2", float, 0),
            ),
        )
    elif shape.tag in ("polyline", "polygon", "path"):
        match shape.tag:
            case "polyline" | "polygon":                
                points_str = get_property(shape, "points", str, "")
                if points_str == "":
                    # This is not really correct, an empty set of points should signify
                    # that rendering is disabled, but I think this is a ok substitute.
                    return Bounds.from_points(Vec2(0, 0))
                match tuple(iterator.chunks(re.split(r"[\s,]*", points_str), 2)):
                    case (first, point_pairs):
                        shape_str = " ".join((
                            "M",
                            *first,
                            *map(lambda pair: " ".join(("L", *pair)), point_pairs)
                        ))
                    case _:
                        impossible()
            case "path":
                shape_str = get_property(shape, "d", str, "")
            case _:
                assert_never(shape.tag)
        
        result = path.evaluate_commands(path.parse_str(shape_str))
        if result == None:
            # Shape was empty.
            # Again, this isn't correct.
            return Bounds.from_points(Vec2(0, 0))
        
        return result.bounds
    else:
        assert_never(shape.tag)

def is_use(element: ET.Element) -> bool:
    return element.tag == "use"

def use_pre_transform_bounds(tree: MaybeElementTree, use: ET.Element) -> Bounds:
    """
    Get the bounding box of a use element in its coordinate system before any
    transformations have been applied.
    
    It's an error to call this function with any element that isn't a use
    element.
    """
    tree = resolve_element_tree(tree)
    
    if use.tag != "use":
        panic(f"element wasn't a use element: {use}")
    
    def parse_pixel_unit(length: str) -> float:
        """
        Parse CSS or SVG length value with the px unit or without a unit, and
        return the length in pixels.
        Panics on other values.
        """
        if match := re.match(r"^((?:[0-9]*\.)?[0-9]+)(?:px)?$", length):
            return float(match.group(1))
        else:
            panic(f"Unable to parse CSS/SVG length value '{length}'. Only unitless or px values are supported.")
        
    
    width = get_property(use, "width", parse_pixel_unit, None)
    height = get_property(use, "height", parse_pixel_unit, None)
    
    x = get_property(use, "x", parse_pixel_unit, None)
    y = get_property(use, "y", parse_pixel_unit, None)
    
    if width is None or height is None or x is None or y is None:
        href = use.get("href", None)
        if href is None:
            panic(f"use element did not have href attribute while it's bounds wasn't completely defined its attributes: {use}")
        used_element_id = href.removeprefix("#")
        match tree_get_id(tree, used_element_id):
            case None:
                panic(f"Could not find element with id '{used_element_id}' referenced by use element: {use}")
            case used_element:
                if width is None:
                    width = get_property(used_element, "width", parse_pixel_unit, None)
                    if width is None:
                        panic(f"width not specified in element, I don't know how to handle the initial value 'auto': {used_element}")
                if height is None:
                    height = get_property(used_element, "height", parse_pixel_unit, None)
                    if height is None:
                        panic(f"height not specified in element, I don't know how to handle the initial value 'auto': {used_element}")
                if x is None:
                    x = get_property(used_element, "x", parse_pixel_unit, 0)
                if y is None:
                    y = get_property(used_element, "y", parse_pixel_unit, 0)
    
    
    return Bounds.from_pos_size(Vec2(x, y), Vec2(width, height))

def apply_transform_origin(tree: MaybeElementTree, element: ET.Element, view_box: ViewBox) -> None:
    """
    Remove transform-origin and transform-box properties from element attributes
    or styles and adjust any transforms so that the resulting transform is the
    same.
    You must also provide the view box that is active for the shape element.
    If transform-origin isn't set, this function is a no-op.
    """
    
    origin = resolve_transform_origin(tree, element, view_box)
    if origin is None:
        return
    
    transform = get_property(element, "transform", str, None)
    if transform is not None:
        def as_translate_str(translation: Vec2) -> str:
            components = ", ".join(map(str, translation))
            return f"translate({components})"
        
        transform = " ".join((
            as_translate_str(origin),
            transform,
            as_translate_str(-origin),
        ))
        remove_properties(element, {"transform"})
        element.attrib["transform"] = transform
    
    remove_properties(element, {"transform-box", "transform-origin"})

def tree_to_str(tree: MaybeElementTree) -> str:
    tree = tree if isinstance(tree, ET.ElementTree) else ET.ElementTree(tree)
    
    output = io.StringIO()
    tree.write(output, encoding="unicode")
    return output.getvalue()

@overload
def render_file_as_png(page: playwright.Page, svg_path: Path, out_path: Path, scale: float, max_tile_size: Vec2[int], *, progress_handler: Callable[[render.TileRenderProgress], None]|None = None) -> render.ImageTileMap: ...
@overload
def render_file_as_png(page: playwright.Page, svg_path: Path, out_path: Path, scale: float) -> None: ...
def render_file_as_png(page: playwright.Page, svg_path: Path, out_path: Path, scale: float, max_tile_size: Vec2[int]|None = None, *, progress_handler: Callable[[render.TileRenderProgress], None]|None = None) -> render.ImageTileMap|None:
    svg = ET.parse(svg_path)
    view_box = tree_get_viewbox(svg)
    
    page.set_viewport_size({
        'width': int(view_box.size.get_x() * scale),
        'height': int(view_box.size.get_y() * scale),
    })
    
    page.goto(f'file://{svg_path.absolute()}')
    
    if max_tile_size:
        return browser.render_segmented(page, max_tile_size, out_path, progress_handler=progress_handler)
    else:
        page.screenshot(path=out_path, omit_background=True, timeout=60000)
        return None

def render_file_as_pdf(page: playwright.Page, svg_path: Path, out_path: Path, scale: float):
    svg = ET.parse(svg_path)
    view_box = tree_get_viewbox(svg)

    width = int(view_box.size.get_x() * scale)
    height = int(view_box.size.get_y() * scale)
    page.set_viewport_size({
        'width': width,
        'height': height,
    })
    
    page.goto(f'file://{svg_path.absolute()}')
    
    page.emulate_media(media="screen")
    page.pdf(path=out_path, width=str(width), height=str(height))

def render_file_as_png_segmented_resvg(
    svg_path: Path,
    out_path: Path,
    scale: float,
    max_segment_size: Vec2[int],
    *,
    progress_handler: Callable[[render.TileRenderProgress], None] | None = None
) -> render.ImageTileMap:
    svg = ET.parse(svg_path)
    view_box = tree_get_viewbox(svg)
    
    # For some reason resvg doesn't scan the share directories from
    # XDG_DATA_DIRS for fonts. Since we don't know which ones contain fonts we
    # just add all of them as potential font directories.
    fonts_arguments = map(
        lambda path: f"--use-fonts-dir={path}",
        os.environ["XDG_DATA_DIRS"].split(":")
    )
    
    def renderer(area: Bounds, path: Path) -> None:
        view_box = ViewBox.from_bounds(area.scaled(1 / scale))
        
        tree_set_viewbox(svg, view_box)
        
        result = shell.run_print_and_capture_output(
            (
                "resvg",
                f"--zoom={scale}",
                # Note: resvg complains when using stdin without specifying
                # `--resources-dir` for some reason...
                "--resources-dir=/dev/null",
                "-",
                path,
                *fonts_arguments,
            ),
            input=tree_to_str(svg),
        )
        if result.stdout != "" or result.stderr != "":
            # Make sure that the next progress print doesn't override the
            # output.
            print("")
    
    result = render.render_segmented(
        area=view_box.bounds().scaled(scale),
        max_segment_size=max_segment_size,
        path=out_path,
        segment_renderer=renderer,
        progress_handler=progress_handler
    )
    
    return result
