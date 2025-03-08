from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import *
from .utils import *

# Matchable error return value

__all__ = [
    "Result",
    "Error",
    "Ok",
    "Option",
    "map_some",
    "map_ok",
    "unwrap",
    "unwrap_or",
    "collect_results",
]

type Result[OkType, ErrType] = Ok[OkType]|Error[ErrType]

@dataclass(frozen=True)
class Error[T]:
    value: T
    
    def unwrap(self) -> Never:
        return panic(f"Tried to unwrap {self}")
    
    def unwrap_err(self) -> T:
        return self.value

@dataclass(frozen=True)
class Ok[T]:
    value: T
    
    def unwrap(self) -> T:
        return self.value
    
    def unwrap_err(self) -> Never:
        return panic(f"Tried to unwrap_err {self}")

type Option[T] = T | None

def map_some[T, R](value: Option[T], f: Callable[[T], R]) -> Option[R]:
    match value:
        case None:
            return value
        case some_value:
            return f(some_value)

def map_ok[T, U, R](value: Result[T, U], f: Callable[[T], R]) -> Result[R, U]:
    match value:
        case Error(err_value):
            return Error(err_value)
        case Ok(ok_value):
            return Ok(f(ok_value))

def unwrap[T](value: Result[T, Any]|Option[T]) -> T:
    match value:
        case Error(error):
            panic(f"Tried to unwrap error({error})", 1)
        case None:
            panic(f"Tried to unwrap None", 1)
        case Ok(ok):
            return ok
        case some:
            return some

def unwrap_or[T, U](value: Result[T, Any]|Option[T], default: U) -> T | U:
    match value:
        case Error(error):
            return default
        case None:
            return default
        case Ok(ok):
            return ok
        case some:
            return some

def collect_results[T, U](iterable: Iterable[Result[T, U]]) -> Result[list[T], U]:
    result = list[T]()
    iterator = iter(iterable)
    try:
        while True:
            match next(iterator):
                case Ok(value):
                    result.append(value)
                case Error(value):
                    return Error(value)
    except StopIteration:
        return Ok(result)
