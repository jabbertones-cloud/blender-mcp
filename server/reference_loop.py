"""Session-scoped still/video reference contract. No MCP, no Blender."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

_ROLES = ("front", "three_quarter", "detail", "motion_plate")
_TIERS = ("draft", "review", "delivery")

_REF: Dict[str, Any] = {"paths": {}, "tier": "review", "camera": None}


def reset() -> None:
    _REF["paths"] = {}
    _REF["tier"] = "review"
    _REF["camera"] = None


def get_state() -> Dict[str, Any]:
    return {
        "paths": dict(_REF["paths"]),
        "tier": _REF["tier"],
        "camera": _REF["camera"],
    }


def attach(args: dict) -> dict:
    role = str(args.get("role") or "front")
    if role not in _ROLES:
        raise ValueError(f"role must be one of {_ROLES}")
    path = str(args.get("path") or args.get("image_url") or "")
    if not path:
        raise ValueError("path or image_url is required")
    tier = str(args.get("tier") or _REF["tier"] or "review")
    if tier not in _TIERS:
        raise ValueError(f"tier must be one of {_TIERS}")
    _REF["paths"][role] = path
    _REF["tier"] = tier
    if role != "motion_plate" and _REF["camera"] is None:
        _REF["camera"] = "implied"
    if args.get("camera") is not None:
        _REF["camera"] = args.get("camera")
    return get_state()


def still_path() -> Optional[str]:
    for role in ("front", "three_quarter", "detail"):
        if role in _REF["paths"]:
            return _REF["paths"][role]
    return None


def correct(metrics: dict) -> dict:
    if metrics.get("blocking_reason") == "camera_unsolved" or metrics.get("status") == "blocked":
        return {
            "next_key": "workflow.reference_camera_solve",
            "reason": "camera_unsolved",
            "metrics": metrics,
        }
    if metrics.get("delta_e") is not None and not metrics.get("delta_e_passed"):
        return {"next_key": "product.material", "reason": "delta_e", "metrics": metrics}
    if metrics.get("ssim_passed") is False:
        return {"next_key": "product.camera", "reason": "ssim", "metrics": metrics}
    if metrics.get("psnr_passed") is False:
        return {"next_key": "product.render_setup", "reason": "psnr", "metrics": metrics}
    return {"next_key": None, "reason": "passed", "metrics": metrics}


def score_render(
    ref_path: str,
    render_path: str,
    tier: str = "review",
    score_fn: Optional[Callable[..., dict]] = None,
) -> dict:
    if score_fn is not None:
        return score_fn(ref_path, render_path, tier=tier)
    from scripts.render_score import score_tiered

    return score_tiered(ref_path, render_path, tier=tier)


def camera_solve(args: dict) -> dict:
    plate = args.get("path") or _REF["paths"].get("motion_plate")
    if plate:
        return {
            "status": "deferred",
            "blocking_reason": "use_workflow_reference_camera_solve",
            "path": plate,
            "camera": _REF["camera"],
        }
    return {
        "status": "unsupported",
        "blocking_reason": "still_camera_solve_unsupported",
        "camera": _REF["camera"],
    }
