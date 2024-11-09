from typing import *
import subprocess

from .error import *
from .utils import *

__all__ = [
    "run_command",
    "run_command_infalliable",
]

def run_command(command: str, *args: str) -> Tuple[int, str]:
    command_list = [command, *args]
    result = subprocess.run(command_list, capture_output=True, text=True)
    if result.returncode != 0:
        return (result.returncode, result.stderr)
    else:
        return (result.returncode, result.stdout)

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
