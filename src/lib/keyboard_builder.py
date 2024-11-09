from __future__ import annotations
from dataclasses import dataclass, field
import xml.etree.ElementTree as ET 
import functools
import damsenviet.kle as kle
from . import project
from .theme import *
from typing import *
from .error import *
from .utils import *
from .pos import *
from .svg_builder import *
from . import font as Font
from .color import *

__all__ = [
    "build_keyboard_svg",
]

def resolve_key_position(key: kle.Key) -> Pos:
    return rotate(Pos(key.x, key.y), Pos(key.rotation_x, key.rotation_y), key.rotation_angle)

# Get svg of the specified id or None if it does not exist.
def lookup_icon_id(id: str) -> SvgElement | None:
    path = project.path_to_absolute(f"assets/icons/[{id}].svg")
    if not path.is_file():
        return None
    
    with path.open() as file:
        svg = ET.parse(file)
    
    element_resolve_namespaces(svg.getroot())
    for child in svg.iter():
        element_resolve_namespaces(child)
    
    untangle_gradient_links(svg)
    
    element = svg.getroot().find(".//svg[@id='icon']")
    if element == None:
        panic(f"icon {id}'s SVG file did not contain child svg element with id 'icon'")
    
    element_resolve_namespaces(element)
    for child in element.iter():
        element_resolve_namespaces(child)
    
    element.attrib["id"] = f"icon_{id}"
    
    return SvgElement(element)
    # return SvgElement(ET.Element("svg", {
    #     "viewBox": "0 0 100 100"
    # }))

# id defaults to text
def create_text_icon_svg(text: str, id: str|None, font: Font.FontDefinition, font_size_px: int) -> SvgElement:
    id = id if id != None else text
    id = f"icon_{id}" if id != "" else "icon"
    
    text_span_element = ET.Element("tspan")
    text_span_element.text = text
    
    centered_y = 100 / 2 + (font_size_px * font.metrics.cap_center_offset())
    
    text_element = ET.Element("text", {
        "style": f"font-weight:{font.weight};font-size:{font_size_px}px;font-family:{font.family};fill:url(#fg_main);",
        "x": "50",
        "y": str(centered_y),
        "text-anchor": "middle",
    })
    text_element.append(text_span_element)
    
    bounding_box_element = ET.Element("rect", {
        "class": "icon-bounding-box",
        "width": "100",
        "height": "100",
        "fill": "none",
    })
    
    root = ET.Element("svg", {
        "id": id,
        "viewBox": "0 0 100 100",
        "width": "100",
        "height": "100",
        "style": "overflow:visible;",
    })
    root.append(bounding_box_element)
    root.append(text_element)
    
    return SvgElement(root)

class KeycapInfo:
    icon_id: str
    # In u units
    major_size: float
    orientation: Orientation
    # CSS color of background
    color: str
    
    def __init__(self, key: kle.Key) -> None:
        # We only consider the value of the central label for looking up the icon
        # id/generating the icon text.
        label = key.labels[4]
        self.icon_id = label.text
        
        if key.height == 1:
            self.orientation = Orientation.HORIZONTAL
            self.major_size = key.width
        elif key.width == 1:
            self.orientation = Orientation.VERTICAL
            self.major_size = key.height
        else:
            panic(f"Key '{label}' was not 1u in either width or height, given key dimensions: ({key.width}, {key.width})")
        
        self.color = key.color
     
    # Get size in '_u' notation, ex: 1u, 1.5u
    def size_u(self) -> str:
        size = float(f"{float(self.major_size):.2}")
        return f"{size}".removesuffix(".0") + "u"

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
    
    def create(self, key: KeycapInfo) -> SizedElement:
        dimensions = Scaling(100, 100)
        match key.orientation:
            case Orientation.HORIZONTAL:
                dimensions.x = key.major_size * 100
            case Orientation.VERTICAL:
                dimensions.y = key.major_size * 100
        
        frame_pos = Pos(0, 0)
        frame_rotation = Rotation(0)
        match key.orientation:
            case Orientation.HORIZONTAL:
                pass
            case Orientation.VERTICAL:
                frame_rotation += 90
                frame_pos.x += 100
        
        frame = self.templates.create_symbol_element(
            key.size_u(),
            Placement(
                translate=frame_pos,
                rotate=frame_rotation
            ),
            (100 * key.major_size, 100),
        )
        if isinstance(frame, Error):
            panic(f"Key size '{key.size_u()}' which was not one of the size defined in given key templates set: {self.templates.symbols.keys()}")
        frame.attrib["class"] = f"keycap-color-{key.color}"

        # Based on dimensions of the #1u template element in assets/templates/frame-templates.svg.
        # Is surface size divided by frame size
        # TODO: Move this somewhere else?
        icon_surface_size_ratio = 36 / 54
        
        # Icon is an svg with a viewbox of "0 0 100 100"
        icon = lookup_icon_id(key.icon_id)
        if icon == None:
            icon = create_text_icon_svg(key.icon_id, None, self.theme.font, self.theme.font_size_px)
        icon.set_size(Scaling(icon_surface_size_ratio))
        
        centered_pos = dimensions.as_pos() / 2
        
        icon_pos = centered_pos - icon.size.as_pos()/2
        
        icon.element.attrib["x"] = str(icon_pos.x)
        icon.element.attrib["y"] = str(icon_pos.y)
        
        group = ET.Element("g")
        group.append(frame)
        group.append(icon.element)
        
        return SizedElement(group, dimensions)

# TODO: Should probably move this to svg_builder.py
@dataclass
class PlacedComponent():
    element: SizedElement
    transform: Transform = field(default_factory=lambda: Transform.identity())
    
    def realize(self) -> ET.Element:
        element = self.element.element
        element.attrib["transform"] = self.transform.to_svg_value()
        
        return element
    
    def bounds(self) -> Bounds:
        return Box(
            self.transform.get_translation(),
            self.element.size,
            self.transform.get_rotation(),
            Pos(0, 0)
        ).bounds()

@dataclass
class KeyboardBuilder():
    theme: Theme
    # Pixels per u
    unit_px: int
    key_templates: SvgSymbolSet
    _factory: KeycapFactory = cast(Never, None) # Is initialized in __post_init__
    _components: list[PlacedComponent] = field(default_factory=lambda: [])
    _builder_extra: Callable[[SvgDocumentBuilder], Any]|None = None
    
    def __post_init__(self):
        self._factory = KeycapFactory(self.key_templates, self.theme)
    
    def key(self, key: kle.Key) -> Self:
        element = self._factory.create(KeycapInfo(key))
        pos = resolve_key_position(key) * self.unit_px
        
        return self.component(PlacedComponent(element, Transform(
            translate=pos,
            rotate=Rotation(key.rotation_angle),
            scale=Scaling(self.unit_px/100),
        )))
    
    def keys(self, *keys: kle.Key) -> Self:
        for key in keys:
            self.key(key)
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
            map(PlacedComponent.bounds, self._components),
        )
        
        # Magic Number: Extra whitespace around generated keymap in pixels.
        padding = 100
        
        viewbox = ViewBox.from_bounds(bounds).add_padding(padding)

        builder = SvgDocumentBuilder()\
            .set_viewbox(viewbox)\
            .palette(self.theme.colors)\
            .add_icon_set(self._factory.templates)
        
        # Make sure that the CSS rule selectors match the property names!
        assert hasattr(self.theme.colors, "bg_main")
        assert hasattr(self.theme.colors, "bg_accent")
        builder.add_element(
            SvgStyleBuilder()\
                .indentation(1, " ")\
                .statement(Font.generate_css_rule(self.theme.font))\
                .rule(CssRule(".keycap-color-bg_main", {
                    "--top-surface": "url(#bg_main)",
                    "--main-body": "url(#bg_main-side)"
                }))
                .rule(CssRule(".keycap-color-bg_accent", {
                    "--top-surface": "url(#bg_accent)",
                    "--main-body": "url(#bg_accent-side)"
                }))
                # .rule(
                #     ".icon-bounding-box {stroke: red; stroke-width: 1px;}"
                # )\
                .build()
        )
        
        builder.add_elements(component.realize() for component in self._components)
        
        if self._builder_extra:
            self._builder_extra(builder)
        
        return builder.build()

def build_keyboard_svg(keyboard: kle.Keyboard, unit: int, theme: Theme, key_templates: SvgSymbolSet) -> ET.ElementTree:
    return (KeyboardBuilder(theme, unit, key_templates)\
        .keys(*keyboard.keys)\
        # TODO: This is pretty hacky
        .builder_extra(lambda builder: \
            builder.root_styles(theme.colors.as_css_styles() | {
                "--top-surface-stroke": "var(--outline_surface)",
                "--main-body-stroke": "var(--outline_frame)",
                "--top-surface": "none",
                "--main-body": "none",
            }))\
        .build())
