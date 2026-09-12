"""Process-local reference loop. VLM is never the pass bit."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mpg", ".mpeg"}

_REF: Dict[str, Any] = {"paths": {}, "tier": "review", "camera": None}

_score_impl: Optional[Callable[..., dict]] = None


def reset() -> None:
    _REF.clear()
    _REF.update({"paths": {}, "tier": "review", "camera": None})


def get_state() -> dict:
    return {
        "paths": dict(_REF.get("paths") or {}),
        "tier": _REF.get("tier") or "review",
        "camera": _REF.get("camera"),
    }


def attach(args: dict) -> dict:
    path = str(args.get("path") or "")
    role = str(args.get("role") or "front")
    _REF.setdefault("paths", {})
    if path:
        _REF["paths"][role] = path
    _REF["tier"] = str(args.get("tier") or "review")
    lower = path.lower()
    is_video = any(lower.endswith(ext) for ext in _VIDEO_EXT)
    if path and not is_video:
        _REF["camera"] = "implied"
    elif is_video:
        _REF["camera"] = None
    return get_state()


def still_path() -> str:
    paths = _REF.get("paths") or {}
    for role in ("front", "three_quarter", "detail"):
        if paths.get(role):
            return str(paths[role])
    for key, value in paths.items():
        if key != "motion_plate" and value:
            return str(value)
    return ""


def set_camera(status: str) -> None:
    _REF["camera"] = status


def score_render(ref_path: str, render_path: str, tier: str = "review") -> dict:
    if _score_impl is not None:
        return _score_impl(ref_path, render_path, tier=tier)
    try:
        from scripts.render_score import score_tiered
    except ModuleNotFoundError:
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root))
        from scripts.render_score import score_tiered
    return score_tiered(ref_path, render_path, tier=tier)


def score_sequence(ref_path: str, frame_paths: List[str], tier: str = "review") -> dict:
    cap = 12 if tier == "draft" else 25 if tier == "review" else 40
    sampled = list(frame_paths)[:cap]
    frames = [score_render(ref_path, path, tier=tier) for path in sampled]
    if not frames:
        return {"passed": False, "frames": [], "worst": None, "error": "no frames"}
    worst = min(frames, key=lambda row: (bool(row.get("passed")), float(row.get("psnr") or 0.0)))
    return {
        "passed": all(bool(row.get("passed")) for row in frames),
        "frames": frames,
        "worst": worst,
        "sampled": len(sampled),
        "cap": cap,
    }


def correct(metrics: dict) -> dict:
    metrics = metrics or {}
    if metrics.get("delta_e_passed") is False and metrics.get("delta_e") is not None:
        return {"next_key": "product.material", "reason": "delta_e", "metrics": metrics}
    if metrics.get("ssim_passed") is False:
        return {"next_key": "product.camera", "reason": "ssim", "metrics": metrics}
    if metrics.get("psnr_passed") is False:
        return {"next_key": "product.render_setup", "reason": "psnr", "metrics": metrics}
    return {"next_key": None, "reason": "pass", "metrics": metrics}


def camera_solve(args: dict | None = None) -> dict:
    plate = str((args or {}).get("path") or get_state()["paths"].get("motion_plate") or "")
    if any(plate.lower().endswith(ext) for ext in _VIDEO_EXT):
        return {"status": "unsupported", "blocking_reason": "libmv_required", "camera": None}
    return {"status": "unsupported", "blocking_reason": "still_unsolved", "camera": None}
