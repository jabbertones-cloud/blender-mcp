# CAD Cross-Pollination Research — Improving the OpenClaw Blender MCP

**Date:** 2026-04-26
**Repo:** `jabbertones-cloud/blender-mcp` (v3.0.0)
**Scope:** Find features, flows, and architectural ideas in the broader CAD ecosystem worth importing into the Blender MCP.
**Method:** Gemini-grounded research → URL verification → NotebookLM ingestion → citation-forced synthesis. Backed by 106 sources in the dedicated [CAD for Blender MCP NotebookLM notebook](https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813).
**Cost of research run:** ~$0.023 in Gemini API calls (vs. ~$1–$2 in Claude tokens for equivalent depth).

---

## Executive Summary

The Blender MCP today is best-in-class for **mesh/asset workflows with VLM verification** but is underweight on the four things modern CAD agents actually need:

1. **Parametric, history-aware modeling** (sketch → extrude, fillet/chamfer DSL, datum planes, robust booleans).
2. **Workflow-level macros** instead of atomic `bpy` ops.
3. **A persistent skill library** the agent can grow over time (Voyager pattern).
4. **BIM/IFC semantics** for organizing scenes by building storey, type, and property set.

The 12 highest-leverage features below were each justified by a direct source quote in the notebook. They are ordered by the ratio of (impact on agent task success) ÷ (engineering effort), not by category.

A surprising finding: the existing **`PatrykIti/blender-ai-mcp`** repo is the single most architecturally aligned reference — it's already running the goal-first / planner-actor-critic / deterministic-measurement pattern that this report recommends adopting more aggressively. Worth a deep read before any new design.

---

## What Already Exists in `jabbertones-cloud/blender-mcp` v3.0.0

Based on `server/blender_mcp_server.py`, `agent_loop.py`, `spatial_tools.py`, `extended_tools.py`, `verify.py`, `drift_guard.py`:

- **Agent loop tools (6):** `blender_router_set_goal`, `blender_plan`, `blender_act`, `blender_critique`, `blender_verify`, `blender_session_status`
- **Spatial tools (4):** `blender_spatial`, `blender_semantic_place`, `blender_dimensions`, `blender_floor_plan`
- **Extended tools (9):** `blender_camera_advanced`, `blender_uv_unwrap`, `blender_texture_bake`, `blender_lod`, `blender_vr_optimize`, `blender_gaussian_splat`, `blender_grease_pencil`, `blender_snapshot`, `blender_drift_status`
- **Verification (verify.py):** 9 GCS constraint types — `on_top_of`, `clearance`, `inside`, `not_overlapping`, `facing`, `vertex_count_range`, `triangulated`, `has_material`, `axis_aligned`
- **Drift guard:** EMA cosine-distance behaviour vector across scene snapshots
- **OTEL telemetry:** `blender.objects_delta`, `blender.vertices_delta` per tool call (action-hallucination signal)
- **Eval harness:** `eval/run.py` with `lego_eval` and `blender_gym` adapters
- **Recipes:** 6 in `.claude/skills/blender-mcp/recipes/` (character rigging, cyberpunk desk, forensic accident, procedural wood floor, product viz 3-point, tutorial reproduction)
- **Safety gate:** `OPENCLAW_ALLOW_EXEC=0` default with AST pre-pass on `blender_execute_python`
- **Total tool surface:** ~80 tools across 23 categories

---

## Top 12 Features to Adopt (Ranked by Impact ÷ Effort)

Each feature is grounded in a direct quote from a source in the notebook. Effort is rough order-of-magnitude (Small = days, Medium = 1–3 weeks, Large = 1–3 months).

### 1. Macro / Workflow Tool Tier — replace atomic-tool flooding (PROCEDURAL, Medium) ⭐⭐⭐
> *"Macro tools are the preferred LLM-facing layer for meaningful task-sized work."* — `PatrykIti/blender-ai-mcp`

**Why:** Today the agent picks from ~80 atomic tools. A 3-tier surface (atomic → macro → workflow) is Karpathy-grade context economy. `macro_finish_form`, `macro_relative_layout`, `workflow_assemble_product_shot` collapse 8–15 atomic calls into one bounded operation.

**Builds on:** Current tool surface stays, but `llm-guided` profile defaults to surfacing macros only.

**Reference impl:** `PatrykIti/blender-ai-mcp`'s "tiny, search-first bootstrap layer".

### 2. Sketch-and-Pad Solid Creation (PARAMETRIC, Medium) ⭐⭐⭐
> *"In the PartDesign Workbench, create a PartDesign Body, then use PartDesign NewSketch and select the XY plane to draw the base sketch; then perform a PartDesign Pad to create a first solid."* — FreeCAD docs

**Proposed tool:** `blender_sketch_and_pad(plane, sketch_2d, depth, taper)` → emits a clean mesh + records the sketch+pad pair on a `parametric_history` collection so subsequent edits can re-derive.

**Source libraries:** FreeCAD PartDesign, Build123d (`Plane.XZ * Pos(X=5) * Rectangle(1, 1)`), CadQuery workplanes, OnShape sketch-extrude.

### 3. Datum Plane Anchoring (PARAMETRIC, Small) ⭐⭐⭐
> *"Use of supporting datum objects like planes and local coordinate systems is strongly recommended to produce models that aren't easily subject to such topological errors."* — FreeCAD Topological Naming Problem doc

**Proposed tool:** `blender_create_datum_plane(name, origin, normal, x_axis)` + `blender_locate_on_workplane(datum_id, ...)`.

**Why:** CadQuery/Build123d/FreeCAD all anchor features on named datums to survive edits. Without datums, every selection-by-vertex-index re-breaks on edit. Cheap to add, foundational for everything else parametric.

### 4. Self-Evolving Skill Library (Voyager pattern) (AI_NATIVE, Large) ⭐⭐
> *"Voyager consists of three key components: 1) an automatic curriculum that maximizes exploration, 2) an ever-growing skill library of executable code for storing and retrieving complex behaviors, and 3) a new iterative prompting mechanism..."* — Voyager (arxiv 2305.16291)

**Proposed tool:** `blender_skill_save(name, code, deps)` + `blender_skill_search(query)` backed by an embedding index over recipes/successful action chains.

**Builds on:** existing `.claude/skills/blender-mcp/recipes/` directory — promote it from static markdown to a queryable skill DB. Each successful agent run becomes a candidate skill.

### 5. Topological Selectors / Property-Based Filtering (PARAMETRIC, Medium) ⭐⭐
> *"Shape topology can be extracted from Shapes with selectors which return ShapeLists. ShapeLists offer methods for sorting, grouping, and filtering Shapes by Shape properties, such as finding a Face by area and selecting position along an Axis..."* — Build123d

**Proposed tool:** `blender_select_by_topology_property(filter={'kind':'face', 'area':'>5', 'normal_axis':'+Z', 'sort_by':'z_max', 'index':0})`.

**Why:** Index-based selection (`obj.data.faces[7]`) breaks every edit. Property-based selection survives topology change — this is the single biggest robustness fix for parametric agent loops.

### 6. CSG-Style Algebraic Composition (PARAMETRIC, Medium) ⭐⭐
> *"Composable: CSG operations (union, difference, hull) map naturally to how LLMs describe shapes."* — `jkoets/OpenSCAD-MCP`
> *"Operator-driven modeling (obj += sub_obj, Plane.XZ * Pos(X=5) * Rectangle(1, 1)) for algebraic, readable, and composable design logic"* — Build123d

**Proposed tool:** `blender_csg(op, a, b, hull=False)` with **Manifold** as the boolean backend (already merged into Blender 4.x — exactly what `elalish/manifold` and the Cherchi 2022 paper describe). Add `hull` because hull is the missing third operator that every CAD lib has and Blender lacks.

### 7. Structured Clarification Flow (`needs_input`) (AI_NATIVE, Small) ⭐⭐
> *"Model-first clarification is the default for router_set_goal(...) on llm-guided: missing workflow parameters return a typed needs_input payload to the outer model first."* — `PatrykIti/blender-ai-mcp`

**Proposed tool:** Extend `blender_router_set_goal` and `blender_plan` to return a typed `{needs_input: {field, kind, choices, default}}` instead of erroring on missing params. Cheap to add, immediate UX win.

### 8. Vision + SAM Segmentation Verification (VERIFICATION, Large) ⭐⭐
> *"segment_and_analyze - Colorize regions with SAM, then have VLM describe each"* — `proximile/FreeCAD-MCP`

**Proposed tool:** `blender_segment_and_describe(viewport_capture)` → SAM mask per object, then VLM caption per mask. Catches "the chair is in frame" when in fact it's the wrong chair.

**Builds on:** existing `blender_viewport_capture` and the VLM judge in `blender_verify`/`blender_critique`.

### 9. IFC Pset / Building-Storey Organization (BIM, Medium) ⭐
> *"Collections are created by building a story, then an IFC type."* — Speckle Blender connector
> *"...a specific IFC class must be assigned... Depending on the selected class, it is possible to associate dedicated attributes, Property Sets (PSets), and custom properties..."* — STEP→IFC conversion paper

**Proposed tools:** `blender_organize_by_building_storey()`, `blender_assign_ifc_pset(obj, pset_name, props)`, `blender_create_ifc_aggregation(parent, children)`. Use `IfcOpenShell` Python lib as the engine. Lets agents work on architectural scenes without inventing their own taxonomy.

### 10. Side-by-Side Render Comparisons (VERIFICATION, Small) ⭐
> *"compare_renders | Side-by-side before/after renders for visual comparison"* — `quellant/openscad-mcp`

**Proposed tool:** `blender_compare_renders(before_id, after_id, layout='horizontal')` — single composite image the VLM can score in one call instead of two. Pairs naturally with the existing `blender_snapshot` and `blender_render_quality_audit`.

### 11. Non-Destructive Modifier Preservation on Re-Ingest (PROCEDURAL, Medium) ⭐
> *"Update your models while preserving any modifiers you've applied in Blender. When new versions arrive from your team, your subdivision surfaces, arrays, boolean operations, and custom modifications stay intact..."* — Speckle for Blender

**Proposed tool:** `blender_reimport_preserve_modifiers(file, target_obj)` — diffs the new geometry against the existing modifier stack, preserves user/agent-added modifiers, replaces only the base mesh.

### 12. IFC Hash-Based Differencing for Versioning (BIM/VERIFICATION, Small) ⭐
> *"...whether 2 successively exported IFC building models are different by testing whether entity instances of the latest are present in the original one or entity instances of the original one are present in the latest version."* — IfcOpenShell Academy

**Proposed tool:** `blender_compare_ifc_hashes(before_path, after_path)` — emits a structured diff (added / removed / changed entities) that the agent can use as a verification step on multi-turn BIM edits.

---

## Reference Architecture: Patterns Borrowed From Each Source Repo

| Source | Patterns to copy |
|---|---|
| **`PatrykIti/blender-ai-mcp`** | Goal-first router, atomic→macro→workflow tier, model-first clarification, deterministic measurement, vision-assisted verification (already 80% aligned with v3.0.0 — read its source as the gold reference) |
| **`ahujasid/blender-mcp` (upstream)** | Socket-based bridge architecture (already in place), handler registration patterns |
| **`PatrykIti` + Voyager** | Skill library that grows with use; auto-curriculum |
| **LL3M (arxiv 2508.08228 + threedle/ll3m)** | 6-agent specialization (planner, retrieval, coding, critic, verification, user feedback). RAG over Blender API docs. Self-critique using both code + visuals |
| **BlenderGym (arxiv 2504.01786)** | 245-scene benchmark across 5 task types — adopt as second eval after LEGO-Eval. Per-dimension scoring (geometry / lighting / material / blend-shape / placement) |
| **CadQuery + Build123d** | Workplane-relative positioning, ShapeList selectors, algebraic composition operators |
| **FreeCAD PartDesign** | Datum-anchored sketch+pad, topological naming as a *known problem* with documented mitigations |
| **OpenSCAD MCP variants (5 of them)** | Code-as-CAD philosophy, deterministic CSG, hull as a first-class op |
| **FreeCAD MCP variants (5 of them)** | Reference patterns for `Sketcher.Sketch` + `PartDesign` exposure to LLMs (esp. `proximile/FreeCAD-MCP` for SAM integration, `bonninr/freecad_mcp` for FreeCAD ↔ Claude wiring) |
| **OnShape MCPs** | FeatureScript as the upper bound on parametric expressiveness |
| **IfcOpenShell + Bonsai (BlenderBIM 2.0)** | The actual implementation Blender already has for BIM; expose as MCP tools rather than reinventing |
| **Speckle Blender connector** | IFC ↔ Blender pipeline; modifier-preserving re-ingest |
| **Manifold (elalish) + Cherchi 2022** | Robust booleans (Blender 4.x already uses Manifold internally — surface it explicitly with diagnostics) |
| **ReAct (arxiv 2210.03629) + Reflexion (arxiv 2303.11366)** | Verbal-RL critique loop format. The existing `blender_critique` should follow the Reflexion buffer pattern |
| **Voyager (arxiv 2305.16291)** | Skill library + automatic curriculum + iterative prompting |
| **CGAL PMP / libigl / pmp-library** | Backend choices for any new robust-mesh-processing tools beyond what Manifold covers |
| **DeepCAD / Text2CAD / Text-to-CadQuery / CADmium / cadrille** | Empirical results on what an LLM can/can't do for parametric CAD; useful as eval baselines |

---

## Interop Matrix — Round-Tripping CAD ↔ Blender

| From | To | Via | Status today | Suggested MCP tool |
|---|---|---|---|---|
| STEP / IGES | Blender mesh | CadQuery → STL → import | Manual | `blender_import_step(path, healing='auto')` (uses OCP/PythonOCC) |
| Blender mesh | STEP | not direct | Painful | `blender_export_brep(obj, format='step')` (mesh→BRep healing) |
| IFC | Blender collections | IfcOpenShell / Bonsai / Speckle | Works (manual) | `blender_import_ifc(path, classify=True)` |
| OnShape | Blender | OnShape API → glTF | Manual | `blender_onshape_pull(doc_id, version)` |
| FreeCAD `.FCStd` | Blender | FreeCAD-MCP → STEP/STL | Works via FreeCAD-MCP | `blender_freecad_pull(file)` (delegates to `neka-nat/freecad-mcp`) |
| Blender | USD | bpy USD exporter (built-in) | Works | Surface `blender_export_usd(payload, asset_resolver_paths)` |
| USD | Blender | bpy USD importer | Works | `blender_import_usd(path, prim_path)` |
| Blender mesh | CadQuery (parametric) | `uki-dev/blendquery` | Possible | `blender_blendquery_eval(cq_script)` |

---

## Suggested Roadmap (8–12 weeks if a single dev; 4 if the agent fleet helps)

**Phase A (Week 1–2): Foundation**
- #1 Macro/workflow tool tier (codify what `PatrykIti/blender-ai-mcp` already does)
- #3 Datum plane anchoring
- #7 `needs_input` clarification flow
- #10 `compare_renders`

**Phase B (Week 3–5): Parametric core**
- #2 `sketch_and_pad`
- #5 Topological selectors
- #6 CSG algebraic composition w/ Manifold

**Phase C (Week 6–8): BIM + Skill loop**
- #9 IFC/Pset/storey tools (wrap IfcOpenShell)
- #4 Self-evolving skill library (promote `recipes/` → embedding-indexed DB)
- #11 Modifier-preserving re-ingest
- #12 IFC hash diff

**Phase D (Week 9–12): Verification depth**
- #8 SAM segmentation verifier
- Adopt BlenderGym 245-scene eval as second baseline alongside LEGO-Eval

---

## Hard truths (the reframe-test section)

1. **Most "AI CAD" repos are demos, not production.** Of the 13 CAD MCP variants in the notebook, only `PatrykIti/blender-ai-mcp` and the v3.0.0 OpenClaw fork show production-shaped patterns (goal-first, deterministic verify, drift detection). Don't copy the demos uncritically.
2. **Blender is mesh-first; pretending it's parametric is asking for pain.** Expose a parametric *layer* (sketch → pad → modifier history collection) but don't try to make every Blender op rewindable. The 80/20 is "sketch+pad+fillet/chamfer", not "full feature tree".
3. **Robust booleans are already solved upstream.** Manifold is already in Blender 4.x. The win is *exposing the boolean diagnostic surface* (intersection curves, manifold/non-manifold report) — not picking a new boolean library.
4. **BIM via IfcOpenShell, not from scratch.** Bonsai (BlenderBIM 2.0) is already mature. The MCP's job is to *expose* its API to the agent, not reinvent IFC. ~10 thin wrapper tools is the whole job.
5. **Agent eval matters more than tool count.** v3.0.0 has 80 tools and beats SOTA on LEGO-Eval. Adding 30 more tools without raising eval scores is regression. Each new tool should land with a measurable BlenderGym/LEGO-Eval delta.

---

## NotebookLM source-of-truth

**Notebook:** [CAD for Blender MCP — Cross-Pollination Research](https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813) (106 sources, 4 categories)

**Routing map slug:** `blender-mcp-cad` (added to `config/notebooklm-map.json`)

**Companion notebooks:**
- [skill: blender-mcp-ops](https://notebooklm.google.com/notebook/a908f9ba-94a8-4d5d-910f-8806e74a814e) (42 sources — operations & safety)
- [skill: blender-guru](https://notebooklm.google.com/notebook/c5d4caa8-e2bc-4ba6-8670-27ea49b7c7ec) (75 sources — curriculum & rubric)
- [Claude AI and Blender MCP Integration Guide](https://notebooklm.google.com/notebook/a00aa84b-da80-4be7-b388-cbcb566853a1) (299 sources — broad capture, near cap)

**Source mix in the new notebook:**
- 18 parametric/B-Rep (CadQuery, Build123d, OpenSCAD, FreeCAD, OCP, Solvespace, Manifold, Trimesh, OnShape, OpenCascade)
- 16 procedural (Geometry Nodes manual + API, Sverchok, Houdini HDA, USD/OpenUSD, Geometry-Script, NodeToPython, geonodes, blendquery)
- 13 BIM (IfcOpenShell, Bonsai, Speckle stack, buildingSMART IFC 4.3)
- 32 AI-native CAD (Zoo.dev, 5 FreeCAD-MCPs, 4 OpenSCAD-MCPs, 3 OnShape-MCPs, BlenderGPT, ThreeStudio, LL3M, BlenderGym, Voyager, ReAct, Reflexion, Text2CAD, Text-to-CadQuery, CADmium, cadrille, DeepCAD, TransCAD, Cherchi mesh booleans)
- + auto-discovered companions surfaced by NotebookLM (BuildArena physics-aligned LLM benchmark, ERGOBOSS, "What's in a Name? Assembly-Part Semantic Knowledge", Snyk's MCP-CAD survey)

---

## How this report was produced

1. Asked clarifying questions (CAD scope, improvement focus, deliverable shape) via AskUserQuestion.
2. Loaded 4 skills: `blender-mcp-ops`, `blender-guru`, `notebooklm-master`, `research`.
3. Inventoried `openclaw-blender-mcp` repo for current tool surface.
4. Created dedicated NotebookLM notebook `blender-mcp-cad`.
5. Ran `gemini-research.js` (Gemini Flash, grounded → URL-verified fallback) for each of the 4 CAD paradigms — ~$0.023 total.
6. Verified all 38 Gemini-returned URLs (50% hallucination rate when grounding fell back; pattern matches the documented gotcha in `CLAUDE.md`).
7. Hand-curated 30 tier-1 canonical sources Gemini missed.
8. Did 8 targeted WebSearch passes for high-tier gaps (BlenderGym, LL3M, Cherchi booleans, Voyager, ReAct/Reflexion, FreeCAD-MCP, OpenSCAD-MCP, OnShape-MCP, DeepCAD/Text2CAD).
9. Bulk-ingested 76 verified URLs into NotebookLM via `mcp__notebooklm-mcp__source_add` (one at a time — bulk `urls` param had a serialization quirk).
10. Ran 3 NotebookLM queries with citation-forcing prompts ("quote the source sentence", "mark unsupported as [UNSUPPORTED] and drop").
11. Synthesized this report and the companion `CAD_FEATURE_BACKLOG.md`.

**Net:** every recommendation in this report has a direct quote from a tier-1 source backing it.
