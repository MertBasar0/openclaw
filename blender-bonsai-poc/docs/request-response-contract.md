# Blender+Bonsai Request/Response Contract v0

This slice turns the Blender+Bonsai PoC into an executor-style boundary similar to the previous SketchUp bridge, but without any paid/licensed desktop automation dependency.

## Request handler

```bash
python3 blender-bonsai-poc/scripts/handle_blender_bonsai_request.py \
  --request blender-bonsai-poc/samples/requests/ifc-demo.request.json
```

The handler writes a machine-readable response envelope to `artifacts.responsePath` or, if omitted, next to the request as `*.result.json`.
When artifact paths are relative, they are resolved from `blender-bonsai-poc/`.

## Supported actions

- `ifc-demo`
  - Create a minimal IFC sample.
  - Extract IFC entity/property snapshot JSON.
  - Generate a deterministic takeoff report from the extracted BIM dimensions and placements.
  - Generate an agent-readable model report in JSON + Markdown from the snapshot/takeoff outputs.
- `ifc-geometry-demo`
  - Create the same minimal IFC sample, but with simple IFC shape representations and object placements authored.
  - Extract representation/placement diagnostics into the JSON snapshot and takeoff summary.
  - Generate the same model report, now with geometry readiness signals populated from IFC shape coverage.
- `ifc-multiroom-demo`
  - Create a two-storey, four-room IFC sample with slabs, perimeter walls, partition walls, doors, windows, furniture, and hosted openings.
  - Defaults to `options.withGeometry=true`, authoring body/axis representations plus boolean wall cuts for openings.
  - Extract the same snapshot, takeoff, hosting, boolean geometry, and model report artifacts through the executor boundary.
- `create-ifc-sample`
  - Only create the IFC sample.
  - Optional `options.withGeometry=true` enables the same geometry authoring used by `ifc-geometry-demo`.
- `extract-ifc-properties`
  - Extract from an existing IFC file.
  - Optional `inputs.generateIfMissing=true` creates the default sample if input is missing.
- `scene-demo`
  - Run the original Blender `.blend` sample scene + scene snapshot + markdown report flow.

All actions require `readOnly: true`. The handler refuses non-read-only requests in this PoC.

## Envelope files

- Request schema: `contracts/blender-bonsai-request-envelope-v0.json`
- Result schema: `contracts/blender-bonsai-result-envelope-v0.json`
- Visual session schema: `contracts/blender-bonsai-session-v0.json`
- Sample request: `samples/requests/ifc-demo.request.json`
- Multi-room sample request: `samples/requests/ifc-multiroom-demo.request.json`
- Visual session sample: `samples/sessions/ifc-geometry-proposals.session.json`
- Sample response: `samples/responses/ifc-demo.result.json`

## Geometry levels

- `ifc-demo`
  - Metadata-only IFC: semantic elements + deterministic dimensions/locations + snapshot-derived takeoff.
- `ifc-geometry-demo` / `ifc-multiroom-demo`
  - Adds real IFC shape representations and placements using IfcOpenShell authoring APIs.
  - Current scope is intentionally narrow and deterministic:
    - slab: swept solid body from an explicit footprint polyline
    - walls: plan axis + wall body swept solid
    - door/window/furniture: rectangle-profile body extrusions
    - openings: rectangle-profile void extrusions hosted by walls
  - `ifc-multiroom-demo` expands this from the minimal one-room sample to a two-storey/four-room sample suitable for broader takeoff and reporting checks.

## New artifact

- `artifacts.ifcTakeoffPath`
  - Optional output path for the takeoff JSON report.
  - Default: `blender-bonsai-poc/out/ifc_takeoff_report.json`
- `artifacts.modelReportJsonPath`
  - Optional output path for the model report JSON artifact.
  - Default: `blender-bonsai-poc/out/ifc_model_report.json`
- `artifacts.modelReportMarkdownPath`
  - Optional output path for the model report Markdown artifact.
  - Default: `blender-bonsai-poc/out/ifc_model_report.md`

## Result shape

For `ifc-demo` and `extract-ifc-properties`, `result` now contains:

- `ifc`
  - Snapshot summary and diagnostics from `extract_ifc_properties.py`
- `takeoff`
  - Summary and diagnostics from `generate_ifc_takeoff.py`
- `modelReport`
  - Agent/human-readable assessment generated from snapshot + takeoff JSON
  - Includes model summary, quantity highlights, geometry readiness, caveats, prioritized next actions, and a natural-language assessment

For `ifc-geometry-demo` and `ifc-multiroom-demo`, the `ifc.summary.geometry` and `takeoff.summary.geometry` sections additionally report:

- how many extracted products have any representation
- how many have a `Model/Body/MODEL_VIEW` body
- how many have a `Plan/Axis/GRAPH_VIEW` axis
- per-context representation counts

Each extracted entity also now carries:

- `placement`
  - local placement type, full 4x4 matrix, translation, and basis axes
- `geometry`
  - `hasRepresentation`, `hasBodyRepresentation`, `hasAxisRepresentation`
  - per-representation context/type/item diagnostics

The takeoff summary includes:

- category/class/material counts
- aggregate bbox volume, footprint area, surface area
- wall face area, slab area, door/window opening area
- `modelExtentsM` for the overall sample envelope

The model report includes:

- `modelSummary`
  - quantified element count plus category/class/material distributions
- `quantityHighlights`
  - `slabAreaM2`, `wallFaceAreaM2`, `openingAreaM2`, `totalBoundingBoxVolumeM3`, `modelExtentsM`
- `geometryReadiness`
  - `hasRealShapeRepresentations`, body/axis counts, context map, normalized `geometryLevel`
- `caveats`
  - deterministic PoC and BIM-semantic limitations
- `recommendedNextActions`
  - ordered next steps for the CAD/BIM copilot PoC
- `naturalLanguageAssessment`
  - short orchestrator-ready summary suitable to show Mert directly

## Reuse mode

Sample requests now set `options.reuseExistingArtifactsIfPresent=true`.

- If the declared snapshot + takeoff artifacts already exist, the handler reuses them and regenerates only the model report layer.
- If they do not exist, the handler falls back to the normal Blender/IfcOpenShell authoring + extraction path.
- `readOnly: true` remains mandatory in both modes.

## Windows bridge integration

The existing queue runner now exposes `blender-bonsai-action`:

```bash
python3 windows-bridge-bootstrap/scripts/run-bridge-request.py \
  blender-bonsai-action \
  --payload-file windows-bridge-bootstrap/samples/blender-bonsai-action.payload.json
```

The bridge payload may be either:

- A full `blender-bonsai-request` envelope.
- A partial object with `action` plus optional `artifacts`, `inputs`, `options`, and `sourceKind`.

For partial payloads, the bridge handler fills in:

- `kind = blender-bonsai-request`
- `contractVersion = 0.1.0`
- `requestId = <bridge requestId>` when omitted
- `artifacts.responsePath = blender-bonsai-poc/out/bridge/<requestId>.result.json` when omitted

Bridge safety rule: `readOnly: true` stays mandatory whether the payload is full or partial.

## Native Bonsai visual session

The executor boundary remains headless. Interactive review is handled by a
separate visual session JSON so Blender can stay open and reload proposal state:

```bash
python3 blender-bonsai-poc/scripts/run_bonsai_session.py \
  --session blender-bonsai-poc/samples/sessions/ifc-geometry-proposals.session.json
```

Session contract:

- `kind = blender-bonsai-session`
- `ifcPath`
  - IFC model opened through Bonsai's native `bpy.ops.bim.load_project` route.
- `proposalsPath`
  - Proposal JSON generated by `generate_edit_proposals.py`.
- `refreshIntervalSeconds`
  - UI timer interval for session/proposal JSON hot-reload.
- `overlay.collectionName`
  - Blender collection used for generated highlight meshes.

Highlighting is read-only and separate from the Bonsai-loaded IFC objects:

- the source IFC objects are not recolored or saved
- each matched source mesh gets a duplicate overlay mesh in the configured collection
- overlay materials map proposal severity to transparent red/orange/yellow
- the text summary is rewritten into the `OpenClaw Bonsai Session` text datablock

`run_bonsai_session.py --once` runs the same loader path once and exits, which is useful for smoke checks when a UI session is not needed.

## Geometry quantity comparison

`validate_ifc_geometry_view.py` now emits geometry-derived quantity signals in its validation JSON:

- per shape `bboxM`, `bboxVolumeM3`, `bboxFootprintAreaM2`, `meshSurfaceAreaM2`, and `meshVolumeM3`
- summary totals for the same metrics
- category-level aggregates in `quantityByCategory`

`scripts/compare_geometry_takeoff.py` compares those geometry-derived quantities with the deterministic takeoff artifact:

```bash
python3 blender-bonsai-poc/scripts/compare_geometry_takeoff.py \
  --takeoff blender-bonsai-poc/samples/reports/ifc-multiroom-demo.takeoff.json \
  --geometry blender-bonsai-poc/out/ifc-multiroom-view-full.validation.json \
  --json-output blender-bonsai-poc/out/ifc-multiroom-geometry-comparison.json \
  --markdown-output blender-bonsai-poc/out/ifc-multiroom-geometry-comparison.md
```

The comparison artifact is intentionally review-oriented rather than a hard executor response field. Current multi-room behavior is good for coverage, slab footprint, wall/slab bbox volume, and wall mesh surface area, but reports `needs-review` for door/window/furniture bbox volume and host-wall net mesh volume. That keeps the read-only contract honest while the IFC representation authoring is still being tightened.

Next safe expansion:

1. Fix door/window/furniture representation scale so geometry-derived bbox quantities match deterministic takeoff.
2. Make host-wall boolean cuts reduce mesh volume consistently before replacing snapshot-derived wall quantities with geometry-derived quantities.
