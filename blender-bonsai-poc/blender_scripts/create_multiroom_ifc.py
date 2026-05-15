"""Multi-room, multi-storey IFC scene for the Blender+Bonsai PoC.

Layout (all dimensions in metres, Y-up convention matches sample scene):

  Ground floor (elevation 0.0):
    ┌──────────┬──────────┐
    │  Salon   │  Mutfak  │
    │  5×4     │  5×4     │
    │          │          │
    └──────────┴──────────┘
       10 × 4 footprint

  First floor (elevation 3.0):
    ┌──────────┬──────────┐
    │ Yatak O. │ Çalışma  │
    │  5×4     │  5×4     │
    │          │          │
    └──────────┴──────────┘

Shared/partition walls between rooms.  Each room has at least one window
and one door.  Storey slabs separate the floors.
"""

import argparse
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit
import ifcopenshell.util.representation
import numpy as np

# ---------------------------------------------------------------------------
# Re-use helpers from the single-room script
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Create a multi-room/multi-storey IFC.")
    parser.add_argument("--output", required=True, help="Output .ifc path")
    parser.add_argument("--with-geometry", action="store_true", help="Author body representations.")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(argv)


def add_pset(model, product, name, properties):
    pset = ifcopenshell.api.pset.add_pset(model, product=product, name=name)
    ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=properties)
    return pset


def create_element(model, ifc_class, name, predefined_type, category, dimensions, location, material, notes, room=None):
    element = ifcopenshell.api.root.create_entity(
        model, ifc_class=ifc_class, predefined_type=predefined_type, name=name,
    )
    element.Description = notes
    props = {
        "CevizCategory": category,
        "ReadOnlyPoC": True,
        "MaterialHint": material,
        "LengthM": float(dimensions[0]),
        "WidthM": float(dimensions[1]),
        "HeightM": float(dimensions[2]),
        "LocationX": float(location[0]),
        "LocationY": float(location[1]),
        "LocationZ": float(location[2]),
    }
    if room:
        props["Room"] = room
    add_pset(model, element, "Pset_CevizPoC", props)
    return element


# ---------------------------------------------------------------------------
# Geometry helpers (copied from create_minimal_ifc for self-containment)
# ---------------------------------------------------------------------------

def placement_matrix(origin, rotation_deg=0.0):
    angle = np.deg2rad(rotation_deg)
    cos_a, sin_a = float(np.cos(angle)), float(np.sin(angle))
    m = np.eye(4)
    m[0][0], m[0][1] = cos_a, -sin_a
    m[1][0], m[1][1] = sin_a, cos_a
    m[0][3], m[1][3], m[2][3] = float(origin[0]), float(origin[1]), float(origin[2])
    return m


def rectangle_profile(model, x_dim, y_dim):
    return model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(x_dim), YDim=float(y_dim))


def apply_geometry(model, contexts, element, category, dimensions, location):
    length, width, height = [float(v) for v in dimensions]
    x, y, z = [float(v) for v in location]

    if category == "slab":
        half_x, half_y = length / 2.0, width / 2.0
        polyline = [(0.0, 0.0), (length, 0.0), (length, width), (0.0, width), (0.0, 0.0)]
        rep = ifcopenshell.api.geometry.add_slab_representation(model, context=contexts["body"], depth=height, polyline=polyline)
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=rep)
        ifcopenshell.api.geometry.edit_object_placement(model, product=element, matrix=placement_matrix((x - half_x, y - half_y, z - height / 2.0)))
        return "body-swept-solid"

    if category == "wall":
        if length >= width:
            axis_length, thickness = length, width
            if y >= 0:
                start = (x - length / 2.0, y, z - height / 2.0)
                rot = 0.0
            else:
                start = (x + length / 2.0, y, z - height / 2.0)
                rot = 180.0
        else:
            axis_length, thickness = width, length
            if x <= 0:
                start = (x, y - width / 2.0, z - height / 2.0)
                rot = 90.0
            else:
                start = (x, y + width / 2.0, z - height / 2.0)
                rot = -90.0
        axis_rep = ifcopenshell.api.geometry.add_axis_representation(model, context=contexts["axis"], axis=((0.0, 0.0), (axis_length, 0.0)))
        body_rep = ifcopenshell.api.geometry.add_wall_representation(model, context=contexts["body"], length=axis_length, height=height, thickness=thickness, offset=-(thickness / 2.0))
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=axis_rep)
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=body_rep)
        ifcopenshell.api.geometry.edit_object_placement(model, product=element, matrix=placement_matrix(start, rotation_deg=rot))
        return "axis+body-swept-solid"

    if category in {"door", "window", "furniture", "opening"}:
        profile = rectangle_profile(model, length, width)
        rep = ifcopenshell.api.geometry.add_profile_representation(model, context=contexts["body"], profile=profile, depth=height)
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=rep)
        ifcopenshell.api.geometry.edit_object_placement(model, product=element, matrix=placement_matrix((x, y, z - height / 2.0)))
        return "body-profile-extrusion"

    return "unsupported"


def wall_placement_metadata(wall_dims, wall_world_center):
    length, width, height = [float(v) for v in wall_dims]
    x, y, z = [float(v) for v in wall_world_center]
    if length >= width:
        thickness = width
        if y >= 0:
            start, rot = (x - length / 2.0, y, z - height / 2.0), 0.0
        else:
            start, rot = (x + length / 2.0, y, z - height / 2.0), 180.0
    else:
        thickness = length
        if x <= 0:
            start, rot = (x, y - width / 2.0, z - height / 2.0), 90.0
        else:
            start, rot = (x, y + width / 2.0, z - height / 2.0), -90.0
    return {"start": start, "rotation_deg": rot, "thickness": float(thickness), "height": float(height)}


def world_to_wall_local(world_point, wall_origin, rotation_deg):
    angle = -np.deg2rad(rotation_deg)
    cos_a, sin_a = float(np.cos(angle)), float(np.sin(angle))
    dx = float(world_point[0] - wall_origin[0])
    dy = float(world_point[1] - wall_origin[1])
    dz = float(world_point[2] - wall_origin[2])
    return (cos_a * dx - sin_a * dy, sin_a * dx + cos_a * dy, dz)


def make_wall_local_void_solid(model, length, depth, height, local_center):
    profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA", XDim=float(length), YDim=float(depth))
    location = model.create_entity("IfcCartesianPoint", Coordinates=(float(local_center[0]), float(local_center[1]), float(local_center[2] - height / 2.0)))
    z_dir = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    x_dir = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    placement = model.create_entity("IfcAxis2Placement3D", Location=location, Axis=z_dir, RefDirection=x_dir)
    return model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile, Position=placement, ExtrudedDirection=z_dir, Depth=float(height))


def cut_wall_bodies_with_openings(model, opening_records, spec_by_name, element_by_name):
    by_host = {}
    for rec in opening_records:
        by_host.setdefault(rec["host"], []).append(rec)
    cut_summary = {}
    for host_name, records in by_host.items():
        wall_spec = spec_by_name[host_name]
        meta = wall_placement_metadata(wall_spec["dimensions"], wall_spec["location"])
        wall_element = element_by_name[host_name]
        body_rep = ifcopenshell.util.representation.get_representation(wall_element, "Model", "Body", "MODEL_VIEW")
        if body_rep is None or not (body_rep.Items or []):
            continue
        wall_solid = body_rep.Items[0]
        depth_buffer = max(meta["thickness"] * 1.5, meta["thickness"] + 0.04)
        void_solids = []
        for rec in records:
            local_center = world_to_wall_local(rec["location"], meta["start"], meta["rotation_deg"])
            void_solids.append(make_wall_local_void_solid(model, float(rec["dimensions"][0]), float(depth_buffer), float(rec["dimensions"][2]), local_center))
        ifcopenshell.api.geometry.add_boolean(model, first_item=wall_solid, second_items=void_solids, operator="DIFFERENCE")
        body_rep.RepresentationType = "Clipping"
        cut_summary[host_name] = {"openingCount": len(void_solids), "wallLocalDepthBufferM": float(depth_buffer), "thicknessM": meta["thickness"]}
    return cut_summary


def ensure_geometry(model, project, elements, opening_records, spec_by_name, element_by_name):
    model_3d = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model_3d)
    plan_ctx = ifcopenshell.api.context.add_context(model, context_type="Plan")
    axis = ifcopenshell.api.context.add_context(model, context_type="Plan", context_identifier="Axis", target_view="GRAPH_VIEW", parent=plan_ctx)
    ctxs = {"body": body, "axis": axis}
    statuses = {}
    for element, cat, dims, loc in elements:
        statuses[element.GlobalId] = apply_geometry(model, ctxs, element, cat, dims, loc)
    cut_summary = cut_wall_bodies_with_openings(model, opening_records, spec_by_name, element_by_name)
    add_pset(model, project, "Pset_CevizPoC_Geometry", {
        "RepresentationContexts": "Model/Body + Plan/Axis",
        "GeometryStatus": "multi-room swept/profile body representations with boolean opening cuts" if cut_summary else "multi-room swept/profile body representations",
        "ReadOnlyPoC": True,
    })
    return statuses, cut_summary


# ---------------------------------------------------------------------------
# Scene definition
# ---------------------------------------------------------------------------

WALL_H = 2.9
WALL_T = 0.12
SLAB_T = 0.20

# Building footprint: 10.12 × 4.12 (outer wall centre-to-centre 10 × 4)
# Partition wall at x=0 splits into two ~5m rooms per storey.

def storey_elements(elevation, storey_label, room_left, room_right):
    """Return (element_specs, hosting_specs) for one storey."""
    z_mid = elevation + WALL_H / 2.0  # wall centre-z
    specs = []
    hosting = []

    # Slab
    specs.append({
        "ifc_class": "IfcSlab", "name": f"{storey_label}_slab", "predefined_type": "FLOOR",
        "category": "slab", "dimensions": (10.0, 4.0, SLAB_T),
        "location": (0, 0, elevation - SLAB_T / 2.0),
        "material": "warm_concrete", "notes": f"{storey_label} floor slab.",
        "room": None,
    })

    # Perimeter walls
    for wall_name, dims, loc, room in [
        (f"{storey_label}_north_wall",  (10.0, WALL_T, WALL_H), (0, 2.0, z_mid),  None),
        (f"{storey_label}_south_wall",  (10.0, WALL_T, WALL_H), (0, -2.0, z_mid), None),
        (f"{storey_label}_west_wall",   (WALL_T, 4.0, WALL_H),  (-5.0, 0, z_mid), room_left),
        (f"{storey_label}_east_wall",   (WALL_T, 4.0, WALL_H),  (5.0, 0, z_mid),  room_right),
    ]:
        specs.append({
            "ifc_class": "IfcWall", "name": wall_name, "predefined_type": "SOLIDWALL",
            "category": "wall", "dimensions": dims, "location": loc,
            "material": "warm_concrete", "notes": f"Perimeter wall for {storey_label}.",
            "room": room,
        })

    # Partition wall (shared between rooms)
    specs.append({
        "ifc_class": "IfcWall", "name": f"{storey_label}_partition",
        "predefined_type": "PARTITIONING", "category": "wall",
        "dimensions": (WALL_T, 4.0, WALL_H), "location": (0, 0, z_mid),
        "material": "warm_concrete",
        "notes": f"Interior partition between {room_left} and {room_right}.",
        "room": None,
    })

    # Left room: window on north, door on south
    specs.append({
        "ifc_class": "IfcWindow", "name": f"{storey_label}_win_left",
        "predefined_type": "WINDOW", "category": "window",
        "dimensions": (1.6, 0.04, 1.0), "location": (-2.5, 2.07, elevation + 1.65),
        "material": "soft_glass", "notes": f"Window in {room_left}.",
        "room": room_left,
    })
    hosting.append((f"{storey_label}_win_left", f"{storey_label}_north_wall"))

    specs.append({
        "ifc_class": "IfcDoor", "name": f"{storey_label}_door_left",
        "predefined_type": "DOOR", "category": "door",
        "dimensions": (0.9, 0.06, 2.1), "location": (-2.5, -2.07, elevation + 1.05),
        "material": "light_wood", "notes": f"Door in {room_left}.",
        "room": room_left,
    })
    hosting.append((f"{storey_label}_door_left", f"{storey_label}_south_wall"))

    # Right room: window on north, door on partition
    specs.append({
        "ifc_class": "IfcWindow", "name": f"{storey_label}_win_right",
        "predefined_type": "WINDOW", "category": "window",
        "dimensions": (1.6, 0.04, 1.0), "location": (2.5, 2.07, elevation + 1.65),
        "material": "soft_glass", "notes": f"Window in {room_right}.",
        "room": room_right,
    })
    hosting.append((f"{storey_label}_win_right", f"{storey_label}_north_wall"))

    specs.append({
        "ifc_class": "IfcDoor", "name": f"{storey_label}_door_right",
        "predefined_type": "DOOR", "category": "door",
        "dimensions": (0.9, 0.06, 2.1), "location": (0.07, -0.5, elevation + 1.05),
        "material": "light_wood", "notes": f"Door between {room_left} and {room_right} on partition wall.",
        "room": room_right,
    })
    hosting.append((f"{storey_label}_door_right", f"{storey_label}_partition"))

    # Furniture
    specs.append({
        "ifc_class": "IfcFurniture", "name": f"{storey_label}_furniture_left",
        "predefined_type": "TABLE", "category": "furniture",
        "dimensions": (1.4, 0.8, 0.75), "location": (-3.0, 0, elevation + 0.375),
        "material": "light_wood", "notes": f"Table in {room_left}.",
        "room": room_left,
    })
    specs.append({
        "ifc_class": "IfcFurniture", "name": f"{storey_label}_furniture_right",
        "predefined_type": "TABLE", "category": "furniture",
        "dimensions": (1.2, 0.6, 0.75), "location": (3.0, 0, elevation + 0.375),
        "material": "light_wood", "notes": f"Desk in {room_right}.",
        "room": room_right,
    })

    return specs, hosting


def main():
    args = parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    model = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Ceviz Multi-Room PoC")
    ifcopenshell.api.unit.assign_unit(model)

    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="PoC Site")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="PoC Building")
    ifcopenshell.api.aggregate.assign_object(model, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(model, products=[building], relating_object=site)

    # --- storeys ---
    ground = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Ground Floor")
    ground.Elevation = 0.0
    first = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="First Floor")
    first.Elevation = 3.0
    ifcopenshell.api.aggregate.assign_object(model, products=[ground, first], relating_object=building)

    # Roof slab (top cap)
    roof_slab_spec = {
        "ifc_class": "IfcSlab", "name": "roof_slab", "predefined_type": "ROOF",
        "category": "slab", "dimensions": (10.0, 4.0, SLAB_T),
        "location": (0, 0, 6.0 - SLAB_T / 2.0),
        "material": "warm_concrete", "notes": "Roof slab.",
        "room": None,
    }

    ground_specs, ground_hosting = storey_elements(0.0, "gf", "Salon", "Mutfak")
    first_specs, first_hosting = storey_elements(3.0, "ff", "Yatak Odası", "Çalışma Odası")

    all_element_data = []   # (element, spec_dict) pairs
    spec_by_name = {}
    element_by_name = {}

    def build_storey(storey_obj, specs, hosting_list):
        elements_for_storey = []
        for s in specs:
            el = create_element(
                model, s["ifc_class"], s["name"], s["predefined_type"],
                s["category"], s["dimensions"], s["location"],
                s["material"], s["notes"], room=s.get("room"),
            )
            elements_for_storey.append(el)
            spec_by_name[s["name"]] = s
            element_by_name[s["name"]] = el
            all_element_data.append((el, s))
        ifcopenshell.api.spatial.assign_container(model, products=elements_for_storey, relating_structure=storey_obj)

        # Openings and hosting
        opening_records = []
        for filling_name, host_name in hosting_list:
            host_s = spec_by_name[host_name]
            filling_s = spec_by_name[filling_name]
            wall_thickness = min(host_s["dimensions"][0], host_s["dimensions"][1])
            f_dims = filling_s["dimensions"]
            f_loc = filling_s["location"]
            o_length = float(f_dims[0])
            o_width = float(wall_thickness)
            o_height = float(f_dims[2])
            o_loc = (float(f_loc[0]), float(host_s["location"][1]), float(f_loc[2]))
            opening = create_element(
                model, "IfcOpeningElement", f"{filling_name}_opening", "OPENING",
                "opening", (o_length, o_width, o_height), o_loc, "void",
                f"Opening hosted by {host_name} for {filling_name}.",
            )
            ifcopenshell.api.feature.add_feature(model, feature=opening, element=element_by_name[host_name])
            ifcopenshell.api.feature.add_filling(model, opening=opening, element=element_by_name[filling_name])
            add_pset(model, opening, "Pset_CevizPoC_Hosting", {
                "HostWallName": host_name, "FillingElementName": filling_name,
                "OpeningLengthM": o_length, "OpeningWidthM": o_width, "OpeningHeightM": o_height,
                "ReadOnlyPoC": True,
            })
            add_pset(model, element_by_name[host_name], f"Pset_CevizPoC_Hosting_{filling_name}", {
                "HostsOpeningName": opening.Name, "HostsFillingName": filling_name,
                "OpeningGlobalId": opening.GlobalId, "FillingGlobalId": element_by_name[filling_name].GlobalId,
                "OpeningAreaM2": round(o_length * o_height, 6),
            })
            add_pset(model, element_by_name[filling_name], "Pset_CevizPoC_Hosted", {
                "HostWallName": host_name, "OpeningName": opening.Name,
                "OpeningGlobalId": opening.GlobalId, "HostWallGlobalId": element_by_name[host_name].GlobalId,
            })
            opening_records.append({
                "name": opening.Name, "filling": filling_name, "host": host_name,
                "dimensions": (o_length, o_width, o_height), "location": o_loc, "element": opening,
            })
            spec_by_name[opening.Name] = {
                "ifc_class": "IfcOpeningElement",
                "name": opening.Name,
                "predefined_type": "OPENING",
                "category": "opening",
                "dimensions": (o_length, o_width, o_height),
                "location": o_loc,
                "material": "void",
                "notes": f"Opening hosted by {host_name} for {filling_name}.",
                "room": None,
            }
            element_by_name[opening.Name] = opening
            all_element_data.append((opening, spec_by_name[opening.Name]))

        return opening_records

    ground_openings = build_storey(ground, ground_specs, ground_hosting)
    first_openings = build_storey(first, first_specs, first_hosting)

    # Roof slab on first floor
    roof_el = create_element(
        model, roof_slab_spec["ifc_class"], roof_slab_spec["name"],
        roof_slab_spec["predefined_type"], roof_slab_spec["category"],
        roof_slab_spec["dimensions"], roof_slab_spec["location"],
        roof_slab_spec["material"], roof_slab_spec["notes"],
    )
    ifcopenshell.api.spatial.assign_container(model, products=[roof_el], relating_structure=first)
    spec_by_name[roof_slab_spec["name"]] = roof_slab_spec
    element_by_name[roof_slab_spec["name"]] = roof_el
    all_element_data.append((roof_el, roof_slab_spec))

    # --- Geometry (opt-in) ---
    geometry_status = "semantic IFC with multi-room layout; no shape representations yet"
    if args.with_geometry:
        geo_inputs = [(el, s["category"], s["dimensions"], s["location"]) for el, s in all_element_data]
        all_openings = ground_openings + first_openings
        statuses, cut_summary = ensure_geometry(model, project, geo_inputs, all_openings, spec_by_name, element_by_name)
        geometry_status = (
            "multi-room swept/profile body representations with boolean opening cuts"
            if cut_summary else
            "multi-room swept/profile body representations"
        )
        for el, s in all_element_data:
            add_pset(model, el, "Pset_CevizPoC_Geometry", {
                "RepresentationStatus": statuses.get(el.GlobalId, "missing"),
                "HasBodyRepresentation": statuses.get(el.GlobalId) not in {None, "unsupported"},
            })
        for host_name, info in cut_summary.items():
            add_pset(model, element_by_name[host_name], "Pset_CevizPoC_BodyBoolean", {
                "BooleanOperator": "DIFFERENCE",
                "RepresentationType": "Clipping",
                "OpeningCount": int(info["openingCount"]),
                "WallThicknessM": float(info["thicknessM"]),
                "VoidDepthBufferM": float(info["wallLocalDepthBufferM"]),
                "ReadOnlyPoC": True,
            })

    add_pset(model, project, "Pset_CevizPoC_Project", {
        "Source": "blender_scripts/create_multiroom_ifc.py",
        "AuthoringRoute": "IfcOpenShell pure Python API under Blender headless",
        "GeometryStatus": geometry_status,
        "SceneType": "multi-room-multi-storey",
        "StoreyCount": 2,
        "RoomsPerStorey": 2,
        "ReadOnlyPoC": True,
    })

    model.write(str(out))
    elem_count = len(list(model))
    print(f"Wrote IFC: {out}")
    print(f"Entities: {elem_count}")
    print(f"Storeys: 2 (Ground Floor + First Floor)")
    print(f"Rooms: 4 (Salon, Mutfak, Yatak Odası, Çalışma Odası)")
    print(f"Geometry: {'enabled' if args.with_geometry else 'disabled'}")


if __name__ == "__main__":
    main()
