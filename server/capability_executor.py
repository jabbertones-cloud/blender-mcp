"""Execution layer for canonical Blender capabilities.

Routing decides *what* to do. This module owns *how* a canonical capability is
executed, including MCP-side product wrappers and required visual observations.
No MCP dependency is used here, so dispatch behavior is unit-testable.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict

try:
    from server.capability_registry import registry, Capability
    from server.product_animation_tools import (
        _gen_material_code,
        _gen_lighting_code,
        _gen_camera_code,
        _gen_render_code,
        _gen_compositor_code,
    )
except ModuleNotFoundError:
    from capability_registry import registry, Capability
    from product_animation_tools import (
        _gen_material_code,
        _gen_lighting_code,
        _gen_camera_code,
        _gen_render_code,
        _gen_compositor_code,
    )

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_. -]{1,128}$")
_VISUAL_FAMILIES = {"lighting", "material", "camera", "render"}

WORKFLOW_SCHEMAS: Dict[str, dict] = {
    "workflow.product_hero": {
        "type": "object",
        "required": ["object_name"],
        "properties": {
            "object_name": {"type": "string"},
            "material": {"type": ["string", "null"], "default": None},
            "lighting": {"type": "string", "default": "product_studio"},
            "camera_style": {"type": "string", "default": "hero_reveal"},
            "quality": {"type": "string", "default": "premium"},
            "resolution": {"type": "string", "default": "square_1080"},
            "transparent_bg": {"type": "boolean", "default": False},
            "auto_render": {"type": "boolean", "default": True},
        },
        "additionalProperties": False,
    }
}

WORKFLOW_DESCRIPTIONS = {
    "workflow.product_hero": (
        "Create a polished product hero shot as one deterministic workflow: inspect, optional product material, "
        "studio lighting, hero camera, premium render setup, visual observations, and optional final render."
    )
}


def _require_safe_name(value: str, field: str) -> str:
    value = str(value or "")
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _has_error(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


def _visual_observation(send_command: Callable[[str, dict], dict]) -> dict:
    """Required visual postcondition for appearance-affecting operations."""
    return send_command("viewport_capture", {"base64": True})


def _execute_product(cap: Capability, args: dict, send_command) -> dict:
    key = cap.key
    if key == "product.material":
        object_name = _require_safe_name(args.get("object_name"), "object_name")
        preset = str(args.get("preset") or "white_product")
        code = _gen_material_code(
            preset,
            object_name,
            args.get("material_name"),
            args.get("color_override"),
            args.get("roughness_override"),
            bool(args.get("add_imperfections", False)),
        )
        return send_command("execute_python", {"code": code})

    if key == "product.lighting":
        preset = str(args.get("preset") or "product_studio")
        code = _gen_lighting_code(
            preset,
            bool(args.get("shadow_catcher", True)),
            bool(args.get("gradient_bg", False)),
            args.get("gradient_top"),
            args.get("gradient_bottom"),
            args.get("hdri_path"),
            float(args.get("hdri_strength", 1.5)),
            float(args.get("hdri_rotation", 0.0)),
        )
        return send_command("execute_python", {"code": code})

    if key == "product.camera":
        target = _require_safe_name(args.get("target_object"), "target_object")
        code = _gen_camera_code(
            str(args.get("style") or "hero_reveal"),
            target,
            int(args.get("frames", 120)),
            float(args.get("camera_distance", 4.0)),
            float(args.get("camera_height", 1.2)),
            float(args.get("focal_length", 50.0)),
            float(args.get("f_stop", 2.8)),
            bool(args.get("use_dof", True)),
            int(args.get("fps", 24)),
            args.get("start_distance"),
            args.get("end_distance"),
            args.get("start_focal"),
            args.get("end_focal"),
            args.get("orbit_angle"),
        )
        return send_command("execute_python", {"code": code})

    if key == "product.render_setup":
        code = _gen_render_code(
            str(args.get("quality") or "balanced"),
            str(args.get("resolution") or "1080p"),
            bool(args.get("transparent_bg", True)),
            args.get("output_path"),
            str(args.get("output_format") or "PNG"),
        )
        render_result = send_command("execute_python", {"code": code})
        if _has_error(render_result):
            return render_result
        comp_code = _gen_compositor_code(bool(args.get("bloom", True)), bool(args.get("vignette", True)))
        compositor_result = send_command("execute_python", {"code": comp_code})
        return {"render_setup": render_result, "compositor": compositor_result}

    return registry.execute(key, args, send_command)


def execute_canonical(key: str, arguments: dict, send_command, *, observe_visual: bool = True) -> dict:
    """Execute one canonical capability and attach required visual evidence."""
    cap = registry.resolve_tool(key)
    args = arguments or {}
    if key.startswith("product."):
        result = _execute_product(cap, args, send_command)
    else:
        result = registry.execute(key, args, send_command)

    response = {"capability": key, "result": result}
    if _has_error(result):
        response["status"] = "failed"
        return response

    response["status"] = "ok"
    if observe_visual and (cap.family in _VISUAL_FAMILIES or key.startswith("product.")):
        observation = _visual_observation(send_command)
        response["visual_observation"] = observation
        response["visual_check_required"] = True
        if _has_error(observation):
            response["status"] = "postcondition_failed"
    return response


def execute_workflow(key: str, arguments: dict, send_command) -> dict:
    if key != "workflow.product_hero":
        raise KeyError(f"Unknown workflow capability: {key}")

    args = arguments or {}
    object_name = _require_safe_name(args.get("object_name"), "object_name")
    steps = []

    def run(step_key: str, step_args: dict, *, observe_visual: bool = True) -> bool:
        out = execute_canonical(step_key, step_args, send_command, observe_visual=observe_visual)
        steps.append(out)
        return out.get("status") == "ok"

    # Establish state before mutating anything.
    if not run("scene.info", {}, observe_visual=False):
        return {"workflow": key, "status": "failed", "steps": steps}

    material = args.get("material")
    if material and not run("product.material", {"object_name": object_name, "preset": material}):
        return {"workflow": key, "status": "failed", "steps": steps}

    if not run("product.lighting", {"preset": args.get("lighting", "product_studio"), "shadow_catcher": True}):
        return {"workflow": key, "status": "failed", "steps": steps}

    if not run("product.camera", {"style": args.get("camera_style", "hero_reveal"), "target_object": object_name, "frames": 120}):
        return {"workflow": key, "status": "failed", "steps": steps}

    if not run("product.render_setup", {
        "quality": args.get("quality", "premium"),
        "resolution": args.get("resolution", "square_1080"),
        "transparent_bg": bool(args.get("transparent_bg", False)),
        "bloom": True,
        "vignette": True,
    }):
        return {"workflow": key, "status": "failed", "steps": steps}

    if bool(args.get("auto_render", True)):
        if not run("scene.render", {"type": "still"}, observe_visual=True):
            return {"workflow": key, "status": "failed", "steps": steps}

    return {
        "workflow": key,
        "status": "ok",
        "object_name": object_name,
        "steps": steps,
        "postcondition": "Every appearance-affecting step produced a viewport observation.",
    }
