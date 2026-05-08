#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round6(value):
    return round(float(value), 6)


def empty_geometry_summary():
    return {
        "elementsWithRepresentation": 0,
        "elementsWithBodyRepresentation": 0,
        "elementsWithAxisRepresentation": 0,
        "elementsWithBooleanBody": 0,
        "totalBooleanOperandChainLength": 0,
        "representationContexts": {},
    }


def normalize_geometry_summary(geometry):
    if not isinstance(geometry, dict):
        return empty_geometry_summary()
    return {
        "elementsWithRepresentation": int(geometry.get("elementsWithRepresentation", 0) or 0),
        "elementsWithBodyRepresentation": int(geometry.get("elementsWithBodyRepresentation", 0) or 0),
        "elementsWithAxisRepresentation": int(geometry.get("elementsWithAxisRepresentation", 0) or 0),
        "elementsWithBooleanBody": int(geometry.get("elementsWithBooleanBody", 0) or 0),
        "totalBooleanOperandChainLength": int(geometry.get("totalBooleanOperandChainLength", 0) or 0),
        "representationContexts": dict(sorted((geometry.get("representationContexts") or {}).items())),
    }


def bbox_from_center(dimensions, location):
    half_x = dimensions["length"] / 2.0
    half_y = dimensions["width"] / 2.0
    half_z = dimensions["height"] / 2.0
    return {
        "min": {
            "x": round6(location["x"] - half_x),
            "y": round6(location["y"] - half_y),
            "z": round6(location["z"] - half_z),
        },
        "max": {
            "x": round6(location["x"] + half_x),
            "y": round6(location["y"] + half_y),
            "z": round6(location["z"] + half_z),
        },
    }


def size_from_bbox(bbox):
    return {
        axis: round6(bbox["max"][axis] - bbox["min"][axis])
        for axis in ("x", "y", "z")
    }


def category_quantities(category, dimensions):
    length = dimensions["length"]
    width = dimensions["width"]
    height = dimensions["height"]
    horizontal_span = max(length, width)
    horizontal_thickness = min(length, width)
    quantities = {
        "boundingBoxVolumeM3": round6(length * width * height),
        "footprintAreaM2": round6(length * width),
        "surfaceAreaM2": round6(2.0 * ((length * width) + (length * height) + (width * height))),
        "horizontalSpanM": round6(horizontal_span),
        "heightM": round6(height),
    }
    if category == "wall":
        quantities["wallFaceAreaM2"] = round6(horizontal_span * height)
        quantities["thicknessM"] = round6(horizontal_thickness)
    if category == "slab":
        quantities["slabAreaM2"] = round6(length * width)
        quantities["thicknessM"] = round6(height)
    if category in {"door", "window"}:
        quantities["openingAreaM2"] = round6(horizontal_span * height)
    return quantities


def init_totals():
    return {
        "count": 0,
        "boundingBoxVolumeM3": 0.0,
        "footprintAreaM2": 0.0,
        "surfaceAreaM2": 0.0,
        "horizontalSpanM": 0.0,
        "wallFaceAreaM2": 0.0,
        "wallFaceAreaNetM2": 0.0,
        "wallOpeningAreaM2": 0.0,
        "slabAreaM2": 0.0,
        "openingAreaM2": 0.0,
    }


def add_totals(target, quantities):
    target["count"] += 1
    for key in (
        "boundingBoxVolumeM3",
        "footprintAreaM2",
        "surfaceAreaM2",
        "horizontalSpanM",
        "wallFaceAreaM2",
        "wallFaceAreaNetM2",
        "wallOpeningAreaM2",
        "slabAreaM2",
        "openingAreaM2",
    ):
        target[key] += quantities.get(key, 0.0)


def round_totals(totals):
    return {
        key: round6(value) if isinstance(value, float) else value
        for key, value in totals.items()
    }


def accumulate_extents(extents, bbox):
    for axis in ("x", "y", "z"):
        extents["min"][axis] = min(extents["min"][axis], bbox["min"][axis])
        extents["max"][axis] = max(extents["max"][axis], bbox["max"][axis])


def extract_takeoff(snapshot):
    takeoff_elements = []
    category_counts = {}
    class_counts = {}
    material_counts = {}
    total_quantities = init_totals()
    per_category = {}
    extents = {
        "min": {"x": float("inf"), "y": float("inf"), "z": float("inf")},
        "max": {"x": float("-inf"), "y": float("-inf"), "z": float("-inf")},
    }
    diagnostics = []

    # Pre-pass: aggregate opening areas hosted by each wall (keyed by wall GlobalId).
    opening_area_by_host = {}
    opening_count_by_host = {}
    for entity in snapshot.get("entities", []):
        if entity.get("class") != "IfcOpeningElement":
            continue
        host = (entity.get("hosting") or {}).get("voidedBy") or {}
        host_global_id = host.get("globalId")
        if not host_global_id:
            continue
        dims = entity.get("dimensionsM") or {}
        length = numeric(dims.get("length"))
        height = numeric(dims.get("height"))
        if length is None or height is None:
            continue
        opening_area_by_host[host_global_id] = opening_area_by_host.get(host_global_id, 0.0) + (length * height)
        opening_count_by_host[host_global_id] = opening_count_by_host.get(host_global_id, 0) + 1

    for entity in snapshot.get("entities", []):
        category = entity.get("cevizCategory")
        if not category:
            continue
        if category == "opening":
            # Openings are accounted for via the host wall's net area; skip individual takeoff rows.
            continue
        pset = entity.get("propertySets", {}).get("Pset_CevizPoC", {})
        dimensions = entity.get("dimensionsM") or {
            "length": numeric(pset.get("LengthM")),
            "width": numeric(pset.get("WidthM")),
            "height": numeric(pset.get("HeightM")),
        }
        location = entity.get("locationM") or {
            "x": numeric(pset.get("LocationX")),
            "y": numeric(pset.get("LocationY")),
            "z": numeric(pset.get("LocationZ")),
        }
        if not dimensions or not location:
            diagnostics.append(
                {
                    "severity": "warn",
                    "code": "missing-dimensions-or-location",
                    "entity": entity.get("name") or entity.get("globalId") or entity.get("id"),
                    "class": entity.get("class"),
                    "category": category,
                }
            )
            continue
        if any(value is None for value in dimensions.values()) or any(value is None for value in location.values()):
            diagnostics.append(
                {
                    "severity": "warn",
                    "code": "missing-dimensions-or-location",
                    "entity": entity.get("name") or entity.get("globalId") or entity.get("id"),
                    "class": entity.get("class"),
                    "category": category,
                }
            )
            continue

        material = pset.get("MaterialHint")
        bbox = bbox_from_center(dimensions, location)
        quantities = category_quantities(category, dimensions)
        if category == "wall":
            global_id = entity.get("globalId")
            opening_area = opening_area_by_host.get(global_id, 0.0)
            opening_count = opening_count_by_host.get(global_id, 0)
            gross = quantities.get("wallFaceAreaM2", 0.0)
            net = max(gross - opening_area, 0.0)
            quantities["wallOpeningAreaM2"] = round6(opening_area)
            quantities["wallFaceAreaNetM2"] = round6(net)
            quantities["hostedOpeningCount"] = opening_count
        accumulate_extents(extents, bbox)
        add_totals(total_quantities, quantities)
        category_counts[category] = category_counts.get(category, 0) + 1
        class_name = entity.get("class")
        class_counts[class_name] = class_counts.get(class_name, 0) + 1
        if material:
            material_counts[material] = material_counts.get(material, 0) + 1
        category_total = per_category.setdefault(category, init_totals())
        add_totals(category_total, quantities)
        hosting = entity.get("hosting") or {}
        takeoff_elements.append(
            {
                "id": entity.get("id"),
                "globalId": entity.get("globalId"),
                "class": class_name,
                "name": entity.get("name"),
                "category": category,
                "materialHint": material,
                "dimensionsM": dimensions,
                "locationM": location,
                "bboxM": bbox,
                "quantities": quantities,
                "hosting": {
                    "hostsOpenings": hosting.get("hostsOpenings", []),
                    "hostWall": hosting.get("hostWall"),
                    "fillsOpening": hosting.get("fillsOpening"),
                },
            }
        )

    has_extents = takeoff_elements and extents["min"]["x"] != float("inf")
    if not has_extents:
        diagnostics.append({"severity": "warn", "code": "no-quantified-elements"})

    hosting_summary = snapshot.get("summary", {}).get("hosting") or {}
    summary = {
        "elementCount": len(takeoff_elements),
        "categoryCounts": dict(sorted(category_counts.items())),
        "classCounts": dict(sorted(class_counts.items())),
        "materialCounts": dict(sorted(material_counts.items())),
        "geometry": normalize_geometry_summary(snapshot.get("summary", {}).get("geometry")),
        "hosting": {
            "wallsHostingOpenings": int(hosting_summary.get("wallsHostingOpenings", 0) or 0),
            "openingsHosted": int(hosting_summary.get("openingsHosted", 0) or 0),
            "fillingsHosted": int(hosting_summary.get("fillingsHosted", 0) or 0),
            "openingsWithoutFilling": int(hosting_summary.get("openingsWithoutFilling", 0) or 0),
            "fillingsWithoutHost": int(hosting_summary.get("fillingsWithoutHost", 0) or 0),
            "totalWallOpeningAreaM2": round6(total_quantities.get("wallOpeningAreaM2", 0.0)),
            "totalWallFaceAreaNetM2": round6(total_quantities.get("wallFaceAreaNetM2", 0.0)),
        },
        "totals": round_totals(total_quantities),
        "byCategory": {
            category: round_totals(values)
            for category, values in sorted(per_category.items())
        },
        "modelExtentsM": None,
    }
    if has_extents:
        summary["modelExtentsM"] = {
            "min": {axis: round6(value) for axis, value in extents["min"].items()},
            "max": {axis: round6(value) for axis, value in extents["max"].items()},
            "size": size_from_bbox(extents),
        }

    return {
        "kind": "ifc-takeoff-report",
        "contractVersion": snapshot.get("contractVersion", "0.1.0"),
        "source": snapshot.get("source", {}),
        "summary": summary,
        "elements": sorted(takeoff_elements, key=lambda item: (item["category"], item["name"] or "")),
        "diagnostics": diagnostics,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate a deterministic takeoff report from IFC property snapshot JSON.")
    parser.add_argument("--input", required=True, help="Input IFC property snapshot JSON path")
    parser.add_argument("--output", required=True, help="Output takeoff JSON path")
    args = parser.parse_args()

    report = extract_takeoff(read_json(Path(args.input)))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote IFC takeoff report: {out}")


if __name__ == "__main__":
    main()
