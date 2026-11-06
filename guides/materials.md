# MATERIALS

Inspect material slots and shader nodes first. Search material capabilities, inspect schemas, then apply parameters or procedural presets. For PBR sets verify base color, roughness, metallic and normal textures are connected with correct color spaces. Render a close-up under neutral lighting; confirm appearance rather than relying on node existence alone.

## Failure policy

Stop on an unverified postcondition, preserve evidence, and retry only a scoped correction. Record what was tested and what remains subjective.

## When to use
Changing surface color, roughness, shader structure, textures, UVs or baked maps.

## When not to use
Do not use to fix object geometry or illumination; confirm expected material slots before replacing a graph.
