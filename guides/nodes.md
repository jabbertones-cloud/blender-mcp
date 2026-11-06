# Nodes — outcome guide

**Outcome:** Create or modify procedural, shader or compositor graphs.

## When to use
Inspect existing node group and sockets through scene.inspect and runtime.rna_describe before editing. Use model.geometry_nodes for geometry graphs; material.shader_nodes for materials; render.compositor for postprocessing. Blender 5.0+ uses scene.compositing_node_group, not scene.node_tree.

## When not to use
Do not recreate user-authored node graphs just to adjust one value; do not mix shader, compositor, and geometry socket contracts. Do not call undocumented RNA enum values.

## Preconditions
Node graph type, owner, interface revision, sockets, target node IDs and expected outputs

## Verification
Read node count, links and socket values, then inspect evaluated geometry or a rendered result; retain an undo checkpoint.

## Failure policy
Stop on unsupported or missing prerequisites, record the exact tool error and preserve existing scene content. Retry only the narrowest approved correction; do not claim a final result without readback.
