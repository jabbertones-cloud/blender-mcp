# Tutorial Reproduction Pipeline v0.1.0

**Intent:** Reproduce any step-list Blender tutorial (YouTube, written recipe, course) using NotebookLM grounding + goal-driven agent loop with plan-act-critique feedback.

**Frontmatter**
```
id: tutorial-reproduction-v0.1.0
title: Tutorial Reproduction Pipeline
level: intermediate
time_estimate: 10-20 minutes per tutorial
deps: blender-mcp-v3.0.0+, notebooklm-mcp
skills: router_set_goal, plan, act, critique, verify
```

## Phase 1: Ground & Extract (2-3 min)

**Input:** Tutorial URL, NotebookLM notebook ID, or local recipe file.

1. Call `notebook_query` with:
   > "Extract every step, parameter value (intensity, angle, distance, size), and measured outcome from this tutorial. Quote exact numerical values. If unsure, mark [INFERRED]. Return as numbered list."

2. Parse response → JSON step list:
   ```json
   [
     {
       "step": 1,
       "action": "Create cube",
       "params": { },
       "expected_outcome": "Mesh object at origin"
     },
     {
       "step": 2,
       "action": "Add light at position (2, 1, 2)",
       "params": { "position": [2, 1, 2], "energy": 1000 },
       "expected_outcome": "Light above and to the right"
     }
   ]
   ```

3. **Flag unsupported actions** (rigging, baking, modifiers not yet in MCP surface) before proceeding.

---

## Phase 2: Set Goal & Plan (3-5 min)

**Input:** Extracted step list.

1. Formulate goal as a single paragraph:
   ```
   Reproduce [Tutorial Name]: [high-level outcome]. Steps: (1) [action], 
   (2) [action], (3) [action]. Constraints: [any project-specific limits].
   ```

2. Call:
   ```python
   router_set_goal(goal=..., profile="llm-guided")
   # (Fallback: switch to direct create/modify calls if schema fails)
   ```

3. Call `blender_plan()` to generate step IDs and dependencies.
   - If timeout or schema error: manually issue `blender_act(step_id=f"s{i}", ...)` calls per extracted list.

---

## Phase 3: Act & Critique Loop (5-10 min)

**For each step in extracted list:**

1. **Act:**
   ```python
   blender_act(
     step_id=f"s{i}",
     tool_name="blender_create_object" or "blender_modify_object" or ...,
     tool_args={ **params_from_step_i }
   )
   ```

2. **Critique (every 2-3 steps):**
   ```python
   blender_critique({
     "type": "spatial_constraint",
     "constraint": "KeyLight above product, FillLight opposite",
     "objects": ["KeyLight", "Product", "FillLight"]
   })
   ```

3. **Repair on critique fail:** Issue corrective `blender_act` calls (e.g., reposition, scale, rotate).

4. **Budget tracking:** Stay within 15 acts, 3 critiques per tutorial.

---

## Phase 4: Final Audit (2-3 min)

1. **Verify:**
   ```python
   blender_verify(expected="[outcome from step N]")
   ```
   Expected: positive verdict.

2. **Scene analysis:**
   ```python
   blender_scene_analyze()
   ```
   Confirm object counts, light count, camera, materials match tutorial spec.

3. **Render (if tutorial includes rendering):**
   ```python
   blender_render()
   blender_viewport_capture(save_to_disk=...)
   ```

4. **Drift check (optional):**
   ```python
   blender_drift_status()
   ```

---

## Example: Product-Viz-3-Point Tutorial

**Input:** `product-viz-3point-v0.1.0.md`

**Extracted steps:**
1. Create sphere (product stand-in)
2. Add KeyLight at upper-left (2.5, 1.5, 2.0), energy 1000W
3. Add FillLight opposite (-2.0, -0.5, 1.5), energy 500W
4. Add BackLight behind (0, -3, 2.5), energy 1000W
5. Position camera front-center (0, 3.5, 1), focal length 50mm
6. Set render: Cycles, 256 samples, OptiX denoiser

**Goal:**
> Reproduce product-viz-3point: Set up professional 3-point lighting rig with key light upper-left, fill opposite softer, back light behind subject. Position camera at eye-level, frame product centrally. Enable Cycles 256-sample render with OptiX denoiser.

**Act calls (simplified):**
```
s1: create_object(type=sphere) → Product_Sphere at origin
s2: create_object(type=light_point) → KeyLight
s3: modify_object(KeyLight, location=[2.5, 1.5, 2.0])
s4: create_object(type=light_point) → FillLight
s5: modify_object(FillLight, location=[-2.0, -0.5, 1.5])
s6: create_object(type=light_point) → BackLight
s7: modify_object(BackLight, location=[0, -3, 2.5])
s8: create_object(type=camera) → ProductCamera
s9: modify_object(ProductCamera, location=[0, 3.5, 1])
s10: set_render_settings(engine=cycles, samples=256, denoiser=optix)
```

**Critique at s5:** Check FillLight is opposite KeyLight → pass.
**Verify:** 3-point lighting rig complete, camera framed. → Pass.
**Scene analyze:** 1 sphere, 3 lights, 1 camera, Cycles render. → Match tutorial spec.

---

## Known Limitations

- **MCP surface coverage:** Rigging, baking, modifiers (except simple add/remove), sculpting, geometry nodes require workarounds or are not yet supported.
- **NotebookLM groundtruth:** Large notebooks (300+ sources) may timeout. Fallback to written recipe or YouTube transcript.
- **Render output paths:** Bridge addon path handling incomplete; use `viewport_capture` for preview saves.
- **Schema mismatches:** Tools returning JSON strings instead of dicts cause parser errors. Workaround: switch to direct calls (e.g., `create_object` instead of `plan`).

---

## Success Criteria

- Tutorial steps successfully converted to agent calls.
- Scene after execution matches tutorial spec (object count, light positions ±0.5m, camera framing, render settings).
- All steps complete within 15 agent acts.
- Final `blender_verify` returns positive verdict.
- Drift status stays "ok" throughout.

---

## Output Artifacts

1. **Step-by-step execution log** (JSON or markdown).
2. **Scene snapshot** via `viewport_capture` or final render.
3. **Verification report** from `scene_analyze` + `verify`.
4. **Timing profile** (total agent time, per-step breakdown).

---

**Next Recipe:** Animation-from-Tutorial (keyframe sequences, curve editing, F-curve easing).
