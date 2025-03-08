from __future__ import annotations
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET 
import functools
import damsenviet.kle as kle
import itertools
import re

from . import project, magic
from .theme import *
from typing import *
from .error import *
from .utils import *
from .pos import *
from .svg_builder import *
from . import svg
from . import font as Font
from .color import *

__all__ = [
    "KeycapGeometry",
    "KeycapInfo",
    "create_keycap_mask",
    "create_text_icon_svg",
    "place_keys",
    "border_from_bounds",
    "build_keyboard_svg",
]

def resolve_key_position(key: kle.Key) -> Vec2:
    return rotate(Vec2(key.x, key.y), Vec2(key.rotation_x, key.rotation_y), key.rotation_angle)

# Get svg of the specified id or None if it does not exist.
def lookup_icon_id(id: str, defs: DefsSet) -> SvgElement | None:
    path = project.path_to_absolute(f"assets/icons/[{id}].svg")
    if not path.is_file():
        return None
    
    with path.open() as file:
        svg = ET.parse(file)
    
    for element in svg.iter():
        element_resolve_namespaces(element)
    
    # This is required if the file has been edited with Inkscape.
    untangle_gradient_links(svg)
    
    element = svg.getroot().find(".//svg[@id='icon']")
    if element == None:
        panic(f"icon {id}'s SVG file did not contain child svg element with id 'icon'")
    
    element.attrib["id"] = f"icon_{id}"
    
    defs.extract_references_from_element_in_tree(element, svg)
    
    return SvgElement(element)

# id defaults to text
def create_text_icon_svg(text: str, id: str|None, keycap_size: Vec2, font: Font.FontDefinition, font_size_px: float, foreground_color: str|None) -> SvgElement:
    id = id if id != None else text
    id = f"icon_{id}" if id != "" else "icon"
    
    text_span_element = ET.Element("tspan")
    text_span_element.text = text
    
    size = keycap_size * 100
    
    centered_y = size.y / 2 + (font_size_px * float(font.metrics.cap_center_offset()))
    
    text_element = ET.Element("text", {
        "style":
            f"font-weight:{font.weight};"
            f"font-size:{font_size_px}px;"
            f"font-family:{font.family};"
            f"fill:url(#{foreground_color or "fg_main"});"
            f"white-space:normal;"
            f"white-space-collapse:collapse;"
            f"text-wrap:nowrap;",
        "x": number_to_str(size.x / 2),
        "y": number_to_str(centered_y),
        "text-anchor": "middle",
        "xml:space": "preserve",
    })
    text_element.append(text_span_element)
    
    root = ET.Element("svg", {
        "id": id,
        "viewBox": f"0 0 {" ".join(map(number_to_str, size))}",
        "width": number_to_str(size.x),
        "height": number_to_str(size.y),
        "style": "overflow:visible;",
    })
    root.append(text_element)
    
    return SvgElement(root)

@dataclass
class KeycapGeometry:
    major_size: float
    orientation: Orientation

    # Returns None if neither of dimensions components are equal to 1u
    @classmethod
    def from_dimensions(cls, dimensions: Vec2) -> Self|None:
        if dimensions.y == 1:
            return cls(dimensions.x, Orientation.HORIZONTAL)
        elif dimensions.x == 1:
            return cls(dimensions.y, Orientation.VERTICAL)
        else:
            return None
    
    # Get major size in '_u' notation, ex: 1u, 1.5u
    def size_u(self) -> str:
        size = float(f"{float(self.major_size):.2}")
        return f"{size}".removesuffix(".0") + "u"

class KeycapInfo:
    icon_id: str
    # In u units
    major_size: float
    orientation: Orientation
    # CSS color of background
    color: str
    color_mappings: list[Tuple[str, str]]
    """A list of tuples where all instances of the first color name should be
    replaced by the second color names."""
    foreground_color: str|None = None
    """The color name which this keys text should default to if given. If any
    color_mappings have been specified this is always `None`."""
    
    def __init__(self, key: kle.Key) -> None:
        # We only consider the value of the central label for looking up the icon
        # id/generating the icon text.
        label = key.labels[4]
        self.icon_id = label.text
        
        geometry = KeycapGeometry.from_dimensions(Vec2(key.width, key.height))
        if geometry is None:
            panic(f"Key '{label}' was not 1u in either width or height, given key dimensions: ({key.width}, {key.width})")
        
        self.orientation = geometry.orientation
        self.major_size = geometry.major_size
        self.color = key.color
        self.color_mappings = []
        self.foreground_color = None
        
        if re.match(r".*->.*(;.*->.*)*", key.default_text_color):
            # This is sort of an abuse of the KLE format:
            # If the key foreground color is set to a string with the grammar
            # `<color-name> "->" <color-name> (";" <color-name> "->" <color-name>)*`,
            # we then interpret that as a list of tuples where all instances of
            # the first color name will be replaced with the color described by
            # the second color name.
            # Note: The replacements are done all at once, meaning that
            # for instance, if we have two mappings of X -> Y and Y -> Z, places
            # that use the color X will only be replaced by Y, and *not* Z.
            for mapping_str in key.default_text_color.split(";"):
                old, new = mapping_str.split("->")
                self.color_mappings.append((old, new))
        else:
            # A foreground color of pure black is considered to be specifying
            # the default color.
            if key.default_text_color == "#000000":
                self.foreground_color = None
            else:
                self.foreground_color = key.default_text_color 
    
    # Get size in '_u' notation, ex: 1u, 1.5u
    def size_u(self) -> str:
        size = float(f"{float(self.major_size):.2}")
        return f"{size}".removesuffix(".0") + "u"

# Create mask for keycap bounding box
def create_keycap_mask(size_u: str, theme: Theme) -> ET.Element:
    id = f"_{size_u}-base"
    
    size = float(size_u.removesuffix("u"))
    
    offset = (theme.unit_size - theme.base_size) / 2
    width = theme.unit_size * size - offset * 2
    height = theme.base_size
    
    rect = ET.Element("rect", {
        "width": f"{width:g}",
        "height": f"{height:g}",
        "x": f"{offset:g}",
        "y": f"{offset:g}",
        "fill": "white",
    })
    
    mask = ET.Element("mask", {
        "id": id,
    })
    mask.append(rect)
    
    return mask

@dataclass
class KeycapFactory:
    """
        Creates svg elements of keycaps. The created element is 100x100 px in size
        (assuming that the keycap is 1u in size).
        
        ```
        ,-origin                    ,-origin
        +----------------------+    +----------+
        |                      |    |          |
        |                      |    |          |
        |        symbol        |    |          |
        |                      |    |          |
        |                      |    |  symbol  |
        +----------------------+    |          |
                                    |          |
                                    |          |
                                    |          |
                                    +----------+
        ```
    """
    
    templates: SvgSymbolSet
    theme: Theme
    _defs: DefsSet = field(init=False)
    _masks: dict[str, ET.Element] = field(default_factory=lambda: {})
    _shading_masks: dict[str, ET.Element] = field(default_factory=lambda: {})
    
    def __post_init__(self):
        self._defs = DefsSet(
            skipped_ids=set(self.theme.colors.keys())
        )
    
    # Creates a mask and return its id
    def _get_size_mask(self, size_u: str) -> str:
        if size_u in self._masks:
            return self._masks[size_u].attrib["id"]
        
        mask = create_keycap_mask(size_u, self.theme)
        
        self._masks[size_u] = mask
        return mask.attrib["id"]
    
    # Creates a mask and return its id
    def _get_shading_mask(self, size_u: str) -> str:
        if size_u in self._shading_masks:
            return self._shading_masks[size_u].attrib["id"]
        
        id = f"_{size_u}-shading"
        
        size = float(size_u.removesuffix("u"))
        
        offset = (self.theme.unit_size - self.theme.top_size) / 2
        width = self.theme.unit_size * size - offset * 2
        height = self.theme.top_size
        
        bg = ET.Element("rect", {
            "width": f"{self.theme.unit_size * size:g}",
            "height": f"{self.theme.unit_size:g}",
            "fill": "white",
        })
        
        top_surface = ET.Element("use", {
            "width": f"{width:g}",
            "height": f"{height:g}",
            "x": f"{offset:g}",
            "y": f"{offset:g}",
            "href": f"#_{size_u}-top",
            "fill": "black",
        })
        
        mask = ET.Element("mask", {
            "id": id,
        })
        mask.append(bg)
        mask.append(top_surface)
        
        self._shading_masks[size_u] = mask
        return id
    
    def get_defs(self) -> Iterable[ET.Element]:
        return itertools.chain(
            (value for _, value in sorted(self._masks.items())),
            (value for _, value in sorted(self._shading_masks.items())),
            self._defs.defs,
        )
    
    def create(self, key: KeycapInfo) -> SizedElement:
        unit = self.theme.unit_size
        
        dimensions = Scaling(unit)
        match key.orientation:
            case Orientation.HORIZONTAL:
                dimensions.x *= key.major_size
            case Orientation.VERTICAL:
                dimensions.y *= key.major_size
        
        frame_pos = Vec2(0, 0)
        frame_rotation = Rotation(0)
        match key.orientation:
            case Orientation.HORIZONTAL:
                pass
            case Orientation.VERTICAL:
                frame_rotation += 90
                frame_pos.x += unit
        
        base = ET.Element("rect", {
            "class": "surface",
            "width": f"{unit * key.major_size:g}",
            "height": f"{unit:g}",
        })
        
        # A 1u icon is an svg with a viewbox of "0 0 100 100"
        if (match := re.match(r"\[(.*)\]", key.icon_id)):
            id = match.group(1)
            icon = lookup_icon_id(id, self._defs)
            if icon is None:
                panic(f"Could not find icon '{key.icon_id}'")
        else:
            icon = create_text_icon_svg(key.icon_id, None, Vec2(1, 1), self.theme.default_font, self.theme.font_size_px, key.foreground_color)
        if key.color_mappings:
            mappings = dict(map(
                lambda pair: (f"#{pair[0]}", f"#{pair[1]}"),
                key.color_mappings
            ))
            svg.tree_replace_in_attributes(icon.element, mappings)
        icon.set_scale(Scaling(self.theme.unit_size / 100))
        
        center_pos = dimensions.as_vec2() / 2
        icon_pos = center_pos - icon.size.as_vec2() / 2
        
        icon.element.attrib["x"] = f"{icon_pos.x:g}"
        icon.element.attrib["y"] = f"{icon_pos.y:g}"
        
        icon_wrapper = ET.Element("g")
        icon_wrapper.append(icon.element)
        element_apply_transform(icon_wrapper, Placement(
            translate=frame_pos.swap(),
            rotate=-frame_rotation
        ))
        
        unshaded_group = ET.Element("g", {
            "id": get_unique_id("keycap-unshaded")
        })
        unshaded_group.append(base)
        unshaded_group.append(icon_wrapper)
        
        shading = ET.Element("use", {
            "href": f"#{unshaded_group.get("id")}",
            "mask": f"url(#{self._get_shading_mask(key.size_u())})",
            "filter": "url(#sideShading)",
        })
        
        group = ET.Element("g", {
            "class": f"keycap-color-{key.color}",
            "mask": f"url(#{self._get_size_mask(key.size_u())})",
        })
        element_apply_transform(group, Placement(
            translate=frame_pos,
            rotate=frame_rotation
        ))
        group.append(unshaded_group)
        group.append(shading)
        
        return SizedElement(group, dimensions)

# TODO: Should probably move this to svg_builder.py
@dataclass
class PlacedComponent():
    element: SizedElement
    transform: Transform = field(default_factory=lambda: Transform.identity())
    
    def realize(self) -> ET.Element:
        element = self.element.element
        element_apply_transform(element, self.transform)
        
        return element
    
    def bounds(self) -> Bounds:
        return Box(
            self.transform.get_translation(),
            self.element.size * self.transform.get_scaling(),
            self.transform.get_rotation(),
            self.transform.get_translation(),
        ).bounds()

def border_from_bounds(bounds: Bounds | svg.ViewBox) -> ET.Element:
    viewbox = svg.ViewBox.from_bounds(bounds) if isinstance(bounds, Bounds) else bounds
    return ET.Element("rect", {
        "width": str(viewbox.size.get_x()),
        "height": str(viewbox.size.get_y()),
        "x": str(viewbox.pos.x),
        "y": str(viewbox.pos.y),
        "stroke": "red",
        "fill": "rgba(255, 0, 0, 0.2)",
    })

def place_keys[T](keys: Iterable[kle.Key], unit_size: float, placer: Callable[[KeycapInfo, Transform], T]) -> list[T]:
    result: list[T] = []
    for key in keys:
        pos = resolve_key_position(key) * unit_size
        
        result.append(placer(KeycapInfo(key), Transform(
            translate=pos,
            rotate=Rotation(key.rotation_angle),
        )))
    
    return result

@dataclass
class KeyboardBuilder():
    theme: Theme
    key_templates: SvgSymbolSet
    _factory: KeycapFactory = field(init=False)
    _components: list[PlacedComponent] = field(default_factory=lambda: [])
    _builder_extra: Callable[[SvgDocumentBuilder], Any]|None = None
    
    def __post_init__(self):
        self._factory = KeycapFactory(self.key_templates, self.theme)
    
    def keys(self, *keys: kle.Key) -> Self:
        def placer(key: KeycapInfo, transform: Transform) -> None:
            element = self._factory.create(key)
            
            self.component(PlacedComponent(element, transform))
        place_keys(keys, self.theme.unit_size, placer)
        
        return self
    
    def component(self, *components: PlacedComponent) -> Self:
        self._components.extend(components)
        return self
    
    def unit(self, unit: int) -> Self:
        self._unit = unit
        return self
    
    def builder_extra(self, callback: Callable[[SvgDocumentBuilder], Any]) -> Self:
        self._builder_extra = callback
        return self
    
    def build(self) -> ET.ElementTree:
        bounds = functools.reduce(
            Bounds.combine,
            (component.bounds() for component in self._components),
        )
        
        viewbox = svg.ViewBox.from_bounds(bounds).add_padding(magic.padding)

        builder = SvgDocumentBuilder()\
            .set_viewbox(viewbox)\
            .palette(self.theme.colors)\
            .add_icon_set(self._factory.templates)\
            .add_element(make_element(
                "defs",
                {
                    "id": "factory-elements",
                },
                self._factory.get_defs()
            ))\
            # .add_element(border_from_bounds(viewbox))
        
        builder.add_element(
            SvgStyleBuilder()
                .indentation(1, "  ")
                .attributes(dict(
                    id="fonts",
                ))
                .statement(*map(Font.generate_css_rule, self.theme.font_family))
                .build()
        )
        builder.add_element(
            SvgStyleBuilder()
                .indentation(1, "  ")
                .attributes(dict(
                    id="surface-colors",
                ))
                .rule(*(
                    CssRule(f".keycap-color-{name} .surface", CssStyles({
                        "fill": f"url(#{name})",
                    }))
                    for name, color in self.theme.colors.keycap_colors()
                ))
                # .rule(
                #     ".icon-bounding-box {stroke: red; stroke-width: 1px;}"
                # )\
                .build()
        )
        
        builder.add_elements(component.realize() for component in self._components)
        
        if self._builder_extra:
            self._builder_extra(builder)
            
        # Visualize keycap bounds
        # builder.add_elements(border_from_bounds(component.bounds()) for component in self._components)
        
        return builder.build()

def build_keyboard_svg(keyboard: kle.Keyboard, theme: Theme, key_templates: SvgSymbolSet) -> ET.ElementTree:
    return (KeyboardBuilder(theme,  key_templates)\
        .keys(*keyboard.keys)\
        .build())
