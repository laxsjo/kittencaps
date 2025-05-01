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

from . import svg_builder, render
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

def render_segmented(page: playwright.Page, segment_max_width: Vec2[int], path: Path, *, progress_handler: Callable[[render.TileRenderProgress], None] | None = None) -> render.ImageTileMap:
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
    pairs = tuple(total_bounds.as_segments(segment_max_width.cast_to(int)))
    for index, (index_pair, segment) in enumerate(pairs):
        if progress_handler is not None:
            progress_handler(render.TileRenderProgress(index, len(pairs)))
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
    return render.ImageTileMap(temp_dir, paths, count, path)
