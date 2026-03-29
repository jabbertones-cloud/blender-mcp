# V8 IMPROVEMENT CYCLE — TARGET 9.5/10
## Execution Plan for OpenClaw Forensic Animation System

### Current: v6 = 4.2/10 | Target: v8 = 9.5/10

---

## PHASE 1: Materials Revolution (Impact: +1.5)
### What changes:
- Replace flat-color Principled BSDF with multi-layer procedural node networks
- Asphalt: Voronoi cracking + Noise aggregate + Musgrave micro-roughness + color variation
- Vehicle paint: Procedural orange-peel micro-texture + clearcoat flake
- Glass: Proper IOR 1.52, thin-film interference tint, rain droplets normal map
- Rubber/tires: Dark with roughness variation, subtle tread pattern via Brick Texture
- Concrete curbs: Staining, aggregate, wear patterns
- Lane markings: Retroreflective bead geometry (Voronoi bump)

### Implementation: 
All procedural — no external texture files needed. Pure Blender node trees sent via run_py().

---

## PHASE 2: HDRI + Professional Lighting (Impact: +0.8)
### What changes:
- Download PolyHaven HDRI via bridge `polyhaven` command
- Scene-matched environments: suburban, urban, industrial, parking lot
- 3-point forensic lighting rig: key sun + fill (soft area) + rim (separation)
- Volumetric world fog for atmosphere depth
- Night scene: proper area lights for parking lot sodium vapor lamps

### Implementation:
Use existing `handle_polyhaven` and `handle_scene_lighting` functions through bridge.

---

## PHASE 3: Exhibit Standards System (Impact: +1.5)
### What changes:
- Auto-generate exhibit frame overlay on every render via compositor
- Scale bar with real-world measurements
- Exhibit reference number (1-A, 1-B format)
- "DEMONSTRATIVE AID — NOT DRAWN TO SCALE" disclaimer
- Case number placeholder watermark
- Compass/north arrow indicator
- Timestamp and version stamp

### Implementation:
Compositor-based overlay system — text rendered to image, composited onto final output.

---

## PHASE 4: Enhanced Vehicle Geometry (Impact: +1.0)
### What changes:
- Add headlight/taillight emissive geometry (proper lens shapes)
- Door panel lines via edge loops and bevel
- Windshield with proper curvature (not flat plane)
- Side mirrors with reflection capability
- Wheel rim detail (5-spoke pattern via boolean/array)
- Basic interior silhouette visible through glass

### Implementation:
Enhanced `_create_vehicle_v8()` function with 2000-4000 vertex vehicles.

---

## PHASE 5: Human Figure Upgrade (Impact: +0.5)
### What changes:
- Single continuous mesh (not disconnected primitives)
- Proper body proportions (anatomical ratios)
- Basic facial features (eye sockets, nose bridge, chin)
- Finger separation on hands
- Clothing color/texture distinction from skin
- Natural standing pose with weight shift

### Implementation:
New `_create_figure_v8()` using bmesh operations for topology.

---

## EXECUTION ORDER:
1. Write `portfolio_render_v8.py` with all Phase 1-3 improvements
2. Test render Scene 1 only (4 cameras) as proof-of-concept
3. If quality passes review, render all 4 scenes (16 renders)
4. Generate v8_thumb/ thumbnails for comparison
5. Write v8 quality re-assessment

## FILES TO CREATE:
- `scripts/v8_materials.py` — Procedural material library
- `scripts/v8_exhibit_overlay.py` — Forensic exhibit annotation system
- `scripts/v8_lighting.py` — Professional lighting rig presets
- `tests/portfolio_render_v8.py` — Main render orchestrator
- `blender_addon/v8_forensic_upgrades.py` — Addon patches
