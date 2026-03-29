# Cinema Render Skill Pack (Blender 5.1+)

Use this pack for commercial/cinema targets where image quality and grading flexibility matter.

## 1) Color Pipeline (AgX / Filmic)

- Prefer `AgX` when available; fallback to `Filmic`.
- Keep exposure conservative (`<= 1.0`) before grading.
- Use contrast look intentionally; avoid over-crushing shadows before comp.

## 2) Multilayer EXR Output

- Format: `OPEN_EXR`
- Depth: `16` or `32`
- Core passes: `Z`, `Normal`
- Recommended extra passes: `Vector` or `Mist`, plus key lighting passes when needed.

## 3) Animation-Safe Denoise Workflow

- Enable Cycles denoise plus adaptive sampling.
- Keep sample floor high enough for motion-heavy frames (avoid aggressive denoise shimmer).
- Tighten adaptive threshold for hero shots.

## 4) Compositing Templates

- Use compositing with pass-based grading.
- Keep depth and normal-driven effects pass-aware.
- Preserve linear workflow until final display transform.

## 5) Render QA Gate

Run `render_quality_audit` before finals and gate on:

- Noise budget (`samples` + adaptive threshold)
- Highlight clipping guard (`AgX/Filmic` + safe exposure)
- Pass completeness (`Z`, `Normal`, plus `Vector`/`Mist`)

## 6) Asset Fidelity Sources

- `sketchfab`: production props/set dressing.
- `polyhaven`: HDRI and PBR materials.
- `hyper3d` / `hunyuan3d`: generated concept assets.

