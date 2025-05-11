#!/usr/bin/env python

from typing import *
from copy import deepcopy
from enum import IntEnum
import subprocess
import os
from pathlib import Path
from dataclasses import dataclass
import io
import zipfile

from .svg_builder import *
from .pos import *
from . import svg, normalize, font, action
from . import keyboard_builder
from . import kle_ext as kle
from .config import *
from .utils import *
from .error import *
from .color import *

class ArchiveStep(IntEnum):
    SCANNING_FOR_FONTS = 0
    BUILDING_SVG = 1
    RENDERING_PRINT = 2
    RENDERING_OUTLINE = 3
    BUILDING_OVERVIEW = 4
    

@dataclass
class ArchiveProgress(action.ActionProgress):
    step: ArchiveStep
    filename: str
    current_icon: int
    total_icons: int
    
    def render(self) -> str | None:
        match self.step:
            case ArchiveStep.SCANNING_FOR_FONTS:
                return f"scanning font directories"
            case ArchiveStep.BUILDING_OVERVIEW:
                return f"building '{self.filename}'"
            case ArchiveStep.BUILDING_SVG:
                step_str = "building SVG     "
            case ArchiveStep.RENDERING_PRINT:
                step_str = "rendering print  "
            case ArchiveStep.RENDERING_OUTLINE:
                step_str = "rendering outline"
        return f"icon {self.current_icon + 1} / {self.total_icons} '{self.filename}' {step_str}"
    
    def render_finished(self) -> str | None:
        return f"{self.total_icons} icon(s)"

def package_keycap_icons_archive(
    layout: kle.Keyboard,
    config: Config,
    key_templates: SvgSymbolSet,
    *,
    progress_handler: Callable[[ArchiveProgress], None] | None = None,
) -> io.BytesIO:
    progress_handler = progress_handler if progress_handler is not None else lambda _: None
    base_builder = SvgDocumentBuilder()\
        .palette(config.colors)\
        .add_icon_set(key_templates)
    
    file = io.BytesIO()
    
    archive = zipfile.ZipFile(file, "w")
    archive.mkdir("print")
    archive.mkdir("outlined")
    
    progress_handler(ArchiveProgress(
        ArchiveStep.SCANNING_FOR_FONTS, "", 0, 0
    ))
    
    # For some reason resvg doesn't scan the share directories from
    # XDG_DATA_DIRS for fonts. Also scanning all of them takes a lot of time,
    # so we do it once, instead of letting resvg do it for every image.
    fonts_arguments = [
        f"--use-font-file={path}"
        for directory in os.environ["XDG_DATA_DIRS"].split(":")
        for path in font.scan_fonts_dir(Path(directory))
    ]
    
    for i, key in enumerate(layout.keys):
        position_u = keyboard_builder.resolve_key_position(key)
        image_name = \
            f"{position_u.x:.3g}".replace(".", "-") \
            + "_" \
            + f"{position_u.y:.3g}".replace(".", "-") \
            + ".png"
        
        progress_handler(
            ArchiveProgress(ArchiveStep.BUILDING_SVG, image_name, i, len(layout.keys))
        )
        
        builder = deepcopy(base_builder)
        
        factory = keyboard_builder.KeycapFactory(config).configure(
            keyboard_builder.KeycapRenderingOptions(
                shading=False,
                outline=keyboard_builder.OutlineOption.INCLUDE_HIDDEN,
                include_margin=True,
            ),
            key_templates
        )
        info = keyboard_builder.KeycapInfo(key)
        element = factory.create(info)
        builder.set_viewbox(svg.ViewBox(
            Vec2.promote(-config.icon_margin),
            element.size + Scaling(config.icon_margin * 2)
        ))
        builder.add_element(make_element(
                "defs",
                {
                    "id": "factory-elements",
                },
                factory.get_defs()
            ))
        builder.add_element(element.element)
        
        tree = builder.build()
        normalize.palette_color_references(tree, config)
        normalize.reduce_color_spaces_to_srgb(tree)
        normalize.reduce_transform_origin(tree)
        
        progress_handler(
            ArchiveProgress(ArchiveStep.RENDERING_PRINT, image_name, i, len(layout.keys))
        )
        
        image = subprocess.check_output(
            [
                "resvg",
                f"--zoom={config.print_scale}",
                # Note: resvg complains when using stdin without specifying
                # `--resources-dir` for some reason...
                "--resources-dir=/dev/null",
                "-",
                "-c",
                *fonts_arguments,
            ],
            input=svg.tree_to_str(tree).encode(),
        )
        archive.writestr(f"print/print_{image_name}", image)
        progress_handler(
            ArchiveProgress(ArchiveStep.RENDERING_OUTLINE, image_name, i, len(layout.keys))
        )
        # Show icon outlines
        for outline in svg.tree_find_by_class(tree, "outline"):
            outline.set("visibility", "visible")
        image = subprocess.check_output(
            [
                "resvg",
                f"--zoom={config.print_outlined_scale}",
                # Note: resvg complains when using stdin without specifying
                # `--resources-dir` for some reason...
                "--resources-dir=/dev/null",
                "-",
                "-c",
                *fonts_arguments,
            ],
            input=svg.tree_to_str(tree).encode(),
        )
        archive.writestr(f"outlined/outlined_{image_name}", image)
    
    progress_handler(
        ArchiveProgress(ArchiveStep.BUILDING_OVERVIEW, "overview.png", len(layout.keys) - 1, len(layout.keys))
    )
    
    tree = keyboard_builder.KeyboardBuilder(config, key_templates)\
        .configure_factory(keyboard_builder.KeycapRenderingOptions(
            shading=False,
            outline=keyboard_builder.OutlineOption.SHOW,
            include_margin=True,
        ))\
        .embed_fonts(False)\
        .keys(*layout.keys)\
        .build()
    normalize.palette_color_references(tree, config)
    normalize.reduce_color_spaces_to_srgb(tree)
    normalize.reduce_transform_origin(tree)
    
    image = subprocess.check_output(
        [
            "resvg",
            f"--zoom={config.overview_scale}",
            # Note: resvg complains when using stdin without specifying
            # `--resources-dir` for some reason...
            "--resources-dir=/dev/null",
            "-",
            "-c",
            *fonts_arguments,
        ],
        input=svg.tree_to_str(tree).encode(),
    )
    archive.writestr(f"overview.png", image)
    
    archive.close()
    return file
