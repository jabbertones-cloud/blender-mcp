# OpenClaw Blender MCP

Blender over MCP, with a **small search-first agent surface** in front of a much larger internal Blender capability catalog.

The project still contains the original ~80 Blender operations for modeling, materials, animation, rendering, rigging, physics, spatial reasoning, product visualization, forensic reconstruction, asset import, and generation. The default MCP entrypoint no longer exposes all of them as equal peers to the model.

## Recommended architecture

```text
Claude / Cursor / MCP client
        |
        | MCP stdio: 5 guided tools
        v
server/blender_mcp_guided.py
        |
        | canonical capability key
        v
server/capability_registry.py
        |
        | validated bridge command only
        v
OpenClaw Blender Bridge :9876
        |
        v
Blender / bpy
```

The full legacy/expert MCP server remains at `server/blender_mcp_server.py`, but it is **not** the recommended model-facing default.

## Guided surface: five tools

`server/blender_mcp_guided.py` exposes only:

1. `router_set_goal` — register the current Blender goal.
2. `router_get_status` — inspect current routing state.
3. `search_capabilities` — search the hidden catalog and return summaries only.
4. `get_capability_schema` — inspect one canonical capability and its argument schema.
5. `execute_capability` — execute one exact canonical capability key.

Typical flow:

```text
router_set_goal("Make a premium chrome product hero render")
  -> search_capabilities("chrome material")
  -> get_capability_schema("scene.set_material")
  -> execute_capability("scene.set_material", {...})
  -> search_capabilities("product softbox lighting")
  -> ...
  -> search_capabilities("render final image")
  -> execute_capability("scene.render", {...})
```

Guided execution deliberately rejects guessed aliases. For example, `blender_create_object` and `create_object` can be resolved internally for compatibility, but `execute_capability` expects the canonical key returned by search, such as `scene.create_object`.

Unknown keys return a distinct `CAPABILITY_NOT_FOUND` error and instruct the agent to search again. Raw model strings are never sent directly to the Blender socket.

## Canonical capability registry

`server/capability_registry.py` is MCP-independent and unit-testable without Blender. A capability owns:

- stable key, such as `scene.create_object`
- family, such as `create`, `material`, `lighting`, `render`, or `inspect`
- description
- Blender bridge command
- legacy MCP name
- input schema
- aliases/tags
- mutation/read semantics

The registry is the dispatch boundary. `CapabilityRegistry.execute()` resolves the canonical capability and sends only its known bridge command.

Examples:

| Family | Canonical capability | Bridge command |
|---|---|---|
| create | `scene.create_object` | `create_object` |
| mutate | `scene.modify_object` | `modify_object` |
| mutate | `scene.delete_object` | `delete_object` |
| lighting | `scene.lighting_preset` | `scene_lighting` |
| material | `scene.set_material` | `set_material` |
| inspect | `scene.info` | `get_scene_info` |
| render | `scene.render` | `render` |
| camera | `scene.camera` | `camera_advanced` |
| world | `scene.world` | `set_world` |

Specialized tools remain available when intent is specific, for example product lighting, product camera, UV unwrap, texture baking, procedural materials, semantic placement, forensic reconstruction, or asset providers.

## Planner / actor contract

The Planner-Actor-Critic implementation remains available for clients that use it, but it now uses the same canonical registry.

`PlanStep` stores both:

- `tool_hint`: canonical capability key
- `args`: planned arguments

`blender_act` follows this contract:

```text
name = input.tool_name OR step.tool_hint
resolve name through CapabilityRegistry
reject unknown names before socket access
arguments = input.tool_args OR step.args
send only capability.bridge_command
```

The planner validates every stored hint. It does not store `None` tool hints. Failed critiques add a real `scene.info` diagnostic step rather than prose pretending to be a tool name.

Render-oriented plans reserve final slots for render-quality audit and final render so `max_steps` cannot silently cut off the finish.

## Deterministic router floor

The initial router is intentionally simple: family-first lexical rules plus keyword scoring. This is a correctness floor, not an embedding project.

CI asserts examples including:

```text
"add a cube"                 -> create
"three point lights"         -> lighting
"make it look like chrome"   -> material
"render a png"               -> render
"what's in the scene"        -> inspect
"move the camera"            -> camera
"delete the default cube"    -> mutate
"hdri background"            -> world
```

Ambiguous instructions fall back to inspection instead of inventing a mutation.

## Quick start

```bash
chmod +x setup.sh
./setup.sh
```

Install and enable the OpenClaw Blender Bridge addon in Blender, then prove the bridge is live:

```bash
python3 scripts/blender_healthcheck.py --live --port 9876
```

Use the provided `claude_mcp_config.json`, which now points to:

```text
server/blender_mcp_guided.py
```

Default bridge address:

```text
127.0.0.1:9876
```

Multi-instance convention remains 9876–9885.

## Router tests: trusted CI floor

Run locally:

```bash
python -m pip install pytest pydantic
python -m pytest tests/test_tool_choice.py tests/test_act_dispatch.py tests/test_capability_router.py -q
```

The `Tool Routing Gate` workflow hard-fails if routing modules do not compile or these tests fail. It does **not** use `continue-on-error`, `|| true`, or an offline-success fallback.

## Evaluation status

The historical LEGO-Eval / BlenderGym adapters are **not currently trusted release evidence**. They previously contained offline success paths, placeholder/random scoring, generic cube execution, and non-GCS constraints.

The GitHub evaluation workflow has therefore been changed to **live-only**. It requires a self-hosted runner labelled `blender-eval`, a real Blender bridge on port 9876, and a successful healthcheck before running:

```bash
python eval/run.py --suite lego-eval --blender-port 9876
python eval/run.py --suite blender-gym --blender-port 9876
python eval/run.py --suite all --blender-port 9876
```

There is no valid `--bench` flag in the current runner. Do not report legacy benchmark scores as quality evidence until the adapters themselves are rebuilt around real task execution and scene assertions.

## Security

`blender_execute_python` remains disabled by default. Enable only with:

```bash
export OPENCLAW_ALLOW_EXEC=1
```

The AST safety layer rejects dangerous imports/builtins unless the deprecated unsafe override is explicitly enabled. The bridge should remain bound to localhost unless authentication/network controls are configured.

## Full expert surface

For debugging, compatibility, or expert clients that intentionally want every direct operation, run:

```bash
python server/blender_mcp_server.py
```

This exposes the broad atomic catalog. For normal LLM use, prefer:

```bash
python server/blender_mcp_guided.py
```

The design principle is simple: **keep the implementation breadth, hide the decision complexity.**

## Important source files

| File | Purpose |
|---|---|
| `server/blender_mcp_guided.py` | recommended five-tool MCP front door |
| `server/capability_registry.py` | canonical identities, schemas, alias resolution, dispatch |
| `server/capability_router.py` | lexical ranking metadata / specialized intent cues |
| `server/agent_loop.py` | routed Planner-Actor-Critic compatibility layer |
| `server/session_state.py` | persisted plan steps, args, results, critique history |
| `server/verify.py` | GCS + VLM verification |
| `server/blender_mcp_server.py` | full expert/legacy atomic MCP surface |
| `.github/workflows/tool-routing.yml` | mandatory deterministic router/dispatch gate |
| `.github/workflows/eval.yml` | live-only Blender evaluation workflow |

## Next quality milestone

The next benchmark pass should replace the legacy evaluation adapters with real goal-conditioned trajectories that measure:

- correct capability/family selection
- argument correctness
- actual scene delta
- unintended side effects
- geometric constraint success
- visual/viewport success
- retries to completion
- tool calls/tokens to completion

Only then should LEGO/Gym-style scores become release gates again.
