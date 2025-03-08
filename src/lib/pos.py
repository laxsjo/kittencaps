from __future__ import annotations
from typing import *
from dataclasses import dataclass, field
from collections import namedtuple
from collections.abc import Sequence
from enum import IntEnum
import math
import functools
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
    "CubicBezierSegment",
]

# TODO: IDK where I should place this
def clamp[T: float|int](value: T, min_value: T, max_value: T) -> T:
    return max(min_value, min(max_value, value))

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
        
    def __add__(self, other: Self) -> Self:
        return type(self)(
            self.x + other.x,
            self.y + other.y,
        )
    
    def __sub__(self, other: Self) -> Self:
        return type(self)(
            self.x - other.x,
            self.y - other.y,
        )
    
    def __mul__(self, factor: float|Self) -> Self:
        cls = type(self)
        other = cls.promote_float(factor)
        return cls(
            self.x * other.x,
            self.y * other.y,
        )
    
    def __truediv__(self, factor: float|Self) -> Self:
        cls = type(self)
        other = cls.promote_float(factor)
        return cls(
            self.x / other.x,
            self.y / other.y,
        )
    
    def __neg__(self) -> Self:
        return self.apply_unary(operator.neg)
    
    def __pow__(self, exponent: float|Self) -> Self:
        return self.apply_binary(operator.pow, (exponent,))
    
    def abs(self) -> Self:
        return self.apply_unary(operator.abs)
    
    def sqrt(self) -> Self:
        return self.apply_unary(math.sqrt)
    
    def min(self, *other_values: float|Self) -> Self:
        return self.apply_binary(min, other_values)
    
    def max(self, *other_values: float|Self) -> Self:
        return self.apply_binary(max, other_values)
        
    def clamp(self, min_value: float|Self, max_value: float|Self) -> Self:
        return self.min(max_value).max(min_value)
    
    def length(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)
    
    def reflect_around(self, center: Self) -> Self:
        return -(self - center) + center 
    
    def dot_product(self, other: Self) -> float:
        return self.x * other.x + self.y * other.y
    
    def angle_to(self, other: Self) -> Rotation:
        """
        Calculate the rotation that when applied to self results in other
        (assuming equal lengths)
        """
        # We clamp it to avoid floating point impressision problems, source:
        # https://mortoray.com/rendering-an-svg-elliptical-arc-as-bezier-curves/
        unsigned_angle_rad = math.acos(clamp(
            self.dot_product(other)
            / (self.length() * other.length()),
            -1,
            1
        ))
        if self.x * other.y - self.y * other.x > 0:
            angle_rad = unsigned_angle_rad
        else:
            angle_rad = -unsigned_angle_rad
        
        return Rotation(math.degrees(angle_rad))
    
    def per_component(self, map_x: Callable[[float], float]|None, map_y: Callable[[float], float]|None) -> Self:
        return self.__class__(
            (map_x or (lambda x: x))(self.x),
            (map_y or (lambda y: y))(self.y),
        )
    
    def apply_unary(self, operator: Callable[[float], float]) -> Self:
        return type(self)(
            operator(self.x),
            operator(self.y),
        )
    
    def apply_binary(self, operator: Callable[[float, float], float], others: Iterable[float|Self]) -> Self:
        other_vec2s = map(self.promote_float, others)
        x_components, y_components = zip(self, *other_vec2s)
        
        return type(self)(
            functools.reduce(operator, x_components),
            functools.reduce(operator, y_components),
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
    """
    Represents a rotation transformation or angle in the clockwise direction
    (note that it isn't counter-clockwise due to SVG's +y down coordinate
    system).
    """
    
    deg: float
    
    def __add__(self, other: Rotation|float) -> Rotation:
        return Rotation(
            self.deg + (other.deg if isinstance(other, Rotation) else other)
        )
    def __sub__(self, other: Rotation|float) -> Rotation:
        return Rotation(
            self.deg - (other.deg if isinstance(other, Rotation) else other)
        )
    def __mul__(self, other: float) -> Rotation:
        return Rotation(
            self.deg * other
        )
    def __truediv__(self, other: float) -> Rotation:
        return Rotation(
            self.deg / other
        )
    def __neg__(self) -> Self:
        return type(self)(
            -self.deg,
        )
    
    def __gt__(self, other: Self|float) -> bool:
        return self.deg > self.promote(other).deg
    
    def __lt__(self, other: Self|float) -> bool:
        return self.deg < self.promote(other).deg
    
    def __matmul__(self, point: Vec2) -> Vec2:
        """
        Apply rotation to point, i.e. rotate point clockwise around origin."""
        
        angle_rad = math.radians(self.deg)
        
        return Vec2(
            math.cos(angle_rad) * point.x - math.sin(angle_rad) * point.y,
            math.sin(angle_rad) * point.x + math.cos(angle_rad) * point.y,
        )
    
    @classmethod
    def promote(cls, value: Self|float) -> Self:
        return cls(value.deg if isinstance(value, Rotation) else value)
    
    
    @classmethod
    def identity(cls) -> Self:
        return cls(0)
    
    def is_identity(self) -> bool:
        return self.deg == 0
    
    def normalize(self) -> Self:
        """Return version of self, where 0 <= angle < 360."""
        return type(self)(self.deg % 360)
    
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
    
    @classmethod
    def from_points(cls, *points: Vec2) -> Self:
        x_components, y_components = zip(*points)
        return cls(
            min=Vec2(min(x_components), min(y_components)),
            max=Vec2(max(x_components), max(y_components)),
        )
    
    @classmethod
    def from_pos_size(cls, pos: Vec2, size: Vec2) -> Self:
        return cls(pos, pos + size)
    
    @classmethod
    def from_quadratic_bezier(cls, start_point: Vec2, handle: Vec2, end_point: Vec2) -> Self:
        # From https://iquilezles.org/articles/bezierbbox/
        
        ends_bounds = cls.from_points(start_point, end_point)
        """Bounds of the start and end points"""
        
        if handle in ends_bounds:
            return ends_bounds
        else:
            # I have no idea what the semantic meaning of these values are :)
            t = ((start_point - handle) / (start_point - handle * 2 + end_point))\
                .clamp(0, 1)
            s = Vec2.promote_float(1) - t
            q = s * s * start_point \
                + (s * t * handle) * 2 \
                + t * t * end_point
            
            bounds = cls(
                min=ends_bounds.min.min(q),
                max=ends_bounds.max.min(q),
            )
            
            return bounds
    
    @classmethod
    def from_cubic_bezier(cls, segment: CubicBezierSegment) -> Self:
        # Also from https://iquilezles.org/articles/bezierbbox/
        
        ends_bounds = cls.from_points(segment.start, segment.end)
        """Bounds of the start and end points"""
        
        c = -segment.start + segment.handle_1
        b = segment.start - segment.handle_1 * 2 + segment.handle_2
        a = -segment.start + segment.handle_1 * 3 - segment.handle_2 * 3 + segment.end 
        h = b * b - a * c
        
        if h.x > 0 or h.y > 0:
            g = h.abs().sqrt()
            
            # This simulates division by zero producing infinity, which would
            # generate an error in python. The original article was written for
            # a shader which has floating point infinity and therefore didn't
            # need this.
            a = a.apply_unary(
                lambda component: 0.000001 if component == 0 else component
            )
            
            t1 = ((-b - g) / a).clamp(0, 1)
            s1 = Vec2.promote_float(1) - t1
            t2 = ((-b + g) / a).clamp(0, 1)
            s2 = Vec2.promote_float(1) - t2
            
            q1 = s1 * s1 * s1 * segment.start \
                + s1 * s1 * t1 * segment.handle_1 * 3 \
                + s1 * t1 * t1 * segment.handle_2 * 3 \
                + t1 * t1 * t1 * segment.end
            q2 = s2 * s2 * s2 * segment.start \
                + s2 * s2 * t2 * segment.handle_1 * 3 \
                + s2 * t2 * t2 * segment.handle_2 * 3 \
                + t2 * t2 * t2 * segment.end
            
            if h.x > 0:
                ends_bounds.min.x = min(ends_bounds.min.x, q1.x, q2.x)
                ends_bounds.max.x = max(ends_bounds.max.x, q1.x, q2.x)
        
            if h.y > 0:
                ends_bounds.min.y = min(ends_bounds.min.y, q1.y, q2.y)
                ends_bounds.max.y = max(ends_bounds.max.y, q1.y, q2.y)
        
        return ends_bounds
    
    def combine(self, other: Bounds) -> Bounds:
        x_components, y_components = zip(self.min, self.max, other.min, other.max)
        
        return Bounds(
            min=Vec2(min(*x_components), min(*y_components)),
            max=Vec2(max(*x_components), max(*y_components))
        )
        
    def __contains__(self, position: Vec2) -> bool:
        return (
            self.min.x <= position.x <= self.max.x
            and self.min.y <= position.y <= self.max.y 
        )
    
    def size(self) -> Vec2:
        return self.max - self.min
    
    def with_margin(self, margin: float) -> Self:
        """
        Return new bounds which is extended `margin` units in every direction.
        """
        
        return type(self)(
            self.min - Vec2(margin, margin),
            self.max + Vec2(margin, margin) * 2,
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

@dataclass
class CubicBezierSegment():
    start: Vec2
    handle_1: Vec2
    handle_2: Vec2
    end: Vec2
    
    @classmethod
    def approximate_arc(cls, center: Vec2, radius: Vec2, x_axis_angle: Rotation, start_angle: Rotation, end_angle: Rotation, segement_min_degrees: float) -> Iterable[Self]:
        """Approximate arc segment of ellipse as a series of count bezier segments.
        
        The arguments correspond to the variables in the SVG implementation note
        document as follows:
        - center: (c_1, c_2)
        - radius: (r_1, r_2)
        - start_angle: theta_1
        - end_angle: theta_2
        - x_axis_angle: phi
        https://www.w3.org/TR/SVG2/implnote.html#ArcParameterizationAlternatives
        """
        
        # Implementation based on https://mortoray.com/rendering-an-svg-elliptical-arc-as-bezier-curves/
        
        def elliptic_arc_point(center: Vec2, radius: Vec2, x_axis_angle: Rotation, angle: Rotation) -> Vec2:
            """Get point along the ellipses that is `angle` clockwise along from uhh somewhere."""
            return Vec2(
                center.x + radius.x * math.cos(x_axis_angle.rad()) * math.cos(angle.rad()) - radius.y * math.sin(x_axis_angle.rad()) * math.sin(angle.rad()),
                center.y + radius.x * math.sin(x_axis_angle.rad()) * math.cos(angle.rad()) + radius.y * math.cos(x_axis_angle.rad()) * math.sin(angle.rad())
            )
        def elliptic_arc_point_derivative(center: Vec2, radius: Vec2, x_axis_angle: Rotation, angle: Rotation) -> Vec2:
            """The derivative of elliptic_arc_point with respects to `angle`"""
            # Generated with ChatGPT :) 
            return Vec2(
                -radius.x * math.cos(x_axis_angle.rad()) * math.sin(angle.rad()) - radius.y * math.sin(x_axis_angle.rad()) * math.cos(angle.rad()),
                -radius.x * math.sin(x_axis_angle.rad()) * math.sin(angle.rad()) + radius.y * math.cos(x_axis_angle.rad()) * math.cos(angle.rad())
            )
        
        def approximate_single(center: Vec2, radius: Vec2, x_axis_angle: Rotation, start_angle: Rotation, end_angle: Rotation) -> Self:
            def calc_point(angle: Rotation) -> Vec2:
                return elliptic_arc_point(center, radius, x_axis_angle, angle)
            def calc_point_derivative(angle: Rotation) -> Vec2:
                return elliptic_arc_point_derivative(center, radius, x_axis_angle, angle)
            
            start = calc_point(start_angle)
            end = calc_point(end_angle)
            
            # What does this mean? No idea!
            alpha = (
                math.sin(end_angle.rad() - start_angle.rad())
                * (
                    math.sqrt(
                        4
                        + 3 * (math.tan(
                            (end_angle.rad() - start_angle.rad())
                            / 2
                        ) ** 2)
                    )
                    - 1
                )
                / 3
            )
            
            return cls(
                start=start,
                end=end,
                handle_1=start + calc_point_derivative(start_angle) * alpha,
                handle_2=end - calc_point_derivative(end_angle) * alpha,
            )
        
        count = math.ceil(abs((end_angle - start_angle).deg) / segement_min_degrees)
        
        segment_delta_angle = (end_angle - start_angle) / count
        for index in range(count):
            segment_start_angle = start_angle + segment_delta_angle * index
            segment_end_angle = segment_start_angle + segment_delta_angle
            
            yield approximate_single(
                center,
                radius,
                x_axis_angle,
                segment_start_angle,
                segment_end_angle
            )
    
    def to_path_command_str(self) -> str:
        """
        Basically only useful when debugging
        """
        
        vec2_to_str = lambda vec2: ",".join(map(str, vec2))
        return f"M {vec2_to_str(self.start)} C {vec2_to_str(self.handle_1)} {vec2_to_str(self.handle_2)} {vec2_to_str(self.end)}"
