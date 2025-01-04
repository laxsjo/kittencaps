from __future__ import annotations
from typing import *
from dataclasses import dataclass, field
from collections import namedtuple
from collections.abc import Sequence
from enum import IntEnum
import math
import operator
from .utils import *

__all__ = [
    "number_to_str",
    "Vec3",
    "Vec2",
    "Rotation",
    "Scaling",
    "rotate",
    "Bounds",
    "Box",
    "Orientation",
]

# Convert number to string, with integer valued floats not including a trailing
# '.0' 
def number_to_str(number: float) -> str:
    return str(number).removesuffix(".0")

@dataclass
class Vec3(Sequence[float]):
    x: float
    y: float
    z: float
    
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z
    
    @overload
    def __getitem__(self, index: int) -> float:
        ...
    @overload
    def __getitem__(self, index: slice) -> Sequence:
        ...
    def __getitem__(self, index: int|slice) -> float|Sequence:
        return (*self,)[index]
    
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
    
    @overload
    def __getitem__(self, index: int) -> float:
        ...
    @overload
    def __getitem__(self, index: slice) -> Sequence:
        ...
    def __getitem__(self, index: int|slice) -> float|Sequence:
        return (*self,)[index]
        
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
    
    def __neg__(self) -> Vec2:
        return Vec2(
            -self.x,
            -self.y,
        )
    def per_component(self, map_x: Callable[[float], float]|None, map_y: Callable[[float], float]|None) -> Self:
        return self.__class__(
            (map_x or (lambda x: x))(self.x),
            (map_y or (lambda y: y))(self.y),
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
    
    # Return a new Vec2 with the x and y components swapped
    def swap(self) -> Vec2:
        return Vec2(self.y, self.x)

@dataclass
class Rotation:
    deg: float
    
    def __add__(self, other: Rotation|float) -> Rotation:
        return Rotation(
            self.deg + (other.deg if isinstance(other, Rotation) else other)
        )
    def __sub__(self, other: Rotation|float) -> Rotation:
        return Rotation(
            self.deg - (other.deg if isinstance(other, Rotation) else other)
        )
    def __mult__(self, other: float) -> Rotation:
        return Rotation(
            self.deg * other
        )
    def __neg__(self) -> Rotation:
        return Rotation(
            -self.deg,
        )
    
    
    @classmethod
    def identity(cls) -> Self:
        return cls(0)
    
    def is_identity(self) -> bool:
        return self.deg == 0
    
    def rad(self) -> float:
        import math
        return math.radians(self.deg)

@dataclass
class Scaling():
    x: float
    y: float
    
    def __init__(self, x: float, y: float|None = None):
        self.x = x
        self.y = y if y is not None else x
    
    def __iter__(self):
        yield self.x
        if self.y != self.x:
            yield self.y
    
    def __len__(self) -> int:
        return 1 if self.y == self.x else 2

    def __add__(self, other: Self) -> Scaling:
        return Scaling(
            self.x + other.x,
            self.y + other.y,
        )
    
    def __sub__(self, other: Self) -> Scaling:
        return Scaling(
            self.x - other.x,
            self.y - other.y,
        )
    
    def __mul__(self, other: float|Scaling) -> Scaling:
        other = Scaling.promote_float(other)
        return Scaling(
            self.x * other.x,
            self.y * other.y,
        )
    
    def __truediv__(self, other: float|Scaling) -> Scaling:
        other = Scaling.promote_float(other)
        return Scaling(
            self.x / other.x,
            self.y / other.y,
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
    
    @classmethod
    def promote_float(cls, value: float|Self) -> Self:
        return value if isinstance(value, Scaling) else cls(value)
    
    # Deprecated
    def promote_to_pair(self) -> Scaling:
        return self
    
    def as_vec2(self) -> Vec2:
        return Vec2(self.x, self.y)

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
        max_corner = self.pos + self.size.as_vec2()
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
