# Plan: Recreate-from-reference (free stack)

Constraint: no paid generation APIs on the guided 5-tool door.

Shipped on `feat/recreate-from-reference-free`:

- Ranker returns matches (`server/workflow_rank.py`)
- Reference attach/score/correct/camera_solve + sequence score
- Free import: local → MIT worker → mapped Poly Haven → optional Sketchfab
- Character auto-weights + Mixamo path env
- HDRI lighting match + image_to_scene compose
- libmv + motion_spec + motion_qa
- Multiview + auto score when a still is attached
- Executor tripwire: no Tripo/Hunyuan calls
- Live E2E: attach+score numeric fields (skip unless `BLENDER_E2E=1`)

Pass bit: `scripts/render_score.py` / injected metrics. VLM never pass.
