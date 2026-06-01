#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path("/mnt/c/Program Files/Blender Foundation/Blender 4.5/blender.exe")
OUT = ROOT / "out"
IFC = OUT / "multiroom.ifc"
SNAPSHOT = OUT / "multiroom_property_snapshot.json"
TAKEOFF = OUT / "multiroom_takeoff_report.json"
REPORT_JSON = OUT / "multiroom_model_report.json"
REPORT_MD = OUT / "multiroom_model_report.md"


def win_path(path: Path) -> str:
    """Return a Windows-readable path for Blender.exe launched from WSL."""
    path = path.resolve()
    parts = path.parts
    if len(parts) >= 4 and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper() + ":"
        rest = "\\".join(parts[3:])
        return f"{drive}\\{rest}"
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    unc_path = str(path).replace("/", "\\")
    return f"\\\\wsl.localhost\\{distro}{unc_path}"


def run(cmd: list[object]) -> subprocess.CompletedProcess[bytes]:
    print("+", " ".join(map(str, cmd)))
    return subprocess.run(list(map(str, cmd)), check=True)


def require_output(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Expected output was not created: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Blender+Bonsai multi-room IFC demo.")
    parser.add_argument(
        "--with-geometry",
        action="store_true",
        help="Author IFC body/axis geometry and boolean opening cuts.",
    )
    args = parser.parse_args()

    if not BLENDER.exists():
        raise SystemExit(f"Blender executable not found: {BLENDER}")
    OUT.mkdir(parents=True, exist_ok=True)

    create_args = ["--", "--output", win_path(IFC)]
    if args.with_geometry:
        create_args.append("--with-geometry")
    run(
        [
            BLENDER,
            "-b",
            "--python",
            win_path(ROOT / "blender_scripts/create_multiroom_ifc.py"),
            *create_args,
        ]
    )
    require_output(IFC)
    run(
        [
            BLENDER,
            "-b",
            "--python",
            win_path(ROOT / "scripts/extract_ifc_properties.py"),
            "--",
            "--input",
            win_path(IFC),
            "--output",
            win_path(SNAPSHOT),
        ]
    )
    require_output(SNAPSHOT)
    run(
        [
            sys.executable,
            ROOT / "scripts/generate_ifc_takeoff.py",
            "--input",
            SNAPSHOT,
            "--output",
            TAKEOFF,
        ]
    )
    run(
        [
            sys.executable,
            ROOT / "scripts/generate_model_report.py",
            "--snapshot",
            SNAPSHOT,
            "--takeoff",
            TAKEOFF,
            "--json-output",
            REPORT_JSON,
            "--markdown-output",
            REPORT_MD,
            "--request-id",
            "blender-bonsai-multiroom-demo-001",
            "--action",
            "create-multiroom-ifc",
        ]
    )

    print(f"Wrote {IFC}")
    print(f"Wrote {SNAPSHOT}")
    print(f"Wrote {TAKEOFF}")
    print(f"Wrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Geometry mode: {'enabled' if args.with_geometry else 'disabled'}")
    print("Verify JSON summary with:")
    print(f"  python3 -m json.tool {TAKEOFF} | head -80")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
