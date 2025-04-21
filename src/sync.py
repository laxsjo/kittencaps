from typing import *
import argparse
import itertools

from .lib import project, shell
from .lib.shell import console

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Regenerate all generated files in the project, using all combinations of layouts and themes. Essentially a wrapper around all of the other generation scripts.",
    )
    
    _ = parser.parse_args()
    
    layouts_dir = project.path_to_absolute("assets/layouts/")
    themes_dir = project.path_to_absolute("assets/themes/")
    
    # Make sure their order is deterministic, it doesn't really matter, it just
    # makes me happy :)
    layouts = sorted(layouts_dir.iterdir(), key=str)
    themes = sorted(themes_dir.iterdir(), key=str)
    for layout, theme in itertools.product(layouts, themes):
        console.print(f"\n[bold cyan]Generating layout {layout.stem} as {theme.stem}...[/bold cyan]")
        
        shell.run_command_print_exit_fail(
            "just", "generate-keycaps",
            f"{layout.stem}",
            f"{theme.stem}",
        )
        
        shell.run_command_print_exit_fail(
            "just", "generate-render-scene",
            f"{layout.stem}",
            f"{theme.stem}",
        )
    
    console.print(f"\n[bold cyan]Updating icon SVG colors...[/bold cyan]")
    
    shell.run_command_print_exit_fail("just", "update-icon-palettes")

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
