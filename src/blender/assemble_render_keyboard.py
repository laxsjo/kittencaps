from typing import *
import PIL.Image
import bpy
from bpy import types as blender_types
import bpy.types
import mathutils
import argparse
from pathlib import Path
import sys
import math
import xml.etree.ElementTree as ET 
import re
import PIL

# Relative imports don't work in blender unfortunately :(
from src.lib import magic
from src.lib.generation_metadata import *
from src.lib.theme import *
from src.lib.keyboard_builder import *
from src.lib.svg_builder import *
from src.lib.utils import *
from src.lib.pos import *
from src.lib.error import *
from src.lib.color import *
from src.lib import kle_ext as kle

def get_modifidier_node_group_safe(name: str) -> bpy.types.NodeTree:
    """
    Access modifier node_group, circumventing the bug of assets not being loaded
    at startup as described in the issue below. It was something with a script
    running with `--background` or after importing a 3D model not loading
    certain assets quick enough... (I don't really understand it)
    
    This code is heavily based on this:
    https://projects.blender.org/blender/blender/issues/117399#issuecomment-1167467
    """
    
    def get_internal_asset_path():
        for path_type in ("LOCAL", "SYSTEM", "USER"):
            path = Path(bpy.utils.resource_path(path_type)) / "datafiles" / "assets"
            if path.exists():
                return path
        assert False
    # TODO: We might not be able to assume that we can easily derive the asset
    # .blend name from the title case human readable name in this way...
    asset_path = str(
        get_internal_asset_path() / "geometry_nodes" / f"{name.lower().replace(" ", "_")}.blend"
    )
    node_group = bpy.data.node_groups.get(name)
    if not node_group or node_group.type != "GEOMETRY":
        print(f"Loading '{name}'...")
        with bpy.data.libraries.load(asset_path) as (data_from, data_to):
            data_to.node_groups = [name]
        node_group = cast(bpy.types.NodeTree, data_to.node_groups[0])
    return node_group

def copy_modifiers(source: bpy.types.Object, destination: bpy.types.Object):
    for source_modifier in source.modifiers:
        destination_modifier = destination.modifiers.get(source_modifier.name, None)
        if not destination_modifier:
            destination_modifier = destination.modifiers.new(source_modifier.name, source_modifier.type)

        # collect names of writable properties
        properties = [p.identifier for p in source_modifier.bl_rna.properties
                        if not p.is_readonly]

        # copy those properties
        for prop in properties:
            setattr(destination_modifier, prop, getattr(source_modifier, prop))
        destination_modifier = destination

def create_keyboard(texture_path: Path, svg_viewbox: ViewBox, keyboard: kle.ExtendedKeyboard, theme: Theme, out_path: Path) -> None:
    with PIL.Image.open(texture_path) as image:
        texture_size = Vec2(*image.size)
    
    unit = magic.keycap_model_unit_size
    
    # Save immediately to new location. This is important to make sure that
    # relative paths resolve correctly. 
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path), check_existing=False)
    
    keyboard_collection = bpy.data.collections["Keyboard"]
    keys_collection = bpy.data.collections["Keys"]
    
    case = keyboard.case
    
    ## Place origin
    # The children's positions will be adjust to be relative to this one.  
    center_position = mathutils.Vector((
        0 if case.mirror_around_x is None else case.mirror_around_x * unit,
        0 if case.mirror_around_y is None else -case.mirror_around_y * unit,
        0
    ))
    origin_object = bpy.data.objects["Keyboard Origin"]
    origin_object.hide_set(True)
    
    ## Place case
    if case.model_path != None:
        type = case.model_path.suffix.lower()
        match type:
            case ".stl":
                result = bpy.ops.wm.stl_import(
                    filepath="assets/cases/moonlander-mk1.stl",
                    up_axis=case.model_up_axis.value,
                    forward_axis=case.model_forward_axis.value,
                    use_scene_unit=False,
                    global_scale=1/case.model_unit_scale,
                )
            case extension:
                panic(f"Unsupported model file extensions: '{extension}'")
        
        context = bpy.context or panic("Oops, no context!")
        case_object = context.object or panic("impossible")
        for collection in case_object.users_collection:
            collection.objects.unlink(case_object)
        keyboard_collection.objects.link(case_object)
        # Doesn't work, due to the bug decsribed in
        # `get_modifidier_node_group_safe`
        # result = bpy.ops.object.shade_auto_smooth()
        smooth_by_angle_modifier = cast(bpy.types.NodesModifier, case_object.modifiers.new("Smooth by Angle", "NODES"))
        smooth_by_angle_modifier.node_group = get_modifidier_node_group_safe("Smooth by Angle")
        smooth_by_angle_modifier["Input_1"] = math.radians(magic.model_minimum_sharp_angle_deg)
        
        weighted_normals_modifier = cast(bpy.types.WeightedNormalModifier, case_object.modifiers.new("WeightedNormal", "WEIGHTED_NORMAL"))
        weighted_normals_modifier.keep_sharp = True
        
        case_object.location = mathutils.Vector((*(case.position * Vec2(1, -1) * unit), 0))
        case_object.location -= center_position
        case_object.parent = origin_object
        
        case_mesh = assert_instance(bpy.types.Mesh, case_object.data)
        case_mesh.materials.append(bpy.data.materials['Case Plastic'])
        color = theme.colors[case.color] if case.color in theme.colors else HideableColor(case.color)
        case_object["color"] = color[0:3]
        
        
        ### Apply mirror
        if case.mirror_around_x is not None or case.mirror_around_y is not None:
            smooth_by_angle_modifier = cast(bpy.types.MirrorModifier, case_object.modifiers.new("Mirror", "MIRROR"))
            smooth_by_angle_modifier.mirror_object = origin_object
            if case.mirror_around_x is not None:
                smooth_by_angle_modifier.use_axis[0] = True
            if case.mirror_around_y is not None:
                smooth_by_angle_modifier.use_axis[1] = True
            
        case_object.select_set(False)
            
            
    
    ## Load and assign texture
    texture = bpy.data.images.load(str(texture_path))
    relative_texture_path = (texture_path.relative_to(out_path.parent))
    texture.filepath = f"//{relative_texture_path}"
    
    if (node_tree := bpy.data.materials['Keycap'].node_tree) == None:
        panic("Material 'Keycap' did not have a node tree.")
    try:
        node = node_tree.nodes["Texture"]
    except KeyError:
        panic("Material 'Keycap' did not have a node named 'Texture'.")
    if not isinstance(node, blender_types.ShaderNodeTexImage):
        panic("'Texture' node of material 'Keycap was not an image texture node.")
    node.image = texture
    
    ## Position keycap mesh origins at their top left corners, to match the SVG.
    for name, mesh in bpy.data.meshes.items():
        match = re.match(r"^DSA_([0-9]+(?:\.[0-9]+)?)u.*$", name)
        if match is None:
            continue
        size = float(match.group(1))
        
        unit = magic.keycap_model_unit_size
        translation = mathutils.Vector((unit / 2 * size, -unit / 2, 0))
        
        mesh.transform(
            mathutils.Matrix.Translation(translation)
        )
    
    ## Place keys
    def place_key(key: KeycapInfo, transform: Transform) -> None:        
        unit = magic.keycap_model_unit_size
        
        mesh_name = f"DSA_{key.major_size:g}u"
        try:
            mesh = bpy.data.meshes[mesh_name]
        except KeyError:
            panic(f"Keycap mesh '{mesh_name}' is not defined") 
        
        object = bpy.data.objects.new(f"Key_{key.icon_id}", mesh)
        
        local_pos = Vec2(0, 0)
        local_rotation_clockwise = Rotation(0)
        match key.orientation:
            case Orientation.HORIZONTAL:
                pass
            case Orientation.VERTICAL:
                local_rotation_clockwise += 90
                local_pos.x += 1
        
        pos = transform.get_translation()
        rotation_clockwise = transform.get_rotation()
        
        matrix = mathutils.Matrix.Identity(4)
        
        ## These are not really the local and global transforms, but I don't care
        # Apply "local" transform
        matrix = mathutils.Matrix.Rotation(
            -local_rotation_clockwise.rad(),
            4,
            (0, 0, 1)
        ) @ matrix
        matrix = mathutils.Matrix.Translation((*(local_pos * unit), 0)) @ matrix
        
        # Apply "global" transform
        matrix = mathutils.Matrix.Rotation(
            -rotation_clockwise.rad(),
            4,
            (0, 0, 1)
        ) @ matrix
        matrix = mathutils.Matrix.Translation((*(pos * unit * Vec2(1, -1)), 0))\
            @ matrix
        matrix = mathutils.Matrix.Translation((
            0,
            0,
            bpy.utils.units.to_value("METRIC", "LENGTH", f"{keyboard.case.vertical_offset_mm} mm"),
        )) @ matrix
        
        object.matrix_world = matrix
        object.location -= center_position
        object.parent = origin_object
        
        
        texture_local_pos = local_pos * theme.unit_size
        texture_pos_pixels = \
            rotate(texture_local_pos, Vec2(0, 0), rotation_clockwise.deg) \
            + transform.get_translation() * theme.unit_size \
            - svg_viewbox.pos
        
        object["texture_position_pixels"] = \
            (*texture_pos_pixels, 0)
        # The negation of the counter-clockwise rotation
        object["texture_rotation"] = -(-rotation_clockwise.rad()) - -local_rotation_clockwise.rad()
        object["texture_dimensions"] = tuple(texture_size)
        object["texture_unit_size"] = theme.unit_size
        object["unit_size"] = magic.keycap_model_unit_size
        object["dimensions"] = (unit * key.major_size, unit)

        reference_object = bpy.data.objects[mesh_name]
        copy_modifiers(reference_object, object)
        
        keys_collection.objects.link(object)
    
    place_keys(keyboard.keys, 1, place_key)
    
    ## Move viewport to camera
    space = bpy.data.screens['Layout'].areas[3].spaces[0]
    if not isinstance(space, blender_types.SpaceView3D):
        panic("Area 3 of workspace 'Layout' isn't a SpaceView3D instance. It likely isn't a 3D Viewport.")
    # Hardcoded position, happens to match the center of all keycap objects of
    # the moonlander-mk1.json
    # TODO: Yes this is ugly, I should probably calculate it as the average of
    # all the keycap positions.
    space.region_3d.view_location = mathutils.Vector((0, 0, 0))
    space.region_3d.view_perspective = "CAMERA"
    
    bpy.ops.wm.save_mainfile(filepath=str(out_path))
    

parser = argparse.ArgumentParser(
    description="",
)
parser.add_argument(
    "--directory",
    metavar="KEYCAP_DIRECTORY",
    type=Path,
    required=True,
    help="Path to a folder which contains the output of a previous invokation of package_keycaps.py."
)

parser.add_argument(
    "--out",
    metavar="DIRECTORY",
    type=Path,
    required=True,
    help="Write the generated .blend file to this directory."
)

try:
    arguments_start_index = sys.argv.index("--") + 1
except ValueError:
    arguments_start_index = 0

args = parser.parse_args(sys.argv[arguments_start_index:])

directory: Path = args.directory
out_path: Path = args.out

metadata = GenerationMetadata.from_file(directory / "metadata.json5")

layout = metadata.load_layout()
theme = metadata.load_theme()

with open(directory / "texture.svg", "r") as file:
    view_box = tree_get_viewbox(ET.parse(file))

create_keyboard(directory / "texture.png", view_box, layout, theme, out_path)
