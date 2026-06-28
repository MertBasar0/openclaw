#!/usr/bin/env python3
"""Compare deterministic IFC takeoff against tessellated geometry metrics."""

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "0.1.0"


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def round6(value: float) -> float:
    return round(float(value), 6)


def as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def percent_delta(actual: float, expected: float) -> float | None:
    if abs(expected) < 1e-9:
        return None
    return round6(((actual - expected) / expected) * 100.0)


def compare_number(name: str, actual: float, expected: float, tolerance: float, units: str) -> dict[str, Any]:
    delta = round6(actual - expected)
    status = "ok" if abs(delta) <= tolerance else "needs-review"
    return {
        "name": name,
        "status": status,
        "actual": round6(actual),
        "expected": round6(expected),
        "delta": delta,
        "deltaPercent": percent_delta(actual, expected),
        "tolerance": tolerance,
        "units": units,
    }


def category_counts(report: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(value) for key, value in (report.get("byCategory") or {}).items()}


def takeoff_category_counts(takeoff: dict[str, Any]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in ((takeoff.get("summary") or {}).get("categoryCounts") or {}).items()
    }


def expected_wall_net_volume_by_global_id(takeoff: dict[str, Any]) -> dict[str, float]:
    expected: dict[str, float] = {}
    for element in takeoff.get("elements") or []:
        if element.get("category") != "wall":
            continue
        gid = element.get("globalId")
        quantities = element.get("quantities") or {}
        gross = as_float(quantities.get("boundingBoxVolumeM3"))
        opening_area = as_float(quantities.get("wallOpeningAreaM2"))
        thickness = as_float(quantities.get("thicknessM"))
        expected[str(gid)] = round6(max(gross - (opening_area * thickness), 0.0))
    return expected


def geometry_by_global_id(geometry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("globalId")): item for item in geometry.get("created") or [] if item.get("globalId")}


def host_wall_volume_checks(takeoff: dict[str, Any], geometry: dict[str, Any]) -> list[dict[str, Any]]:
    expected_by_gid = expected_wall_net_volume_by_global_id(takeoff)
    geometry_by_gid = geometry_by_global_id(geometry)
    checks = []
    for gid, expected in sorted(expected_by_gid.items()):
        item = geometry_by_gid.get(gid)
        if not item or int(item.get("hostedOpeningCount") or 0) <= 0:
            continue
        actual = as_float(item.get("meshVolumeM3"))
        check = compare_number(
            f"host wall net mesh volume: {item.get('name') or gid}",
            actual,
            expected,
            tolerance=0.05,
            units="m3",
        )
        check["globalId"] = gid
        check["hostedOpeningCount"] = int(item.get("hostedOpeningCount") or 0)
        checks.append(check)
    return checks


def shape_coverage_check(takeoff: dict[str, Any], geometry: dict[str, Any]) -> dict[str, Any]:
    expected = int(((takeoff.get("summary") or {}).get("elementCount")) or 0)
    actual = int(geometry.get("shapeCreatedCount") or 0)
    failures = int(geometry.get("shapeFailureCount") or 0)
    status = "ok" if actual == expected and failures == 0 else "needs-review"
    return {
        "name": "shape coverage",
        "status": status,
        "actual": actual,
        "expected": expected,
        "shapeFailureCount": failures,
    }


def category_coverage_check(takeoff: dict[str, Any], geometry: dict[str, Any]) -> dict[str, Any]:
    expected = takeoff_category_counts(takeoff)
    actual = category_counts(geometry)
    return {
        "name": "category coverage",
        "status": "ok" if actual == expected else "needs-review",
        "actual": actual,
        "expected": expected,
    }


def aggregate_checks(takeoff: dict[str, Any], geometry: dict[str, Any]) -> list[dict[str, Any]]:
    takeoff_summary = takeoff.get("summary") or {}
    takeoff_totals = takeoff_summary.get("totals") or {}
    takeoff_by_category = takeoff_summary.get("byCategory") or {}
    geometry_totals = geometry.get("totals") or {}
    geometry_by_category = geometry.get("quantityByCategory") or {}
    slab_geometry = geometry_by_category.get("slab") or {}
    wall_geometry = geometry_by_category.get("wall") or {}
    checks = [
        compare_number(
            "slab bbox footprint area",
            as_float(slab_geometry.get("bboxFootprintAreaM2")),
            as_float(takeoff_totals.get("slabAreaM2")),
            tolerance=0.02,
            units="m2",
        ),
        compare_number(
            "overall bbox volume",
            as_float(geometry_totals.get("bboxVolumeM3")),
            as_float(takeoff_totals.get("boundingBoxVolumeM3")),
            tolerance=0.05,
            units="m3",
        ),
    ]
    for category, tolerance in (
        ("door", 0.02),
        ("furniture", 0.02),
        ("slab", 0.02),
        ("wall", 0.02),
        ("window", 0.02),
    ):
        geometry_category = geometry_by_category.get(category) or {}
        takeoff_category = takeoff_by_category.get(category) or {}
        checks.append(
            compare_number(
                f"{category} bbox volume",
                as_float(geometry_category.get("bboxVolumeM3")),
                as_float(takeoff_category.get("boundingBoxVolumeM3")),
                tolerance=tolerance,
                units="m3",
            )
        )
    checks.append(
        compare_number(
            "wall mesh surface area vs deterministic wall surface",
            as_float(wall_geometry.get("meshSurfaceAreaM2")),
            as_float((takeoff_by_category.get("wall") or {}).get("surfaceAreaM2")),
            tolerance=5.0,
            units="m2",
        )
    )
    checks.extend(host_wall_volume_checks(takeoff, geometry))
    return checks


def summarize_status(checks: list[dict[str, Any]]) -> str:
    if any(check.get("status") == "fail" for check in checks):
        return "fail"
    if any(check.get("status") == "needs-review" for check in checks):
        return "needs-review"
    return "ok"


def build_report(takeoff_path: Path, geometry_path: Path) -> dict[str, Any]:
    takeoff = read_json(takeoff_path)
    geometry = read_json(geometry_path)
    checks = [
        shape_coverage_check(takeoff, geometry),
        category_coverage_check(takeoff, geometry),
        *aggregate_checks(takeoff, geometry),
    ]
    status = summarize_status(checks)
    return {
        "kind": "ifc-geometry-takeoff-comparison",
        "contractVersion": CONTRACT_VERSION,
        "status": status,
        "sourceTakeoff": str(takeoff_path),
        "sourceGeometryValidation": str(geometry_path),
        "summary": {
            "checkCount": len(checks),
            "okCount": sum(1 for check in checks if check.get("status") == "ok"),
            "needsReviewCount": sum(1 for check in checks if check.get("status") == "needs-review"),
            "failCount": sum(1 for check in checks if check.get("status") == "fail"),
        },
        "checks": checks,
        "notes": [
            "Deterministic takeoff remains the baseline contract.",
            "Geometry metrics come from IfcOpenShell tessellation and are used as independent review evidence.",
            "Host-wall mesh volume checks are the key signal for whether boolean opening cuts survive into tessellated geometry.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# IFC Geometry Takeoff Comparison",
        "",
        f"- Status: {report['status']}",
        f"- Checks: {report['summary']['okCount']} ok, {report['summary']['needsReviewCount']} needs review, {report['summary']['failCount']} fail",
        "",
        "## Checks",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"### {check['name']}")
        lines.append(f"- Status: {check['status']}")
        if "actual" in check:
            lines.append(f"- Actual: {check['actual']}")
        if "expected" in check:
            lines.append(f"- Expected: {check['expected']}")
        if "delta" in check:
            units = check.get("units", "")
            lines.append(f"- Delta: {check['delta']} {units}".rstrip())
        if check.get("deltaPercent") is not None:
            lines.append(f"- Delta percent: {check['deltaPercent']}%")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--takeoff", required=True, type=Path)
    parser.add_argument("--geometry", required=True, type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    report = build_report(args.takeoff, args.geometry)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
