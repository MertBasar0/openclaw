#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path('/mnt/c/Program Files/Blender Foundation/Blender 4.5/blender.exe')
OUT = ROOT / 'out'
DEFAULTS = {
    'ifcPath': OUT / 'sample_room.ifc',
    'ifcSnapshotPath': OUT / 'ifc_property_snapshot.json',
    'ifcTakeoffPath': OUT / 'ifc_takeoff_report.json',
    'modelReportJsonPath': OUT / 'ifc_model_report.json',
    'modelReportMarkdownPath': OUT / 'ifc_model_report.md',
    'blendPath': OUT / 'sample_room.blend',
    'sceneSnapshotPath': OUT / 'scene_snapshot.json',
    'sceneReportPath': OUT / 'scene_report.md',
}


def now_ms() -> int:
    return int(time.time() * 1000)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def win_path(path: Path) -> str:
    path = path.resolve()
    parts = path.parts
    if len(parts) >= 4 and parts[1] == 'mnt' and len(parts[2]) == 1:
        drive = parts[2].upper() + ':'
        rest = '\\'.join(parts[3:])
        return f'{drive}\\{rest}'
    distro = os.environ.get('WSL_DISTRO_NAME', 'Ubuntu')
    unc_path = str(path).replace('/', '\\')
    return f'\\\\wsl.localhost\\{distro}{unc_path}'


def run(cmd: list[Any]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(list(map(str, cmd)), text=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(
            'Command failed with code {code}: {cmd}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}'.format(
                code=completed.returncode,
                cmd=' '.join(map(str, cmd)),
                stdout=completed.stdout[-4000:],
                stderr=completed.stderr[-4000:],
            )
        )
    return completed


def blender_python(script: Path, *args: Any) -> subprocess.CompletedProcess[str]:
    if not BLENDER.exists():
        raise FileNotFoundError(f'Blender executable not found: {BLENDER}')
    return run([BLENDER, '-b', '--python', win_path(script), '--', *args])


def resolve_declared_path(base_dir: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def resolve_path(request: dict[str, Any], key: str) -> Path:
    artifacts = request.get('artifacts') or {}
    inputs = request.get('inputs') or {}
    value = artifacts.get(key) or inputs.get(key)
    return resolve_declared_path(ROOT, value) if value else DEFAULTS[key]


def response_path(request_path: Path, request: dict[str, Any]) -> Path:
    artifacts = request.get('artifacts') or {}
    value = artifacts.get('responsePath')
    if value:
        return resolve_declared_path(ROOT, value)
    return request_path.with_suffix('.result.json')


def validate_request(request: dict[str, Any]) -> None:
    required = ['kind', 'contractVersion', 'requestId', 'action', 'readOnly']
    missing = [k for k in required if k not in request]
    if missing:
        raise ValueError(f'Missing required request fields: {missing}')
    if request['kind'] != 'blender-bonsai-request':
        raise ValueError(f'Unsupported request kind: {request["kind"]}')
    if request['contractVersion'] != '0.1.0':
        raise ValueError(f'Unsupported contractVersion: {request["contractVersion"]}')
    if request['readOnly'] is not True:
        raise ValueError('Only readOnly=true requests are supported in this PoC')


def empty_geometry_summary() -> dict[str, Any]:
    return {
        'elementsWithRepresentation': 0,
        'elementsWithBodyRepresentation': 0,
        'elementsWithAxisRepresentation': 0,
        'representationContexts': {},
    }


def normalize_geometry_summary(geometry: Any) -> dict[str, Any]:
    if not isinstance(geometry, dict):
        return empty_geometry_summary()
    return {
        'elementsWithRepresentation': int(geometry.get('elementsWithRepresentation', 0) or 0),
        'elementsWithBodyRepresentation': int(geometry.get('elementsWithBodyRepresentation', 0) or 0),
        'elementsWithAxisRepresentation': int(geometry.get('elementsWithAxisRepresentation', 0) or 0),
        'representationContexts': dict(sorted((geometry.get('representationContexts') or {}).items())),
    }


def load_ifc_summary(snapshot_path: Path) -> dict[str, Any] | None:
    if not snapshot_path.exists():
        return None
    data = read_json(snapshot_path)
    summary = dict(data.get('summary') or {})
    summary['geometry'] = normalize_geometry_summary(summary.get('geometry'))
    return {
        'snapshotKind': data.get('kind'),
        'summary': summary,
        'diagnostics': data.get('diagnostics'),
    }


def load_takeoff_summary(takeoff_path: Path) -> dict[str, Any] | None:
    if not takeoff_path.exists():
        return None
    data = read_json(takeoff_path)
    summary = dict(data.get('summary') or {})
    summary['geometry'] = normalize_geometry_summary(summary.get('geometry'))
    return {
        'reportKind': data.get('kind'),
        'summary': summary,
        'diagnostics': data.get('diagnostics'),
    }


def load_model_report(report_path: Path) -> dict[str, Any] | None:
    if not report_path.exists():
        return None
    return read_json(report_path)


def build_model_report(
    ifc_snapshot_path: Path,
    ifc_takeoff_path: Path,
    model_report_json_path: Path,
    model_report_markdown_path: Path,
    envelope_path: Path | None = None,
    request_id: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    report_cmd = [
        sys.executable,
        ROOT / 'scripts/generate_model_report.py',
        '--snapshot',
        ifc_snapshot_path,
        '--takeoff',
        ifc_takeoff_path,
        '--json-output',
        model_report_json_path,
        '--markdown-output',
        model_report_markdown_path,
    ]
    if envelope_path:
        report_cmd.extend(['--envelope', envelope_path])
    if request_id:
        report_cmd.extend(['--request-id', request_id])
    if action:
        report_cmd.extend(['--action', action])
    run(report_cmd)
    return {
        'ifc': load_ifc_summary(ifc_snapshot_path),
        'takeoff': load_takeoff_summary(ifc_takeoff_path),
        'modelReport': load_model_report(model_report_json_path),
    }


def generate_ifc_outputs(
    ifc_path: Path,
    ifc_snapshot_path: Path,
    ifc_takeoff_path: Path,
    model_report_json_path: Path,
    model_report_markdown_path: Path,
    envelope_path: Path | None = None,
    request_id: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    blender_python(ROOT / 'scripts/extract_ifc_properties.py', '--input', win_path(ifc_path), '--output', win_path(ifc_snapshot_path))
    run([sys.executable, ROOT / 'scripts/generate_ifc_takeoff.py', '--input', ifc_snapshot_path, '--output', ifc_takeoff_path])
    return build_model_report(
        ifc_snapshot_path,
        ifc_takeoff_path,
        model_report_json_path,
        model_report_markdown_path,
        envelope_path,
        request_id,
        action,
    )


def detect_geometry_level(result: dict[str, Any]) -> str:
    geometry = ((result.get('ifc') or {}).get('summary') or {}).get('geometry') or {}
    return 'real-ifc-shape-representations' if geometry.get('elementsWithRepresentation', 0) > 0 else 'metadata-only'


def handle(request: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    action = request['action']
    warnings: list[str] = []
    options = request.get('options') or {}
    ifc_path = resolve_path(request, 'ifcPath')
    ifc_snapshot_path = resolve_path(request, 'ifcSnapshotPath')
    ifc_takeoff_path = resolve_path(request, 'ifcTakeoffPath')
    model_report_json_path = resolve_path(request, 'modelReportJsonPath')
    model_report_markdown_path = resolve_path(request, 'modelReportMarkdownPath')
    blend_path = resolve_path(request, 'blendPath')
    scene_snapshot_path = resolve_path(request, 'sceneSnapshotPath')
    scene_report_path = resolve_path(request, 'sceneReportPath')
    reuse_existing = bool(options.get('reuseExistingArtifactsIfPresent'))

    if action == 'create-ifc-sample':
        create_args = ['--output', win_path(ifc_path)]
        if bool((request.get('options') or {}).get('withGeometry')):
            create_args.append('--with-geometry')
        blender_python(ROOT / 'blender_scripts/create_minimal_ifc.py', *create_args)
        return {'created': {'ifcPath': str(ifc_path)}}, warnings

    if action == 'extract-ifc-properties':
        generate_if_missing = bool((request.get('inputs') or {}).get('generateIfMissing'))
        if reuse_existing and ifc_snapshot_path.exists() and ifc_takeoff_path.exists():
            warnings.append('Reused existing IFC snapshot/takeoff artifacts because reuseExistingArtifactsIfPresent=true.')
            return build_model_report(
                ifc_snapshot_path,
                ifc_takeoff_path,
                model_report_json_path,
                model_report_markdown_path,
                request_id=request.get('requestId'),
                action=action,
            ), warnings
        if not ifc_path.exists() and generate_if_missing:
            warnings.append('Input IFC was missing; generated the default minimal sample first.')
            blender_python(ROOT / 'blender_scripts/create_minimal_ifc.py', '--output', win_path(ifc_path))
        if not ifc_path.exists():
            raise FileNotFoundError(f'Input IFC does not exist: {ifc_path}')
        return generate_ifc_outputs(
            ifc_path,
            ifc_snapshot_path,
            ifc_takeoff_path,
            model_report_json_path,
            model_report_markdown_path,
            request_id=request.get('requestId'),
            action=action,
        ), warnings

    if action == 'ifc-demo':
        if reuse_existing and ifc_snapshot_path.exists() and ifc_takeoff_path.exists():
            warnings.append('Reused existing IFC snapshot/takeoff artifacts because reuseExistingArtifactsIfPresent=true.')
            return build_model_report(
                ifc_snapshot_path,
                ifc_takeoff_path,
                model_report_json_path,
                model_report_markdown_path,
                request_id=request.get('requestId'),
                action=action,
            ), warnings
        blender_python(ROOT / 'blender_scripts/create_minimal_ifc.py', '--output', win_path(ifc_path))
        return generate_ifc_outputs(
            ifc_path,
            ifc_snapshot_path,
            ifc_takeoff_path,
            model_report_json_path,
            model_report_markdown_path,
            request_id=request.get('requestId'),
            action=action,
        ), warnings

    if action == 'ifc-geometry-demo':
        if reuse_existing and ifc_snapshot_path.exists() and ifc_takeoff_path.exists():
            warnings.append('Reused existing IFC snapshot/takeoff artifacts because reuseExistingArtifactsIfPresent=true.')
            return build_model_report(
                ifc_snapshot_path,
                ifc_takeoff_path,
                model_report_json_path,
                model_report_markdown_path,
                request_id=request.get('requestId'),
                action=action,
            ), warnings
        blender_python(ROOT / 'blender_scripts/create_minimal_ifc.py', '--output', win_path(ifc_path), '--with-geometry')
        return generate_ifc_outputs(
            ifc_path,
            ifc_snapshot_path,
            ifc_takeoff_path,
            model_report_json_path,
            model_report_markdown_path,
            request_id=request.get('requestId'),
            action=action,
        ), warnings

    if action == 'scene-demo':
        blender_python(ROOT / 'blender_scripts/create_sample_scene.py', '--output', win_path(blend_path))
        blender_python(ROOT / 'blender_scripts/extract_scene_snapshot.py', '--input', win_path(blend_path), '--output', win_path(scene_snapshot_path))
        run([sys.executable, ROOT / 'scripts/generate_report.py', '--input', scene_snapshot_path, '--output', scene_report_path])
        scene_summary = read_json(scene_snapshot_path).get('scene') if scene_snapshot_path.exists() else None
        return {'scene': scene_summary}, warnings

    raise ValueError(f'Unsupported action: {action}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Handle a Blender+Bonsai PoC request envelope.')
    parser.add_argument('--request', required=True, help='Request JSON path')
    parser.add_argument('--response', help='Optional response JSON path override')
    args = parser.parse_args()

    request_path = Path(args.request).expanduser().resolve()
    request: dict[str, Any] | None = None
    started = now_ms()
    action = None
    rid = None
    response = None
    try:
        request = read_json(request_path)
        validate_request(request)
        action = request['action']
        rid = request['requestId']
        out_path = Path(args.response).expanduser().resolve() if args.response else response_path(request_path, request)
        result, warnings = handle(request)
        response = {
            'kind': 'blender-bonsai-result',
            'contractVersion': '0.1.0',
            'requestId': rid,
            'action': action,
            'ok': True,
            'readOnly': True,
            'generatedAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'execution': {
                'mode': 'local-headless-blender',
                'durationMs': now_ms() - started,
                'blenderPath': str(BLENDER),
                'ifcAuthoringRoute': 'IfcOpenShell pure Python API',
                'ifcTakeoffRoute': 'Snapshot-derived deterministic quantity report',
                'geometryLevel': detect_geometry_level(result),
            },
            'artifacts': {
                'requestPath': str(request_path),
                'responsePath': str(out_path),
                **{k: str(resolve_path(request, k)) for k in DEFAULTS},
            },
            'result': result,
            'warnings': warnings,
            'errors': [],
        }
        write_json(out_path, response)
        print(json.dumps({'ok': True, 'responsePath': str(out_path), 'result': result}, indent=2))
        return 0
    except Exception as exc:
        out_path = Path(args.response).expanduser().resolve() if args.response else (response_path(request_path, request) if request else request_path.with_suffix('.result.json'))
        response = {
            'kind': 'blender-bonsai-result',
            'contractVersion': '0.1.0',
            'requestId': rid or 'unknown',
            'action': action or 'unknown',
            'ok': False,
            'readOnly': True,
            'generatedAtUtc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'execution': {'mode': 'local-headless-blender', 'durationMs': now_ms() - started},
            'artifacts': {'requestPath': str(request_path), 'responsePath': str(out_path)},
            'result': None,
            'warnings': [],
            'errors': [{'type': exc.__class__.__name__, 'message': str(exc)}],
        }
        write_json(out_path, response)
        print(json.dumps({'ok': False, 'responsePath': str(out_path), 'error': str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
