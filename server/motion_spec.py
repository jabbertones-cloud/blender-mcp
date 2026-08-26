"""Compile motion_spec JSON to keyframe ops. LLM edits spec, not F-curves."""
from __future__ import annotations

from typing import Any, Dict, List


def compile_motion_spec(spec: dict, object_name: str) -> List[Dict[str, Any]]:
    if not isinstance(spec, dict):
        raise ValueError("motion_spec must be an object")
    frames = spec.get("keyframes") or spec.get("beats") or []
    ops = []
    for row in frames:
        frame = int(row.get("frame", 1))
        loc = row.get("location")
        rot = row.get("rotation")
        payload: Dict[str, Any] = {"object_name": object_name, "frame": frame}
        if loc is not None:
            payload["location"] = loc
        if rot is not None:
            payload["rotation"] = rot
        ops.append(payload)
    return ops
