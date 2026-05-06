# How to install the v3.1 SKILL.md

The `.claude/skills/blender-mcp/` path is write-protected in the Cowork session, so the polished v3.1 SKILL.md is staged here. To install:

```bash
cd /Users/tatsheen/claw-architect/openclaw-blender-mcp
cp reports/v3.1-skill-staging/SKILL.md .claude/skills/blender-mcp/SKILL.md
git add .claude/skills/blender-mcp/SKILL.md
git commit -m "skill(blender-mcp): v3.1 — CADAM-style parametric workflow

Adds the v3.1 section covering the five new tools (generate_bpy_script,
run_bpy_script, apply_params, reference_image_to_scene, list_available_assets),
the # --- PARAMETERS --- block contract, the 6-step asset-discovery recipe,
and the anti-patterns callout.

Validated via skill-creator eval harness:
- Pass rate: 23% → 100% (4/17 → 17/17 assertions)
- Avg latency: 124s → 102s (–22s)
- 3 evals × old_skill + with_skill, 3 iterations
"
```

## Verifying the diff

```bash
diff -u .claude/skills/blender-mcp/SKILL.md reports/v3.1-skill-staging/SKILL.md
```

Expected: ~230 lines of diff, all additive (frontmatter `description` + `version` bump, one new `## NEW (v3.1):` section before LEGACY, one new tool-taxonomy row).

## What landed

- Frontmatter description expanded with v3.1 trigger keywords (parametric, CADAM, image extraction, asset discovery).
- `version: v3.0.0` → `v3.1.0`.
- Header line updated to v3.1.0.
- `## NEW (v3.1): CADAM-style Parametric Workflow` section (≈220 lines) with:
  - Tool surface table (5 new tools).
  - PARAMETERS-block contract — *exact* `# --- PARAMETERS ---` markers, allowed value types, why the markers must be exact.
  - Anti-patterns callout — five real failure modes from iteration-1.
  - Worked recipe: image → scene (canonical end-to-end flow).
  - Worked recipe: asset cache discovery → render (6-step, with verbatim-copy directive).
  - Server-side safety section reaffirming `OPENCLAW_ALLOW_EXEC` + AST gate.
  - When NOT to use the parametric workflow.
  - Test + reference-code pointers.
- Tool taxonomy table gets one new row: `CADAM Parametric (v3.1) | 5 | ...`.
- Total tool count `~80` → `~85`, categories `23` → `24`.

## Quantitative validation

| Metric | Baseline (v3.0) | v3.1 (final) | Δ |
|---|---|---|---|
| Pass rate | 23% (4/17) | **100% (17/17)** | **+77pp** |
| Avg latency | 124s ± 19s | 102s ± 62s | −22s |
| Avg tokens | 161,863 | 163,829 | +1,966 (≈ flat) |

Iterations: 3. Test surface: 3 prompts × 6 assertions/each (avg).

## Per-eval delta

| Eval | Iter-1 | Iter-2 | Iter-3 |
|---|---|---|---|
| slider-loop-camera-fov | 5/6 | 6/6 | 6/6 |
| image-to-scene-two-pass | 5/5 | 5/5 | 5/5 |
| asset-cache-discovery | 2/6 | 3/6 | 6/6 |
| **TOTAL** | **12/17 (71%)** | **14/17 (82%)** | **17/17 (100%)** |

The asset-cache eval is what each iteration moved — iter-2 added the worked 6-step recipe and anti-pattern callout, iter-3 sharpened the recipe with verbatim-copy directives + visible generate→run separation.

## What changed iteration-by-iteration

**Iteration 1** (initial draft) found three concrete failures:
1. LLM dropped the dashes on `# --- PARAMETERS ---`.
2. LLM invented `blender_polyhaven(action='list')` instead of using the new tool.
3. LLM collapsed `generate_bpy_script` and `run_bpy_script` into a single tool call.

**Iteration 2** added:
- "Anti-patterns" subsection naming all three failure modes.
- A worked 6-step asset-discovery recipe (`discover → branch → download-if-missing → constant-ize → generate → run`).
- An emphatic "marker tokens are exact" callout for `# --- PARAMETERS ---`.

**Iteration 3** sharpened:
- A verbatim-copy directive at the top of the recipe ("don't paraphrase `providers=[...]` into `provider:`").
- Each step explicitly tagged with the tool name (`[tool: blender_list_available_assets]`).
- Steps 5 and 6 visibly separated with their own headers and "Step 5 is its own tool call. It does NOT execute anything." / "Step 6 is its own tool call, distinct from step 5."

## Notes

- The `OPENCLAW_ALLOW_EXEC` gate at `blender_addon/openclaw_blender_bridge.py:917-945` is **untouched** by this skill update — it remains the authoritative kill switch.
- The skill update is pure documentation; no runtime behavior changes.
- All 22 CADAM port tests (`tests/test_cadam_p1_p2_split_exec.py`, `tests/test_cadam_p3_reference_image.py`, `tests/test_cadam_p4_list_assets.py`) still pass.
