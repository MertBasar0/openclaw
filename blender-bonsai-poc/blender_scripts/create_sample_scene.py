import argparse
import sys
from pathlib import Path
import bpy
from mathutils import Vector


def mat(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    return m


def cube_obj(name, loc, scale, material, category):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(material)
    obj["ceviz_category"] = category
    obj["read_only_poc"] = True
    return obj


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    concrete = mat("warm_concrete", (0.72, 0.68, 0.62, 1.0))
    glass = mat("soft_glass", (0.45, 0.75, 1.0, 0.45))
    wood = mat("light_wood", (0.78, 0.55, 0.34, 1.0))

    arch = bpy.data.collections.new("Architecture")
    bpy.context.scene.collection.children.link(arch)

    objs = [
        cube_obj("floor_slab", (0, 0, -0.05), (6.0, 4.0, 0.10), concrete, "slab"),
        cube_obj("north_wall", (0, 2.0, 1.45), (6.0, 0.12, 2.9), concrete, "wall"),
        cube_obj("south_wall", (0, -2.0, 1.45), (6.0, 0.12, 2.9), concrete, "wall"),
        cube_obj("west_wall", (-3.0, 0, 1.45), (0.12, 4.0, 2.9), concrete, "wall"),
        cube_obj("east_wall", (3.0, 0, 1.45), (0.12, 4.0, 2.9), concrete, "wall"),
        cube_obj("window_north", (0, 2.07, 1.65), (1.8, 0.04, 1.0), glass, "window"),
        cube_obj("door_south", (-1.9, -2.07, 1.0), (0.9, 0.06, 2.0), wood, "door"),
        cube_obj("table_placeholder", (0.8, -0.4, 0.45), (1.4, 0.8, 0.9), wood, "furniture"),
    ]
    for obj in objs:
        # move from root scene collection to Architecture collection
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        arch.objects.link(obj)

    bpy.ops.object.light_add(type="AREA", location=(0, 0, 3.2))
    light = bpy.context.object
    light.name = "ceiling_area_light"
    light.data.energy = 350
    light.data.size = 4

    bpy.ops.object.camera_add(location=(6, -6, 4), rotation=(1.1, 0, 0.75))
    bpy.context.scene.camera = bpy.context.object

    bpy.context.scene["ceviz_poc"] = "blender-bonsai-readonly-v0"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))


if __name__ == "__main__":
    main()
