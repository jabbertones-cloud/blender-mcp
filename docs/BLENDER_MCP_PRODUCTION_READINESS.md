# Blender MCP Production Readiness Ledger

Last updated: 2026-09-24

## Status model

Every canonical capability must have exactly one readiness state:

- **DESIGNED** — contract exists, no implementation proof.
- **IMPLEMENTED** — code/handler exists.
- **DETERMINISTIC** — positive + negative + parity tests pass.
- **LIVE_PROVEN** — executed successfully against supported real Blender and read back.
- **PRODUCTION** — live proven + documented execution/rollback/version behavior.
- **EXPERIMENTAL** — intentionally callable but not production authority.
- **UNAVAILABLE** — known unsupported in current runtime/configuration.

Never describe IMPLEMENTED or DETERMINISTIC as production-ready.

## Required evidence per capability

| Evidence | Required |
|---|---|
| Canonical key | yes |
| Search metadata | yes |
| Exact JSON schema | yes |
| No generic fallback | yes |
| Registered addon handler or explicit adapter | yes |
| Positive deterministic test | yes |
| Negative/fail-closed deterministic test | yes |
| Bridge parity test | yes |
| Real Blender execution | yes for LIVE_PROVEN |
| Readback/postcondition | yes for LIVE_PROVEN |
| Supported Blender versions recorded | yes for PRODUCTION |
| Execution policy recorded | yes for PRODUCTION |
| Rollback semantics recorded if mutating | yes for PRODUCTION |

## Current known issues

### Contract generation

Current schema generation imports the full expert server to obtain Pydantic models.
That initializes far more MCP/server plumbing than a schema build should need and can hang/slow generation.

Target:
- move authoritative input models to lightweight modules, or
- generate/check schemas in a controlled build step without server startup.

### Render contract mismatch

Current generated `scene.render` schema lost the real enum `image|animation`.
This proves generated schemas must support explicit bridge-contract overlays.

### Product animation

A canonical path still records `execute_python` for product animation.
Guided production architecture should replace raw Python authority with native typed handlers/workflows before declaring it production.

### Dirty original checkout

The original `blender-mcp` checkout contains many deleted generated/export assets and tracked pycache noise.
Do not use it for overhaul commits.
Use the isolated audit/consolidation worktree until repository hygiene is repaired.

## Live-proof matrix

The active target matrix is:
- Blender 4.5 LTS
- Blender 5.2 LTS

A capability may be LIVE_PROVEN on one runtime and unavailable/experimental on another.
Record that explicitly.

## Release gate

A release candidate fails if any of the following are true:
- guided canonical capability has a generic schema
- advertised bridge command is unregistered
- production capability lacks live proof
- deterministic suite is red
- live healthcheck is red
- sequence can partially mutate before preflight failure
- rollback claims success without confirming undo
- unsupported/stub capability is searchable as production
- `mcp:start` launches expert instead of guided

## 2026-09-24 implementation checkpoint
- Guided registry now has generated, validated schemas and promotes proven hidden handlers rather than creating duplicate public tools.
- Read-only `scene.context`, `scene.inspect`, `mesh.inspect`, `runtime.rna_search`, and `runtime.rna_describe` are canonical capabilities; live Blender 5.1.1 smoke proof passed for all five.
- Fresh-install topology was fixed: installers now copy `new_handlers_phase5.py`, `quality_handlers.py`, and `depsgraph_helpers.py` alongside the bridge. Installed hashes were verified identical to the repo.
- `workflow.sequence` provides bounded canonical composition (max 25 steps), pre-validates every step, forbids nested workflows, creates one rollback boundary, and rolls back on failure. Blender's `ed.undo` is invalid in background context, so rollback was changed to a temporary `.blend` snapshot; real Blender 5.1.1 rollback smoke proof passed.
- Full deterministic suite at this checkpoint: 107 passed, 3 skipped.
