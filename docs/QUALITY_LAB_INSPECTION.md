# Read-only scene-quality inspection

Donor: `AleBrito124356/blender-quality-lab@9b4b0132deb49d17ee9bdf7823cd11fac2f3f2e0` (MIT, API v1).
The dependency is pinned in `requirements.txt`. It runs Blender with isolated preferences and autoexec disabled.

In the MCP server process environment, configure `BLENDER_QUALITY_ROOT` to the root of the user's **authorized scene workspace**, and `BLENDER_QUALITY_BIN` to the tested Blender executable. Both are required. The caller may only pass saved `.blend` files under the configured root, with symlink targets checked. Reports are written into a fresh temporary directory; original Blender scene data is not modified.

Use existing five-tool MCP flow: set goal `check scene quality`, search, inspect the `workflow.quality_inspect` schema, execute with `{"scene_path":"/absolute/authorized/file.blend"}`. Optional `subject` limits review to a specific object, and `strict_contact` treats floating contact as a hard gate. Output contains the full per-gate verdict, `failed_gates`, `warnings`, and only human-readable suggested actions, not the donor's generated Python snippets. A scene may be technically passing yet have warnings that require review.

Acceptance: the same real Blender scene must fail its missing-material gate, then pass after an independently authorized native edit to a **copy**, with source-file SHA-256 unchanged. `BLENDER_E2E=1 BLENDER_QUALITY_TEST_SCENE=/absolute/scene.blend` enables the real fixture; use a real Blender executable in `BLENDER_QUALITY_BIN` and an authorized `BLENDER_QUALITY_ROOT`.

No arbitrary Blender code is introduced into the MCP execution surface. This is a read-only report gate, not autonomous corrective execution or proof of artistic quality.
