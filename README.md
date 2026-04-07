# OpenClaw Blender MCP

**Blender over MCP (Model Context Protocol)** — a FastMCP server that talks to the OpenClaw Blender Bridge addon (JSON over TCP). Use it from Claude, Cursor, or any MCP client to build scenes, render, export, and run `bpy` safely on a dedicated host.

**Naming:** use **OpenClaw Blender MCP** on resumes and in prose. The GitHub repository slug is **`jabbertones-cloud/blender-mcp`** (same project).

This repository also ships a **3D Forge** production pipeline (Node.js): trend scan → harvest → concept generation → Blender produce → validate → autoresearch. See `package.json` scripts (`forge:*`, `render:*`, `pool:*`).

## GitHub “About” (copy-paste)

Use these in the repository **Description** and **Topics** fields on GitHub.

| Field | Suggested value |
|--------|------------------|
| **Description** | MCP server for Blender: 65 tools, TCP bridge to bpy, multi-instance ports, 3D Forge asset pipeline, product lighting/camera presets, render QA. |
| **Topics** | `blender`, `mcp`, `model-context-protocol`, `bpy`, `3d`, `ai-3d`, `openclaw`, `fastmcp`, `glb`, `stl`, `rendering` |

## What changed (audit summary)

Verified against `server/blender_mcp_server.py` and `server/product_animation_tools.py` (2026-04):

| Area | Detail |
|------|--------|
| **Tool count** | **65** MCP tools — **59** in the main server + **6** product-animation tools (registered when `product_animation_tools.py` loads). Older docs that say “35 tools” are obsolete. |
| **Multi-instance** | `blender_instances` lists, pings, or connects to Bridge ports (default range **9876–9885**). Align `BLENDER_PORT` and `OPENCLAW_PORT` per instance. See `docs/MULTI-BLENDER-ARCHITECTURE.md`. |
| **Runtime** | `OPENCLAW_HOST` / `BLENDER_HOST`, `BLENDER_PORT` / `OPENCLAW_PORT`, `OPENCLAW_TIMEOUT`, `OPENCLAW_COMPACT`, optional `BLENDER_REGISTRY_PATH`, `BLENDER_HEARTBEAT_TIMEOUT` — see `server/runtime_config.py`. |
| **Responses** | JSON envelope with `status`, `tokens_est`, and `data`; optional compact JSON via `OPENCLAW_COMPACT`. `get_scene_info` is summarized to save tokens. |
| **Advanced domains** | Mesh edit, sculpt, geometry nodes, weight paint, shape keys, curves, images, fluid, force fields, cloth, procedural materials, viewport capture, batch ops, scene templates, advanced animation, render presets, scene analyze, scene lighting, forensic scene workflow. |
| **Ecosystem** | Poly Haven, Sketchfab, Hyper3D, Hunyuan3D integrations (API keys / network as documented in-tool). |
| **Product suite** | One-call product animation plus focused tools: material presets, lighting rigs, camera motion, render setup, F-curve easing. |

## Architecture

```
Claude / IDE  ── MCP (stdio) ──►  blender_mcp_server.py  ── TCP ──►  OpenClaw Bridge addon (bpy)
                                 FastMCP · 65 tools              default 127.0.0.1:9876
```

## MCP tools (65)

### Core server (59)

| Category | Tools |
|----------|--------|
| **Connection / scene** | `blender_ping`, `blender_get_scene_info`, `blender_get_object_data`, `blender_scene_operations`, `blender_scene_analyze`, `blender_instances` |
| **Objects** | `blender_create_object`, `blender_modify_object`, `blender_delete_object`, `blender_select_objects`, `blender_duplicate_object`, `blender_transform_object`, `blender_parent_objects` |
| **Modeling** | `blender_apply_modifier`, `blender_boolean_operation`, `blender_uv_operations`, `blender_cleanup`, `blender_mesh_edit`, `blender_sculpt` |
| **Materials / textures** | `blender_set_material`, `blender_shader_nodes`, `blender_procedural_material` |
| **Animation** | `blender_set_keyframe`, `blender_clear_keyframes`, `blender_advanced_animation` |
| **Rendering** | `blender_set_render_settings`, `blender_render`, `blender_viewport`, `blender_compositor`, `blender_viewport_capture`, `blender_render_presets`, `blender_render_quality_audit` |
| **Collections / world** | `blender_manage_collection`, `blender_set_world` |
| **Rigging** | `blender_armature_operations`, `blender_constraint_operations` |
| **Physics / sim** | `blender_physics`, `blender_particle_system`, `blender_fluid_simulation`, `blender_force_field`, `blender_cloth_simulation` |
| **Curves / images / text** | `blender_curve_operations`, `blender_image_operations`, `blender_text_object` |
| **Advanced geometry** | `blender_geometry_nodes`, `blender_weight_paint`, `blender_shape_keys` |
| **I/O** | `blender_import_file`, `blender_export_file`, `blender_save_file` |
| **Batch / templates** | `blender_batch_operations`, `blender_scene_template` |
| **Lighting / scenes** | `blender_scene_lighting`, `blender_forensic_scene` |
| **Ecosystem** | `blender_polyhaven`, `blender_sketchfab`, `blender_hyper3d`, `blender_hunyuan3d` |
| **Escape hatch** | `blender_execute_python` |

### Product animation add-on (6)

`blender_product_animation`, `blender_product_material`, `blender_product_lighting`, `blender_product_camera`, `blender_product_render_setup`, `blender_fcurve_edit`

Phrase-to-tool mapping for artists: `BLENDER_SKILLS_REFERENCE.md`.

## Wire protocol note

MCP exposes tools with a `blender_*` name. The **Bridge** expects command names **without** that prefix (for example `execute_python`, not `blender_execute_python`). See `.claude/skills/blender-mcp/SKILL.md` for the full protocol, quoting rules, and failure modes.

## Quick start

```bash
# 1. Setup (Python venv + deps — see setup.sh)
chmod +x setup.sh && ./setup.sh

# 2. Install the addon in Blender and open a file (Bridge listens on OPENCLAW_PORT)

# 3. Config and wiring
python3 scripts/blender_healthcheck.py
python3 scripts/blender_healthcheck.py --live --port 9876

# 4. Tests and render QA
python3 tests/qa_runner.py
python3 scripts/test_no_flake.py
npm run blender:qa:render

# 5. Point your MCP client at server/blender_mcp_server.py (see claude_mcp_config.json)
```

### Render QA readiness

Before strict render QA, ensure the bridge exposes render-quality audit support:

```bash
python3 scripts/ensure_render_qa_ready.py
```

`npm run blender:qa:render` and `npm run blender:qa:render:strict` run this precheck.

## 3D Forge and Node tooling

The `package.json` **description** summarizes the stack: MCP bridge plus **3D Forge** for trending asset generation. Useful entrypoints:

- `npm run forge:run` — full pipeline (or `forge:run:dry`)
- `npm run forge:gate` — quality gates
- `npm run pool:status` — optional Blender instance pool helpers

## Source of truth

| Doc | Role |
|-----|------|
| `.claude/skills/blender-mcp/SKILL.md` | Operational rules: wire protocol, Python-in-JS quoting, cleanup, validation, 3D Forge paths |
| `BLENDER_SKILLS_REFERENCE.md` | Natural language → tool mapping |
| `CINEMA_RENDER_SKILL_PACK.md` | Cinema / AgX / EXR workflow notes |
| `docs/MULTI-BLENDER-ARCHITECTURE.md` | Concurrent Blender instances |
| `docs/REPOSITORY-ABOUT.md` | Short copy for GitHub metadata |

## Object types (create_object)

cube, sphere, ico_sphere, cylinder, cone, torus, plane, circle, grid, monkey, empty, camera, light_point, light_sun, light_spot, light_area

## Modifier types (apply_modifier)

SUBSURF, MIRROR, ARRAY, BEVEL, SOLIDIFY, BOOLEAN, DECIMATE, REMESH, SHRINKWRAP, SMOOTH, SIMPLE_DEFORM, DISPLACE, WIREFRAME

## Import / export formats

FBX, OBJ, glTF/GLB, STL, PLY, SVG, Alembic, USD/USDC/USDA

## Python execution

`blender_execute_python` runs arbitrary Python in Blender (`bpy`, `mathutils`, …). Assign `__result__` to return data to the client. Treat this as **full access** to the Blender process; keep the Bridge bound to **localhost** unless you understand the risk.
