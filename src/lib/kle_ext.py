from __future__ import annotations
from typing import *
from damsenviet.kle import *
from pathlib import Path
from coloraide import Color
from dataclasses import dataclass, field
from enum import Enum

from .pos import *
from .utils import *
from .error import *

__all__ = [
    "Case",
    "ExtendedKeyboard"
]

class Axis(Enum):
    X = "X"
    Y = "Y"
    Z = "Z"
    NEGATIVE_X = "NEGATIVE_X"
    NEGATIVE_Y = "NEGATIVE_Y"
    NEGATIVE_Z = "NEGATIVE_Z"
    
    @classmethod
    def parse_str(cls, value: str) -> Result[Axis, str]:
        value = value.lower()
        is_positive = True
        if value.startswith("+"):
            value = value.removeprefix("+")
            is_positive = True
        elif value.startswith("-"):
            value = value.removeprefix("-")
            is_positive = False
        
        match value:
            case "x" if is_positive:
                return Ok(cls.X)
            case "y" if is_positive:
                return Ok(cls.Y)
            case "z" if is_positive:
                return Ok(cls.Z)
            case "X":
                return Ok(cls.NEGATIVE_X)
            case "Y":
                return Ok(cls.NEGATIVE_Y)
            case "Z":
                return Ok(cls.NEGATIVE_Z)
            case str:
                return Error(f"Invalid axis string '{str}'")

@dataclass
class Case:
    model_path: Path | None = None
    """Path to a 3D model of the case"""
    model_unit_scale: float = 1000
    """Number of the 3D model's unit per meter. Defaults to 1000 (mm)."""
    model_up_axis: Axis = Axis.Z
    """The axis which signifies the up axis in the 3D model."""
    model_forward_axis: Axis = Axis.Y
    """The axis which signifies the forward axis in the 3D model."""
    color: str = field(default_factory=lambda: "white")
    position: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    vertical_offset_mm: float = 0
    """How much the keycap bases are offset vertically from the models origin"""
    mirror_around_x: float | None = None
    mirror_around_y: float | None = None

def _playback_case_changes(
    case: Case,
    case_changes: dict,
) -> None:
    if "modelPath" in case_changes:
        case.model_path = Path(case_changes["modelPath"])
    if "modelUnitScale" in case_changes:
        case.model_unit_scale = case_changes["modelUnitScale"]
    if "modelUpAxis" in case_changes:
        match Axis.parse_str(case_changes["modelUpAxis"]):
            case Ok(axis):
                case.model_up_axis = axis
            case Error(reason):
                panic(f"Invalid value of 'modelUpAxis': {reason}")
    if "modelForwardAxis" in case_changes:
        match Axis.parse_str(case_changes["modelForwardAxis"]):
            case Ok(axis):
                case.model_up_axis = axis
            case Error(reason):
                panic(f"Invalid value of 'modelForwardAxis': {reason}")
    if "color" in case_changes:
        case.color = case_changes["color"]
    if "position" in case_changes:
        try:
            case.position = Vec2(*case_changes["position"])
        except TypeError:
            pass
    if "verticalOffsetMM" in case_changes:
        case.vertical_offset_mm = case_changes["verticalOffsetMM"]
    if "mirrorAroundX" in case_changes:
        case.mirror_around_x = case_changes["mirrorAroundX"]
    if "mirrorAroundY" in case_changes:
        case.mirror_around_y = case_changes["mirrorAroundY"]

Keyboard_JSON = list[dict | list[str | dict]]
class ExtendedKeyboard(Keyboard):
    case: Case
    icon_margin: float
    """
    Margin around to add around individual icons. For this option to be useful
    the icons should specify a viewbox that extends beyond the standard
    100x100 px rectangle at (0, 0). This extended area is then included in the
    texture variant.
    """
    scale: float
    """
    All dimensions in the final SVG are scaled by this factor, effectively
    increasing the resolution of the generated PNG.
    """
    
    def __init__(self):
        """Initializes a Keyboard."""
        super().__init__()
        self.case = Case()
    
    @classmethod
    def from_json(
        cls,
        keyboard_json: Keyboard_JSON,
    ) -> Self: 
        super_keyboard = super().from_json(keyboard_json)
        super_keyboard.__class__ = cls
        keyboard = cast(Self, super_keyboard)
        keyboard.case = Case()
        keyboard.icon_margin = 0
        keyboard.scale = 1
        
        # TODO: We should probably validate keyboard_json...
        
        for item in keyboard_json:
            if type(item) is dict:
                if "case" in item and type(item["case"]) is dict:
                    _playback_case_changes(keyboard.case, item["case"])
                if "iconMargin" in item and isinstance(item["iconMargin"], (float, int)):
                    keyboard.icon_margin = item["iconMargin"]
                if "scale" in item and isinstance(item["scale"], (float, int)):
                    keyboard.scale = item["scale"]
        
        return keyboard
