# Spatial — outcome guide

**Outcome:** Place objects using measured geometry.

## When to use
Inspect evaluated world bounds and dimensions, then use scene.spatial_query, scene.dimensions or scene.floor_plan to measure. Use scene.semantic_place only after target reference objects are resolved.

## When not to use
Do not guess coordinates from a prompt or overlap-test a base mesh while ignoring unapplied modifiers. Do not move unrelated scene content.

## Preconditions
Object identities, target relation, units, collision/clearance constraints and scene scale

## Verification
Re-read world-space bounds, collision results and object transforms; for layouts inspect top, front and perspective views.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
