# CHANGELOG

All notable changes to OpenClaw Blender MCP (`jabbertones-cloud/blender-mcp`) are documented here.

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
