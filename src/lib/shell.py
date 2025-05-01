from typing import *
import subprocess
import select
import os
import sys
import io
from rich.console import Console

from .error import *
from .utils import *

__all__ = [
    "console",
    "run_command",
    "run_command_print_exit_fail",
    "run_command_infalliable",
]

type StrOrBytesPath = str | bytes | os.PathLike[str] | os.PathLike[bytes]
type SubprocessCMD = StrOrBytesPath | Sequence[StrOrBytesPath]

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

def run_print_and_capture_output(args: SubprocessCMD, *, input: str | None = None) -> subprocess.CompletedProcess[str]:
    """
    Conceptually a wrapper around `subprocess.run`, with it being ran in text
    mode and capturing any output while also writing it to stdout or stderr.
    # If
    # anything is output, then the specified prefix is written to stdout before
    # the first byte of output is.
    # `suprocess.CalledProcessError` is raised if the exit-code was non-zero.
    """
    
    
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    
    process.communicate
    
    if input is not None:
        match process.stdin:
            case None:
                impossible()
            case stdin:
                # This might produce deadlocks...
                stdin.write(input)
                stdin.close()
    
    match process.stdout:
        case None:
            impossible()
        case stdout:
            pass
    match process.stderr:
        case None:
            impossible()
        case stderr:
            pass
    
    output_stdout = io.StringIO()
    output_stderr = io.StringIO()
    
    while process.returncode is None:
        process.poll()
        
        ready = select.select([stdout, stderr], [], [], 1)
        
        if stdout in ready[0]:
            data = stdout.readline()
            if len(data) > 0:
                print(data, end="", file=sys.stdout)
                output_stdout.write(data)
        
        if stderr in ready[0]:
            data = stderr.readline()
            if len(data) > 0:
                print(data, end="", file=sys.stderr)
                output_stderr.write(data)
    
    if process.returncode != 0:
        raise subprocess.CalledProcessError(
            process.returncode,
            args,
            output_stdout.getvalue(),
            output_stderr.getvalue(),
        )

    return subprocess.CompletedProcess(
        args,
        process.returncode,
        output_stdout.getvalue(),
        output_stderr.getvalue(),
    )
