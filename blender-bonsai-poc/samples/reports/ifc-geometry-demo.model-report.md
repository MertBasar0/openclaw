# IFC Model Report

## Assessment
This PoC IFC model contains 8 quantified elements across 5 categories, 5 IFC classes, and 3 material hints. It reports 24.0 m2 slab area, 58.0 m2 wall face area, 3.6 m2 opening area, and 10.548 m3 total bbox volume within overall extents of 6.12 x 4.19 x 3.0 m. Real IFC shape coverage is present on 8 elements (8 body, 4 axis). Diagnostics are currently empty.

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
- hasRealShapeRepresentations: true
- elementsWithRepresentation: 8
- elementsWithBodyRepresentation: 8
- elementsWithAxisRepresentation: 4
- geometryLevel: real-ifc-shape-representations
- representationContexts: {"Model/Body/MODEL_VIEW": 8, "Plan/Axis/GRAPH_VIEW": 4}

## Caveats
- Quantities are deterministic PoC outputs derived from curated IFC dimensions/placements, not production BIM validation.
- Opening hosting, void relationships, and clash-aware wall/window/door semantics are not modeled in this slice.
- Representation coverage only confirms the presence of basic IFC shape representations; it does not certify authoring correctness or downstream viewer compatibility.

## Recommended Next Actions
1. Model hosted openings explicitly with IfcOpeningElement and wall void relationships.
1. Cross-check deterministic takeoff totals against geometry-derived quantities or native QTO extraction.
1. Expose model-report readiness flags in the queue/orchestrator so follow-up agents can branch without re-parsing raw JSON.
1. Expand the sample set beyond the single-room layout to cover multi-room or multi-storey cases before broadening the copilot surface.
