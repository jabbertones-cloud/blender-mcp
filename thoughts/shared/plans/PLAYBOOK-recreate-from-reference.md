# Playbook: recreate-from-reference (free stack)

No new MCP tools. No paid generation APIs. Branch: `feat/recreate-from-reference-free`.

## Door

`search_capabilities` → `get_capability_schema` → `execute_capability`. Workflows auto-route via `WORKFLOW_SCHEMAS`.

Ranker: `server/workflow_rank.py` (`workflow_match` must return). Tests: `tests/test_guided_workflow_search.py` (imports FastMCP).

## Mesh order (`_free_import_mesh`)

1. `filepath` → `io.import`
2. `IMAGE_TO_3D_WORKER_URL` POST `{image_url}` → `{filepath}`
3. Mapped Poly Haven CC0 `search` + `import_model` (`server/free_stack.py`)
4. Optional Sketchfab downloadable if `SKETCHFAB_API_TOKEN`
5. Fail with `next` + `order`

Never search Poly Haven with `"reconstruct subject"`. Character: auto-weights + `MIXAMO_FBX_PATH`.

## Score

`workflow.reference_score` / `_sequence`. Inject metrics in unit tests. Stills: camera `implied`. Video: libmv or `blocked`. VLM never pass bit.

## FakeBridge

`tests/test_recreate_workflows.py` `RecreateBridge`: polyhaven import_model adds `GenAsset`; ARMATURE_AUTO / detect_features on execute_python.

## CI

`.github/workflows/tool-routing.yml` includes `tests/test_recreate_workflows.py` and py_compile of free-stack modules.

## Honest

Live Blender required for Poly Haven download, CLIP_EDITOR libmv, Mixamo FBX. Unit tests do not prove those.
