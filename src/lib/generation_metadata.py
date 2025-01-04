from __future__ import annotations
from typing import *
from dataclasses import dataclass
import os
import json5
import jsonschema
import pathlib

from .error import *
from .utils import *
from .font import *
from .sp_color import *
from .color import *
from . import project
from .theme import *
from . import kle_ext as kle

__all__ = [
    "GenerationMetadata",
]

@dataclass
class GenerationMetadata():
    layout_path: pathlib.Path
    theme_path: pathlib.Path
    
    @classmethod
    def from_file(cls, path: str | os.PathLike) -> Self:
        # Why does this not exist :,(
        # type JsonValueSimple = str | int | None
        # type JsonValue = JsonValueSimple | dict[str, JsonValue] | list[JsonValue]
        
        with open(project.path_to_absolute("assets/schemas/generation-metadata-schema.json")) as file:
            schema = json5.load(file)
        
        path = pathlib.Path(path)
        if not path.exists():
            panic(f"File '{path}' does not exist")
        
        if not path.is_file():
            panic(f"'{path}' is not a file")
        
        with open(path) as file:
            metadata = json5.load(file)
        
        try:
            jsonschema.validate(metadata, schema)
        except jsonschema.ValidationError as error:
            panic(f"The specified generation metadata '{path}' json is invalid:\n    {error}")
        
        return cls(
            layout_path=pathlib.Path(metadata["layout_path"]),
            theme_path=pathlib.Path(metadata["theme_path"]),
        )
    
    def load_layout(self) -> kle.ExtendedKeyboard:
        with open(self.layout_path, "r") as file:
            return kle.ExtendedKeyboard.from_json(
                json5.load(file)
            )
    
    def load_theme(self) -> Theme:
        return Theme.load_file(self.theme_path)

    def store_at(self, path: pathlib.Path) -> None:
        with open(path, "w") as file:
            result = {
                "layout_path": str(self.layout_path),
                "theme_path": str(self.theme_path),
            }
            
            json5.dump(result, file)
