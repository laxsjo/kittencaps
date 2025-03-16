from __future__ import annotations
from typing import *
from pathlib import Path
from dataclasses import dataclass
import tempfile
import subprocess
import re
import xml.etree.ElementTree as ET 
from playwright import sync_api as playwright
import io
from contextlib import contextmanager

from . import svg_builder
from .utils import *
from .error import *
from .color import *
from .pos import *
from .default import *
from . import iterator

@contextmanager
def create_page() -> Iterator[playwright.Page]:
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        
        try:
            yield page
        finally:
            browser.close()


def render_single_segment(page: playwright.Page, rect: Bounds, path: Path) -> None:
    pos, size = rect.to_pos_size()
    page.screenshot(
        path=path,
        clip={"x": pos.x, "y": pos.y, "width": size.x, "height": size.y},
    )

@dataclass
class _ImageTileMap():
    """
    Intermediate result returned by `render_segment`. Call `stich_together` to
    finish the operation. Is separate to allow easy measurement of how long the
    two stages take.
    """
    dir: tempfile.TemporaryDirectory
    paths: map[Path]
    count: Vec2[int]
    out_path: Path
    
    def stich_together(self) -> None:
        subprocess.check_call([
            "magick", "montage",
            *self.paths,
            "-mode", "Concatenate",
            "-tile", f"{self.count.x}x{self.count.y}",
            self.out_path
        ])
        
        self.dir.cleanup()

def render_segmented(page: playwright.Page, segment_max_width: Vec2[int], path: Path) -> _ImageTileMap:
    if page.viewport_size is None:
        panic(f"No viewport_size in {page}")
    total_size = Vec2[float](
        page.viewport_size["width"],
        page.viewport_size["height"]
    )
    total_bounds = Bounds.from_pos_size(Vec2(0, 0), total_size)
    temp_dir = tempfile.TemporaryDirectory()
    directory = Path(temp_dir.name)
    indices = list[Vec2[int]]()
    for index_pair, segment in total_bounds.as_segments(segment_max_width.cast_to(int)):
        render_single_segment(page, segment, directory / f"{index_pair.x}_{index_pair.y}.png")
        indices.append(index_pair)
    
    # Sorted, so that the first n items constitutes the first row, the second
    # constitutes the second row and so on.
    indices_sorted = sorted(indices, key=lambda pair: tuple(pair[::-1]))
    paths = map(
        lambda pair: directory / f"{pair.x}_{pair.y}.png", 
        indices_sorted
    )
    
    count = Vec2[int].max(*indices) + Vec2(1, 1)
    return _ImageTileMap(temp_dir, paths, count, path)
