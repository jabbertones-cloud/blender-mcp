# Product shot — outcome guide

The judgment. The tool is `blender_product_shot`; this file is when to use it,
what it does, and how to read what it hands back.

## The outcome

> **The packshot render of this subject matches this brief.**

| Contract part | What it is here |
|---|---|
| Spec | The brief: subject, material/lighting presets, viewpoint, background, quality, resolution — plus an optional golden image with PSNR/SSIM thresholds |
| Procedure | material → lighting → camera → render settings → compositor → render (this guide) |
| Evidence | Render file path, render-quality audit summary, similarity metrics vs the golden |
| Verdict | `pass` only when the render exists, the audit has no failed checks, and (with a golden) PSNR ≥ threshold and SSIM ≥ threshold |
| Metric | First-try brief-match rate. Failures land in `data/product_shot_failures.jsonl` with their full spec — that file is the improvement backlog |
| Failure log | `data/product_shot_failures.jsonl` (override: `BLENDER_PRODUCT_SHOT_FAILURE_LOG`) |

The tool never returns a bare "success." If it says `pass`, the basis list
says *why* it believes that. If it says `fail`, `whats_off` says what to fix.

## When to use this (and when not to)

**Use `blender_product_shot` when** the job is "a packshot of X": one still,
product on a clean stage, ready to judge or ship. E-commerce hero images,
listing photos, portfolio stills, regression shots against an approved look.

**Use `blender_product_animation` instead when** the product needs to move —
turntable, hero reveal, orbit. A golden compare for motion is a different
test (per-frame) and this tool does not do it.

**Use the generic tools (`blender_set_material`, `blender_scene_lighting`,
`blender_camera_advanced`, …) instead when** you are building or repairing
the scene itself — modeling, fixing topology, weighing a rig. Product shot
assumes the product already exists and is presentable; it dresses a stage,
it does not build the actor.

**Use `blender_product_animation`'s step tools (`blender_product_material`,
`blender_product_lighting`, …) instead when** you want the presets but intend
to break the procedure — custom order, interleaved scene work, no render at
the end. You lose the verdict. That is the trade, and sometimes it is right.

## The brief, field by field

Only `subject` (or `asset_path`) is required. Everything else defaults to a
sane packshot: studio rig, three-quarter view, transparent background,
balanced Cycles at 1080p.

- `subject` — object name in the scene. The tool fails fast and tells you
  what *is* in the scene when the name is wrong. Check `blender_get_scene_info`
  first if unsure.
- `asset_path` — import this file first (path resolved on the Blender host).
  Without `subject`, the first imported mesh becomes the subject.
- `material_preset` — the 16 product materials (glass, chrome, leather…).
  Omit to keep the object's existing material. `color_override` /
  `roughness_override` / `imperfections` adjust it.
- `lighting_preset` — the 6 rigs (studio, jewelry, cosmetics, electronics,
  automotive, food). **Warning: any rig replaces ALL existing lights.** The
  rig owns the stage. If the scene's lighting is hand-tuned and precious,
  this is the wrong tool.
- `background` — `transparent` (alpha; default), `gradient`, or `studio`
  (the rig's flat world colour). `hdri_path` overrides the world entirely.
- `viewpoint` — `three_quarter` (default), `front`, `side`, `top`, `hero_low`.
  Camera distance/height/focal/f-stop/DOF behave like the product camera
  tool, except the rig is frozen at frame 1 — no keyframes.
- `quality` / `resolution` — the product render presets (128/256/512 samples;
  720p→4k plus square/vertical/instagram crops). `bloom`/`vignette` default
  **off**: golden compares want clean renders, and post-processing makes two
  honest renders disagree.
- `golden_image` — the approved render, as a PNG the **MCP server** can read.
  `min_psnr_db` (30) and `min_ssim` (0.90) are the pass bar.

## Preconditions

1. Blender is running with the bridge addon; the tool pings first and fails
   clean rather than half-dressing a stage it cannot reach.
2. `OPENCLAW_ALLOW_EXEC=1` on the Blender side. The procedure ships bpy
   snippets through `execute_python` — the same gate the existing product
   tools already require (see the bridge's Issue #201 hardening). Without
   it, every snippet step errors and the verdict says so.
3. The subject exists and is roughly at scene scale. The camera frames the
   evaluated bounding-box centre, not the object origin — but a product
   modelled 100× too large still gets a 4-metre camera inside it. Rule of
   thumb: products ~0.1–2 m across, `camera_distance` ≈ 3–5× the size.

## How to read the verdict

```json
{ "verdict": "pass", "subject": "Bottle",
  "render": {"path": "/tmp/product_shot.png", "resolution": "1920x1080", "engine": "CYCLES"},
  "audit": {"score": 92, "failed": 0, "failed_checks": []},
  "similarity": {"ssim": 0.97, "psnr_db": 34.1},
  "basis": ["render produced", "render audit clean", "golden-image PSNR/SSIM above thresholds"],
  "whats_off": [] }
```

- `basis` is the honest claim. Without a golden it ends with *"visual match
  itself is unverified"* — settings and existence were proven, the look was
  not. Do not report that as "looks right."
- `whats_off` mixes hard failures (the reason for `fail`) with advisories
  (flat-colour render, audit warnings, golden resampled to a different size).
  Advisories never flip a verdict; they are the tool noticing things.
- Audit *warnings* (denoising off, colour management) are advisory. Audit
  *failures* (wrong engine, below sample floor, DOF required but off) fail
  the shot even when the render file exists — a file existing is not the
  outcome.

## Making goldens

1. Run the shot without a golden. Judge the render yourself (this is the
   one human call in the loop).
2. Copy the approved render to a stable name — `goldens/<subject>-<rig>.png`
   next to your project files. PNG, not interlaced (the comparer is
   stdlib-only and says so rather than guessing).
3. From now on, pass it as `golden_image`. Re-renders that drift (material
   change, rig change, Blender version) fail with the numbers attached.

Threshold sense: same scene, same build re-rendered → PSNR 40+, SSIM 0.99.
Lighting nudge → PSNR ~25–35. Different product pose → below 20. The
defaults (30 dB / 0.90) catch real drift without crying over denoiser noise.
At `quality="fast"` (128 samples), expect PSNR noise around the threshold —
approve goldens at the quality you will ship.

## Gotchas

- **Golden on the wrong host.** The MCP server reads the golden; Blender
  writes the render. If the render file is not readable from the server
  host, the tool re-renders through `viewport_capture` (full engine render
  from the scene camera) to get pixels — correct, but you pay for a second
  render. Same host = free. The response's `evidence.pixels_source` tells
  you which path ran.
- **Keyframes from earlier product-animation work.** This tool's camera is
  static, but if the *subject* carries animation, the shot is taken at
  frame 1. Clear or pose deliberately.
- **Transparent background + studio intent.** `transparent` keeps the rig's
  lighting but alpha's the backdrop. Compositing later? Right choice.
  Showing the image as-is? Pick `gradient` or `studio`.
- **`film_transparent` and the shadow catcher.** The catcher plane only
  shows shadows on the transparent background. Without `shadow_catcher`,
  transparent shots float — usually the first thing a human judge rejects.
- **Audit profile is cinema-strict on settings you did not set.** The
  verdict passes `require_exr=false` and `require_motion_blur=false`
  because a PNG still is a legitimate spec; everything else (engine,
  samples, denoising, colour management) is judged at the cinema bar.

## When the tool can't express it

Fall back to `blender_execute_python` for the missing step, then call the
shot again — and leave a line in the failure log review: a brief the tool
could not express is a procedure bug, and the fix is a better guide or
preset, not a new tool.
