# CHANGELOG

All notable changes to OpenClaw Blender MCP (`jabbertones-cloud/blender-mcp`) are documented here.

## v3.1.1 — 2026-04-26 — CAD cross-pollination batch (issues #6, #10, #11)

Three Sprint-1 follow-ups to v3.1.0 that close the highest-leverage gaps from the [CAD cross-pollination research pass](CAD_RESEARCH_REPORT.md). Backed by a [106-source NotebookLM notebook](https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813).

### Added — `needs_input` payload (Issue #6)

- **`needs_input_payload(...)`** helper in `server/blender_mcp_server.py` — typed clarification response: `{status: "needs_input", needs_input: {field, kind, default?, choices?, available?, hint?}}`. Pattern from [`PatrykIti/blender-ai-mcp`](https://github.com/PatrykIti/blender-ai-mcp).
- **`blender_apply_params`** now returns `needs_input` instead of erroring when:
  - The caller passes an override key not present in the cached PARAMETERS block (`kind: "enum"`, `choices: [...]`)
  - The caller passes an empty `new_values` dict on a script that has tunable params (`kind` matches the first PARAMETERS value, `default` set, `available` lists all keys)
  - The PARAMETERS block rewrite fails (typed payload with hint about literal-only values)
- **`blender_router_set_goal`** (`server/agent_loop.py`) returns `needs_input` for empty goal (`kind: "string"`) or invalid profile (`kind: "enum"`, `choices: [default, llm-guided, power-user, forensic]`).
- **`blender_plan`** returns `needs_input` for missing goal (was: opaque error).
- **8 new tests** in `tests/test_needs_input.py`, including a 3-step `needs_input → answer → needs_input → answer → success` flow.

### Added — CADAM migration of `product_animation_tools.py` (Issue #10)

- **`run_cadam_script(...)`** sync helper in `server/blender_mcp_server.py` — wraps an opaque bpy snippet in a synthetic PARAMETERS-block manifest, AST-validates, caches with `script_kind` tag, executes. Returns `{script_id, parameters, result}` so callers can compose with their own format wrappers.
- **`_build_parameters_block` + `_is_literal_safe`** helpers — render Python literals via `repr()` (NOT `json.dumps`, which would emit `null`/`true`/`false` that `ast.literal_eval` rejects).
- **`register_product_tools` 4-arg signature** — accepts optional `run_cadam_script_fn` as the 4th positional arg. When provided, every product-animation site routes through the CADAM contract; when omitted, the legacy `send_command_fn("execute_python", ...)` path is used (back-compat preserved).
- **All 11 raw `execute_python` sites migrated** in `server/product_animation_tools.py`:
  - `blender_product_animation`: 5 sites (material, lighting, camera, render, compositor)
  - `blender_product_material`: 1 site
  - `blender_product_lighting`: 1 site
  - `blender_product_camera`: 1 site
  - `blender_product_render_setup`: 2 sites (render + compositor)
  - `blender_fcurve_edit`: 1 site
  Each site now passes a typed `parameters` dict that becomes the cached script's PARAMETERS block — enabling `blender_apply_params` round-trips and a permanent script_id audit trail.
- **8 new tests** in `tests/test_product_animation_cadam_migration.py` — covers the helper, signature compat (4-arg + 3-arg fallback), end-to-end emission of script_ids by every product tool, and an `apply_params` round-trip on a product-animation `script_id`.

### Fixed

- **`_gen_material_code` indentation bug** (`server/product_animation_tools.py:269`) — the join string was 8 spaces but the f-string template indented at 4 spaces, producing `unexpected indent` SyntaxError on every preset that emitted >1 extra (glossy_plastic, polished_chrome, gold, rose_gold, copper, clear_glass, frosted_glass, tinted_glass, ceramic_glazed). 7/16 presets were silently broken; the legacy `execute_python` path swallowed the error inside Blender. Caught by the CADAM AST gate during the migration. **All 16 material presets now parse cleanly.**

### Documentation (Issue #11)

- **`docs/CAD_RESEARCH_REPORT.md`** — 19K full report: repo teardowns across parametric / procedural / BIM / AI-native CAD, ranked Top-12 features, interop matrix, hard truths.
- **`docs/CAD_INTEGRATION_PLAN.md`** — 14K plan: how the 12 features fold onto the v3.1.0 CADAM contract; Tier 0 (already shipped) → Tier 1–4 (planned) tool taxonomy; 4-sprint roadmap.
- **`docs/CAD_GITHUB_ISSUES.md`** — 25K of issue specs (mirrored to GitHub issues #1–#12).
- **`docs/SKILL_V3_1_0_APPEND.md`** — ~150-line v3.1.0 / Tier-taxonomy section staged for `.claude/skills/blender-mcp/SKILL.md` (which was write-protected during the v3.1.0 ship). Closes #11 once pasted in.

### Tests

`tests/` now has 5 self-contained suites totaling 37 passing tests, all without a live Blender:
- `test_cadam_p1_p2_split_exec.py` (9 OK)
- `test_cadam_p3_reference_image.py` (5 passed)
- `test_cadam_p4_list_assets.py` (7 OK)
- `test_needs_input.py` (8 OK) **NEW**
- `test_product_animation_cadam_migration.py` (8 OK) **NEW**

### Why this matters

The `needs_input` payload turns silent errors into typed clarifications — agents can recover in-flight instead of regenerating entire scripts. The product_animation migration extends every product-shoot recipe with the CADAM benefits (cache, AST gate, audit trail, `apply_params` slider loop) — a turntable scene's camera FOV is now a one-call tweak, not a re-LLM. The indentation-bug discovery is the v3.1.0 CADAM contract paying its first dividend: **we just shipped a fix for a latent bug we didn't know we had, because the AST gate caught it.**

## v3.1.0 — 2026-04-25 — CADAM-style parametric workflow

Imports the design pattern that makes CADAM (Claude + OpenSCAD WASM) so cheap and fast: every generated 3D script declares its dimensions/materials/lighting as **named UPPER_CASE constants in a fenced `# --- PARAMETERS ---` block**, and parameter tweaks re-run only that block instead of round-tripping the LLM.

### Added

- **`server/codegen_prompt.py`** — central system prompt + `extract_parameters` / `replace_parameters` / `validate_parameters_block` helpers using `ast.literal_eval` (never `eval`/`exec`). Includes two few-shot scripts and the asset-workflow rule (`blender_list_available_assets` first, PolyHaven second, magic strings never).
- **`server/image_extraction.py`** — CADAM two-pass mapper: image → strict structured JSON (dimensions, materials, lighting, camera) → `seed_parameters` dict that flows into a PARAMETERS block.
- **Five new MCP tools** in `server/blender_mcp_server.py`:
  - `blender_generate_bpy_script` — publishes the contract (system prompt + template + optional seed values). Read-only; the calling LLM authors the script.
  - `blender_run_bpy_script` — server-side AST gate (defense-in-depth on top of the addon's `OPENCLAW_ALLOW_EXEC` gate) + PARAMETERS validation + LRU cache (32 entries) keyed by `script_id`.
  - `blender_apply_params` — CADAM slider re-run: rewrite only the PARAMETERS block of a cached script and re-execute. **The LLM is not called.**
  - `blender_reference_image_to_scene` — three-action two-pass tool (`extraction_prompt` → `submit_extraction` → `build_seed_params`). Aligns with the blender-guru v3.0 photo-reference workflow.
  - `blender_list_available_assets` — discovers already-downloaded Poly Haven / ambientCG / Sketchfab / Hyper3D / Hunyuan3D / local assets via `OPENCLAW_ASSET_CACHE` env var, `~/.openclaw/assets/`, repo-`./assets/`. Groups files by asset id (strips `_1k/_2k/_4k/_8k` and PBR channels like `_diff/_nor_gl/_rough`). Memoized; `refresh=True` re-scans.
- **22 new persistent tests** across `tests/test_cadam_p1_p2_split_exec.py`, `tests/test_cadam_p3_reference_image.py`, `tests/test_cadam_p4_list_assets.py`. Self-contained — stub FastMCP, mock `send_command`, no live Blender required.

### Changed

- `blender_execute_python` is now a **deprecated alias** that delegates to `blender_run_bpy_script(require_parameters_block=False, cache=False)`. All existing call sites continue to work; new code should use the generate/run pair so numeric literals are pinned to a PARAMETERS block.
- `BPY_GENERATION_SYSTEM_PROMPT` mandates an asset-workflow rule: call `blender_list_available_assets` before any HDRI/PBR-loading code, reference cached ids as PARAMETERS-block string constants, only fall through to `blender_polyhaven(action='search')` on a cache miss.

### Why this matters (CADAM port rationale)

Before v3.1, every parameter tweak (camera FOV, light energy, material roughness) required a fresh LLM call to regenerate the entire script. With the parametric loop:

1. `blender_generate_bpy_script` → caller authors a script following the contract → `blender_run_bpy_script` (LLM called once).
2. Tweaks: `blender_apply_params(script_id, new_values)` — rewrites only the PARAMETERS block via `ast.literal_eval` round-trip, re-executes (no LLM).

This matches CADAM's slider→recompile loop and unlocks token-cheap iteration loops on top of an already-generated scene.

## v3.0.0 — 2026-04-23 — Agentic Studio Release (Phases 1–7)

Batch release landing the full improvement plan from the NotebookLM research notebooks (`a00aa84b` / `7b05be04`). Tool surface grows 65 → ~80. Core reliability, security, observability, agent loop, and self-evolving skill bank all land together.

### Security (Phase 1) — breaking

- **Closed RCE at `handle_execute_python`** (matches ahujasid/blender-mcp Issue #201). `exec(code, namespace)` no longer runs with `os` pre-imported. New behavior:
  - Gated by `OPENCLAW_ALLOW_EXEC` (default **off**). When off, the tool returns `{error: "execute_python is disabled...", disabled_by_policy: true}`.
  - AST pre-pass rejects `import os`, `subprocess`, `socket`, `shutil`, `requests`, `urllib`, `http`, `ctypes`, `multiprocessing` and names `eval`, `exec`, `__import__`, `compile`, `open`.
  - Override for legacy scripts: `OPENCLAW_ALLOW_UNSAFE_EXEC=1` (deprecated; remove by v3.2).
  - New module: `server/safety.py` (AST checker, 200 lines).
- Addon namespace for `execute_python` no longer includes `os` — use `blender_export_file`, `blender_save_file`, etc.

### Correctness (Phase 1)

- New module `blender_addon/depsgraph_helpers.py` (297 lines) — `evaluated_mesh` context manager, `evaluated_bbox_world`, `scene_object_snapshot`. Every geometry read in Phase 5 handlers is depsgraph-backed.
- Documented the depsgraph rule, undo trap, and `bpy.ops` O(n²) trap in `SKILL.md` and `README.md`.

### Observability (Phase 2)

- New `server/telemetry.py` (274 lines) — `@traced_tool` decorator, W3C Trace Context helpers, scene-diff span attributes. Opt in with `OPENCLAW_OTEL_ENABLED=1`; set `OPENCLAW_OTEL_ENDPOINT` for OTLP export.
- New `server/drift_guard.py` (305 lines) — EMA behavioral-drift monitor (β=0.9), cosine distance, pure-math. Exposed via `blender_drift_status` tool.

### Agent loop (Phase 3)

- New modules in `server/`:
  - `agent_loop.py` (505 lines) — registers `blender_router_set_goal`, `blender_plan`, `blender_act`, `blender_critique`, `blender_verify`, `blender_session_status`.
  - `verify.py` (546 lines) — 9 GCS constraint types (`on_top_of`, `inside`, `not_overlapping`, `clearance`, `facing`, `vertex_count_range`, `triangulated`, `has_material`, `axis_aligned`) + VLM judge (Anthropic default).
  - `session_state.py` (221 lines) — per-session todo list, snapshots, critique history.

### Self-evolving skills (Phase 4)

- New directory `.claude/skills/blender-mcp/recipes/` with 5 seed recipes (product-viz, forensic accident, procedural wood, cyberpunk desk, character rigging) + `MANIFEST.json`.
- New `scripts/skill_evo.py` — replay-evaluate-mutate-promote loop (`replay`, `evaluate`, `mutate`, `promote`, `extract`, `status` subcommands).

### Tool surface expansion (Phase 5) — ~15 new tools

- New `server/spatial_tools.py` — `blender_spatial` (raycast / bbox / collision / find_placement / movement_range / scene_bounds), `blender_semantic_place`, `blender_dimensions`, `blender_floor_plan`.
- New `server/extended_tools.py` — `blender_camera_advanced`, `blender_uv_unwrap` (8 methods), `blender_texture_bake`, `blender_lod`, `blender_vr_optimize`, `blender_gaussian_splat`, `blender_grease_pencil`, `blender_snapshot` (save/diff/list/clear/get), `blender_drift_status`.
- New `config/dimensions-db.json` — 70+ real-world dimensions entries with aliases, for grounding LLM scale decisions.
- New `blender_addon/new_handlers_phase5.py` — 25 new command handlers wired into the addon's dispatch table.

### Evaluation (Phase 6)

- New `eval/` directory with `run.py`, `lego_eval/adapter.py`, `blender_gym/adapter.py`, `common.py` (MCP TCP client), `README.md`.
- `.github/workflows/eval.yml` — smoke PR job + weekly full eval.
- Baselines to beat: LEGO-Eval 10% holistic SR, BlenderGym/EZBlender 58–85% TCR.

### Documentation (Phase 7)

- Rewrote `.claude/skills/blender-mcp/SKILL.md` — added depsgraph rule, undo trap, `bpy.ops` trap, `execute_python` safety, Planner-Actor-Critic recipe, GCS constraints, scene-diff verification, recipes/ overview, new tool taxonomy.
- Rewrote `README.md` — security posture section, agent-loop quickstart, observability section, eval benchmarks, ~80-tool count.
- Expanded `.gitignore` (was 5 lines, now 50+).
- Added this `CHANGELOG.md`.

### Integration

- `server/blender_mcp_server.py` now registers the new tool modules via `_try_register()` — server still boots if any module is missing.
- Addon merges `DISPATCH_NEW_HANDLERS` from `new_handlers_phase5.py` into the main command dispatch dict at module load time.

### Breaking changes

1. `blender_execute_python` returns an error by default. Opt in with `OPENCLAW_ALLOW_EXEC=1`.
2. `os` no longer in the `execute_python` namespace. Code using `os.path.join(...)` etc. must be refactored to use dedicated MCP tools or set `OPENCLAW_ALLOW_UNSAFE_EXEC=1` (deprecated).
3. `get_object_data` / `scene_analyze` reported mesh counts will change in a follow-up patch that switches them to depsgraph-evaluated meshes. Existing behavior preserved in 3.0.0 for compatibility; planned for 3.1.

### Migration

- Scripts that relied on `import os` inside `execute_python` must either (a) migrate to MCP filesystem tools, or (b) set `OPENCLAW_ALLOW_EXEC=1 OPENCLAW_ALLOW_UNSAFE_EXEC=1` (not recommended).
- MCP clients pointed at `server/blender_mcp_server.py` need no changes — new tools appear automatically at startup.
- Blender addon must be re-installed if `depsgraph_helpers.py` and `new_handlers_phase5.py` are not already in `blender_addon/`.

### Known limitations

- `blender_texture_bake` and `blender_vr_optimize(action="optimize")` return structured "not yet implemented" errors — to be wired in 3.1.
- `blender_gaussian_splat_import_*` require the external KIRI/PolyCam splat addon; returns a pointer to the install page if missing.
- OpenTelemetry adds ~5–20ms per tool call when enabled; default off for no overhead.

### Acknowledgments

- NotebookLM research (287 + 56 sources across two notebooks)
- CGWire for the depsgraph export guide
- ahujasid/blender-mcp for surfacing Issue #201 publicly
- mlolson/blender-orchestrator for the spatial-reasoning pattern
- Aztech-Lab/EZ_Blender for the BlenderGym benchmark adapter target
- All the research papers: EZBlender, Planner-Actor-Critic (arXiv 2601.05016), SkillX (arXiv 2604.04804), AutoSkill, SAFi Spirit drift engine

---

## v2.x — earlier

See `git log` for the pre-v3.0.0 history. v2.2 added forensic scene reconstruction; v2.1 added Poly Haven / Sketchfab / Scene Lighting; v2.0 added VFX-grade tools (fluid, procedural materials, batch ops, scene templates).
