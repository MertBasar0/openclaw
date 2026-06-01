#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path('/mnt/c/Program Files/Blender Foundation/Blender 4.5/blender.exe')
OUT = ROOT / 'out'
IFC = OUT / 'sample_room.ifc'
SNAPSHOT = OUT / 'ifc_property_snapshot.json'
TAKEOFF = OUT / 'ifc_takeoff_report.json'


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
    parser = argparse.ArgumentParser(description='Run the Blender+Bonsai IFC demo.')
    parser.add_argument('--with-geometry', action='store_true', help='Author simple IFC geometry and placements.')
    args = parser.parse_args()

    if not BLENDER.exists():
        raise SystemExit(f'Blender executable not found: {BLENDER}')
    OUT.mkdir(parents=True, exist_ok=True)

    # Run inside Blender Python because Bonsai installs IfcOpenShell there on this machine.
    create_args = ['--', '--output', win_path(IFC)]
    if args.with_geometry:
        create_args.append('--with-geometry')
    run([
        BLENDER,
        '-b',
        '--python', win_path(ROOT / 'blender_scripts/create_minimal_ifc.py'),
        *create_args,
    ])
    run([
        BLENDER,
        '-b',
        '--python', win_path(ROOT / 'scripts/extract_ifc_properties.py'),
        '--', '--input', win_path(IFC), '--output', win_path(SNAPSHOT),
    ])
    run([
        sys.executable,
        ROOT / 'scripts/generate_ifc_takeoff.py',
        '--input', SNAPSHOT,
        '--output', TAKEOFF,
    ])

    print(f'Wrote {IFC}')
    print(f'Wrote {SNAPSHOT}')
    print(f'Wrote {TAKEOFF}')
    print(f'Geometry mode: {"enabled" if args.with_geometry else "disabled"}')
    print('Verify JSON summary with:')
    print(f'  python3 -m json.tool {SNAPSHOT} | head -80')


if __name__ == '__main__':
    main()
