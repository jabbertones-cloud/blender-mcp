#!/usr/bin/env bash
# ship-cad-batch.sh — commit + push the v3.1.1 CAD cross-pollination batch
# (issues #6 needs_input, #10 product_animation migration, #11 SKILL.md docs)
#
# Why this script exists: the Cowork sandbox can't unlink .git/index.lock
# (SMB filesystem doesn't support atomic unlink — see CLAUDE.md landmine #5
# in the openclaw-blender-mcp ops skill). All file edits + tests pass; this
# script just commits + pushes them from your real Mac.
#
# Run from the repo root:
#   chmod +x scripts/ship-cad-batch.sh && ./scripts/ship-cad-batch.sh
#
# Or dry-run first:
#   ./scripts/ship-cad-batch.sh --dry-run

set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

cd "$(git rev-parse --show-toplevel)"
BRANCH=$(git branch --show-current)
echo "→ Branch: $BRANCH"

# ─── Sanity: confirm tests still pass before committing ──────────────────────
echo "→ Running test suite (37 tests, no live Blender required)..."
PYBIN="${PYBIN:-./.venv/bin/python3.12}"
if [[ ! -x "$PYBIN" ]]; then PYBIN="python3"; fi
for t in tests/test_cadam_p1_p2_split_exec.py tests/test_cadam_p3_reference_image.py tests/test_cadam_p4_list_assets.py tests/test_needs_input.py tests/test_product_animation_cadam_migration.py; do
  if [[ -f "$t" ]]; then
    "$PYBIN" "$t" >/dev/null 2>&1 && echo "  ✓ $t" || { echo "  ✗ $t — STOPPING"; exit 1; }
  fi
done

# ─── Commit 1: docs (Issue #11 + research report) ────────────────────────────
echo
echo "→ Commit 1/3: docs (closes #11)"
git add docs/SKILL_V3_1_0_APPEND.md \
        docs/CAD_RESEARCH_REPORT.md \
        docs/CAD_INTEGRATION_PLAN.md \
        docs/CAD_GITHUB_ISSUES.md
if [[ $DRY_RUN -eq 0 ]]; then
  git commit -m "docs(cad): research report + integration plan + GitHub issue specs (closes #11)

Adds the source-of-truth docs for the CAD cross-pollination batch:

- docs/CAD_RESEARCH_REPORT.md  — full repo teardowns + ranked Top-12 + interop matrix
- docs/CAD_INTEGRATION_PLAN.md — how the 12 features fold onto v3.1.0 CADAM
- docs/CAD_GITHUB_ISSUES.md    — full issue specs (mirrored to GH issues #1–#12)
- docs/SKILL_V3_1_0_APPEND.md  — Tier 0–4 taxonomy + PARAMETERS conventions
                                 staged for SKILL.md (write-protected during
                                 v3.1.0 ship-out). Closes #11 once pasted in.

Backed by a 106-source NotebookLM notebook:
https://notebooklm.google.com/notebook/4e13f3d9-732b-4d8b-95cb-d172f62cb813"
fi

# ─── Commit 2: needs_input payload (Issue #6) ────────────────────────────────
echo
echo "→ Commit 2/3: needs_input payload (closes #6)"
git add server/agent_loop.py tests/test_needs_input.py
# blender_mcp_server.py contains BOTH #6 and #10 changes — stage hunks selectively
# via a temporary patch dance. Easiest: add the whole file in commit 2 and let
# commit 3 just add the migration test + product_animation_tools.py.
git add server/blender_mcp_server.py
if [[ $DRY_RUN -eq 0 ]]; then
  git commit -m "feat(needs_input): typed clarification payload for apply_params + router (closes #6)

Pattern from PatrykIti/blender-ai-mcp: when a tool can't proceed because of
missing/unknown input, return a typed needs_input payload so the calling
model can ask the user instead of guessing or regenerating.

Shape:
  {
    \"status\": \"needs_input\",
    \"needs_input\": {
      \"field\": <str>, \"kind\": \"string|number|boolean|array|object|enum|any\",
      \"description\": <prompt>, \"default\"?, \"choices\"?, \"available\"?, \"hint\"?
    }
  }

- needs_input_payload() helper in server/blender_mcp_server.py
- blender_apply_params returns needs_input on:
  * unknown override key (kind=enum, choices=cached_param_names)
  * empty new_values when script has tunable params
  * PARAMETERS rewrite failure
- blender_router_set_goal (server/agent_loop.py) returns needs_input on:
  * empty/whitespace goal (kind=string)
  * invalid profile (kind=enum, choices=4 valid profiles)
- blender_plan returns needs_input on missing goal

8 new tests in tests/test_needs_input.py including a 3-step
needs_input → answer → needs_input → answer → success flow.
All 22 existing CADAM tests still pass.

Note: this commit also includes the run_cadam_script helper for the
sibling Issue #10 commit; the two changesets share blender_mcp_server.py
and were drafted as one batch."
fi

# ─── Commit 3: product_animation CADAM migration (Issue #10) ─────────────────
echo
echo "→ Commit 3/3: product_animation CADAM migration (closes #10)"
git add server/product_animation_tools.py \
        tests/test_product_animation_cadam_migration.py \
        docs/CHANGELOG.md README.md
if [[ $DRY_RUN -eq 0 ]]; then
  git commit -m "refactor(product_animation): migrate 11 execute_python sites to CADAM contract (closes #10)

All 11 raw send_command_fn(\"execute_python\", ...) call sites in
server/product_animation_tools.py now route through run_cadam_script
(added in the previous commit), giving them:

- PARAMETERS-block manifest of input args (audit trail)
- Server-side AST gate (defense-in-depth on top of OPENCLAW_ALLOW_EXEC)
- LRU script cache keyed by stable script_id
- blender_apply_params re-runnability (tweak FOV/energy without re-LLM)

register_product_tools gains an optional 4th arg run_cadam_script_fn.
3-arg legacy callers continue to work unchanged (back-compat).

Sites migrated:
  blender_product_animation: 5 (material, lighting, camera, render, compositor)
  blender_product_material:  1
  blender_product_lighting:  1
  blender_product_camera:    1
  blender_product_render_setup: 2 (render + compositor)
  blender_fcurve_edit:       1
  TOTAL: 11

Bonus fix (caught by the CADAM AST gate during this migration):
  _gen_material_code's join indent was 8 spaces but the f-string template
  indented at 4 spaces, producing 'unexpected indent' SyntaxError on every
  preset that emitted >1 extra. 7/16 presets were silently broken; the
  legacy execute_python path swallowed the error inside Blender.
  All 16 material presets now parse cleanly.

8 new tests in tests/test_product_animation_cadam_migration.py.
Total test count across the batch: 37 passing tests, no live Blender required.

CHANGELOG: full v3.1.1 entry."
fi

# ─── Push ────────────────────────────────────────────────────────────────────
echo
if [[ $DRY_RUN -eq 1 ]]; then
  echo "→ DRY RUN — not pushing. Re-run without --dry-run to commit + push."
else
  echo "→ Pushing $BRANCH to origin..."
  git push -u origin "$BRANCH"
  echo
  echo "✓ Done. Open a PR at:"
  echo "  https://github.com/jabbertones-cloud/blender-mcp/compare/main...$BRANCH?expand=1"
  echo
  echo "  Suggested PR title: v3.1.1 — CAD cross-pollination batch (#6, #10, #11)"
  echo "  Closes: #6, #10, #11 (and partially closes the meta epic #12)"
fi
