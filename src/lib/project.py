from __future__ import annotations
import os
from dataclasses import dataclass
from typing import TypedDict
from pathlib import Path
from colour import Color, RGB_color_picker, hash_or_str

from .error import *
from .utils import *
from .font import *
from .sp_color import *

__all__ = [
    "path_to_absolute",
]

# Convert path relative to project root into a absolute path. 
# Note: This function assumes that the current script is called in the 'src' directory...
def path_to_absolute(relative_path: str|Path) -> Path:
    return Path(os.path.dirname(__file__)).joinpath("../..", relative_path).resolve()
