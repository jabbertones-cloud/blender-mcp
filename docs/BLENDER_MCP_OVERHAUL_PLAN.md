# Blender MCP Overhaul — Execution Plan

Last updated: 2026-09-24

## Mission

Turn the existing Blender MCP into a small public control plane over a broad, typed, proven capability engine.

Do not ship a huge catalog of nominal calls.
Ship capabilities that complete real Blender work and can prove they worked.

## Non-negotiable architecture

### Public surface

Keep the five-tool guided MCP front door.

The model should discover capabilities through search/schema rather than receive dozens of atomics at startup.

### Internal layers

1. **Capability discovery**
   - compact canonical registry
   - aliases/tags/search terms
   - readiness/availability metadata

2. **Contract layer**
   - exact JSON schema for every canonical capability
   - no generic-any-object fallback
   - bridge-contract overlays for semantics Pydantic cannot express
   - validate before any socket call

3. **Inspection/readback**
   - task-sized structured `scene.context`
   - `scene.inspect`
   - `mesh.inspect`
   - runtime RNA/API discovery
   - typed native dictionaries, not prose

4. **Execution**
   - canonical typed operations
   - no raw Python as the normal escape hatch
   - execution policy: live_required / live_preferred / headless_ok

5. **Composition**
   - bounded `workflow.sequence`
   - all steps preflighted before step 1
   - exact per-step receipts
   - no recursive workflow
   - no arbitrary-code fields

6. **Transactions/recovery**
   - undo boundary after successful scene mutation
   - no undo spam for read-only/selection/export
   - rollback_on_failure with exact mutation count
   - honest rollback receipt

7. **Verification**
   - deterministic readback/postconditions
   - visual verification where relevant
   - live Blender proof

8. **Jobs**
   - queued/running/completed/failed/cancelled
   - progress/status/cancel
   - bounded admission
   - terminal artifact validation

## P0 — make the existing architecture actually usable

### P0.1 Contract correctness

- Finish full schema generation/curation.
- Add explicit contract overlays for bridge-only constraints.
- Fix `scene.render.type = image|animation`.
- Fail build if any guided capability lacks a schema.
- Validate arguments before any scene inspection/socket call.
- Add schema drift tests.

Acceptance:
- zero generic schemas
- invalid required field/type/range causes zero Blender calls
- registry contract and handler contract tests agree

### P0.2 Promote proven hidden handlers

Promote into canonical guided discovery, without new MCP tools:
- `object.duplicate`
- `object.parent`
- `scene.collections`
- `model.curve`
- `animation.shape_keys`
- `rig.weight_paint`
- `physics.particles`
- `physics.force_field`
- `scene.text`
- `render.compositor`
- `image.manage`
- `animation.clear`
- `scene.manage`
- `scene.snapshot`

Phase5 spatial helpers should be mapped rather than reimplemented.

Do not promote:
- incomplete Gaussian splat handlers
- incomplete grease-pencil handlers
- any stub that cannot pass live proof

### P0.3 Mega inspection

Add:
- `scene.context`
- `scene.inspect`
- `mesh.inspect`

Required truth:
- current mode
- active object
- selection
- frame
- scene/render basics
- object transform/type/hierarchy
- mesh vertex/edge/face counts
- evaluated/world dimensions/bounds where available
- modifiers
- material slots
- UV maps/presence
- shape keys
- vertex groups
- selection state

All outputs structured and version-tolerant.

### P0.4 Workflow sequence

Add canonical `workflow.sequence`:
- max 25 steps
- canonical keys only
- preflight all keys + schemas before execution
- no recursion
- no arbitrary Python
- stop on first failure
- receipts for each step
- optional rollback_on_failure
- zero partial execution if the plan is invalid before execution

### P0.5 Undo/rollback

Addon-side:
- safe undo push after successful mutations
- explicit history undo/redo primitive
- skip read-only/export/selection/history calls

Workflow:
- count successful mutating steps
- on failure, undo exact count when rollback enabled
- if any undo fails, report rollback incomplete; never claim success

### P0.6 Runtime truth

Add read-only runtime discovery:
- Blender version
- search RNA type
- describe RNA type/property
- property type
- enum options
- numeric limits
- readonly flag

Rule:
- RNA discovery is knowledge only.
- It never authorizes an arbitrary property write.

### P0.7 Default/run consistency

- `npm run mcp:start` -> guided
- `npm run mcp:start:power` -> expert server
- setup/config/readme must agree

### P0.8 Test and live-proof gate

Deterministic:
- full pytest green
- positive + negative tests for every promoted capability
- bridge parity
- search discovery
- schema validation
- sequence/rollback

Live:
- supported Blender LTS matrix
- persistent background bridge harness
- healthcheck before E2E
- real create/modify/inspect/delete round trip
- real modifier/material/curve/shape-key operations
- real undo rollback
- real sequence
- saved output/readback

No capability reaches production state without live proof.

## P1 — reliability for long jobs and unattended work

### P1.1 Background job manager

For renders, bakes, simulations, generation:
- job_id
- queued/running/completed/failed/cancelled
- progress current/total
- message
- cancellation
- timestamps
- timeout
- terminal artifact validation

### P1.2 Headless saved-file execution

Adapt bpy-dev/sandraschi patterns:
- live preferred when interaction matters
- fresh subprocess for saved-file jobs
- timeout
- bounded stdout/stderr
- strict token-bound result framing
- safe temp script
- synchronized numbered .blend copies if needed
- approved typed operations only in guided mode

### P1.3 Runtime API docs

Exact docs/signatures from the current Blender runtime.
Use for recovery when Blender APIs change.

### P1.4 Recipes/macros

Named reusable workflows compile into `workflow.sequence`.

Examples:
- hard-surface panel
- product hero setup
- turntable
- rig + auto weights
- cloth setup
- physics bake
- UV + material + render
- reference blockout

Recipes are data/contracts, not raw Python blobs.

### P1.5 Bridge hardening

- shared secret
- strict framing
- command allowlist
- approved file roots
- inline code disabled by default on guided path
- listener watchdog

## P2 — task-completion superiority

Build benchmark/eval tasks that measure outcomes rather than tool count.

Required benchmark families:
1. existing-scene inspection without mutation
2. hard-surface modeling
3. curve/cable/path modeling
4. material + UV + lighting
5. rigging + weights
6. shape-key animation
7. procedural/Geometry Nodes scene
8. cloth
9. rigid body / fluid setup
10. spatial placement with collision checks
11. reference reconstruction
12. repair deliberately broken scene
13. 15-25 step composed workflow
14. injected mid-workflow failure + exact rollback
15. saved-file/headless continuation

For each benchmark record:
- success/failure
- number of model/tool round trips
- invalid-call count
- recovery count
- rollback correctness
- artifact/readback validity
- visual/technical score where relevant

## Branch/release strategy

Current authoritative integration base:
- `fix/pr18-integration-hardening`

Local important commit preserved:
- native `product_material` / `product_render_setup` handlers

Do not merge the old PR stack blindly.
Consolidate behavior into one release line.

Every PR must state:
- capabilities added/promoted
- exact schema source
- handler authority
- deterministic tests
- live proof status
- execution policy
- rollback semantics
- known unsupported Blender versions/contexts

## 2026-09-24 implementation checkpoint
- Guided registry now has generated, validated schemas and promotes proven hidden handlers rather than creating duplicate public tools.
- Read-only `scene.context`, `scene.inspect`, `mesh.inspect`, `runtime.rna_search`, and `runtime.rna_describe` are canonical capabilities; live Blender 5.1.1 smoke proof passed for all five.
- Fresh-install topology was fixed: installers now copy `new_handlers_phase5.py`, `quality_handlers.py`, and `depsgraph_helpers.py` alongside the bridge. Installed hashes were verified identical to the repo.
- `workflow.sequence` provides bounded canonical composition (max 25 steps), pre-validates every step, forbids nested workflows, creates one rollback boundary, and rolls back on failure. Blender's `ed.undo` is invalid in background context, so rollback was changed to a temporary `.blend` snapshot; real Blender 5.1.1 rollback smoke proof passed.
- Full deterministic suite at this checkpoint: 107 passed, 3 skipped.
