from __future__ import annotations
from typing import *
from dataclasses import dataclass
import math
import re
from colour import Color, RGB_color_picker, hash_or_str

from .error import *
from .utils import *
from .pos import *

__all__ = [
    "CssStyles",
    "CssStatement",
    "CssRule",
    "HideableColor",
    "KeycapColor",
]

# TODO: move out CSS stuff
class CssStyles(dict[str, str]):
    @classmethod
    def from_style(cls, style: str) -> Self:
        statements = list(filter(lambda x: x != "", (statement.strip() for statement in style.split(";"))))
        if len(statements) == 1 and statements[0] == "":
            return cls()
        return cls(
            re.split(r"\s*:\s*", statement, 1)
            for statement in statements
        )
    
    def to_style(self) -> str:
        return ";".join(f"{name}:{value}" for name, value in self.items())

# Definitely arguable if this class should exist
@dataclass
class CssStatement():
    content: str
    
    def realize(self) -> str:
        return self.content.removesuffix("\n")

@dataclass
class CssRule():
    selector: str
    styles: CssStyles
    
    def realize(self) -> str:
        style_lines = (f"  {name}: {value};\n" for name, value in self.styles.items())
        return (
            self.selector + " {\n" +
            "".join(style_lines) +
            "}"
        )
            

class HideableColor(Color):
    _hidden: bool
    
    def __init__(self, color=None,
                 pick_for=None, picker=RGB_color_picker, pick_key=hash_or_str,
                 hidden=False,
                 **kwargs):
        Color.__init__(self, color, pick_for, picker, pick_key, **kwargs)
        
        if isinstance(color, HideableColor):
            self.hidden = color.hidden
        self.hidden = hidden
    
    def get_hidden(self) -> bool:
        return self._hidden
    def set_hidden(self, hidden: bool):
        object.__setattr__(self, "_hidden", hidden)
    
    def to_css_value(self) -> str:
        return "none" if self.hidden else self.hex
    
    def as_linear_vec3(self) -> Vec3 | None:
        if self.hidden:
            return None
        
        return Vec3(*(c ** 2.2 for c in self.rgb))
    
    @classmethod
    def from_linear_vec3(cls, linear_color: Vec3) -> Self:
        result = cls()
        result.rgb = tuple(c ** (1/2.2) for c in linear_color)
        return result
        

@dataclass
class KeycapColor:
    color: HideableColor
    
    # Get color the keycap's side faces: color but darkened slightly
    # TODO: Unused, should probably remove
    def get_side(self) -> HideableColor:
        # We assume that the top surface has an angle of 90 degrees, which means that
        # self.color represents the surface when fully lit.
        
        surface_color = self.color.as_linear_vec3()
        if surface_color == None:
            return HideableColor(hidden=True)
        
        light_color = unwrap(HideableColor("#FFFFFF").as_linear_vec3())
        ambient_strength = 0.5
        ambient_light = light_color * ambient_strength
        
        light_angle = -math.pi/2 # -90 degrees
        side_angle = math.radians(10)
        
        # 2D cross product
        light_fraction = max(
            math.cos(side_angle) * math.cos(-light_angle)
            + math.sin(side_angle) * math.sin(-light_angle),
            0.0
        )
        
        diffuse_light = light_color * light_fraction
        
        result = (ambient_light + diffuse_light) * surface_color
        
        return HideableColor.from_linear_vec3(result)
