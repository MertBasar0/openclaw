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


def parse_args():
    parser = argparse.ArgumentParser(description="Create a minimal BIM/IFC slice for the Blender+Bonsai PoC.")
    parser.add_argument("--output", required=True, help="Output .ifc path")
    parser.add_argument("--with-geometry", action="store_true", help="Author simple IFC body representations and placements.")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    return parser.parse_args(argv)


def add_pset(model, product, name, properties):
    pset = ifcopenshell.api.pset.add_pset(model, product=product, name=name)
    ifcopenshell.api.pset.edit_pset(model, pset=pset, properties=properties)
    return pset


def create_element(model, ifc_class, name, predefined_type, category, dimensions, location, material, notes):
    element = ifcopenshell.api.root.create_entity(
        model,
        ifc_class=ifc_class,
        predefined_type=predefined_type,
        name=name,
    )
    # Keep this first BIM slice intentionally metadata-only. It is safer and more
    # deterministic in headless environments than attempting Bonsai UI authoring.
    element.Description = notes
    add_pset(
        model,
        element,
        "Pset_CevizPoC",
        {
            "CevizCategory": category,
            "ReadOnlyPoC": True,
            "MaterialHint": material,
            "LengthM": float(dimensions[0]),
            "WidthM": float(dimensions[1]),
            "HeightM": float(dimensions[2]),
            "LocationX": float(location[0]),
            "LocationY": float(location[1]),
            "LocationZ": float(location[2]),
        },
    )
    return element


def placement_matrix(origin, rotation_deg=0.0):
    angle = np.deg2rad(rotation_deg)
    cos_a = float(np.cos(angle))
    sin_a = float(np.sin(angle))
    matrix = np.eye(4)
    matrix[0][0] = cos_a
    matrix[0][1] = -sin_a
    matrix[1][0] = sin_a
    matrix[1][1] = cos_a
    matrix[0][3] = float(origin[0])
    matrix[1][3] = float(origin[1])
    matrix[2][3] = float(origin[2])
    return matrix


def rectangle_profile(model, x_dim, y_dim):
    return model.create_entity(
        "IfcRectangleProfileDef",
        ProfileType="AREA",
        XDim=float(x_dim),
        YDim=float(y_dim),
    )


def apply_geometry(model, contexts, element, category, dimensions, location):
    length, width, height = [float(value) for value in dimensions]
    x, y, z = [float(value) for value in location]

    if category == "slab":
        half_x = length / 2.0
        half_y = width / 2.0
        polyline = [
            (0.0, 0.0),
            (length, 0.0),
            (length, width),
            (0.0, width),
            (0.0, 0.0),
        ]
        representation = ifcopenshell.api.geometry.add_slab_representation(
            model,
            context=contexts["body"],
            depth=height,
            polyline=polyline,
        )
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=representation)
        ifcopenshell.api.geometry.edit_object_placement(
            model,
            product=element,
            matrix=placement_matrix((x - half_x, y - half_y, z - (height / 2.0))),
        )
        return "body-swept-solid"

    if category == "wall":
        if length >= width:
            axis_length = length
            thickness = width
            if y >= 0:
                start = (x - (length / 2.0), y, z - (height / 2.0))
                rotation_deg = 0.0
            else:
                start = (x + (length / 2.0), y, z - (height / 2.0))
                rotation_deg = 180.0
        else:
            axis_length = width
            thickness = length
            if x <= 0:
                start = (x, y - (width / 2.0), z - (height / 2.0))
                rotation_deg = 90.0
            else:
                start = (x, y + (width / 2.0), z - (height / 2.0))
                rotation_deg = -90.0
        axis = ifcopenshell.api.geometry.add_axis_representation(
            model,
            context=contexts["axis"],
            axis=((0.0, 0.0), (axis_length, 0.0)),
        )
        body = ifcopenshell.api.geometry.add_wall_representation(
            model,
            context=contexts["body"],
            length=axis_length,
            height=height,
            thickness=thickness,
            offset=-(thickness / 2.0),
        )
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=axis)
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=body)
        ifcopenshell.api.geometry.edit_object_placement(
            model,
            product=element,
            matrix=placement_matrix(start, rotation_deg=rotation_deg),
        )
        return "axis+body-swept-solid"

    if category in {"door", "window", "furniture"}:
        profile = rectangle_profile(model, length, width)
        representation = ifcopenshell.api.geometry.add_profile_representation(
            model,
            context=contexts["body"],
            profile=profile,
            depth=height,
        )
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=representation)
        ifcopenshell.api.geometry.edit_object_placement(
            model,
            product=element,
            matrix=placement_matrix((x, y, z - (height / 2.0))),
        )
        return "body-profile-extrusion"

    if category == "opening":
        profile = rectangle_profile(model, length, width)
        representation = ifcopenshell.api.geometry.add_profile_representation(
            model,
            context=contexts["body"],
            profile=profile,
            depth=height,
        )
        ifcopenshell.api.geometry.assign_representation(model, product=element, representation=representation)
        ifcopenshell.api.geometry.edit_object_placement(
            model,
            product=element,
            matrix=placement_matrix((x, y, z - (height / 2.0))),
        )
        return "body-profile-extrusion"

    return "unsupported"


def wall_placement_metadata(wall_dims, wall_world_center):
    length, width, height = [float(value) for value in wall_dims]
    x, y, z = [float(value) for value in wall_world_center]
    if length >= width:
        thickness = width
        if y >= 0:
            start = (x - length / 2.0, y, z - height / 2.0)
            rotation_deg = 0.0
        else:
            start = (x + length / 2.0, y, z - height / 2.0)
            rotation_deg = 180.0
    else:
        thickness = length
        if x <= 0:
            start = (x, y - width / 2.0, z - height / 2.0)
            rotation_deg = 90.0
        else:
            start = (x, y + width / 2.0, z - height / 2.0)
            rotation_deg = -90.0
    return {"start": start, "rotation_deg": rotation_deg, "thickness": float(thickness), "height": float(height)}


def world_to_wall_local(world_point, wall_origin, rotation_deg):
    angle = -np.deg2rad(rotation_deg)
    cos_a = float(np.cos(angle))
    sin_a = float(np.sin(angle))
    dx = float(world_point[0] - wall_origin[0])
    dy = float(world_point[1] - wall_origin[1])
    dz = float(world_point[2] - wall_origin[2])
    return (cos_a * dx - sin_a * dy, sin_a * dx + cos_a * dy, dz)


def make_wall_local_void_solid(model, length, depth, height, local_center):
    profile = model.create_entity(
        "IfcRectangleProfileDef",
        ProfileType="AREA",
        XDim=float(length),
        YDim=float(depth),
    )
    location = model.create_entity(
        "IfcCartesianPoint",
        Coordinates=(
            float(local_center[0]),
            float(local_center[1]),
            float(local_center[2] - height / 2.0),
        ),
    )
    z_dir = model.create_entity("IfcDirection", DirectionRatios=(0.0, 0.0, 1.0))
    x_dir = model.create_entity("IfcDirection", DirectionRatios=(1.0, 0.0, 0.0))
    placement = model.create_entity(
        "IfcAxis2Placement3D",
        Location=location,
        Axis=z_dir,
        RefDirection=x_dir,
    )
    return model.create_entity(
        "IfcExtrudedAreaSolid",
        SweptArea=profile,
        Position=placement,
        ExtrudedDirection=z_dir,
        Depth=float(height),
    )


def cut_wall_bodies_with_openings(model, opening_records, spec_by_name, element_by_name):
    by_host = {}
    for record in opening_records:
        by_host.setdefault(record["host"], []).append(record)
    cut_summary = {}
    for host_name, records in by_host.items():
        wall_spec = spec_by_name[host_name]
        meta = wall_placement_metadata(wall_spec[4], wall_spec[5])
        wall_element = element_by_name[host_name]
        body_rep = ifcopenshell.util.representation.get_representation(
            wall_element, "Model", "Body", "MODEL_VIEW"
        )
        if body_rep is None or not (body_rep.Items or []):
            continue
        wall_solid = body_rep.Items[0]
        void_solids = []
        depth_buffer = max(meta["thickness"] * 1.5, meta["thickness"] + 0.04)
        for record in records:
            local_center = world_to_wall_local(record["location"], meta["start"], meta["rotation_deg"])
            void_solids.append(
                make_wall_local_void_solid(
                    model,
                    length=float(record["dimensions"][0]),
                    depth=float(depth_buffer),
                    height=float(record["dimensions"][2]),
                    local_center=local_center,
                )
            )
        ifcopenshell.api.geometry.add_boolean(
            model,
            first_item=wall_solid,
            second_items=void_solids,
            operator="DIFFERENCE",
        )
        body_rep.RepresentationType = "Clipping"
        cut_summary[host_name] = {
            "openingCount": len(void_solids),
            "wallLocalDepthBufferM": float(depth_buffer),
            "thicknessM": meta["thickness"],
        }
    return cut_summary


def ensure_geometry(model, project, elements):
    model_3d = ifcopenshell.api.context.add_context(model, context_type="Model")
    body = ifcopenshell.api.context.add_context(
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_3d,
    )
    axis = ifcopenshell.api.context.add_context(
        model,
        context_type="Plan",
        context_identifier="Axis",
        target_view="GRAPH_VIEW",
        parent=ifcopenshell.api.context.add_context(model, context_type="Plan"),
    )
    statuses = {}
    for element, category, dimensions, location in elements:
        statuses[element.GlobalId] = apply_geometry(model, {"body": body, "axis": axis}, element, category, dimensions, location)
    add_pset(
        model,
        project,
        "Pset_CevizPoC_Geometry",
        {
            "RepresentationContexts": "Model/Body + Plan/Axis",
            "GeometryStatus": "simple swept/profile body representations with deterministic placements",
            "ReadOnlyPoC": True,
        },
    )
    return statuses


def main():
    args = parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    model = ifcopenshell.api.project.create_file(version="IFC4")
    project = ifcopenshell.api.root.create_entity(model, ifc_class="IfcProject", name="Ceviz Blender Bonsai PoC")
    ifcopenshell.api.unit.assign_unit(model)

    site = ifcopenshell.api.root.create_entity(model, ifc_class="IfcSite", name="PoC Site")
    building = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuilding", name="PoC Building")
    storey = ifcopenshell.api.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Ground Floor")
    storey.Elevation = 0.0

    ifcopenshell.api.aggregate.assign_object(model, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(model, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(model, products=[storey], relating_object=building)

    element_specs = [
        ("IfcSlab", "floor_slab", "FLOOR", "slab", (6.0, 4.0, 0.10), (0, 0, -0.05), "warm_concrete", "Room floor slab from sample scene dimensions."),
        ("IfcWall", "north_wall", "SOLIDWALL", "wall", (6.0, 0.12, 2.9), (0, 2.0, 1.45), "warm_concrete", "North wall from sample scene."),
        ("IfcWall", "south_wall", "SOLIDWALL", "wall", (6.0, 0.12, 2.9), (0, -2.0, 1.45), "warm_concrete", "South wall from sample scene."),
        ("IfcWall", "west_wall", "SOLIDWALL", "wall", (0.12, 4.0, 2.9), (-3.0, 0, 1.45), "warm_concrete", "West wall from sample scene."),
        ("IfcWall", "east_wall", "SOLIDWALL", "wall", (0.12, 4.0, 2.9), (3.0, 0, 1.45), "warm_concrete", "East wall from sample scene."),
        ("IfcWindow", "window_north", "WINDOW", "window", (1.8, 0.04, 1.0), (0, 2.07, 1.65), "soft_glass", "North-facing semantic window placeholder."),
        ("IfcDoor", "door_south", "DOOR", "door", (0.9, 0.06, 2.0), (-1.9, -2.07, 1.0), "light_wood", "South-facing semantic door placeholder."),
        ("IfcFurniture", "table_placeholder", "TABLE", "furniture", (1.4, 0.8, 0.9), (0.8, -0.4, 0.45), "light_wood", "Furniture placeholder from sample scene."),
    ]
    # Filling element name -> host wall name. Wall thickness is reused for the opening depth.
    hosting_specs = [
        ("window_north", "north_wall"),
        ("door_south", "south_wall"),
    ]
    elements = [
        create_element(model, ifc_class, name, predefined_type, category, dimensions, location, material, notes)
        for ifc_class, name, predefined_type, category, dimensions, location, material, notes in element_specs
    ]
    ifcopenshell.api.spatial.assign_container(model, products=elements, relating_structure=storey)

    spec_by_name = {spec[1]: spec for spec in element_specs}
    element_by_name = {spec[1]: element for spec, element in zip(element_specs, elements, strict=True)}
    opening_records = []
    for filling_name, host_name in hosting_specs:
        host_spec = spec_by_name[host_name]
        filling_spec = spec_by_name[filling_name]
        host_dims = host_spec[4]
        wall_thickness = min(host_dims[0], host_dims[1])
        filling_dims = filling_spec[4]
        filling_loc = filling_spec[5]
        opening_length = float(filling_dims[0])
        opening_width = float(wall_thickness)
        opening_height = float(filling_dims[2])
        opening_location = (
            float(filling_loc[0]),
            float(host_spec[5][1]),
            float(filling_loc[2]),
        )
        opening_notes = (
            f"Opening hosted by {host_name} for filling {filling_name}; "
            f"deterministic PoC void cut through the wall thickness."
        )
        opening = create_element(
            model,
            ifc_class="IfcOpeningElement",
            name=f"{filling_name}_opening",
            predefined_type="OPENING",
            category="opening",
            dimensions=(opening_length, opening_width, opening_height),
            location=opening_location,
            material="void",
            notes=opening_notes,
        )
        wall_element = element_by_name[host_name]
        filling_element = element_by_name[filling_name]
        ifcopenshell.api.feature.add_feature(model, feature=opening, element=wall_element)
        ifcopenshell.api.feature.add_filling(model, opening=opening, element=filling_element)
        add_pset(
            model,
            opening,
            "Pset_CevizPoC_Hosting",
            {
                "HostWallName": host_name,
                "FillingElementName": filling_name,
                "OpeningLengthM": opening_length,
                "OpeningWidthM": opening_width,
                "OpeningHeightM": opening_height,
                "ReadOnlyPoC": True,
            },
        )
        add_pset(
            model,
            wall_element,
            f"Pset_CevizPoC_Hosting_{filling_name}",
            {
                "HostsOpeningName": opening.Name,
                "HostsFillingName": filling_name,
                "OpeningGlobalId": opening.GlobalId,
                "FillingGlobalId": filling_element.GlobalId,
                "OpeningAreaM2": round(opening_length * opening_height, 6),
            },
        )
        add_pset(
            model,
            filling_element,
            "Pset_CevizPoC_Hosted",
            {
                "HostWallName": host_name,
                "OpeningName": opening.Name,
                "OpeningGlobalId": opening.GlobalId,
                "HostWallGlobalId": wall_element.GlobalId,
            },
        )
        opening_records.append({
            "name": opening.Name,
            "filling": filling_name,
            "host": host_name,
            "dimensions": (opening_length, opening_width, opening_height),
            "location": opening_location,
            "element": opening,
        })

    geometry_status = "semantic IFC with deterministic dimensions/locations; no shape representations yet"
    if args.with_geometry:
        geometry_inputs = [
            (element, category, dimensions, location)
            for element, (_, _, _, category, dimensions, location, _, _) in zip(elements, element_specs, strict=True)
        ]
        for record in opening_records:
            geometry_inputs.append(
                (record["element"], "opening", record["dimensions"], record["location"])
            )
        statuses = ensure_geometry(model, project, geometry_inputs)
        cut_summary = cut_wall_bodies_with_openings(
            model, opening_records, spec_by_name, element_by_name
        )
        geometry_status = (
            "simple swept/profile body representations with deterministic placements; "
            "wall bodies boolean-DIFFERENCEd by hosted opening voids"
            if cut_summary
            else "simple swept/profile body representations and object placements authored"
        )
        for element in elements + [record["element"] for record in opening_records]:
            add_pset(
                model,
                element,
                "Pset_CevizPoC_Geometry",
                {
                    "RepresentationStatus": statuses.get(element.GlobalId, "missing"),
                    "HasBodyRepresentation": statuses.get(element.GlobalId) not in {None, "unsupported"},
                },
            )
        for host_name, info in cut_summary.items():
            wall_element = element_by_name[host_name]
            add_pset(
                model,
                wall_element,
                "Pset_CevizPoC_BodyBoolean",
                {
                    "BooleanOperator": "DIFFERENCE",
                    "RepresentationType": "Clipping",
                    "OpeningCount": int(info["openingCount"]),
                    "WallThicknessM": float(info["thicknessM"]),
                    "VoidDepthBufferM": float(info["wallLocalDepthBufferM"]),
                    "ReadOnlyPoC": True,
                },
            )

    add_pset(
        model,
        project,
        "Pset_CevizPoC_Project",
        {
            "Source": "blender_scripts/create_sample_scene.py",
            "AuthoringRoute": "IfcOpenShell pure Python API under Blender headless",
            "GeometryStatus": geometry_status,
            "ReadOnlyPoC": True,
        },
    )

    model.write(str(out))
    print(f"Wrote IFC: {out}")
    print(f"Entities: {len(list(model))}")


if __name__ == "__main__":
    main()
