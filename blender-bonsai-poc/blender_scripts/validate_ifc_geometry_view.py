"""Render an IFC through IfcOpenShell geometry as a headless viewer check.

This is intentionally separate from the authoring path.  It opens the emitted
IFC, asks IfcOpenShell's geometry engine to tessellate the products, builds a
Blender scene from those meshes, and writes both a PNG render and a compact JSON
validation report.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
from mathutils import Vector


PRODUCT_CLASSES = (
    "IfcSlab",
    "IfcWall",
    "IfcWindow",
    "IfcDoor",
    "IfcFurniture",
)


def parse_args():
    parser = argparse.ArgumentParser(description="Render IFC geometry for visual validation.")
    parser.add_argument("--input", required=True, help="Input IFC path")
    parser.add_argument("--render-output", required=True, help="Output PNG path")
    parser.add_argument("--report-output", required=True, help="Output JSON report path")
    parser.add_argument("--hide-fillings", action="store_true", help="Hide doors/windows to inspect wall openings.")
    parser.add_argument("--only-categories", help="Comma-separated category filter, e.g. wall,slab")
    parser.add_argument("--view", choices=["axon", "north", "south"], default="axon", help="Camera view for the render.")
    parser.add_argument("--focus-host-walls", action="store_true", help="Render only walls with hosted openings.")
    parser.add_argument("--explode", action="store_true", help="Offset created objects so overlapping elements are easier to inspect.")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(argv)


def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def material(name, color):
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Alpha"].default_value = color[3]
    mat.blend_method = "BLEND" if color[3] < 1 else "OPAQUE"
    return mat


def category_of(entity):
    psets = ifcopenshell.util.element.get_psets(entity, psets_only=True)
    return (psets.get("Pset_CevizPoC") or {}).get("CevizCategory") or entity.is_a()


def make_mesh_object(entity, shape, mat):
    geom = shape.geometry
    verts = [(geom.verts[i], geom.verts[i + 1], geom.verts[i + 2]) for i in range(0, len(geom.verts), 3)]
    faces = [(geom.faces[i], geom.faces[i + 1], geom.faces[i + 2]) for i in range(0, len(geom.faces), 3)]
    mesh = bpy.data.meshes.new(f"{entity.Name or entity.GlobalId}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(entity.Name or entity.GlobalId, mesh)
    obj.data.materials.append(mat)
    obj["ifc_class"] = entity.is_a()
    obj["ifc_global_id"] = entity.GlobalId
    obj["ceviz_category"] = category_of(entity)
    bpy.context.collection.objects.link(obj)
    return obj, len(verts), len(faces)


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_camera_and_light(view):
    bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
    sun = bpy.context.object
    sun.name = "validation_sun"
    sun.data.energy = 2.0
    sun.rotation_euler = (math.radians(45), 0, math.radians(35))

    bpy.ops.object.light_add(type="AREA", location=(0, -4, 8))
    area = bpy.context.object
    area.name = "validation_area"
    area.data.energy = 450
    area.data.size = 6

    if view == "north":
        camera_location = (0, 12.5, 3.0)
        target = (0, 0, 3.0)
        ortho_scale = 7.4
    elif view == "south":
        camera_location = (0, -12.5, 3.0)
        target = (0, 0, 3.0)
        ortho_scale = 7.4
    else:
        camera_location = (10.5, -8.5, 6.5)
        target = (0, 0, 2.8)
        ortho_scale = 11.5

    bpy.ops.object.camera_add(location=camera_location)
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = ortho_scale
    look_at(camera, target)
    bpy.context.scene.camera = camera


def render(path):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = 64
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "Medium High Contrast"
    scene.render.filepath = str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)


def has_hosted_openings(entity):
    return bool(getattr(entity, "HasOpenings", None) or [])


def hosted_opening_count(entity):
    return len(getattr(entity, "HasOpenings", None) or [])


def main():
    args = parse_args()
    ifc_path = Path(args.input)
    render_output = Path(args.render_output)
    report_output = Path(args.report_output)

    clean_scene()
    model = ifcopenshell.open(str(ifc_path))
    only_categories = None
    if args.only_categories:
        only_categories = {item.strip() for item in args.only_categories.split(",") if item.strip()}
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.DISABLE_OPENING_SUBTRACTIONS, False)

    mats = {
        "slab": material("slab_warm_concrete", (0.72, 0.68, 0.60, 1.0)),
        "wall": material("wall_warm_concrete", (0.78, 0.74, 0.66, 0.88)),
        "window": material("window_soft_glass", (0.35, 0.70, 1.00, 0.45)),
        "door": material("door_light_wood", (0.74, 0.48, 0.25, 1.0)),
        "furniture": material("furniture_light_wood", (0.55, 0.34, 0.18, 1.0)),
    }

    created = []
    failures = []
    totals = {"vertices": 0, "triangles": 0}
    by_category = {}
    created_index = 0
    for ifc_class in PRODUCT_CLASSES:
        for entity in model.by_type(ifc_class):
            category = category_of(entity)
            if args.focus_host_walls and not (entity.is_a() == "IfcWall" and has_hosted_openings(entity)):
                continue
            if args.hide_fillings and category in {"door", "window"}:
                continue
            if only_categories is not None and category not in only_categories:
                continue
            try:
                shape = ifcopenshell.geom.create_shape(settings, entity)
                obj, vertex_count, triangle_count = make_mesh_object(entity, shape, mats.get(category, mats["wall"]))
                if args.explode:
                    obj.location.x += (created_index % 3) * 4.2
                    obj.location.y += (created_index // 3) * 3.2
                    created_index += 1
                created.append(
                    {
                        "name": obj.name,
                        "globalId": entity.GlobalId,
                        "class": entity.is_a(),
                        "category": category,
                        "hostedOpeningCount": hosted_opening_count(entity),
                        "vertices": vertex_count,
                        "triangles": triangle_count,
                    }
                )
                totals["vertices"] += vertex_count
                totals["triangles"] += triangle_count
                by_category[category] = by_category.get(category, 0) + 1
            except Exception as exc:
                failures.append(
                    {
                        "name": getattr(entity, "Name", None),
                        "globalId": getattr(entity, "GlobalId", None),
                        "class": entity.is_a(),
                        "category": category,
                        "error": f"{exc.__class__.__name__}: {exc}",
                    }
                )

    add_camera_and_light(args.view)
    render(render_output)

    report = {
        "kind": "ifc-geometry-view-validation",
        "sourceIfc": str(ifc_path),
        "renderOutput": str(render_output),
        "hideFillings": bool(args.hide_fillings),
        "onlyCategories": sorted(only_categories) if only_categories else None,
        "view": args.view,
        "ok": not failures and bool(created),
        "shapeCreatedCount": len(created),
        "shapeFailureCount": len(failures),
        "byCategory": dict(sorted(by_category.items())),
        "totals": totals,
        "failures": failures,
        "created": sorted(created, key=lambda item: (item["category"], item["name"])),
    }
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "shapeCreatedCount", "shapeFailureCount", "byCategory", "totals")}, indent=2))


if __name__ == "__main__":
    main()
