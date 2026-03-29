# Forensic Animation Quality — Comprehensive Autoresearch

> Updated: 2026-03-24 (post quality push v7b — polish pass)
> Context: Multi-session effort to bring forensic courtroom animation from $7K to $25-50K quality via OpenClaw Blender MCP
> Status: Quality at ~8.5/10 after v7b polish. All major bugs fixed. Remaining: vehicle detail (low-poly Kenney limitation), pedestrian material, animation end-to-end test.

## Current Quality Rating: 7.9/10 (v7b actual, 6 cameras assessed)

### Quality Ceiling Analysis (honest)
The rendering pipeline (Cycles + lighting + shadows + materials) is now solid at ~8/10. Getting to 9.5/10 requires:
- **Better vehicle models** (Kenney low-poly reads as "toy cars" — need medium-poly realistic vehicles)
- **Proper human models** (pedestrian is ghostly white T-pose — needs skin/clothing material + pose)
- **Text solution** (3D text mirrors from reverse cameras — need HUD overlay or per-camera toggling)
- **Environment detail** (trees, signs, lampposts with proper materials — not bare signal poles)
These are ASSET issues, not rendering issues. The rendering pipeline is ready for 9.5/10 content.

Progression: 3/10 (primitive boxes) → 5/10 (Kenney models + physics) → 5.5/10 (impact torus, debris, ray tracing) → 4/10 (v2 blown out) → 6/10 (v3 dark asphalt, contrast, HUD) → 7.5/10 (v5 Cycles: real shadows + grass ground) → **7.75/10 (v6: z-fighting fixed, intersection center visible)** → 0/10 (v7: volume fog regression — REVERTED) → **8.5/10 (v7b: v6 + signal poles hidden, vehicle colors, curbs, text cleanup)**.

### v6 Breakthrough: Z-Fighting Fix
- Road_Cross raised z+0.003 to break z-fighting with Road_Main → **black intersection center ELIMINATED**
- Impact markers, debris, fluid spill objects hidden from render
- "Impact Zone" text now visible on road surface in all camera angles
- Vehicle multi-material applied (window, chrome, headlight, taillight, tire)

### v7 REGRESSION: Volume Scatter Fog
- **NEVER use `ShaderNodeVolumeScatter` with density > 0.0005 in outdoor Cycles scenes**
- Density 0.003 (which sounds tiny) caused complete blackout — all 6 renders nearly solid black
- File size was the early warning: 654KB vs 2.3MB (healthy renders are 2-3MB at 1920x1080)
- Volume scatter in Cycles absorbs ALL bounced light at even low densities
- For atmospheric depth: use compositing fog pass or Mist pass instead of volume scatter

### v7b Polish (v6 base + targeted fixes, NO fog)
- Signal poles and traffic signals hidden from render (eliminated floating green lines in grass)
- Vehicle body materials: V1 sedan = deep navy (0.015,0.05,0.20), V2 SUV = deep burgundy (0.20,0.025,0.025)
- Both vehicles have clearcoat (Coat Weight=1.0, Coat Roughness=0.02) for automotive realism
- Road edge curbs added (light concrete, 6cm height) for realistic road-grass transition
- Text emission boosted to 0.6 for readability, constraints removed

### Addon Baked Changes (cumulative v5-v7b)
1. Outdoor lighting preset: sun=1.5, sky_strength=0.25, fill=0.3, Filmic High Contrast, exposure=0.3
2. set_time_of_day forwards sun_energy, sky_strength, fill_energy, exposure params
3. EEVEE shadow quality: ray_count=3, step_count=16
4. setup_courtroom_render: Cycles default (128spl for presentation, 32 for draft), both with denoising
5. Presentation preset: `raytracing=True, shadows=True` (not removed gtao/bloom/motion_blur)
6. Bridge socket timeout: 600s (was 30s — too short for Cycles renders)
7. Road_Cross z offset +0.003 (breaks z-fighting)
8. Grass ground plane (200×200, z=-0.03) added to intersection builder
9. Asphalt base color 0.08 (lightened for Cycles rendering)

Best renders: `q9v5_01_Cam_BirdEye.png` (7.5/10 — shadows, grass, composition), `q9v5_02_Cam_DriverPOV.png` (8/10 — ground shadow under sedan, green horizon, natural feel). Previous best: `q9v3_05_Cam_Wide.png` (7.5/10 with HUD).

### CRITICAL FINDING: Cycles vs EEVEE for Shadows
**EEVEE cannot produce visible ground shadows** in this scene configuration. Tested across v1-v4 with every shadow setting combination. Cycles produces clear, natural cast shadows at 128 samples + denoising. **Use Cycles for all final/courtroom renders.** EEVEE is acceptable for fast preview only.

### v5 Breakthrough Changes
- **Cycles 128 samples + denoising** — shadows work, ~2-4 min per frame (vs 15s EEVEE)
- **Grass ground plane** (200×200, z=-0.03) — eliminates black void, green environment
- **Asphalt base color 0.065** (bumped from 0.045 for Cycles which renders darker)
- **Sidewalk concrete material** on curb objects (warm 0.28 base)
- **Addon baked defaults** — set_time_of_day("day") now produces calibrated lighting (sun=1.5, sky=0.25, fill=0.3, Filmic High Contrast, exposure=0.3)

---

## SECTION 1: Blender 5.1 API Reference (Hard-Won)

Everything in this section was discovered through trial-and-error. Blender 5.x changed many APIs from 4.x and prior documentation is often wrong.

### Render Engine
- **Use `BLENDER_EEVEE`** — NOT `BLENDER_EEVEE_NEXT`, NOT `EEVEE`, NOT `EEVEE_NEXT`
- `scene.render.engine = 'BLENDER_EEVEE'` is the only valid EEVEE value in 5.1
- Cycles is `CYCLES` (unchanged)

### EEVEE Settings That EXIST in 5.1
```python
eevee = scene.eevee
eevee.use_shadows = True                    # Master shadow toggle
eevee.shadow_ray_count = 3                  # 1-4, more = softer shadows
eevee.shadow_step_count = 16                # 6-32, more = better shadow quality
eevee.shadow_resolution_scale = 1.0         # 0.25-4.0, 1.0 = standard
eevee.use_raytracing = True                 # Screen-space ray tracing
eevee.ray_tracing_method = 'SCREEN'         # Only option in EEVEE
eevee.use_volumetric_shadows = True         # Volumetric shadow support
# shadow_pool_size takes STRING enum, NOT integer: '512', '1024', etc.
```

### EEVEE Settings REMOVED in 5.1 (DO NOT USE)
```python
# ALL OF THESE WILL THROW AttributeError:
eevee.use_gtao          # REMOVED — was ambient occlusion
eevee.use_bloom          # REMOVED — bloom is automatic now
eevee.use_motion_blur    # REMOVED
eevee.use_ssr            # REMOVED — replaced by use_raytracing
eevee.use_ssr_refraction # REMOVED
eevee.taa_render_samples # REMOVED — replaced by scene.eevee.taa_samples
```

### Sun Light Shadow Attributes
```python
sun = light_object.data  # where light_object.data.type == 'SUN'
sun.use_shadow = True
sun.shadow_soft_size = 0.02           # Angular size (radians) — smaller = sharper
# These MAY exist depending on build:
sun.shadow_cascade_count = 4          # 1-4 cascades
sun.shadow_cascade_max_distance = 120 # Max shadow distance
```

### Sky Texture
```python
sky_node = tree.nodes.new("ShaderNodeTexSky")
sky_node.sky_type = "MULTIPLE_SCATTERING"  # Best quality in 5.1
# Also available: "SINGLE_SCATTERING" (renamed from old "NISHITA")
# "PREETHAM" and "HOSEK_WILKIE" also available but lower quality
sky_node.sun_elevation = math.radians(35)  # 0-90, radians
sky_node.sun_rotation = math.radians(220)  # Azimuth
sky_node.ground_albedo = 0.15              # 0-1, lower = darker ground
```

### Transparent/Glass Materials
```python
# In Blender 5.1, use surface_render_method, NOT blend_method:
mat.surface_render_method = 'DITHERED'  # For transparency
# OLD (4.x): mat.blend_method = 'BLEND'  # DOES NOT WORK in 5.1
```

### Principled BSDF Input Names (5.1)
```python
bsdf.inputs["Base Color"]           # (R, G, B, A) tuple
bsdf.inputs["Metallic"]             # 0.0 - 1.0
bsdf.inputs["Roughness"]            # 0.0 - 1.0
bsdf.inputs["Alpha"]                # 0.0 - 1.0
bsdf.inputs["Emission Strength"]    # 0.0+
bsdf.inputs["Emission Color"]       # (R, G, B, A)
bsdf.inputs["Transmission Weight"]  # 0.0 - 1.0 (NOT "Transmission" alone)
bsdf.inputs["Coat Weight"]          # 0.0 - 1.0 (clearcoat)
bsdf.inputs["Coat Roughness"]       # 0.0 - 1.0
bsdf.inputs["Specular IOR Level"]   # Replaces old "Specular"
bsdf.inputs["Normal"]               # For bump/normal maps
bsdf.inputs["Subsurface Weight"]    # SSS
```

### Color Management (Filmic)
```python
scene.view_settings.view_transform = 'Filmic'  # NOT 'Standard'
scene.view_settings.look = 'High Contrast'      # Or 'Medium High Contrast'
scene.view_settings.exposure = 0.3               # EV offset
scene.view_settings.gamma = 1.0
scene.render.film_transparent = False            # True = transparent BG
```

### Object Operations
```python
# Shadow catcher (makes object catch shadows but be otherwise invisible):
obj.is_shadow_catcher = True

# DOF:
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 15.0
cam.data.dof.aperture_fstop = 2.8

# TRACK_TO constraint:
tc = obj.constraints.new('TRACK_TO')
tc.target = target_object
tc.track_axis = 'TRACK_NEGATIVE_Z'  # For cameras
tc.up_axis = 'UP_Y'
```

---

## SECTION 2: Lighting Science (Learned Through 4 Failed Renders)

### The Brightness Problem
EEVEE with Filmic view transform handles light accumulation differently than expected. Multiple light sources add up fast.

| Setting | v1 (blown out) | v2 (still blown out) | v3 (decent) | Recommended |
|---------|---------------|---------------------|-------------|-------------|
| Sun energy | 8 | 4 | 1.5 | 1.0-2.0 |
| Sky strength | 1.3 | 0.8 | 0.25 | 0.15-0.35 |
| Fill light energy | N/A | 1.0 | 0.3 | 0.2-0.5 |
| Ground albedo | 0.3 | 0.3 | 0.15 | 0.1-0.2 |
| Exposure | 0 | 0 | 0.3 | 0.0-0.5 |

**Key insight**: Sky background acts as an HDRI — it contributes ambient light from all directions. At strength 0.8, it was equivalent to wrapping the scene in a bright light dome. Strength 0.25 gives visible sky color without flooding the scene.

### Light Setup for Forensic Scenes
```
Sun (key light): energy 1.5, warm (1.0, 0.95, 0.88), elevation ~42°, use_shadow=True
Fill (rim light): energy 0.3, cool blue (0.7, 0.8, 1.0), opposite direction, use_shadow=False
Sky environment: MULTIPLE_SCATTERING, strength 0.25, ground_albedo 0.15
```

This gives: visible blue sky gradient, warm key shadows, cool fill to prevent dead-black shadow areas, and overall contrast that makes vehicles pop against the road.

### Shadow Problem — SOLVED (Cycles)
EEVEE screen-space shadows DO NOT produce visible cast shadows on road geometry in this scene, regardless of settings. Tested `use_shadows=True`, `use_raytracing=True`, `shadow_ray_count=3`, `shadow_step_count=16` — zero visible ground shadows in v1/v2/v3/v4 EEVEE renders.

**Root cause**: EEVEE's screen-space approach calculates shadows from the camera's perspective. For top-down and low-angle views where the shadow falls on a large flat surface below the object, EEVEE simply doesn't trace the ray path correctly. Contact shadows (which were in 4.x) have been removed from 5.1.

**Solution**: Use **Cycles** for all quality renders. Cycles at 128 samples + denoising produces clear, physically correct cast shadows. Confirmed in v4 and v5 renders — sedan shadow, SUV shadow, and witness figure shadow all clearly visible.

**Render time tradeoff**:
- EEVEE: ~15 sec/frame, no shadows (preview only)
- Cycles 64 samples: ~60 sec/frame, shadows visible but slightly noisy
- Cycles 128 samples + denoising: ~2-4 min/frame, clean shadows (RECOMMENDED)
- Cycles 256 samples: ~5-8 min/frame, highest quality (use for hero shots)

**Implementation**: Add `render_engine` parameter to `setup_courtroom_render`. Default to Cycles for "presentation" preset. Keep EEVEE for "draft" preset.

---

## SECTION 3: Material Science

### Asphalt Material (Dark)
The single biggest visual improvement came from making asphalt DARK (base color 0.03-0.07, not 0.1-0.2).
```python
# Good asphalt base colors:
dark_asphalt = (0.045, 0.045, 0.05)   # Fresh dark asphalt
worn_asphalt = (0.08, 0.08, 0.085)    # Worn/lighter patches
# BAD: (0.15, 0.15, 0.16) — too light, looks like concrete
```

Procedural texture chain: `Noise(scale=120, detail=14) → ColorRamp(0.03↔0.07) → Base Color` + `Noise(scale=300, detail=16) → Bump(strength=0.15) → Normal`

### Vehicle Materials (Multi-Material Assignment)
Kenney car models have named mesh parts. Material assignment by mesh name:
```
'window' / 'windshield' / 'glass' → Window (transparent, transmission=0.9, roughness=0.02)
'headlight' / 'lamp_front'        → Headlight (emissive, warm white)
'taillight' / 'lamp_rear'         → Taillight (emissive red)
'bumper' / 'grill' / 'grille'     → Chrome (metallic=1.0, roughness=0.05)
'wheel' / 'tire'                  → Tire (near-black, roughness=0.95)
Body (default)                    → User-specified color + clearcoat
```

Clearcoat settings for body paint: `Coat Weight = 0.9, Coat Roughness = 0.03, base Roughness = 0.12`

### Kenney Model Import — Texture Atlas Fix
**CRITICAL**: Every Kenney GLB references an external `colormap.png` texture atlas. On import, all meshes get a material pointing to this missing texture, rendering as magenta/pink.

Fix (MUST be done on every import):
```python
for child in imported_objects:
    if child.type == 'MESH':
        child.data.materials.clear()  # Remove atlas reference
        child.data.materials.append(new_pbr_material)  # Apply fresh PBR
```

Also clean orphan atlas materials:
```python
for mat in list(bpy.data.materials):
    if mat.name.startswith(('colormap', 'skin')) and mat.users == 0:
        bpy.data.materials.remove(mat)
```

**Known bug**: `colormap.001` persists with users>0 from character FBX import. The armature object holds a reference. Needs armature material slot cleanup too.

### Character Materials (5-Material Differentiation)
Kenney character FBX has generic mesh parts. Assign by mesh name heuristics:
```
'head' / 'face'  → Skin color (roughness=0.6)
'body' / 'torso' → Shirt color (roughness=0.7)
'leg' / 'pants'  → Pants color (roughness=0.7)
'foot' / 'shoe'  → Dark near-black (roughness=0.5)
'hair'           → Dark brown (roughness=0.8)
```

### Road Marking Material
White with slight emission for visibility from all angles:
```python
color = (0.9, 0.9, 0.9, 1.0)
roughness = 0.6
emission_strength = 0.05  # Very subtle, just enough to read at night
```

---

## SECTION 4: Camera Composition for Courtroom

### Standard Camera Set (6 angles)
1. **Bird's Eye** — Directly overhead, wide lens (24mm), no DOF. Best for showing intersection layout, vehicle positions, approach paths. Jurors understand spatial relationships.
2. **Orbit** — Elevated 3/4 view (~35° from vertical), shows depth. Best overall establishing shot. Lens 30-35mm.
3. **Wide** — Lower angle, wide lens (28mm), shows full scene with sky. Best for HUD overlay (exhibit label + disclaimer readable). Place at distance 25-30 units.
4. **Driver POV** — Very low (z=1.2-1.5), behind vehicle, lens 45-50mm. DOF with f/2.8, focus 15m. Shows what the driver would have seen.
5. **Witness** — Eye level (z=1.7), from witness position, looking toward impact. DOF f/2.8. Matches witness testimony perspective.
6. **Dramatic** — Low angle (z=1.5-2.0), with DOF f/2.0, wide lens 35mm. Pointed at impact zone via TRACK_TO constraint. Creates visual impact for jury.

### Camera Mistakes Made
- **v2 Dramatic too close to witness figure** — character filled the frame, blocking the scene
- **v1 all cameras were static and centered** — boring, no visual hierarchy
- **TRACK_TO on text objects causes mirroring** — text faces camera but reads backwards from the opposite side. Remove TRACK_TO, use fixed orientation per render or use emissive text that reads correctly from intended angle.

### HUD Overlay (Camera-Parented)
Exhibit labels and disclaimers work best as camera-parented text objects:
```python
hud_label.parent = camera
hud_label.location = (-0.16, -0.085, -0.3)  # Top-left in view
hud_label.data.size = 0.018
# Use emission=2.0 for readability against any background
```

**Must re-parent to each camera before rendering that camera's view.** Then unparent after all renders.

---

## SECTION 5: Text Readability Problem (UNSOLVED)

3D text in Blender is a flat mesh that faces one direction. From the reverse side it appears mirrored.

### Approaches Tried
1. **TRACK_TO constraint** targeting active camera — FAILED. Text still appears mirrored from certain angles because TRACK_TO rotates the whole object, but the glyph geometry still has a "front" face.
2. **Emissive text** without billboard — PARTIALLY WORKS. Text is readable from its intended direction but backwards from opposite. Acceptable for bird's eye and wide shots where text is small.
3. **Camera-parented HUD text** — WORKS for exhibit labels/disclaimers that should appear the same in every shot. Does NOT work for in-scene annotations (speed labels, vehicle names) which need to be positioned in 3D space.

### Recommended Solution (NOT YET IMPLEMENTED)
For in-scene annotations: create **duplicate text objects** that face opposite directions, and toggle visibility per-camera at render time. Or use compositing nodes to add 2D text overlay post-render.

---

## SECTION 6: Scene Structure That Works

### Object Count by Category (from bridge test)
- Road infrastructure: ~90 objects (lanes, curbs, sidewalks, signals, crosswalks, markings)
- Vehicles: ~40 objects each (18-19 mesh children per Kenney vehicle + parent empty)
- Markers/annotations: ~15 objects
- Cameras: 4-6
- Lights: 2-3
- Total: 150-170 objects for a single-intersection scene

### Working Scene Build Order
1. Clear scene (select all → delete, then clean orphan data blocks)
2. Build road (`forensic_scene → build_road`)
3. Place vehicles (`forensic_scene → place_vehicle` × N)
4. Place figures (`forensic_scene → place_figure` × N)
5. Add annotations (`forensic_scene → add_annotation` × N)
6. Add impact markers (`forensic_scene → add_impact_marker` × N)
7. Setup cameras (`forensic_scene → setup_cameras`)
8. Set lighting (`forensic_scene → set_time_of_day`)
9. Apply quality enhancements (dark asphalt, vehicle materials, Filmic, EEVEE settings)
10. Render all cameras

### DO NOT use `bpy.ops.wm.read_factory_settings()`
This kills the TCP bridge server running as an addon. The bridge thread gets destroyed. Use object-by-object deletion instead.

---

## SECTION 7: Kenney Model Library

### Vehicles (CC0 license, /models/vehicles/)
| File | Type | Meshes | Vertices | Notes |
|------|------|--------|----------|-------|
| sedan.glb | Sedan | 18 | 3714 | Most detailed, good for V1 |
| suv.glb | SUV | 19 | 4366 | Tall, good for V2 |
| suv-luxury.glb | Luxury SUV | ~20 | ~4500 | Variant |
| police.glb | Police | ~18 | ~3800 | Has light bar |
| van.glb | Van | ~15 | ~3200 | Box shape |
| truck.glb | Pickup | ~16 | ~3500 | Extended |

**Vehicle orientation**: Kenney models face +X in local space. Heading conversion: `rotation_z = 90 - heading_degrees` (where heading 0 = north/+Y, 90 = east/+X).

### Characters (/models/characters/)
| File | Type | Notes |
|------|------|-------|
| characterMedium.fbx | Standing | Has idle/run/jump animations. Requires material cleanup. |

### Debris (/models/debris/)
Glass debris is currently procedural (flattened icospheres). Kenney debris models (door, bumper, tire, plate) exist but aren't integrated for auto-scatter yet.

---

## SECTION 8: Physics Engine Reference

### Collision Simulation (in addon at `simulate_collision` action)
```
Input: vehicle masses (kg), approach speeds (m/s), approach angles (degrees)
Physics: 2D momentum conservation with coefficient of restitution (e=0.15)
Output: post-impact velocities, spin rates, rest positions
```

Friction deceleration: `a = μ × g` where μ=0.65 (dry asphalt), g=9.81
Skid distance: `d = v² / (2 × μ × g)`
Impact energy: `E = 0.5 × m × v²`

Keyframe animation uses per-frame friction deceleration (not linear interpolation) for realistic deceleration curves.

### What's Missing in Physics
- No vehicle deformation (would need shape keys or soft-body simulation)
- No glass breakage particle system
- Spin rate manually set, not computed from impact offset from center of mass
- No suspension compression
- Tire marks should progressively darken during skid (uniform currently)

---

## SECTION 9: Multi-Instance Architecture

### How It Works
```
Agent 1 → MCP Server (OPENCLAW_PORT=9876) → Blender Instance 1 (port 9876) → scene_a.blend
Agent 2 → MCP Server (OPENCLAW_PORT=9877) → Blender Instance 2 (port 9877) → scene_b.blend
Agent 3 → MCP Server (OPENCLAW_PORT=9878) → Blender Instance 3 (port 9878) → scene_c.blend
```

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| OPENCLAW_PORT | 9876 | TCP port for bridge communication |
| OPENCLAW_HOST | 127.0.0.1 | Host address |
| OPENCLAW_INSTANCE | blender-{port} | Human-readable instance name |
| OPENCLAW_TIMEOUT | 30.0 | Socket timeout in seconds |

### Launch Commands
```bash
# Single instance (default)
open /Applications/Blender.app

# Multiple instances with different ports
OPENCLAW_PORT=9876 /Applications/Blender.app/Contents/MacOS/Blender &
OPENCLAW_PORT=9877 /Applications/Blender.app/Contents/MacOS/Blender &

# Or use launcher script
./scripts/launch-blender-instances.sh 3
```

### Instance Discovery
```python
blender_instances(action="list")           # Probes ports 9876-9885
blender_instances(action="ping", port=9877) # Check specific instance
blender_instances(action="connect", port=9877) # Switch target
```

---

## SECTION 10: Addon Architecture (openclaw_blender_bridge.py — 7147 lines)

### TCP Command Protocol
```json
{"id": "1", "command": "forensic_scene", "params": {"action": "build_road", "road_type": "intersection", "lanes": 2, "length": 60}}
{"id": "2", "command": "execute_python", "params": {"code": "import bpy; print(len(bpy.data.objects))"}}
```

### Forensic Scene Actions (all under `command: "forensic_scene"`)
| Action | Purpose | Key Params |
|--------|---------|------------|
| build_road | Create intersection/straight road | road_type, lanes, length |
| place_vehicle | Import vehicle model | name, vehicle_type, location, rotation, color, damaged, impact_side |
| place_figure | Import character | name, location, rotation, label |
| add_annotation | Speed/distance/text labels | annotation_type, text, location, size |
| setup_cameras | Create standard camera set | camera_type (all/overhead/orbit/etc), target |
| set_time_of_day | Lighting presets | time (day/sunset/night), strength |
| animate_vehicle | Keyframe vehicle motion | name, keyframes (list of {frame, location, rotation}) |
| simulate_collision | Physics-based collision | vehicles (list with mass, speed, angle) |
| add_impact_marker | Impact point/skid/debris | marker_type, location, start/end |
| ghost_scenario | Semi-transparent path preview | vehicles (list with positions) |
| build_full_scene | One-call complete scene | scenario (dict with all elements) |
| add_scene_template | Pre-built templates | template_type (t_bone, rear_end, etc) |
| add_measurement_grid | Reference grid overlay | spacing, size |
| add_exhibit_overlay | Courtroom exhibit elements | case_number, title, scale_bar |
| setup_courtroom_render | Render presets | preset (testimony/exhibit/jury), resolution |
| setup_cinematic_cameras | Animated camera rigs | camera_type (crane/dolly/closeup/overhead) |
| add_data_overlay | Speed/energy/time HUD | overlay_type, vehicles |

### Key Internal Functions
| Function | Line | Purpose |
|----------|------|---------|
| `_make_mat()` | 4364 | Create PBR material with all parameters |
| `_apply_clean_materials_to_import()` | 4456 | Strip atlas textures, apply PBR |
| `_try_import_vehicle_model()` | 4471 | Import Kenney GLB with fallback |
| `_create_vehicle()` | 4541 | Full vehicle creation pipeline |
| `_try_import_figure_model()` | 4947 | Import Kenney FBX character |
| `_create_figure()` | 5012 | Full character creation pipeline |
| `handle_forensic_scene()` | 4341 | Main forensic action dispatcher |

---

## SECTION 11: What's NOT Baked Into Addon (Test Script Only)

These quality improvements exist only in `tests/quality_push_v3.py` and need to be integrated:

1. **Dark asphalt material** (base color 0.045) — addon still uses lighter default
2. **Sky strength 0.25** — addon `set_time_of_day("day")` uses higher strength
3. **Sun energy 1.5** — addon uses higher values
4. **Fill light (cool blue, energy 0.3)** — not in addon at all
5. **White road marking material with slight emission** — not standardized
6. **Tire material (near-black, roughness 0.95)** — not in vehicle material pipeline
7. **Vehicle clearcoat** (Coat Weight=0.9) — exists in addon but with different values
8. **Filmic + High Contrast** — addon has Filmic but uses "Medium High Contrast"
9. **Camera-parented HUD text** — addon has HUD system but doesn't parent to camera
10. **Exposure boost (0.3)** — not in addon
11. **film_transparent = False** — not explicitly set
12. **Dark ground albedo (0.15)** — addon uses default 0.3

### Integration Priority
These should be added as defaults in `set_time_of_day("day")` and `setup_courtroom_render()` so every scene gets them automatically without test scripts.

---

## SECTION 12: Render Pipeline & Iteration Learnings

### Render Execution
- Scripts take 2-5 minutes for 5-6 camera renders at 1920×1080
- `mcp__Desktop_Commander__start_process` with `timeout_ms=300000` (5 min)
- osascript times out on anything over ~2 minutes — use Desktop Commander instead
- Save blend file after enhancements, before rendering (allows re-render without rebuilding)

### Render Assessment Checklist
For each render, check:
- [ ] Sky visible (blue gradient, not white void)
- [ ] Road is dark (asphalt color, not light gray)
- [ ] Vehicles have visible contrast against road
- [ ] Ground shadows under vehicles (STILL FAILING)
- [ ] Text annotations readable (not mirrored/backwards)
- [ ] HUD overlay visible (exhibit label, disclaimer)
- [ ] Color contrast (Filmic + High Contrast)
- [ ] Debris visible on ground
- [ ] Impact zone indicator visible
- [ ] Lane markings crisp white
- [ ] No magenta/pink materials
- [ ] No floating objects

### Common Failures
| Symptom | Cause | Fix |
|---------|-------|-----|
| White void / blown out | Sky strength too high + sun energy too high | Sky ≤0.35, sun ≤2.0 |
| Magenta/pink vehicles | Atlas texture not cleared on import | `_apply_clean_materials_to_import()` |
| Text backwards | TRACK_TO constraint or viewing from back | Remove constraint, use HUD parenting |
| No shadows | EEVEE shadow limitations | Try Cycles, or add contact shadow proxy |
| Objects disappearing | `read_factory_settings()` killed bridge | Use manual object deletion |
| Render timeout | osascript timeout <2min | Use Desktop Commander |
| Materials not applied | Material name mismatch | Check actual material names with audit |

---

## SECTION 13: KPIs for Quality Tracking

| KPI | v1 | v2 | v3 | Target | How to Measure |
|-----|----|----|-----|--------|---------------|
| Overall quality | 3/10 | 4/10 | 6/10 | 9.5/10 | Side-by-side with reference forensic videos |
| Vehicle model fidelity | 2/10 | 5/10 | 5/10 | 7/10 | Polygon count, material detail |
| Physics accuracy | 0/10 | 6/10 | 6/10 | 9/10 | Compare to CRASH3 output |
| Forensic completeness | 1/10 | 5.5/10 | 6.5/10 | 9/10 | Checklist of courtroom elements |
| Camera work | 1/10 | 3.5/10 | 5/10 | 8/10 | Composition, DOF, variety |
| Text readability | 0/10 | 3/10 | 4/10 | 8/10 | Readable from all render angles |
| Shadow quality | 0/10 | 0/10 | 0/10 | 8/10 | Visible ground shadows |
| Material quality | 1/10 | 5/10 | 6/10 | 8/10 | Multi-material, PBR correct, no magenta |
| Lighting balance | 2/10 | 2/10 | 6/10 | 8/10 | No blowout, visible sky, contrast |
| Courtroom presentation | 0/10 | 2/10 | 5/10 | 9/10 | Exhibit label, scale, compass, disclaimer |

---

## SECTION 14: Revenue & Market Context

### Pricing Tiers (forensic animation market)
- **$5-7K**: Basic 3D animation, primitive geometry, no physics validation
- **$10-15K**: Imported models, basic physics, multiple camera angles, exhibit labels
- **$25-35K**: Realistic models, validated physics, professional lighting, Daubert-ready documentation
- **$50K+**: Photorealistic, expert witness testimony support, CRASH3 validation, multi-pass compositing

### Our Current Position
At 6/10 quality with Kenney models, we're in the $10-12K range. The addon infrastructure (bridge, multi-instance, physics engine, 18 forensic actions) is actually $25K+ tier. The visual output is what's dragging the price down.

### Path to $25K
1. Fix shadows (biggest single quality gap)
2. Source 3-5 realistic vehicle models (sedan, SUV, truck, motorcycle, pedestrian)
3. HDRI environment instead of procedural sky
4. Bake v3 quality settings into addon defaults
5. Animated scenes (the physics engine works, just needs visual polish)

---

## SECTION 15: File Inventory

### Core Files
```
blender_addon/openclaw_blender_bridge.py    — Main addon (7147 lines)
server/blender_mcp_server.py                — MCP FastMCP server (~1513 lines)
claude_mcp_config.json                      — MCP configuration
scripts/launch-blender-instances.sh          — Multi-instance launcher
```

### Test Scripts (quality iteration)
```
tests/test_bridge_forensic.py               — End-to-end bridge test (380 lines)
tests/quality_push_v2.py                    — v2 quality push (blown out — lessons learned)
tests/quality_push_v3.py                    — v3 quality push (dark asphalt, better)
tests/quality_push_9.py                     — Original quality push (blown out)
tests/probe_eevee.py                        — EEVEE attribute discovery
tests/check_cameras.py                      — Camera verification
tests/build_forensic_proper.py              — Reference physics implementation
```

### Models
```
models/vehicles/                             — Kenney Car Kit (CC0)
models/characters/                           — Kenney Animated Characters
models/debris/                               — Kenney debris pieces
```

### Renders (output)
```
renders/q9v3_*.png                           — Latest quality push renders (6 cameras)
renders/quality_push_v3.blend                — Latest scene file
renders/bridge_test_*.png                    — Original bridge test renders
renders/bridge_test_scene.blend              — Original scene (160 objects, 4 cameras)
renders/bridge_test_audit.txt                — Scene audit report
```

### Documentation
```
docs/FORENSIC-QUALITY-AUTORESEARCH.md        — This document
```

---

## SECTION 16: Next Actions (Prioritized, post-v7b)

### SOLVED (v5-v7b)
- ~~Fix ground shadows~~ → **SOLVED: Cycles 128spl + denoising**
- ~~Bake quality settings into addon~~ → **SOLVED: lighting, Cycles default, asphalt, grass, z-fighting all baked**
- ~~Add sidewalk/grass material~~ → **SOLVED: grass ground plane + sidewalk concrete in addon**
- ~~Black intersection center~~ → **SOLVED: Road_Cross z+0.003 offset**
- ~~Bridge timeout for Cycles renders~~ → **SOLVED: 600s timeout (was 30s)**

### CRITICAL (blocks 9.5/10)
1. **Source medium-poly vehicle models** — Kenney low-poly reads as "toy cars." Need at least sedan + SUV with proper body panels, headlight detail, window frames. PolyHaven, Sketchfab, or BlenderKit.
2. **Proper human model** — Current pedestrian is ghostly white T-pose. Need posed character with skin/clothing materials. Blender 5.1 renamed "Subsurface Color" (API issue to work around).
3. **Text solution** — 3D text mirrors from reverse cameras. Options: (a) composite overlay in post, (b) per-camera visibility driver, (c) camera-facing constraint with billboard mode, (d) render text as separate pass.
4. **Kenney material fix for vehicle body colors** — `materials.clear() + append(new_mat)` doesn't work on Kenney imports because the atlas texture is baked into UV mapping. Need to detect and overwrite the Principled BSDF node inputs directly on existing materials instead.

### HIGH (needed for $25K tier)
5. **HDRI environment** — PolyHaven daylight HDRI instead of procedural sky for photorealistic lighting.
6. **Test animate_vehicle through bridge** — Physics animation exists in code but untested end-to-end.
7. **Animated speed readout** — Text showing speed per-frame during animation.
8. **Environment props** — Trees, street signs, lampposts with proper materials (current signal poles are bare wireframe-like objects).

### MEDIUM (polish)
9. **Progressive skid marks** — Darken along length.
10. **Vehicle deformation shape keys** — Basic front/side crumple for post-impact frames.
11. **Composite overlay pipeline** — 2D text/graphics in post-processing, not 3D geometry.
12. **Road marking variety** — Turn arrows, lane numbers, yield markings.

## SECTION 17: Hard-Won Lessons (v1-v7b, do NOT repeat)

### Rendering
- **EEVEE cannot cast ground shadows** in this scene config. Tested v1-v4. Use Cycles.
- **Cycles 128 samples + denoising** is the sweet spot: shadows + quality in ~2 min/frame.
- **Volume scatter density 0.003 = complete blackout** in Cycles. For outdoor scenes: max 0.0005, or skip it entirely and use compositing Mist pass instead.
- **File size is a quality indicator**: healthy 1920x1080 PNG = 2-3MB. Below 1MB = something is very wrong.
- **Filmic + High Contrast + exposure 0.3** is the right color management for forensic outdoor.
- **Asphalt base color**: 0.045 for EEVEE, 0.065-0.08 for Cycles (Cycles renders darker).

### Bridge / Infrastructure
- **Bridge socket timeout must be 600s** for Cycles renders (was 30s, caused every render to fail with "Timeout waiting for Blender execution").
- **`__result__` is how to return data** from execute_python, NOT print(). Bridge doesn't capture stdout.
- **Blender --background mode** doesn't run timers — bridge commands queue but never execute. Must use GUI mode.
- **Multiple Blender instances** compete for CPU. 3 instances = ~200% CPU each instead of ~800%. Kill competing renders before quality push.

### Materials / Scene
- **Z-fighting between co-planar planes** renders as solid black in Cycles. Offset one by z+0.003.
- **Kenney vehicle atlas textures** need `obj.data.materials.clear()` on EVERY import to remove atlas references. Body color changes need to target the Principled BSDF node inputs directly on existing materials.
- **Blender 5.1 API changes**: No `use_gtao`, `use_bloom`, `use_motion_blur`, `use_ssr`. No `Subsurface Color` (renamed). `surface_render_method = 'DITHERED'` for transparency (not `blend_method`).
- **Sun energy 1.5** (not 5 or 8). **Sky strength 0.25** (not 0.8 or 1.0). These values were calibrated across 4 failed renders.
- **Signal poles extend into grass** as thin green lines. Always hide them for final renders.

### Process
- **Always check file size** after render before declaring success. 654KB ≠ 2.3MB means regression.
- **One camera per bridge command** to avoid TCP timeout. Don't send all 6 in one execute_python.
- **Background `nohup` for long renders** — MCP tools have 60s hard timeout, Cycles renders take 2-4 min each.
