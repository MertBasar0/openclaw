# IFC Model Report

## Assessment
This PoC IFC model contains 8 quantified elements across 5 categories, 5 IFC classes, and 3 material hints. It reports 24.0 m2 slab area, 58.0 m2 wall face area, 3.6 m2 opening area, and 10.548 m3 total bbox volume within overall extents of 6.12 x 4.19 x 3.0 m. No IFC body or axis shape representations were detected; this remains a metadata-only model. Diagnostics are currently empty.

## Model Summary
- Quantified elements: 8
- Extracted entities: 12
- Categories: {"door": 1, "furniture": 1, "slab": 1, "wall": 4, "window": 1}
- Classes: {"IfcDoor": 1, "IfcFurniture": 1, "IfcSlab": 1, "IfcWall": 4, "IfcWindow": 1}
- Materials: {"light_wood": 2, "soft_glass": 1, "warm_concrete": 5}

## Quantity Highlights
- slabAreaM2: 24.0
- wallFaceAreaM2: 58.0
- openingAreaM2: 3.6
- totalBoundingBoxVolumeM3: 10.548
- extents: 6.12 x 4.19 x 3.0 m

## Geometry Readiness
- hasRealShapeRepresentations: false
- elementsWithRepresentation: 0
- elementsWithBodyRepresentation: 0
- elementsWithAxisRepresentation: 0
- geometryLevel: metadata-only
- representationContexts: {}

## Caveats
- Quantities are deterministic PoC outputs derived from curated IFC dimensions/placements, not production BIM validation.
- Opening hosting, void relationships, and clash-aware wall/window/door semantics are not modeled in this slice.
- Representation coverage only confirms the presence of basic IFC shape representations; it does not certify authoring correctness or downstream viewer compatibility.
- This action is metadata-only: no IFC body or axis shape representations were detected.

## Recommended Next Actions
1. Use ifc-geometry-demo as the next controlled upgrade path when downstream agents need representation-aware BIM review.
1. Keep the current deterministic takeoff as the baseline contract and compare it against future geometry-derived quantities.
1. Expose model-report readiness flags in the queue/orchestrator so follow-up agents can branch without re-parsing raw JSON.
1. Expand the sample set beyond the single-room layout to cover multi-room or multi-storey cases before broadening the copilot surface.
