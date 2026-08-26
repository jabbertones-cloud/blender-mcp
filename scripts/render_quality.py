"""
Shared Blender Cycles render quality settings utility.
Import inside a bpy script; call apply_quality_settings(scene) before rendering.
Run standalone: python3 render_quality.py --test
"""

PRESETS = {
    "draft": {
        "samples": 64,
        "use_adaptive_sampling": True,
        "adaptive_threshold": 0.05,
        "use_denoising": True,
        "denoiser": "OPENIMAGEDENOISE",
    },
    "standard": {
        "samples": 256,
        "use_adaptive_sampling": True,
        "adaptive_threshold": 0.002,
        "use_denoising": True,
        "denoiser": "OPENIMAGEDENOISE",
        "caustics_reflective": False,
        "caustics_refractive": False,
        "sample_clamp_indirect": 10.0,
        "sample_clamp_direct": 0.0,
        "max_bounces": 16,
        "diffuse_bounces": 8,
        "glossy_bounces": 8,
        "transmission_bounces": 12,
        "denoising_normal_pass": True,
        "denoising_albedo_pass": True,
    },
    "high": {
        "samples": 512,
        "use_adaptive_sampling": True,
        "adaptive_threshold": 0.001,
        "use_denoising": True,
        "denoiser": "OPENIMAGEDENOISE",
        "caustics_reflective": False,
        "caustics_refractive": False,
        "sample_clamp_indirect": 10.0,
        "sample_clamp_direct": 0.0,
        "max_bounces": 24,
        "diffuse_bounces": 12,
        "glossy_bounces": 12,
        "transmission_bounces": 16,
        "denoising_normal_pass": True,
        "denoising_albedo_pass": True,
    },
}


def apply_quality_settings(scene=None, preset="standard"):
    import bpy  # only available inside Blender Python environment
    if scene is None:
        scene = bpy.context.scene

    # Auto-switch EEVEE -> Cycles in background mode
    if bpy.app.background and "EEVEE" in scene.render.engine:
        print(f"[render_quality] EEVEE detected in background mode, switching to CYCLES")
        scene.render.engine = "CYCLES"

    if scene.render.engine not in ("CYCLES", "BLENDER_EEVEE_NEXT"):
        scene.render.engine = "CYCLES"

    cfg = PRESETS.get(preset, PRESETS["standard"])
    applied = {"preset": preset, "engine": scene.render.engine}

    if scene.render.engine == "CYCLES":
        cycles = scene.cycles
        cycles.samples = cfg["samples"]
        cycles.use_adaptive_sampling = cfg["use_adaptive_sampling"]
        cycles.adaptive_threshold = cfg["adaptive_threshold"]
        cycles.use_denoising = cfg.get("use_denoising", True)
        cycles.denoiser = cfg.get("denoiser", "OPENIMAGEDENOISE")

        for attr in ("caustics_reflective", "caustics_refractive"):
            if attr in cfg and hasattr(cycles, attr):
                setattr(cycles, attr, cfg[attr])

        for attr in ("sample_clamp_indirect", "sample_clamp_direct",
                     "max_bounces", "diffuse_bounces", "glossy_bounces",
                     "transmission_bounces"):
            if attr in cfg and hasattr(cycles, attr):
                setattr(cycles, attr, cfg[attr])

        # Denoising data passes
        vl = bpy.context.view_layer
        if cfg.get("denoising_normal_pass") and hasattr(vl, "use_pass_denoising_normal"):
            vl.use_pass_denoising_normal = True
        if cfg.get("denoising_albedo_pass") and hasattr(vl, "use_pass_denoising_albedo"):
            vl.use_pass_denoising_albedo = True

        applied.update({k: cfg[k] for k in cfg})

    print(f"[render_quality] Applied preset '{preset}': samples={cfg['samples']}, denoiser={cfg.get('denoiser')}")
    return applied


if __name__ == "__main__":
    import json, sys
    if "--test" in sys.argv:
        print(json.dumps(PRESETS, indent=2, default=str))
        sys.exit(0)
    print("Usage: python3 render_quality.py --test")
