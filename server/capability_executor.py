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
        _gen_libmv_solve_code,
        _gen_auto_weights_code,
    )
except ModuleNotFoundError:
    from capability_registry import registry, Capability
    from product_animation_tools import (
        _gen_material_code,
        _gen_lighting_code,
        _gen_camera_code,
        _gen_render_code,
        _gen_compositor_code,
        _gen_libmv_solve_code,
        _gen_auto_weights_code,
    )

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_. -]{1,128}$")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_./ -]{1,512}$")
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mpg", ".mpeg"}
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
    "workflow.reference_attach": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "image_url": {"type": "string"},
            "role": {"type": "string", "default": "front"},
            "tier": {"type": "string", "default": "review"},
        },
        "additionalProperties": False,
    },
    "workflow.reference_score": {
        "type": "object",
        "properties": {
            "output_path": {"type": "string", "default": "/tmp/openclaw_ref_score.png"},
            "render_path": {"type": "string"},
            "allow_unsolved": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    },
    "workflow.reference_correct": {
        "type": "object",
        "properties": {
            "metrics": {"type": "object"},
        },
        "additionalProperties": False,
    },
    "workflow.reference_camera_solve": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "workflow.image_to_asset": {
        "type": "object",
        "properties": {
            "image_url": {"type": "string"},
            "filepath": {"type": "string"},
            "keyword": {"type": "string"},
            "prompt": {"type": "string", "default": "product"},
            "format": {"type": "string", "default": "gltf"},
        },
        "additionalProperties": False,
    },
    "workflow.character_from_image": {
        "type": "object",
        "properties": {
            "image_url": {"type": "string"},
            "filepath": {"type": "string"},
            "keyword": {"type": "string"},
            "mixamo_fbx": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "workflow.match_reference_lighting": {
        "type": "object",
        "properties": {
            "hdri_path": {"type": ["string", "null"]},
            "hdri_strength": {"type": "number", "default": 1.5},
            "preset": {"type": "string", "default": "product_studio"},
            "keyword": {"type": "string"},
            "asset_id": {"type": "string"},
        },
        "additionalProperties": False,
    },
    "workflow.motion_from_video": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "object_name": {"type": "string"},
            "motion_spec": {"type": "object"},
        },
        "additionalProperties": False,
    },
    "workflow.image_to_scene": {
        "type": "object",
        "properties": {
            "image_url": {"type": "string"},
            "object_name": {"type": "string"},
            "prompt": {"type": "string", "default": "reconstruct subject"},
        },
        "additionalProperties": False,
    },
    "workflow.viewport_multiview": {
        "type": "object",
        "properties": {
            "views": {"type": "array", "items": {"type": "string"}, "default": ["front", "right", "top", "iso"]},
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
    "workflow.reference_attach": (
        "Attach a still or video plate with a role and score tier for the numeric reference loop."
    ),
    "workflow.reference_score": (
        "Render a still and score it against the attached reference with PSNR/SSIM/LPIPS. VLM is not the pass bit."
    ),
    "workflow.reference_correct": (
        "Map failing score metrics to the next typed capability key. Does not auto-execute repair."
    ),
    "workflow.reference_camera_solve": (
        "Attempt camera solve. Stills are unsupported; video libmv is blocked until verified on the target Blender."
    ),
    "workflow.image_to_asset": (
        "Import a mesh from a local file, a self-hosted IMAGE_TO_3D_WORKER_URL (TRELLIS.2/TripoSR MIT), "
        "or a CC0 PolyHaven model search. No paid APIs."
    ),
    "workflow.character_from_image": (
        "Free character path: CC0/local mesh, Blender armature automatic weights, optional local Mixamo FBX. No Tripo."
    ),
    "workflow.match_reference_lighting": (
        "Match product studio / HDRI world lighting to the attached reference, with visual observation."
    ),
    "workflow.motion_from_video": (
        "Compile a motion_spec to keyframes, or run allowlisted libmv detect/track/solve on a video plate."
    ),
    "workflow.image_to_scene": (
        "Compose hero asset from image plus lighting and camera. Not photogrammetry."
    ),
    "workflow.viewport_multiview": (
        "Capture front, right, top, and iso viewport stills in one workflow."
    ),
}


def _require_safe_name(value: str, field: str) -> str:
    value = str(value or "")
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _require_safe_path(value: str, field: str) -> str:
    value = str(value or "")
    if ".." in value or not _SAFE_PATH.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _is_video_path(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _VIDEO_EXT)


def _has_error(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


def _has_visual_evidence(obs: Any) -> bool:
    """Return True only when the bridge returned actual image pixels.

    A filesystem path is not visual evidence: the model/client cannot inspect it
    unless bytes are separately loaded and surfaced. viewport_capture is requested
    with base64=True, so fail closed unless an image payload is present.
    """
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

    if key == "product.animation":
        target = _require_safe_name(args.get("object_name") or args.get("target_object"), "object_name")
        code = _gen_camera_code(
            str(args.get("style") or "turntable"),
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

    if key == "workflow.reference_attach":
        try:
            from server.reference_loop import attach as ref_attach
        except ModuleNotFoundError:
            from reference_loop import attach as ref_attach
        state = ref_attach(args)
        return {"workflow": key, "status": "ok", "steps": steps, "reference": state}

    if key == "workflow.reference_correct":
        try:
            from server.reference_loop import correct as ref_correct
        except ModuleNotFoundError:
            from reference_loop import correct as ref_correct
        mapped = ref_correct(args.get("metrics") or {})
        return {"workflow": key, "status": "ok", "steps": steps, **mapped}

    if key == "workflow.reference_camera_solve":
        try:
            from server.reference_loop import camera_solve, get_state
        except ModuleNotFoundError:
            from reference_loop import camera_solve, get_state
        plate = str(args.get("path") or get_state()["paths"].get("motion_plate") or "")
        if plate and _is_video_path(plate):
            clip_path = _require_safe_path(plate, "path")
            code = _gen_libmv_solve_code(clip_path)
            result = send_command("execute_python", {"code": code})
            payload = result.get("data", result) if isinstance(result, dict) else result
            if _has_error(result):
                return {"workflow": key, "status": "failed", "steps": steps, "result": result}
            status = "ok"
            if isinstance(payload, dict) and payload.get("status") == "blocked":
                status = "blocked"
            return {"workflow": key, "status": status, "steps": steps, "libmv": payload}
        solved = camera_solve(args)
        return {"workflow": key, "steps": steps, **solved}

    if key == "workflow.character_from_image":
        try:
            from server.tripo_client import TripoError, run_character_pipeline
        except ModuleNotFoundError:
            from tripo_client import TripoError, run_character_pipeline
        try:
            pipeline = run_character_pipeline(str(args.get("image_url") or ""))
        except TripoError as exc:
            reason = str(exc)
            code = "tripo_api_key_missing" if "TRIPO_API_KEY" in reason else "tripo_failed"
            return {"workflow": key, "status": "blocked", "blocking_reason": code, "error": reason, "steps": steps}
        before = _scene_summary(send_command)
        imported = execute_canonical(
            "io.import",
            {"filepath": pipeline["filepath"]},
            send_command,
            observe_visual=True,
        )
        steps.append(imported)
        if imported.get("status") != "ok":
            return fail()
        after = _scene_summary(send_command)
        delta = _scene_delta(before, after)
        if not delta["added"]:
            return {
                "workflow": key,
                "status": "postcondition_failed",
                "error": "import reported success but no new object appeared",
                "steps": steps,
                "tripo": pipeline,
            }
        return {
            "workflow": key,
            "status": "ok",
            "steps": steps,
            "tripo": pipeline,
            "object_name": delta["added"][0],
            "scene_delta": delta,
        }

    if key == "workflow.motion_from_video":
        spec = args.get("motion_spec")
        object_name = args.get("object_name")
        if spec and object_name:
            object_name = _require_safe_name(object_name, "object_name")
            try:
                from server.motion_spec import compile_motion_spec
            except ModuleNotFoundError:
                from motion_spec import compile_motion_spec
            ops = compile_motion_spec(spec, object_name)
            for op in ops:
                if not run("animation.keyframe", op, observe_visual=False):
                    return fail()
            return {"workflow": key, "status": "ok", "steps": steps, "keyframes": ops}
        try:
            from server.reference_loop import get_state
        except ModuleNotFoundError:
            from reference_loop import get_state
        plate = str(args.get("path") or get_state()["paths"].get("motion_plate") or "")
        if not plate:
            return {"workflow": key, "status": "failed", "error": "video path required", "steps": steps}
        clip_path = _require_safe_path(plate, "path")
        code = _gen_libmv_solve_code(clip_path)
        result = send_command("execute_python", {"code": code})
        if _has_error(result):
            return {"workflow": key, "status": "failed", "steps": steps, "result": result}
        payload = result.get("data", result) if isinstance(result, dict) else result
        status = "ok"
        if isinstance(payload, dict) and payload.get("status") == "blocked":
            status = "blocked"
        return {"workflow": key, "status": status, "steps": steps, "libmv": payload}

    if key == "workflow.match_reference_lighting":
        asset_id = args.get("asset_id")
        keyword = args.get("keyword")
        if not asset_id and keyword:
            search = execute_canonical(
                "assets.polyhaven",
                {"action": "search", "asset_type": "hdris", "keyword": keyword},
                send_command,
                observe_visual=False,
            )
            steps.append(search)
            rows = ((search.get("result") or {}).get("results") or [])
            if rows:
                asset_id = rows[0].get("id")
        if asset_id:
            applied = execute_canonical(
                "assets.polyhaven",
                {
                    "action": "apply_hdri",
                    "asset_id": asset_id,
                    "resolution": "1k",
                    "strength": float(args.get("hdri_strength", 1.5)),
                },
                send_command,
                observe_visual=False,
            )
            steps.append(applied)
            if applied.get("status") != "ok":
                return fail()
        lighting_args = {
            "preset": args.get("preset") or "product_studio",
            "shadow_catcher": True,
            "hdri_path": args.get("hdri_path"),
            "hdri_strength": float(args.get("hdri_strength", 1.5)),
        }
        if not run("product.lighting", lighting_args):
            return fail()
        return {"workflow": key, "status": "ok", "steps": steps, "asset_id": asset_id}

    if key == "workflow.reference_score":
        try:
            from server import reference_loop
        except ModuleNotFoundError:
            import reference_loop
        state = reference_loop.get_state()
        if state.get("camera") is None and not bool(args.get("allow_unsolved", False)):
            return {
                "workflow": key,
                "status": "blocked",
                "blocking_reason": "camera_unsolved",
                "steps": steps,
            }
        ref_path = reference_loop.still_path()
        if not ref_path:
            return {"workflow": key, "status": "failed", "error": "no still reference attached", "steps": steps}
        output_path = str(args.get("render_path") or args.get("output_path") or "/tmp/openclaw_ref_score.png")
        if not run("scene.render", {"type": "image", "output_path": output_path}, observe_visual=True):
            return fail()
        metrics = reference_loop.score_render(ref_path, output_path, tier=state.get("tier") or "review")
        return {
            "workflow": key,
            "status": "ok" if metrics.get("passed") else "failed",
            "steps": steps,
            "metrics": metrics,
            "verdict": bool(metrics.get("passed")),
        }

    if key == "workflow.viewport_multiview":
        views = args.get("views") or ["front", "right", "top", "iso"]
        captures = []
        for view in views:
            obs = send_command("viewport_capture", {"base64": True, "filepath": f"/tmp/openclaw_view_{view}.png"})
            captures.append({"view": view, "observation": obs})
            if not _has_visual_evidence(obs):
                return {
                    "workflow": key,
                    "status": "postcondition_failed",
                    "error": f"no pixel evidence for view {view}",
                    "steps": steps,
                    "captures": captures,
                }
        return {"workflow": key, "status": "ok", "steps": steps, "captures": captures}

    if key in {"workflow.image_to_asset", "workflow.image_to_scene"}:
        image_url = str(args.get("image_url") or "")
        object_name = args.get("object_name")
        if image_url:
            hunyuan = execute_canonical(
                "generation.hunyuan3d",
                {
                    "action": "generate_and_import",
                    "prompt": str(args.get("prompt") or "reconstruct subject"),
                    "image_url": image_url,
                    "mode": "image_to_3d",
                    "format": str(args.get("format") or "glb"),
                },
                send_command,
                observe_visual=False,
            )
            steps.append(hunyuan)
            if hunyuan.get("status") != "ok":
                return fail()
            added = (hunyuan.get("scene_delta") or {}).get("added") or []
            if not added:
                return {
                    "workflow": key,
                    "status": "postcondition_failed",
                    "error": "import reported success but no new object appeared",
                    "steps": steps,
                }
            object_name = added[0]
        elif object_name:
            object_name = _require_safe_name(object_name, "object_name")
        else:
            return {"workflow": key, "status": "failed", "error": "image_url or object_name required", "steps": steps}

        observation = _visual_observation(send_command)
        if not _has_visual_evidence(observation):
            return {
                "workflow": key,
                "status": "postcondition_failed",
                "error": "appearance-affecting step returned no pixel evidence",
                "steps": steps,
            }
        if key == "workflow.image_to_scene":
            if not run("product.lighting", {"preset": "product_studio", "shadow_catcher": True}):
                return fail()
            if not run("product.camera", {"style": "hero_reveal", "target_object": object_name, "frames": 120}):
                return fail()
        return {
            "workflow": key,
            "status": "ok",
            "object_name": object_name,
            "steps": steps,
            "visual_observation": observation,
        }

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
            if not run("scene.render", {"type": "image"}, observe_visual=True):
                return fail()
        return {
            "workflow": key,
            "status": "ok",
            "object_name": object_name,
            "steps": steps,
            "postcondition": "Turntable camera orbit was created with pixel observation.",
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
        if not run("scene.render", {"type": "image"}, observe_visual=True):
            return fail()

    return {
        "workflow": key,
        "status": "ok",
        "object_name": object_name,
        "steps": steps,
        "postcondition": "Every appearance-affecting step produced pixel evidence.",
    }
