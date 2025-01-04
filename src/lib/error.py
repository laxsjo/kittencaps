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
    "unwrap"
]

type Result[OkType, ErrType] = Ok[OkType]|Error[ErrType]

@dataclass
class Error[T]:
    value: T
    
    def unwrap(self) -> Never:
        return panic(f"Tried to unwrap {self}")
    
    def unwrap_err(self) -> T:
        return self.value

@dataclass
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
