# Physics — outcome guide

**Outcome:** Configure and bake a controlled simulation.

## When to use
Inspect object scale, collision meshes, current frame range and simulation settings. Choose physics.rigid_body, physics.cloth, physics.fluid, physics.particles or physics.force_field based on physical goal; execute on an owned copy and keep a checkpoint.

## When not to use
Do not substitute animation.keyframe for physical simulation; do not bake before checking collisions, scale, frame span and cache destinations. Avoid a heavy simulation for an unverified draft.

## Preconditions
Supported Blender version, named objects, time range, simulation type, collision targets and storage budget

## Verification
Check simulation modifier or physics settings and evidence from multiple evaluated frames. Report any unsupported bake/job state.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
