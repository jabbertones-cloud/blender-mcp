# Workflow — outcome guide

**Outcome:** Run an ordered, rollback-capable sequence of canonical Blender operations.

## When to use
Use workflow.sequence for 1–25 supported canonical steps. First search exact keys, inspect every argument schema and snapshot the scene; only then run. Invalid plans must fail without a single Blender call.

## When not to use
Do not nest workflows, pass arbitrary Python, assume rollback succeeded without readback, or use this tool for long asynchronous renders requiring progress and cancellation.

## Preconditions
Named target scene, canonical keys, schemas, expected per-step mutations, rollback policy and job budget

## Verification
Inspect step receipts, verify no partial writes on preflight failure, confirm rollback on execution failure and compare the final scene state.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
