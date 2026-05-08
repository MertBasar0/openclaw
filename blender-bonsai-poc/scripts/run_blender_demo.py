#!/usr/bin/env python3
import os
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path('/mnt/c/Program Files/Blender Foundation/Blender 4.5/blender.exe')
OUT = ROOT / 'out'
BLEND = OUT / 'sample_room.blend'
SNAPSHOT = OUT / 'scene_snapshot.json'
REPORT = OUT / 'scene_report.md'


def win_path(path: Path) -> str:
    """Return a Windows-readable path for Blender.exe launched from WSL."""
    path = path.resolve()
    parts = path.parts
    if len(parts) >= 4 and parts[1] == 'mnt' and len(parts[2]) == 1:
        drive = parts[2].upper() + ':'
        rest = '\\'.join(parts[3:])
        return f'{drive}\\{rest}'
    distro = os.environ.get('WSL_DISTRO_NAME', 'Ubuntu')
    unc_path = str(path).replace('/', '\\')
    return f'\\\\wsl.localhost\\{distro}{unc_path}'


def run(cmd):
    print('+', ' '.join(map(str, cmd)))
    return subprocess.run(list(map(str, cmd)), check=True)


def main():
    if not BLENDER.exists():
        raise SystemExit(f'Blender executable not found: {BLENDER}')
    OUT.mkdir(parents=True, exist_ok=True)
    run([BLENDER, '-b', '--python', win_path(ROOT / 'blender_scripts/create_sample_scene.py'), '--', '--output', win_path(BLEND)])
    run([BLENDER, '-b', '--python', win_path(ROOT / 'blender_scripts/extract_scene_snapshot.py'), '--', '--input', win_path(BLEND), '--output', win_path(SNAPSHOT)])
    run([sys.executable, ROOT / 'scripts/generate_report.py', '--input', SNAPSHOT, '--output', REPORT])
    print(f'Wrote {BLEND}')
    print(f'Wrote {SNAPSHOT}')
    print(f'Wrote {REPORT}')

if __name__ == '__main__':
    main()
