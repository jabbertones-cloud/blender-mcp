# SKILL.md v3.1.0 Append — ready to paste

> **Status (2026-04-26):** `.claude/skills/blender-mcp/SKILL.md` is write-protected in the current session. This file holds the v3.1.0 / Tier-taxonomy section ready to copy-append after `## 18.5 Critical Fixes (verified empirically)` (currently at line 1411 of SKILL.md). Closes [#11](https://github.com/jabbertones-cloud/blender-mcp/issues/11) once pasted.

```markdown
---

## 19. v3.1.0 — CADAM Contract + Tier 0–4 Tool Taxonomy

> **Added 2026-04-25 with v3.1.0.** This section is the new authoritative vocabulary for tool selection. When in doubt, **reach for `apply_params` first**. If params can't express the change, regenerate. If you don't know what to regenerate, `skill_search` first.

### 19.1 The CADAM Contract (the single most important rule)

Every script generated for Blender via this server **MUST** include a fenced `# --- PARAMETERS ---` block at the top:

```python
# --- PARAMETERS ---
PARAMETER_NAME_1 = "default_value"
PARAMETER_NAME_2 = 42
PARAMETER_NAME_3 = [1.0, 2.0, 3.0]
# --- /PARAMETERS ---
```

**Rules:**
- Names: UPPER_SNAKE_CASE
- Values: literal Python only (str, int, float, bool, list, dict, None) — parsed via `ast.literal_eval`, never `eval`/`exec`
- No function calls, no imports, no comprehensions, no expressions inside the block
- The PARAMETERS block is the contract boundary. The server extracts and validates it before execution.

**Why it matters:** parameter tweaks (camera FOV, light energy, material roughness, dimensions) re-run only the PARAMETERS block via `blender_apply_params` — **the LLM is not called**. This collapses 100s of regeneration tokens into a single deterministic re-execution.

### 19.2 Tier 0 — already shipped in v3.1.0

| Tool | Purpose |
|---|---|
| `blender_generate_bpy_script` | Publishes the contract (system prompt + template + optional seed values). Read-only; the calling LLM authors the script. |
| `blender_run_bpy_script` | AST gate (defense-in-depth on top of `OPENCLAW_ALLOW_EXEC`) + PARAMETERS validation + LRU cache (32 entries) keyed by `script_id`. |
| `blender_apply_params` | **CADAM slider re-run.** Rewrite only the PARAMETERS block of a cached script and re-execute. **Zero LLM tokens.** |
| `blender_reference_image_to_scene` | Three-action two-pass: `extraction_prompt` → `submit_extraction` → `build_seed_params`. |
| `blender_list_available_assets` | Discovers cached PolyHaven/ambientCG/Sketchfab/Hyper3D/Hunyuan3D/local assets. Memoized; `refresh=True` re-scans. **Call this first** before any HDRI/PBR-loading code. |

`blender_execute_python` is now a **deprecated alias** delegating to `blender_run_bpy_script(require_parameters_block=False, cache=False)`. All existing call sites still work; new code should use the generate/run pair.

### 19.3 Tier 1 — parametric core (planned, see GitHub issues #1–#6)

| Tool | What it adds | Issue |
|---|---|---|
| `blender_topology_select` | Property-based face/edge/vertex selection (area, length, normal_axis, sort_by). Survives `apply_params` re-runs even when dimensions change. **Highest-leverage parametric fix.** | #1 |
| `blender_sketch_pad` | Canonical script_id template for sketch-on-plane → extrude with PARAMETERS schema. | #2 |
| `blender_datum_plane` | Named, queryable datum planes. PARAMETERS convention: `DATUM_FRONT = {"origin":[0,0,0], "normal":[0,1,0]}`. | #3 |
| `blender_csg_hull` + `blender_csg_diagnose` | The missing third CSG op (hull) + manifold/intersection diagnostics that feed `blender_critique`. | #4 |
| `blender_skill_promote` + `blender_skill_search` | Voyager-style persistent skill library backed by embedding+rerank over `~/.openclaw/skills/`. | #5 |
| `needs_input` payload | When required PARAMETERS values are missing or workflow params unspecified, return typed `{needs_input: {field, kind, choices, default}}` instead of erroring. | #6 |

### 19.4 Tier 2 — BIM layer (planned, see GitHub issues #7–#8)

| Tool | What it adds | Issue |
|---|---|---|
| `blender_ifc_assign_pset` | Assign IFC class + Property Sets via IfcOpenShell. PARAMETERS holds `PSET_VALUES = {...}`. | (T7) |
| `blender_ifc_aggregate` | `IfcRelAggregates` hierarchy (assemblies → parts). | (T8) |
| `blender_ifc_organize_by_storey` | Auto-build `IfcBuildingStorey` + Blender collections from `STOREYS = [...]` PARAMETERS. | #7 |
| `blender_ifc_hash_diff` | Diff two IFC files semantically (added/removed/changed entities). | #8 |

### 19.5 Tier 3 — verification depth (planned, see GitHub issue #9)

| Tool | What it adds |
|---|---|
| `blender_compare_renders` | Side-by-side composite (horizontal/vertical/diff) with SSIM. Pairs with `apply_params` loops. |
| `blender_segment_and_describe` | SAM masks + per-mask VLM captions for fine-grained "is the *intended* chair in frame?" verification. |

### 19.6 Tier 4 — interop (planned, see CAD_GITHUB_ISSUES.md T13/T14)

| Tool | What it adds |
|---|---|
| `blender_step_to_ifc_bridge` | Mechanical CAD (CadQuery/Build123d) → simplified mesh → IFC entity with PSet. |
| `blender_blendquery_eval` | Run CadQuery/Build123d under the PARAMETERS-block contract; mesh via Manifold. |

### 19.7 PARAMETERS-block conventions (the shared vocabulary)

| Convention | Used by | Example |
|---|---|---|
| `PSET_VALUES` | T7 BIM | `PSET_VALUES = {"Pset_WallCommon": {"FireRating": "60min", "LoadBearing": True}}` |
| `STOREYS` | T9 BIM | `STOREYS = [{"name":"L1", "elevation":0.0, "height":3.5}, ...]` |
| `DATUM_*` | T3 parametric | `DATUM_FRONT = {"origin":[0,0,0], "normal":[0,1,0]}` |
| `SKETCH_VERTS_2D` | T2 parametric | `SKETCH_VERTS_2D = [[0,0],[10,0],[10,5],[0,5]]` |
| `BOOLEAN_OP` | T2/T4 | `BOOLEAN_OP = "ADD"` (ADD/SUBTRACT/INTERSECT/NONE) |
| `OUTPUT_NAME` | T14 blendquery | `OUTPUT_NAME = "MyPart"` |
| `MESH_RESOLUTION` | T14 blendquery | `MESH_RESOLUTION = 0.1` |

### 19.8 The "reach for apply_params first" decision tree

```
A change is needed in the scene
├── Can it be expressed as a PARAMETERS-block value tweak?
│   └── YES → blender_apply_params(script_id, overrides)   [zero LLM tokens]
│
├── Does a similar cached script_id already exist?
│   └── YES → blender_skill_search(query) → apply_params with the right script_id
│
└── NO to both → blender_generate_bpy_script (LLM authors)
                 → blender_run_bpy_script (server caches by script_id)
                 → on success, blender_skill_promote(script_id, ...) to persist
```

### 19.9 Bonsai / IfcOpenShell idiom → blender-mcp BIM tool mapping

When the agent already knows a Bonsai/IfcOpenShell pattern, here's the MCP equivalent:

| Bonsai / IfcOpenShell | blender-mcp tool |
|---|---|
| `ifcopenshell.api.run("pset.add_pset", ...)` | `blender_ifc_assign_pset` (T7) |
| `ifcopenshell.api.run("aggregate.assign_object", ...)` | `blender_ifc_aggregate` (T8) |
| `ifcopenshell.api.run("spatial.assign_container", relating_structure=storey)` | `blender_ifc_organize_by_storey` (T9) |
| Manual entity-instance hash diff per the Academy tutorial | `blender_ifc_hash_diff` (T10) |

The MCP tools are **wrappers, not reinventions**. Reuse Bonsai patterns; just call them via the MCP surface so the calling agent gets the cache, AST gate, and parameter loop.

### 19.10 Asset workflow rule (mandatory in all generated scripts)

```
1. blender_list_available_assets(category="hdri")  → check cache first
2. If hit: reference cached id as a PARAMETERS-block string constant
3. If miss: blender_polyhaven(action="search", ...) → blender_polyhaven(action="download", ...)
4. NEVER use a magic string for a file path
```

### 19.11 Migration cheatsheet for older code

| Old pattern | New pattern |
|---|---|
| `bpy.ops.import_scene.gltf(...)` direct from script | Wrap in `blender_run_bpy_script` with explicit PARAMETERS block |
| `send_command("execute_python", {"code": code})` | `blender_run_bpy_script(script=..., require_parameters_block=True, cache=True)` |
| Hardcoded file paths in scripts | `blender_list_available_assets()` + PARAMETERS string constant |
| Selection by face index `obj.data.faces[7]` | `blender_topology_select(...)` (T1, when shipped) |
| Re-generating script for parameter tweak | `blender_apply_params(script_id, overrides={"DEPTH": 3.0})` |

### 19.12 Where to look for the contract source

- **System prompt + helpers:** `server/codegen_prompt.py` (`BPY_GENERATION_SYSTEM_PROMPT`, `extract_parameters`, `replace_parameters`, `validate_parameters_block`)
- **Image extraction → seed params:** `server/image_extraction.py`
- **Tools:** `server/blender_mcp_server.py` (search for `blender_generate_bpy_script`, `blender_run_bpy_script`, `blender_apply_params`)
- **Tests:** `tests/test_cadam_p1_p2_split_exec.py`, `tests/test_cadam_p3_reference_image.py`, `tests/test_cadam_p4_list_assets.py` (22 tests, no live Blender required)
- **Changelog:** `docs/CHANGELOG.md` v3.1.0 entry
- **Research backing:** `docs/CAD_RESEARCH_REPORT.md`, `docs/CAD_INTEGRATION_PLAN.md`, `docs/CAD_GITHUB_ISSUES.md`
- **NotebookLM source-of-truth:** https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813 (106 sources)
```

---

## How to apply

When `.claude/skills/blender-mcp/SKILL.md` is writable:

```bash
# Append the section above (everything inside the outer code fence) verbatim
# after the existing "### 18.5 Critical Fixes (verified empirically)" subsection.
# Then close issue #11.
```

Or programmatically:

```python
import pathlib
skill = pathlib.Path('.claude/skills/blender-mcp/SKILL.md')
content = skill.read_text()
append = pathlib.Path('docs/SKILL_V3_1_0_APPEND.md').read_text()
# Extract just the inner ```markdown block from this file
import re
m = re.search(r'```markdown\n(.*?)\n```', append, re.DOTALL)
skill.write_text(content.rstrip() + '\n\n' + m.group(1) + '\n')
```
