# CAD Integration GitHub Issues — Ready to Post

Draft issues for `jabbertones-cloud/blender-mcp`, generated from `CAD_RESEARCH_REPORT.md` + `CAD_INTEGRATION_PLAN.md`.
Each issue is self-contained: problem, source justification, acceptance criteria, and how it composes with v3.1.0's CADAM contract.

**Suggested labels:** `cad-integration`, `v3.2`, plus tier label (`tier-1`, `tier-2`, `tier-3`, `tier-4`).
**NotebookLM source-of-truth:** https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813

---

## Issue #1 — `[T1] Add blender_topology_select for property-based face/edge selection`

**Labels:** `cad-integration`, `tier-1`, `parametric`, `priority-high`

### Problem
The CADAM v3.1.0 parameter loop (`blender_apply_params`) silently breaks any cached `script_id` that selects geometry by hardcoded index (`obj.data.faces[7]`). When a dimension parameter changes (e.g., `BOX_LENGTH`), face indices shift and downstream `chamfer`/`fillet`/`material` operations target the wrong geometry. This is the single biggest robustness gap blocking parametric agent loops.

### Source justification
> "Shape topology can be extracted from Shapes with selectors which return ShapeLists. ShapeLists offer methods for sorting, grouping, and filtering Shapes by Shape properties, such as finding a Face by area and selecting position along an Axis."
> — Build123d ([README](https://github.com/gumyr/build123d))

CadQuery, Build123d, FreeCAD, OnShape FeatureScript all use property-based selectors — Blender exposes geometry only by index.

### Proposed API
```python
@mcp.tool()
def blender_topology_select(
    object_name: str,
    kind: Literal["face", "edge", "vertex"],
    filter: dict,  # e.g. {"area": ">5", "normal_axis": "+Z"}
    sort_by: str | None = None,  # e.g. "z_max"
    index: int | slice = 0,
) -> list[int]:
    """Return geometry indices matching property filters. Survives dimension edits."""
```

### Acceptance criteria
- [ ] Filter operators: `>, <, >=, <=, ==` on `area`, `length`, `volume`, `index`
- [ ] `normal_axis` filter: `+X/-X/+Y/-Y/+Z/-Z`
- [ ] `sort_by`: `area_asc`, `area_desc`, `z_min`, `z_max`, etc.
- [ ] Selector runs in cached `script_id` context with **same indices guaranteed across `apply_params` re-runs** when topology is preserved
- [ ] Tests cover: re-run with edited dimension parameter still selects the "top face"
- [ ] Documented in `BPY_GENERATION_SYSTEM_PROMPT` with a few-shot example

### How it composes with CADAM
Generated scripts call `blender_topology_select` instead of indexing. The selector's parametric robustness is what makes `blender_apply_params` actually safe at any reasonable speed.

### Effort
Medium (~1.5 weeks)

---

## Issue #2 — `[T2] Add blender_sketch_pad canonical script_id template (FreeCAD-style)`

**Labels:** `cad-integration`, `tier-1`, `parametric`, `priority-high`

### Problem
There is no first-class sketch-on-plane → extrude primitive in Blender, so agents either invent ad-hoc bmesh sequences (brittle) or skip parametric workflows entirely. CadQuery, Build123d, and FreeCAD all anchor on this pattern.

### Source justification
> "In the PartDesign Workbench, create a PartDesign Body, then use PartDesign NewSketch and select the XY plane to draw the base sketch; then perform a PartDesign Pad to create a first solid."
> — FreeCAD docs ([Topological naming problem](https://wiki.freecad.org/Topological_naming_problem))

### Proposed API
Ship as a **canonical, server-blessed `script_id`** with a fixed PARAMETERS schema:
```python
# --- PARAMETERS ---
DATUM_PLANE = "XY"  # or a named datum from blender_datum_plane
SKETCH_VERTS_2D = [[0,0], [10,0], [10,5], [0,5]]  # closed polygon
DEPTH = 2.0
TAPER_DEG = 0.0
BOOLEAN_OP = "ADD"  # ADD | SUBTRACT | INTERSECT | NONE
TARGET_OBJECT = ""  # for non-NONE booleans
# --- /PARAMETERS ---
```
Subsequent extrusions reference its `script_id` and edit only the PARAMETERS block via `blender_apply_params`.

### Acceptance criteria
- [ ] Recipe lives at `.claude/skills/blender-mcp/recipes/sketch-pad-v0.1.0.md`
- [ ] Pre-seeded into the script cache at server boot with stable `script_id`
- [ ] Boolean op uses Manifold backend (Blender 4.x default)
- [ ] Test: 3-pad assembly via 3 `apply_params` calls produces correct geometry without re-LLM
- [ ] System prompt few-shot uses this recipe

### How it composes with CADAM
Sketch+pad is the first parametric primitive that proves the value of `apply_params` for actual CAD design (vs. just material/lighting tweaks). After landing, every recipe that needs an extruded shape references this `script_id` rather than re-implementing extrude logic.

### Effort
Medium (~1.5 weeks)

---

## Issue #3 — `[T3] Add blender_datum_plane convention + helper`

**Labels:** `cad-integration`, `tier-1`, `parametric`, `priority-medium`, `good-first-issue`

### Problem
Without datum planes, every sketch+pad anchors on raw vertex coordinates that drift with edits. Datums are how every parametric CAD library survives the topological-naming problem.

### Source justification
> "Use of supporting datum objects like planes and local coordinate systems is strongly recommended to produce models that aren't easily subject to such topological errors."
> — FreeCAD Topological Naming Problem doc

### Proposed API
```python
@mcp.tool()
def blender_datum_plane(
    name: str,
    origin: list[float],   # [x,y,z]
    normal: list[float],   # [x,y,z]
    x_axis: list[float] | None = None,  # for orientation; default = world-X projected
) -> dict:
    """Create a named, queryable datum plane. Persists across script runs."""
```
PARAMETERS block convention: datums are named UPPER_CASE constants:
```python
DATUM_FRONT = {"origin": [0,0,0], "normal": [0,1,0]}
DATUM_TOP   = {"origin": [0,0,5], "normal": [0,0,1]}
```
T2 (`blender_sketch_pad`) accepts either `"XY"` or a named datum.

### Acceptance criteria
- [ ] Datums survive `blender_apply_params` re-runs (stored as Blender Empties with custom property `datum_plane=True`)
- [ ] Helper functions: `find_datum(name)`, `align_to_datum(obj, datum)`
- [ ] Tests: datum referenced by name in PARAMETERS still resolves after re-run with new origin
- [ ] System prompt example showing `DATUM_FRONT` usage

### Effort
Small (~3 days)

---

## Issue #4 — `[T4] Add blender_csg_hull + blender_csg_diagnose`

**Labels:** `cad-integration`, `tier-1`, `parametric`, `priority-medium`, `good-first-issue`

### Problem
Blender 4.x already uses Manifold for booleans, but `hull` (the third major CSG op) is missing as a first-class operation. OpenSCAD, CadQuery, Build123d all expose `hull`. Additionally, when booleans fail (manifold/non-manifold violations), there is no diagnostic surface for the agent — it just gets a silent malformed mesh.

### Source justification
> "Composable: CSG operations (union, difference, hull) map naturally to how LLMs describe shapes."
> — `jkoets/OpenSCAD-MCP`

> "Geometry library for topological robustness."
> — [Manifold](https://github.com/elalish/manifold) (the lib Blender already ships)

### Proposed API
```python
@mcp.tool()
def blender_csg_hull(input_objects: list[str], result_name: str) -> dict:
    """Compute convex hull of N input meshes."""

@mcp.tool()
def blender_csg_diagnose(object_name: str) -> dict:
    """Returns: {is_manifold, intersection_curves: [...], non_manifold_edges: [...], holes: int}"""
```

### Acceptance criteria
- [ ] `hull` uses Manifold or scipy.spatial.ConvexHull as backend
- [ ] `diagnose` runs via `bmesh.ops.find_doubles` + manifold checks
- [ ] Output of `diagnose` is consumable by `blender_critique` (structured fields, not just text)
- [ ] Test: union of 2 cubes → diagnose returns `is_manifold=True`; deliberately-broken mesh → returns `is_manifold=False` with edge indices

### Effort
Small (~3 days)

---

## Issue #5 — `[T5] Add blender_skill_promote + blender_skill_search (Voyager pattern)`

**Labels:** `cad-integration`, `tier-1`, `ai_native`, `priority-high`, `large`

### Problem
`script_id` LRU cache (32 entries) is the in-memory skill cache, but it's volatile. Voyager (Wang et al. 2023) showed that **a persistent, queryable skill library** is the difference between a one-shot agent and a lifelong-learning one. The OpenClaw fleet should grow its skill base with every successful session.

### Source justification
> "Voyager consists of three key components: 1) an automatic curriculum that maximizes exploration, 2) an ever-growing skill library of executable code for storing and retrieving complex behaviors, and 3) a new iterative prompting mechanism..."
> — [Voyager](https://arxiv.org/abs/2305.16291)

### Proposed API
```python
@mcp.tool()
def blender_skill_promote(
    script_id: str,
    name: str,
    tags: list[str],
    description: str,
) -> str:
    """Promote a cached script to disk-backed skill DB. Returns skill_id."""

@mcp.tool()
def blender_skill_search(query: str, top_k: int = 5) -> list[dict]:
    """Embedding+rerank search over skills. Returns [{skill_id, name, score, tags, parameters_schema, description}]."""
```

### Acceptance criteria
- [ ] Backed by `~/.openclaw/skills/` (JSON manifest + script body) + an embedding index (sentence-transformers or OpenAI embeddings)
- [ ] Search uses BM25 + embedding rerank (hybrid)
- [ ] Promoted skills appear in `blender_list_available_assets`-style discovery
- [ ] `blender_apply_params(skill_id=..., params=...)` works (skill_id resolves to script body)
- [ ] Existing recipes (`.claude/skills/blender-mcp/recipes/`) auto-promoted at server boot
- [ ] Tests: promote → search → apply_params loop end-to-end without LLM

### Effort
Large (~3 weeks)

---

## Issue #6 — `[T6] Extend needs_input payload to blender_apply_params + router`

**Labels:** `cad-integration`, `tier-1`, `ai_native`, `good-first-issue`, `priority-medium`

### Problem
When `blender_apply_params` is called with insufficient overrides for a complex script, it errors out silently. Same for `blender_router_set_goal` when workflow params are missing. The agent then has to guess what was wrong, often regenerating the entire script.

### Source justification
> "Model-first clarification is the default for router_set_goal(...) on llm-guided: missing workflow parameters return a typed needs_input payload to the outer model first."
> — `PatrykIti/blender-ai-mcp` ([README](https://github.com/PatrykIti/blender-ai-mcp))

### Proposed API
On a missing required parameter, return:
```json
{
  "status": "needs_input",
  "needs_input": {
    "field": "DEPTH",
    "kind": "number",
    "min": 0.1,
    "max": 100,
    "default": 2.0,
    "description": "Extrusion depth in meters"
  }
}
```
Same shape returned by `blender_router_set_goal` for missing workflow choices, with `kind: "enum"` and a `choices` field.

### Acceptance criteria
- [ ] `blender_apply_params` returns `needs_input` for missing PARAMETERS-block values without defaults
- [ ] `blender_router_set_goal` returns `needs_input` for missing required workflow fields
- [ ] Partial answers persist across follow-up calls (existing session_state plumbing)
- [ ] Tests: agent can complete a 3-step `needs_input → answer → needs_input → answer → success` flow

### Effort
Small (~3 days)

---

## Issue #7 — `[T7] Add blender_ifc_assign_pset (BIM semantics)`

**Labels:** `cad-integration`, `tier-2`, `bim`, `priority-medium`

### Problem
Blender + Bonsai/BlenderBIM has all the IFC machinery, but no MCP-level surface. Agents can't assign IFC classes or property sets without dropping into raw bpy or IfcOpenShell scripts — defeating the CADAM contract.

### Source justification
> "...a specific IFC class must be assigned based on the nature of the product... Depending on the selected class, it is possible to associate dedicated attributes, Property Sets (PSets), and custom properties..."
> — [STEP→IFC paper](https://www.preprints.org/manuscript/202309.0541/v1)

### Proposed API
```python
@mcp.tool()
def blender_ifc_assign_pset(
    object_name: str,
    ifc_class: str,        # e.g. "IfcWall", "IfcDoor"
    pset_values: dict,     # {"Pset_WallCommon": {"FireRating": "60min", "LoadBearing": True}}
) -> dict:
    """Assign IFC class and property set values via IfcOpenShell."""
```
Designed to run inside a CADAM script:
```python
# --- PARAMETERS ---
PSET_VALUES = {"Pset_WallCommon": {"FireRating": "60min", "LoadBearing": True}}
# --- /PARAMETERS ---
```
`blender_apply_params` can flip semantic data without re-meshing.

### Acceptance criteria
- [ ] Uses IfcOpenShell as engine (no rolled-own IFC writer)
- [ ] Validates IFC class name against schema (IFC 4.3 by default)
- [ ] Validates Pset name against the assigned class (e.g., `Pset_WallCommon` only on `IfcWall`)
- [ ] Tests: assign via apply_params → export IFC → re-import → values preserved

### Effort
Medium (~1.5 weeks)

---

## Issue #8 — `[T8] Add blender_ifc_aggregate (assembly hierarchy)`

**Labels:** `cad-integration`, `tier-2`, `bim`, `priority-low`

### Problem
No first-class way to express "this is an assembly of N parts" in IFC terms. Agents end up flattening hierarchies or inventing parent/child collections.

### Source justification
> "Assemblies are mapped to the IfcElementAssembly class... the IfcRelAggregates relationship is used to explicitly model the hierarchical decomposition between the assembly and the entities it contains."
> — STEP→IFC paper

### Proposed API
```python
@mcp.tool()
def blender_ifc_aggregate(
    parent_name: str,        # the assembly
    parent_class: str = "IfcElementAssembly",
    children: list[str],     # object names
) -> dict:
    """Create IfcRelAggregates relationship."""
```

### Acceptance criteria
- [ ] Uses IfcOpenShell `ifc.create_entity('IfcRelAggregates', ...)`
- [ ] Children's existing IFC classes preserved
- [ ] Round-trip: create aggregate → export → re-import → hierarchy intact
- [ ] Composes with T7 (PSets on the parent assembly)

### Effort
Medium (~1 week)

---

## Issue #9 — `[T9] Add blender_ifc_organize_by_storey`

**Labels:** `cad-integration`, `tier-2`, `bim`, `priority-medium`

### Problem
Architectural scenes have an obvious organizing principle (building storeys) that Blender collections can mirror, but agents don't auto-organize this way today.

### Source justification
> "Collections are created by building a story, then an IFC type."
> — Speckle Blender connector

### Proposed API
```python
@mcp.tool()
def blender_ifc_organize_by_storey(
    storeys: list[dict],  # [{"name": "L1", "elevation": 0.0, "height": 3.5}, ...]
) -> dict:
    """Create IfcBuildingStorey + Blender collections; auto-assign by Z."""
```
PARAMETERS block convention:
```python
STOREYS = [
    {"name": "GroundFloor", "elevation": 0.0, "height": 3.5},
    {"name": "L1",          "elevation": 3.5, "height": 3.0},
]
```
`blender_apply_params` shifts elevations → all storey-tagged objects move atomically.

### Acceptance criteria
- [ ] Creates `IfcBuildingStorey` entities
- [ ] Blender collections named `Storey_<name>` with custom property `ifc_storey_id`
- [ ] Auto-classification: object Z-min within `[elevation, elevation+height]` → assigned to that storey
- [ ] Re-running with edited heights atomically shifts assigned objects

### Effort
Medium (~1.5 weeks)

---

## Issue #10 — `[T10] Add blender_ifc_hash_diff (BIM verification)`

**Labels:** `cad-integration`, `tier-2`, `bim`, `verification`, `good-first-issue`

### Problem
After an edit, no fast way to know what changed in semantic terms (added/removed/changed IFC entities). Agents resort to viewport diffs which miss semantic-only changes.

### Source justification
> "...whether 2 successively exported IFC building models are different by testing whether entity instances of the latest are present in the original one or entity instances of the original one are present in the latest version."
> — [IfcOpenShell Academy](https://academy.ifcopenshell.org/)

### Proposed API
```python
@mcp.tool()
def blender_ifc_hash_diff(before_path: str, after_path: str) -> dict:
    """Returns: {added: [{guid, class}, ...], removed: [...], changed: [{guid, class, fields_changed}, ...]}"""
```

### Acceptance criteria
- [ ] Hash strategy = `(class, sorted_attribute_tuple)` per the IfcOpenShell Academy tutorial
- [ ] Output schema is `blender_critique`-consumable
- [ ] Test: edit one wall's `FireRating` → diff returns `{changed: [{guid, "IfcWall", ["FireRating"]}]}`

### Effort
Small (~3 days)

---

## Issue #11 — `[T11] Add blender_compare_renders`

**Labels:** `cad-integration`, `tier-3`, `verification`, `good-first-issue`

### Problem
Many `apply_params` loops compare a "before" and "after" render. Today the VLM has to score them separately, doubling token cost.

### Source justification
> "compare_renders | Side-by-side before/after renders for visual comparison"
> — `quellant/openscad-mcp`

### Proposed API
```python
@mcp.tool()
def blender_compare_renders(
    before_id: str,         # snapshot id from blender_snapshot
    after_id: str,
    layout: Literal["horizontal", "vertical", "diff"] = "horizontal",
    annotate: bool = True,  # add "BEFORE"/"AFTER" labels
) -> dict:
    """Returns {composite_path, perceptual_diff: 0-1}."""
```

### Acceptance criteria
- [ ] Uses Pillow for layout (already a dep via vision tools)
- [ ] Optional `diff` layout shows pixel-diff heatmap
- [ ] `perceptual_diff` via SSIM
- [ ] `blender_critique` can take `compare_render_id` directly

### Effort
Small (~2 days)

---

## Issue #12 — `[T12] Add blender_segment_and_describe (SAM + VLM verifier)`

**Labels:** `cad-integration`, `tier-3`, `verification`, `large`

### Problem
The VLM judge in `blender_verify`/`blender_critique` can confirm "the chair is in frame" but cannot easily confirm "the *intended* chair is in frame, in the *intended* pose". SAM-based segmentation closes the gap.

### Source justification
> "segment_and_analyze - Colorize regions with SAM, then have VLM describe each"
> — `proximile/FreeCAD-MCP`

### Proposed API
```python
@mcp.tool()
def blender_segment_and_describe(
    snapshot_id: str,
    target_objects: list[str] | None = None,  # optional; default = all in frame
    sam_model: Literal["mobile-sam", "sam-vit-h"] = "mobile-sam",
) -> dict:
    """Returns {masks: [{object_name, bbox, area}], descriptions: [{mask_id, vlm_text}]}."""
```

### Acceptance criteria
- [ ] Uses Mobile-SAM by default for speed (~50ms/image)
- [ ] Object IDs from Blender pass / cryptomatte — not just SAM auto-mask
- [ ] VLM caption per mask via existing OpenRouter/Gemini routes
- [ ] Plugs into `blender_verify` as a new constraint type: `vlm_caption_matches`

### Effort
Large (~3 weeks)

---

## Issue #13 — `[T13] Add blender_step_to_ifc_bridge (mechanical → BIM round-trip)`

**Labels:** `cad-integration`, `tier-4`, `interop`, `large`

### Problem
Mechanical CAD (CadQuery/Build123d) and architectural CAD (Bonsai) live in different worlds. The STEP→IFC paper outlines a 4-step framework that bridges them; expose it as one tool.

### Source justification
> "...the resulting geometries (usually in the form of meshes) are converted into IFC entities, to which the previously processed attributes and properties are associated."
> — STEP→IFC paper

### Proposed API
```python
@mcp.tool()
def blender_step_to_ifc_bridge(
    cadquery_script_id: str,    # a CADAM script that emits a Build123d/CadQuery shape
    target_ifc_class: str,      # e.g. "IfcDuctSegment"
    pset_values: dict,
    simplify_below_volume_m3: float = 0.001,  # drop screws/flanges
) -> dict:
    """Evaluate parametric CAD → simplified mesh → wrap as IFC entity."""
```

### Acceptance criteria
- [ ] Geometric simplification before IFC wrap (per the paper)
- [ ] PSet attached to the wrapping entity (T7)
- [ ] If `cadquery_script_id`'s PARAMETERS change via `apply_params`, the IFC wrapping re-emits

### Effort
Large (~3 weeks; depends on T7)

---

## Issue #14 — `[T14] Add blender_blendquery_eval (CadQuery in PARAMETERS-block scripts)`

**Labels:** `cad-integration`, `tier-4`, `parametric`, `interop`

### Problem
Direct CadQuery/Build123d evaluation inside Blender unlocks the full BRep parametric expressiveness. `uki-dev/blendquery` proves the integration is feasible.

### Source justification
> "CadQuery and Build123d integration for Blender"
> — [uki-dev/blendquery](https://github.com/uki-dev/blendquery)

### Proposed API
```python
@mcp.tool()
def blender_blendquery_eval(
    script_id: str,         # a CADAM script that imports cadquery / build123d
    target_object: str | None = None,   # default: name from PARAMETERS.OUTPUT_NAME
) -> dict:
    """Run CadQuery/Build123d under PARAMETERS-block contract; mesh via Manifold."""
```

### Acceptance criteria
- [ ] Detects CadQuery vs Build123d at parse time
- [ ] PARAMETERS schema standardized: `OUTPUT_NAME`, optional `MESH_RESOLUTION`
- [ ] Errors map to `needs_input` (T6) when params malformed
- [ ] Test: a single Build123d script with `apply_params` swept across 5 dimensions produces 5 distinct meshes without re-LLM

### Effort
Medium (~1.5 weeks)

---

## Issue #15 — `[INFRA] Migrate product_animation_tools.py raw execute_python sites to PARAMETERS-block`

**Labels:** `cad-integration`, `infra`, `tech-debt`, `good-first-issue`

### Problem
v3.1.0 ships the new contract but 9 raw `execute_python` call sites remain in `server/product_animation_tools.py`. Each one bypasses the LRU cache, AST gate, and parameter loop.

### Acceptance criteria
- [ ] All 9 sites converted to `blender_run_bpy_script(require_parameters_block=True, cache=True)`
- [ ] Each script gets a stable `script_id` and a documented PARAMETERS schema
- [ ] Existing tests still pass; product animation presets still work
- [ ] CHANGELOG note added

### Effort
Small (~1 day, ~150 LOC delta)

---

## Issue #16 — `[INFRA] Update .claude/skills/blender-mcp/SKILL.md with v3.1.0 + Tier taxonomy`

**Labels:** `cad-integration`, `infra`, `docs`, `good-first-issue`

### Problem
SKILL.md was write-protected during the v3.1.0 ship. Needs the full CADAM contract section, asset-workflow rule, T1–T14 tool taxonomy, PARAMETERS block conventions, and Bonsai → MCP mapping.

### Acceptance criteria
- [ ] CADAM contract section copied from `docs/CHANGELOG.md` v3.1.0 entry
- [ ] Tier 0/1/2/3/4 tool taxonomy table from `docs/CAD_INTEGRATION_PLAN.md`
- [ ] PARAMETERS-block convention table (`PSET_VALUES`, `STOREYS`, `DATUM_*`, `SKETCH_VERTS_2D`)
- [ ] "Reach for `apply_params` first" rule prominently placed
- [ ] Bonsai/IfcOpenShell idiom → blender-mcp BIM tool mapping (T7–T10)

### Effort
Small (~2 hours)

---

## Issue #17 — `[EVAL] Adopt BlenderGym 245-scene benchmark alongside LEGO-Eval`

**Labels:** `cad-integration`, `eval`, `priority-low`, `medium`

### Problem
LEGO-Eval is the only general benchmark in CI. BlenderGym (arxiv 2504.01786) covers 5 task families (procedural geometry, lighting, materials, blend shapes, object placement) across 245 scenes — much richer signal for catching regressions in T1–T14.

### Source justification
> "BlenderGym consists of 245 hand-crafted Blender scenes across 5 key graphics editing tasks: procedural geometry editing, lighting adjustments, procedural material design, blend shape manipulation, and object placement."
> — [BlenderGym paper](https://arxiv.org/abs/2504.01786)

### Acceptance criteria
- [ ] Adapter in `eval/blender_gym/` (placeholder exists)
- [ ] Per-task scores reported (5 dimensions)
- [ ] Baseline established for v3.1.0
- [ ] Regression gate in CI: any T-series PR must not regress more than 5pp on any dimension

### Effort
Medium (~2 weeks)

---

# Summary

| # | Tool | Tier | Priority | Effort |
|---|---|---|---|---|
| #1 | `blender_topology_select` | 1 | High | M |
| #2 | `blender_sketch_pad` | 1 | High | M |
| #3 | `blender_datum_plane` | 1 | Medium | S |
| #4 | `blender_csg_hull` + `_diagnose` | 1 | Medium | S |
| #5 | `blender_skill_promote` + `_search` | 1 | High | L |
| #6 | `needs_input` payload extension | 1 | Medium | S |
| #7 | `blender_ifc_assign_pset` | 2 | Medium | M |
| #8 | `blender_ifc_aggregate` | 2 | Low | M |
| #9 | `blender_ifc_organize_by_storey` | 2 | Medium | M |
| #10 | `blender_ifc_hash_diff` | 2 | Medium | S |
| #11 | `blender_compare_renders` | 3 | Medium | S |
| #12 | `blender_segment_and_describe` | 3 | Low | L |
| #13 | `blender_step_to_ifc_bridge` | 4 | Low | L |
| #14 | `blender_blendquery_eval` | 4 | Medium | M |
| #15 | INFRA: migrate `product_animation_tools.py` | — | Medium | S |
| #16 | INFRA: update SKILL.md | — | Medium | S |
| #17 | EVAL: BlenderGym adoption | — | Low | M |

**Recommended Sprint 1 (this week):** #3, #4, #6, #10, #11, #15, #16 — all Small.
**Recommended Sprint 2 (next 2 weeks):** #1, #2, #7, #9 — Medium parametric core + first BIM tools.
**Recommended Sprint 3 (4–6 weeks):** #5, #8, #13, #14, #17.
**Recommended Sprint 4 (7–10 weeks):** #12.
