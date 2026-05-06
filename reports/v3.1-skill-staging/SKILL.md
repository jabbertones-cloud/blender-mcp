---
name: blender-mcp
description: "OpenClaw Blender MCP — agentic 3D creation engine with ~85 tools, CADAM-style parametric bpy generation (PARAMETERS-block contract + slider-style apply_params loop), depsgraph-aware geometry, two-pass image→scene extraction, agent-loop orchestration (Planner-Actor-Critic), vision-as-a-judge GCS constraints, self-evolving skill recipes, and behavioral-drift monitoring. Use whenever Scott asks to build/render/animate/light/extract/iterate on a Blender scene, generate bpy code, tweak scene parameters without re-prompting the LLM, or work with HDRIs/PBR textures from Poly Haven/ambientCG/Sketchfab."
version: v3.1.0
contact: jabbertones-cloud
project_urls:
  github: https://github.com/jabbertones-cloud/blender-mcp
  docs: https://github.com/jabbertones-cloud/blender-mcp/tree/main/docs
tags: [blender, 3d, generative-design, geometry, parametric, cadam, agent-loop, vision-language, observability, self-evolving-skills]
---

# OpenClaw Blender MCP — Skill Guide v3.1.0

**This guide is the single source of truth for safe, effective use of the blender-mcp server. v3.1 adds the CADAM-style parametric workflow (generate/run/apply_params, image→scene, asset discovery) on top of the v3.0 security + agent-loop floor. Read the operational rules below before any Blender work in a new session.**

---

## Source of Truth

This skill file is the authoritative reference for:
1. Depsgraph geometry reads and the post-modifier rule
2. Undo invalidation and re-fetch patterns
3. bpy.ops O(n²) trap and raw-API alternatives
4. execute_python safety gating (Issue #201 RCE closure)
5. Agent-loop orchestration (Planner-Actor-Critic)
6. Vision-as-a-Judge constraint validation and GCS types
7. Scene-diff hallucination detection
8. Self-evolving skill recipes and mutation
9. Observability & behavioral-drift monitoring

**All other documentation (README.md, CHANGELOG.md, inline code docstrings) are secondary.** If you find a conflict, trust this file first.

---

## NEW: The Depsgraph Rule

**Rule**: Every geometry read (vertices, edges, faces, bounding box, normals) **after modifiers** must use the post-modifier evaluated mesh via depsgraph.

**Why**: `obj.data.vertices` reads the *base* mesh; modifiers (Subdivision, Array, Solidify, etc.) exist only in the depsgraph's evaluated object.

**Pattern — WRONG:**
```python
# Reading base mesh, ignoring modifiers
verts = obj.data.vertices
bbox = [min(v.co.x for v in verts), max(v.co.x for v in verts)]
# BUG: Array modifier adds 5 instances; you only see 1
```

**Pattern — RIGHT:**
```python
# Use evaluated_depsgraph_get helper from blender_addon/depsgraph_helpers.py
from blender_addon.depsgraph_helpers import evaluated_mesh

with evaluated_mesh(depsgraph, obj) as eval_mesh:
    verts = eval_mesh.vertices
    bbox = [min(v.co.x for v in verts), max(v.co.x for v in verts)]
    # OK: Array instances are included in eval_mesh
```

**References**: CGWire depsgraph export guide. See `blender_addon/depsgraph_helpers.py` (297 lines) for `evaluated_mesh()` contextmanager and `evaluated_bbox_world()`.

---

## NEW: The Undo Trap

The **undo trap** is a critical correctness issue in Blender scripting. **Rule**: After `bpy.ops.ed.undo()` or mode toggle (Edit ↔ Object), all `bpy.types.ID` references (objects, materials, meshes, etc.) become invalid pointers.

**Why**: Undo rewrites the entire scene state. References are dangling.

**Pattern — WRONG:**
```python
cube = bpy.data.objects["Cube"]
bpy.ops.ed.undo()
cube.location.x = 5  # CRASH: cube pointer is now invalid
```

**Pattern — RIGHT:**
```python
cube = bpy.data.objects["Cube"]
bpy.ops.ed.undo()
cube = bpy.data.objects["Cube"]  # Re-fetch by name
cube.location.x = 5  # OK
```

**Best Practice**: After any undo, re-fetch all object/mesh/material references by name or by iterating `bpy.data.*`.

---

## NEW: The bpy.ops O(n²) Trap

**Rule**: Each `bpy.ops.*` call triggers implicit view-layer updates. Calling it N times in a loop = O(n²) viewport overhead.

**Why**: `bpy.ops` is a UI operator wrapper; it syncs the entire view layer after each call.

**Pattern — WRONG:**
```python
for i in range(1000):
    bpy.ops.mesh.primitive_cube_add(location=(i, 0, 0))
    # 1000 × O(n) viewport sync = O(n²) hang
```

**Pattern — RIGHT:**
```python
for i in range(1000):
    mesh = bpy.data.meshes.new("Cube")
    obj = bpy.data.objects.new("Cube", mesh)
    scene.collection.objects.link(obj)
    obj.location = (i, 0, 0)
# Batch creation, one view-layer sync at end = O(n)
```

**Key APIs**: `bpy.data.meshes.new()`, `bpy.data.objects.new()`, `collection.objects.link()`, `scene.collection` — all skip `bpy.ops` and side-step the O(n²) trap.

---

## NEW: execute_python Safety (Issue #201)

**Rule**: `execute_python` is disabled by default. Opt in with `OPENCLAW_ALLOW_EXEC=1`. All code is AST-scanned before execution.

**Why**: Issue #201 identified RCE via `exec(code, {"os": os, ...})`. The os module was pre-imported.

**Gating**: Set environment variable `OPENCLAW_ALLOW_EXEC=1` to enable. Returns error `{error: "execute_python is disabled...", disabled_by_policy: true}` if off.

**AST Rejection List**: The following imports and builtins are rejected even if OPENCLAW_ALLOW_EXEC=1:
- `import os`, `subprocess`, `socket`, `shutil`, `requests`, `urllib`, `http`, `ctypes`, `multiprocessing`
- Builtins: `eval`, `exec`, `__import__`, `compile`, `open`

**Test Cases**:

REJECTED (even with OPENCLAW_ALLOW_EXEC=1):
```python
import os
os.system("rm -rf /")  # AST catch: os module forbidden
```

REJECTED:
```python
exec("print('hi')")  # AST catch: exec builtin forbidden
```

ACCEPTED (with OPENCLAW_ALLOW_EXEC=1):
```python
bpy.data.objects["Cube"].location.x = 5  # bpy API, no forbidden imports
print("OK")  # print is allowed
```

**Fallback**: Set `OPENCLAW_ALLOW_UNSAFE_EXEC=1` to bypass AST checks (deprecated; remove by v3.2).

**Module**: See `server/safety.py` (200 lines) for the AST checker.

---

## NEW: The Agent Loop — Planner-Actor-Critic

**Rule**: Agent orchestration follows a fixed state machine: Goal → Plan → (Act + Critique)* → Verify.

**Why**: This pattern ensures robust agentic loops: plan once, iterate on mutations, verify at the end.

**Flowchart**:
```
Goal (user request)
  ↓
Plan (blender_router_set_goal + blender_plan)
  ↓
Act (blender_act with up to 3 mutations)
  ├→ Critique (blender_critique) after each mutation
  ├→ If satisfied: proceed to Verify
  └→ If not satisfied: mutate and retry (max 3 times)
  ↓
Verify (blender_verify with GCS constraints)
  ↓
Done or rollback
```

**Tools**:
- `blender_router_set_goal` — register goal and context
- `blender_plan` — generate mutation steps
- `blender_act` — execute one mutation, return diff
- `blender_critique` — evaluate action against goal
- `blender_verify` — run GCS validation
- `blender_session_status` — inspect plan, mutations, snapshots

**Example: Cyberpunk Desk**

Goal: "Create a futuristic desk scene with 1 desk, 1 monitor, 1 chair. Desk width 2m."

1. **Set Goal**: `blender_router_set_goal` registers goal + user context
2. **Plan**: `blender_plan` → steps = [
   - Create Desk (box 2×0.8×0.75m)
   - Create Monitor (flat 0.6×0.4m)
   - Create Chair (pedestal + back + wheels)
   - Position monitor on desk
   - Position chair beside desk
   - Add material: metallic gray
   - Add lighting
   ]
3. **Act 1**: `blender_act` → Execute "Create Desk" → `blender_snapshot diff` shows new Cube + transforms
4. **Critique 1**: "Desk width OK (2.0m), but missing wheels. Continue."
5. **Act 2**: `blender_act` → Execute "Create Chair" → new Cylinder + transforms
6. **Critique 2**: "Chair placed, but overlaps desk by 0.3m. Mutate position."
7. **Act 3**: `blender_act` → Execute "Adjust Chair position" → move Chair.location.y += 0.5
8. **Critique 3**: "Looks good. Call Verify."
9. **Verify**: `blender_verify` → Check GCS constraints:
   - Chair `not_overlapping` Desk? ✓
   - Monitor `on_top_of` Desk? ✓
   - All objects `inside` scene bounds? ✓
10. **Done**: Scene matches goal.

**Max Mutations**: 3 per act cycle before forced Verify. If not satisfied, start new Plan.

---

## NEW: Vision-as-a-Judge + GCS Constraints

**Rule**: Constraint verification is two-tier: VLM judge first (qualitative), then GCS validation (quantitative).

**VLM Judge**: Claude vision evaluates the scene against the goal narrative. Examples:
- "Does the desk look professional and futuristic?"
- "Are the chair wheels inside the desk bounding box?"
- "Is the monitor centered on the desk?"

**GCS (Geometric Constraint System)**: 9 quantitative constraint types. See `server/verify.py` (546 lines).

| Constraint | Params | Example | Meaning |
|---|---|---|---|
| `on_top_of` | obj_a, obj_b, tolerance_cm | Monitor on_top_of Desk (5cm) | obj_a.bbox.min.z >= obj_b.bbox.max.z - tolerance |
| `inside` | obj_a, container_bounds | Desk inside scene bounds | bbox entirely within scene |
| `not_overlapping` | obj_a, obj_b, min_gap_cm | Chair not_overlapping Desk (10cm) | min distance >= min_gap |
| `clearance` | obj_a, obj_b, distance_cm | Monitor 50cm from Desk edge | center-to-center distance >= threshold |
| `facing` | obj_a, direction, tolerance_deg | Monitor facing +Y (5°) | normal vector within cone |
| `vertex_count_range` | obj_a, min, max | Cube vertex_count_range(8, 8) | len(mesh.vertices) in [min, max] |
| `triangulated` | obj_a | Desk triangulated | all faces have 3 vertices |
| `has_material` | obj_a, material_name | Monitor has_material "Glass" | material exists and is assigned |
| `axis_aligned` | obj_a, axis, tolerance_deg | Monitor axis_aligned Z (2°) | rotation around axis <= tolerance |

**Typical Flow**:
```python
# Planner proposes mutations
# Actor executes mutations
# Critic uses VLM: "Does the layout feel balanced?"
# Verify uses GCS: `not_overlapping`, `on_top_of`, `axis_aligned`
# If all GCS pass, return success
# If GCS fails, plan new mutation
```

---

## NEW: Scene-Diff Verification

**Rule**: Detect action hallucination via snapshot diff. Save before mutation, diff after, verify changes match the declared action.

**Tools**: `blender_snapshot save`, `blender_snapshot diff`, `blender_snapshot list`, `blender_snapshot clear`, `blender_snapshot get`

**Example Workflow**:

1. **Save Snapshot**: `blender_snapshot save name="desk_base"`
   - Stores scene state: object list, transforms, materials, geometry hashes

2. **Mutate**: `blender_act` → "Create Monitor and position it"
   - Internal: executes Blender operations

3. **Diff Snapshot**: `blender_snapshot diff base="desk_base"`
   - Returns:
   ```json
   {
     "added_objects": ["Monitor"],
     "modified_objects": [],
     "deleted_objects": [],
     "transform_deltas": {"Monitor": {"location.z": "+0.85m"}},
     "geometry_changes": []
   }
   ```

4. **Verify Action**: Compare declared action ("Create Monitor") to diff.
   - If diff shows "added Monitor" → action matches ✓
   - If diff shows no changes → hallucination (LLM claimed action but nothing happened) ✗
   - If diff shows unexpected changes → side-effect detection ✗

**Hallucination Detection**:
```python
# Critic checks: "I declared to add Monitor, but snapshot diff shows no added objects"
# → Hallucination detected. Retry mutation.
```

---

## NEW: Self-Evolving Skill Bank

**Rule**: Recipes are mutation templates stored in `.claude/skills/blender-mcp/recipes/`. Use `scripts/skill_evo.py` to replay, evaluate, mutate, and promote recipes.

**Recipe Structure**: `.claude/skills/blender-mcp/recipes/`
```
recipes/
  ├─ MANIFEST.json (registry of 5+ seed recipes)
  ├─ product-viz/
  │  ├─ recipe.json (steps, mutations, examples)
  │  └─ examples/ (before/after screenshots)
  ├─ forensic-accident/
  ├─ procedural-wood/
  ├─ cyberpunk-desk/
  └─ character-rigging/
```

**Recipe JSON Format**:
```json
{
  "name": "cyberpunk-desk",
  "description": "Create a futuristic desk scene with Monitor + Chair",
  "steps": [
    {
      "action": "Create Desk",
      "details": "Box primitive, 2m × 0.8m × 0.75m, material: metallic gray"
    },
    {
      "action": "Create Monitor",
      "details": "Plane, 0.6m × 0.4m, position on desk, add glass material"
    },
    {
      "action": "Create Chair",
      "details": "Pedestal + back, position 0.5m from desk"
    }
  ],
  "mutations": [
    {
      "id": "adjust-monitor-height",
      "description": "Move monitor up 5cm for ergonomics",
      "delta": {"Monitor.location.z": "+0.05m"}
    },
    {
      "id": "add-desk-legs",
      "description": "Replace desk box with box + 4 cylinders",
      "delta": {"Desk": "replace_with_template('desk-with-legs')"}
    }
  ]
}
```

**skill_evo.py CLI** (6 subcommands):

- `skill_evo.py replay <recipe>` — Execute a recipe step-by-step in Blender
- `skill_evo.py evaluate <recipe>` — Run VLM + GCS validation on recipe output
- `skill_evo.py mutate <recipe>` — Apply mutations and generate variants
- `skill_evo.py promote <recipe>` — Mark recipe as "production" in MANIFEST.json
- `skill_evo.py extract <scene>` — Convert current Blender scene to recipe.json
- `skill_evo.py status` — List recipes and promotion status

**Workflow**:
```bash
# 1. Create a scene manually in Blender
# 2. Extract to recipe
skill_evo.py extract /tmp/my-scene.blend → recipes/my-recipe/recipe.json

# 3. Evaluate recipe (VLM + GCS)
skill_evo.py evaluate recipes/my-recipe

# 4. Mutate recipe (generate variants)
skill_evo.py mutate recipes/my-recipe → recipes/my-recipe-v2/recipe.json

# 5. Evaluate v2
skill_evo.py evaluate recipes/my-recipe-v2

# 6. If v2 is better, promote
skill_evo.py promote recipes/my-recipe-v2
```

---

## NEW: Observability Quickstart

**Rule**: Enable OpenTelemetry tracing with `OPENCLAW_OTEL_ENABLED=1`. Monitor behavioral drift with `blender_drift_status`.

**Setup**:
```bash
export OPENCLAW_OTEL_ENABLED=1
export OPENCLAW_OTEL_ENDPOINT="http://localhost:4317"  # OTLP gRPC collector
python server/blender_mcp_server.py
```

**Features**:
- `@traced_tool` decorator on all tools (see `server/telemetry.py`, 274 lines)
- Scene-diff span attributes: `added_objects`, `deleted_objects`, `transform_deltas`
- W3C Trace Context for cross-service correlation

**Drift Monitoring** (see `server/drift_guard.py`, 305 lines):

- EMA behavioral drift score (β=0.9, cosine distance)
- Warn threshold: 0.3, Alert threshold: 0.5
- Tracks: action distribution, mutation success rate, constraint violations

**Tool**: `blender_drift_status`
```json
{
  "drift_score": 0.24,
  "status": "nominal",
  "ema_history": [0.10, 0.12, 0.15, 0.18, 0.20, 0.22, 0.24],
  "mutation_success_rate": 0.87,
  "constraint_violations_pct": 2.1,
  "recent_actions": ["create_object", "transform", "apply_material"],
  "recommendation": "Continue current trajectory"
}
```

**Interpretation**:
- drift_score < 0.3: nominal, trust current behavior
- 0.3 ≤ drift_score < 0.5: investigate (warn)
- drift_score ≥ 0.5: alert, consider checkpoint/replan

---

## NEW: Tool Taxonomy (~80 tools)

| Category | Count | Tools |
|---|---|---|
| Agent Loop | 6 | blender_router_set_goal, blender_plan, blender_act, blender_critique, blender_verify, blender_session_status |
| Spatial | 4 | blender_spatial, blender_semantic_place, blender_dimensions, blender_floor_plan |
| Extended Tools | 9 | blender_camera_advanced, blender_uv_unwrap, blender_texture_bake, blender_lod, blender_vr_optimize, blender_gaussian_splat, blender_grease_pencil, blender_snapshot, blender_drift_status |
| Scene Management | 5 | get_scene_graph, set_scene_properties, list_collections, manage_collection, export_scene |
| Object Operations | 8 | add_object, delete_object, duplicate_object, rename_object, parent_object, set_transform, get_object_data, batch_transform |
| Geometry | 7 | extrude, inset, bevel, subdivide, decimate, remesh, geometry_nodes |
| Materials & Rendering | 6 | add_material, set_material_properties, add_texture, set_shade_smooth, render_viewport, render_final |
| Modifiers | 5 | add_modifier, remove_modifier, set_modifier_strength, apply_modifier, modifier_stack |
| Animation | 4 | insert_keyframe, set_keyframe_range, easing, dope_sheet |
| UV & Texturing | 6 | unwrap_uv, pack_uv, set_uv_layer, texture_paint, bake_texture, create_material_preview |
| Constraints | 4 | add_constraint, remove_constraint, target_constraint, constraint_influence |
| Lighting | 5 | add_light, set_light_properties, light_linking, volumetric, shadow_catcher |
| Camera | 4 | add_camera, set_camera_properties, depth_of_field, camera_tracking |
| Rendering | 5 | set_render_engine, set_render_settings, compositor, denoiser, light_bake |
| Import/Export | 6 | import_file, export_file, usd_import, gltf_import, fbx_import, obj_import |
| Geometry Scripting | 4 | execute_python, bmesh_ops, kdtree, math_utils |
| File & Project | 4 | save_file, load_file, save_incremental, project_management |
| VFX & Simulation | 5 | smoke_sim, fluid_sim, particle_system, cloth_sim, rigid_body |
| Performance | 3 | viewport_optimize, memory_profile, batch_render |
| Data & Analysis | 3 | scene_analyze, export_metadata, statistics |
| **CADAM Parametric (v3.1)** | **5** | **blender_generate_bpy_script, blender_run_bpy_script, blender_apply_params, blender_reference_image_to_scene, blender_list_available_assets** |

Total: ~85 tools across 24 categories.

---

## NEW (v3.1): CADAM-style Parametric Workflow

**Rule**: When generating bpy code, prefer the parametric pair `blender_generate_bpy_script` → `blender_run_bpy_script` over `blender_execute_python`. Tweak parameters via `blender_apply_params` instead of regenerating the script. Discover already-cached assets via `blender_list_available_assets` before downloading new ones. For image-driven scenes, use the two-pass `blender_reference_image_to_scene`.

**Why**: This is the design pattern from CADAM (Claude + OpenSCAD WASM): the LLM is called **once per intent**, never once per slider drag. Every numeric literal that affects geometry, materials, lighting, or camera lives in a fenced `# --- PARAMETERS ---` block at the top of the script. Subsequent tweaks edit only that block via `ast.literal_eval` round-trip — no token cost, no regeneration, no chance of the model accidentally changing something else. Empirically also more reliable for image inputs: image → structured JSON → bpy beats image → bpy in one shot.

### Tool surface

| Tool | What it does | When to call |
|---|---|---|
| `blender_generate_bpy_script(intent, reference_params?)` | Returns the contract: system prompt + PARAMETERS template + (optional) seed values from a prior image extraction. **Read-only**, no Blender call. | First step of any new bpy generation. |
| `blender_run_bpy_script(script, cache=True, require_parameters_block=True)` | AST-validates the script server-side, parses the PARAMETERS block, caches under a `script_id` (LRU, max 32), then sends to the addon for execution. | After authoring the script per the contract. |
| `blender_apply_params(script_id, new_values, rerun=True)` | Rewrites only the PARAMETERS block of a cached script with `new_values` and re-runs. **Zero LLM tokens.** | Every parameter tweak (FOV, light energy, roughness). |
| `blender_list_cached_scripts()` | Diagnostic — lists `script_id`s in the LRU cache. | When picking a target for `apply_params` after a long session. |
| `blender_reference_image_to_scene(action, ...)` | Three-action two-pass tool: `extraction_prompt` → `submit_extraction` → `build_seed_params`. | Image-driven scene work. |
| `blender_list_available_assets(providers?, asset_types?, refresh?)` | Walks Poly Haven / ambientCG / Sketchfab / Hyper3D / Hunyuan3D / local cache dirs (`OPENCLAW_ASSET_CACHE` env, `~/.openclaw/assets/`, repo `assets/` and `cache/`). Groups files by id (strips `_1k/_2k/_4k/_8k` and PBR channel suffixes). | **Before** any HDRI / PBR-texture-loading code. |

### The PARAMETERS-block contract (HARD)

Every script that goes through `blender_run_bpy_script` (with the default `require_parameters_block=True`) must look like this:

```python
# --- PARAMETERS ---
CUBE_SIZE = 2.0
LIGHT_ENERGY = 800.0
CAM_FOV_DEG = 50.0
MAT_ROUGHNESS = 0.45
HDRI_ID = "kiara_1_dawn"
RENDER_SAMPLES = 128
# --- /PARAMETERS ---

import bpy
# ... build the scene using the constants above ...
__result__ = {"summary": "..."}
```

**The marker tokens are exact.** Open with `# --- PARAMETERS ---` (six characters: hash, space, three dashes, space, the literal word PARAMETERS, space, three dashes). Close with `# --- /PARAMETERS ---` — same shape with a leading slash before PARAMETERS. `# PARAMETERS`, `## PARAMETERS`, `# -- PARAMETERS --`, or any other shorthand FAILS the regex and the script is rejected by `blender_run_bpy_script` with a `blocked_by_policy: true` error before it ever reaches Blender. The validator in `server/codegen_prompt.py` literally regex-greps for those tokens, so don't paraphrase.

Allowed value types in the block: `int`, `float`, `bool`, `str`, `tuple` of 2-4 numbers. **No function calls, no bpy references, no list comprehensions** — every value must be a plain Python literal so `ast.literal_eval` can re-parse it for the slider loop. Names must be UPPER_CASE.

If you find yourself wanting to add a numeric literal to the body of the script: stop, add it to the PARAMETERS block as a constant, reference the constant. Otherwise the slider loop won't see it.

### Anti-patterns (real failure modes from iteration-1 evals)

These are mistakes the LLM has actually made when this skill is loaded. Don't repeat them.

**1. Don't invent actions on `blender_polyhaven`.** There is no `action='list'`, no `action='catalog'`, no `action='inventory'`. To DISCOVER what's already on disk, use `blender_list_available_assets`. To SEARCH PolyHaven's online catalog (network call), use `blender_polyhaven(action='search')`. These are different tools with different jobs — a "list" action on `blender_polyhaven` does not exist and will return an error.

**2. Don't shorten the PARAMETERS marker.** `# PARAMETERS` (without the dashes) is the most common failure. The validator regex is strict on purpose so the slider loop's `extract_parameters` / `replace_parameters` round-trip is reliable. Always type the full `# --- PARAMETERS ---` and `# --- /PARAMETERS ---` markers.

**3. Don't inline asset ids as magic strings.** `bg_node.image = bpy.data.images.load("kiara_1_dawn.exr")` in the body of the script is wrong even if it works. Declare `HDRI_ID = "kiara_1_dawn"` in the PARAMETERS block and reference `HDRI_ID` in the body — otherwise `blender_apply_params` can't change the HDRI without regenerating.

**4. Don't recommend `blender_execute_python` for any iterative work.** It's a deprecated alias kept only for back-compat with old callers. New work goes through `blender_generate_bpy_script` → `blender_run_bpy_script` → `blender_apply_params`.

**5. Don't write your own cache-existence check in Python.** `blender_list_available_assets` already returns `total_assets` per provider and a `global_hints` array that tells you what's missing. There's no need to glob `~/.cache/polyhaven/` yourself in the bpy script.

### Worked recipe — asset cache discovery → render

Use this template anytime the user wants HDRI / PBR work AND hasn't already pinned an asset id. It's the canonical 6-step flow that the v3.1 server is designed around. **When responding to the user, copy the call signatures verbatim — don't paraphrase `providers=[...]` into `provider:` or collapse two distinct tool calls into one. The list_available_assets call MUST include both `providers=[...]` and `asset_types=[...]` keyword arguments. The flow MUST end in two separate calls — `blender_generate_bpy_script` first, THEN `blender_run_bpy_script` — never just one.**

```text
Step 1 — DISCOVER what's already cached on disk    [tool: blender_list_available_assets]
   blender_list_available_assets(
       providers=["polyhaven", "ambientcg"],   # ← keyword arg, list of provider names
       asset_types=["hdri", "texture"]         # ← keyword arg, plural, list of types
   )
   → returns providers[].assets[] with {id, type, resolutions_available}
   This is the ONLY tool that lists what is already on disk. There is no list action
   on blender_polyhaven. Do not paraphrase the args.

Step 2 — BRANCH on cache hit vs miss
   if the HDRI/texture you want is in the returned ids:
       cache hit — use that id directly, skip to Step 4
   else:
       cache miss — proceed to Step 3

Step 3 — DOWNLOAD what's missing                    [tool: blender_polyhaven]
   3a (search):  blender_polyhaven(action="search", asset_type="hdris", categories="...")
                 → pick a result id that matches the user's intent
   3b (fetch):   blender_polyhaven(action="download_hdri", asset_id="<id>", resolution="2k")
                 (or action="download_texture" for PBR; download_hdri auto-applies
                  the asset to the world environment.)

Step 4 — DECLARE the asset ids as PARAMETERS-block constants
   The script you're about to author MUST start with this exact header:

       # --- PARAMETERS ---
       HDRI_ID = "kiara_1_dawn"            # cached HDRI asset id (string)
       HDRI_STRENGTH = 1.2                 # tweakable
       FLOOR_PBR_ID = "wood_planks_oak"    # cached PBR asset id (string)
       FLOOR_TILE_SCALE = 2.0              # tweakable
       RENDER_SAMPLES = 128                # tweakable
       # --- /PARAMETERS ---

   Reference HDRI_ID / FLOOR_PBR_ID / etc. by name in the script body — never
   inline as magic strings. (Common variants like HDRI_ASSET_ID or WOOD_ID are
   fine; the only requirement is UPPER_CASE and inside the dashed block.)

Step 5 — PUBLISH the contract                       [tool: blender_generate_bpy_script]
   blender_generate_bpy_script(
       intent="wood floor scene with HDRI environment",
       reference_params={"HDRI_ID": "kiara_1_dawn", "FLOOR_PBR_ID": "wood_planks_oak"}
   )
   → returns the system prompt + parameters template + version stamp.
   Author the script (a single bpy module) following the returned contract.
   Step 5 is its own tool call. It does NOT execute anything.

Step 6 — EXECUTE                                    [tool: blender_run_bpy_script]
   blender_run_bpy_script(script=<the authored script with PARAMETERS block>)
   → returns {script_id, parameters, result}.
   Step 6 is its own tool call, distinct from step 5. It validates, AST-gates,
   caches under script_id, then sends to the addon.

Subsequent tweaks (HDRI strength, tile scale, render samples)  [blender_apply_params]
   blender_apply_params(script_id="<id_from_step_6>",
                        new_values={"HDRI_STRENGTH": 1.6})
   No LLM call. No regeneration. Just re-runs the rewritten PARAMETERS block.
```

The same 6 steps apply for textures, models, and Sketchfab/Hyper3D assets — swap the provider list and the action names. The shape stays the same: **discover (list_available_assets) → branch → download-if-missing (polyhaven) → constant-ize (PARAMETERS block) → generate (generate_bpy_script) → run (run_bpy_script)**. Six steps, six tool calls when the cache misses, four tool calls when it hits (skips 3a/3b).

### Canonical end-to-end flow

```
Intent: "make a hero shot of this perfume bottle photo"

1. blender_reference_image_to_scene(action="extraction_prompt",
                                     image_path="/abs/path/photo.jpg")
   → returns { extraction_prompt, json_schema, next_call }

2. (Caller multimodal LLM call against the image, following the schema)
   → produces structured extraction JSON

3. blender_reference_image_to_scene(action="submit_extraction",
                                     extracted=<JSON>)
   → returns { extraction_id, validated, warnings }

4. blender_reference_image_to_scene(action="build_seed_params",
                                     extraction_id=<id>)
   → returns { seed_parameters: {PRIMARY_SIZE, BASE_COLOR_PRIMARY, ...}, missing_keys }

5. blender_list_available_assets(providers=["polyhaven"],
                                 asset_types=["hdri","texture"])
   → returns the on-disk catalog; pick HDRI_ID + PBR_ID

6. blender_generate_bpy_script(intent="hero shot of perfume bottle",
                               reference_params={**seed_parameters,
                                                 "HDRI_ID":"kiara_1_dawn"})
   → returns the contract; caller authors a script with PARAMETERS block

7. blender_run_bpy_script(script=<authored>)
   → validated, AST-gated, cached, executed → returns script_id

8. blender_apply_params(script_id=<id>,
                         new_values={"CAM_FOCAL_LEN_MM":85, "KEY_LIGHT_ENERGY":1500})
   → ZERO LLM tokens. Re-runs only the PARAMETERS block.
   Repeat step 8 indefinitely on a slider — never goes back to the LLM.
```

### Asset workflow rule

Before writing any HDRI-loading or PBR-texture-loading bpy code:

1. `blender_list_available_assets(providers=["polyhaven","ambientcg"], asset_types=["hdri"])` — see what's already on disk.
2. Reference the asset id as a PARAMETERS-block string constant: `HDRI_ID = "kiara_1_dawn"`. **Never inline magic strings** in the script body.
3. If the asset is missing from the cache, call `blender_polyhaven(action='search')` then `download_hdri` / `download_texture`, then `apply_texture`. Only THEN reference it.

The same rule applies to Sketchfab models and Hyper3D / Hunyuan3D generated meshes — query the cache first, then download, then constant-ize the id.

### Server-side safety (defense in depth)

The addon's `OPENCLAW_ALLOW_EXEC` gate at `blender_addon/openclaw_blender_bridge.py:917-945` is **untouched** in v3.1 — it remains the authoritative kill switch. v3.1 layers a server-side AST check on top inside `blender_run_bpy_script` and `blender_apply_params`, using the same `server/safety.py` deny lists (`os`, `subprocess`, `socket`, `eval`, `exec`, `__import__`, `compile`, `open`, …). A bad script is rejected before the socket is even opened — fail fast, fail cheap.

If `OPENCLAW_ALLOW_EXEC` is unset/0, the addon returns `{error: "execute_python is disabled...", disabled_by_policy: true}` and `blender_run_bpy_script` surfaces it unchanged.

### When NOT to use the parametric workflow

- One-off diagnostic snippets that don't affect geometry/materials/lighting (e.g. "print all object names"). Use `blender_run_bpy_script(script=..., require_parameters_block=False)` or the legacy `blender_execute_python` alias.
- Scene introspection where you don't intend to iterate. `blender_get_scene_info` / `blender_get_object_data` are still the right tools.
- Anything covered by an existing high-level tool (`blender_create_object`, `blender_set_material`, `blender_scene_lighting`, etc.) — those are deterministic and skip the LLM entirely.

The parametric workflow shines when you'll be tweaking values multiple times, when you're driving from a reference image, or when you want the LLM out of the loop on routine adjustments.

### Tests + reference code

- `tests/test_cadam_p1_p2_split_exec.py` — 10 tests covering the contract, run/cache/apply_params loop, and security gates.
- `tests/test_cadam_p3_reference_image.py` — 5 tests covering the two-pass image flow.
- `tests/test_cadam_p4_list_assets.py` — 7 tests covering asset discovery and grouping.

All three are self-contained — they stub `mcp.server.fastmcp` and mock `send_command`, so they require neither pip-installed `mcp` nor a live Blender. Run via `python3 tests/test_cadam_*.py` from the repo root.

Modules: `server/codegen_prompt.py` (system prompt + safe `extract_parameters`/`replace_parameters`), `server/image_extraction.py` (extraction schema + seed-param mapper), and the v3.1 tools live in `server/blender_mcp_server.py` (search for `# ─── v3.1`).

---

## LEGACY Sections (1–18)

[Legacy content preserved from v2.x: Wire Protocol, Python Quoting, Scene Management Patterns, Geometry Execution, Material & Rendering Polish, Export Pipeline, Rendering & Bake, Validation & Constraints, Cinema Pack, Data Structures, Multi-Instance Patterns, Free Model Sourcing, Common Errors & Fixes, Autoresearch, Performance, Smart Render Settings, Forensic Metrics, 3D Library Sourcing, Self-Correction & Mutation]

See previous versions for full legacy documentation. All legacy sections updated with tool count 65 → ~80.

---

**Last Updated**: v3.0.0 — 2026-04-23  
**Maintained By**: jabbertones-cloud  
**Status**: Production

---

# LEGACY SECTIONS (v2.x Reference)

## Source Of Truth

This file is the operational source of truth for Blender MCP usage in this repo.

- `README.md` should stay high-level and defer here for operational behavior.
- `BLENDER_SKILLS_REFERENCE.md` is a phrase-to-tool lookup and defers here on conflicts.
- `CINEMA_RENDER_SKILL_PACK.md` contains shot-quality presets for AgX/EXR/pass workflows.
- Codex-native Blender skill wrappers should point here instead of duplicating rules.
- Use `scripts/blender_healthcheck.py` before claiming local MCP wiring is correct.
- In multi-instance setups, keep `BLENDER_PORT` and `OPENCLAW_PORT` set to the same value.

### MCP tool inventory (audited)

The MCP server registers **65 tools** total: **59** in `server/blender_mcp_server.py` plus **6** product tools from `server/product_animation_tools.py` (`blender_product_*` and `blender_fcurve_edit`) when that module loads. Use `blender_instances` to list, ping, or connect to a Bridge on another port (default scan range 9876–9885). Do not use outdated “35 tools” references. Full grouped list: root `README.md`.

## 1. MCP Wire Protocol

The Blender MCP server listens on TCP (default port 9876). Communication is JSON over raw TCP sockets — no HTTP, no newline delimiters.

**Request format:**
```json
{"id": 1, "command": "execute_python", "params": {"code": "..."}}
```

**Critical rules:**

- **NO `blender_` prefix on ANY command — this is a universal rule.** The server registers tools as `execute_python`, `render`, `export_file`, `save_file`, `create_object`, `set_render_settings`, `cleanup`, etc. If you send `blender_execute_python`, `blender_render`, `blender_cleanup`, or any `blender_*` prefixed name, it will fail silently or error. The `blender_` prefix exists only in the MCP tool registry for namespacing — strip it before sending over the socket. This means: `client.call('execute_python', ...)` not `client.call('blender_execute_python', ...)`. And `client.call('cleanup', ...)` not `client.call('blender_cleanup', ...)`. Every single MCP tool call follows this rule with zero exceptions.

- **Brace-depth JSON parsing.** Blender sends raw JSON without newline terminators. You cannot use `readline()` or split on `\n`. You must count brace depth: track `{` (depth++) and `}` (depth--), ignoring braces inside quoted strings and escaped characters. When depth returns to 0, you have a complete JSON message.

- **Double-nested result for execute_python.** The response is `{"id": N, "result": {"result": actual_data}}`. You must unwrap twice: `const outer = msg.result; const inner = outer.result;` — `inner` is your actual Python `__result__` value.

- **Timeout: 30 seconds default.** Long operations (rendering at high resolution, complex geometry) can exceed this. Use EEVEE (2-3s per render) not Cycles (60s+) for pipeline renders.

## 2. Python Code in JavaScript

When writing Python code inside a JavaScript string (for `execute_python` calls), these rules prevent crashes:

**Single quotes only — EVERYWHERE in the Python string.** Python code inside JS template literals or strings gets passed through `JSON.stringify()`, which escapes double quotes to `\"`. The Blender addon's `exec()` or JSON parser chokes on these escaped quotes, causing an ECONNRESET that kills the TCP connection with no error message. This applies to ALL strings inside the Python code — object names, dict keys, dict values, function arguments, everything.

```javascript
// CORRECT — single quotes for ALL strings in the Python code
await client.call('execute_python', {
  code: `import bpy\nobj = bpy.data.objects.get('Cube')\nif obj:\n    obj.location = (1, 2, 3)\n__result__ = {'moved': True}`
});

// CORRECT — even for complex code with multiple strings
await client.call('execute_python', {
  code: `import bpy\nfor obj in bpy.data.objects:\n    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):\n        mat = bpy.data.materials.new(name='Material')\n        mat.use_nodes = True\n        bsdf = mat.node_tree.nodes.get('Principled BSDF')\n        if bsdf:\n            bsdf.inputs['Base Color'].default_value = (0.8, 0.2, 0.2, 1.0)\n__result__ = {'applied': True}`
});

// WRONG — double quotes ANYWHERE in the Python string will crash
await client.call('execute_python', {
  code: `import bpy\nobj = bpy.data.objects.get("Cube")\n...`  // CRASH — "Cube"
});
await client.call('execute_python', {
  code: `import bpy\n__result__ = {"status": "ok"}`  // CRASH — "status", "ok"
});
```

**When in doubt:** search your Python code string for `"` — if you find any, replace them with `'`. There are zero cases where double quotes are needed inside Python code sent via MCP.

**Newlines as `\n`.** The code string is sent as a single JSON string value. Use `\n` for line breaks, not actual newlines (unless you're in a template literal and the JSON serialization handles it).

**Always set `__result__`.** The Python code must assign to `__result__` for the MCP server to return data. Without it, you get `null` back.

**No f-strings with braces.** If you need to interpolate JS variables into Python code, do it in the JS template literal, not with Python f-strings. The brace-depth parser can get confused by unmatched braces in string content.

## 3. Scene Management

### Starting Clean

Every production run MUST start with a clean scene. Without cleanup, leftover objects from whatever was previously open in Blender will pollute your scene. We've seen 152 leftover objects from a traffic accident scene cause 200000mm bounding boxes and garbage validation.

**Cleanup procedure (both steps required):**

```javascript
// Step 1: Request a new empty scene from the MCP server
await client.call('save_file', { action: 'new', use_empty: true });

// Step 2: Belt-and-suspenders Python nuke of ALL data blocks
// (some Blender configs keep default objects even with use_empty)
await client.call('execute_python', {
  code: `import bpy\nfor obj in list(bpy.data.objects):\n    bpy.data.objects.remove(obj, do_unlink=True)\nfor mesh in list(bpy.data.meshes):\n    bpy.data.meshes.remove(mesh)\nfor mat in list(bpy.data.materials):\n    bpy.data.materials.remove(mat)\nfor cam in list(bpy.data.cameras):\n    bpy.data.cameras.remove(cam)\nfor light in list(bpy.data.lights):\n    bpy.data.lights.remove(light)\n__result__ = {'cleared': True, 'objects': len(bpy.data.objects)}`
});
```

**Why both steps:** `save_file` with `use_empty` tells Blender to start fresh, but the Python nuke catches edge cases where default objects survive. The Python cleanup also removes orphaned data blocks (meshes, materials) that `save_file` doesn't touch.

### Scene Persistence Gotcha — READ THIS

> **This caused our worst bug.** After the producer script disconnects from the MCP socket, Blender does NOT keep the scene the producer built. It reverts to whatever was previously loaded — undo history, auto-save recovery, or a completely different project file. The producer's TCP session is ephemeral; the scene only persists in the saved `.blend` file on disk.

**What this means in practice:**
- The **producer** works fine during its session (cleanup → create → render → save → disconnect). Everything looks correct while connected.
- The moment the producer **disconnects**, the Blender scene may snap back to a previous state (we saw it revert to a 152-object traffic accident scene).
- Any **subsequent script** that connects to the same Blender instance and queries `bpy.data.objects` will see the OLD stale scene, not the model that was just produced.
- Therefore the **validator** (or any post-production script) MUST call `bpy.ops.wm.open_mainfile(filepath=...)` to explicitly load the saved `.blend` file before measuring anything. See Section 8 (Validation) for the exact code.
- This is the root cause whenever you see impossibly large bounding boxes (e.g., 156000mm for a 50mm chess piece) — the validator is measuring a stale scene, not the produced model.

## 4. Geometry Step Execution

Concept files define geometry steps in `blender_steps[]`. Each step has a `tool` and `params` (or `code` for Python steps).

**Tool name mapping for concept data:**
- If `step.tool` is `'blender_execute_python'` or `'execute_python'` → call `execute_python` with the step's code
- If `step.tool` is anything else (e.g., `'blender_create_object'`) → call that tool name directly with `step.params`

The concept files may use the `blender_` prefix in their tool names (that's fine — it's data, not a bug). But the MCP `client.call()` must strip or handle it. Current producer code passes `step.tool` directly to `client.call()`, which works because the MCP client strips the prefix internally.

**Retry on failure:** Geometry steps should retry once on failure before logging as failed. Many transient errors (context issues, selection state) resolve on retry.

## 5. Polish Phase

After geometry steps, apply finishing operations:

### Subdivision Surface Modifier

```javascript
await client.call('execute_python', {
  code: `import bpy\nfor obj in bpy.data.objects:\n    if obj.type == 'MESH':\n        mod = obj.modifiers.new('Subsurf', 'SUBSURF')\n        mod.levels = 2\n        mod.render_levels = 2\n__result__ = {'applied': True}`
});
```

### Shade Smooth

**DO NOT use `blender_cleanup` with `action: 'shade_smooth'`.** This fails 100% of the time with a `bpy_prop_collection` error. Use direct Python instead:

```javascript
await client.call('execute_python', {
  code: `import bpy\nfor obj in bpy.data.objects:\n    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):\n        bpy.context.view_layer.objects.active = obj\n        obj.select_set(True)\n        bpy.ops.object.shade_smooth()\n        obj.select_set(False)\n__result__ = {'shaded': True}`
});
```

The key details: you must set each object as active AND selected before calling `shade_smooth()`, then deselect it. Skip `_ground_plane` objects. This loops through all meshes individually — do not try to select-all and smooth-all at once.

### Materials

Apply materials from the concept's `visual_analysis.materials` array. Use `execute_python` to create Principled BSDF materials and assign them.

### UV Mapping

```javascript
await client.call('execute_python', {
  code: `import bpy\nfor obj in bpy.data.objects:\n    if obj.type == 'MESH':\n        bpy.context.view_layer.objects.active = obj\n        bpy.ops.object.mode_set(mode='EDIT')\n        bpy.ops.mesh.select_all(action='SELECT')\n        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)\n        bpy.ops.object.mode_set(mode='OBJECT')\n__result__ = {'uv_mapped': True}`
});
```

## 6. Export

### STL Export

There is NO `export_stl` action in `export_file`. STL must go through `execute_python`:

```javascript
const stlPath = path.join(outputDir, 'model.stl');
await client.call('execute_python', {
  code: `import bpy\nbpy.ops.wm.stl_export(filepath='${stlPath}')\n__result__ = {'exported': '${stlPath}'}`
});
```

### FBX/GLTF Export

Use the `export_file` tool with `action: 'export_fbx'` or `action: 'export_gltf'`:

```javascript
await client.call('export_file', {
  action: 'export_fbx',
  filepath: path.join(outputDir, 'model.fbx')
});
```

### Save .blend File

```javascript
await client.call('save_file', {
  action: 'save_as',
  filepath: path.join(outputDir, 'model.blend')
});
```

## 7. Rendering

### Render Settings

Use `set_render_settings` with **lowercase** engine names:

```javascript
await client.call('set_render_settings', {
  engine: 'eevee',           // NOT 'EEVEE' or 'Eevee'
  resolution_x: 2048,
  resolution_y: 2048,
  samples: 64,
  output_format: 'PNG'
});
```

### Studio Lighting Setup

White backgrounds wash out models completely. The vision API scored 1.6/10 with white backgrounds, 6/10 with gray. Always use this setup:

```javascript
await client.call('execute_python', {
  code: `import bpy, mathutils

# Find model center and size for relative positioning
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(wc)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0,0,0))
    size = 2.0

# World background: medium gray (0.18) — NOT white
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)
    bg.inputs[1].default_value = 1.0

# 3-point area lighting relative to model size
d = max(size * 2.0, 3.0)
for name, loc, energy in [('key_light', (d, d, d*0.8), 500.0), ('fill_light', (-d*0.6, d*0.6, d*0.5), 200.0), ('rim_light', (0, -d*0.8, d*0.5), 300.0)]:
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = energy
    light_data.size = size * 0.5
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = center + mathutils.Vector(loc)
    dir = center - light_obj.location
    rot = dir.to_track_quat('-Z', 'Y')
    light_obj.rotation_euler = rot.to_euler()

# Ground plane: proportional to model, neutral gray, named for exclusion
bpy.ops.mesh.primitive_plane_add(size=size*4, location=(center.x, center.y, min(zs) - 0.01 if meshes else -0.5))
ground = bpy.context.active_object
ground.name = '_ground_plane'
mat = bpy.data.materials.new('ground_mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
ground.data.materials.append(mat)

__result__ = {'center': [center.x, center.y, center.z], 'size': size, 'light_dist': d}`
});
```

**Key details:**
- Background: `(0.18, 0.18, 0.2)` — medium gray, not white
- Lights: 500W key, 200W fill, 300W rim (area lights). Default Blender energy of 2.0 is invisible.
- Light size: `size * 0.5` for soft shadows proportional to model
- Ground plane: `size * 4` (not scale 10 — that creates 20000mm planes), named `_ground_plane`
- All positions relative to model center and size

### Camera Auto-Framing

Hardcoded camera positions miss the model entirely, producing blank renders. Always calculate position from the model's bounding box:

```javascript
// For each render shot, calculate camera position relative to model
const cameraCode = `import bpy, mathutils

meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != '_ground_plane']
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(world_corner)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

d = max(size * 2.5, 3.0)

cam = bpy.data.objects.get('Camera')
if not cam:
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object

# Position based on shot angle (interpolate JS variable)
angle = '${shot.angle}'
if angle == 'hero':
    cam.location = center + mathutils.Vector((d*0.6, d*0.6, d*0.45))
elif angle == 'front':
    cam.location = center + mathutils.Vector((0, d, 0))
elif angle == 'side':
    cam.location = center + mathutils.Vector((d, 0, 0))
elif angle == 'top':
    cam.location = center + mathutils.Vector((0, 0.001, d))
elif angle == 'detail':
    cam.location = center + mathutils.Vector((d*0.35, d*0.35, d*0.25))

# Aim camera at model center
dir = center - cam.location
rot = dir.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam
__result__ = {'center': [center.x, center.y, center.z], 'distance': d}`;
```

**Key details:**
- Exclude `_ground_plane` from bounding box calculation for camera framing
- Use `to_track_quat('-Z', 'Y')` to aim camera — this is Blender's standard "look at" technique
- Distance = `size * 2.5` gives good framing with some breathing room
- For top view, use `(0, 0.001, d)` not `(0, 0, d)` — pure Z-axis creates gimbal lock

### Executing Renders

```javascript
await client.call('render', {
  output_path: path.join(outputDir, 'hero.png')  // NOT "filepath" — that param doesn't exist
});
```

**The parameter is `output_path`, NOT `filepath`.** This caused silent failures in early versions.

## 8. Validation

### Mechanical Validation

The validator connects to Blender MCP and runs Python to measure mesh properties. **It MUST open the .blend file first:**

```javascript
// CRITICAL: Open the .blend file before measuring
await blenderClient.executePython(
  `import bpy\nbpy.ops.wm.open_mainfile(filepath='${absPath}')\n__result__ = {'opened': True, 'objects': len(bpy.data.objects)}`
);
```

Without this, the validator measures whatever scene happens to be loaded in Blender (often a completely different project), producing garbage results like 200000mm bounding boxes from stale scenes.

## 7.5 Cinema Render Pack

Use this preset stack whenever a user asks for "cinema quality", "film look", or "commercial-grade" output:

1. **Color pipeline (AgX/Filmic)**
   - Prefer `AgX` when available; otherwise `Filmic`.
   - Keep exposure conservative (`<= 1.0`) to avoid highlight clipping.
2. **EXR pass workflow**
   - Render format: `OPEN_EXR` with `16` or `32` bit depth.
   - Enable at least `Z` and `Normal` passes; prefer `Vector` or `Mist` too.
3. **Animation-safe denoise**
   - Use Cycles denoising + adaptive sampling.
   - For high motion shots, use higher sample floors before denoise to reduce temporal shimmer.
4. **Asset sourcing for fidelity**
   - `sketchfab` for production props and set dressing.
   - `polyhaven` for HDRIs/PBRs.
   - `hyper3d` / `hunyuan3d` for generated hero concepts.
5. **Render QA gate**
   - Run `render_quality_audit` before final renders.
   - Must pass: engine, noise budget, highlight clipping guard, compositing pass completeness.

### Ground Plane Exclusion

When collecting mesh data for bounding box measurement, ALWAYS exclude the ground plane:

```python
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]
```

This is why the ground plane MUST be named `_ground_plane` — it's a convention the entire pipeline relies on.

### Mechanical Checks

| Check | Pass Condition | Platform |
|-------|---------------|----------|
| manifold | 0 non-manifold edges | all |
| tri_count | ≤ 50000 triangles | game |
| loose_verts | 0 loose vertices | all |
| degenerate_faces | 0 degenerate faces (area < 1e-8) | all |
| wall_thickness | ≥ 1.5mm estimated | 3d-print |
| bounding_box | ≤ 5000mm per axis (game) or ≤ 300mm (3d-print) | varies |

### Visual Validation

Uses a multi-provider vision API chain:
1. **Gemini 2.0 Flash** (primary) — cheapest, fastest
2. **Anthropic Claude Haiku** (fallback) — when Gemini 429s
3. **OpenAI GPT-4o** (last resort)

The vision API receives all rendered images and scores: shape_accuracy, proportion_accuracy, detail_level, material_quality, marketplace_readiness (each 1-10). Average determines verdict: ≥7 = PASS, 4-6.99 = NEEDS_REVISION, <4 = REJECT.

### Scoring

`production_quality_score` = weighted combination of mechanical pass rate and visual average. Scale 0-100.
- Mechanical PASS + Visual PASS → 90-100
- Mechanical PASS + Visual NEEDS_REVISION → 70-89
- Mechanical FAIL → capped at 50

## 9. Data Structures

### Concept JSON (`data/3d-forge/concepts/<id>.json`)
```json
{
  "concept_id": "uuid",
  "name": "...",
  "platform": "game_asset",
  "blender_steps": [
    {"step": 1, "tool": "blender_create_object", "params": {"type": "cube", "size": 1}},
    {"step": 2, "tool": "blender_execute_python", "code": "import bpy\n..."}
  ],
  "visual_analysis": {
    "materials": ["plastic", "metal"],
    "colors": ["#FF0000"],
    "proportions": {"width": 100, "height": 100, "depth": 100}
  }
}
```

Note: `concept_id` is the field name, NOT `id`. Always use `concept.concept_id || concept.id` as fallback.

### Metadata JSON (`exports/3d-forge/<id>/metadata.json`)
```json
{
  "concept_id": "uuid",
  "status": "completed",
  "production_time_seconds": 3,
  "steps_executed": 13,
  "steps_failed": 0,
  "step_log": [{"step": "new_scene", "success": true}, ...],
  "file_sizes": {"model.stl": 2484, "hero.png": 937810}
}
```

### Validation JSON (`exports/3d-forge/<id>/validation.json`)
```json
{
  "overall_verdict": "PASS|NEEDS_REVISION|REJECT",
  "production_quality_score": 80,
  "mechanical": {
    "passed": true,
    "checks": {
      "manifold": {"passed": true, "value": 0},
      "bounding_box": {"passed": true, "value": "1000×1000×1000mm"}
    }
  },
  "visual": {
    "average": 6.0,
    "verdict": "NEEDS_REVISION",
    "issues": ["..."],
    "suggested_fixes": ["..."]
  }
}
```

## 10. Pipeline Architecture (6 Stages)

1. **SCAN** — Monitor trend sources for trending products/designs
2. **HARVEST** — Collect reference images and analyze visual features
3. **GENERATE** — LLM creates concept JSON with blender_steps from references
4. **PRODUCE** — `blender-producer.js` executes concept in Blender (cleanup → geometry → polish → export → render)
5. **VALIDATE** — `asset-validator.js` runs mechanical + visual checks
6. **LEARN** — `autoresearch-agent.js` tracks KPIs, detects regressions, encodes learnings

### Key Files
```
scripts/3d-forge/
├── forge-orchestrator.js      — Runs all 6 stages
├── blender-producer.js        — PRODUCE stage (~830 lines)
├── asset-validator.js         — VALIDATE stage (mechanical + visual)
├── autoresearch-agent.js      — LEARN stage (18 KPIs, 20 regression checks)
├── trend-scanner.js           — SCAN stage
├── reference-harvester.js     — HARVEST stage
├── concept-generator.js       — GENERATE stage
└── README.md
config/3d-forge/               — Pipeline config files
data/3d-forge/concepts/        — Concept JSON files
exports/3d-forge/<concept_id>/ — Per-concept outputs (STL, .blend, renders, validation)
reports/                       — Autoresearch reports
```

### Full forge orchestrator (ingest + learn)

Default `forge:run` ends with **METRICS** (`reports/3d-forge-metrics-latest.json`) and **SKILL_LEARN** (`config/3d-forge/skill-plan-adjustments.json`). The skill planner reads adjustments on the next `blender-producer` run. Use `npm run forge:run:deep` / `forge:run:mega` for higher `--limit` (more trends harvested → more reference images). Chain `forge:full:with-gates` if you also need `quality-gate-runner.js` retries.

### Quality gate pitfalls (avoid repeat failures)

1. **`concept-generator.js` must parse** — if GENERATE throws `SyntaxError`, the hourly run still processes **stale** concepts from disk; fix the script before trusting scores.
2. **Reference images** — validation loads `data/3d-forge/refs/{trend_id}/`. If `trend_id` is missing, vision used to compare renders to **zero** references; `asset-validator.js` now uses an **absolute-quality** JSON rubric when `references.length === 0` (critical for **Ollama llava** when cloud APIs are rate-limited).
3. **Cloud vs local vision** — Gemini/OpenAI/Anthropic are tried first; when quota fails, **llava** is the real scorer. **`concept-generator.js`** also falls back to **Ollama llava** for GENERATE (set `OLLAMA_SKIP_CONCEPT_VISION=1` to disable). Keep Ollama up and prefer the no-reference prompt when harvest did not run.
4. **Mechanical vs score** — if trimesh reports non-watertight / bad STL, fix export or manifold repair before chasing visual points.

## 11. Multi-Blender Instance Support

For parallel production, each agent needs its own Blender instance on a different port:

```javascript
const instances = [
  { port: 9876, busy: false },
  { port: 9877, busy: false },
  { port: 9878, busy: false },
];
```

Launch additional Blender instances with: `blender --python-expr "..." --background` where the Python starts the MCP addon on a specific port. Each producer claims an instance, marks it busy, and releases it when done.

## §11 — FREE MODEL SOURCING (MANDATORY)

**CRITICAL RULE: NEVER build vehicles, pedestrians, buildings, or props from primitive geometry (cubes, cones, spheres). This is why renders score 1.5/10 — everything looks like toy blocks.**

### Mandatory Workflow
Before creating ANY object in a forensic scene:
1. **SEARCH** free 3D model sources for a suitable asset
2. **DOWNLOAD** the best match in .blend, .glb, or .fbx format
3. **IMPORT** into the scene using `bpy.ops.import_scene.gltf()` or `bpy.ops.wm.append()`
4. **SCALE** to real-world dimensions
5. **ONLY** build from scratch if nothing suitable exists after exhaustive search

### Priority Sources (all free, all legal)
| Source | URL | License | Best For |
|--------|-----|---------|----------|
| Polyhaven | polyhaven.com/models | CC0 | HDRIs, textures, some models |
| Sketchfab | sketchfab.com (CC0 filter) | CC0/CC-BY | Vehicles, people, environments |
| BlenderKit Free | blenderkit.com | CC0/RF | Blender-native assets |
| Free3D | free3d.com | Free | Vehicles, props |
| CGTrader Free | cgtrader.com/free | RF | Detailed models |
| Turbosquid Free | turbosquid.com (free) | RF | Professional quality |

### Import Code Templates

**Import GLTF/GLB:**
```python
import bpy
bpy.ops.import_scene.gltf(filepath='/path/to/model.glb')
# Scale to real world
obj = bpy.context.selected_objects[0]
obj.scale = (1.0, 1.0, 1.0)  # Adjust as needed
```

**Append from .blend:**
```python
import bpy
blend_path = '/path/to/model.blend'
with bpy.data.libraries.load(blend_path) as (data_from, data_to):
    data_to.objects = data_from.objects
for obj in data_to.objects:
    if obj is not None:
        bpy.context.collection.objects.link(obj)
```

**Import HDRI Environment:**
```python
import bpy
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
env_tex = world.node_tree.nodes.new('ShaderNodeTexEnvironment')
env_tex.image = bpy.data.images.load('/path/to/hdri.exr')
bg = world.node_tree.nodes['Background']
world.node_tree.links.new(env_tex.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.0
```

### Real-World Dimensions Reference
- Sedan: ~4.5m L × 1.8m W × 1.4m H
- SUV: ~4.8m L × 1.9m W × 1.7m H  
- Pickup truck: ~5.3m L × 2.0m W × 1.8m H
- Semi truck: ~16m L × 2.6m W × 4.0m H
- Adult pedestrian: ~1.7m H × 0.5m W
- Traffic light: ~0.3m W × 1.0m H (head), mounted at 5-6m
- Street lamp: 6-10m H
- Lane width: 3.0-3.7m
- Crosswalk width: 1.8-3.0m

### What NEVER to Do
- ❌ Use a cube as a "car"
- ❌ Use a cone as a "person"  
- ❌ Use a sphere as a "wheel"
- ❌ Build vehicle interiors from scratch when models exist
- ❌ Skip the search step to "save time"

## 12. Common Errors and Fixes

| Error | Root Cause | Fix |
|-------|-----------|-----|
| ECONNRESET on execute_python | Double quotes in Python code | Use single quotes only (see §2) |
| `bpy_prop_collection` on shade_smooth | Using `blender_cleanup` action (or ANY `blender_*` prefixed call — see §1) | Use `execute_python` with per-object loop (see §5). Also note: `blender_cleanup` violates the no-prefix rule. |
| Bounding box 200000mm+ | Validator reading stale scene, not .blend file (see §3 Scene Persistence) | Open .blend with `bpy.ops.wm.open_mainfile()` first (see §8) |
| Blank renders (visual 0-2/10) | Camera at hardcoded position missing model | Auto-frame from bounding box center (see §7 Camera) |
| Washed out renders (visual 1-3/10) | White background + low light energy + possibly bad camera framing | Gray bg (0.18) + 500W/200W/300W area lights (see §7 Lighting) AND check camera framing (see §7 Camera) — both cause low visual scores |
| Ground plane inflating bounding box | Ground plane too large or not excluded | Name `_ground_plane`, size `model_size*4`, filter in validator |
| `null` result from execute_python | Missing `__result__` assignment | Always set `__result__ = {...}` |
| STL export fails via export_file | No STL action in export_file tool | Use `execute_python` with `bpy.ops.wm.stl_export()` (see §6) |
| Render produces no file | Using `filepath` param instead of `output_path` | Use `output_path` in render call (see §7) |
| Engine not recognized | Uppercase engine name | Use lowercase: `'eevee'`, `'cycles'` |
| 152 leftover objects in scene | No cleanup at start of production | `save_file` with `use_empty` + Python nuke (see §3) |
| Gemini 429 rate limit | API quota exceeded | Falls back to Anthropic Claude Haiku automatically |
| `MESH_OT_primitive_cube_add.size expected float` | Concept passes size as array/string | Validate step params before execution |
| Any `blender_*` call fails silently | Using `blender_` prefix on MCP command name | Strip the prefix — see §1. This applies to ALL tools: `cleanup` not `blender_cleanup`, `render` not `blender_render`, etc. |
| GEOMETRY_FROM_SCRATCH | Using primitive geometry when free models are available | Search free model sources, download and import proper models (see §11). This is a major render quality killer. |

### Diagnostic Checklist: Low Visual Scores

When the vision API scores renders below 5/10, check ALL of these (they compound):

1. **Background color** — Is it white (0.95)? Change to gray (0.18, 0.18, 0.2). White washes out everything.
2. **Light energy** — Are lights at default energy (2.0 or 10.0)? Need 200W+ area lights. Use 3-point: 500W key, 200W fill, 300W rim.
3. **Light type** — Point lights create harsh shadows. Use area lights with `size = model_size * 0.5` for soft illumination.
4. **Camera position** — Is the camera at a hardcoded position like `(5, 5, 5)`? It might be pointing at empty space. Auto-frame from bounding box center (see §7 Camera).
5. **Camera aim** — Even if the camera is nearby, is it actually pointed at the model? Use `to_track_quat('-Z', 'Y')` to aim.
6. **Engine** — Is the engine name lowercase `'eevee'`? Uppercase `'EEVEE'` may silently fall back to defaults.
7. **Ground plane** — Is there one? A neutral gray ground plane prevents the model from floating in void.
8. **Render resolution** — At least 2048×2048 for marketplace quality.

## 13. Autoresearch Regression Checks

The autoresearch agent (`autoresearch-agent.js`) scans pipeline source code for anti-patterns every run. Currently 20 checks across these categories:

**Protocol checks:** No `blender_` prefix in MCP calls, brace-depth parser present (not readline), double-nested result unwrapping

**Python checks:** No double quotes in execute_python code strings

**Render checks:** `output_path` not `filepath`, lowercase engine names, gray background (not white), light energy ≥200W

**Scene checks:** `use_empty` in scene reset, `_ground_plane` naming in producer and validator

**Validation checks:** Validator opens .blend file, ground plane excluded from bounding box

**Quality checks:** Camera uses bounding box framing (not hardcoded), shade_smooth uses execute_python (not blender_cleanup)

When adding new code to the pipeline, ensure it doesn't trigger any of these anti-patterns. The autoresearch agent runs on every production cycle and will flag regressions.

## 14. Performance Baselines

From production runs (mock concept, single cube geometry):

| Metric | Before Fixes | After Fixes |
|--------|-------------|-------------|
| Production time | 3-17s | 3s |
| Steps failed | 2/13 | 0/13 |
| Mechanical | FAIL (2/6) | PASS (6/6) |
| Bounding box | 200000mm | 1000mm |
| Visual score | 1.6/10 | 6/10 |
| Overall score | 47/100 REJECT | 80/100 NEEDS_REVISION |
| shade_smooth | 100% fail | PASS |

The 6/10 visual ceiling is from the mock concept (plain cube). Real LLM-generated concepts with multi-step geometry should score 7-8+.

## 15. Smart Render Pipeline (v22+)

The smart pipeline adds 4 acceleration layers to the forensic render workflow. All scripts are production-tested.

### Architecture

```
scripts/
├── pre_render_validator.py      — Scene introspection without rendering (~1-2ms)
├── proxy_render.py              — Configurable resolution proxy renders (25%/50%/100%)
├── v22_postprocess_denoise.py   — 3-layer denoising (NLM + luminance + bilateral)
├── v22_render_standalone.py     — Standalone Blender render with auto EEVEE→Cycles switch
├── adaptive_render_pipeline.sh  — Shell orchestrator: validate → proxy → full → merge
├── 3d-forge/vision-llm-scorer.js — Claude-powered vision scoring against 3-track audit
└── smart_render_pipeline.js     — Master Node.js orchestrator tying everything together
```

### npm Scripts

```bash
npm run render:smart              # Full pipeline, all 4 scenes
npm run render:smart:dry           # Dry run — show what would execute
npm run render:smart:fast          # Skip vision scoring for speed
npm run render:smart:scene -- 1    # Single scene only
npm run render:validate            # Pre-render validation only
npm run render:vision              # Vision score existing renders
npm run render:vision:image -- path.png  # Score a single image
```

### 15.1 Pre-Render Validator (`scripts/pre_render_validator.py`)

Introspects `bpy.data` without rendering to catch setup errors. Runs in ~1-2ms.

**6 validation categories:**
- Cameras: existence, sensor size, clip range, resolution
- Lighting: energy levels, shadow casting, type checks
- Materials: existence on meshes, node tree validity
- Geometry: degenerate faces, loose vertices, manifold edges
- Render settings: valid engine (`CYCLES`, `BLENDER_EEVEE`, `BLENDER_EEVEE_NEXT`), sample counts, resolution
- Forensic compliance: evidence markers, measurement references, proper camera naming

**Usage:**
```bash
/Applications/Blender.app/Contents/MacOS/Blender scene.blend --background --python scripts/pre_render_validator.py -- --json
```

**Key detail:** Engine check accepts `BLENDER_EEVEE` and `BLENDER_EEVEE_NEXT` (Blender 5.x identifiers), not just `EEVEE`.

### 15.2 Proxy Render (`scripts/proxy_render.py`)

Renders at reduced resolution for fast quality gating before full renders.

```bash
# 25% resolution — fast gate (~2s)
/Applications/Blender.app/Contents/MacOS/Blender scene.blend --background --python scripts/proxy_render.py -- --percent 25 --output /tmp/proxy25.png

# 50% resolution — medium gate
/Applications/Blender.app/Contents/MacOS/Blender scene.blend --background --python scripts/proxy_render.py -- --percent 50 --output /tmp/proxy50.png
```

**EEVEE headless auto-switch:** In `--background` mode, EEVEE requires a GPU context (Metal) that is unavailable. The proxy renderer auto-switches to Cycles with optimized settings:
- 25% proxy: 32 samples
- 50% proxy: 48 samples  
- 100% full: 64 samples
- OpenImageDenoise enabled, adaptive sampling threshold 0.05

### 15.3 Vision LLM Scorer (`scripts/3d-forge/vision-llm-scorer.js`)

Claude-powered forensic render assessment using the 3-track audit rubric.

```bash
# Single image
node scripts/3d-forge/vision-llm-scorer.js --image renders/v21_final/scene1_BirdEye.png --scene-type t-bone

# Batch scoring
node scripts/3d-forge/vision-llm-scorer.js --batch renders/v22_final/

# Output to file
node scripts/3d-forge/vision-llm-scorer.js --image render.png --json-out scores.json
```

**Key details:**
- Loads `ANTHROPIC_API_KEY` from `.env` file in project root (no dotenv dependency)
- Auto-detects scene type from filename (`scene1`→t-bone, `scene2`→pedestrian, etc.)
- Auto-resizes images >4.8MB base64 using macOS `sips` (progressively: 1920→1440→1280→1024→800px)
- Falls back to mock scores if no API key found
- Resolves relative paths from REPO_ROOT
- Scene types: `t-bone`, `pedestrian`, `highway`, `parking-lot-night`

**Output structure:**
```json
{
  "vision_scores": {
    "forensic_clarity": 7,
    "physical_plausibility": 6,
    "cinematic_presentation": 5,
    "weighted": 6.1,
    "gate_check": { "FC_pass": true, "PP_pass": false, "CP_pass": false }
  },
  "improvements": ["..."],
  "courtroom_ready": false,
  "is_mock": false
}
```

### 15.4 Post-Process Denoising (`scripts/v22_postprocess_denoise.py`)

3-layer denoising pipeline: NLM → luminance-channel → bilateral with 70/30 blend.

```bash
python3 scripts/v22_postprocess_denoise.py input.png output.png
```

**CRITICAL: Selective application only.** Blanket denoising causes -4.93 avg regression. Only apply when noise score >5.0. Images with noise <0.01 are HURT by denoising (lost detail). Use best-of merge strategy: only keep denoised version if score improves.

### 15.5 Adaptive Pipeline (`scripts/adaptive_render_pipeline.sh`)

Shell orchestrator implementing the full multi-pass pipeline:
1. Pre-validate scene → abort on critical errors
2. 25% proxy render → pixel score gate (reject <3.0)
3. 50% proxy render → pixel score gate (reject <5.0)
4. 100% full render → pixel + vision score
5. Best-of merge → only commit improvements

### 15.6 EEVEE Headless Limitation ⚠️

**This is the #1 infrastructure issue.** EEVEE requires Metal GPU context which is unavailable in `--background` mode. Symptoms:
- BirdEye cameras: mean pixel value ~0.1 (completely black)
- Other cameras: mean ~214-216, std ~0.8 (flat white/blown out)
- Error: `Failed to create GPU texture from Blender image`

**Current workaround:** Auto-switch to Cycles in background mode. But scenes tuned for EEVEE lighting may look different under Cycles.

**Proper fix options:**
1. Re-tune scenes for Cycles compatibility
2. Fix MCP bridge to work in foreground Blender (timers + keepalive)
3. Use headless Vulkan/EGL context (requires Blender build with EGL support)

## 16. Forensic Scene Quality Metrics (v22)

### 3-Track Audit System

| Track | Weight | Min Gate | Criteria Count |
|-------|--------|----------|----------------|
| Forensic Clarity (FC) | 40% | ≥7.0 | 5 |
| Physical Plausibility (PP) | 35% | ≥7.0 | 5 |
| Cinematic Presentation (CP) | 25% | ≥6.5 | 5 |

**Overall pass:** weighted ≥8.5 AND all track minimums met.

### Pixel-Level Scoring (Tier 1)
- Blank detection: mean pixel value <5 = score 0
- Contrast: std dev of pixel values
- Exposure: mean in [80-180] ideal range
- Detail: Laplacian variance
- Noise: Laplacian variance on 50 random 8×8 patches, /2000, penalty threshold 0.3

### Vision LLM Scoring (Tier 2)
- Claude Sonnet evaluates against 3-track rubric
- More nuanced than pixel metrics: catches semantic issues (wrong materials, missing markers)
- ~15s per image, ~$0.01-0.05 per call

### Score History
| Version | Overall | 3-Track Weighted | Key Change |
|---------|---------|-----------------|------------|
| v21 | 95.07 | 9.159 | Baseline |
| v22 | 96.21 | ~9.3 | Selective best-of merge, denoising |


## 17. 3D Library Code Index (v3) — READ FIRST, DON'T REDISCOVER

**MANDATORY**: Before writing ANY validation, mesh repair, or export optimization code, read `config/3d-forge/code-library.json`. It contains indexed, ready-to-use snippets with benchmarks.

### 17.1 Installed Libraries

| Library | Version | Language | Primary Use | Speed vs bpy |
|---------|---------|----------|-------------|--------------|
| **trimesh** | 4.11.5 | Python | Mesh validation, repair, wall thickness | **160x faster** |
| **gltf-validator** | npm | Node.js | Khronos-official GLB validation | N/A (new) |
| **gltf-transform** | npm | Node.js | GLB optimization (Draco, quantize, dedup) | N/A (new) |
| **Blender 3D Print Toolbox** | built-in | Python/bpy | Thickness, overhang, self-intersection | Same (in Blender) |

### 17.2 Blocked (needs Python 3.10+)

| Library | Use Case | Why We Want It |
|---------|----------|----------------|
| **pymeshlab** | Taubin smoothing, remeshing, Hausdorff distance | Fixes shade_smooth 36% failure rate, mesh quality metrics |

### 17.3 Quick Reference — Most Used Operations

**Validate a mesh (replaces 2000-line asset-validator.js mechanical checks):**
```bash
python3 scripts/3d-forge/trimesh-validator.py exports/3d-forge/{id}/model.stl --tier learning
```

**Validate GLB export (NEW — we had no GLB validation before):**
```javascript
const { validateBytes } = require('gltf-validator');
const data = new Uint8Array(fs.readFileSync('model.glb'));
const result = await validateBytes(data, { maxIssues: 50 });
```

**Optimize GLB for marketplace (30-50% size reduction):**
```javascript
// ES module
import { NodeIO } from '@gltf-transform/core';
import { quantize, dedup, weld, prune } from '@gltf-transform/functions';
const io = new NodeIO(); const doc = await io.read('model.glb');
await doc.transform(prune(), dedup(), weld(), quantize());
fs.writeFileSync('model-opt.glb', await io.writeBinary(doc));
```

**Smooth mesh when shade_smooth fails (100% success rate via trimesh):**
```python
import trimesh
mesh = trimesh.load('model.stl', force='mesh')
trimesh.smoothing.filter_taubin(mesh, iterations=10, lamb=0.5)
mesh.export('model_smooth.stl')
```

**Repair mesh (auto-fix degenerate faces, normals, holes):**
```python
import trimesh
mesh = trimesh.load('model.stl', force='mesh')
mesh.update_faces(mesh.nondegenerate_faces())
mesh.fix_normals()
trimesh.repair.fill_holes(mesh)
mesh.remove_unreferenced_vertices()
mesh.export('model_repaired.stl')
```

### 17.4 When to Use What

| Task | Use This | NOT This |
|------|----------|----------|
| Manifold/watertight check | `trimesh: mesh.is_watertight` | bpy vertex iteration via MCP |
| Triangle count | `trimesh: len(mesh.faces)` | bpy getMeshData via MCP |
| Wall thickness | `trimesh: ray casting` | bpy custom Python calculation |
| Degenerate faces | `trimesh: mesh.nondegenerate_faces()` | bpy polygon area check |
| GLB validation | `gltf-validator` | Nothing (we had no check) |
| GLB optimization | `gltf-transform` | Nothing (we exported raw) |
| Mesh smoothing fallback | `trimesh: filter_taubin()` | bpy shade_smooth (36% fail rate) |
| Camera/lighting setup | bpy via MCP (still needed) | trimesh (no render capability) |
| Rendering | Blender Cycles via MCP | trimesh (no renderer) |

### 17.5 Key Files
- **Code library KB**: `config/3d-forge/code-library.json` — all snippets, benchmarks, integration guide
- **Trimesh validator**: `scripts/3d-forge/trimesh-validator.py` — standalone CLI validator
- **Knowledge base**: `config/blender-knowledge-base.json` — materials, lighting, camera presets
- **KB Architecture**: `config/kb-architecture.json` — unified self-correction methodology

## 18. SELF-CORRECTION PROTOCOL (Lynn Cole 8-Step Loop)

**This is the #1 priority for pipeline quality. The pipeline must FLOW, not make excuses.**

### 18.1 The 8 Steps (every concept, every step)

1. **REQUIREMENT** — Parse concept JSON into atomic bpy.* API calls
2. **GENERATE** — Produce Python code from atomic requirements
3. **EXECUTE** — Run in Blender headless via MCP
4. **EVALUATE** — Different system checks result (not the producer itself)
5. **FINGERPRINT** — If error, SHA256(error_class + stack_frame + tool). Check known fixes.
6. **CORRECT** — Apply known fix OR generate hypothesis (max 3 attempts)
7. **RETEST** — Re-execute corrected code. Measure quality delta.
8. **PROMOTE** — If fix worked 3+ times → add to verified KB (Voyager rule)

### 18.2 Seven Governing Methodologies

| # | Method | Source | Rule |
|---|--------|--------|------|
| 1 | Fingerprinting | Datadog | Hash errors structurally, skip analysis for known fingerprints |
| 2 | External Source | Google SRE | Every KB entry needs verified source, not agent guesses |
| 3 | Multi-Agent Eval | Reflexion/MAR | Producer never evaluates its own output |
| 4 | Voyager Rule | Wang et al. | Only successful verified patterns stored in KB |
| 5 | MemGPT Tiers | Packer et al. | Buffer → consolidated → long-term archive |
| 6 | K8s Separation | Kubernetes | Detection and remediation are independent systems |
| 7 | Cole Loop | Lynn Cole | 8-step self-correcting generation, no human needed |

### 18.3 Memory Tiers (MemGPT)

- **Tier 1 (Buffer)**: `hourly-run-log.jsonl` — raw run data, current context only
- **Tier 2 (Consolidated)**: `autoresearch-state.json` — rolling 20-run KPIs and patterns
- **Tier 3 (Archive)**: `blender-knowledge-base.json` + `code-library.json` — permanent verified knowledge

### 18.4 Pipeline Flow Rules

- Pipeline MUST produce assets. Logging errors without fixing them is NOT acceptable.
- Failed concepts get re-queued with error context (producer retry fix v24)
- Producer does NOT exit(1) on partial failures — all concepts get attempted
- Feedback loop produces ACTIONABLE code changes, not "review reference images"
- Every run must target 3+ completed assets minimum

### 18.5 Critical Fixes (verified empirically)

- **Light energy**: Area lights need 150W+ minimum (500W key, 200W fill, 300W rim). Energy of 2.0 = invisible.
- **Engine casing**: bpy.context.scene.render.engine = 'CYCLES' (uppercase in bpy API)
- **Mesh aggregation**: Iterate `bpy.data.objects` with `visible_get()`, never rely on `active_object`
- **shade_smooth**: BLOCKED at 48.3% success. Use trimesh taubin_smooth as fallback.