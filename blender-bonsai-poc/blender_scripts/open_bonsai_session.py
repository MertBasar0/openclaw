#!/usr/bin/env python3
"""Open a Blender+Bonsai visual review session.

The session JSON is intentionally small: it points Blender at an IFC file and a
proposal JSON file.  Blender keeps the IFC loaded through Bonsai, draws proposal
highlights in a separate overlay collection, and hot-reloads the session/proposal
JSON while the UI is open.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import bpy

DEFAULT_COLLECTION = "OpenClaw Proposal Highlight Overlay"
DEFAULT_REFRESH_SECONDS = 1.0
SESSION_KIND = "blender-bonsai-session"

SEVERITY_COLOR = {
    "high": (1.0, 0.04, 0.02, 0.36),
    "medium": (1.0, 0.50, 0.00, 0.32),
    "low": (1.0, 0.88, 0.05, 0.28),
}
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def cli_args() -> list[str]:
    argv = sys.argv
    return argv[argv.index("--") + 1 :] if "--" in argv else argv[1:]


def arg_value(args: list[str], flag: str) -> str | None:
    if flag not in args:
        return None
    idx = args.index(flag)
    if idx + 1 >= len(args):
        raise ValueError(f"Missing value for {flag}")
    return args[idx + 1]


def flag_enabled(args: list[str], flag: str) -> bool:
    return flag in args


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} did not contain a JSON object")
    return payload


def resolve_path(base_dir: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base_dir / path).resolve()


def file_stamp(path: Path | None) -> tuple[int, int] | None:
    if not path or not path.exists():
        return None
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def enable_bonsai() -> None:
    for module in ("bl_ext.user_default.bonsai", "bonsai"):
        try:
            bpy.ops.preferences.addon_enable(module=module)
            print("Enabled addon:", module)
            return
        except Exception as exc:  # noqa: BLE001
            print("Could not enable", module, exc)


def object_ifc_identity(obj: bpy.types.Object) -> dict[str, str]:
    identity: dict[str, str] = {}
    if obj.name.startswith("Ifc") and "/" in obj.name:
        identity["class"] = obj.name.split("/", 1)[0]
    try:
        import bonsai.tool as tool

        entity = tool.Ifc.get_entity(obj)
        if entity is not None:
            identity["class"] = entity.is_a()
            identity["globalId"] = getattr(entity, "GlobalId", "") or ""
            identity["name"] = getattr(entity, "Name", "") or ""
    except Exception:  # noqa: BLE001
        pass
    if obj.get("ifc_class"):
        identity["class"] = str(obj["ifc_class"])
    if obj.get("ifc_global_id"):
        identity["globalId"] = str(obj["ifc_global_id"])
    return {key: value for key, value in identity.items() if value}


def normalize_target(value: Any) -> str:
    return str(value or "").strip()


def target_matches(identity: dict[str, str], target: str) -> bool:
    if not target:
        return False
    if target in identity.values():
        return True
    if target.startswith("Ifc") and identity.get("class") == target:
        return True
    return False


def severity_by_target(proposals: list[dict[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for proposal in proposals:
        target = normalize_target(proposal.get("target"))
        if not target:
            continue
        severity = str(proposal.get("severity") or "low")
        previous = result.get(target)
        if previous is None or SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(previous, 0):
            result[target] = severity
    return result


def overlay_material(severity: str) -> bpy.types.Material:
    material_name = f"OpenClaw proposal overlay {severity}"
    existing = bpy.data.materials.get(material_name)
    if existing:
        return existing
    color = SEVERITY_COLOR.get(severity, SEVERITY_COLOR["low"])
    mat = bpy.data.materials.new(material_name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Alpha"].default_value = color[3]
    mat.blend_method = "BLEND"
    mat.show_transparent_back = True
    return mat


def overlay_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def clear_overlay(collection: bpy.types.Collection) -> None:
    for obj in list(collection.objects):
        mesh = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def candidate_objects(collection_name: str) -> list[bpy.types.Object]:
    return [
        obj
        for obj in bpy.data.objects
        if obj.type == "MESH"
        and obj.name not in {collection_name}
        and not obj.get("openclaw_overlay")
        and object_ifc_identity(obj)
    ]


def build_overlay(
    proposals: list[dict[str, Any]], collection_name: str
) -> tuple[int, dict[str, str]]:
    collection = overlay_collection(collection_name)
    clear_overlay(collection)
    targets = severity_by_target(proposals)
    highlighted = 0
    matched: dict[str, str] = {}

    for source in candidate_objects(collection_name):
        identity = object_ifc_identity(source)
        severity = None
        matched_target = None
        for target, target_severity in targets.items():
            if target_matches(identity, target):
                if severity is None or SEVERITY_RANK.get(target_severity, 0) > SEVERITY_RANK.get(severity, 0):
                    severity = target_severity
                    matched_target = target
        if severity is None:
            continue

        overlay = source.copy()
        overlay.data = source.data.copy()
        overlay.animation_data_clear()
        overlay.name = f"OpenClaw overlay - {source.name}"
        overlay["openclaw_overlay"] = True
        overlay["openclaw_overlay_source"] = source.name
        overlay["openclaw_overlay_target"] = matched_target or ""
        overlay.data.materials.clear()
        overlay.data.materials.append(overlay_material(severity))
        overlay.show_in_front = True
        overlay.display_type = "TEXTURED"
        collection.objects.link(overlay)
        highlighted += 1
        if matched_target:
            matched[matched_target] = severity

    return highlighted, dict(sorted(matched.items()))


def render_text(doc: dict[str, Any], session: dict[str, Any]) -> str:
    proposals = doc.get("proposals") or []
    summary = doc.get("summary") or {}
    lines = [
        f"OPENCLAW BONSAI SESSION  {session.get('sessionId', '')}",
        f"IFC: {session.get('ifcPath')}",
        f"Proposals: {summary.get('proposalCount', len(proposals))}",
        "Overlay collection: separate read-only highlight objects",
        "Legend: HIGH=red  MEDIUM=orange  LOW=yellow",
        "=" * 72,
        "",
    ]
    if not proposals:
        lines.append("No proposals loaded.")
        return "\n".join(lines)
    for proposal in proposals:
        lines.append(f"[{str(proposal.get('severity', '')).upper()}] {proposal.get('id')}")
        lines.append(f"  target : {proposal.get('target')} / {proposal.get('field')}")
        lines.append(f"  change : {proposal.get('operation')}: {proposal.get('currentValue')} -> {proposal.get('proposedValue')}")
        lines.append(f"  why    : {proposal.get('rationale')}")
        lines.append("")
    return "\n".join(lines)


def show_text(doc: dict[str, Any], session: dict[str, Any]) -> None:
    text = bpy.data.texts.get("OpenClaw Bonsai Session") or bpy.data.texts.new("OpenClaw Bonsai Session")
    text.clear()
    text.write(render_text(doc, session))
    screen = getattr(bpy.context, "screen", None)
    if not screen:
        return
    candidates = [area for area in screen.areas if area.type != "VIEW_3D"]
    if not candidates:
        return
    area = min(candidates, key=lambda item: item.width * item.height)
    try:
        area.type = "TEXT_EDITOR"
        area.spaces.active.text = text
        area.spaces.active.show_word_wrap = True
    except Exception as exc:  # noqa: BLE001
        print("Could not show session text:", exc)


class SessionState:
    def __init__(self, session_path: Path, cli_ifc: str | None, cli_proposals: str | None) -> None:
        self.session_path = session_path
        self.cli_ifc = cli_ifc
        self.cli_proposals = cli_proposals
        self.session_stamp: tuple[int, int] | None = None
        self.proposals_stamp: tuple[int, int] | None = None
        self.loaded_ifc: Path | None = None
        self.session: dict[str, Any] = {}
        self.proposals_path: Path | None = None

    def load_session(self) -> dict[str, Any]:
        session = load_json(self.session_path)
        if session.get("kind") not in {None, SESSION_KIND}:
            raise ValueError(f"Unsupported session kind: {session.get('kind')}")
        base = self.session_path.parent
        if self.cli_ifc:
            session["ifcPath"] = self.cli_ifc
        if self.cli_proposals:
            session["proposalsPath"] = self.cli_proposals
        ifc_path = resolve_path(base, session.get("ifcPath"))
        proposals_path = resolve_path(base, session.get("proposalsPath"))
        if ifc_path is None:
            raise ValueError("Session is missing ifcPath")
        session["ifcPath"] = str(ifc_path)
        if proposals_path:
            session["proposalsPath"] = str(proposals_path)
        self.session = session
        self.proposals_path = proposals_path
        return session

    def load_ifc_if_needed(self) -> None:
        ifc_path = Path(str(self.session["ifcPath"]))
        if self.loaded_ifc == ifc_path:
            return
        if not ifc_path.exists():
            raise FileNotFoundError(f"IFC does not exist: {ifc_path}")
        bpy.ops.bim.load_project(filepath=str(ifc_path))
        self.loaded_ifc = ifc_path
        print("Loaded IFC through Bonsai:", ifc_path)

    def reload_if_needed(self, force: bool = False) -> float:
        session_stamp = file_stamp(self.session_path)
        session_changed = force or session_stamp != self.session_stamp
        if session_changed:
            self.session_stamp = session_stamp
            self.load_session()
            self.load_ifc_if_needed()

        proposals_stamp = file_stamp(self.proposals_path)
        proposals_changed = force or session_changed or proposals_stamp != self.proposals_stamp
        if proposals_changed:
            self.proposals_stamp = proposals_stamp
            doc = load_json(self.proposals_path) if self.proposals_path else {"proposals": []}
            overlay = self.session.get("overlay") or {}
            collection_name = str(overlay.get("collectionName") or DEFAULT_COLLECTION)
            highlighted, matched = build_overlay(doc.get("proposals") or [], collection_name)
            show_text(doc, self.session)
            print(f"SESSION_RELOAD highlighted={highlighted} matched={matched}")

        return float(self.session.get("refreshIntervalSeconds") or DEFAULT_REFRESH_SECONDS)


def main() -> int:
    args = cli_args()
    session_arg = arg_value(args, "--session")
    if not session_arg:
        print("No --session path provided")
        return 1

    enable_bonsai()
    session_path = Path(session_arg).expanduser().resolve()
    state = SessionState(
        session_path=session_path,
        cli_ifc=arg_value(args, "--ifc"),
        cli_proposals=arg_value(args, "--proposals"),
    )
    state.reload_if_needed(force=True)
    if flag_enabled(args, "--once"):
        return 0

    def hot_reload_timer() -> float:
        try:
            return state.reload_if_needed()
        except Exception as exc:  # noqa: BLE001
            print("SESSION_RELOAD_ERROR", f"{exc.__class__.__name__}: {exc}")
            return DEFAULT_REFRESH_SECONDS

    bpy.app.timers.register(hot_reload_timer, first_interval=float(state.session.get("refreshIntervalSeconds") or DEFAULT_REFRESH_SECONDS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
