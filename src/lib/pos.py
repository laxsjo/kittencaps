from __future__ import annotations
from typing import *
from dataclasses import dataclass, field
from collections import namedtuple
from enum import IntEnum
import math
import operator
from .utils import *

__all__ = [
    "Vec3",
    "Vec2",
    "Rotation",
    "Scaling",
    "rotate",
    "Bounds",
    "Box",
    "Orientation",
]

@dataclass
class Vec3():
    x: float
    y: float
    z: float
    
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z
    
    def __len__(self) -> int:
        return 3
    
    def __add__(self, other: Vec3) -> Vec3:
        return Vec3(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z,
        )
    
    def __sub__(self, other: Vec3) -> Vec3:
        return Vec3(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z,
        )
    
    def __mul__(self, factor: Vec3 | float) -> Vec3:
        other = Vec3.promote_float(factor)
        return Vec3(
            self.x * other.x,
            self.y * other.y,
            self.z * other.z,
        )
    
    def __truediv__(self, factor: Vec3 | float) -> Vec3:
        other = Vec3.promote_float(factor)
        return Vec3(
            self.x / other.x,
            self.y / other.y,
            self.z / other.z,
        )
    
    @classmethod
    def promote_float(cls, component: float|Self) -> Self:
        return cls(component, component, component) if not isinstance(component, Vec3) else component

@dataclass
class Vec2():
    x: float
    y: float
    
    def __iter__(self):
        yield self.x
        yield self.y
        
    def __add__(self, other: Vec2) -> Vec2:
        return Vec2(
            self.x + other.x,
            self.y + other.y,
        )
    
    def __sub__(self, other: Vec2) -> Vec2:
        return Vec2(
            self.x - other.x,
            self.y - other.y,
        )
    
    def __mul__(self, factor: float|Vec2) -> Vec2:
        other = Vec2.promote_float(factor)
        return Vec2(
            self.x * other.x,
            self.y * other.y,
        )
    
    def __truediv__(self, factor: float|Vec2) -> Vec2:
        other = Vec2.promote_float(factor)
        return Vec2(
            self.x / other.x,
            self.y / other.y,
        )
    
    @classmethod
    def promote_float(cls, component: float|Self) -> Self:
        return cls(component, component) if not isinstance(component, Vec2) else component

    
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
    
    def get_x(self) -> float:
        return self.x
    def get_y(self) -> float:
        return self.y or self.x
    
    def is_identity(self) -> bool:
        return self.x == 1 and self.y == 1
    
    def promote_to_pair(self) -> Scaling:
        return self if self.y != None else Scaling(self.x, self.x)
    
    def as_pos(self) -> Vec2:
        return Vec2(*self.promote_to_pair())

def rotate(point: Vec2, origin: Vec2, angle: float) -> Vec2:
    """
    Rotate a point counterclockwise by a given angle around a given origin.

    The angle should be given in degrees.
    """
    
    angle_rad = math.radians(angle)
    
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle_rad) * (px - ox) - math.sin(angle_rad) * (py - oy)
    qy = oy + math.sin(angle_rad) * (px - ox) + math.cos(angle_rad) * (py - oy)
    return Vec2(qx, qy)

class Orientation(IntEnum):
    HORIZONTAL = 0
    VERTICAL = 1

@dataclass
class Bounds():
    min: Vec2
    max: Vec2
    
    def combine(self, other: Bounds) -> Bounds:
        import operator
        
        x_components, y_components = zip(self.min, self.max, other.min, other.max)
        
        return Bounds(
            min=Vec2(min(*x_components), min(*y_components)),
            max=Vec2(max(*x_components), max(*y_components))
        )

@dataclass
class Box():
    pos: Vec2
    size: Scaling
    rotation: Rotation
    # TODO: this is kind of ugly
    rotation_origin: Vec2
    
    def bounds(self) -> Bounds:
        min_corner = self.pos
        max_corner = self.pos + self.size.as_pos()
        corners = [
            Vec2(min_corner.x, min_corner.y),
            Vec2(min_corner.x, max_corner.y),
            Vec2(max_corner.x, max_corner.y),
            Vec2(max_corner.x, min_corner.y),
        ]
        
        rotated = map(lambda pos: rotate(pos, self.rotation_origin, self.rotation.deg), corners)
        
        # Type system is not advanced enough to understand this :(
        x_components, y_components = cast(
            tuple[tuple[float, ...], tuple[float, ...]],
            zip(*rotated)
        )
        
        return Bounds(
            min=Vec2(min(*x_components), min(*y_components)),
            max=Vec2(max(*x_components), max(*y_components))
        )
