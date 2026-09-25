# Blender MCP Overhaul — Research Notes

Last updated: 2026-09-24

## Goal

Build the most reliable Blender MCP control plane we can, optimized for **task completion**, not public tool count.

The current repo already has broad Blender functionality, but the guided control plane hides too much of it, exposes weak schemas for many capabilities, has branch-stack drift, and does not consistently prove that a nominal capability actually works against Blender.

The solution is not "more tools." The solution is:

**search -> exact contract -> inspect -> preflight -> execute -> verify -> rollback/repair -> prove live**

## Donor architecture map

### PatrykIti/blender-ai-mcp

Key files:
- `_docs/TOOLS/MEGA_TOOLS_ARCHITECTURE.md`
- `blender_addon/infrastructure/rpc_server.py`

What to adapt:
- Grouped task-sized read tools above internal atomics: `scene_context`, `scene_inspect`, `mesh_inspect`.
- Atomic handlers stay the execution substrate; grouped tools shape the agent-facing contract.
- Automatic undo boundaries happen **after successful mutating RPC calls**.
- Read-only, selection-only, and pure output operations are excluded from undo spam.
- Addon-side long-running job state with queued/running/completed/failed/cancelled, progress, cancel request, result/error, timestamps.
- Listener watchdog/self-healing.

Decision:
- Heavy architectural donor for P0 grouped inspection + undo.
- Heavy donor for P1 jobs/watchdog.

### dcc-mcp/dcc-mcp-blender

Key files:
- `src/dcc_mcp_blender/_capability_manifest.py`
- `src/dcc_mcp_blender/_rna_query.py`
- `src/dcc_mcp_blender/skills/blender-rna/SKILL.md`
- `docs/capability-coverage.md`

What to adapt:
- Compact capability manifest instead of flooding tool schemas into context.
- Runtime Blender RNA search and exact type/property descriptions.
- Return property types, ranges, readonly flags, enums, and availability from the **actual running Blender version**.
- Critical rule: **discovery does not grant mutation authority**. Writes still require a typed, approved canonical capability.
- Version-specific unavailable capabilities must report unavailable explicitly.
- Long-running operations require bounded admission, status, cancellation, and terminal artifact validation.

Decision:
- P0 runtime discovery/read-side truth.
- P1 compact manifest/readiness and jobs.

### bpy-dev/blender-mcp

Key files:
- `mcp/blmcp/tools/get_runtime_python_api_docs.py`
- `mcp/blmcp/tools_helpers/blender_cli.py`

What to adapt:
- Runtime Blender Python API documentation from the connected or CLI runtime.
- Saved-file/headless subprocess execution.
- Explicit timeout, bounded diagnostic output, strict JSON framing, token-bound result frames.
- Temporary script files instead of overlong command lines.
- Backend choice: full Blender executable or standalone bpy Python.
- Safe numbered synchronized copies when the live file contains unsaved changes.

Important license note:
- GPL-3.0 project. Adapt concepts/architecture unless deliberate license-compatible porting is chosen.

Decision:
- P1 saved-file/headless runtime and runtime documentation.

### seehiong/blender-mcp-bridge

Key files:
- `blender_mcp_bridge/sessions.py`
- history/undo implementation in the addon

What to adapt:
- Record clean tool/canonical call + arguments.
- Replay validated sequences.
- Parameter expansion, bounded loops/branches.
- History/undo/redo surface.

Decision:
- P1 named workflow recipes/macros compiled into our canonical `workflow.sequence`.
- Do not record secrets or arbitrary raw code.

### sandraschi/blender-mcp

Key file:
- `src/blender_mcp/utils/blender_runtime.py`

What to adapt:
- Prefer live session; fall back to headless when appropriate.
- Different tasks legitimately need different runtimes.

Decision:
- Add per-capability execution policy:
  - `live_required`
  - `live_preferred`
  - `headless_ok`

### mlolson/blender-orchestrator

Useful patterns:
- Semantic placement.
- Collision-free placement.
- Validate transform before mutation.
- Safe movement range.
- Real-world dimensions / placement reasoning.
- Floor-plan/spatial visualization.

Decision:
- We already have much of this in Phase5. Promote and strengthen existing spatial handlers instead of rewriting them.

### XliuXjianX/blender-production-skills

Key concepts:
- Top-level router owns route/stage/retry/rollback state.
- Validators report PASS/WARN/FAIL evidence but cannot silently reroute or delete work.
- Reversible blockout precedes formal production.
- Bounded review/repair budgets.
- Explicit native-system choice and protected/task-owned scope.

Decision:
- Adapt authority separation and bounded recovery.
- Do not import the full artifact bureaucracy into every MCP call.

### djeada/blender-mcp-server

Useful patterns:
- Shared-secret bridge authentication.
- Strict framing.
- Allowed-command allowlist.
- Approved file roots / safe mode.
- Async jobs + status/cancel.
- Headless transport for heavy bakes/renders.

Decision:
- P1 bridge hardening and job execution.

### ahujasid/mcp-for-blender

Useful as:
- Ecosystem compatibility baseline.
- Simple socket/addon architecture reference.

Decision:
- Reference only; not the primary architecture donor.

---

## Findings in our repo

### 1. The guided layer throws away capability knowledge

The expert server already defines structured Pydantic inputs for many operations, but the guided registry historically used generic object schemas for most of them.

Impact:
- Search can find a capability.
- Schema discovery then fails to tell the agent how to call it.
- The model guesses fields/actions/types.
- Blender errors become the discovery mechanism.

Required fix:
- Every canonical capability must have a real schema.
- No silent generic fallback.

### 2. Runtime contract can differ from source model metadata

Example found during this audit:
- Bridge supports render type only `image|animation`.
- Legacy Pydantic model describes that constraint in prose but does not encode the enum.
- Generated JSON schema therefore lost the real enum.

Rule:
- **Live addon/bridge contract wins over generated metadata.**
- Generated schemas may be tightened by explicit bridge-contract overlays.
- Contract tests must compare registry schema to live handler semantics.

### 3. Many already-working addon handlers are invisible to guided discovery

High-value implemented handlers currently hidden or underexposed include:
- duplicate object
- parenting
- collection management
- curves
- shape keys
- weight painting
- particle systems
- force fields
- 3D text
- compositor
- image operations
- clear keyframes
- scene operations
- scene snapshots/diffs
- Phase5 spatial helpers

Rule:
- Promote proven handlers into the canonical catalog without adding public MCP tools.

### 4. Public tool count is not the right optimization target

Keep the guided five-tool front door.
Increase hidden canonical breadth and make search/schema/execute reliable.

### 5. A capability is not "production" because code exists

A production capability requires:
1. canonical key
2. exact schema
3. real registered bridge handler or explicit server-side adapter
4. deterministic positive test
5. deterministic negative/fail-closed test
6. bridge parity test
7. live Blender proof on a supported Blender version
8. readback/postcondition proof
9. known execution policy
10. failure/rollback semantics where mutating

Anything short of this must be reported as experimental, unverified, or unavailable.

## 2026-09-24 implementation checkpoint
- Guided registry now has generated, validated schemas and promotes proven hidden handlers rather than creating duplicate public tools.
- Read-only `scene.context`, `scene.inspect`, `mesh.inspect`, `runtime.rna_search`, and `runtime.rna_describe` are canonical capabilities; live Blender 5.1.1 smoke proof passed for all five.
- Fresh-install topology was fixed: installers now copy `new_handlers_phase5.py`, `quality_handlers.py`, and `depsgraph_helpers.py` alongside the bridge. Installed hashes were verified identical to the repo.
- `workflow.sequence` provides bounded canonical composition (max 25 steps), pre-validates every step, forbids nested workflows, creates one rollback boundary, and rolls back on failure. Blender's `ed.undo` is invalid in background context, so rollback was changed to a temporary `.blend` snapshot; real Blender 5.1.1 rollback smoke proof passed.
- Full deterministic suite at this checkpoint: 107 passed, 3 skipped.
