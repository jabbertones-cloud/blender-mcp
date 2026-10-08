# PRODUCT SHOT

Inputs: target object, visual brief, intended background, material finish, camera angle, aspect ratio, output destination and whether a turntable is needed. Inspect scene and snapshot before changes. Set material, lighting, camera and render settings through discovered canonical capabilities; avoid scene-clearing presets. Render a preview, compare subject framing and visual characteristics to the brief, correct defects, then render final. Verify file format/dimensions and capture a scene-state diff. For turntables inspect multiple frames. The proposed one-call blender_product_shot orchestrator is not assumed implemented.

## Failure policy

Stop on an unverified postcondition, preserve evidence, and retry only a scoped correction. Record what was tested and what remains subjective.

## Existing canonical workflows

Use `workflow.product_hero` for a general premium hero image, `workflow.amazon_packshot` for marketplace main imagery, or `workflow.turntable` for a 360-degree presentation. Discover each workflow through `search_capabilities` and inspect its schema before execution. These are already implemented in `server/capability_executor.py`; do not invent a parallel `blender_product_shot` key. `workflow.sequence` is available for bounded compositions with rollback, but verify the final scene and image independently.

## Evidence distinction

The workflow's return payload may contain operation and visual-observation results. A successful status is not proof of visual acceptability: inspect the resulting pixels, check dimensions and framing, and report subjective deviations from the brief. Never promise an output filename or destructive overwrite unless it is supported by the inspected schema.
