from typing import *
import sys
import traceback
import os

__all__ = [
    "eprint",
    "panic",
    "todo",
    "Todo",
    "assert_instance",
]

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def panic(reason: str, traceback_level: int = 0) -> Never:
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

type Todo = Never

# Assert that value is an instance of class, and return that value if so.
def assert_instance[T](_class: type[T], value: Any) -> T:
    if isinstance(value, _class):
        return value
    else:
        panic(f"assert_instance: Value {value} is not an instance of {_class}")
