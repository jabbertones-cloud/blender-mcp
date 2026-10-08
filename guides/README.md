# Outcome-driven Blender workflows

The default MCP entrypoint is the five-tool guided router in `server/blender_mcp_guided.py`. **Do not expose the legacy catalog as 78 independent choices.** Search for canonical capabilities, inspect their schemas, and execute only validated keys.

## Universal contract

1. **Observe:** check Blender connection, retrieve scene information, and identify existing objects, collections, camera, and output settings.
2. **Specify:** write the intended observable delta before changing the scene (object identity, transforms, geometry, material, camera, output file).
3. **Execute:** use `search_capabilities`, then `get_capability_schema`, then `execute_capability`. Never guess canonical keys.
4. **Verify:** inspect the resulting scene and compare against the intended delta. For appearance, capture or render and inspect the actual pixels. File existence alone does not prove a good image.
5. **Recover:** on failure, report the exact failing assertion and retry the smallest corrective action. Never silently delete unrelated scene content.
6. **Deliver:** save the Blender project, verify outputs, and report verified facts separately from subjective visual judgments.

## Workflow selection

| User outcome | Guide | Minimum proof |
| --- | --- | --- |
| Create or edit a model | [modeling](modeling.md) | Expected objects, topology, and transforms |
| Assign materials | [materials](materials.md) | Shader parameters and appearance check |
| Light the subject | [lighting](lighting.md) | Lights/world plus rendered exposure inspection |
| Frame the subject | [camera](camera.md) | Camera target and image-space bounding box |
| Produce an image | [render](render.md) | Output dimensions, format, and visual QA |
| Animate a scene | [animation](animation.md) | Keyframes plus multiple-frame motion QA |
| Deform a character | [rigging](rigging.md) | Bone motion produces expected deformation |
| Improve mesh topology | [retopology](retopology.md) | Manifoldness, face budget, and deformation suitability |
| Produce a product packshot | [product-shot](product-shot.md) | Brief checklist and final rendered image |

## Safety and compatibility

Legacy tools remain compatibility paths; guide authors should prefer canonical keys returned by the registry. `blender_execute_python` is an expert escape hatch, not the default: require explicit trust for arbitrary code, limit file access and execution time, and record actions. Scene-clearing templates, destructive cleanup, and overwrites require explicit confirmation. A visual similarity score is advisory, never a substitute for deterministic scene assertions.

## Acceptance metrics

Track first-try outcome success, verified postcondition coverage, median tool calls per successful job, failed-action recovery, and render acceptance. A smaller tool count is not itself a success criterion.
