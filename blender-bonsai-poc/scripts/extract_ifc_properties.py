#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import ifcopenshell
import ifcopenshell.util.element
import ifcopenshell.util.placement
import ifcopenshell.util.representation

PRODUCT_CLASSES = (
    "IfcProject",
    "IfcSite",
    "IfcBuilding",
    "IfcBuildingStorey",
    "IfcSlab",
    "IfcWall",
    "IfcWindow",
    "IfcDoor",
    "IfcFurniture",
    "IfcOpeningElement",
)


def scalar(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [scalar(v) for v in value]
    return str(value)


def numeric(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def property_sets(entity):
    psets = ifcopenshell.util.element.get_psets(entity, psets_only=True)
    clean = {}
    for pset_name, props in sorted(psets.items()):
        clean[pset_name] = {
            prop_name: scalar(prop_value)
            for prop_name, prop_value in sorted(props.items())
            if prop_name != "id"
        }
    return clean


def classify(entity):
    psets = property_sets(entity)
    return psets.get("Pset_CevizPoC", {}).get("CevizCategory")


def dimensions_and_location(psets):
    ceviz = psets.get("Pset_CevizPoC", {})
    dimensions = {
        "length": numeric(ceviz.get("LengthM")),
        "width": numeric(ceviz.get("WidthM")),
        "height": numeric(ceviz.get("HeightM")),
    }
    location = {
        "x": numeric(ceviz.get("LocationX")),
        "y": numeric(ceviz.get("LocationY")),
        "z": numeric(ceviz.get("LocationZ")),
    }
    if any(v is None for v in dimensions.values()):
        dimensions = None
    if any(v is None for v in location.values()):
        location = None
    return dimensions, location


def round6(value):
    return round(float(value), 6)


def matrix_to_rows(matrix):
    return [[round6(value) for value in row] for row in matrix.tolist()]


def placement_info(entity):
    placement = getattr(entity, "ObjectPlacement", None)
    if not placement:
        return None
    matrix = ifcopenshell.util.placement.get_local_placement(placement)
    return {
        "type": placement.is_a(),
        "matrix": matrix_to_rows(matrix),
        "translation": {
            "x": round6(matrix[0][3]),
            "y": round6(matrix[1][3]),
            "z": round6(matrix[2][3]),
        },
        "xAxis": [round6(value) for value in matrix[:3, 0]],
        "yAxis": [round6(value) for value in matrix[:3, 1]],
        "zAxis": [round6(value) for value in matrix[:3, 2]],
    }


def hosting_info(entity):
    info = {
        "hostsOpenings": [],
        "voidedBy": None,
        "fillsOpening": None,
        "filledBy": None,
        "hostWall": None,
    }
    for rel in getattr(entity, "HasOpenings", []) or []:
        opening = getattr(rel, "RelatedOpeningElement", None)
        if opening is not None:
            info["hostsOpenings"].append(
                {
                    "globalId": getattr(opening, "GlobalId", None),
                    "name": getattr(opening, "Name", None),
                    "class": opening.is_a(),
                }
            )
    for rel in getattr(entity, "VoidsElements", []) or []:
        host = getattr(rel, "RelatingBuildingElement", None)
        if host is not None:
            info["voidedBy"] = {
                "globalId": getattr(host, "GlobalId", None),
                "name": getattr(host, "Name", None),
                "class": host.is_a(),
            }
    for rel in getattr(entity, "HasFillings", []) or []:
        filling = getattr(rel, "RelatedBuildingElement", None)
        if filling is not None:
            info["filledBy"] = {
                "globalId": getattr(filling, "GlobalId", None),
                "name": getattr(filling, "Name", None),
                "class": filling.is_a(),
            }
    for rel in getattr(entity, "FillsVoids", []) or []:
        opening = getattr(rel, "RelatingOpeningElement", None)
        if opening is not None:
            info["fillsOpening"] = {
                "globalId": getattr(opening, "GlobalId", None),
                "name": getattr(opening, "Name", None),
                "class": opening.is_a(),
            }
            for void_rel in getattr(opening, "VoidsElements", []) or []:
                host = getattr(void_rel, "RelatingBuildingElement", None)
                if host is not None:
                    info["hostWall"] = {
                        "globalId": getattr(host, "GlobalId", None),
                        "name": getattr(host, "Name", None),
                        "class": host.is_a(),
                    }
    return info


def representation_info(entity):
    representations = list(ifcopenshell.util.representation.get_representations_iter(entity))
    infos = []
    for representation in representations:
        context = representation.ContextOfItems
        resolved = ifcopenshell.util.representation.resolve_representation(representation)
        items = list(resolved.Items or [])
        infos.append(
            {
                "id": representation.id(),
                "representationIdentifier": getattr(representation, "RepresentationIdentifier", None),
                "representationType": getattr(representation, "RepresentationType", None),
                "contextType": getattr(context, "ContextType", None),
                "contextIdentifier": getattr(context, "ContextIdentifier", None),
                "targetView": getattr(context, "TargetView", None),
                "itemTypes": sorted({item.is_a() for item in items}),
                "itemCount": len(items),
            }
        )
    body = ifcopenshell.util.representation.get_representation(entity, "Model", "Body", "MODEL_VIEW")
    axis = ifcopenshell.util.representation.get_representation(entity, "Plan", "Axis", "GRAPH_VIEW")
    boolean_classes = {"IfcBooleanResult", "IfcBooleanClippingResult"}
    body_boolean = None
    if body is not None:
        body_items = list(body.Items or [])
        body_item_types = sorted({item.is_a() for item in body_items})
        is_boolean = any(item_type in boolean_classes for item_type in body_item_types)
        body_boolean = {
            "isBoolean": bool(is_boolean),
            "representationType": getattr(body, "RepresentationType", None),
            "itemTypes": body_item_types,
        }
        if is_boolean:
            second_operand_count = 0
            for item in body_items:
                cursor = item
                while cursor.is_a() in boolean_classes:
                    second_operand_count += 1
                    first = getattr(cursor, "FirstOperand", None)
                    if first is None:
                        break
                    cursor = first
            body_boolean["operandChainLength"] = second_operand_count
    return {
        "hasRepresentation": bool(representations),
        "hasBodyRepresentation": body is not None,
        "hasAxisRepresentation": axis is not None,
        "bodyBoolean": body_boolean,
        "representations": infos,
    }


def extract(path: Path):
    model = ifcopenshell.open(str(path))
    entities = []
    category_counts = {}
    class_counts = {}
    geometry_summary = {
        "elementsWithRepresentation": 0,
        "elementsWithBodyRepresentation": 0,
        "elementsWithAxisRepresentation": 0,
        "elementsWithBooleanBody": 0,
        "totalBooleanOperandChainLength": 0,
        "representationContexts": {},
    }
    hosting_summary = {
        "wallsHostingOpenings": 0,
        "openingsHosted": 0,
        "fillingsHosted": 0,
        "openingsWithoutFilling": 0,
        "fillingsWithoutHost": 0,
    }

    for ifc_class in PRODUCT_CLASSES:
        for entity in model.by_type(ifc_class):
            psets = property_sets(entity)
            category = psets.get("Pset_CevizPoC", {}).get("CevizCategory")
            dimensions, location = dimensions_and_location(psets)
            geometry = representation_info(entity)
            placement = placement_info(entity)
            hosting = hosting_info(entity)
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1
            class_counts[entity.is_a()] = class_counts.get(entity.is_a(), 0) + 1
            if hosting["hostsOpenings"]:
                hosting_summary["wallsHostingOpenings"] += 1
            if entity.is_a() == "IfcOpeningElement":
                hosting_summary["openingsHosted"] += 1
                if hosting["filledBy"] is None:
                    hosting_summary["openingsWithoutFilling"] += 1
            if entity.is_a() in ("IfcWindow", "IfcDoor"):
                if hosting["fillsOpening"] is not None:
                    hosting_summary["fillingsHosted"] += 1
                else:
                    hosting_summary["fillingsWithoutHost"] += 1
            if geometry["hasRepresentation"]:
                geometry_summary["elementsWithRepresentation"] += 1
            if geometry["hasBodyRepresentation"]:
                geometry_summary["elementsWithBodyRepresentation"] += 1
            if geometry["hasAxisRepresentation"]:
                geometry_summary["elementsWithAxisRepresentation"] += 1
            body_boolean = geometry.get("bodyBoolean") or {}
            if body_boolean.get("isBoolean"):
                geometry_summary["elementsWithBooleanBody"] += 1
                geometry_summary["totalBooleanOperandChainLength"] += int(body_boolean.get("operandChainLength", 0) or 0)
            for info in geometry["representations"]:
                context_key = "/".join(
                    [
                        info.get("contextType") or "unknown",
                        info.get("contextIdentifier") or "none",
                        info.get("targetView") or "none",
                    ]
                )
                geometry_summary["representationContexts"][context_key] = geometry_summary["representationContexts"].get(context_key, 0) + 1
            entities.append(
                {
                    "id": entity.id(),
                    "globalId": getattr(entity, "GlobalId", None),
                    "class": entity.is_a(),
                    "name": getattr(entity, "Name", None),
                    "predefinedType": getattr(entity, "PredefinedType", None),
                    "description": getattr(entity, "Description", None),
                    "cevizCategory": category,
                    "dimensionsM": dimensions,
                    "locationM": location,
                    "placement": placement,
                    "geometry": geometry,
                    "hosting": hosting,
                    "propertySets": psets,
                }
            )

    diagnostics = []
    for required in ["slab", "wall", "window", "door"]:
        if category_counts.get(required, 0) == 0:
            diagnostics.append({"severity": "warn", "code": "missing-category", "category": required})
    if category_counts.get("wall", 0) < 4:
        diagnostics.append({"severity": "warn", "code": "expected-four-walls", "count": category_counts.get("wall", 0)})
    if geometry_summary["elementsWithBodyRepresentation"] == 0:
        diagnostics.append({"severity": "info", "code": "no-body-representations-detected"})
    if hosting_summary["openingsWithoutFilling"]:
        diagnostics.append({"severity": "warn", "code": "openings-without-filling", "count": hosting_summary["openingsWithoutFilling"]})
    if hosting_summary["fillingsWithoutHost"]:
        diagnostics.append({"severity": "warn", "code": "fillings-without-host", "count": hosting_summary["fillingsWithoutHost"]})

    return {
        "kind": "ifc-entity-property-snapshot",
        "contractVersion": "0.1.0",
        "source": {
            "tool": "IfcOpenShell",
            "version": ifcopenshell.version,
            "file": str(path),
            "schema": model.schema,
        },
        "summary": {
            "entityCount": len(list(model)),
            "extractedEntityCount": len(entities),
            "classCounts": dict(sorted(class_counts.items())),
            "categoryCounts": dict(sorted(category_counts.items())),
            "geometry": {
                **{key: value for key, value in geometry_summary.items() if key != "representationContexts"},
                "representationContexts": dict(sorted(geometry_summary["representationContexts"].items())),
            },
            "hosting": hosting_summary,
        },
        "entities": sorted(entities, key=lambda e: (e["class"], e["name"] or "")),
        "diagnostics": diagnostics,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract IFC entities and property sets to JSON.")
    parser.add_argument("--input", required=True, help="Input .ifc path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)

    data = extract(Path(args.input))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Wrote IFC property snapshot: {out}")


if __name__ == "__main__":
    main()
