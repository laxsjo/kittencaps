from __future__ import annotations
from dataclasses import dataclass
from typing import *
import itertools
import more_itertools
import math
import os
import io

from .utils import *

__all__ = [
    "Range",
    "source_extract_range",
    "source_extract_range_str",
    "SourceEditor",
]

_T_contra = TypeVar("_T_contra", contravariant=True)
class SupportsWrite(Protocol[_T_contra]):
    def write(self, s: _T_contra, /) -> object: ...

type StrOrBytes = str | bytes
type FileDescriptorOrPath = int | str | bytes | os.PathLike[str] | os.PathLike[bytes]

type Range = tuple[int, int]

def source_extract_range[T: StrOrBytes](src: T, range: tuple[int, int]) -> T:
    return cast(T, src[range[0]:range[1]])

def source_extract_range_str(src: StrOrBytes, range: tuple[int, int]) -> str:
    if isinstance(src, str):
        return src[range[0]:range[1]]
    elif isinstance(src, bytes):
        return src[range[0]:range[1]].decode()
    else:
        impossible()

def index_in_range(index: int, range: Range) -> bool:
    return range[0] <= index < range[1]

def collapse_ranges(ranges: set[Range]) -> list[Range]:
    ranges_sorted = iter(sorted(ranges, key=lambda x: x[0]))
    try:
        result_ranges = [next(ranges_sorted)]
    except StopIteration:
        return []
    
    for range in ranges_sorted:
        last_index = len(result_ranges) - 1
        match result_ranges[last_index]:
            case (start, end) if end < range[0]:
                result_ranges.append(range)
            case (start, end):
                result_ranges[last_index] = (start, range[1])
    
    return result_ranges

def invert_ranges(global_range: Range, sorted_subranges: Iterable[Range]) -> Iterable[Range]:
    last_end = global_range[0]
    for start, end in sorted_subranges:
        if start < last_end:
            # Range overlaps with previous
            start = last_end
        if end < start:
            # Range is not well formed, or is contained within previous range.
            continue
        
        if last_end == start:
            continue
        yield (last_end, start)
        last_end = end
    
    if last_end != global_range[1]:
        yield (last_end, global_range[1])

def range_split_at_indices(range: Range, indices: Iterable[int]) -> Iterable[Range]:
    current_start = range[0]
    for index in indices:
        if index < current_start:
            panic(f"Index {index} is lower than either the given range {range} or the previous index.", 1)
        if index > range[1]:
            panic(f"Index {index} is greater than the given range {range}.", 1)
        yield (current_start, index)
        current_start = index
        
    yield (current_start, range[1])

@dataclass
class _Insertion[T: StrOrBytes]:
    content: T

@dataclass
class _Copy:
    range: Range

class SourceEditor[T: StrOrBytes]:
    src: T
    _deleted_ranges: set[Range]
    _insertions: set[tuple[int, T]]
    
    @overload
    @staticmethod
    def from_readable(readable: BinaryIO) -> SourceEditor[bytes]:
        ...
    @overload
    @staticmethod
    def from_readable(readable: TextIO) -> SourceEditor[str]:
        ...
    @staticmethod
    def from_readable(readable: TextIO|BinaryIO) -> SourceEditor[str]|SourceEditor[bytes]:
        src = readable.read()
        # Cast is safe due to overload definitions
        return cast(Never, SourceEditor(src))
    
    def __init__(self, src: T) -> None:
        self.src = src
        self._deleted_ranges = set()
        self._insertions = set()
    
    def delete(self, range: Range) -> None:
        self._deleted_ranges.add(range)
        
    def insert(self, index: int, content: T) -> None:
        self._insertions.add((index, content))
    
    def _resolve_actions(self) -> Iterable[_Insertion[T] | _Copy]:
        copied_ranges = tuple(invert_ranges(
            (0, len(self.src)),
            collapse_ranges(self._deleted_ranges)
        ))
        
        insertions = sorted(self._insertions, key=lambda pair: pair[0])
        
        def with_insertions_in_between(ranges: Sequence[Range], _insertions: Sequence[tuple[int, T]]) -> Iterator[_Insertion[T] | _Copy]:
            ranges_with_next = more_itertools.peekable(cast(
                Iterator[tuple[Range, Range|None]],
                more_itertools.windowed(itertools.chain(ranges, (None,)), 2)
            ))
            
            if ranges_with_next.peek(None) == None:
                # There are no ranges.
                yield from map(lambda pair: _Insertion(pair[1]), _insertions)
                return
            
            first_range = ranges_with_next.peek()[0]
            # Yield insertions before first range
            yield from more_itertools.filter_map(
                lambda pair: _Insertion(pair[1]) if pair[0] <= first_range[0] else None,
                _insertions
            )
            
            for range, next_range in cast(
                Iterator[tuple[Range, Range|None]],
                more_itertools.windowed(itertools.chain(copied_ranges, (None,)), 2)
            ):
                yield _Copy(range)
                
                if next_range == None:
                    next_start = math.inf
                else:
                    next_start = next_range[0]
                
                end = range[1]
                
                # Yield insertions after current range but before next
                yield from more_itertools.filter_map(
                    lambda pair: _Insertion(pair[1]) if end <= pair[0] < next_start else None,
                    insertions
                )
        # Add insertions that lie between copied_ranges
        initial_actions = with_insertions_in_between(copied_ranges, insertions)
        
        # Add insertions that lie within copied_ranges
        for action in initial_actions:
            match action:
                case _Insertion(_) as action:
                    yield action
                case _Copy(range) as action:
                    insertions_in_range = tuple(filter(
                        lambda pair: index_in_range(pair[0], range),
                        insertions
                    ))
                    
                    split_ranges = range_split_at_indices(range, map(lambda pair: pair[0], insertions_in_range))
                    
                    yield from more_itertools.interleave_longest(
                        map(_Copy, split_ranges),
                        map(lambda pair: _Insertion(pair[1]), insertions_in_range)
                    )
    
    def write(self, file: SupportsWrite[T]):
        for action in list(self._resolve_actions()):
            match action:
                case _Insertion(content):
                    file.write(content)
                case _Copy(range):
                    file.write(source_extract_range(self.src, range))
    
    def output(self) -> T:
        if isinstance(self.src, str):
            output = io.StringIO()
            self = cast(SourceEditor[str], self)
            self.write(output)
        else:
            output = io.BytesIO()
            self = cast(SourceEditor[bytes], self)
            self.write(output)
        
        return cast(T, assert_type(output.getvalue(), StrOrBytes))
