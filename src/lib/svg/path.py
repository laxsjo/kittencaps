from typing import *
from dataclasses import dataclass
from abc import ABC, abstractmethod
from copy import copy
import math
import functools
import more_itertools

from ..utils import *
from ..error import *
from ..pos import *

__all__ = [
    "PathState",
    "PathResult",
    "PathCommand",
    "MoveTo",
    "ClosePath",
    "LineTo",
    "HorizontalLineTo",
    "VerticalLineTo",
    "CurveTo",
    "ShorthandCurveTo",
    "QuadraticCurveTo",
    "ShorthandQuadraticCurveTo",
    "EllipticalArc",
    "evaluate_commands",
    "parse_str",
]

@dataclass(frozen=True)
class PathState():
    initial_position: Vec2
    current_position: Vec2
    last_handle: Vec2|None
    bounds: Bounds|None
    
    @classmethod
    def from_initial_position(cls, initial_position: Vec2) -> Self:
        return cls(
            initial_position=initial_position,
            current_position=initial_position,
            last_handle=None,
            bounds=None,
        )
    
    def update(self, next_position: Vec2, additional_bounds: Bounds, initial_position: Vec2|None = None, last_handle: Vec2|None = None) -> Self:
        return type(self)(
            current_position=next_position,
            bounds=additional_bounds if self.bounds is None else self.bounds.combine(additional_bounds),
            last_handle=last_handle,
            initial_position=initial_position if initial_position is not None else self.initial_position
        )
    
    def resolve_position(self, relative: bool, position_or_offset: Vec2) -> Vec2:
        if relative:
            return self.current_position + position_or_offset
        else:
            return position_or_offset
    
    def get_reflected_handle(self) -> Vec2:
        if self.last_handle is None:
            return self.current_position
        else:
            return self.last_handle.reflect_around(self.current_position)

@dataclass(frozen=True)
class PathResult():
    bounds: Bounds
    
    @classmethod
    def from_path_state(cls, state: PathState) -> Self:
        if state.bounds is None:
            panic(f"State did not have any bounds: {state}")
        
        return cls(
            bounds=state.bounds
        )

type PathArgument = float | Vec2 | bool | Rotation
type PathArgumentType = type[float] | type[Vec2] | type[bool] | type[Rotation]

class PathCommand(ABC):
    relative: bool
    
    @staticmethod
    @abstractmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        """The arguments that this command consumes"""
        ...
    
    @abstractmethod
    def update(self, state: PathState) -> PathState:
        """
        Given a current path state, return the new state after this path
        command has been applied.
        """
        ...

@dataclass(frozen=True)
class MoveTo(PathCommand):
    relative: bool
    position: Vec2
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2,)
    
    def update(self, state: PathState) -> PathState:
        next_position = state.resolve_position(self.relative, self.position)
        
        return state.update(
            next_position,
            Bounds.from_points(next_position),
            initial_position=next_position,
        )

@dataclass(frozen=True)
class ClosePath(PathCommand):
    relative: bool
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return tuple()
    
    def update(self, state: PathState) -> PathState:
        next_position = state.initial_position
        return state.update(
            next_position,
            Bounds.from_points(state.current_position, next_position)
        )

@dataclass(frozen=True)
class LineTo(PathCommand):
    relative: bool
    position: Vec2
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2,)
    
    def update(self, state: PathState) -> PathState:
        next_position = state.resolve_position(self.relative, self.position)
        
        return state.update(
            next_position,
            Bounds.from_points(state.current_position, next_position)
        )

@dataclass(frozen=True)
class HorizontalLineTo(PathCommand):
    relative: bool
    x: float
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (float,)
    
    def update(self, state: PathState) -> PathState:
        next_position = copy(state.current_position)
        if self.relative:
            next_position.x += self.x
        else:
            next_position.x = self.x
        
        return state.update(
            next_position,
            Bounds.from_points(state.current_position, next_position)
        )

@dataclass(frozen=True)
class VerticalLineTo(PathCommand):
    relative: bool
    y: float
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (float,)
    
    def update(self, state: PathState) -> PathState:
        next_position = copy(state.current_position)
        if self.relative:
            next_position.y += self.y
        else:
            next_position.y = self.y
        
        return state.update(
            next_position,
            Bounds.from_points(state.current_position, next_position)
        )

@dataclass(frozen=True)
class CurveTo(PathCommand):
    relative: bool
    handle_1: Vec2
    handle_2: Vec2
    position: Vec2
    """The end position"""
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2, Vec2, Vec2)
    
    def update(self, state: PathState) -> PathState:
        handle_1 = state.resolve_position(self.relative, self.handle_1)
        handle_2 = state.resolve_position(self.relative, self.handle_2)
        next_position = state.resolve_position(self.relative, self.position)
        
        next_bounds = Bounds.from_cubic_bezier(CubicBezierSegment(
            state.current_position,
            handle_1,
            handle_2,
            next_position            
        ))
        
        return state.update(
            next_position,
            next_bounds,
            last_handle=handle_2,
        )

@dataclass(frozen=True)
class ShorthandCurveTo(PathCommand):
    relative: bool
    handle_2: Vec2
    position: Vec2
    """The end position"""
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2, Vec2)
    
    def update(self, state: PathState) -> PathState:
        return CurveTo(
            self.relative,
            state.get_reflected_handle(),
            self.handle_2,
            self.position,
        ).update(state)

@dataclass(frozen=True)
class QuadraticCurveTo(PathCommand):
    relative: bool
    handle: Vec2
    position: Vec2
    """The end position"""
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2, Vec2)
    
    def update(self, state: PathState) -> PathState:
        handle = state.resolve_position(self.relative, self.handle)
        next_position = state.resolve_position(self.relative, self.position)
        
        next_bounds = Bounds.from_quadratic_bezier(
            state.current_position,
            handle,
            next_position,
        )
        
        return state.update(
            next_position,
            next_bounds,
            last_handle=handle,
        )

@dataclass(frozen=True)
class ShorthandQuadraticCurveTo(PathCommand):
    relative: bool
    position: Vec2
    """The end position"""
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2,)
    
    def update(self, state: PathState) -> PathState:
        return QuadraticCurveTo(
            self.relative,
            state.get_reflected_handle(),
            self.position,
        ).update(state)

@dataclass(frozen=True)
class EllipticalArc(PathCommand):
    relative: bool
    radius: Vec2
    x_axis_rotation: Rotation
    large_arc_flag: bool
    sweep_flag: bool
    position: Vec2
    """The end position"""
    
    @staticmethod
    def arguments() -> tuple[PathArgumentType, ...]:
        return (Vec2, Rotation, bool, bool, Vec2)
    
    def update(self, state: PathState) -> PathState:
        next_position = state.resolve_position(self.relative, self.position)
        
        ## Based on https://www.w3.org/TR/SVG2/implnote.html#ArcConversionEndpointToCenter
        # Step 1
        shifted_position = (state.current_position - next_position) / 2
        transformed_position = -self.x_axis_rotation @ shifted_position
        
        # Bonus step from https://mortoray.com/rendering-an-svg-elliptical-arc-as-bezier-curves/
        # Scale up radius if too small
        # This variable corresponds to `cr` in the article's implementation
        magic_check_radius_ratio = functools.reduce(lambda x, y: x + y, (transformed_position / self.radius) ** 2)
        radius = self.radius
        if magic_check_radius_ratio > 1.0000000000001: # That ought to do it ;)
            print(f"Warning had to scale up by {math.sqrt(magic_check_radius_ratio)},")
            print(f"  while updating path with {self}")
            radius = self.radius * math.sqrt(magic_check_radius_ratio)
        
        # Step 2
        funny_coefficient = math.sqrt(max(
            # Note: we take the min here to account for floating point
            # imprecision, source: https://mortoray.com/rendering-an-svg-elliptical-arc-as-bezier-curves/
            0,
            (
                radius.x ** 2 * radius.y ** 2
                - radius.x ** 2 * transformed_position.y ** 2
                - radius.y ** 2 * transformed_position.x ** 2
            ) / (
                radius.x ** 2 * transformed_position.y ** 2
                + radius.y ** 2 * transformed_position.x ** 2
            )
        ))
        transformed_center = Vec2(
            x=radius.x * transformed_position.y / radius.y,
            y=-(radius.y * transformed_position.x / radius.x),
        ) * funny_coefficient \
            * (1 if self.large_arc_flag != self.sweep_flag else -1)
        
        # Step 3
        center = self.x_axis_rotation @ transformed_center \
            + (state.current_position + next_position) / 2
        
        # Step 4
        # Note: An "angle around the ellipse" specifies an angle from the middle
        # right side of the ellipse (before rotating it), where positive angles
        # walk clockwise, e.g. the angle 0 correspons to the point (1, 0) for
        # the unit circle.
        theta_1 = Vec2[float](1, 0).angle_to(
            (transformed_position - transformed_center)
            / radius
        )
        
        # This version is from the mortoray.com article and deviates slightly
        # from the SVG implementation notes version.
        delta_theta = Rotation((
            (transformed_position - transformed_center)
            / radius
        ).angle_to(
            (-transformed_position - transformed_center)
            / radius
        ).deg % 360)
        
        if not self.sweep_flag:
            delta_theta -= 360

        # I'm unsure if this is the right way around...
        # delta_theta = theta_2 - theta_1 (I picked this one)
        # => theta_2 = theta_1 + delta_theta
        # delta_theta = theta_1 - theta_2
        # => theta_2 = theta_1 - delta_theta
        theta_2 = theta_1 + delta_theta
        
        ## Calculate Bounds
        # We cheat by approximating the arc as a series of cubic bezier curves,
        # which we then calculate the bounds of.
        segments = CubicBezierSegment.approximate_arc(
            center=center,
            radius=radius,
            x_axis_angle=self.x_axis_rotation,
            start_angle=theta_1,
            end_angle=theta_2,
            segement_min_degrees=45,
        )
        
        next_bounds = functools.reduce(Bounds.combine, map(Bounds.from_cubic_bezier, segments))
        
        return state.update(
            next_position,
            next_bounds,
        )

def evaluate_commands(commands: Iterable[PathCommand]) -> PathResult|None:
    initial_state = PathState.from_initial_position(Vec2(0, 0))
    result = functools.reduce(
        lambda state, command: command.update(state),
        commands,
        initial_state,
    )
    if result is initial_state:
        return None
    else:
        return PathResult.from_path_state(result)

@dataclass
class PathLetter():
    value: str
@dataclass
class PathNumber():
    value: float

type PathToken = PathLetter | PathNumber

def tokenize_str(path_str: str) -> Iterable[PathToken]:
    def extract_token(path_str: str) -> tuple[PathToken, str] | None:
        # This implementation is not compliant with the spec, as it would allow
        # the following syntax: "M,, 0 0"
        
        white_space_comma = "\t \n\f\r,"
        path_str = path_str.lstrip(white_space_comma)
        import re
        
        token = None
        if match := re.match(r"^[a-z]", path_str, re.IGNORECASE):
            command = match.group(0)
            return (PathLetter(command), path_str[match.end(0):])
        elif match := re.match(r"^(\+|-)?[0-9]*\.?[0-9]+", path_str):
            number = float(match.group(0))
            return (PathNumber(number), path_str[match.end(0):])
        else:
            return None
    
    
    while True:
        match extract_token(path_str):
            case None:
                break
            case (token, new_path_str):
                path_str = new_path_str
                yield token

def consume_tokens[T: PathToken](token_stream: Iterator[PathToken], token_type: type[T], count) -> Result[Iterable[T], str]:
    tokens = list[T]()
    for i in range(count):
        try:
            token = next(token_stream)
        except StopIteration:
            return Error(f"Ran out of tokens, expected {count} more, but only found {i}")
        if not isinstance(token, token_type):
            error_msg = f"Found incorrect token type, expected {token_type.__name__}, but found {token}"
            if len(tokens) > 0:
                error_msg += f" Found so far: {tokens}."
            return Error(error_msg)
        
        tokens.append(token)
    
    return Ok(tokens)

def parse_float(token_stream: Iterator[PathToken]) -> Result[float, str]:
    match consume_tokens(token_stream, PathNumber, 1):
        case Error(msg):
            return Error(msg)
        case Ok(result):
            (number_token,) = result
            return Ok(number_token.value)

def parse_vec2(token_stream: Iterator[PathToken]) -> Result[Vec2, str]:
    match consume_tokens(token_stream, PathNumber, 2):
        case Error(msg):
            return Error(msg)
        case Ok(result):
            (x, y) = result
            return Ok(Vec2(x.value, y.value))

def parse_bool(token_stream: Iterator[PathToken]) -> Result[bool, str]:
    match consume_tokens(token_stream, PathNumber, 1):
        case Error(msg):
            return Error(msg)
        case Ok(result):
            (number,) = result
            if number.value == 0 or number.value == 1:
                return Ok(bool(number.value))
            else:
                return Error(f"Could not parse flag from '{number}', expected 0 or 1")
    
def parse_rotation(token_stream: Iterator[PathToken]) -> Result[Rotation, str]:
    match parse_float(token_stream):
        case Error(msg):
            return Error(msg)
        case Ok(degrees):
            return Ok(Rotation(degrees))

# type PathArgumentType = type[float] | type[Vec2] | type[bool] | type[Rotation]
def parse_type(token_stream: Iterator[PathToken], argument_type: PathArgumentType) -> Result[PathArgument, str]:
    if issubclass(argument_type, float):
        return parse_float(token_stream)
    elif issubclass(argument_type, Vec2):
        return parse_vec2(token_stream)
    elif issubclass(argument_type, bool):
        return parse_bool(token_stream)
    elif issubclass(argument_type, Rotation):
        return parse_rotation(token_stream)
    elif issubclass(argument_type, int):
        # IDK what we should do here tbh...
        panic("Uhh, don't pass int to argument_type you dummy")
    else:
        assert_never(argument_type)
        panic()

def parse_str(path_str: str) -> Iterable[PathCommand]:
    tokens = more_itertools.peekable(tokenize_str(path_str))
    
    command_letters = {
        "m": MoveTo,
        
        "z": ClosePath,
        
        "l": LineTo,
        "h": HorizontalLineTo,
        "v": VerticalLineTo,
        
        "c": CurveTo,
        "s": ShorthandCurveTo,
        
        "q": QuadraticCurveTo,
        "t": ShorthandQuadraticCurveTo,
        
        "a": EllipticalArc,
    }
    
    while True:
        match next(tokens, None):
            case None:
                return
            case PathLetter(letter):
                lowercase_letter = letter.lower()
                if lowercase_letter not in command_letters:
                    panic(f"Encountered invalid command letter '{letter}' while parsing path: {path_str}")
                
                command_type = command_letters[lowercase_letter]
                arguments = command_type.arguments()
                found_any = False
                while True:
                    if not isinstance(tokens.peek(None), PathNumber):
                        if len(arguments) > 0:
                            if not found_any:
                                panic(f"Required arguments did not follow command {letter}")
                            break
                    
                    match collect_results(map(
                        lambda type: parse_type(tokens, type),
                        command_type.arguments()
                    )):
                        case Ok(arguments):
                            found_any = True
                            relative = not letter.isupper()
                            yield command_type(relative, *cast(list[Any], arguments))
                        case Error(msg):
                            panic(f"Failed parsing command {letter} due to: '{msg}'\n  while parsing: {path_str}")
                    if len(arguments) == 0:
                        break
            case _:
                # No more commands to consume
                remaining_tokens = tuple(tokens)
                if len(remaining_tokens) > 0:
                    print(f"Warning: got extra tokens {remaining_tokens}")
                    print(f"  while parsing: {path_str}")
                return


