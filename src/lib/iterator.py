from typing import *
import itertools
import more_itertools

__all__ = [
    "chunks",
]

@overload
def chunks[T](iterator: Iterable[T], chunk_size: Literal[5]) -> Iterable[tuple[T, T, T, T, T]]:
    ...
@overload
def chunks[T](iterator: Iterable[T], chunk_size: Literal[4]) -> Iterable[tuple[T, T, T, T]]:
    ...
@overload
def chunks[T](iterator: Iterable[T], chunk_size: Literal[3]) -> Iterable[tuple[T, T, T]]:
    ...
@overload
def chunks[T](iterator: Iterable[T], chunk_size: Literal[2]) -> Iterable[tuple[T, T]]:
    ...
@overload
def chunks[T](iterator: Iterable[T], chunk_size: Literal[1]) -> Iterable[tuple[T]]:
    ...
@overload
def chunks[T](iterator: Iterable[T], chunk_size: Literal[0]) -> Iterable[tuple[()]]:
    ...
def chunks[T](iterator: Iterable[T], chunk_size: int) -> Iterable[tuple[T, ...]]:
    """
    Returns an iterator over `chunk_size` elements of the slice at a time,
    starting at the beginning of the slice.
    
    The chunks are slices and do not overlap. If `chunk_size` does not divide
    the length of the slice, then the last chunk will not have length
    `chunk_size`.
    """
    
    while True:
        chunk = tuple(more_itertools.take(chunk_size, iterator))
        if len(chunk) != chunk_size:
            return
        
        yield chunk
