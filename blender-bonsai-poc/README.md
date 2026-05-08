# Blender + Bonsai BIM Read-Only PoC

SketchUp PoC lisans duvarına takıldığı için bu hat Blender/Bonsai eksenine taşındı.

Amaç: ücretsiz/açık kaynak bir CAD/BIM yüzeyi üzerinde agent mimarisini kanıtlamak:

1. Blender headless çalışır.
2. Minimal mimari sahne (`sample_room.blend`) oluşturulur.
3. Sahne read-only snapshot JSON'a çıkarılır.
4. Snapshot'tan Ceviz tarafında kısa inceleme raporu üretilir.
5. Bonsai/IfcOpenShell hattında ilk IFC/BIM slice'ı üretilir, property set'ler JSON'a çıkarılır, deterministik takeoff raporu ve agent-readable model report üretilir.
6. İstenirse aynı slice üzerinde kontrollü IFC body/axis geometry + placement authoring denenir.

## Blender sahne demo

```bash
python3 blender-bonsai-poc/scripts/run_blender_demo.py
```

Çıktılar:

- `blender-bonsai-poc/out/sample_room.blend`
- `blender-bonsai-poc/out/scene_snapshot.json`
- `blender-bonsai-poc/out/scene_report.md`

## IFC/BIM slice demo

```bash
python3 blender-bonsai-poc/scripts/run_ifc_demo.py
```

Çıktılar:

- `blender-bonsai-poc/out/sample_room.ifc`
- `blender-bonsai-poc/out/ifc_property_snapshot.json`
- `blender-bonsai-poc/out/ifc_takeoff_report.json`
- `blender-bonsai-poc/out/ifc_model_report.json`
- `blender-bonsai-poc/out/ifc_model_report.md`

Bu demo Blender 4.5 LTS'nin headless Python ortamında çalışan IfcOpenShell `0.8.5-post1` API'sini kullanır. Bonsai extension import edilebiliyor, fakat bu slice güvenilirlik için Bonsai UI/operator authoring yerine saf IfcOpenShell API ile semantik IFC + snapshot-derived takeoff üretir. Üretilen IFC'de:

- spatial hierarchy: `IfcProject -> IfcSite -> IfcBuilding -> IfcBuildingStorey`
- elementler: 1 `IfcSlab`, 4 `IfcWall`, 1 `IfcWindow`, 1 `IfcDoor`, 1 `IfcFurniture`
- `Pset_CevizPoC`: kategori, ölçü, konum, materyal ipucu ve read-only PoC bayrağı
- takeoff raporu: her eleman için `dimensionsM`, `locationM`, `bboxM`, `quantities`; özet olarak kategori toplamları, kaba hacim/alanlar ve model extents
- model report: agent/human-readable özet, geometry readiness, caveat listesi ve önerilen sonraki adımlar

## IFC geometry demo

```bash
python3 blender-bonsai-poc/scripts/handle_blender_bonsai_request.py \
  --request blender-bonsai-poc/samples/requests/ifc-geometry-demo.request.json
```

Bu varyant metadata-only IFC'yi korur ama ek olarak gerçek IFC representation/placement authoring dener:

- `IfcSlab`: explicit footprint + swept solid body
- `IfcWall`: plan axis + wall body swept solid
- `IfcDoor`, `IfcWindow`, `IfcFurniture`: rectangle-profile body extrusion
- `IfcOpeningElement`: rectangle-profile extrusion through wall thickness, hosted by wall via `IfcRelVoidsElement` and filled by window/door via `IfcRelFillsElement`
- Wall bodies hosting openings: `IfcBooleanResult` (DIFFERENCE) operands subtract wall-local void solids from the original swept solid; the wall body representation type flips from `SweptSolid` to `Clipping`.

Extractor artık her element için `placement`, `geometry` (içinde `bodyBoolean` alt-bloğu) ve `hosting` blokları üretir; özet içinde representation coverage'ın yanı sıra opening hosting istatistikleri (`wallsHostingOpenings`, `openingsHosted`, `fillingsHosted`) ve boolean body sayacı (`elementsWithBooleanBody`, `totalBooleanOperandChainLength`) görünür.
Takeoff her duvar için `wallFaceAreaM2`, `wallFaceAreaNetM2` ve `wallOpeningAreaM2` üretir; opening alanları host wall'dan deductible olarak çıkarılır.
Yeni report katmanı aynı machine JSON'ları okuyup hem JSON hem Markdown assessment üretir; opening hosting ve boolean cut varlığına göre caveats ve recommended next actions adapte olur.

Doğrulama örneği:

```bash
python3 - <<'PY'
import json
snapshot = json.load(open('blender-bonsai-poc/out/ifc_property_snapshot.json', encoding='utf-8'))
takeoff = json.load(open('blender-bonsai-poc/out/ifc_takeoff_report.json', encoding='utf-8'))
print(snapshot['summary'])
print(takeoff['summary']['totals'])
print('extents', takeoff['summary']['modelExtentsM'])
PY
```

Beklenen özet: `wall: 4`, `slab/window/door/furniture: 1`, toplam bbox hacmi `10.548 m3`, slab alanı `24.0 m2`, wall face area `58.0 m2`, model extents `6.12 x 4.19 x 3.0 m`, diagnostics boş.

`ifc-geometry-demo` çıktısı için ek hosting beklentileri: `IfcOpeningElement: 2`, takeoff totals'ta `wallFaceAreaNetM2: 54.4`, `wallOpeningAreaM2: 3.6`; takeoff/snapshot summary'lerinde `hosting.wallsHostingOpenings: 2`, `hosting.openingsHosted: 2`, `hosting.fillingsHosted: 2`.


## Request/response executor demo

```bash
python3 blender-bonsai-poc/scripts/handle_blender_bonsai_request.py \
  --request blender-bonsai-poc/samples/requests/ifc-demo.request.json
```

Bu demo request envelope alır, Blender headless + IfcOpenShell üzerinden IFC üretip property extraction yapar ve result envelope yazar. Detay: `docs/request-response-contract.md`.

Çıktılar:

- `blender-bonsai-poc/samples/responses/ifc-demo.result.json`
- `blender-bonsai-poc/samples/reports/ifc-demo.takeoff.json`
- `blender-bonsai-poc/samples/reports/ifc-demo.model-report.json`
- `blender-bonsai-poc/samples/reports/ifc-demo.model-report.md`
- `blender-bonsai-poc/out/request_ifc_demo.ifc`
- `blender-bonsai-poc/out/request_ifc_property_snapshot.json`
- `blender-bonsai-poc/samples/reports/ifc-geometry-demo.takeoff.json`
- `blender-bonsai-poc/samples/reports/ifc-geometry-demo.model-report.json`
- `blender-bonsai-poc/samples/reports/ifc-geometry-demo.model-report.md`

Not: örnek request dosyaları `options.reuseExistingArtifactsIfPresent=true` ile gelir. Bu sayede mevcut snapshot/takeoff JSON'larından report layer hızlıca yeniden üretilebilir; artifact yoksa handler normal Blender/IfcOpenShell yoluna döner.

## Durum

- Blender 4.5 LTS ile headless API doğrulandı.
- `bpy` tabanlı sahne/snapshot kontratı korunuyor.
- IFC tarafında ilk gerçek BIM semantic slice üretildi; property extraction ve deterministic takeoff script'i eklendi.
- Aynı slice üstüne küçük ama faydalı bir model report katmanı eklendi; orchestrator agent artık ham JSON parse etmeden kısa değerlendirme gösterebilir.
- Geometry spike eklendi: opt-in `ifc-geometry-demo` ile basit swept/profile representations ve deterministic placements yazılıyor.
- Geometry slice Windows bridge queue üzerinden uçtan uca smoke test edildi (2026-05-08): bridge wrapper `succeeded`, handler `ok=true`, geometry seviyesi `real-ifc-shape-representations`.
- Opening-host enrichment eklendi: `ifc-geometry-demo` artık `IfcOpeningElement` + `IfcRelVoidsElement` + `IfcRelFillsElement` ile pencere/kapı'yı duvarda hostluyor; extractor/takeoff/model report bu ilişkileri yüzeye çıkarıyor (net wall face area = 54.4 m², opening cut-out = 3.6 m²).
- Boolean cut eklendi: `north_wall` ve `south_wall` body'leri `IfcBooleanResult` DIFFERENCE ile wall-local void solid'leri üzerinden çıkartılıyor; wall body representation type `SweptSolid` → `Clipping`. Snapshot/takeoff/report `elementsWithBooleanBody`, `hasBooleanBodyCuts` ve operand chain uzunluğunu raporluyor (2 wall, 2 IfcBooleanResult, 2026-05-08 itibarıyla doğrulandı).
- Sonraki adım: multi-room/multi-storey sahne çeşitlendirmesi + dış viewer (Bonsai/BlenderBIM) doğrulaması.
