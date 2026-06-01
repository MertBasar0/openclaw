#!/usr/bin/env python3
"""Emit a compact orchestration summary from a Blender+Bonsai bridge result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def as_bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def as_int(value: Any) -> int:
    return int(value) if isinstance(value, int | float) else 0


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def response_payload(envelope: dict[str, Any]) -> dict[str, Any]:
    output = envelope.get("output")
    if isinstance(output, dict):
        response = output.get("response")
        if isinstance(response, dict):
            return response
    return envelope


def build_summary(path: Path, envelope: dict[str, Any]) -> dict[str, Any]:
    response = response_payload(envelope)
    result = response.get("result") if isinstance(response.get("result"), dict) else {}
    model_report = result.get("modelReport") if isinstance(result.get("modelReport"), dict) else {}
    ifc = result.get("ifc") if isinstance(result.get("ifc"), dict) else {}
    takeoff = result.get("takeoff") if isinstance(result.get("takeoff"), dict) else {}

    geometry = model_report.get("geometryReadiness")
    if not isinstance(geometry, dict):
        geometry = ifc.get("summary", {}).get("geometry", {})
    hosting = model_report.get("hostingReadiness")
    if not isinstance(hosting, dict):
        hosting = takeoff.get("summary", {}).get("hosting", {})
    quantities = model_report.get("quantityHighlights")
    if not isinstance(quantities, dict):
        quantities = takeoff.get("summary", {}).get("totals", {})

    diagnostics = []
    for source in (model_report, ifc, takeoff):
        source_diagnostics = source.get("diagnostics")
        if isinstance(source_diagnostics, list):
            diagnostics.extend(source_diagnostics)

    has_real_shapes = as_bool(geometry.get("hasRealShapeRepresentations")) or (
        as_int(geometry.get("elementsWithBodyRepresentation")) > 0
    )
    has_hosted_openings = as_bool(hosting.get("hasOpeningHosting")) or (
        as_int(hosting.get("openingsHosted")) > 0
        and as_int(hosting.get("fillingsHosted")) > 0
    )
    has_boolean_cuts = as_bool(geometry.get("hasBooleanBodyCuts")) or (
        as_int(geometry.get("elementsWithBooleanBody")) > 0
    )

    return {
        "kind": "cad-bim-bridge-readiness-summary",
        "contractVersion": "0.1.0",
        "sourcePath": str(path),
        "requestId": response.get("requestId") or envelope.get("requestId"),
        "action": response.get("action"),
        "ok": bool(response.get("ok")) and not diagnostics,
        "readOnly": bool(response.get("readOnly")),
        "status": model_report.get("status") or response.get("status"),
        "routing": {
            "readyForReadOnlyCopilotReview": bool(response.get("ok")) and has_real_shapes,
            "readyForViewerValidation": bool(response.get("ok"))
            and has_real_shapes
            and has_hosted_openings,
            "readyForEditProposal": bool(response.get("ok"))
            and has_real_shapes
            and has_hosted_openings
            and has_boolean_cuts
            and not diagnostics,
        },
        "geometryReadiness": {
            "geometryLevel": geometry.get("geometryLevel"),
            "hasRealShapeRepresentations": has_real_shapes,
            "elementsWithBodyRepresentation": as_int(
                geometry.get("elementsWithBodyRepresentation")
            ),
            "hasBooleanBodyCuts": has_boolean_cuts,
            "elementsWithBooleanBody": as_int(geometry.get("elementsWithBooleanBody")),
        },
        "hostingReadiness": {
            "hasOpeningHosting": has_hosted_openings,
            "openingsHosted": as_int(hosting.get("openingsHosted")),
            "fillingsHosted": as_int(hosting.get("fillingsHosted")),
            "openingsWithoutFilling": as_int(hosting.get("openingsWithoutFilling")),
            "fillingsWithoutHost": as_int(hosting.get("fillingsWithoutHost")),
        },
        "quantityHighlights": {
            "slabAreaM2": quantities.get("slabAreaM2"),
            "wallFaceAreaM2": quantities.get("wallFaceAreaM2"),
            "wallFaceAreaNetM2": quantities.get("wallFaceAreaNetM2"),
            "wallOpeningAreaM2": quantities.get("wallOpeningAreaM2"),
            "totalBoundingBoxVolumeM3": quantities.get("totalBoundingBoxVolumeM3")
            or quantities.get("boundingBoxVolumeM3"),
        },
        "diagnosticCount": len(diagnostics),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    summary = build_summary(args.result_json, load_json(args.result_json))
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
