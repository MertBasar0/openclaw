#!/usr/bin/env python3
"""Show read-only IFC edit proposals inside Blender.

Loads an IFC model through Bonsai, then surfaces a proposal set produced by
``scripts/generate_edit_proposals.py`` in two ways:

1. Text: writes a readable proposal listing into a Blender Text datablock
   ("Edit Proposals") and, when a UI is available, flips a small editor area to
   the Text Editor so the listing is visible.
2. Colour: tints every object whose IFC class is referenced by a proposal using
   a severity colour (high=red, medium=orange, low=yellow) and switches the 3D
   viewport to Object colour shading.

This is a visualisation only - it never edits or saves the IFC model.
"""

import bpy
import json
import sys
from pathlib import Path

SEV_COLOR = {
    "high": (0.85, 0.10, 0.10, 1.0),
    "medium": (0.95, 0.55, 0.05, 1.0),
    "low": (0.90, 0.85, 0.10, 1.0),
}
SEV_RANK = {"low": 0, "medium": 1, "high": 2}


def get_arg(flag: str) -> str | None:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if flag in argv:
        idx = argv.index(flag)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def enable_bonsai() -> None:
    for mod in ("bl_ext.user_default.bonsai", "bonsai"):
        try:
            bpy.ops.preferences.addon_enable(module=mod)
            print("Enabled addon:", mod)
            return
        except Exception as exc:  # noqa: BLE001
            print("Could not enable", mod, exc)


def object_ifc_class(obj: bpy.types.Object) -> str | None:
    name = obj.name
    if name.startswith("Ifc") and "/" in name:
        return name.split("/", 1)[0]
    try:
        import bonsai.tool as tool

        entity = tool.Ifc.get_entity(obj)
        if entity is not None:
            return entity.is_a()
    except Exception:  # noqa: BLE001
        pass
    return None


def severity_by_class(proposals: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for p in proposals:
        target = str(p.get("target", ""))
        sev = str(p.get("severity", "low"))
        if not target.startswith("Ifc"):
            continue
        if target not in mapping or SEV_RANK.get(sev, 0) > SEV_RANK.get(mapping[target], 0):
            mapping[target] = sev
    return mapping


def colorize(proposals: list[dict]) -> tuple[int, dict[str, str]]:
    class_sev = severity_by_class(proposals)
    colored = 0
    for obj in bpy.data.objects:
        cls = object_ifc_class(obj)
        if not cls:
            continue
        sev = class_sev.get(cls)
        if sev:
            obj.color = SEV_COLOR[sev]
            colored += 1
    # Switch any 3D viewport to object-colour solid shading.
    screen = getattr(bpy.context, "screen", None)
    if screen:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                for space in area.spaces:
                    if space.type == "VIEW_3D":
                        space.shading.type = "SOLID"
                        space.shading.color_type = "OBJECT"
    return colored, class_sev


def render_text(doc: dict) -> str:
    proposals = doc.get("proposals", [])
    summary = doc.get("summary", {})
    lines = [
        f"IFC EDIT PROPOSALS  (count={summary.get('proposalCount', len(proposals))})",
        f"mode={doc.get('mode')}  readOnly={doc.get('readOnly')}  modelStatus={doc.get('modelStatus')}",
        "legend: HIGH=red  MEDIUM=orange  LOW=yellow",
        "=" * 60,
        "",
    ]
    if not proposals:
        lines.append("No edit proposals; model meets current checks.")
        return "\n".join(lines)
    for p in proposals:
        lines.append(f"[{str(p.get('severity', '')).upper()}] {p.get('id')}")
        lines.append(f"  target : {p.get('target')} / {p.get('field')}")
        lines.append(f"  change : {p.get('operation')}: {p.get('currentValue')} -> {p.get('proposedValue')}")
        lines.append(f"  why    : {p.get('rationale')}")
        lines.append("")
    return "\n".join(lines)


def show_text(doc: dict) -> None:
    name = "Edit Proposals"
    txt = bpy.data.texts.get(name) or bpy.data.texts.new(name)
    txt.clear()
    txt.write(render_text(doc))
    # Flip the smallest editor area to a Text Editor so the listing is visible.
    screen = getattr(bpy.context, "screen", None)
    if not screen:
        return
    candidates = [a for a in screen.areas if a.type not in {"VIEW_3D"}]
    if not candidates:
        return
    area = min(candidates, key=lambda a: a.width * a.height)
    try:
        area.type = "TEXT_EDITOR"
        space = area.spaces.active
        space.text = txt
        space.show_word_wrap = True
    except Exception as exc:  # noqa: BLE001
        print("Could not flip area to Text Editor:", exc)


def main() -> int:
    enable_bonsai()
    ifc_path = get_arg("--ifc")
    proposals_path = get_arg("--proposals")
    if not proposals_path:
        print("No --proposals path provided")
        return 1

    if ifc_path:
        try:
            bpy.ops.bim.load_project(filepath=ifc_path)
            print("Loaded IFC:", ifc_path)
        except Exception as exc:  # noqa: BLE001
            print("load_project failed:", exc)

    doc = json.loads(Path(proposals_path).read_text(encoding="utf-8"))
    proposals = doc.get("proposals", [])

    colored, class_sev = colorize(proposals)
    show_text(doc)

    print(f"PROPOSAL_VIZ colored={colored} classSeverity={class_sev}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
