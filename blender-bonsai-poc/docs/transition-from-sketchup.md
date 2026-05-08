# Transition from SketchUp PoC

## Decision

SketchUp desktop automation is frozen because the useful automation surface (desktop app + Ruby startup/plugin API) is behind the paid desktop license/trial gate. The free SketchUp plan is web-oriented and does not give the automation surface this PoC needs.

## New target

Use Blender 4.5 LTS + Bonsai BIM:

- Blender gives a free, scriptable `bpy` API and reliable headless execution.
- Bonsai provides IFC/BIM semantics and IfcOpenShell in the Blender environment.
- The old SketchUp bridge/contract lessons remain useful, but the executor target changes.

## Current machine status

- Blender 4.5 LTS installed via winget.
- Bonsai `0.8.5-post1` Windows extension downloaded from Blender Extensions and installed into the user extension repo.
- Blender Python imports verified:
  - `ifcopenshell`: available
  - `bonsai`: available
  - legacy `blenderbim`: not expected / missing

## First verified slice

`python3 blender-bonsai-poc/scripts/run_blender_demo.py`

This creates a sample room `.blend`, extracts a read-only scene snapshot JSON, and generates a markdown report.

## Next slice

Add true IFC/BIM path:

1. Create or import a small IFC sample.
2. Use Bonsai/IfcOpenShell to extract IFC entity type, GlobalId, property sets, storey/space relations, and quantities.
3. Extend `scene_snapshot` with BIM fields without coupling Ceviz to Blender internals.
