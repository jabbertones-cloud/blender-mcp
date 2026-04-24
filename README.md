# OpenClaw Blender MCP — v3.0.0

**Blender over MCP (Model Context Protocol)** — a FastMCP server that talks to the OpenClaw Blender Bridge addon (JSON over TCP). Use it from Claude, Cursor, or any MCP client to build scenes, render, export, and run `bpy` safely on a dedicated host.

**~80 tools** across 23 categories: core modeling, materials, animation, rendering, rigging, physics, ecosystem imports (Poly Haven, Sketchfab, Hyper3D, Hunyuan3D), product-viz suite, forensic scene reconstruction, **and (new in v3.0.0)** spatial reasoning, Planner-Actor-Critic agent loop, GCS verification, OpenTelemetry observability, drift detection, and a self-evolving skill bank.

**Naming:** use **OpenClaw Blender MCP** on resumes and in prose. The GitHub repository slug is **`jabbertones-cloud/blender-mcp`**.

---

## What's new in v3.0.0 (Phases 1–7)

| Phase | Ships |
|------|-------|
| **1 — Security + correctness floor** | **RCE closed** (Issue #201: `execute_python` now gated by `OPENCLAW_ALLOW_EXEC`, `os` removed from namespace, AST pre-pass). Depsgraph helpers (`blender_addon/depsgraph_helpers.py`) for correct post-modifier geometry reads. |
| **2 — Observability** | OpenTelemetry spans per tool (`OPENCLAW_OTEL_ENABLED=1`), EMA drift detector with cosine distance, retry/backoff on socket errors. |
| **3 — Agent loop** | `blender_router_set_goal`, `blender_plan`, `blender_act`, `blender_critique`, `blender_verify`, `blender_session_status`. 9 GCS constraint types + Vision-as-a-Judge (Claude Sonnet 4.6 default, OpenAI/local optional). |
| **4 — Self-evolving skills** | `.claude/skills/blender-mcp/recipes/` with 5 seed recipes, `scripts/skill_evo.py` replay→evaluate→mutate→promote loop. |
| **5 — Tool expansion** | Spatial (`blender_spatial`, `blender_semantic_place`, `blender_dimensions`, `blender_floor_plan`), UV (8 methods), texture bake, LOD, VR optimize, Gaussian splat, Grease Pencil, snapshot/diff. 70+ dimensions-DB entries. |
| **6 — Evaluation** | LEGO-Eval adapter (130 instructions), BlenderGym/EZBlender adapter (245 scenes), CI (`.github/workflows/eval.yml`). |
| **7 — Docs** | Rewritten SKILL.md, README (this file), CHANGELOG, expanded .gitignore. |

---

## Security posture

The RCE described in [ahujasid/blender-mcp Issue #201](https://github.com/ahujasid/blender-mcp/issues/201) is **closed** here:

- `blender_execute_python` is **off by default**. Opt in with `OPENCLAW_ALLOW_EXEC=1` (document it in your secrets/ops runbook).
- The exec namespace no longer includes `os` — use `blender_export_file` / `blender_save_file` etc. for filesystem ops.
- AST pre-pass blocks `import os`, `subprocess`, `socket`, `shutil`, `requests`, `urllib`, `http`, `ctypes`, `multiprocessing` and names `eval`, `exec`, `__import__`, `compile`, `open`. Override with `OPENCLAW_ALLOW_UNSAFE_EXEC=1` (deprecated — remove by 3.2).
- Addon binds to `127.0.0.1` by default. Set `OPENCLAW_AUTH_TOKEN` before any non-localhost deployment.

See `.claude/skills/blender-mcp/SKILL.md` → *execute_python safety* for full details.

---

## Agent loop — quick start

Replace brittle `execute_python` chains with the Planner-Actor-Critic pattern:

```python
# 1. Set the goal + pick a curated profile
blender_router_set_goal(goal="Build a cyberpunk desk scene with neon lighting",
                        profile="llm-guided")

# 2. Plan
plan = blender_plan(goal=None)   # uses session goal

# 3. Iterate — never chain 4+ tools without critique
for step in plan["todo"]:
    blender_act(step_id=step["step_id"], tool_name=step["tool_hint"], tool_args={...})
    blender_critique(step_id=step["step_id"],
                     constraints=[{"type": "not_overlapping", "a": "Desk", "b": "Floor"}])

# 4. Final verify before render
blender_verify(expected="Neon glow visible, desk centered, reflective floor",
               constraints=[{"type": "on_top_of", "a": "Monitor", "b": "Desk"}])
blender_render()
```

**Rule from the EZBlender research:** never chain more than ~3 mutations without a critique — agents produce "geometry soup" by step 3-4 without visual/GCS feedback.

---

## Observability

```bash
export OPENCLAW_OTEL_ENABLED=1
export OPENCLAW_OTEL_ENDPOINT=http://localhost:4318/v1/traces   # OTLP
# or view in terminal:
export OPENCLAW_OTEL_DEBUG=1
```

Every tool call produces a span with attributes: `mcp.tool.name`, `mcp.tool.duration_ms`, `blender.objects_before`, `blender.objects_after`, `blender.vertices_before`, `blender.vertices_after`, `blender.objects_delta`, `blender.vertices_delta`. Scene-diff deltas are the primary signal for **action-hallucination** detection: tool returns success but the scene didn't actually change.

Drift detection:

```python
blender_drift_status()
# → {drift_score: 0.18, baseline_turn: 1, current_turn: 47, status: "ok"}
# drift_score >= 0.3 → warn; >= 0.5 → alert (agent has deviated from baseline style)
```

---

## Evaluation benchmarks

```bash
python eval/run.py --bench lego --limit 10           # smoke
python eval/run.py --bench blender_gym --trials 5    # smoke
python eval/run.py --bench all                       # full
python eval/run.py --report                           # roll up last 10 runs
```

**Baselines to beat:**
- LEGO-Eval (130 instructions, 1,250 constraints): SOTA LLM scene generators hit ~10% holistic SR. Target: >25% for v3.1.
- BlenderGym / EZBlender (245 scenes × 50 episodes): EZBlender 58–85% TCR, BlenderGPT 23–41%, BlenderAlchemy 14–20%. Target: enter the 60% band.

Weekly CI run posts `reports/weekly-eval.md` to the repo.

---

## Self-evolving skills

```
.claude/skills/blender-mcp/
├── SKILL.md                           # master operational rules
├── recipes/
│   ├── product-viz-3point-v0.1.0.md
│   ├── forensic-accident-reconstruction-v0.1.0.md
│   ├── procedural-wood-floor-v0.1.0.md
│   ├── cyberpunk-desk-scene-v0.1.0.md
│   ├── character-rigging-starter-v0.1.0.md
│   └── MANIFEST.json
└── trajectories/                       # auto-recorded session logs
```

Run the skill-evolution loop:

```bash
python scripts/skill_evo.py replay    --recipe product-viz-3point
python scripts/skill_evo.py evaluate  --trajectory trajectories/product-viz-3point-*.jsonl
python scripts/skill_evo.py mutate    --recipe product-viz-3point
python scripts/skill_evo.py promote   --recipe product-viz-3point --bump patch
python scripts/skill_evo.py extract   --trajectory trajectories/new-workflow.jsonl
python scripts/skill_evo.py status
```

---

## Architecture

```
Claude / IDE ── MCP stdio ──► server/blender_mcp_server.py ── TCP JSON ──► openclaw_blender_bridge.py (addon)
                              FastMCP · ~80 tools                         bpy.app.timers on main thread
                              + telemetry, drift, agent loop,             default 127.0.0.1:9876
                                spatial, extended tools
```

Multi-instance: port range **9876–9885**, discover via `blender_instances(action="list")`.

---

## Runtime configuration

| Variable | Default | Purpose |
|---|---|---|
| `BLENDER_HOST` / `OPENCLAW_HOST` | `127.0.0.1` | Bridge host |
| `BLENDER_PORT` / `OPENCLAW_PORT` | `9876` | Bridge port (align both per instance) |
| `OPENCLAW_TIMEOUT` | `30` | Socket command timeout seconds |
| `OPENCLAW_COMPACT` | `0` | Compact JSON responses |
| `OPENCLAW_ALLOW_EXEC` | `0` | Enable `blender_execute_python` |
| `OPENCLAW_ALLOW_UNSAFE_EXEC` | `0` | Disable AST pre-pass (deprecated) |
| `OPENCLAW_AUTH_TOKEN` | unset | Shared secret for TCP auth (Phase 1 follow-up) |
| `OPENCLAW_OTEL_ENABLED` | `0` | OpenTelemetry per-tool spans |
| `OPENCLAW_OTEL_ENDPOINT` | `http://localhost:4318/v1/traces` | OTLP target |
| `OPENCLAW_OTEL_DEBUG` | `0` | Also emit to stdout |
| `OPENCLAW_SESSION_PERSIST` | `0` | Persist Planner-Actor-Critic session state to `/tmp/openclaw-sessions.jsonl` |
| `BLENDER_REGISTRY_PATH` | `config/blender-instances.json` | Multi-instance registry |
| `BLENDER_HEARTBEAT_TIMEOUT` | `300` | Instance heartbeat timeout seconds |
| `ANTHROPIC_API_KEY` | unset | For VLM judge in `blender_verify` / `blender_critique` |

---

## Tool surface (~80)

### Core (59 server + 6 product animation = 65)

| Category | Tools |
|---|---|
| Connection / scene | `blender_ping`, `blender_get_scene_info`, `blender_get_object_data`, `blender_scene_operations`, `blender_scene_analyze`, `blender_instances` |
| Objects | `blender_create_object`, `blender_modify_object`, `blender_delete_object`, `blender_select_objects`, `blender_duplicate_object`, `blender_transform_object`, `blender_parent_objects` |
| Modeling | `blender_apply_modifier`, `blender_boolean_operation`, `blender_uv_operations`, `blender_cleanup`, `blender_mesh_edit`, `blender_sculpt` |
| Materials | `blender_set_material`, `blender_shader_nodes`, `blender_procedural_material` |
| Animation | `blender_set_keyframe`, `blender_clear_keyframes`, `blender_advanced_animation` |
| Rendering | `blender_set_render_settings`, `blender_render`, `blender_viewport`, `blender_compositor`, `blender_viewport_capture`, `blender_render_presets`, `blender_render_quality_audit` |
| Collections / world | `blender_manage_collection`, `blender_set_world` |
| Rigging | `blender_armature_operations`, `blender_constraint_operations` |
| Physics / sim | `blender_physics`, `blender_particle_system`, `blender_fluid_simulation`, `blender_force_field`, `blender_cloth_simulation` |
| Curves / images / text | `blender_curve_operations`, `blender_image_operations`, `blender_text_object` |
| Advanced geometry | `blender_geometry_nodes`, `blender_weight_paint`, `blender_shape_keys` |
| I/O | `blender_import_file`, `blender_export_file`, `blender_save_file` |
| Batch / templates | `blender_batch_operations`, `blender_scene_template` |
| Lighting / scenes | `blender_scene_lighting`, `blender_forensic_scene` |
| Ecosystem | `blender_polyhaven`, `blender_sketchfab`, `blender_hyper3d`, `blender_hunyuan3d` |
| Escape hatch | `blender_execute_python` (gated) |
| Product animation | `blender_product_animation`, `blender_product_material`, `blender_product_lighting`, `blender_product_camera`, `blender_product_render_setup`, `blender_fcurve_edit` |

### New in v3.0.0 (~15)

| Category | Tools |
|---|---|
| Agent loop | `blender_router_set_goal`, `blender_plan`, `blender_act`, `blender_critique`, `blender_verify`, `blender_session_status` |
| Spatial | `blender_spatial` (raycast, bbox, collision, placement, movement_range, scene_bounds), `blender_semantic_place`, `blender_dimensions`, `blender_floor_plan` |
| Extended modeling | `blender_camera_advanced`, `blender_uv_unwrap` (8 methods), `blender_texture_bake`, `blender_lod` |
| Workflow | `blender_vr_optimize`, `blender_gaussian_splat`, `blender_grease_pencil`, `blender_snapshot`, `blender_drift_status` |

Full list in `.claude/skills/blender-mcp/SKILL.md` → *Tool taxonomy*.

---

## Quick start

```bash
# 1. Setup
chmod +x setup.sh && ./setup.sh

# 2. Install the addon in Blender (Preferences → Add-ons → Install → openclaw_blender_bridge.py)
#    The addon auto-imports depsgraph_helpers.py and new_handlers_phase5.py from blender_addon/

# 3. Sanity check
python3 scripts/blender_healthcheck.py --live --port 9876

# 4. Point your MCP client at server/blender_mcp_server.py (claude_mcp_config.json is a template)
#    Recommended env for dev:
#      OPENCLAW_ALLOW_EXEC=0   (keep RCE closed)
#      OPENCLAW_OTEL_ENABLED=1
#      OPENCLAW_OTEL_DEBUG=1

# 5. Run the eval smoke suite after any significant change
python eval/run.py --bench lego --limit 5
python eval/run.py --bench blender_gym --trials 2
```

---

## Source of truth

| Doc | Purpose |
|---|---|
| `.claude/skills/blender-mcp/SKILL.md` | Operational rules — wire protocol, depsgraph rule, undo trap, `bpy.ops` trap, `execute_python` safety, PAC recipe, GCS constraints, tool taxonomy |
| `.claude/skills/blender-mcp/recipes/*.md` | Versioned SkillX/AutoSkill recipes |
| `BLENDER_SKILLS_REFERENCE.md` | Phrase-to-tool mapping for artists |
| `docs/MULTI-BLENDER-ARCHITECTURE.md` | Concurrent instances |
| `docs/CHANGELOG.md` | This release's full changelog |
| `eval/README.md` | Running LEGO-Eval + BlenderGym locally |

---

## Wire-protocol note

MCP exposes tools as `blender_*`. The **Bridge** expects command names **without** that prefix (e.g. `execute_python`, not `blender_execute_python`). Phase 5 handlers follow the same convention (`spatial_raycast`, `camera_advanced`, etc.). See `SKILL.md` → *wire protocol* for full details.
