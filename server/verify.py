"""Evidence-backed geometric verification for the Blender MCP.

This module deliberately does not contain a server-side aesthetic pass bit.
Objective constraints are evaluated from real addon handlers. Subjective visual
judgement is returned as ``review_required`` so a client that can actually see
pixels can make that decision.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

SendCommand = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload(result: Any) -> dict:
    if not isinstance(result, dict):
        return {}
    data = result.get("data", result)
    return data if isinstance(data, dict) else {}


def _error(result: Any) -> Optional[str]:
    if not isinstance(result, dict):
        return "non-dict bridge response"
    if result.get("error"):
        return str(result["error"])
    status = str(result.get("status") or "").lower()
    if status in {"failed", "postcondition_failed", "partial_failure"}:
        return str(result.get("error") or status)
    return None


def _scene_objects(send_command: SendCommand) -> tuple[list[dict], Optional[str]]:
    result = send_command("get_scene_info", {})
    err = _error(result)
    if err:
        return [], err
    rows = _payload(result).get("objects") or []
    return [row for row in rows if isinstance(row, dict)], None


def _scene_object(send_command: SendCommand, name: str) -> tuple[Optional[dict], Optional[str]]:
    rows, err = _scene_objects(send_command)
    if err:
        return None, err
    row = next((row for row in rows if str(row.get("name")) == name), None)
    if row is None:
        return None, f"object '{name}' not found"
    return row, None


def _bbox(send_command: SendCommand, name: str) -> tuple[Optional[dict], Optional[str]]:
    result = send_command("spatial_bbox_world", {"name": name})
    err = _error(result)
    if err:
        return None, err
    box = _payload(result).get("bbox")
    if not isinstance(box, dict):
        return None, f"spatial_bbox_world returned no bbox for '{name}'"
    if not all(isinstance(box.get(key), list) and len(box[key]) == 3 for key in ("min", "max")):
        return None, f"invalid bbox shape for '{name}'"
    return box, None


def _axis_gap(a: dict, b: dict, axis: int) -> float:
    if a["max"][axis] < b["min"][axis]:
        return float(b["min"][axis] - a["max"][axis])
    if b["max"][axis] < a["min"][axis]:
        return float(a["min"][axis] - b["max"][axis])
    return 0.0


def _aabb_distance(a: dict, b: dict) -> float:
    gaps = [_axis_gap(a, b, axis) for axis in range(3)]
    return math.sqrt(sum(gap * gap for gap in gaps))


def _penetration(a: dict, b: dict) -> list[float]:
    return [
        min(float(a["max"][axis]), float(b["max"][axis]))
        - max(float(a["min"][axis]), float(b["min"][axis]))
        for axis in range(3)
    ]


@dataclass
class GCSConstraint:
    type: str
    object: Optional[str] = None
    support: Optional[str] = None
    distance: Optional[float] = None
    tolerance: Optional[float] = None
    direction: Optional[str] = None
    min_vertices: Optional[int] = None
    max_vertices: Optional[int] = None
    material_name: Optional[str] = None
    axis: Optional[str] = None


@dataclass
class VerificationResult:
    passed: bool
    constraint: Dict[str, Any]
    detail: str
    measured: Optional[Dict[str, Any]] = None
    evidence_status: str = "verified"


def _fail(constraint: dict, detail: str, measured: Optional[dict] = None, *, status: str = "unavailable") -> VerificationResult:
    return VerificationResult(False, constraint, detail, measured, status)


def check_constraint(send_command: SendCommand, constraint: Dict[str, Any]) -> VerificationResult:
    """Evaluate one objective constraint from registered bridge evidence."""
    ctype = str(constraint.get("type") or "unknown")
    obj_name = constraint.get("object")
    support_name = constraint.get("support")
    tolerance = float(constraint.get("tolerance", 0.02) or 0.02)

    try:
        if ctype == "on_top_of":
            if not obj_name or not support_name:
                return _fail(constraint, "on_top_of requires object and support")
            obj_box, err = _bbox(send_command, str(obj_name))
            if err:
                return _fail(constraint, err)
            support_box, err = _bbox(send_command, str(support_name))
            if err:
                return _fail(constraint, err)
            vertical_gap = float(obj_box["min"][2] - support_box["max"][2])
            overlap_x = min(obj_box["max"][0], support_box["max"][0]) - max(obj_box["min"][0], support_box["min"][0])
            overlap_y = min(obj_box["max"][1], support_box["max"][1]) - max(obj_box["min"][1], support_box["min"][1])
            passed = abs(vertical_gap) <= tolerance and overlap_x > 0 and overlap_y > 0
            return VerificationResult(
                passed,
                constraint,
                f"vertical gap={vertical_gap:.4f}m, xy overlap=({overlap_x:.4f},{overlap_y:.4f})m",
                {"vertical_gap": vertical_gap, "overlap_x": overlap_x, "overlap_y": overlap_y, "tolerance": tolerance},
            )

        if ctype == "inside":
            if not obj_name or not support_name:
                return _fail(constraint, "inside requires object and support/container")
            obj_box, err = _bbox(send_command, str(obj_name))
            if err:
                return _fail(constraint, err)
            container_box, err = _bbox(send_command, str(support_name))
            if err:
                return _fail(constraint, err)
            inside = all(
                obj_box["min"][axis] >= container_box["min"][axis] - tolerance
                and obj_box["max"][axis] <= container_box["max"][axis] + tolerance
                for axis in range(3)
            )
            return VerificationResult(inside, constraint, f"{obj_name} inside {support_name}: {inside}", {"tolerance": tolerance})

        if ctype == "not_overlapping":
            if not obj_name or not support_name:
                return _fail(constraint, "not_overlapping requires object and support")
            a, err = _bbox(send_command, str(obj_name))
            if err:
                return _fail(constraint, err)
            b, err = _bbox(send_command, str(support_name))
            if err:
                return _fail(constraint, err)
            penetration = _penetration(a, b)
            # Touching at a surface is not volumetric overlap. Require positive
            # penetration beyond tolerance on all axes before declaring overlap.
            overlapping = all(value > tolerance for value in penetration)
            return VerificationResult(
                not overlapping,
                constraint,
                f"volumetric overlap={overlapping}; penetration={penetration}",
                {"penetration": penetration, "tolerance": tolerance, "overlapping": overlapping},
            )

        if ctype == "clearance":
            if not obj_name:
                return _fail(constraint, "clearance requires object")
            required = float(constraint.get("distance", 0.1) or 0.1)
            target_box, err = _bbox(send_command, str(obj_name))
            if err:
                return _fail(constraint, err)
            rows, err = _scene_objects(send_command)
            if err:
                return _fail(constraint, err)
            nearest: Optional[tuple[str, float]] = None
            for row in rows:
                other = str(row.get("name") or "")
                if not other or other == obj_name or str(row.get("type") or "").upper() not in {"MESH", "CURVE", "SURFACE", "FONT", "META"}:
                    continue
                box, box_err = _bbox(send_command, other)
                if box_err or box is None:
                    continue
                distance = _aabb_distance(target_box, box)
                if nearest is None or distance < nearest[1]:
                    nearest = (other, distance)
            if nearest is None:
                return VerificationResult(True, constraint, "no other geometry available to violate clearance", {"nearest": None, "required": required})
            passed = nearest[1] + tolerance >= required
            return VerificationResult(
                passed,
                constraint,
                f"nearest={nearest[0]} at {nearest[1]:.4f}m; required={required:.4f}m",
                {"nearest_object": nearest[0], "min_distance": nearest[1], "required": required, "tolerance": tolerance},
            )

        if ctype in {"has_material", "vertex_count_range", "axis_aligned", "triangulated", "facing"}:
            if not obj_name:
                return _fail(constraint, f"{ctype} requires object")
            row, err = _scene_object(send_command, str(obj_name))
            if err or row is None:
                return _fail(constraint, err or "object evidence unavailable")

            if ctype == "has_material":
                materials = [m for m in (row.get("materials") or []) if m]
                target = constraint.get("material_name")
                passed = (target in materials) if target else bool(materials)
                return VerificationResult(passed, constraint, f"materials={materials}", {"materials": materials, "target": target})

            if ctype == "vertex_count_range":
                value = row.get("vertex_count")
                if not isinstance(value, int):
                    return _fail(constraint, "vertex_count unavailable from scene evidence")
                low = int(constraint.get("min_vertices", 0) or 0)
                high = int(constraint.get("max_vertices", 999999) or 999999)
                passed = low <= value <= high
                return VerificationResult(passed, constraint, f"vertices={value}, range={low}-{high}", {"vertex_count": value, "min": low, "max": high})

            if ctype == "axis_aligned":
                rotation = row.get("rotation_euler")
                if not isinstance(rotation, list) or len(rotation) != 3:
                    return _fail(constraint, "rotation_euler unavailable from scene evidence")
                axis = str(constraint.get("axis") or "z").lower()
                idx = {"x": 0, "y": 1, "z": 2}.get(axis)
                if idx is None:
                    return _fail(constraint, f"unknown axis '{axis}'")
                angle = float(rotation[idx]) % math.tau
                distance_to_axis = min(abs(angle), abs(angle - math.pi), abs(angle - math.tau))
                passed = distance_to_axis <= tolerance
                return VerificationResult(passed, constraint, f"axis {axis} deviation={distance_to_axis:.4f}rad", {"rotation_rad": angle, "deviation": distance_to_axis, "tolerance": tolerance})

            if ctype == "triangulated":
                return _fail(
                    constraint,
                    "triangulated cannot be proven from current registered inspection evidence; refusing to infer from face count",
                    {"face_count": row.get("face_count")},
                    status="not_proven",
                )

            if ctype == "facing":
                return _fail(
                    constraint,
                    "generic object 'facing' is undefined without an explicit semantic forward axis; refusing to guess",
                    {"rotation_euler": row.get("rotation_euler"), "requested_direction": constraint.get("direction")},
                    status="not_proven",
                )

        return _fail(constraint, f"unknown constraint type: {ctype}")
    except Exception as exc:
        return _fail(constraint, f"constraint check error: {exc}")


def run_gcs(send_command: SendCommand, constraints: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = [check_constraint(send_command, constraint) for constraint in constraints]
    passed_count = sum(1 for result in results if result.passed)
    total = len(results)
    return {
        "passed": passed_count == total,
        "failed": total - passed_count,
        "results": [asdict(result) for result in results],
        "score": passed_count / total if total else 1.0,
        "timestamp": _now(),
    }


def vlm_judge(screenshot_b64: str, expected: str, api: str = "client", model: Optional[str] = None) -> Dict[str, Any]:
    """Never fabricate semantic image judgement inside the MCP server.

    The screenshot is returned through MCP tool output for the client/model that
    can actually inspect it. This function intentionally cannot return a visual
    pass, regardless of environment variables or provider names.
    """
    return {
        "passed": False,
        "status": "review_required",
        "confidence": 0.0,
        "reasoning": "Server-side VLM pass is disabled. A client with vision must inspect the returned pixels.",
        "provider": api,
        "model": model,
        "pixel_evidence": bool(isinstance(screenshot_b64, str) and screenshot_b64.strip()),
        "expected": expected,
        "timestamp": _now(),
    }


def verify_action(
    send_command: SendCommand,
    expected: str,
    constraints: Optional[List[Dict[str, Any]]] = None,
    use_vlm: bool = True,
) -> Dict[str, Any]:
    """Verify objective constraints and surface semantic review honestly."""
    constraints = constraints or []
    gcs_result = run_gcs(send_command, constraints)
    detail: Dict[str, Any] = {"expected": expected, "objective": gcs_result}
    vlm_result = None
    review_required = False

    if use_vlm:
        observation = send_command("viewport_capture", {"base64": True})
        obs_err = _error(observation)
        image = _payload(observation).get("base64") if not obs_err else None
        if obs_err or not isinstance(image, str) or not image.strip():
            vlm_result = {
                "passed": False,
                "status": "unavailable",
                "confidence": 0.0,
                "reasoning": obs_err or "viewport returned no base64 pixels",
                "pixel_evidence": False,
                "timestamp": _now(),
            }
        else:
            vlm_result = vlm_judge(image, expected)
            review_required = True
        detail["visual"] = vlm_result

    if not gcs_result["passed"]:
        status = "failed"
        passed = False
        confidence = float(gcs_result["score"])
    elif review_required:
        status = "review_required"
        passed = False
        confidence = 0.0
    elif use_vlm and vlm_result and vlm_result.get("status") == "unavailable":
        status = "failed"
        passed = False
        confidence = 0.0
    else:
        status = "passed"
        passed = True
        confidence = float(gcs_result["score"])

    return {
        "passed": passed,
        "status": status,
        "review_required": review_required,
        "final_confidence": confidence,
        "detail": detail,
        "gcs_result": gcs_result,
        "vlm_result": vlm_result,
        "timestamp": _now(),
    }
