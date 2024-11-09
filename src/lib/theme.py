from __future__ import annotations
from typing import *
from dataclasses import dataclass
import dataclasses
from colour import Color, RGB_color_picker, hash_or_str
import os
import json
import jsonschema
import pathlib

from .error import *
from .utils import *
from .font import *
from . import font as Font
from .sp_color import *
from .color import *
from . import project

__all__ = [
    "Palette",
    "Theme",
]

class HiddenColorDeclaration(TypedDict):
    hidden: Literal[True]

class SpColorDeclaration(TypedDict):
    SPColor: str

type ColorDeclaration = str | HiddenColorDeclaration
type MaybeSpColorDeclaration = ColorDeclaration | SpColorDeclaration
class PaletteDeclaration(TypedDict):
    # None values signify the color be hidden
    bg_main: MaybeSpColorDeclaration
    bg_accent: MaybeSpColorDeclaration
    
    fg_main: ColorDeclaration
    fg_1: ColorDeclaration
    fg_2: ColorDeclaration
    fg_3: ColorDeclaration
    
    outline_frame: ColorDeclaration
    outline_surface: ColorDeclaration

@dataclass
class ThemeDeclaration(TypedDict):
    font_family: str
    font_weight: int
    font_size_px: int
    colors: PaletteDeclaration

@dataclass
class Palette:
    bg_main: KeycapColor
    bg_accent: KeycapColor
    
    fg_main: HideableColor
    fg_1: HideableColor
    fg_2: HideableColor
    fg_3: HideableColor
    
    outline_frame: HideableColor
    outline_surface: HideableColor
    
    def __init__(self, declaration: PaletteDeclaration):
        def resolve_color(declaration: ColorDeclaration) -> HideableColor:
            if isinstance(declaration, str):
                return HideableColor(declaration)
            else:
                return HideableColor(hidden=True)
        
        def resolve_plastic_color(declaration: MaybeSpColorDeclaration) -> KeycapColor:
            if isinstance(declaration, dict) and "SPColor" in declaration:
                color = HideableColor(SPColor(declaration["SPColor"]).to_color())
            else:
                color = resolve_color(declaration)
            
            return KeycapColor(color)
        
        self.bg_main = resolve_plastic_color(declaration["bg_main"])
        self.bg_accent = resolve_plastic_color(declaration["bg_accent"])
        self.fg_main = resolve_color(declaration["fg_main"])
        self.fg_1 = resolve_color(declaration["fg_1"])
        self.fg_2 = resolve_color(declaration["fg_2"])
        self.fg_3 = resolve_color(declaration["fg_3"])
        self.outline_frame = resolve_color(declaration["outline_frame"])
        self.outline_surface = resolve_color(declaration["outline_surface"])
    
    # Create map of own fields to valid CSS color strings.
    def css_colors(self) -> dict[str, str]:
        result: dict[str, str] = dict()
        for field in dataclasses.fields(self):
            name = field.name
            value = getattr(self, name)
            # ! You must make sure to update this if you edit any of the field types!
            value: KeycapColor|HideableColor
            
            if isinstance(value, KeycapColor):
                result[name] = value.color.to_css_value()
                result[name + "-side"] = value.get_side().to_css_value()
            else:
                result[name] = value.to_css_value()
        
        return result
    
    def as_css_styles(self) -> CssStyles:
        return dict((f"--{name}", color) for name, color in self.css_colors().items())

@dataclass
class Theme():
    font: FontDefinition
    font_size_px: int
    colors: Palette
    
    @classmethod
    def from_declaration(cls, declaration: ThemeDeclaration) -> Self:
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
            font=font,
            font_size_px=declaration["font_size_px"],
            colors=Palette(declaration["colors"]),
        )
    
    @classmethod
    def load_file(cls, theme_path: str | os.PathLike) -> Self:
        # Why does this not exist :,(
        # type JsonValueSimple = str | int | None
        # type JsonValue = JsonValueSimple | dict[str, JsonValue] | list[JsonValue]
        
        with open(project.path_to_absolute("assets/themes/theme-schema.json")) as file:
            schema = json.load(file)
    
        path = pathlib.Path(theme_path)
        if not path.exists():
            panic(f"File '{path}' does not exist")
        
        if not path.is_file():
            panic(f"'{path}' is not a file")
        
        with open(path) as file:
            theme_object = json.load(file)
        
        try:
            jsonschema.validate(theme_object, schema)
        except jsonschema.ValidationError as error:
            panic(f"The specified theme '{theme_path}' json is invalid:\n    {error}")
        # This type cast is technically not completely sound, as the json object may
        # contain additional fields, but oh well...
        declaration = cast(ThemeDeclaration, theme_object)
        
        return cls.from_declaration(declaration)
