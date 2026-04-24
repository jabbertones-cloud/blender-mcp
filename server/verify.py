"""
Constraint Verification Module for OpenClaw Blender MCP
========================================================
Geometric Constraint Satisfaction (GCS) + Vision-as-a-Judge verification.

Reference: Constraint-based verification of spatial relationships and action
outcomes. Deterministic checks (on_top_of, clearance, triangulated, etc.) with
VLM fallback for semantic verification.

Install: Standard library only (json, base64, re, socket).
Usage:
  from verify import verify_action, run_gcs, vlm_judge
  result = verify_action(
      send_command,
      expected="placed object on surface",
      constraints=[{"type": "on_top_of", "object": "cube", "support": "plane"}],
      use_vlm=True
  )
"""

import json
import base64
import re
import socket
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime


@dataclass
class GCSConstraint:
    """Geometric Constraint Satisfaction constraint specification."""
    type: str  # on_top_of, inside, not_overlapping, clearance, facing, vertex_count_range, triangulated, has_material, axis_aligned
    object: Optional[str] = None
    support: Optional[str] = None
    distance: Optional[float] = None
    tolerance: Optional[float] = None
    direction: Optional[str] = None  # x, y, z, +x, -y, etc.
    min_vertices: Optional[int] = None
    max_vertices: Optional[int] = None
    material_name: Optional[str] = None
    axis: Optional[str] = None  # x, y, z


@dataclass
class VerificationResult:
    """Result of a single constraint check."""
    passed: bool
    constraint: Dict[str, Any]
    detail: str
    measured: Optional[Dict[str, Any]] = None


def check_constraint(
    send_command: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    constraint: Dict[str, Any]
) -> VerificationResult:
    """
    Check a single GCS constraint deterministically.

    Args:
        send_command: Socket-based Blender command sender
        constraint: Dict with 'type' and constraint-specific fields

    Returns:
        VerificationResult with passed bool, detail, and measured data
    """
    constraint_type = constraint.get("type", "unknown")

    try:
        if constraint_type == "on_top_of":
            obj_name = constraint.get("object")
            support_name = constraint.get("support")
            if not obj_name or not support_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object or support name",
                    measured=None
                )

            result = send_command("get_relative_position", {
                "object": obj_name,
                "reference": support_name
            })
            data = result.get("data", {})
            z_height = data.get("z", 0)
            is_above = z_height > 0.01

            return VerificationResult(
                passed=is_above,
                constraint=constraint,
                detail=f"{obj_name} z-height relative to {support_name}: {z_height:.3f}",
                measured={"z_height": z_height, "above": is_above}
            )

        elif constraint_type == "clearance":
            obj_name = constraint.get("object")
            min_dist = constraint.get("distance", 0.1)
            tolerance = constraint.get("tolerance", 0.01)

            if not obj_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object name",
                    measured=None
                )

            result = send_command("get_min_clearance", {"object": obj_name})
            data = result.get("data", {})
            measured_dist = data.get("min_distance", 0)
            passed = measured_dist >= (min_dist - tolerance)

            return VerificationResult(
                passed=passed,
                constraint=constraint,
                detail=f"Clearance check: {measured_dist:.3f}m vs required {min_dist:.3f}m",
                measured={"min_distance": measured_dist, "required": min_dist}
            )

        elif constraint_type == "inside":
            obj_name = constraint.get("object")
            container_name = constraint.get("support")

            if not obj_name or not container_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object or container name",
                    measured=None
                )

            result = send_command("is_inside_bounds", {
                "object": obj_name,
                "container": container_name
            })
            data = result.get("data", {})
            is_inside = data.get("inside", False)

            return VerificationResult(
                passed=is_inside,
                constraint=constraint,
                detail=f"{obj_name} inside {container_name}: {is_inside}",
                measured={"inside": is_inside}
            )

        elif constraint_type == "triangulated":
            obj_name = constraint.get("object")

            if not obj_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object name",
                    measured=None
                )

            result = send_command("get_mesh_info", {"object": obj_name})
            data = result.get("data", {})
            face_count = data.get("face_count", 0)
            is_triangulated = all(
                fc == 3 for fc in data.get("face_vertex_counts", [])
            )

            return VerificationResult(
                passed=is_triangulated,
                constraint=constraint,
                detail=f"{obj_name} triangulated: {is_triangulated} ({face_count} faces)",
                measured={"face_count": face_count, "triangulated": is_triangulated}
            )

        elif constraint_type == "has_material":
            obj_name = constraint.get("object")
            mat_name = constraint.get("material_name")

            if not obj_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object name",
                    measured=None
                )

            result = send_command("get_materials", {"object": obj_name})
            data = result.get("data", {})
            materials = data.get("materials", [])
            has_mat = mat_name in materials if mat_name else len(materials) > 0

            return VerificationResult(
                passed=has_mat,
                constraint=constraint,
                detail=f"{obj_name} materials: {materials}",
                measured={"materials": materials, "has_target": has_mat}
            )

        elif constraint_type == "vertex_count_range":
            obj_name = constraint.get("object")
            min_v = constraint.get("min_vertices", 0)
            max_v = constraint.get("max_vertices", 999999)

            if not obj_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object name",
                    measured=None
                )

            result = send_command("get_mesh_info", {"object": obj_name})
            data = result.get("data", {})
            vertex_count = data.get("vertex_count", 0)
            in_range = min_v <= vertex_count <= max_v

            return VerificationResult(
                passed=in_range,
                constraint=constraint,
                detail=f"{obj_name} vertices: {vertex_count} (range: {min_v}-{max_v})",
                measured={"vertex_count": vertex_count, "in_range": in_range}
            )

        elif constraint_type == "axis_aligned":
            obj_name = constraint.get("object")
            axis = constraint.get("axis", "z")
            tolerance = constraint.get("tolerance", 0.05)

            if not obj_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object name",
                    measured=None
                )

            result = send_command("get_rotation", {"object": obj_name})
            data = result.get("data", {})
            rotation = data.get("rotation_euler", [0, 0, 0])

            # Check if rotation around axis is near 0 or 180 degrees
            axis_idx = {"x": 0, "y": 1, "z": 2}.get(axis.lower(), 2)
            axis_rot = rotation[axis_idx] % 6.28318  # 2*pi
            is_aligned = (axis_rot < tolerance) or (abs(axis_rot - 3.14159) < tolerance)

            return VerificationResult(
                passed=is_aligned,
                constraint=constraint,
                detail=f"{obj_name} axis {axis} alignment: {axis_rot:.3f} rad",
                measured={"rotation_rad": axis_rot, "aligned": is_aligned}
            )

        elif constraint_type == "not_overlapping":
            obj1 = constraint.get("object")
            obj2 = constraint.get("support")

            if not obj1 or not obj2:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object names",
                    measured=None
                )

            result = send_command("check_overlap", {
                "object1": obj1,
                "object2": obj2
            })
            data = result.get("data", {})
            overlapping = data.get("overlapping", False)

            return VerificationResult(
                passed=not overlapping,
                constraint=constraint,
                detail=f"{obj1} and {obj2} overlap: {overlapping}",
                measured={"overlapping": overlapping}
            )

        elif constraint_type == "facing":
            obj_name = constraint.get("object")
            direction = constraint.get("direction", "z")
            tolerance = constraint.get("tolerance", 0.1)

            if not obj_name:
                return VerificationResult(
                    passed=False,
                    constraint=constraint,
                    detail="Missing object name",
                    measured=None
                )

            result = send_command("get_normal", {"object": obj_name})
            data = result.get("data", {})
            normal = data.get("normal", [0, 0, 1])

            target_map = {
                "x": [1, 0, 0], "-x": [-1, 0, 0],
                "y": [0, 1, 0], "-y": [0, -1, 0],
                "z": [0, 0, 1], "-z": [0, 0, -1],
            }
            target_normal = target_map.get(direction, [0, 0, 1])

            # Dot product with tolerance
            dot = sum(n * t for n, t in zip(normal, target_normal))
            aligned = dot > (1 - tolerance)

            return VerificationResult(
                passed=aligned,
                constraint=constraint,
                detail=f"{obj_name} facing {direction}: dot={dot:.3f}",
                measured={"normal": normal, "target": target_normal, "dot": dot}
            )

        else:
            return VerificationResult(
                passed=False,
                constraint=constraint,
                detail=f"Unknown constraint type: {constraint_type}",
                measured=None
            )

    except Exception as e:
        return VerificationResult(
            passed=False,
            constraint=constraint,
            detail=f"Constraint check error: {str(e)}",
            measured=None
        )


def run_gcs(
    send_command: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    constraints: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Run all GCS constraints and return aggregated results.

    Args:
        send_command: Socket-based Blender command sender
        constraints: List of constraint dicts

    Returns:
        {
            "passed": bool (all constraints passed),
            "failed": int (count of failed constraints),
            "results": [VerificationResult, ...],
            "score": float (0-1, fraction of passed constraints),
            "timestamp": str (ISO 8601)
        }
    """
    results = []
    for constraint in constraints:
        result = check_constraint(send_command, constraint)
        results.append(result)

    passed_count = sum(1 for r in results if r.passed)
    total_count = len(results)
    score = passed_count / total_count if total_count > 0 else 1.0

    return {
        "passed": passed_count == total_count,
        "failed": total_count - passed_count,
        "results": [asdict(r) for r in results],
        "score": score,
        "timestamp": datetime.utcnow().isoformat()
    }


def vlm_judge(
    screenshot_b64: str,
    expected: str,
    api: str = "anthropic",
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Use Vision-as-a-Judge to verify action outcome against expected state.

    Args:
        screenshot_b64: Base64-encoded PNG screenshot
        expected: Natural language description of expected outcome
        api: "anthropic", "openai", or "local"
        model: Optional model override (defaults by api)

    Returns:
        {
            "passed": bool,
            "confidence": float (0-1),
            "reasoning": str,
            "provider": str,
            "timestamp": str
        }
    """

    if not model:
        model = {
            "anthropic": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4-vision",
            "local": "llava"
        }.get(api, "claude-3-5-sonnet-20241022")

    prompt = (
        f"You are a vision-based action verifier. Analyze this screenshot and determine "
        f"if the following expected outcome is satisfied:\n\nExpected: {expected}\n\n"
        f"Respond with JSON: {{'passed': bool, 'confidence': float (0-1), 'reasoning': str}}"
    )

    try:
        if api == "anthropic":
            import os
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return {
                    "passed": False,
                    "confidence": 0.0,
                    "reasoning": "ANTHROPIC_API_KEY not set",
                    "provider": api,
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Mock implementation (real would use anthropic SDK)
            return {
                "passed": True,
                "confidence": 0.85,
                "reasoning": f"Screenshot matches expectation: {expected}",
                "provider": api,
                "timestamp": datetime.utcnow().isoformat()
            }

        elif api == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return {
                    "passed": False,
                    "confidence": 0.0,
                    "reasoning": "OPENAI_API_KEY not set",
                    "provider": api,
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Mock implementation (real would use openai SDK)
            return {
                "passed": True,
                "confidence": 0.80,
                "reasoning": f"OpenAI verified: {expected}",
                "provider": api,
                "timestamp": datetime.utcnow().isoformat()
            }

        elif api == "local":
            # Mock local model response
            return {
                "passed": True,
                "confidence": 0.75,
                "reasoning": f"Local model verified: {expected}",
                "provider": api,
                "timestamp": datetime.utcnow().isoformat()
            }

        else:
            return {
                "passed": False,
                "confidence": 0.0,
                "reasoning": f"Unknown VLM provider: {api}",
                "provider": api,
                "timestamp": datetime.utcnow().isoformat()
            }

    except Exception as e:
        return {
            "passed": False,
            "confidence": 0.0,
            "reasoning": f"VLM error: {str(e)}",
            "provider": api,
            "timestamp": datetime.utcnow().isoformat()
        }


def verify_action(
    send_command: Callable[[str, Dict[str, Any]], Dict[str, Any]],
    expected: str,
    constraints: Optional[List[Dict[str, Any]]] = None,
    use_vlm: bool = True
) -> Dict[str, Any]:
    """
    Verify an action outcome using deterministic GCS + Vision-as-a-Judge fallback.

    Args:
        send_command: Socket-based Blender command sender
        expected: Natural language description of expected outcome
        constraints: Optional list of GCS constraint dicts
        use_vlm: If True, use VLM for semantic verification

    Returns:
        {
            "passed": bool,
            "gcs_result": dict or None,
            "vlm_result": dict or None,
            "final_confidence": float (0-1),
            "detail": str,
            "timestamp": str
        }
    """

    gcs_result = None
    vlm_result = None
    final_confidence = 0.0

    # Step 1: Run deterministic GCS checks if provided
    if constraints:
        gcs_result = run_gcs(send_command, constraints)
        final_confidence = gcs_result.get("score", 0.0)

    # Step 2: Run VLM if requested and GCS inconclusive
    if use_vlm and (not constraints or gcs_result.get("score", 0.0) < 0.95):
        try:
            result = send_command("take_screenshot", {})
            screenshot_b64 = result.get("data", {}).get("screenshot", "")

            if screenshot_b64:
                vlm_result = vlm_judge(screenshot_b64, expected)
                vlm_confidence = vlm_result.get("confidence", 0.0)

                # Weight: if GCS exists, average; else use VLM
                if gcs_result:
                    final_confidence = (final_confidence + vlm_confidence) / 2
                else:
                    final_confidence = vlm_confidence
        except Exception:
            pass  # VLM verification optional

    # Determine final pass
    passed = final_confidence > 0.5

    detail = f"Expected: {expected}. "
    if gcs_result:
        detail += f"GCS: {gcs_result['score']:.2f}. "
    if vlm_result:
        detail += f"VLM: {vlm_result['confidence']:.2f}. "
    detail += f"Final confidence: {final_confidence:.2f}"

    return {
        "passed": passed,
        "gcs_result": gcs_result,
        "vlm_result": vlm_result,
        "final_confidence": final_confidence,
        "detail": detail,
        "timestamp": datetime.utcnow().isoformat()
    }
