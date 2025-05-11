from __future__ import annotations
from dataclasses import dataclass
from typing import *
from pathlib import Path
import os
import base64
from fontTools import ttLib
from fontTools.pens.boundsPen import BoundsPen
from decimal import Decimal
import functools

from .utils import *
from .error import *
from . import shell
from .svg_builder import *
from .pos import *
from .color import *

__all__ = [
    "FontMetrics",
    "FontDefinition",
    "get_system_family",
    "generate_css_rule",
]

# fc weight to css weight
_fc_weight_mapping = {
    "0": "100", # FC_WEIGHT_THIN
    "40": "200", # FC_WEIGHT_EXTRALIGHT
    "50": "300", # FC_WEIGHT_LIGHT
    "55": "350", # FC_WEIGHT_DEMILIGHT, FC_WEIGHT_SEMILIGHT
    "75": "380", # FC_WEIGHT_BOOK
    "80": "400", # FC_WEIGHT_REGULAR, FC_WEIGHT_NORMAL
    "100": "500", # FC_WEIGHT_MEDIUM
    "180": "600", # FC_WEIGHT_DEMIBOLD, FC_WEIGHT_SEMIBOLD
    "200": "700", # FC_WEIGHT_BOLD
    "205": "800", # FC_WEIGHT_EXTRABOLD, FC_WEIGHT_ULTRABOLD
    "210": "900", # FC_WEIGHT_BLACK, FC_WEIGHT_HEAVY
    "215": "1000", # FC_WEIGHT_EXTRABLACK, FC_WEIGHT_ULTRABLACK
}

from fontTools.ttLib.tables._h_e_a_d import table__h_e_a_d
from fontTools.ttLib.tables._h_h_e_a import table__h_h_e_a
from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
from fontTools.ttLib.ttGlyphSet import _TTGlyphSetVARC, _TTGlyphSetCFF, _TTGlyphSetGlyf
class TTFontWrapper:

    tt: ttLib.TTFont
    
    def __init__(self, path: Path) -> None:
        self.tt = ttLib.TTFont(path)
    
        
    # Get Horizontal Header Table
    # For all properties, see <python-dir>/site-packages/fontTools/ttLib/tables/_h_h_e_a.py
    def hhea(self) -> table__h_h_e_a|Any:
        return cast(table__h_h_e_a, self.tt["hhea"])
        
    # Get Head Table
    # For all properties, see <python-dir>/site-packages/fontTools/ttLib/tables/_h_e_a_d.py
    def head(self) -> table__h_e_a_d|Any:
        return cast(table__h_e_a_d, self.tt["head"])
        
    # Get Glyph Table
    # For all properties, see <python-dir>/site-packages/fontTools/ttLib/tables/_g_l_y_f.py
    def glyf(self) -> table__g_l_y_f|Any:
        return cast(table__g_l_y_f, self.tt["glyf"])
        
    def getGlyphSet(self) -> _TTGlyphSetVARC | _TTGlyphSetCFF | _TTGlyphSetGlyf:
        return self.tt.getGlyphSet()

@dataclass
class Extenders:
    descenders: Decimal
    ascenders: Decimal
    
    # For a glyph with these ascenders and descenders, get the offset of its bounding box's
    # center point from the baseline in the unit em. The bounding box is formed
    # tightly around the extenders.
    def center_offset(self) -> Decimal:
        return (self.ascenders + self.descenders) / 2

class FontMetrics:
    tables: TTFontWrapper
    
    def __init__(self, font_file: Path) -> None:
        self.tables = TTFontWrapper(font_file)
    
    @functools.cache
    def units_per_em(self) -> int:
        head = self.tables.head()
        return assert_instance(int, head.unitsPerEm) # type: ignore
    
    # Get the extends of this font in em, i.e. the distance from the baseline to
    # the highest ascender and lowest descender.
    @functools.cache
    def extenders(self) -> Extenders:
        hhea = self.tables.hhea()
        
        return Extenders(
            Decimal(hhea.ascent) / self.units_per_em(),
            Decimal(hhea.descent) / self.units_per_em(),
        )
    
    # Get the ascenders and descenders of the letter with the given glyph name
    # in em.
    @functools.cache
    def glyph_extenders(self, glyph_name: str) -> Extenders:
        glyphs = self.tables.getGlyphSet()
        bounds_pen = BoundsPen(glyphs)
        glyphs[glyph_name].draw(bounds_pen)
        y_min_units = assert_instance(int, bounds_pen.bounds[1])
        y_max_units = assert_instance(int, bounds_pen.bounds[3])
        return Extenders(
            Decimal(y_min_units) / self.units_per_em(),
            Decimal(y_max_units) / self.units_per_em(),
        )
    
    # Get the height of the letter with the name glyph_name in the unit em.
    @functools.cache
    def glyph_height(self, glyph_name: str) -> Decimal:
        extenders = self.glyph_extenders(glyph_name)
        return extenders.ascenders - extenders.descenders
    
    # The height of the letter H in em.
    @functools.cache
    def cap_height(self) -> Decimal:
        return self.glyph_height("H")
    
    # The height of the letter x in em.
    @functools.cache
    def x_height(self) -> Decimal:
        return self.glyph_height("x")
    
    # Get the offset of the center point of the bounding box defined by the fonts ascent
    # and descent metrics in the unit em.
    @functools.cache
    def center_offset(self) -> Decimal:
        return self.extenders().center_offset()
    
    # Get the offset of the center point of the bounding box of 'H' from the baseline in
    # the unit em.
    @functools.cache
    def cap_center_offset(self) -> Decimal:
        return self.glyph_extenders("H").center_offset()
    
    # Get the offset of the center point of the bounding box of 'x' from the baseline in
    # the unit em.
    @functools.cache
    def x_center_offset(self) -> Decimal:
        return self.glyph_extenders("x").center_offset()

@dataclass
class FontDefinition:
    family: str
    weight: str
    path: Path
    metrics: FontMetrics
    
    def __init__(self, file: str | Path) -> None:
        path = file if isinstance(file, Path) else Path(file)
        known_font_extensions = [".otf", ".ttf", ".woff", ".woff2"]
        
        if path.suffix not in known_font_extensions:
            panic(f"Invalid file extension in font file '{path}'. Valid extensions are {known_font_extensions}")
        
        self.family = shell.run_command_infalliable("fc-query", str(path), "-f", "%{family}")
        fc_weight = shell.run_command_infalliable("fc-query", str(path), "-f", "%{weight}")
        if fc_weight in _fc_weight_mapping:
            self.weight = _fc_weight_mapping[fc_weight]
        else:
            self.weight = fc_weight
        
        self.path = path
        self.metrics = FontMetrics(path)

def get_system_family(family: str) -> Result[list[FontDefinition], None]:
    match shell.run_command("fc-list", "-q", f":family={family}"):
        case (127, _):
            panic("fc-list is not installed!")
        case (code, _):
            is_installed = (code == 0)
    
    if not is_installed:
        return Error(None)
    
    file_paths = shell.run_command_infalliable("fc-list", f":family={family}", "-f", "%{file}\n").removesuffix("\n").split("\n")
    
    return Ok([FontDefinition(path) for path in file_paths])

def generate_css_rule(font: FontDefinition) -> CssStatement:
    mime_type = f"font/{font.path.suffix.removeprefix(".")}"
    encoded = base64.b64encode(font.path.read_bytes()).decode()
    
    return CssStatement(
        "@font-face {\n"
        f"  font-family: \"{font.family}\";\n"
        f"  font-weight: {font.weight};\n"
        f"  src: url(data:{mime_type};base64,{encoded})\n"
        "}"
    )

def scan_fonts_dir(dir: Path) -> Iterable[Path]:
    """Find list of font files in directory and its subdirectories.
    
    Returns the exact same font files that resvg would when --use-fonts-dir is
    used.
    """
    
    for root, _, filenames in os.walk(dir):
        for filename in filenames:
            path = Path(root) / filename
            match path.suffix.lower():
                case ".ttf" | ".ttc" | ".otf" | ".otc":
                    yield path
                case _:
                    continue
