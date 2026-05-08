#!/usr/bin/env python3
import argparse
import json
import time
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def round6(value: Any) -> float:
    return round(float(value), 6)


def empty_geometry_summary() -> dict[str, Any]:
    return {
        "elementsWithRepresentation": 0,
        "elementsWithBodyRepresentation": 0,
        "elementsWithAxisRepresentation": 0,
        "representationContexts": {},
    }


def normalize_geometry_summary(geometry: Any) -> dict[str, Any]:
    if not isinstance(geometry, dict):
        return {**empty_geometry_summary(), "elementsWithBooleanBody": 0, "totalBooleanOperandChainLength": 0}
    return {
        "elementsWithRepresentation": int(geometry.get("elementsWithRepresentation", 0) or 0),
        "elementsWithBodyRepresentation": int(geometry.get("elementsWithBodyRepresentation", 0) or 0),
        "elementsWithAxisRepresentation": int(geometry.get("elementsWithAxisRepresentation", 0) or 0),
        "elementsWithBooleanBody": int(geometry.get("elementsWithBooleanBody", 0) or 0),
        "totalBooleanOperandChainLength": int(geometry.get("totalBooleanOperandChainLength", 0) or 0),
        "representationContexts": dict(sorted((geometry.get("representationContexts") or {}).items())),
    }


def detect_geometry_level(geometry: dict[str, Any]) -> str:
    if geometry.get("elementsWithRepresentation", 0) > 0:
        return "real-ifc-shape-representations"
    return "metadata-only"


def assessment_status(geometry_level: str, diagnostics: list[dict[str, Any]]) -> str:
    if diagnostics:
        return "needs-review"
    if geometry_level == "real-ifc-shape-representations":
        return "geometry-aware-poc-ready"
    return "metadata-takeoff-poc-ready"


def build_caveats(geometry_level: str, hosting: dict[str, Any], geometry: dict[str, Any]) -> list[str]:
    has_hosting = (hosting.get("openingsHosted", 0) or 0) > 0
    has_boolean_cuts = bool(geometry.get("hasBooleanBodyCuts"))
    caveats = [
        "Quantities are deterministic PoC outputs derived from curated IFC dimensions/placements, not production BIM validation.",
        "Representation coverage only confirms the presence of basic IFC shape representations; it does not certify authoring correctness or downstream viewer compatibility.",
    ]
    if has_boolean_cuts:
        caveats.append(
            "Wall bodies use IfcBooleanResult DIFFERENCE operands to subtract opening voids, but tessellated mesh validation against viewer renderers is not performed here."
        )
    elif has_hosting:
        caveats.append(
            "Opening hosting is wired through IfcRelVoidsElement and IfcRelFillsElement, but the wall bodies remain solid swept volumes (no boolean cut)."
        )
    else:
        caveats.append(
            "Opening hosting, void relationships, and clash-aware wall/window/door semantics are not modeled in this slice."
        )
    if geometry_level == "metadata-only":
        caveats.append("This action is metadata-only: no IFC body or axis shape representations were detected.")
    return caveats


def build_next_actions(geometry_level: str, hosting: dict[str, Any], geometry: dict[str, Any]) -> list[str]:
    has_hosting = (hosting.get("openingsHosted", 0) or 0) > 0
    has_boolean_cuts = bool(geometry.get("hasBooleanBodyCuts"))
    if geometry_level == "real-ifc-shape-representations":
        actions = []
        if not has_hosting:
            actions.append("Model hosted openings explicitly with IfcOpeningElement and wall void relationships.")
        elif not has_boolean_cuts:
            actions.append("Author opening boundary geometry that fully clashes through the wall body so net wall area matches the void cut.")
        else:
            actions.append("Validate boolean wall bodies in an external viewer (e.g. BlenderBIM/Bonsai) and tighten the void buffer once visual artefacts are ruled out.")
        actions.extend([
            "Cross-check deterministic takeoff totals against geometry-derived quantities or native QTO extraction.",
            "Expose model-report readiness flags in the queue/orchestrator so follow-up agents can branch without re-parsing raw JSON.",
            "Expand the sample set beyond the single-room layout to cover multi-room or multi-storey cases before broadening the copilot surface.",
        ])
        return actions
    return [
        "Use ifc-geometry-demo as the next controlled upgrade path when downstream agents need representation-aware BIM review.",
        "Keep the current deterministic takeoff as the baseline contract and compare it against future geometry-derived quantities.",
        "Expose model-report readiness flags in the queue/orchestrator so follow-up agents can branch without re-parsing raw JSON.",
        "Expand the sample set beyond the single-room layout to cover multi-room or multi-storey cases before broadening the copilot surface.",
    ]


def build_assessment(
    model_summary: dict[str, Any],
    quantity_highlights: dict[str, Any],
    geometry_readiness: dict[str, Any],
    hosting_readiness: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> str:
    element_count = model_summary["quantifiedElementCount"]
    category_count = len(model_summary["categoryCounts"])
    class_count = len(model_summary["classCounts"])
    material_count = len(model_summary["materialCounts"])
    extents = quantity_highlights["modelExtentsM"]["size"] if quantity_highlights.get("modelExtentsM") else None
    extents_text = (
        f"{extents['x']} x {extents['y']} x {extents['z']} m"
        if extents
        else "unknown extents"
    )
    if geometry_readiness["hasRealShapeRepresentations"]:
        boolean_phrase = (
            f", with {geometry_readiness['elementsWithBooleanBody']} boolean-cut bodies"
            if geometry_readiness.get("hasBooleanBodyCuts")
            else ""
        )
        geometry_sentence = (
            f"Real IFC shape coverage is present on {geometry_readiness['elementsWithRepresentation']} elements "
            f"({geometry_readiness['elementsWithBodyRepresentation']} body, {geometry_readiness['elementsWithAxisRepresentation']} axis"
            f"{boolean_phrase})."
        )
    else:
        geometry_sentence = "No IFC body or axis shape representations were detected; this remains a metadata-only model."
    diagnostics_sentence = (
        f" {len(diagnostics)} diagnostics need review."
        if diagnostics
        else " Diagnostics are currently empty."
    )
    if hosting_readiness.get("hasOpeningHosting"):
        hosting_sentence = (
            f" Opening hosting is wired: {hosting_readiness['openingsHosted']} openings across "
            f"{hosting_readiness['wallsHostingOpenings']} walls, "
            f"{hosting_readiness['fillingsHosted']} fillings linked, "
            f"net wall face area {hosting_readiness['totalWallFaceAreaNetM2']} m2 "
            f"(opening cut-out {hosting_readiness['totalWallOpeningAreaM2']} m2)."
        )
    else:
        hosting_sentence = " No opening hosting was detected; walls remain solid in this slice."
    return (
        f"This PoC IFC model contains {element_count} quantified elements across {category_count} categories, "
        f"{class_count} IFC classes, and {material_count} material hints. "
        f"It reports {quantity_highlights['slabAreaM2']} m2 slab area, {quantity_highlights['wallFaceAreaM2']} m2 wall face area "
        f"({quantity_highlights['wallFaceAreaNetM2']} m2 net), "
        f"{quantity_highlights['openingAreaM2']} m2 opening area, and {quantity_highlights['totalBoundingBoxVolumeM3']} m3 total bbox volume "
        f"within overall extents of {extents_text}. {geometry_sentence}{hosting_sentence}{diagnostics_sentence}"
    )


def build_report(
    snapshot: dict[str, Any],
    takeoff: dict[str, Any],
    envelope: dict[str, Any] | None,
    request_id: str | None,
    action: str | None,
) -> dict[str, Any]:
    snapshot_summary = snapshot.get("summary") or {}
    takeoff_summary = takeoff.get("summary") or {}
    geometry = normalize_geometry_summary(takeoff_summary.get("geometry") or snapshot_summary.get("geometry"))
    geometry_level = detect_geometry_level(geometry)
    combined_diagnostics = list(snapshot.get("diagnostics") or []) + list(takeoff.get("diagnostics") or [])

    model_summary = {
        "quantifiedElementCount": takeoff_summary.get("elementCount", 0),
        "extractedEntityCount": snapshot_summary.get("extractedEntityCount", 0),
        "categoryCounts": dict(sorted((takeoff_summary.get("categoryCounts") or {}).items())),
        "classCounts": dict(sorted((takeoff_summary.get("classCounts") or {}).items())),
        "materialCounts": dict(sorted((takeoff_summary.get("materialCounts") or {}).items())),
    }
    totals = takeoff_summary.get("totals") or {}
    hosting_summary = takeoff_summary.get("hosting") or snapshot_summary.get("hosting") or {}
    quantity_highlights = {
        "slabAreaM2": round6(totals.get("slabAreaM2", 0.0)),
        "wallFaceAreaM2": round6(totals.get("wallFaceAreaM2", 0.0)),
        "wallFaceAreaNetM2": round6(totals.get("wallFaceAreaNetM2", totals.get("wallFaceAreaM2", 0.0))),
        "wallOpeningAreaM2": round6(totals.get("wallOpeningAreaM2", 0.0)),
        "openingAreaM2": round6(totals.get("openingAreaM2", 0.0)),
        "totalBoundingBoxVolumeM3": round6(totals.get("boundingBoxVolumeM3", 0.0)),
        "modelExtentsM": takeoff_summary.get("modelExtentsM"),
    }
    geometry_readiness = {
        "hasRealShapeRepresentations": geometry.get("elementsWithRepresentation", 0) > 0,
        "elementsWithRepresentation": int(geometry.get("elementsWithRepresentation", 0) or 0),
        "elementsWithBodyRepresentation": int(geometry.get("elementsWithBodyRepresentation", 0) or 0),
        "elementsWithAxisRepresentation": int(geometry.get("elementsWithAxisRepresentation", 0) or 0),
        "elementsWithBooleanBody": int(geometry.get("elementsWithBooleanBody", 0) or 0),
        "totalBooleanOperandChainLength": int(geometry.get("totalBooleanOperandChainLength", 0) or 0),
        "hasBooleanBodyCuts": (geometry.get("elementsWithBooleanBody", 0) or 0) > 0,
        "representationContexts": dict(sorted((geometry.get("representationContexts") or {}).items())),
        "geometryLevel": geometry_level,
    }
    hosting_readiness = {
        "wallsHostingOpenings": int(hosting_summary.get("wallsHostingOpenings", 0) or 0),
        "openingsHosted": int(hosting_summary.get("openingsHosted", 0) or 0),
        "fillingsHosted": int(hosting_summary.get("fillingsHosted", 0) or 0),
        "openingsWithoutFilling": int(hosting_summary.get("openingsWithoutFilling", 0) or 0),
        "fillingsWithoutHost": int(hosting_summary.get("fillingsWithoutHost", 0) or 0),
        "totalWallOpeningAreaM2": round6(hosting_summary.get("totalWallOpeningAreaM2", quantity_highlights["wallOpeningAreaM2"])),
        "totalWallFaceAreaNetM2": round6(hosting_summary.get("totalWallFaceAreaNetM2", quantity_highlights["wallFaceAreaNetM2"])),
        "hasOpeningHosting": (hosting_summary.get("openingsHosted", 0) or 0) > 0,
    }
    assessment = build_assessment(model_summary, quantity_highlights, geometry_readiness, hosting_readiness, combined_diagnostics)

    request_id = (envelope.get("requestId") if envelope else None) or request_id
    action = (envelope.get("action") if envelope else None) or action

    return {
        "kind": "ifc-model-report",
        "contractVersion": takeoff.get("contractVersion") or snapshot.get("contractVersion") or "0.1.0",
        "generatedAtUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "requestId": request_id,
        "action": action,
        "source": {
            "snapshot": snapshot.get("source"),
            "takeoff": takeoff.get("source"),
            "resultEnvelope": {
                "requestId": request_id,
                "action": action,
                "ok": envelope.get("ok"),
                "geometryLevel": ((envelope.get("execution") or {}).get("geometryLevel")),
            }
            if envelope
            else None,
        },
        "status": assessment_status(geometry_level, combined_diagnostics),
        "modelSummary": model_summary,
        "quantityHighlights": quantity_highlights,
        "geometryReadiness": geometry_readiness,
        "hostingReadiness": hosting_readiness,
        "caveats": build_caveats(geometry_level, hosting_readiness, geometry_readiness),
        "recommendedNextActions": build_next_actions(geometry_level, hosting_readiness, geometry_readiness),
        "naturalLanguageAssessment": assessment,
        "diagnostics": combined_diagnostics,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["modelSummary"]
    quantities = report["quantityHighlights"]
    geometry = report["geometryReadiness"]
    extents = quantities.get("modelExtentsM")
    extents_line = (
        f"{extents['size']['x']} x {extents['size']['y']} x {extents['size']['z']} m"
        if extents
        else "n/a"
    )

    lines = [
        "# IFC Model Report",
        "",
        "## Assessment",
        report["naturalLanguageAssessment"],
        "",
        "## Model Summary",
        f"- Quantified elements: {summary['quantifiedElementCount']}",
        f"- Extracted entities: {summary['extractedEntityCount']}",
        f"- Categories: {json.dumps(summary['categoryCounts'], sort_keys=True)}",
        f"- Classes: {json.dumps(summary['classCounts'], sort_keys=True)}",
        f"- Materials: {json.dumps(summary['materialCounts'], sort_keys=True)}",
        "",
        "## Quantity Highlights",
        f"- slabAreaM2: {quantities['slabAreaM2']}",
        f"- wallFaceAreaM2: {quantities['wallFaceAreaM2']}",
        f"- wallFaceAreaNetM2: {quantities['wallFaceAreaNetM2']}",
        f"- wallOpeningAreaM2: {quantities['wallOpeningAreaM2']}",
        f"- openingAreaM2: {quantities['openingAreaM2']}",
        f"- totalBoundingBoxVolumeM3: {quantities['totalBoundingBoxVolumeM3']}",
        f"- extents: {extents_line}",
        "",
        "## Geometry Readiness",
        f"- hasRealShapeRepresentations: {str(geometry['hasRealShapeRepresentations']).lower()}",
        f"- elementsWithRepresentation: {geometry['elementsWithRepresentation']}",
        f"- elementsWithBodyRepresentation: {geometry['elementsWithBodyRepresentation']}",
        f"- elementsWithAxisRepresentation: {geometry['elementsWithAxisRepresentation']}",
        f"- geometryLevel: {geometry['geometryLevel']}",
        f"- elementsWithBooleanBody: {geometry['elementsWithBooleanBody']}",
        f"- hasBooleanBodyCuts: {str(geometry['hasBooleanBodyCuts']).lower()}",
        f"- totalBooleanOperandChainLength: {geometry['totalBooleanOperandChainLength']}",
        f"- representationContexts: {json.dumps(geometry['representationContexts'], sort_keys=True)}",
        "",
        "## Hosting Readiness",
        f"- hasOpeningHosting: {str(report['hostingReadiness']['hasOpeningHosting']).lower()}",
        f"- wallsHostingOpenings: {report['hostingReadiness']['wallsHostingOpenings']}",
        f"- openingsHosted: {report['hostingReadiness']['openingsHosted']}",
        f"- fillingsHosted: {report['hostingReadiness']['fillingsHosted']}",
        f"- openingsWithoutFilling: {report['hostingReadiness']['openingsWithoutFilling']}",
        f"- fillingsWithoutHost: {report['hostingReadiness']['fillingsWithoutHost']}",
        f"- totalWallOpeningAreaM2: {report['hostingReadiness']['totalWallOpeningAreaM2']}",
        f"- totalWallFaceAreaNetM2: {report['hostingReadiness']['totalWallFaceAreaNetM2']}",
        "",
        "## Caveats",
    ]
    lines.extend(f"- {item}" for item in report["caveats"])
    lines.extend(["", "## Recommended Next Actions"])
    lines.extend(f"1. {item}" for item in report["recommendedNextActions"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an agent-readable IFC model report from snapshot and takeoff JSON.")
    parser.add_argument("--snapshot", required=True, help="IFC property snapshot JSON path")
    parser.add_argument("--takeoff", required=True, help="IFC takeoff JSON path")
    parser.add_argument("--json-output", required=True, help="Output JSON report path")
    parser.add_argument("--markdown-output", required=True, help="Output Markdown report path")
    parser.add_argument("--envelope", help="Optional result envelope JSON path")
    parser.add_argument("--request-id", help="Optional request identifier when no result envelope is available")
    parser.add_argument("--action", help="Optional action name when no result envelope is available")
    args = parser.parse_args()

    snapshot = read_json(Path(args.snapshot))
    takeoff = read_json(Path(args.takeoff))
    envelope = read_json(Path(args.envelope)) if args.envelope else None
    report = build_report(snapshot, takeoff, envelope, args.request_id, args.action)

    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    write_text(json_output, json.dumps(report, indent=2) + "\n")
    write_text(markdown_output, render_markdown(report))
    print(
        json.dumps(
            {
                "ok": True,
                "jsonOutput": str(json_output),
                "markdownOutput": str(markdown_output),
                "status": report["status"],
                "geometryLevel": report["geometryReadiness"]["geometryLevel"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
