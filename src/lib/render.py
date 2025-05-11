from __future__ import annotations
from typing import *
from pathlib import Path
from dataclasses import dataclass
import tempfile
import subprocess
import xml.etree.ElementTree as ET 

from . import action
from .utils import *
from .error import *
from .color import *
from .pos import *
from .default import *

@dataclass(frozen=True)
class TileRenderProgress(action.ActionProgress):
    current_tile: int
    total_tiles: int
    
    def render(self) -> str | None:
        return f"tile {self.current_tile + 1}/{self.total_tiles}"
    
    def render_finished(self) -> str | None:
        return f"{self.total_tiles} tile(s)"

@dataclass
class ImageTileMap():
    """
    Intermediate result returned by `render_segmented`. Call `stich_together` to
    finish the operation. Is separate to allow easy measurement of how long the
    two stages take.
    """
    dir: tempfile.TemporaryDirectory
    paths: Iterator[Path]
    count: Vec2[int]
    out_path: Path
    
    def stich_together(self) -> None:
        subprocess.check_call([
            "magick", "montage",
            *self.paths,
            "-mode", "Concatenate",
            "-tile", f"{self.count.x}x{self.count.y}",
            "-background", "none",
            self.out_path,
        ])
        
        self.dir.cleanup()

type SegmentRenderer = Callable[[Bounds, Path], None]

def render_segmented(
    area: Bounds,
    max_segment_size: Vec2[int],
    path: Path,
    segment_renderer: SegmentRenderer,
    *,
    progress_handler: Callable[[TileRenderProgress], None] | None = None
) -> ImageTileMap:
    temp_dir = tempfile.TemporaryDirectory()
    directory = Path(temp_dir.name)
    indices = list[Vec2[int]]()
    pairs = tuple(area.as_segments(max_segment_size.cast_to(int)))
    for index, (index_pair, segment) in enumerate(pairs):
        if progress_handler is not None:
            progress_handler(TileRenderProgress(index, len(pairs)))
        segment_renderer(segment, directory / f"{index_pair.x}_{index_pair.y}.png")
        indices.append(index_pair)
    
    # Sorted, so that the first n items constitutes the first row, the second
    # constitutes the second row and so on.
    indices_sorted = sorted(indices, key=lambda pair: tuple(pair[::-1]))
    paths = map(
        lambda pair: directory / f"{pair.x}_{pair.y}.png", 
        indices_sorted
    )
    count = Vec2[int].max(*indices) + Vec2(1, 1)
    
    return ImageTileMap(temp_dir, paths, count, path)
