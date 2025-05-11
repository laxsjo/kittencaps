from typing import *
import collections.abc
import sys
import traceback
import os

__all__ = [
    "eprint",
    "panic",
    "todo",
    "impossible",
    "Todo",
    "assert_instance",
    "inspect",
    "time_it",
]

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def panic(reason: str = "", traceback_level: int = 0) -> Never:
    location = traceback.extract_stack()[-(traceback_level + 2)]
    
    path = os.path.relpath(location.filename, os.getcwd())
    
    message = f"Paniced at '{reason}'\n"
    message += f" --> {path}:{location.lineno}"
    if location.colno is not None:
        message += f":{location.colno}"
    message += f" in {location.name}"
    
    eprint(message)
    exit(101)

def todo() -> Never:
    panic("TODO: unfinished code", 1)
    
def impossible() -> Never:
    panic("Reached impossible code", 1)

type Todo = Never

# Assert that value is an instance of class, and return that value if so.
def assert_instance[T](_class: type[T], value: Any) -> T:
    if isinstance(value, _class):
        return value
    else:
        panic(f"assert_instance: Value {value} is not an instance of {_class}")

def inspect[T](value: T) -> T:
    print(value)
    return value

def time_it[T](function: Callable[[], T]) -> tuple[T, float]:
    from time import time
    start = time()
    
    result = function()
    
    end = time()
    return result, end - start

class WriteHooked[T: (str, bytes)](IO[T]):
    def __init__(self, file: IO[T], on_write: Callable[[int], None]) -> None:
        self.file = file
        self.on_write = on_write
    
    def __setattr__(self, name: str, value: Any) -> None:
        match name:
            case "file" | "on_write":
                super().__setattr__(name, value)
            case _:
                self.file.__setattr__(name, value)
    
    def __getattribute__(self, name: str) -> None:
        match name:
            case "file", "on_write" | "write":
                return super().__getattribute__(name)
            case _:
                return getattr(super().__getattribute__("file"), name)
    
    def write(self, s: collections.abc.Buffer|T) -> int:
        # The typeshed IO protocol requires that write has an overload taking
        # a Buffer, but I'm not sure why, and I'm just going ignore that :)
        s = cast(T, s)
        
        result = self.file.write(s)
        self.on_write(result)
        return result

class WriteTracker(TextIO):
    # TODO: For some reason this makes `fileno` attribute be `None`.
    def __init__(self, file: TextIO) -> None:
        self.file = file
        self.write_amount = 0
    
    def __setattr__(self, name: str, value: Any) -> None:
        match name:
            case "file" | "write_amount":
                super().__setattr__(name, value)
            case _:
                self.file.__setattr__(name, value)
    
    # Called for *every* access
    def __getattribute__(self, name: str) -> Any:
        match name:
            case "buffer":
                def on_write(amount: int) -> None:
                    self.write_amount += amount
                return WriteHooked(self.file.buffer, on_write)
            case "file" | "write_amount" | "write":
                return super().__getattribute__(name)
            case _:
                return getattr(super().__getattribute__("file"), name)
    
    def write(self, s: str) -> int:
        result = self.file.write(s)
        self.write_amount += result
        return result
