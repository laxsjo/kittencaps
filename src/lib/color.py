from __future__ import annotations
from typing import *
from dataclasses import dataclass
from colour import Color, RGB_color_picker, hash_or_str

from .error import *
from .utils import *

__all__ = [
    "CssStyles",
    "CssStatement",
    "CssRule",
    "HideableColor",
    "KeycapColor",
]

# TODO: move out CSS stuff
type CssStyles = dict[str, str]

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

@dataclass
class KeycapColor:
    color: HideableColor
    
    # Get color the keycap's side faces: color but darkened slightly
    def get_side(self) -> HideableColor:
        return HideableColor(
            self.color,
            saturation=self.color.hsl[1]*0.6,
            luminance=self.color.hsl[2]*0.8
        )
