# IFC Model Report

## Assessment

This PoC IFC model contains 25 quantified elements across 5 categories, 5 IFC classes, and 3 material hints. It reports 120.0 m2 slab area, 185.6 m2 wall face area (171.64 m2 net), 13.96 m2 opening area, and 49.7416 m3 total bbox volume within overall extents of 10.12 x 4.19 x 6.2 m. Real IFC shape coverage is present on 33 elements (33 body, 10 axis, with 6 boolean-cut bodies). Opening hosting is wired: 8 openings across 6 walls, 8 fillings linked, net wall face area 171.64 m2 (opening cut-out 13.96 m2). Diagnostics are currently empty.

## Model Summary

- Quantified elements: 25
- Extracted entities: 38
- Categories: {"door": 4, "furniture": 4, "slab": 3, "wall": 10, "window": 4}
- Classes: {"IfcDoor": 4, "IfcFurniture": 4, "IfcSlab": 3, "IfcWall": 10, "IfcWindow": 4}
- Materials: {"light_wood": 8, "soft_glass": 4, "warm_concrete": 13}

## Quantity Highlights

- slabAreaM2: 120.0
- wallFaceAreaM2: 185.6
- wallFaceAreaNetM2: 171.64
- wallOpeningAreaM2: 13.96
- openingAreaM2: 13.96
- totalBoundingBoxVolumeM3: 49.7416
- extents: 10.12 x 4.19 x 6.2 m

## Geometry Readiness

- hasRealShapeRepresentations: true
- elementsWithRepresentation: 33
- elementsWithBodyRepresentation: 33
- elementsWithAxisRepresentation: 10
- geometryLevel: real-ifc-shape-representations
- elementsWithBooleanBody: 6
- hasBooleanBodyCuts: true
- totalBooleanOperandChainLength: 8
- representationContexts: {"Model/Body/MODEL_VIEW": 33, "Plan/Axis/GRAPH_VIEW": 10}

## Hosting Readiness

- hasOpeningHosting: true
- wallsHostingOpenings: 6
- openingsHosted: 8
- fillingsHosted: 8
- openingsWithoutFilling: 0
- fillingsWithoutHost: 0
- totalWallOpeningAreaM2: 13.96
- totalWallFaceAreaNetM2: 171.64

## Caveats

- Quantities are deterministic PoC outputs derived from curated IFC dimensions/placements, not production BIM validation.
- Representation coverage only confirms the presence of basic IFC shape representations; it does not certify authoring correctness or downstream viewer compatibility.
- Wall bodies use IfcBooleanResult DIFFERENCE operands to subtract opening voids, but tessellated mesh validation against viewer renderers is not performed here.

## Recommended Next Actions

1. Validate boolean wall bodies in an external viewer (e.g. BlenderBIM/Bonsai) and tighten the void buffer once visual artefacts are ruled out.
1. Cross-check deterministic takeoff totals against geometry-derived quantities or native QTO extraction.
1. Expose model-report readiness flags in the queue/orchestrator so follow-up agents can branch without re-parsing raw JSON.
1. Add an external viewer validation pass for the multi-room sample before broadening the copilot surface.
