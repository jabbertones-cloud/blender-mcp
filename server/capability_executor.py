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
_CREATE_KEYS = {"scene.create_object"}
_DELETE_KEYS = {"scene.delete_object"}

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
    },
    "workflow.turntable": {
        "type": "object",
        "required": ["object_name"],
        "properties": {
            "object_name": {"type": "string"},
            "lighting": {"type": "string", "default": "product_studio"},
            "frames": {"type": "integer", "default": 120},
            "quality": {"type": "string", "default": "balanced"},
            "auto_render": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    },
    "workflow.forensic_recon": {
        "type": "object",
        "required": ["action"],
        "properties": {
            "action": {"type": "string"},
        },
        "additionalProperties": True,
    },
    "workflow.amazon_packshot": {
        "type": "object",
        "required": ["object_name"],
        "properties": {
            "object_name": {"type": "string"},
            "material": {"type": ["string", "null"], "default": None},
            "transparent_bg": {"type": "boolean", "default": True},
        },
        "additionalProperties": False,
    },
}

WORKFLOW_DESCRIPTIONS = {
    "workflow.product_hero": (
        "Create a polished product hero shot as one deterministic workflow: inspect, optional product material, "
        "studio lighting, hero camera, premium render setup, visual observations, and optional final render."
    ),
    "workflow.turntable": (
        "Build a 360 product turntable: inspect, product lighting, turntable camera orbit, optional still render."
    ),
    "workflow.forensic_recon": (
        "Run the forensic/accident reconstruction handler as one workflow after a scene inspect."
    ),
    "workflow.amazon_packshot": (
        "Amazon main-image packshot: square 1080, premium samples, product studio lighting, hero camera, transparent background by default."
    ),
}


def _require_safe_name(value: str, field: str) -> str:
    value = str(value or "")
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _has_error(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


def _has_visual_evidence(obs: Any) -> bool:
    if not isinstance(obs, dict) or obs.get("error"):
        return False
    payload = obs.get("data", obs)
    if not isinstance(payload, dict):
        return False
    return any(payload.get(key) for key in ("base64", "image", "image_base64", "filepath", "path"))


def _visual_observation(send_command: Callable[[str, dict], dict]) -> dict:
    """Required visual postcondition for appearance-affecting operations."""
    return send_command("viewport_capture", {"base64": True})


def _object_names(scene: Any) -> list[str]:
    if not isinstance(scene, dict):
        return []
    payload = scene.get("data", scene)
    objects = payload.get("objects") if isinstance(payload, dict) else []
    names = []
    for row in objects or []:
        if isinstance(row, dict) and row.get("name"):
            names.append(str(row["name"]))
        elif isinstance(row, str):
            names.append(row)
    return names


def _scene_summary(send_command: Callable[[str, dict], dict]) -> dict:
    info = send_command("get_scene_info", {})
    names = _object_names(info)
    return {
        "object_names": names,
        "object_count": len(names),
        "error": info.get("error") if isinstance(info, dict) else None,
    }


def _scene_delta(before: dict, after: dict) -> dict:
    before_set = set(before.get("object_names") or [])
    after_set = set(after.get("object_names") or [])
    return {
        "added": sorted(after_set - before_set),
        "removed": sorted(before_set - after_set),
        "count_before": before.get("object_count", 0),
        "count_after": after.get("object_count", 0),
    }


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
    before = _scene_summary(send_command) if cap.mutates_scene else None
    if key.startswith("product."):
        result = _execute_product(cap, args, send_command)
    else:
        result = registry.execute(key, args, send_command)

    response = {"capability": key, "bridge_command": cap.bridge_command, "result": result}
    if _has_error(result):
        response["status"] = "failed"
        return response

    response["status"] = "ok"
    if before is not None:
        after = _scene_summary(send_command)
        delta = _scene_delta(before, after)
        response["scene_delta"] = delta
        if key in _CREATE_KEYS and not delta["added"]:
            response["status"] = "postcondition_failed"
            response["error"] = "create capability reported success but no new object appeared"
        if key in _DELETE_KEYS and not delta["removed"]:
            response["status"] = "postcondition_failed"
            response["error"] = "delete capability reported success but no object disappeared"
    if observe_visual and (cap.family in _VISUAL_FAMILIES or key.startswith("product.")):
        observation = _visual_observation(send_command)
        response["visual_observation"] = observation
        response["visual_check_required"] = True
        if _has_error(observation) or not _has_visual_evidence(observation):
            response["status"] = "postcondition_failed"
            response["error"] = "appearance-affecting step returned no visual evidence"
    return response


def execute_workflow(key: str, arguments: dict, send_command) -> dict:
    if key not in WORKFLOW_SCHEMAS:
        raise KeyError(f"Unknown workflow capability: {key}")

    args = arguments or {}
    steps = []

    def run(step_key: str, step_args: dict, *, observe_visual: bool = True) -> bool:
        out = execute_canonical(step_key, step_args, send_command, observe_visual=observe_visual)
        steps.append(out)
        return out.get("status") == "ok"

    def fail() -> dict:
        return {"workflow": key, "status": "failed", "steps": steps}

    object_name = None
    if key in {"workflow.product_hero", "workflow.turntable", "workflow.amazon_packshot"}:
        object_name = _require_safe_name(args.get("object_name"), "object_name")

    if not run("scene.info", {}, observe_visual=False):
        return fail()

    if key == "workflow.forensic_recon":
        forensic_args = dict(args)
        forensic_args.setdefault("action", "build_road")
        if not run("workflow.forensic_scene", forensic_args, observe_visual=False):
            return fail()
        return {"workflow": key, "status": "ok", "steps": steps}

    if key == "workflow.turntable":
        if not run("product.lighting", {"preset": args.get("lighting", "product_studio"), "shadow_catcher": True}):
            return fail()
        if not run("product.camera", {
            "style": "turntable",
            "target_object": object_name,
            "frames": int(args.get("frames", 120)),
        }):
            return fail()
        if bool(args.get("auto_render", False)):
            if not run("scene.render", {"type": "still"}, observe_visual=True):
                return fail()
        return {
            "workflow": key,
            "status": "ok",
            "object_name": object_name,
            "steps": steps,
            "postcondition": "Turntable camera orbit was created with visual observation.",
        }

    if key == "workflow.amazon_packshot":
        args = {
            **args,
            "lighting": "product_studio",
            "camera_style": "hero_reveal",
            "quality": "premium",
            "resolution": "square_1080",
            "transparent_bg": bool(args.get("transparent_bg", True)),
            "auto_render": True,
        }

    material = args.get("material")
    if material and not run("product.material", {"object_name": object_name, "preset": material}):
        return fail()

    if not run("product.lighting", {"preset": args.get("lighting", "product_studio"), "shadow_catcher": True}):
        return fail()

    if not run("product.camera", {"style": args.get("camera_style", "hero_reveal"), "target_object": object_name, "frames": 120}):
        return fail()

    if not run("product.render_setup", {
        "quality": args.get("quality", "premium"),
        "resolution": args.get("resolution", "square_1080"),
        "transparent_bg": bool(args.get("transparent_bg", False)),
        "bloom": True,
        "vignette": True,
    }):
        return fail()

    if bool(args.get("auto_render", True)):
        if not run("scene.render", {"type": "still"}, observe_visual=True):
            return fail()

    return {
        "workflow": key,
        "status": "ok",
        "object_name": object_name,
        "steps": steps,
        "postcondition": "Every appearance-affecting step produced a viewport observation.",
    }
