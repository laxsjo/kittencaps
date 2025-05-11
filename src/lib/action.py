
from typing import *
import sys
from time import time
import curses

from . import utils, project

_stdout = utils.WriteTracker(sys.stdout)
_stderr = utils.WriteTracker(sys.stderr)

sys.stdout = _stdout
sys.stderr = _stderr

curses.setupterm()

def get_written_output_length() -> Tuple[int, int]:
    """
    Get an identifier value which if equal to the result of an earlier call of
    this function means that something has been written to stdout or
    stderr since then.
    """
    return (_stdout.write_amount, _stderr.write_amount)


def get_clear_last_progress() -> str:
    if project.verbose():
        return ""
    else:
        return "".join((
            (curses.tigetstr("cuu1") or bytes()).decode(),
            "\r",
            (curses.tigetstr("el") or bytes()).decode(),
        ))

class Timer():
    def __init__(self, start_time: float | None = None):
        self.start_time = time() if start_time is None else start_time
    
    def get_pretty(self) -> str:
        seconds = time() - self.start_time
        if seconds < 1:
            return f"{seconds * 1000.0:.1f} ms"
        else:
            return f"{seconds:.2f} s"

class StartedTimedAction:
    def __init__(self, action: str):
        self.action = action
        self.timer = Timer()
        
        print(f"{action}...")
        self.last_write_amount = get_written_output_length()
    
    def update(self, *, updated_action: str | None = None) -> None:
        if updated_action is not None:
            self.action = updated_action
        
        if self.last_write_amount == get_written_output_length():
            print(get_clear_last_progress(), end="")
        print(f"{self.action} for {self.timer.get_pretty()}")
        self.last_write_amount = get_written_output_length()
    
    def done(self, *, updated_action: str | None = None) -> None:
        if updated_action is not None:
            self.action = updated_action

        if self.last_write_amount == get_written_output_length():
            print(get_clear_last_progress(), end="")
        print(f"{self.action} took {self.timer.get_pretty()}")
        self.last_write_amount = get_written_output_length()

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
    
    # Type inference doesn't recognize that a value P may be assigned...
    last_progress = cast(P | None, last_progress)
    
    if last_progress is None:
        last_progress_str = ""
    else:
        last_progress_str = f" {last_progress.render_finished()}"
    timer.done(updated_action=action + last_progress_str)
    
    return result
