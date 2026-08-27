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
        _gen_libmv_solve_code,
        _gen_auto_weights_code,
    )
    from server.spatial_tools import _format_ascii_floor_plan, _load_dimensions_db, _resolve_alias
    from server.visual_quality import critique_visual_evidence
    from server.quality_loop import run_quality_loop
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
    from spatial_tools import _format_ascii_floor_plan, _load_dimensions_db, _resolve_alias
    from visual_quality import critique_visual_evidence
    from quality_loop import run_quality_loop

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_. -]{1,128}$")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_./ -]{1,512}$")
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mpg", ".mpeg"}
_VISUAL_FAMILIES = {"lighting", "material", "camera", "render"}
_CREATE_KEYS = {"scene.create_object"}
_DELETE_KEYS = {"scene.delete_object"}

WORKFLOW_SCHEMAS: Dict[str, dict] = {
    "workflow.product_hero": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "material": {"type": ["string", "null"], "default": None}, "lighting": {"type": "string", "default": "product_studio"}, "camera_style": {"type": "string", "default": "hero_reveal"}, "quality": {"type": "string", "default": "premium"}, "resolution": {"type": "string", "default": "square_1080"}, "transparent_bg": {"type": "boolean", "default": False}, "auto_render": {"type": "boolean", "default": True}}, "additionalProperties": False},
    "workflow.turntable": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "lighting": {"type": "string", "default": "product_studio"}, "frames": {"type": "integer", "default": 120}, "quality": {"type": "string", "default": "balanced"}, "auto_render": {"type": "boolean", "default": False}}, "additionalProperties": False},
    "workflow.forensic_recon": {"type": "object", "required": ["action"], "properties": {"action": {"type": "string"}}, "additionalProperties": True},
    "workflow.amazon_packshot": {"type": "object", "required": ["object_name"], "properties": {"object_name": {"type": "string"}, "material": {"type": ["string", "null"], "default": None}, "transparent_bg": {"type": "boolean", "default": True}}, "additionalProperties": False},
    "workflow.reference_attach": {"type": "object", "properties": {"path": {"type": "string"}, "role": {"type": "string"}, "tier": {"type": "string"}}, "additionalProperties": False},
    "workflow.reference_score": {"type": "object", "properties": {"output_path": {"type": "string"}, "render_path": {"type": "string"}, "allow_unsolved": {"type": "boolean", "default": False}}, "additionalProperties": False},
    "workflow.reference_score_sequence": {"type": "object", "properties": {"frames": {"type": "array", "items": {"type": "string"}}, "allow_unsolved": {"type": "boolean", "default": False}}, "additionalProperties": False},
    "workflow.reference_correct": {"type": "object", "properties": {"metrics": {"type": "object"}}, "additionalProperties": False},
    "workflow.reference_camera_solve": {"type": "object", "properties": {"path": {"type": "string"}}, "additionalProperties": False},
    "workflow.image_to_asset": {"type": "object", "properties": {"image_url": {"type": "string"}, "filepath": {"type": "string"}, "keyword": {"type": "string"}, "prompt": {"type": "string"}, "format": {"type": "string"}}, "additionalProperties": False},
    "workflow.character_from_image": {"type": "object", "properties": {"image_url": {"type": "string"}, "filepath": {"type": "string"}, "keyword": {"type": "string"}, "mixamo_fbx": {"type": "string"}}, "additionalProperties": False},
    "workflow.match_reference_lighting": {"type": "object", "properties": {"hdri_path": {"type": ["string", "null"]}, "hdri_strength": {"type": "number"}, "preset": {"type": "string"}, "keyword": {"type": "string"}, "asset_id": {"type": "string"}, "prompt": {"type": "string"}}, "additionalProperties": False},
    "workflow.motion_from_video": {"type": "object", "properties": {"path": {"type": "string"}, "object_name": {"type": "string"}, "motion_spec": {"type": "object"}}, "additionalProperties": False},
    "workflow.motion_qa": {"type": "object", "properties": {"samples": {"type": "array"}}, "additionalProperties": False},
    "workflow.image_to_scene": {"type": "object", "properties": {"image_url": {"type": "string"}, "filepath": {"type": "string"}, "object_name": {"type": "string"}, "prompt": {"type": "string"}, "keyword": {"type": "string"}, "path": {"type": "string"}}, "additionalProperties": False},
    "workflow.viewport_multiview": {"type": "object", "properties": {"views": {"type": "array", "items": {"type": "string"}}}, "additionalProperties": False},
}

WORKFLOW_DESCRIPTIONS = {
    "workflow.product_hero": "Create a polished product hero shot as one deterministic workflow: inspect, optional product material, studio lighting, hero camera, premium render setup, visual observations, and optional final render.",
    "workflow.turntable": "Build a 360 product turntable: inspect, product lighting, turntable camera orbit, optional still render.",
    "workflow.forensic_recon": "Run the forensic/accident reconstruction handler as one workflow after a scene inspect.",
    "workflow.amazon_packshot": "Amazon main-image packshot: square 1080, premium samples, product studio lighting, hero camera, transparent background by default.",
    "workflow.reference_attach": "Attach a still or video plate with a role and score tier for the numeric reference loop.",
    "workflow.reference_score": "Render a still and score it against the attached reference with PSNR/SSIM/LPIPS. VLM is not the pass bit.",
    "workflow.reference_score_sequence": "Score up to N sampled frames against the still/plate. Worst window is the verdict.",
    "workflow.reference_correct": "Map failing score metrics to the next typed capability key. Does not auto-execute repair.",
    "workflow.reference_camera_solve": "Solve camera from a video plate with allowlisted Blender libmv. Stills stay unsupported.",
    "workflow.image_to_asset": "Free mesh: local file, self-hosted TRELLIS.2/TripoSR worker, mapped Poly Haven CC0 models, optional Sketchfab downloadable. No paid generation APIs.",
    "workflow.character_from_image": "Free character: CC0/local mesh, Blender automatic weights, MIXAMO_FBX_PATH or mixamo_fbx. No Tripo.",
    "workflow.match_reference_lighting": "Apply a mapped Poly Haven HDRI then product lighting. CC0, no paid APIs.",
    "workflow.motion_from_video": "Compile a motion_spec to keyframes, or run allowlisted libmv detect/track/solve on a video plate.",
    "workflow.motion_qa": "Numeric foot-skate and pop checks from evaluated bone samples. No VLM.",
    "workflow.image_to_scene": "Free hero import, HDRI lighting match, shadow catcher, camera. Not photogrammetry.",
    "workflow.viewport_multiview": "Capture front, right, top, and iso viewport stills in one workflow.",
}


def _require_safe_name(value: str, field: str) -> str:
    value = str(value or "")
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _has_error(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    return bool(result.get("error")) or str(result.get("status") or "").lower() in {
        "failed", "partial_failure", "postcondition_failed"
    }


def _has_visual_evidence(obs: Any) -> bool:
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
        return send_command("product_material", args)
    if key == "product.lighting":
        return send_command("product_lighting", args)
    if key == "product.camera":
        args["target_object"] = _require_safe_name(args.get("target_object"), "target_object")
        return send_command("product_camera", args)
    if key == "product.render_setup":
        return send_command("product_render_setup", args)
    if key == "product.animation":
        object_name = _require_safe_name(args.get("object_name"), "object_name")
        frames = int(args.get("frames", 120))
        fps = int(args.get("fps", 24))
        output_path = args.get("output_path") or "/tmp/product_render/frame_####"
        results = {}
        material = args.get("material")
        if material:
            results["material"] = send_command("product_material", {"preset": str(material), "object_name": object_name})
        results["lighting"] = send_command("product_lighting", {"preset": str(args.get("lighting") or "product_studio"), "shadow_catcher": bool(args.get("shadow_catcher", True)), "gradient_bg": bool(args.get("gradient_bg", False))})
        results["camera"] = send_command("product_camera", {"style": str(args.get("camera_style") or "turntable"), "target_object": object_name, "frames": frames, "camera_distance": float(args.get("camera_distance", 4.0)), "camera_height": float(args.get("camera_height", 1.2)), "focal_length": float(args.get("focal_length", 50.0)), "f_stop": float(args.get("f_stop", 2.8)), "use_dof": bool(args.get("use_dof", True)), "fps": fps})
        results["render"] = send_command("product_render_setup", {"quality": str(args.get("quality") or "balanced"), "resolution": str(args.get("resolution") or "1080p"), "transparent_bg": bool(args.get("transparent_bg", True)), "output_path": output_path, "output_format": "PNG", "bloom": bool(args.get("bloom", True)), "vignette": bool(args.get("vignette", True))})
        if bool(args.get("auto_render", False)):
            results["render_start"] = send_command("render", {"type": "animation", "output_path": output_path})
        errors = [name for name, value in results.items() if _has_error(value)]
        payload = {"status": "ok" if not errors else "partial_failure", "object": object_name, "frames": frames, "fps": fps, "duration_sec": round(frames / max(fps, 1), 1), "results": results, "errors": errors}
        if errors:
            payload["error"] = f"product animation setup failed in: {', '.join(errors)}"
        return payload
    return registry.execute(key, args, send_command)


def _execute_spatial_adapter(key: str, args: dict, send_command) -> dict:
    if key == "scene.spatial_query":
        action = str(args.get("action") or "scene_bounds")
        commands = {"raycast": "spatial_raycast", "bounding_box_world": "spatial_bbox_world", "check_collision": "spatial_check_collision", "find_placement_position": "spatial_find_placement", "get_safe_movement_range": "spatial_movement_range", "scene_bounds": "spatial_scene_bounds"}
        command = commands.get(action)
        return send_command(command, args) if command else {"error": f"unknown spatial action: {action}"}
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
        response["error"] = result.get("error", "capability execution failed") if isinstance(result, dict) else "capability execution failed"
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


def _is_unknown_bridge_command(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    err = str(result.get("error") or "")
    return "unknown command" in err.lower()


def _final_quality_review(key: str, object_name: str, send_command) -> dict:
    diagnostics = send_command("scene_diagnostics", {})
    if _has_error(diagnostics) or _is_unknown_bridge_command(diagnostics):
        diagnostics = send_command("get_scene_info", {})
    viewport = _visual_observation(send_command)
    return critique_visual_evidence(
        scene=diagnostics,
        viewport=viewport,
        diagnostics=diagnostics if not _is_unknown_bridge_command(diagnostics) else None,
        workflow=key,
        target_object=object_name,
    )


def _complete_product_quality(key: str, object_name: str, send_command, steps: list) -> dict:
    def review_once() -> dict:
        return _final_quality_review(key, object_name, send_command)

    def exec_cap(cap_key: str, arguments: dict) -> dict:
        return execute_canonical(cap_key, arguments, send_command, observe_visual=False)

    review = run_quality_loop(
        workflow=key,
        target_object=object_name,
        review_once=review_once,
        execute_canonical=exec_cap,
    )
    for attempt in review.get("repair_attempts") or []:
        steps.append({"capability": "quality.repair", "result": attempt})
    return review


def _require_safe_path(value: str, field: str) -> str:
    value = str(value or "")
    if ".." in value or not _SAFE_PATH.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def _is_video_path(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _VIDEO_EXT)


def _tag_free(imported: dict, source: str, **extra) -> dict:
    imported["free_source"] = source
    imported.update(extra)
    return imported


def _maybe_reference_score(send_command, steps: list, *, allow_unsolved: bool = False) -> dict | None:
    try:
        from server import reference_loop
    except ModuleNotFoundError:
        import reference_loop
    state = reference_loop.get_state()
    if not reference_loop.still_path():
        return None
    if state.get("camera") is None and not allow_unsolved:
        return {"status": "blocked", "blocking_reason": "camera_unsolved"}
    output_path = "/tmp/openclaw_ref_score.png"
    rendered = execute_canonical("scene.render", {"type": "image", "output_path": output_path}, send_command, observe_visual=True)
    steps.append(rendered)
    if rendered.get("status") != "ok":
        return {"status": "failed", "error": "render for score failed"}
    metrics = reference_loop.score_render(reference_loop.still_path(), output_path, tier=state.get("tier") or "review")
    return {"status": "ok" if metrics.get("passed") else "failed", "metrics": metrics, "verdict": bool(metrics.get("passed"))}


def _apply_mapped_hdri(args: dict, send_command, steps: list):
    try:
        from server.free_stack import hdri_search_terms
    except ModuleNotFoundError:
        from free_stack import hdri_search_terms
    asset_id = args.get("asset_id")
    keyword = str(args.get("keyword") or args.get("prompt") or "studio")
    if not asset_id:
        for term in hdri_search_terms(keyword):
            search = execute_canonical(
                "assets.polyhaven",
                {"action": "search", "asset_type": "hdris", "keyword": term},
                send_command,
                observe_visual=False,
            )
            steps.append(search)
            rows = ((search.get("result") or {}).get("results") or [])
            if rows:
                asset_id = rows[0].get("id")
                break
    if asset_id:
        applied = execute_canonical(
            "assets.polyhaven",
            {"action": "apply_hdri", "asset_id": asset_id, "resolution": "1k", "strength": float(args.get("hdri_strength", 1.5))},
            send_command,
            observe_visual=False,
        )
        steps.append(applied)
        if applied.get("status") != "ok":
            return None, applied
    return asset_id, None


def _free_import_mesh(args: dict, send_command, steps: list, default_keyword: str) -> dict:
    import json
    import os
    import urllib.request

    try:
        from server.free_stack import fail_hints, polyhaven_search_terms, sketchfab_enabled
    except ModuleNotFoundError:
        from free_stack import fail_hints, polyhaven_search_terms, sketchfab_enabled

    local = args.get("filepath")
    if local:
        imported = execute_canonical("io.import", {"filepath": _require_safe_path(str(local), "filepath")}, send_command, observe_visual=True)
        steps.append(imported)
        return _tag_free(imported, "local_filepath")

    worker = os.getenv("IMAGE_TO_3D_WORKER_URL", "").strip()
    image_url = str(args.get("image_url") or "")
    if worker and image_url:
        req = urllib.request.Request(worker, data=json.dumps({"image_url": image_url}).encode(), headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
        mesh_path = payload.get("filepath")
        if not mesh_path:
            return {"status": "failed", "error": "IMAGE_TO_3D_WORKER_URL returned no filepath", "capability": "image_to_3d_worker", **fail_hints()}
        imported = execute_canonical("io.import", {"filepath": _require_safe_path(str(mesh_path), "filepath")}, send_command, observe_visual=True)
        steps.append(imported)
        return _tag_free(imported, "IMAGE_TO_3D_WORKER_URL")

    prompt = str(args.get("keyword") or args.get("prompt") or default_keyword)
    character = "character" in default_keyword.lower() or "character" in prompt.lower()
    last_search = None
    for term in polyhaven_search_terms(prompt, character=character):
        search = execute_canonical("assets.polyhaven", {"action": "search", "asset_type": "models", "keyword": term}, send_command, observe_visual=False)
        steps.append(search)
        last_search = search
        rows = ((search.get("result") or {}).get("results") or [])
        if not rows:
            continue
        imported = execute_canonical(
            "assets.polyhaven",
            {"action": "import_model", "asset_id": rows[0].get("id"), "format": str(args.get("format") or "gltf")},
            send_command,
            observe_visual=True,
        )
        steps.append(imported)
        return _tag_free(imported, "polyhaven_cc0_models", search_term=term, asset_id=rows[0].get("id"))

    if sketchfab_enabled():
        search = execute_canonical(
            "assets.sketchfab",
            {"action": "search", "query": prompt, "downloadable": "true", "kind": "models", "count": 5},
            send_command,
            observe_visual=False,
        )
        steps.append(search)
        if search.get("status") == "ok":
            rows = ((search.get("result") or {}).get("results") or [])
            uid = rows[0].get("uid") if rows else None
            if uid:
                imported = execute_canonical(
                    "assets.sketchfab",
                    {"action": "download_and_import", "model_uid": uid, "format": "glb"},
                    send_command,
                    observe_visual=True,
                )
                steps.append(imported)
                return _tag_free(imported, "sketchfab_downloadable", model_uid=uid)

    return {
        "status": "failed",
        "error": "no free CC0/downloadable mesh for mapped keywords",
        "capability": "assets.polyhaven",
        "result": (last_search or {}).get("result"),
        **fail_hints(),
    }


def _execute_recreate(key: str, args: dict, send_command, steps: list, run, fail) -> dict:
    try:
        from server import reference_loop
        from server.free_stack import mixamo_fbx_path
        from server.motion_spec import compile_motion_spec
        from server.motion_qa import score_motion_qa
    except ModuleNotFoundError:
        import reference_loop
        from free_stack import mixamo_fbx_path
        from motion_spec import compile_motion_spec
        from motion_qa import score_motion_qa

    if key == "workflow.reference_attach":
        state = reference_loop.attach(args)
        return {"workflow": key, "status": "ok", "steps": steps, "reference": state}

    if key == "workflow.reference_correct":
        mapped = reference_loop.correct(args.get("metrics") or {})
        return {"workflow": key, "status": "ok", "steps": steps, **mapped}

    if key == "workflow.reference_camera_solve":
        plate = str(args.get("path") or reference_loop.get_state()["paths"].get("motion_plate") or "")
        if plate and _is_video_path(plate):
            clip_path = _require_safe_path(plate, "path")
            result = send_command("execute_python", {"code": _gen_libmv_solve_code(clip_path)})
            payload = result.get("data", result) if isinstance(result, dict) else result
            if _has_error(result):
                return {"workflow": key, "status": "failed", "steps": steps, "result": result}
            status = "ok"
            if isinstance(payload, dict) and payload.get("status") == "blocked":
                status = "blocked"
            elif isinstance(payload, dict) and payload.get("is_valid"):
                reference_loop.set_camera("solved")
            return {"workflow": key, "status": status, "steps": steps, "libmv": payload}
        solved = reference_loop.camera_solve(args)
        return {"workflow": key, "steps": steps, **solved}

    if key == "workflow.reference_score":
        state = reference_loop.get_state()
        if state.get("camera") is None and not bool(args.get("allow_unsolved", False)):
            return {"workflow": key, "status": "blocked", "blocking_reason": "camera_unsolved", "steps": steps}
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

    if key == "workflow.reference_score_sequence":
        state = reference_loop.get_state()
        if state.get("camera") is None and not bool(args.get("allow_unsolved", False)):
            return {"workflow": key, "status": "blocked", "blocking_reason": "camera_unsolved", "steps": steps}
        ref_path = reference_loop.still_path()
        frames = list(args.get("frames") or [])
        if not ref_path:
            return {"workflow": key, "status": "failed", "error": "no still reference attached", "steps": steps}
        seq = reference_loop.score_sequence(ref_path, frames, tier=state.get("tier") or "review")
        return {"workflow": key, "status": "ok" if seq.get("passed") else "failed", "steps": steps, **seq}

    if key == "workflow.match_reference_lighting":
        asset_id, err = _apply_mapped_hdri(args, send_command, steps)
        if err is not None:
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
        scored = _maybe_reference_score(send_command, steps)
        out = {"workflow": key, "status": "ok", "steps": steps, "captures": captures}
        if scored:
            out["reference_score"] = scored
        return out

    if key == "workflow.motion_qa":
        qa = score_motion_qa(args.get("samples") or [])
        return {"workflow": key, "status": "ok" if qa.get("passed") else "failed", "steps": steps, "motion_qa": qa}

    if key == "workflow.motion_from_video":
        spec = args.get("motion_spec")
        object_name = args.get("object_name")
        if spec and object_name:
            object_name = _require_safe_name(object_name, "object_name")
            ops = compile_motion_spec(spec, object_name)
            for op in ops:
                if not run("animation.keyframe", op, observe_visual=False):
                    return fail()
            return {"workflow": key, "status": "ok", "steps": steps, "keyframes": ops}
        plate = str(args.get("path") or reference_loop.get_state()["paths"].get("motion_plate") or "")
        if not plate:
            return {"workflow": key, "status": "failed", "error": "video path required", "steps": steps}
        clip_path = _require_safe_path(plate, "path")
        result = send_command("execute_python", {"code": _gen_libmv_solve_code(clip_path)})
        if _has_error(result):
            return {"workflow": key, "status": "failed", "steps": steps, "result": result}
        payload = result.get("data", result) if isinstance(result, dict) else result
        status = "ok"
        if isinstance(payload, dict) and payload.get("status") == "blocked":
            status = "blocked"
        elif isinstance(payload, dict) and payload.get("is_valid"):
            reference_loop.set_camera("solved")
        return {"workflow": key, "status": status, "steps": steps, "libmv": payload}

    if key == "workflow.character_from_image":
        imported = _free_import_mesh(args, send_command, steps, str(args.get("keyword") or "character"))
        if imported.get("status") != "ok":
            return {"workflow": key, "status": imported.get("status") or "failed", "error": imported.get("error"), "steps": steps, "next": imported.get("next"), "order": imported.get("order")}
        added = (imported.get("scene_delta") or {}).get("added") or []
        if not added:
            return {"workflow": key, "status": "postcondition_failed", "error": "import reported success but no new object appeared", "steps": steps}
        mesh_name = added[0]
        weights = send_command("execute_python", {"code": _gen_auto_weights_code(mesh_name)})
        steps.append({"capability": "rig.auto_weights", "result": weights})
        mixamo = mixamo_fbx_path(args)
        if mixamo:
            fbx = execute_canonical("io.import", {"filepath": _require_safe_path(str(mixamo), "mixamo_fbx")}, send_command, observe_visual=False)
            steps.append(fbx)
            if fbx.get("status") != "ok":
                return fail()
        return {
            "workflow": key,
            "status": "ok",
            "steps": steps,
            "object_name": mesh_name,
            "source": imported.get("free_source"),
            "search_term": imported.get("search_term"),
            "scene_delta": imported.get("scene_delta"),
        }

    if key in {"workflow.image_to_asset", "workflow.image_to_scene"}:
        imported = None
        object_name = args.get("object_name")
        if object_name and not args.get("filepath") and not args.get("image_url") and not args.get("keyword"):
            object_name = _require_safe_name(object_name, "object_name")
        else:
            imported = _free_import_mesh(args, send_command, steps, str(args.get("prompt") or args.get("keyword") or "product"))
            if imported.get("status") != "ok":
                return {
                    "workflow": key,
                    "status": imported.get("status") or "failed",
                    "error": imported.get("error"),
                    "steps": steps,
                    "next": imported.get("next"),
                    "order": imported.get("order"),
                }
            added = (imported.get("scene_delta") or {}).get("added") or []
            if not added:
                return {"workflow": key, "status": "postcondition_failed", "error": "import reported success but no new object appeared", "steps": steps}
            object_name = added[0]
        observation = _visual_observation(send_command)
        if not _has_visual_evidence(observation):
            return {"workflow": key, "status": "postcondition_failed", "error": "appearance-affecting step returned no pixel evidence", "steps": steps}
        if key == "workflow.image_to_scene":
            asset_id, err = _apply_mapped_hdri(args, send_command, steps)
            if err is not None:
                return fail()
            if not run("product.lighting", {"preset": "product_studio", "shadow_catcher": True}):
                return fail()
            plate = str(args.get("path") or reference_loop.get_state()["paths"].get("motion_plate") or "")
            if plate and _is_video_path(plate):
                solve = _execute_recreate("workflow.reference_camera_solve", {"path": plate}, send_command, steps, run, fail)
                steps.append({"capability": "workflow.reference_camera_solve", "result": solve})
            if not run("product.camera", {"style": "hero_reveal", "target_object": object_name, "frames": 120}):
                return fail()
        scored = _maybe_reference_score(send_command, steps)
        out = {
            "workflow": key,
            "status": "ok",
            "object_name": object_name,
            "steps": steps,
            "visual_observation": observation,
            "free_source": (imported or {}).get("free_source"),
            "search_term": (imported or {}).get("search_term"),
        }
        if key == "workflow.image_to_scene":
            out["asset_id"] = locals().get("asset_id")
        if scored:
            out["reference_score"] = scored
        return out

    return fail()


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

    recreate = {
        "workflow.reference_attach",
        "workflow.reference_score",
        "workflow.reference_score_sequence",
        "workflow.reference_correct",
        "workflow.reference_camera_solve",
        "workflow.image_to_asset",
        "workflow.character_from_image",
        "workflow.match_reference_lighting",
        "workflow.motion_from_video",
        "workflow.motion_qa",
        "workflow.image_to_scene",
        "workflow.viewport_multiview",
    }
    if key in recreate:
        return _execute_recreate(key, args, send_command, steps, run, fail)

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
        review = _complete_product_quality(key, object_name, send_command, steps)
        return {"workflow": key, "status": review["status"], "object_name": object_name, "steps": steps, "quality_review": review, "postcondition": "Turntable stage produced pixels and completed objective quality review."}
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
    review = _complete_product_quality(key, object_name, send_command, steps)
    return {"workflow": key, "status": review["status"], "object_name": object_name, "steps": steps, "quality_review": review, "postcondition": "Appearance steps produced pixels and workflow completed objective quality review."}
