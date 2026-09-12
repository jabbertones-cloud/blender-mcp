"""Compile motion_spec JSON to animation.keyframe ops."""
from __future__ import annotations


def compile_motion_spec(spec: dict, object_name: str) -> list[dict]:
    ops = []
    for row in (spec or {}).get("keyframes") or []:
        op = {"object_name": object_name, "frame": int(row.get("frame") or 1)}
        if "location" in row:
            op["location"] = list(row["location"])
        if "rotation" in row:
            op["rotation"] = list(row["rotation"])
        if "scale" in row:
            op["scale"] = list(row["scale"])
        ops.append(op)
    return ops
