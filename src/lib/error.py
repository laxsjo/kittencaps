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
    "unwrap"
]

type Result[OkType, ErrType] = Ok[OkType]|Error[ErrType]

@dataclass
class Error[T]:
    value: T
    
    def unwrap(self) -> Never:
        return panic(f"Tried to unwrap ${self}")
    
    def unwrap_err(self) -> T:
        return self.value

@dataclass
class Ok[T]:
    value: T
    
    def unwrap(self) -> T:
        return self.value
    
    def unwrap_err(self) -> Never:
        return panic(f"Tried to unwrap_err {self}")

def unwrap[T](option: T|Error[Any]|None) -> T:
    if isinstance(option, Error):
        panic(f"Tried to unwrap error {option}", 1)
    if option == None:
        panic(f"Tried to unwrap None", 1)
    return option
