from typing import *
import sys
import traceback
import os
from time import time
import curses


__all__ = [
    "eprint",
    "panic",
    "todo",
    "impossible",
    "Todo",
    "assert_instance",
    "inspect",
    "time_it",
    "StartedTimedAction",
    "ActionProgress",
    "log_action",
]

curses.setupterm()

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

def get_move_cursor_up() -> str:
    match curses.tigetstr("cuu1"):
        case None:
            return ""
        case value:
            return value.decode()

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
        self.start_time = time()
        
        print(f"{action}...")
    
    def update(self, *, updated_action: str | None = None) -> None:
        if updated_action is not None:
            self.action = updated_action
        
        seconds = time() - self.start_time
        print(f"{get_move_cursor_up()}\r{self.action} for {seconds * 1000.0:.1f} ms")
        
    
    def done(self, *, updated_action: str | None = None) -> None:
        if updated_action is not None:
            self.action = updated_action

        seconds = time() - self.start_time
        print(f"{get_move_cursor_up()}\r{self.action} took {seconds * 1000.0:.1f} ms")

class ActionProgress(Protocol):
    def render(self) -> str | None: ...
    def render_finished(self) -> str | None: ...

def log_action[P: ActionProgress, R](action: str, function: Callable[[Callable[[P], None]], R]) -> R:
    timer = StartedTimedAction(action)
    
    last_progress: P | None = None
    def handler(progress: P) -> None:
            nonlocal last_progress
            last_progress = progress
            
            progress_content = progress.render()
            if progress_content is None:
                progress_str = ""
            else:
                progress_str = f" {progress_content}"
                
            timer.update(updated_action=action + progress_str)
    
    result = function(handler)
    
    seconds = time() - timer.start_time
    
    # Type inference doesn't recognize that a value P may be assigned
    last_progress = cast(P | None, last_progress)
    
    if last_progress is None:
        last_progress_str = ""
    else:
        last_progress_str = f" {last_progress.render_finished()}"
    timer.done(updated_action=action + last_progress_str)
    
    return result
