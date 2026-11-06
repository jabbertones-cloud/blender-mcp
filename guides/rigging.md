# RIGGING

Inspect armature, mesh transforms and weights. Build or modify bones and constraints with explicit target objects. Verify parenting, vertex group normalization and pose-to-mesh deformation using at least two test poses. Flag collapsed joints, clipping and unintended influence before delivery.

## Failure policy

Stop on an unverified postcondition, preserve evidence, and retry only a scoped correction. Record what was tested and what remains subjective.

## When to use
Binding meshes to armatures, painting weights and validating deformations across multiple poses.

## When not to use
Do not use a rigging tool for topology repair or claim that bone objects prove acceptable skinning weights.
