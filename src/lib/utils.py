from typing import *
import sys
import traceback
import os
from dataclasses import dataclass
from time import time


__all__ = [
    "eprint",
    "panic",
    "todo",
    "impossible",
    "Todo",
    "assert_instance",
    "inspect",
    "time_it",
    "log_split_action_time",
    "log_action_time",
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

class StartedTimedAction:
    def __init__(self, action: str):
        self.action = action
        self.start = time()
        
        print(f"{action}...", end="")
    
    def done(self) -> None:
        seconds = time() - self.start
        
        print(f"\r{self.action} took {seconds * 1000.0:.1f} ms")

def log_split_action_time(action: str) -> StartedTimedAction:
    return StartedTimedAction(action)

def log_action_time[T](action: str, function: Callable[[], T]) -> T:
    timer = log_split_action_time(action)
    
    result = function()
    
    timer.done()
    
    return result
