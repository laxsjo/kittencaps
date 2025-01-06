from typing import *
import subprocess
import sys
from rich.console import Console

from .error import *
from .utils import *

__all__ = [
    "console",
    "run_command",
    "run_command_print_exit_fail",
    "run_command_infalliable",
]

console = Console()

def run_command(command: str, *args: str) -> Tuple[int, str]:
    command_list = [command, *args]
    result = subprocess.run(command_list, capture_output=True, text=True)
    if result.returncode != 0:
        return (result.returncode, result.stderr)
    else:
        return (result.returncode, result.stdout)

# Run system command and print stdout and stderr, and exit if subprocess exits
# with a non-zero exit code. Never return anything, therefore the command is ran
# purely for it's side effects.
def run_command_print_exit_fail(command: str, *args: str) -> None:
    command_list = [command, *args]
    result = subprocess.run(command_list, stdout=sys.stdout, stderr=sys.stderr)
    if result.returncode != 0:
        exit(result.returncode)

# Run command and panic on non-zero exit codes
def run_command_infalliable(command: str, *args: str) -> str:
    command_list = [command, *args]
    result = subprocess.run(command_list, capture_output=True, text=True)
    if result.returncode == 127:
        panic(f"{command} is not installed!")
    if result.returncode != 0:
        print(result.stderr)
        panic(f"Running '{" ".join(command_list)}' failed with exit-code {result.returncode}")
    
    return result.stdout
