"""Read-only Blender Quality Lab API v1 adapter. No fix code is executed."""
from __future__ import annotations
import os
import tempfile
from pathlib import Path

def inspect_saved_scene(args: dict) -> dict:
    root_setting, blender_bin = os.getenv("BLENDER_QUALITY_ROOT"), os.getenv("BLENDER_QUALITY_BIN")
    if not root_setting or not blender_bin:
        return {"status": "blocked", "error": "Set BLENDER_QUALITY_ROOT and BLENDER_QUALITY_BIN explicitly"}
    try:
        root = Path(root_setting).expanduser().resolve(strict=True)
        scene = Path(args["scene_path"]).expanduser().resolve(strict=True)
    except (OSError, ValueError) as exc:
        return {"status": "blocked", "error": f"Scene path unavailable: {type(exc).__name__}"}
    if not (root.is_dir() and scene.is_file() and scene.suffix.lower() == ".blend" and scene.is_relative_to(root)):
        return {"status": "blocked", "error": "Only .blend files inside BLENDER_QUALITY_ROOT may be inspected"}
    if not Path(blender_bin).is_file():
        return {"status": "blocked", "error": "Configured Blender executable is missing"}
    try:
        from blender_quality import api
    except ImportError:
        return {"status": "blocked", "error": "Install pinned blender-quality-lab dependency"}
    try:
        output = tempfile.mkdtemp(prefix="blender-quality-")
        report = api.check(str(scene), output_dir=output, blender=blender_bin,
                           subject=args.get("subject"), strict_contact=args.get("strict_contact", False),
                           preview=False, timeout=120)
    except (api.BlenderError, OSError, ValueError) as exc:
        return {"status": "failed", "error": f"Quality inspection failed: {type(exc).__name__}"}
    warnings = report.get("warnings") or []
    passed = bool(report.get("all_gates_passed"))
    return {"status": "failed" if not passed else "review_required" if warnings else "ok",
            "technical_pass": passed, "failed_gates": report.get("failed_gates") or [],
            "warnings": warnings, "checks": report.get("checks") or [],
            "suggested_actions": [{k: fix[k] for k in ("priority", "problem", "action") if k in fix}
                                  for fix in report.get("fixes") or []],
            "report_json": (report.get("files") or {}).get("report_json"),
            "scene_path": str(scene), "read_only": True}
