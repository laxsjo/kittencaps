from __future__ import annotations
from typing import *
from dataclasses import dataclass
import math
import re
from coloraide import Color
from coloraide.types import ColorInput, VectorLike
import coloraide.util as color_util

from .error import *
from .utils import *
from .pos import *

__all__ = [
    "CssStyles",
    "CssStatement",
    "CssRule",
    "css_parse_url",
    "HideableColor",
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

# Parse a "url" css value, and return the found content inside the "url(*)"
# statement, with any escape sequences or surrounding quotes resolved, or `None`
# if the value is not a "url" value.
def css_parse_url(value: str) -> str|None:
    value = value.strip()
    if not value.startswith("url(") or not value.endswith(")"):
        return None
    
    value = value\
        .removeprefix("url(")\
        .removesuffix(")")\
        .strip()
    
    if re.match(r"^\".*[^\\]\"$|^\"\"$", value):
        value = value.removeprefix("\"").removesuffix("\"")
    if re.match(r"^'.*[^\\]'$|^''$", value):
        value = value.removeprefix("'").removesuffix("'")
    
    return re.sub(r"\\(.)", r"\1", value)

class HideableColor(Color):
    hidden: bool
    
    @overload
    def __init__(
        self,
        color: ColorInput,
        data: VectorLike | None = None,
        alpha: float = color_util.DEF_ALPHA,
        hidden: Literal[False] = False,
        **kwargs: Any
    ):
        ...
    @overload
    def __init__(
        self,
        color: ColorInput | None = None,
        data: VectorLike | None = None,
        alpha: float = color_util.DEF_ALPHA,
        hidden: Literal[True] = True,
        **kwargs: Any
    ):
        ...
    def __init__(
        self,
        color: ColorInput|None = None,
        data: VectorLike | None = None,
        alpha: float = color_util.DEF_ALPHA,
        hidden: bool = False,
        **kwargs: Any
    ):
        if color == None:
            if hidden == False:
                panic("Non-hidden colors need to specify color argument")
            color = "#000000"
        
        Color.__init__(self, color, data, alpha, **kwargs)
        
        if isinstance(color, HideableColor):
            self.hidden = color.hidden
        self.hidden = hidden
    
    def to_css_value(self) -> str:
        return (
            "none" if self.hidden else
            self.to_string(hex=True) if self.space() == "srgb" else
            self.to_string()
        )
    
    def as_linear_vec3(self) -> Vec3 | None:
        if self.hidden:
            return None
        
        return Vec3(*self.convert("srgb-linear")[:3])
    
    @staticmethod
    def from_linear_vec3(linear_color: Vec3) -> HideableColor:
        return HideableColor(Color("srgb-linear", linear_color).convert("srgb"))
