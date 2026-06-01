#!/usr/bin/env python3
"""Derive deterministic, read-only IFC edit proposals from review artifacts.

This is the next stage after the read-only copilot review: it converts model
report, checklist and copilot review findings into a structured set of concrete,
machine-readable *proposed* edits. Nothing is applied here - every proposal
carries ``applied: false`` and the document carries ``mode: proposal-only`` so
the read-only safety contract of the PoC is preserved. Applying proposals would
be a separate, explicitly write-enabled stage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "0.1.0"

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def proposal(
    pid: str,
    category: str,
    target: str,
    operation: str,
    field: str,
    current_value: Any,
    proposed_value: Any,
    rationale: str,
    source: str,
    severity: str,
) -> dict[str, Any]:
    return {
        "id": pid,
        "category": category,
        "target": target,
        "operation": operation,
        "field": field,
        "currentValue": current_value,
        "proposedValue": proposed_value,
        "rationale": rationale,
        "source": source,
        "severity": severity,
        "requiresWrite": True,
        "applied": False,
    }


def metadata_proposals(review: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    missing = review.get("missing_metadata") or []
    for item in missing:
        text = str(item).lower()
        if "phase" in text:
            proposals.append(
                proposal(
                    pid="meta-project-phase",
                    category="metadata",
                    target="IfcProject",
                    operation="set-attribute",
                    field="Phase",
                    current_value=None,
                    proposed_value="Design Development",
                    rationale=f"Copilot review flagged: {item}.",
                    source="copilot-review.missing_metadata",
                    severity="medium",
                )
            )
        elif "author" in text:
            proposals.append(
                proposal(
                    pid="meta-owner-author",
                    category="metadata",
                    target="IfcOwnerHistory",
                    operation="set-attribute",
                    field="OwningUser.ThePerson.GivenName",
                    current_value=None,
                    proposed_value="Unassigned (requires author input)",
                    rationale=f"Copilot review flagged: {item}.",
                    source="copilot-review.missing_metadata",
                    severity="medium",
                )
            )
    return proposals


def quality_proposals(checklist: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for warning in checklist.get("warnings") or []:
        text = str(warning).lower()
        if "slab" in text:
            proposals.append(
                proposal(
                    pid="geom-add-slab",
                    category="geometry",
                    target="IfcSlab",
                    operation="add-element",
                    field="bodyRepresentation",
                    current_value=0.0,
                    proposed_value="Author a base slab covering the floor footprint.",
                    rationale=f"Checklist warning: {warning}.",
                    source="checklist.warnings",
                    severity="medium",
                )
            )
    for failed in checklist.get("failedChecks") or []:
        text = str(failed).lower()
        if "empty" in text:
            proposals.append(
                proposal(
                    pid="geom-populate-model",
                    category="geometry",
                    target="IfcProject",
                    operation="add-element",
                    field="spatialContainment",
                    current_value=0,
                    proposed_value="Add at least one storey with walls and a slab.",
                    rationale=f"Checklist failure: {failed}.",
                    source="checklist.failedChecks",
                    severity="high",
                )
            )
    return proposals


def hosting_proposals(model_report: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    hosting = model_report.get("hostingReadiness") or {}
    without_filling = int(hosting.get("openingsWithoutFilling") or 0)
    without_host = int(hosting.get("fillingsWithoutHost") or 0)
    if without_filling > 0:
        proposals.append(
            proposal(
                pid="host-fill-openings",
                category="hosting",
                target="IfcOpeningElement",
                operation="add-relationship",
                field="IfcRelFillsElement",
                current_value=without_filling,
                proposed_value=0,
                rationale=f"{without_filling} opening(s) have no door/window filling.",
                source="model-report.hostingReadiness.openingsWithoutFilling",
                severity="high",
            )
        )
    if without_host > 0:
        proposals.append(
            proposal(
                pid="host-attach-fillings",
                category="hosting",
                target="IfcElement",
                operation="add-relationship",
                field="IfcRelVoidsElement",
                current_value=without_host,
                proposed_value=0,
                rationale=f"{without_host} filling(s) are not hosted by a wall opening.",
                source="model-report.hostingReadiness.fillingsWithoutHost",
                severity="high",
            )
        )
    return proposals


def geometry_proposals(model_report: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    geometry = model_report.get("geometryReadiness") or {}
    if not geometry.get("hasRealShapeRepresentations") and int(
        geometry.get("elementsWithBodyRepresentation") or 0
    ) == 0:
        proposals.append(
            proposal(
                pid="geom-author-shapes",
                category="geometry",
                target="IfcProduct",
                operation="add-representation",
                field="Representation.Body",
                current_value="metadata-only",
                proposed_value="real-ifc-shape-representations",
                rationale="Model has no real body shape representations; only metadata is present.",
                source="model-report.geometryReadiness.hasRealShapeRepresentations",
                severity="high",
            )
        )
    return proposals


def build_document(
    source_path: Path,
    model_report: dict[str, Any],
    review: dict[str, Any],
    checklist: dict[str, Any],
) -> dict[str, Any]:
    proposals: list[dict[str, Any]] = []
    proposals.extend(metadata_proposals(review))
    proposals.extend(quality_proposals(checklist))
    proposals.extend(hosting_proposals(model_report))
    proposals.extend(geometry_proposals(model_report))

    proposals.sort(key=lambda p: (-SEVERITY_RANK.get(p["severity"], 0), p["id"]))

    counts: dict[str, int] = {}
    for p in proposals:
        counts[p["severity"]] = counts.get(p["severity"], 0) + 1

    return {
        "kind": "cad-bim-edit-proposal-set",
        "contractVersion": CONTRACT_VERSION,
        "mode": "proposal-only",
        "readOnly": True,
        "appliedAny": False,
        "sourceModelReport": str(source_path),
        "modelStatus": model_report.get("status"),
        "requestId": model_report.get("requestId"),
        "summary": {
            "proposalCount": len(proposals),
            "bySeverity": dict(sorted(counts.items())),
            "byCategory": _count_by(proposals, "category"),
        },
        "proposals": proposals,
    }


def _count_by(proposals: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in proposals:
        counts[p[key]] = counts.get(p[key], 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(doc: dict[str, Any]) -> str:
    lines = ["# IFC Edit Proposals", ""]
    lines.append(f"- Mode: {doc['mode']} (read-only; nothing applied)")
    lines.append(f"- Source model status: {doc.get('modelStatus')}")
    summary = doc["summary"]
    lines.append(f"- Proposals: {summary['proposalCount']}")
    if summary["bySeverity"]:
        sev = ", ".join(f"{k}: {v}" for k, v in summary["bySeverity"].items())
        lines.append(f"- By severity: {sev}")
    lines.append("")
    if not doc["proposals"]:
        lines.append("No edit proposals derived; model meets current checks.")
        return "\n".join(lines) + "\n"
    for p in doc["proposals"]:
        lines.append(f"## [{p['severity'].upper()}] {p['id']}")
        lines.append(f"- Target: `{p['target']}` / `{p['field']}`")
        lines.append(f"- Operation: {p['operation']}")
        lines.append(f"- Current: {p['currentValue']}")
        lines.append(f"- Proposed: {p['proposedValue']}")
        lines.append(f"- Rationale: {p['rationale']}")
        lines.append(f"- Source: `{p['source']}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-report", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--checklist", required=True, type=Path)
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    model_report = load_json(args.model_report)
    review = load_json(args.review)
    checklist = load_json(args.checklist)

    doc = build_document(args.model_report, model_report, review, checklist)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(doc), encoding="utf-8")

    print(json.dumps(doc["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
