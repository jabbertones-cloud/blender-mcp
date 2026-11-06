# Inspection — outcome guide

**Outcome:** Read the current scene without mutation.

## When to use
Use scene.context/scene.inspect for current selection, active mode, object hierarchy and targets. Use mesh.inspect for evaluated mesh data and scene.diagnostics for camera, world, and lights. Use runtime.rna_search/describe to discover version-dependent property names.

## When not to use
Do not create or delete objects to determine scene state. Never guess an object name or Blender enum from older documentation.

## Preconditions
Object names and types, current mode, selected and active items, evaluated bounds and supported RNA properties

## Verification
Compare structured readback to the requested target; fail closed if the object or property does not exist.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
