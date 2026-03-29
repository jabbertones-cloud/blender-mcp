# OpenClaw Blender MCP

Control Blender entirely through AI prompts via the Model Context Protocol (MCP).

## Architecture

```
Claude / AI  ──MCP──►  blender_mcp_server.py  ──TCP──►  Blender Addon (port 9876)
                       (FastMCP, 35 tools)              (socket server + bpy.* execution)
```

## 35 Tools (Full Coverage)

| Category | Tools |
|----------|-------|
| **Scene** | `blender_ping`, `blender_get_scene_info`, `blender_get_object_data`, `blender_scene_operations` |
| **Objects** | `blender_create_object`, `blender_modify_object`, `blender_delete_object`, `blender_select_objects`, `blender_duplicate_object`, `blender_transform_object`, `blender_parent_objects` |
| **Modeling** | `blender_apply_modifier`, `blender_boolean_operation`, `blender_uv_operations`, `blender_cleanup` |
| **Materials** | `blender_set_material`, `blender_shader_nodes` |
| **Animation** | `blender_set_keyframe`, `blender_clear_keyframes` |
| **Rendering** | `blender_set_render_settings`, `blender_render`, `blender_viewport`, `blender_compositor` |
| **Rigging** | `blender_armature_operations`, `blender_constraint_operations` |
| **Physics** | `blender_physics`, `blender_particle_system` |
| **Organization** | `blender_manage_collection`, `blender_set_world` |
| **I/O** | `blender_import_file`, `blender_export_file`, `blender_save_file` |
| **Text** | `blender_text_object` |
| **Advanced** | `blender_execute_python`, `blender_grease_pencil`, `blender_render_quality_audit` |
| **Ecosystem** | `blender_polyhaven`, `blender_sketchfab`, `blender_hyper3d`, `blender_hunyuan3d` |

## Quick Start

```bash
# 1. Setup
chmod +x setup.sh && ./setup.sh

# 2. Open Blender (addon auto-starts)

# 3. Check config and local wiring
python3 scripts/blender_healthcheck.py

# 4. Test against a live Blender bridge
python3 tests/qa_runner.py
python3 scripts/test_no_flake.py
python3 scripts/render_qa_cli.py --profile cinema --min-score 80 --max-failed 0

# 5. Add to Claude config (the setup script generates claude_mcp_config.json)
```

### Render QA readiness

Before any render QA gate run, ensure the running bridge instance has `render_quality_audit` loaded:

```bash
python3 scripts/ensure_render_qa_ready.py
```

The npm scripts `blender:qa:render` and `blender:qa:render:strict` run this precheck automatically.

## Source Of Truth

The operational source of truth for Blender MCP usage is
`.claude/skills/blender-mcp/SKILL.md`.

- Use `BLENDER_SKILLS_REFERENCE.md` as a phrase-to-tool lookup.
- Use `scripts/blender_healthcheck.py` for config and bridge verification.
- Keep `BLENDER_PORT` and `OPENCLAW_PORT` aligned for multi-instance setups.

## Object Types

cube, sphere, ico_sphere, cylinder, cone, torus, plane, circle, grid, monkey, empty, camera, light_point, light_sun, light_spot, light_area

## Modifier Types

SUBSURF, MIRROR, ARRAY, BEVEL, SOLIDIFY, BOOLEAN, DECIMATE, REMESH, SHRINKWRAP, SMOOTH, SIMPLE_DEFORM, DISPLACE, WIREFRAME

## Import/Export Formats

FBX, OBJ, glTF/GLB, STL, PLY, SVG, Alembic, USD/USDC/USDA

## Python Execution

The `blender_execute_python` tool runs arbitrary Python inside Blender with access to `bpy`, `mathutils`, `math`, and `os`. Set `__result__` to return data.
