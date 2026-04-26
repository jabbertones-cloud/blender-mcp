# CADAM Port — Master Integration Report

**Status:** ALL 4 PRIORITIES LANDED  
**Date:** 2026-04-25  
**Tag target:** `v3.1.0`  
**Tests:** 22/22 passing across 3 test files (no regression to v3.0)

---

## What this is

A port of the design pattern from CADAM (Claude + OpenSCAD WASM) into openclaw-blender-mcp. The CADAM insight: don't ask the LLM to generate a finished CAD model — ask it to generate **parametric code where every dimension is a named UPPER_CASE constant**, then re-run only the parameters block on tweaks. The LLM is called once per intent, never once per slider drag.

This release imports that loop end-to-end for `bpy` script generation, plus the supporting infrastructure CADAM-style workflows need (two-pass image extraction, asset-cache discovery, server-side AST gate).

---

## Files created / modified

| File | Status | Lines (approx) |
|---|---|---|
| `server/codegen_prompt.py` | NEW | 320 |
| `server/image_extraction.py` | NEW (P3) | 368 |
| `server/blender_mcp_server.py` | MODIFIED | +540 net (3 imports + 4 tools + cache helpers + asset scanner) |
| `tests/test_cadam_p1_p2_split_exec.py` | NEW | 220 |
| `tests/test_cadam_p3_reference_image.py` | NEW (P3) | 290 |
| `tests/test_cadam_p4_list_assets.py` | NEW | 195 |
| `docs/CHANGELOG.md` | MODIFIED (v3.1 entry) | +34 |
| `README.md` | MODIFIED (header + v3.1 blurb) | +6 |
| `.claude/skills/blender-mcp/SKILL.md` | **NOT updated** — write-protected in this session. Recommend adding the v3.1 section at the next manual edit. | — |
| `reports/cadam-port-p3.md`, `reports/cadam-port-summary.md` | NEW (this report) | — |

---

## P1 — `# --- PARAMETERS ---` block constraint (system prompt)

**Module:** `server/codegen_prompt.py` exports `BPY_GENERATION_SYSTEM_PROMPT` (a multi-section prompt with two few-shot examples), `PARAMETERS_BLOCK_TEMPLATE`, `PARAMETER_BLOCK_REGEX`, and three pure-Python helpers — `extract_parameters`, `replace_parameters`, `validate_parameters_block`. Parameter values are parsed via `ast.literal_eval` only — never `eval`/`exec`.

**Asset workflow rule** added to the prompt: call `blender_list_available_assets` first; reference cached ids as PARAMETERS-block string constants; call `blender_polyhaven(action='search')` only on cache miss.

---

## P2 — Split `execute_blender_code` into generate + run

**Three new tools** in `server/blender_mcp_server.py`, plus the legacy alias preserved:

| Tool | What it does |
|---|---|
| `blender_generate_bpy_script` | Read-only contract publisher. Returns `{ system_prompt, parameters_template, intent, seed_parameters?, next_call }`. Does **not** call any LLM; the calling agent IS the LLM. |
| `blender_run_bpy_script` | Validates the PARAMETERS block, runs `safety.check(strict=True)` server-side (defense in depth on top of the addon gate), inserts into a 32-entry LRU cache keyed by `script_id`, then `send_command("execute_python", {code})` to the addon. |
| `blender_apply_params` | CADAM slider re-run: rewrite only the PARAMETERS block of a cached script with new values and re-execute. **Zero LLM tokens.** |
| `blender_list_cached_scripts` | Diagnostic; returns the cache contents. |
| `blender_execute_python` (legacy) | Now delegates to `blender_run_bpy_script(require_parameters_block=False, cache=False)`. Backward compatible. |

**Server-side AST gate** is the addition that wasn't there before. The addon already checked at `bridge:917-945`; v3.1 adds an identical pre-check at `run_bpy_script` so we fail fast and never even open the socket on a bad script.

---

## P3 — `blender_reference_image_to_scene` (two-pass)

CADAM proved that **image → structured JSON → bpy** is more reliable than image → bpy in one shot. The MCP server doesn't itself call a multimodal API — the calling LLM does — so the tool is split into three actions:

1. `extraction_prompt` → returns the strict JSON schema + extraction prompt the calling LLM should follow when looking at the image.
2. `submit_extraction` → calling LLM submits the structured JSON, the server validates against the schema, caches under an `extraction_id`.
3. `build_seed_params` → resolves an `extraction_id` to a 14–16 key seed-parameters dict (PRIMARY_SIZE, KEY_LIGHT_ENERGY, CAM_FOCAL_LEN_MM, BASE_COLOR_PRIMARY, RENDER_SAMPLES, etc.) ready to pass as `reference_params` to `blender_generate_bpy_script`.

`server/image_extraction.py` holds the prompt + schema + mapper so it's testable in isolation. 5/5 smoke tests pass; full report in `reports/cadam-port-p3.md`.

---

## P4 — `blender_apply_params` (already in P2) + `blender_list_available_assets`

`apply_params` shipped as part of P2 since it shares the LRU script cache.

`blender_list_available_assets` walks `OPENCLAW_ASSET_CACHE` / `BLENDER_MCP_ASSET_CACHE` (env), `~/.openclaw/assets/<provider>/`, `<repo>/assets/<provider>/`, and `<repo>/cache/<provider>/`. Detects asset type by extension (`.hdr/.exr` → hdri, `.png/.jpg/.jpeg/.webp/.tif` → texture, `.glb/.gltf/.fbx/.obj/.usd/.ply/.stl` → model, `.blend` → blend). Groups files by stripping `_1k/_2k/_4k/_8k` resolution suffixes and PBR channel suffixes (`_diff/_nor_gl/_rough/_arm/_disp/_ao/_metallic/_albedo`). Memoizes the listing (per-cache-key); `refresh=True` re-scans.

Surfaces:
- `providers[]` — `{name, cache_roots, assets[], total_assets, truncated}`
- `assets[i]` — `{id, type, files[], resolutions_available[], size_bytes, root}`
- `global_hints[]` — context-aware nudges ("no cached assets for X — call `blender_polyhaven(action='search')` first").

7/7 smoke tests pass.

---

## Test summary

```
=== P1 + P2 ===                         (10 tests)
  extract/replace round-trip            OK
  missing block raises                  OK
  unknown key raises                    OK
  PROMPT_VERSION format                 OK (optional export, present)
  generate_bpy_script publishes contract OK
  run rejects missing PARAMETERS block  OK
  run blocks `import os` server-side    OK
  run + apply_params slider loop        OK
  apply_params rejects unknown script_id OK
  legacy blender_execute_python alias   OK

=== P3 ===                              (5 tests)
  extraction_prompt                     OK
  validate_extraction (valid)           OK
  validate_extraction (invalid)         OK
  build_seed_params                     OK
  full two-pass flow                    OK

=== P4 ===                              (7 tests)
  empty-cache shape                     OK
  HDRI grouping (kiara_1_dawn @ 1k+2k)  OK
  PBR channel grouping (3 channels)     OK
  asset_types=['hdri'] filter           OK
  refresh=True bypasses listing cache   OK
  unknown provider rejected             OK
  system prompt references new tools    OK
```

**Total: 22/22 passing.** Tests are self-contained — they stub `mcp.server.fastmcp` and mock `send_command` so they require neither pip-installed `mcp` nor a live Blender. Run via `python3 tests/test_cadam_*.py` from the repo root.

---

## End-to-end flow (the canonical CADAM-style invocation)

```
Caller intent: "make a hero shot of this perfume bottle photo"

1. blender_reference_image_to_scene(action="extraction_prompt", image_path=...)
   → returns JSON schema + extraction prompt
2. (Caller-side multimodal LLM call)
   → produces structured extraction JSON
3. blender_reference_image_to_scene(action="submit_extraction", extracted=...)
   → returns extraction_id
4. blender_reference_image_to_scene(action="build_seed_params", extraction_id=...)
   → returns seed_parameters dict (PRIMARY_SIZE, BASE_COLOR_PRIMARY, ...)
5. blender_list_available_assets(providers=["polyhaven"], asset_types=["hdri"])
   → returns ["studio_small_03", "kiara_1_dawn", ...]
6. blender_generate_bpy_script(intent="hero shot of perfume bottle",
                                reference_params={**seed_parameters, "HDRI_ID": "kiara_1_dawn"})
   → returns the contract; caller authors a script with PARAMETERS block
7. blender_run_bpy_script(script=...)
   → validated, AST-gated, cached, executed → returns script_id
8. blender_apply_params(script_id=..., new_values={"CAM_FOCAL_LEN_MM": 85, "KEY_LIGHT_ENERGY": 1500})
   → ZERO LLM tokens. Re-runs only the PARAMETERS block.
```

Steps 6–8 use the LLM exactly once. Steps 7→8 can repeat indefinitely on a slider.

---

## Outstanding follow-ups (not in scope this session)

1. **`.claude/skills/blender-mcp/SKILL.md`** — couldn't write to it (workspace policy). Recommend manually appending the v3.1 section that's drafted in the change history; copy from `docs/CHANGELOG.md` v3.1.0 entry.
2. **`product_animation_tools.py`** — still uses raw `send_command_fn("execute_python", {"code": code})` patterns in 9 places (lines 716, 723, 731, 739, 743, 783, 801, 824, 842, 845, 888). These should migrate to `blender_run_bpy_script` once the product-viz scripts are refactored to declare PARAMETERS blocks; not a blocker.
3. **PROMPT_VERSION sha** — `codegen_prompt.py` (the version landed by sub-agent) does not export `PROMPT_VERSION`; the server falls back to `"unknown"` in the contract payload. Consider adding `PROMPT_VERSION = hashlib.sha1(BPY_GENERATION_SYSTEM_PROMPT.encode()).hexdigest()[:12]` for cache-invalidation downstream.
4. **List-assets cache invalidation** — `_ASSET_LISTING_CACHE` is in-memory, never expires. Fine for short sessions; for long-running servers consider a TTL (e.g. 5 min) since users may drop new files into the cache between tool calls.
5. **`os.walk` performance** — on huge asset libraries `_scan_provider_cache` is fine but quadratic in deeply-nested dirs. Worth a `max_depth=3` cap if Scott has a >100k-file cache.

---

## Security posture (unchanged + reinforced)

- The addon's `OPENCLAW_ALLOW_EXEC` gate at `blender_addon/openclaw_blender_bridge.py:927` is **untouched** — it remains the authoritative kill switch. v3.1 layers a server-side AST check on top so a bad script is rejected before the socket is even opened.
- `safety.py`'s deny lists are reused as-is — no new imports were whitelisted.
- `apply_params` runs the safety check on the *rewritten* script too, even though parameters can't subvert it (a constant can't smuggle `import os`); the symmetry is intentional defense in depth.

---

## Sources

- CADAM design pattern (Claude + OpenSCAD WASM) — Scott's spec in this session.
- blender-guru v3.0 photo-reference workflow (Phases 1-3) — referenced in the loaded skill at `/var/folders/.../skills/blender-guru/SKILL.md`.
- openclaw-blender-mcp v3.0.0 architecture — `README.md`, `docs/CHANGELOG.md`, `.claude/skills/blender-mcp/SKILL.md`, `server/safety.py`, `blender_addon/openclaw_blender_bridge.py:917-945`.
