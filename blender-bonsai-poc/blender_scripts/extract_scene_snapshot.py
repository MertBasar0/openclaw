import argparse, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector


def color_tuple(mat):
    try:
        return [round(float(x), 4) for x in mat.diffuse_color]
    except Exception:
        return None


def obj_bounds(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mins = [min(v[i] for v in corners) for i in range(3)]
    maxs = [max(v[i] for v in corners) for i in range(3)]
    return {"min": [round(x, 4) for x in mins], "max": [round(x, 4) for x in maxs]}


def custom_props(obj):
    out = {}
    for k in obj.keys():
        if k.startswith("_"):
            continue
        v = obj[k]
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v
        else:
            out[k] = str(v)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    args = parser.parse_args(argv)

    bpy.ops.wm.open_mainfile(filepath=args.input)
    mesh_objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    objects = []
    diagnostics = []
    for o in mesh_objects:
        mats = [slot.material.name for slot in o.material_slots if slot.material]
        dims = [round(float(x), 4) for x in o.dimensions]
        props = custom_props(o)
        if not mats:
            diagnostics.append({"severity": "warn", "object": o.name, "code": "missing-material"})
        if "ceviz_category" not in props:
            diagnostics.append({"severity": "info", "object": o.name, "code": "missing-semantic-category"})
        objects.append({
            "name": o.name,
            "type": o.type,
            "collections": [c.name for c in o.users_collection],
            "location": [round(float(x), 4) for x in o.location],
            "dimensions": dims,
            "bounds": obj_bounds(o),
            "materials": mats,
            "customProperties": props,
        })

    all_bounds = None
    if mesh_objects:
        mins = [math.inf, math.inf, math.inf]
        maxs = [-math.inf, -math.inf, -math.inf]
        for o in mesh_objects:
            b = obj_bounds(o)
            for i in range(3):
                mins[i] = min(mins[i], b["min"][i])
                maxs[i] = max(maxs[i], b["max"][i])
        all_bounds = {"min": mins, "max": maxs, "size": [round(maxs[i]-mins[i], 4) for i in range(3)]}

    data = {
        "kind": "blender-scene-snapshot",
        "contractVersion": "0.1.0",
        "source": {"tool": "Blender", "version": bpy.app.version_string, "file": args.input},
        "scene": {
            "name": bpy.context.scene.name,
            "objectCount": len(bpy.context.scene.objects),
            "meshObjectCount": len(mesh_objects),
            "materialCount": len(bpy.data.materials),
            "collectionCount": len(bpy.data.collections),
            "bounds": all_bounds,
        },
        "collections": sorted([c.name for c in bpy.data.collections]),
        "materials": [{"name": m.name, "diffuseColor": color_tuple(m)} for m in bpy.data.materials],
        "objects": objects,
        "diagnostics": diagnostics,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
