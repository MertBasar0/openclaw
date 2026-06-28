#!/usr/bin/env python3
"""Launch the interactive Blender+Bonsai proposal review session."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path("/mnt/c/Program Files/Blender Foundation/Blender 4.5/blender.exe")


def win_path(path: Path) -> str:
    path = path.resolve()
    parts = path.parts
    if len(parts) >= 4 and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper() + ":"
        rest = "\\".join(parts[3:])
        return f"{drive}\\{rest}"
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    unc_path = str(path).replace("/", "\\")
    return f"\\\\wsl.localhost\\{distro}{unc_path}"


def run(cmd: list[Any]) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(map(str, cmd)))
    return subprocess.run(list(map(str, cmd)), check=True, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True, type=Path)
    parser.add_argument("--ifc", type=Path, help="Override session ifcPath")
    parser.add_argument("--proposals", type=Path, help="Override session proposalsPath")
    parser.add_argument("--once", action="store_true", help="Load once and exit; useful for smoke checks.")
    args = parser.parse_args()

    if not BLENDER.exists():
        raise SystemExit(f"Blender executable not found: {BLENDER}")

    cmd: list[Any] = [
        BLENDER,
        "--python",
        win_path(ROOT / "blender_scripts/open_bonsai_session.py"),
        "--",
        "--session",
        win_path(args.session),
    ]
    if args.ifc:
        cmd.extend(["--ifc", win_path(args.ifc)])
    if args.proposals:
        cmd.extend(["--proposals", win_path(args.proposals)])
    if args.once:
        cmd.append("--once")
    run(cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
