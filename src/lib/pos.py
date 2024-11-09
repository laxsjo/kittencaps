from __future__ import annotations
from typing import *
from dataclasses import dataclass, field
from collections import namedtuple
from enum import IntEnum
import math
import operator
from .utils import *

__all__ = [
    "Pos",
    "Rotation",
    "Scaling",
    "rotate",
    "Bounds",
    "Box",
    "Orientation",
]

@dataclass
class Pos():
    x: float
    y: float
    
    def __iter__(self):
        yield self.x
        yield self.y
        
    def __add__(self, other: Pos) -> Pos:
        return Pos(
            self.x + other.x,
            self.y + other.y,
        )
    
    def __sub__(self, other: Pos) -> Pos:
        return Pos(
            self.x - other.x,
            self.y - other.y,
        )
    
    def __mul__(self, factor: float) -> Pos:
        return Pos(
            self.x * factor,
            self.y * factor,
        )
    
    def __truediv__(self, factor: float) -> Pos:
        return Pos(
            self.x / factor,
            self.y / factor,
        )
    
    @classmethod
    def identity(cls) -> Self:
        return cls(0, 0)
    
    def is_identity(self) -> bool:
        return self.x == 0 and self.y == 0
    
    def as_scaling(self) -> Scaling:
        return Scaling(*self)

@dataclass
class Rotation:
    deg: float
    
    def __add__(self, other: Rotation|float) -> Rotation:
        return Rotation(
            self.deg + other.deg if isinstance(other, Rotation) else other
        )
    def __sub__(self, other: Rotation|float) -> Rotation:
        return Rotation(
            self.deg - other.deg if isinstance(other, Rotation) else other
        )
    def __mult__(self, other: float) -> Rotation:
        return Rotation(
            self.deg * other
        )
    
    @classmethod
    def identity(cls) -> Self:
        return cls(0)
    
    def is_identity(self) -> bool:
        return self.deg == 0

@dataclass
class Scaling():
    x: float
    y: float|None = None
    
    def __iter__(self):
        yield self.x
        if self.y != None:
            yield self.y
    
    def __len__(self) -> int:
        return 1 if self.y == None else 2

    def __add__(self, other: Self) -> Scaling:
        if len(self) == len(other):
            return Scaling(
                *(map(lambda pair: pair[0] + pair[1], zip(self, other)))
            )
        else:
            return self.promote_to_pair() + other.promote_to_pair()
    
    def __sub__(self, other: Self) -> Scaling:
        if len(self) == len(other):
            return Scaling(
                *(map(lambda pair: pair[0] - pair[1], zip(self, other)))
            )
        else:
            return self.promote_to_pair() + other.promote_to_pair()
    
    def __mul__(self, other: float|Scaling) -> Scaling:
        return self._mul_scaling(other) if isinstance(other, Scaling) else self._mul_float(other)
    
    def _mul_scaling(self, other: Scaling) -> Scaling:
        if len(self) == len(other):
            return Scaling(
                *(map(lambda pair: pair[0] * pair[1], zip(self, other)))
            )
        else:
            return self.promote_to_pair() * other.promote_to_pair()
    
    def _mul_float(self, factor: float) -> Scaling:
        return Scaling(
            *(map(lambda x: x * factor, self))
        )
    
    def __truediv__(self, factor: float) -> Scaling:
        return Scaling(
            *(map(lambda x: x * factor, self))
        )
    
    @classmethod
    def identity(cls) -> Self:
        return cls(1, 1)

    
    def is_identity(self) -> bool:
        return self.x == 1 and self.y == 1
    
    def promote_to_pair(self) -> Scaling:
        return self if self.y != None else Scaling(self.x, self.x)
    
    def as_pos(self) -> Pos:
        return Pos(*self.promote_to_pair())

def rotate(point: Pos, origin: Pos, angle: float) -> Pos:
    """
    Rotate a point counterclockwise by a given angle around a given origin.

    The angle should be given in degrees.
    """
    
    angle_rad = math.radians(angle)
    
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle_rad) * (px - ox) - math.sin(angle_rad) * (py - oy)
    qy = oy + math.sin(angle_rad) * (px - ox) + math.cos(angle_rad) * (py - oy)
    return Pos(qx, qy)

class Orientation(IntEnum):
    HORIZONTAL = 0
    VERTICAL = 1

@dataclass
class Bounds():
    min: Pos
    max: Pos
    
    def combine(self, other: Bounds) -> Bounds:
        import operator
        
        x_components, y_components = zip(self.min, self.max, other.min, other.max)
        
        return Bounds(
            min=Pos(min(*x_components), min(*y_components)),
            max=Pos(max(*x_components), max(*x_components))
        )
        
        # Bounds(
        #     min=Pos(min(self.min.x, other.min.x), min(self.min.y, other.min.y)),
        #     max=Pos(max(self.max.x, other.max.x), max(self.min.y, other.min.y)),
        # )

@dataclass
class Box():
    pos: Pos
    size: Scaling
    rotation: Rotation
    # TODO: this is kind of ugly
    rotation_origin: Pos
    
    def bounds(self) -> Bounds:
        # I'm assuming that negative y is the positive direction
        top_left = self.pos - self.size.as_pos()/2
        bottom_right = self.pos + self.size.as_pos()/2
        corners = [
            top_left,
            Pos(bottom_right.x, top_left.y),
            bottom_right,
            Pos(top_left.x, bottom_right.y),
        ]
        
        rotated = map(lambda pos: rotate(pos, self.rotation_origin, self.rotation.deg), corners)
        
        # Type system is not advanced enough to understand this :(
        x_components, y_components = cast(tuple[tuple[float, ...], tuple[float, ...]], zip(*rotated))
        
        return Bounds(
            min=Pos(min(*x_components), min(*y_components)),
            max=Pos(max(*x_components), max(*x_components))
        )
