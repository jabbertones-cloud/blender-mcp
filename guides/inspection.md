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

## Saved-scene technical quality audit (Blender Quality Lab)

When the user asks to check scene quality, use `workflow.quality_inspect` with a saved `.blend` path inside `BLENDER_QUALITY_ROOT`. The MCP-side `BLENDER_QUALITY_BIN` must identify the intended Blender executable. This starts a separate, read-only, autoexec-disabled Blender inspection. It returns objective failed gates, advisory warnings, and suggested *actions only*, never executable fix snippets. Technical gates passing does **not** mean visual/aesthetic approval; warnings still require review. Apply any correction through separately selected, validated canonical capabilities and then rerun inspection. Never use this report as authorization to execute arbitrary Python.
