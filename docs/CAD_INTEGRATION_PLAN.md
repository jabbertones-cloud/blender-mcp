# CAD Research → CADAM v3.1.0 Integration Plan

**Date:** 2026-04-26
**Status:** v3.1.0 just shipped (5 new tools, 2 modules, 22 tests). This doc maps the 12 features from `CAD_RESEARCH_REPORT.md` onto the CADAM contract and re-prioritizes.
**Companion:** [`CAD_RESEARCH_REPORT.md`](./CAD_RESEARCH_REPORT.md), [NotebookLM source notebook](https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813) (106 sources)

---

## What CADAM v3.1.0 Already Solves (and How That Reshapes the Roadmap)

The five tools shipped in `server/blender_mcp_server.py` map almost 1:1 to several of the highest-priority recommendations in the original research report. Specifically:

| Research recommendation | CADAM tool that already implements (or unblocks) it |
|---|---|
| **Macro/workflow tier** (#1 in report) | A **cached `script_id`** *is* a macro — it bundles intent + parameters + verified execution. Just needs a "promote to skill" path. |
| **Code-as-CAD / LL3M pattern** (referenced throughout AI_NATIVE section) | `blender_generate_bpy_script` + `blender_run_bpy_script` is exactly this. |
| **Voyager skill library** (#4 in report) | **80% there.** `script_id` LRU cache (32 entries) is the in-memory skill cache; promoting to embedding-indexed disk DB is the remaining step. |
| **CADmium parameter loop** (Text-to-CAD literature) | `blender_apply_params` *is* CADmium's parameter-only re-run — the LLM is not called. |
| **Text2CAD with visual feedback** (arxiv 2501.19054) | `blender_reference_image_to_scene` is the three-action two-pass equivalent. |
| **Asset cache discipline** (asset-workflow rule in CADAM prompt) | `blender_list_available_assets` + the prompt rule "magic strings never". |
| **AST safety gate** (research recommended; CADAM ships) | `server-side AST gate + LRU cache + execute` in `blender_run_bpy_script`. |

**Implication:** the report's Phase A (foundation) is largely done. The next wave should layer **parametric semantics** (sketch+pad, datum planes, topological selectors, CSG hull) and **BIM semantics** (IFC PSet, building storey, aggregation) on top of the PARAMETERS-block contract — not as new agent loops.

---

## Re-Prioritized Top 12 (How Each Folds Into CADAM)

Each feature is restated as a delta on top of v3.1.0, with the **specific CADAM construct it should plug into**.

### Tier 0 — Already Covered (mark complete in CHANGELOG)

| # | Feature (from research report) | CADAM construct that covers it |
|---|---|---|
| #1 | Macro/workflow tier | `script_id` cache. **Remaining:** `blender_skill_promote(script_id, name, tags)` to persist and tag. |
| Code-as-CAD (LL3M pattern) | `blender_generate_bpy_script` + `blender_run_bpy_script` |
| Parameter-only re-run loop | `blender_apply_params` (no LLM call) |
| AST safety gate on script execution | `blender_run_bpy_script` AST pre-pass + the addon's `OPENCLAW_ALLOW_EXEC` |
| Image→scene seed | `blender_reference_image_to_scene` 3-action two-pass |
| Cached-asset enumeration | `blender_list_available_assets` (PolyHaven/ambientCG/Sketchfab/Hyper3D/Hunyuan3D/local) |

### Tier 1 — New Tools That Plug Into CADAM (recommended next)

> Each of these is grounded in a quoted source in the [`CAD for Blender MCP` notebook](https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813). The "PARAMETERS block role" column shows how the tool composes with the v3.1.0 contract.

| # | Tool name | Source pattern (quoted) | PARAMETERS block role | Effort |
|---|---|---|---|---|
| **T1** | `blender_topology_select` | *"Shape topology can be extracted from Shapes with selectors which return ShapeLists. ShapeLists offer methods for sorting, grouping, and filtering Shapes by Shape properties..."* — Build123d | Helper available inside generated scripts. Keeps `blender_apply_params` re-runs from breaking when dimension parameters change face indices. **This is the single biggest robustness fix for the parameter loop.** | M |
| **T2** | `blender_sketch_pad` (recipe + macro) | *"In the PartDesign Workbench, create a PartDesign Body, then use PartDesign NewSketch...; then perform a PartDesign Pad to create a first solid."* — FreeCAD docs | Shipped as a **canonical `script_id` recipe** with a fixed PARAMETERS schema (`PLANE`, `SKETCH_VERTS_2D`, `DEPTH`, `TAPER_DEG`, `BOOLEAN_OP`). Subsequent extrudes reference its `script_id`. | M |
| **T3** | `blender_datum_plane` (helper + PARAMETERS rule) | *"Use of supporting datum objects like planes and local coordinate systems is strongly recommended to produce models that aren't easily subject to such topological errors."* — FreeCAD Topo-Naming doc | Datums become **named PARAMETERS-block constants** (`DATUM_FRONT = {"origin":[0,0,0], "normal":[0,1,0]}`). All sketch/pad scripts reference them by name. Survives `apply_params` edits. | S |
| **T4** | `blender_csg_hull` + `blender_csg_diagnose` | *"Composable: CSG operations (union, difference, hull) map naturally to how LLMs describe shapes."* — `jkoets/OpenSCAD-MCP` | `hull` is the missing third op (Blender already has Manifold for union/diff/intersect). `diagnose` reports manifold/non-manifold + intersection curves — feeds `blender_critique`. Hull op exposed both as a Python helper and as a `script_id` template. | S |
| **T5** | `blender_skill_promote` + `blender_skill_search` | *"Voyager consists of three key components: 1) an automatic curriculum...; 2) an ever-growing skill library of executable code for storing and retrieving complex behaviors..."* — Voyager (arxiv 2305.16291) | Promotes a `script_id` from in-memory LRU cache (32) to on-disk embedding-indexed DB. `search(query)` returns ranked `script_id`s the agent can `apply_params` against. **Closes the loop with `recipes/`.** | L |
| **T6** | `blender_needs_input` payload extension | *"Model-first clarification is the default for router_set_goal(...) on llm-guided: missing workflow parameters return a typed needs_input payload to the outer model first."* — `PatrykIti/blender-ai-mcp` | When `blender_apply_params` is called with insufficient overrides, return `{needs_input: {field, kind, choices, default}}` instead of erroring. Same pattern in `blender_router_set_goal`. | S |

### Tier 2 — BIM Layer (new, no v3.1.0 coverage)

| # | Tool name | Source pattern (quoted) | PARAMETERS block role | Effort |
|---|---|---|---|---|
| **T7** | `blender_ifc_assign_pset` | *"...a specific IFC class must be assigned... Depending on the selected class, it is possible to associate dedicated attributes, Property Sets (PSets), and custom properties..."* — STEP→IFC paper | PARAMETERS schema accepts a `PSET_VALUES = {"Pset_WallCommon": {"FireRating": "60min", "LoadBearing": True}}` block. Tool injects via IfcOpenShell. Re-runnable via `apply_params` to flip semantic data without re-meshing. | M |
| **T8** | `blender_ifc_aggregate` | *"Assemblies are mapped to the IfcElementAssembly class... the IfcRelAggregates relationship is used to explicitly model the hierarchical decomposition..."* — STEP→IFC paper | A meta-script whose PARAMETERS block lists child `script_id`s and their relative offsets. The aggregate becomes an IFC entity. | M |
| **T9** | `blender_ifc_organize_by_storey` | *"Collections are created by building a story, then an IFC type."* — Speckle Blender connector | PARAMETERS block defines `STOREYS = [{"name":"L1", "elevation":0.0, "height":3.5}, ...]`. Tool builds Blender collections + IFC `IfcBuildingStorey` entities. `apply_params` shifts elevations atomically. | M |
| **T10** | `blender_ifc_hash_diff` | *"...whether 2 successively exported IFC building models are different by testing whether entity instances of the latest are present in the original one..."* — IfcOpenShell Academy | Verification tool, called by `blender_verify` for BIM scenes. Returns `{added: [...], removed: [...], changed: [...]}`. | S |

### Tier 3 — Verification depth (new, complements existing `blender_verify` / `blender_critique`)

| # | Tool name | Source pattern (quoted) | PARAMETERS block role | Effort |
|---|---|---|---|---|
| **T11** | `blender_compare_renders` | *"compare_renders | Side-by-side before/after renders for visual comparison"* — `quellant/openscad-mcp` | Composes two `blender_snapshot` outputs into one image. The VLM in `blender_critique` scores the diff in one call. Pairs naturally with `apply_params` re-run loops. | S |
| **T12** | `blender_segment_and_describe` | *"segment_and_analyze - Colorize regions with SAM, then have VLM describe each"* — `proximile/FreeCAD-MCP` | Adds SAM masks to viewport captures so the VLM judge can confirm "the chair is in frame" really means "the *intended* chair". Plugs into `blender_verify`. | L |

### Tier 4 — Round-trip / interop (new, infrastructure)

| # | Tool name | Source pattern (quoted) | PARAMETERS block role | Effort |
|---|---|---|---|---|
| **T13** | `blender_step_to_ifc_bridge` | *"...the resulting geometries (usually in the form of meshes) are converted into IFC entities, to which the previously processed attributes and properties are associated."* — STEP→IFC paper | Bridges mechanical CAD → BIM. Takes a CadQuery/Build123d `script_id`, evaluates → mesh → wraps as IFC entity with PSet from PARAMETERS. | L |
| **T14** | `blender_blendquery_eval` | `uki-dev/blendquery` (CadQuery+Build123d in Blender) | A specialized variant of `blender_run_bpy_script` whose generated script imports CadQuery/Build123d and emits a B-Rep that Blender ingests via Manifold meshing. PARAMETERS govern the parametric inputs. | M |

---

## How This Reshapes the Roadmap

### Sprint 1 (this week — fast wins on top of v3.1.0)
- **T3** datum-plane convention (just a PARAMETERS naming rule + 1 helper) — Small
- **T4** hull + diagnose — Small
- **T6** `needs_input` payload extension — Small
- **T11** `compare_renders` — Small
- **T10** `ifc_hash_diff` — Small (uses IfcOpenShell — already a Bonsai dep)

### Sprint 2 (next 2–3 weeks — parametric core)
- **T1** topology selectors — Medium (most important: makes `apply_params` survive dimension changes)
- **T2** `sketch_pad` recipe + canonical `script_id` — Medium
- **T9** `ifc_organize_by_storey` — Medium
- **T7** `ifc_assign_pset` — Medium

### Sprint 3 (4–6 weeks out — skill + BIM depth)
- **T5** `skill_promote` + `skill_search` (the Voyager closer) — Large
- **T8** `ifc_aggregate` — Medium
- **T13** `step_to_ifc_bridge` — Large
- **T14** `blendquery_eval` — Medium

### Sprint 4 (7–10 weeks out — verification depth)
- **T12** SAM segmentation in verify — Large
- BlenderGym 245-scene adoption alongside LEGO-Eval — Medium

---

## Migration Note: `product_animation_tools.py`

Per the v3.1.0 ship-out, there are 9 raw `execute_python` call sites in `server/product_animation_tools.py` that still bypass the PARAMETERS-block contract. These should be migrated to `blender_run_bpy_script(require_parameters_block=True, cache=True)`, which gives them:

1. Free LRU caching (re-runs of the same camera setup hit the cache)
2. Free parameter-loop access (you can `blender_apply_params` to tweak FOV/aperture without re-running the LLM)
3. AST safety gate
4. Audit trail via `script_id`

Estimate: **1 day of work, 9 call sites, ~150 LOC delta**. Do this before adding T-series tools so the tier surface is consistent.

---

## What to Update in `.claude/skills/blender-mcp/SKILL.md`

You noted this file was write-protected during v3.1.0. When unlocked, add:

1. **CADAM contract section** — copy the v3.1.0 entry from `docs/CHANGELOG.md`, plus the asset-workflow rule.
2. **Tier-0 / Tier-1 / Tier-2 / Tier-3 / Tier-4 tool taxonomy** from this document.
3. **PARAMETERS-block convention table** for the new tools (`PSET_VALUES`, `STOREYS`, `DATUM_*`, `SKETCH_VERTS_2D`).
4. **Reference architecture cheatsheet:** *"Reach for `apply_params` first. If params can't express the change, regenerate. If you don't know what to regenerate, `skill_search` first."*
5. **Mapping table** from Bonsai/IfcOpenShell idioms → blender-mcp BIM tools (T7–T10), so agents know they are wrappers, not reinventions.

---

## What to Update in `config/openclaw-blender-mcp.json`

Add the 14 new tool names (T1–T14) under the existing tool taxonomy with explicit `tier` fields. The `llm-guided` profile should default-surface only Tier 0 + Tier 1 + recipe macros — the Tier 2 BIM tools should be opt-in via `profile=bim` so non-BIM sessions don't get token-flooded.

---

## Hard-truths reframe (v3.1.0 edition)

1. **The hardest piece is already done.** CADAM's PARAMETERS-block + parameter-loop is the high-leverage engineering. The 14 tools above are mostly thin wrappers + naming conventions on top.
2. **Topology selectors (T1) are not optional.** Without them, `apply_params` will silently break any script that does selection-by-index whenever a dimension parameter changes. This needs to land before T2 ships.
3. **BIM tools only matter if there's a BIM use case in the eval.** Add `bim_residential_floorplan` and `bim_pset_propagation` scenes to the eval suite *before* T7–T10, so improvements are measurable.
4. **The skill library (T5) only pays off if the ranking is good.** Promote `script_id`s aggressively, but invest in the embedding+rerank pipeline — a junk skill DB is worse than no skill DB.
5. **Don't migrate `blender_execute_python` away from being a deprecated alias.** Keep it forever as a back-compat layer. The cost is one function definition, the benefit is no breaking changes for downstream consumers.

---

## Source-of-truth pointers

- **NotebookLM:** [`CAD for Blender MCP — Cross-Pollination Research`](https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813) — 106 sources
- **Routing map slug:** `blender-mcp-cad`
- **Companion notebooks:** `blender-mcp-ops` (a908f9ba), `blender-guru` (c5d4caa8)
- **CADAM v3.1.0 changelog entry:** [`docs/CHANGELOG.md`](./CHANGELOG.md)
- **Companion research report:** [`CAD_RESEARCH_REPORT.md`](./CAD_RESEARCH_REPORT.md)
- **GitHub issue drafts:** [`CAD_GITHUB_ISSUES.md`](./CAD_GITHUB_ISSUES.md)
