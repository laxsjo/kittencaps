from __future__ import annotations
from typing import *
from dataclasses import dataclass, asdict
import dataclasses
import os
import json5
import jsonschema
import pathlib

from .error import *
from .utils import *
from .font import *
from . import font as Font
from .sp_color import *
from .color import *
from . import project, kle_ext as kle

__all__ = [
    "Palette",
    "Theme",
    "Args",
    "Config",
]

class HiddenColorDeclaration(TypedDict):
    hidden: Literal[True]

class SpColorDeclaration(TypedDict):
    SPColor: str

type ColorDeclaration = str | HiddenColorDeclaration
type MaybeSpColorDeclaration = ColorDeclaration | SpColorDeclaration
type PaletteDeclaration = dict[str, MaybeSpColorDeclaration]

@dataclass
class ThemeDeclaration(TypedDict):
    font_family: str
    font_weight: int
    font_size_px: int
    unit_size: float
    base_size: float
    top_size: float
    colors: PaletteDeclaration

class Palette(dict[str, HideableColor]):
    
    def __init__(self, declaration: PaletteDeclaration):
        def resolve_color(declaration: ColorDeclaration) -> HideableColor:
            if isinstance(declaration, str):
                return HideableColor(declaration)
            else:
                return HideableColor(hidden=True)
        
        def resolve_plastic_color(declaration: MaybeSpColorDeclaration) -> HideableColor:
            if isinstance(declaration, dict) and "SPColor" in declaration:
                color = HideableColor(SPColor(declaration["SPColor"]).to_color())
            else:
                color = resolve_color(declaration)
            
            return color
        
        for name, color_declaration in declaration.items():
            self[name] = resolve_plastic_color(color_declaration)
    
    # Return list of keycap colors in self, i.e. those that start with "bg_"
    def keycap_colors(self) -> Iterable[tuple[str, HideableColor]]:
        return filter(lambda pair: pair[0].startswith("bg_"), self.items())
    
    # Create map of own fields to valid CSS color strings.
    def css_colors(self) -> dict[str, str]:
        return dict((name, value.to_css_value()) for name, value in self.items())
    
    def as_css_styles(self) -> CssStyles:
        return CssStyles((f"--{name}", color) for name, color in self.css_colors().items())

@dataclass
class Theme():
    default_font: FontDefinition
    font_family: list[FontDefinition]
    font_size_px: float
    unit_size: float
    base_size: float
    top_size: float
    colors: Palette
    
    @classmethod
    def from_declaration_and_layout(cls, declaration: ThemeDeclaration) -> Self:
        match Font.get_system_family(declaration["font_family"]):
            case Error(_):
                panic(f"Font '{declaration["font_family"]}' is not installed")
            case Ok(fonts):
                
                matching_fonts = list(font for font in fonts if font.weight == str(declaration["font_weight"]))
                
                if len(matching_fonts) == 0:
                    panic(
                        f"Font weight '{declaration["font_weight"]}' is not installed for font '{declaration["font_family"]}'. "
                        f"Found weights: {list(font.weight for font in fonts)}"
                    )
                
                font = matching_fonts[0]
        
        return cls(
            default_font=font,
            font_family=fonts,
            font_size_px=declaration["font_size_px"],
            unit_size=declaration["unit_size"],
            base_size=declaration["base_size"],
            top_size=declaration["top_size"],
            colors=Palette(declaration["colors"]),
        )
    
    @classmethod
    def load_file(cls, theme_path: str | os.PathLike) -> Self:
        # Why does this not exist :,(
        # type JsonValueSimple = str | int | None
        # type JsonValue = JsonValueSimple | dict[str, JsonValue] | list[JsonValue]
        
        with open(project.path_to_absolute("assets/schemas/theme-schema.json")) as file:
            schema = json5.load(file)
        
        path = pathlib.Path(theme_path)
        if not path.exists():
            panic(f"File '{path}' does not exist")
        
        if not path.is_file():
            panic(f"'{path}' is not a file")
        
        with open(path) as file:
            theme_object = json5.load(file)
        
        try:
            jsonschema.validate(theme_object, schema)
        except jsonschema.ValidationError as error:
            panic(f"The specified theme '{theme_path}' json is invalid:\n    {error}")
        # This type cast is technically not completely sound, as the json object may
        # contain additional fields, but oh well...
        declaration = cast(ThemeDeclaration, theme_object)
        
        return cls.from_declaration_and_layout(declaration)

@dataclass
class Args():
    preview_scale: float|None
    texture_scale: float|None
    print_outlined_scale: float|None
    print_scale: float|None

@dataclass
class Config:
    # From theme file
    default_font: FontDefinition
    font_family: list[FontDefinition]
    font_size_px: float
    unit_size: float
    base_size: float
    top_size: float
    colors: Palette
    # From layout file
    icon_margin: float
    
    preview_scale: float
    """Amount to scale the resolution of preview.png by."""
    texture_scale: float
    """Amount to scale the resolution of texture.png by."""
    print_outlined_scale: float
    """Amount to scale the resolution of print-outlined.png by."""
    print_scale: float
    """Amount to scale the resolution of print.png by."""
    
    @classmethod
    def from_parts(cls, *, theme: Theme, layout: kle.ExtendedKeyboard, args: Args) -> Self:
        return cls(
            default_font=theme.default_font,
            font_family=theme.font_family,
            font_size_px=theme.font_size_px,
            unit_size=theme.unit_size,
            base_size=theme.base_size,
            top_size=theme.top_size,
            colors=theme.colors,
            icon_margin=layout.icon_margin,
            preview_scale=layout.scale if args.preview_scale is None else args.preview_scale,
            texture_scale=layout.scale if args.texture_scale is None else args.texture_scale,
            print_outlined_scale=layout.scale if args.print_outlined_scale is None else args.print_outlined_scale,
            print_scale=layout.scale if args.print_scale is None else args.print_scale,
        )
    
    def as_theme(self) -> Theme:
        return Theme(
            default_font=self.default_font,
            font_family=self.font_family,
            font_size_px=self.font_size_px,
            unit_size=self.unit_size,
            base_size=self.base_size,
            top_size=self.top_size,
            colors=self.colors,
        )