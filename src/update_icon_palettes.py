from __future__ import annotations
from typing import *
from pathlib import Path
import os
import argparse
import re
import fnmatch
import itertools
import more_itertools
import tree_sitter as ts
import tree_sitter_xml as ts_xml
import io
import hashlib

from .lib.utils import *
from .lib import font as Font
from .lib.svg_builder import *
from .lib.keyboard_builder import *
from .lib.pos import *
from .lib.theme import *
from .lib.color import *
from .lib import project
from .lib.error import *
from .lib.source import *
from .lib import svg

XML_LANGUAGE = ts.Language(ts_xml.language_xml())
XML_PARSER = ts.Parser(XML_LANGUAGE)

def node_get_content_in_src(node: ts.Node, src: bytes) -> str:
    return source_extract_range(src, node.byte_range).decode()

def node_get_child_by_id(node: ts.Node, id: str) -> ts.Node|None:
    query = XML_LANGUAGE.query(
fr"""
((element [
    (EmptyElemTag (Attribute
        (Name) @name
        (AttValue) @value))
    (STag (Attribute
        (Name) @name
        (AttValue) @value))
]) @element
    (#eq? @name "id")
    (#eq? @value "\"{id}\""))
"""
    )
    
    captures = query.captures(node)
    if "element" not in captures or len(captures["element"]) == 0:
        return None
    return captures["element"][0]

def node_get_query(node: ts.Node, capture_name: str, query: str|ts.Query) -> ts.Node | None:
    query = query if isinstance(query, ts.Query) else XML_LANGUAGE.query(query)
    
    captures = query.captures(node)
    if capture_name not in captures or len(captures[capture_name]) == 0:
        return None
    return captures[capture_name][0]

def element_range_with_whitespace(element: ts.Node) -> tuple[int, int]:
        if element.prev_sibling is not None and element.prev_sibling.type == "CharData":
            return (element.prev_sibling.start_byte, element.end_byte)
        else:
            return element.byte_range

# Get the char data before the given element, or "" if there is none. This value
# can be used as a separator between new text fragments, which results in them 
# getting the same indentation as the original element.
def element_get_prefix_in_src(element: ts.Node, src: bytes) -> str:
    match element.prev_sibling:
        case None:
            return ""
        case sibling:
            if sibling.type != "CharData":
                return ""
            return node_get_content_in_src(sibling, src)

# Update palette elements in the given SVG file to match palette, return bool
# indicating if the file content ended up being changed.
def update_palette_in_file(svg_file: Path, palette: Palette) -> bool:
    with open(svg_file, "rb") as file:
        src = file.read()
    hash_before = hashlib.sha256(src)
    editor = SourceEditor(src)
    
    tree = XML_PARSER.parse(src)
        
    defs_element = node_get_child_by_id(tree.root_node, "palette-colors")
    if defs_element == None:
        panic(f"SVG '{str(svg_file)}' did not contain an element with id 'palette-colors'.")
        
    elements_to_remove = tuple(filter(None, map(lambda name: node_get_child_by_id(defs_element, name), palette.keys())))
    for element in elements_to_remove:
        editor.delete(element_range_with_whitespace(element))
    
    first_indentation_element = node_get_query(tree.root_node, "x", """
        (document root: (element [
            (content . (CharData) . (element) @x)
            (content . (element) @x)
        ]))
    """)
    if first_indentation_element is None:
        panic(f"No first_indentation_element in file '{str(svg_file)}' (I'm pretty sure this is impossible...)")
    indentation = element_get_prefix_in_src(first_indentation_element, src).removeprefix("\n")
    def_prefix = element_get_prefix_in_src(elements_to_remove[0], src)
    new_line = "\n" if def_prefix.startswith("\n") else ""
    def_prefix = def_prefix.removeprefix("\n")
    
    new_defs_content = io.StringIO()
    for def_element in build_palette_def(palette):
        new_defs_content.write(new_line)
        new_defs_content.write(def_prefix)
        tree_filtered_indent(def_element, space=indentation, level=0)
        content = svg.tree_to_str(def_element)\
            .replace(" />", "/>") # Ensure that the output is consistent with BoxySVG formatting.

        new_defs_content.write(content.replace("\n", "\n" + def_prefix))
    
    defs_start_tag = defs_element.child(0)
    if defs_start_tag == None or defs_start_tag.type != "STag":
        panic(f"Defs element in SVG '{str(svg_file)}' is self-closing, it must have a start and end tag.")
    
    editor.insert(defs_start_tag.end_byte, new_defs_content.getvalue().encode())

    with open(svg_file, "wb+") as file:
        editor.write(file)
        file.seek(0)
        hash_after = hashlib.file_digest(file, "sha256")
    
    return hash_before.digest() != hash_after.digest()
        

def main() -> None:
    parser = argparse.ArgumentParser(description="Update all of the palette colors in the given existing icon SVGs to match those of the given theme.")
    
    parser.add_argument(
        "files",
        metavar="ICON_FILES",
        default=["*"],
        nargs="*",
        help=(
            "The icon names whose SVG files' palletes will be updated. The "
            "names should not include the brackets and '.svg', and must match "
            "one of the icons under under 'assets/icons'. The names may be "
            "glob patterns, and will in that case be evaluated on the set of "
            "names, without said brackets and extensions. If not given "
            "defaults to all icons."
        ),
    )
    parser.add_argument(
        "--theme",
        metavar="THEME",
        type=Path,
        default=project.path_to_absolute("assets/themes/standard.json"),
        help="Path to a JSON file describing the colors to insert into the given SVGs.)",
    )

    args = parser.parse_args()
    
    file_patterns: list[str] = args.files
    theme = Theme.load_file(args.theme)
    
    all_names = [
        cast(str, match.group(1)) # For some fucking reason the return value of Match.group is set to str | Any, instead of the correct str | None.
        for path in os.listdir(project.path_to_absolute("assets/icons"))
        if (match := re.match(r"\[(.*)\]\.svg", Path(path).name)) != None
    ]
    
    files = tuple(map(
        lambda name: f"assets/icons/[{name}].svg",
        more_itertools.unique_everseen(itertools.chain.from_iterable(map(
            lambda name_pattern: fnmatch.filter(all_names, name_pattern),
            file_patterns
        )))
    ))
    
    changed_files = [] 
    for file in files:
        if update_palette_in_file(project.path_to_absolute(file), theme.colors):
            changed_files.append(file)
    
    print("Updated the pallettes in:")
    for file in changed_files:
        print(f"  {str(file)}")
    if len(changed_files) == 0:
        print(f"  No files needed updating.")

def run() -> None:
    try:
        main()
    except BrokenPipeError:
        exit(0)

if __name__ == "__main__":
    run()
