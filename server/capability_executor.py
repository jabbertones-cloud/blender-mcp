"""Execution layer for canonical Blender capabilities.

Routing decides *what* to do. This module owns *how* a canonical capability is
executed, including MCP-side wrappers and required visual observations.
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
    from server.spatial_tools import _format_ascii_floor_plan, _load_dimensions_db, _resolve_alias
except ModuleNotFoundError:
    from capability_registry import registry, Capability
    from product_animation_tools import (
        _gen_material_code,
        _gen_lighting_code,
        _gen_camera_code,
        _gen_render_code,
        _gen_compositor_code,
    )
    from spatial_tools import _format_ascii_floor_plan, _load_dimensions_db, _resolve_alias

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_. -]{1,128}$")
_VISUAL_FAMILIES = {"lighting", "material", "camera", "render"}
_CREATE_KEYS = {"scene.create_object"}
_DELETE_KEYS = {"scene.delete_object"}

WORKFLOW_SCHEMAS: Dict[str, dict] = {
    "workflow.product_hero": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "material": {"type": ["string", "null"], "default": None}, "lighting": {"type": "string", "default": "product_studio"}, "camera_style": {"type": "string", "default": "hero_reveal"}, "quality": {"type": "string", "default": "premium"}, "resolution": {"type": "string", "default": "square_1080"}, "transparent_bg": {"type": "boolean", "default": False}, "auto_render": {"type": "boolean", "default": True}}, "additionalProperties": False},
    "workflow.turntable": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "lighting": {"type": "string", "default": "product_studio"}, "frames": {"type": "integer", "default": 120}, "quality": {"type": "string", "default": "balanced"}, "auto_render": {"type": "boolean", "default": False}}, "additionalProperties": False},
    "workflow.forensic_recon": {"type": "object", "required": ["action"], "properties": {"action": {"type": "string"}}, "additionalProperties": True},
    "workflow.amazon_packshot": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "material": {"type": ["string", "null"], "default": None}, "transparent_bg": {"type": "boolean", "default": True}}, "additionalProperties": False},
}

WORKFLOW_DESCRIPTIONS = {
    "workflow.product_hero": "Create a polished product hero shot as one deterministic workflow: inspect, optional product material, studio lighting, hero camera, premium render setup, visual observations, and optional final render.",
    "workflow.turntable": "Build a 360 product turntable: inspect, product lighting, turntable camera orbit, optional still render.",
    "workflow.forensic_recon": "Run the forensic/accident reconstruction handler as one workflow after a scene inspect.",
    "workflow.amazon_packshot": "Amazon main-image packshot: square 1080, premium samples, product studio lighting, hero camera, transparent background by default.",
}


def _require_safe_name(value: str, field: str) -> str:
    value = str(value or "")
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _has_error(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


def _has_visual_evidence(obs: Any) -> bool:
    """Return True only when the bridge returned actual image pixels."""
    if not isinstance(obs, dict) or obs.get("error"):
        return False
    payload = obs.get("data", obs)
    if not isinstance(payload, dict):
        return False
    for key in ("base64", "image", "image_base64"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False


def _visual_observation(send_command: Callable[[str, dict], dict]) -> dict:
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
    return {"object_names": names, "object_count": len(names), "error": info.get("error") if isinstance(info, dict) else None}


def _scene_delta(before: dict, after: dict) -> dict:
    before_set = set(before.get("object_names") or [])
    after_set = set(after.get("object_names") or [])
    return {"added": sorted(after_set - before_set), "removed": sorted(before_set - after_set), "count_before": before.get("object_count", 0), "count_after": after.get("object_count", 0)}


def _execute_product(cap: Capability, args: dict, send_command) -> dict:
    key = cap.key
    if key == "product.material":
        object_name = _require_safe_name(args.get("object_name"), "object_name")
        code = _gen_material_code(str(args.get("preset") or "white_product"), object_name, args.get("material_name"), args.get("color_override"), args.get("roughness_override"), bool(args.get("add_imperfections", False)))
        return send_command("execute_python", {"code": code})
    if key == "product.lighting":
        code = _gen_lighting_code(str(args.get("preset") or "product_studio"), bool(args.get("shadow_catcher", True)), bool(args.get("gradient_bg", False)), args.get("gradient_top"), args.get("gradient_bottom"), args.get("hdri_path"), float(args.get("hdri_strength", 1.5)), float(args.get("hdri_rotation", 0.0)))
        return send_command("execute_python", {"code": code})
    if key == "product.camera":
        target = _require_safe_name(args.get("target_object"), "target_object")
        code = _gen_camera_code(str(args.get("style") or "hero_reveal"), target, int(args.get("frames", 120)), float(args.get("camera_distance", 4.0)), float(args.get("camera_height", 1.2)), float(args.get("focal_length", 50.0)), float(args.get("f_stop", 2.8)), bool(args.get("use_dof", True)), int(args.get("fps", 24)), args.get("start_distance"), args.get("end_distance"), args.get("start_focal"), args.get("end_focal"), args.get("orbit_angle"))
        return send_command("execute_python", {"code": code})
    if key == "product.render_setup":
        code = _gen_render_code(str(args.get("quality") or "balanced"), str(args.get("resolution") or "1080p"), bool(args.get("transparent_bg", True)), args.get("output_path"), str(args.get("output_format") or "PNG"))
        render_result = send_command("execute_python", {"code": code})
        if _has_error(render_result):
            return render_result
        comp_code = _gen_compositor_code(bool(args.get("bloom", True)), bool(args.get("vignette", True)))
        compositor_result = send_command("execute_python", {"code": comp_code})
        return {"render_setup": render_result, "compositor": compositor_result}
    if key == "product.animation":
        object_name = _require_safe_name(args.get("object_name"), "object_name")
        frames = int(args.get("frames", 120))
        fps = int(args.get("fps", 24))
        output_path = args.get("output_path") or "/tmp/product_render/frame_####"
        results = {}
        material = args.get("material")
        if material:
            results["material"] = send_command("execute_python", {"code": _gen_material_code(str(material), object_name)})
        results["lighting"] = send_command("execute_python", {"code": _gen_lighting_code(str(args.get("lighting") or "product_studio"), bool(args.get("shadow_catcher", True)), bool(args.get("gradient_bg", False)), hdri_path=None, hdri_strength=1.5)})
        results["camera"] = send_command("execute_python", {"code": _gen_camera_code(str(args.get("camera_style") or "turntable"), object_name, frames, float(args.get("camera_distance", 4.0)), float(args.get("camera_height", 1.2)), float(args.get("focal_length", 50.0)), float(args.get("f_stop", 2.8)), bool(args.get("use_dof", True)), fps)})
        results["render"] = send_command("execute_python", {"code": _gen_render_code(str(args.get("quality") or "balanced"), str(args.get("resolution") or "1080p"), bool(args.get("transparent_bg", True)), output_path, "PNG")})
        results["compositor"] = send_command("execute_python", {"code": _gen_compositor_code(bool(args.get("bloom", True)), bool(args.get("vignette", True)))})
        if bool(args.get("auto_render", False)):
            results["render_start"] = send_command("render", {"type": "animation", "output_path": output_path})
        errors = [name for name, value in results.items() if _has_error(value)]
        return {"status": "ok" if not errors else "partial_failure", "object": object_name, "frames": frames, "fps": fps, "duration_sec": round(frames / max(fps, 1), 1), "results": results, "errors": errors}
    return registry.execute(key, args, send_command)


def _execute_spatial_adapter(key: str, args: dict, send_command) -> dict:
    if key == "scene.spatial_query":
        action = str(args.get("action") or "scene_bounds")
        commands = {
            "raycast": "spatial_raycast",
            "bounding_box_world": "spatial_bbox_world",
            "check_collision": "spatial_check_collision",
            "find_placement_position": "spatial_find_placement",
            "get_safe_movement_range": "spatial_movement_range",
            "scene_bounds": "spatial_scene_bounds",
        }
        command = commands.get(action)
        if not command:
            return {"error": f"unknown spatial action: {action}"}
        return send_command(command, args)

    if key == "scene.dimensions":
        action = str(args.get("action") or "")
        db = _load_dimensions_db()
        if action == "list":
            items = db.get("objects", {})
            category = args.get("category")
            if category:
                items = {k: v for k, v in items.items() if v.get("category") == category}
            return {"count": len(items), "objects": items}
        if action == "get":
            object_type = args.get("object_type")
            if not object_type:
                return {"error": "object_type required"}
            resolved = _resolve_alias(str(object_type), db)
            entry = db.get("objects", {}).get(resolved)
            return ({"object_type": resolved, "requested": object_type, **entry} if entry else {"error": f"'{object_type}' not in dimensions DB"})
        if action == "estimate_from_mesh":
            name = args.get("object_name")
            return send_command("dimensions_estimate", {"name": name}) if name else {"error": "object_name required"}
        if action == "scale_to_realistic":
            name, object_type = args.get("object_name"), args.get("object_type")
            if not (name and object_type):
                return {"error": "object_name and object_type required"}
            resolved = _resolve_alias(str(object_type), db)
            target = db.get("objects", {}).get(resolved)
            return send_command("dimensions_scale", {"name": name, "target_dimensions": target}) if target else {"error": f"'{object_type}' not in dimensions DB"}
        return {"error": f"unknown dimensions action: {action}"}

    if key == "scene.floor_plan":
        axis = str(args.get("axis") or "z")
        data = send_command("floor_plan_data", {"axis": axis})
        if _has_error(data):
            return data
        objects = data.get("objects", []) if isinstance(data, dict) else []
        return {"floor_plan": _format_ascii_floor_plan(objects, int(args.get("width", 80)), int(args.get("height", 30)), axis), "object_count": len(objects), "axis": axis}

    return registry.execute(key, args, send_command)


def execute_canonical(key: str, arguments: dict, send_command, *, observe_visual: bool = True) -> dict:
    cap = registry.resolve_tool(key)
    args = arguments or {}
    before = _scene_summary(send_command) if cap.mutates_scene else None
    if key.startswith("product."):
        result = _execute_product(cap, args, send_command)
    elif key in {"scene.spatial_query", "scene.dimensions", "scene.floor_plan"}:
        result = _execute_spatial_adapter(key, args, send_command)
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
            response["error"] = "appearance-affecting step returned no pixel evidence"
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
        if not run("product.camera", {"style": "turntable", "target_object": object_name, "frames": int(args.get("frames", 120))}):
            return fail()
        if bool(args.get("auto_render", False)) and not run("scene.render", {"type": "image"}, observe_visual=True):
            return fail()
        return {"workflow": key, "status": "ok", "object_name": object_name, "steps": steps, "postcondition": "Turntable camera orbit was created with pixel observation."}
    if key == "workflow.amazon_packshot":
        args = {**args, "lighting": "product_studio", "camera_style": "hero_reveal", "quality": "premium", "resolution": "square_1080", "transparent_bg": bool(args.get("transparent_bg", True)), "auto_render": True}
    material = args.get("material")
    if material and not run("product.material", {"object_name": object_name, "preset": material}):
        return fail()
    if not run("product.lighting", {"preset": args.get("lighting", "product_studio"), "shadow_catcher": True}):
        return fail()
    if not run("product.camera", {"style": args.get("camera_style", "hero_reveal"), "target_object": object_name, "frames": 120}):
        return fail()
    if not run("product.render_setup", {"quality": args.get("quality", "premium"), "resolution": args.get("resolution", "square_1080"), "transparent_bg": bool(args.get("transparent_bg", False)), "bloom": True, "vignette": True}):
        return fail()
    if bool(args.get("auto_render", True)) and not run("scene.render", {"type": "image"}, observe_visual=True):
        return fail()
    return {"workflow": key, "status": "ok", "object_name": object_name, "steps": steps, "postcondition": "Every appearance-affecting step produced pixel evidence."}
