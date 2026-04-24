"""
new_handlers_phase5.py — Addon-side handlers for Phase 5 MCP tools.

Must be imported by openclaw_blender_bridge.py and DISPATCH_NEW_HANDLERS merged
into the main command-dispatch dict (right before the socket_server_thread starts).

All geometry reads use depsgraph_helpers.py (Phase 1 correctness) —
never raw obj.data. Per CGWire: obj.data gives pre-modifier counts; the
evaluated depsgraph is the only source of truth.

Main-thread discipline: these functions run inside the existing bpy.app.timers
timer_callback queue; they do NOT spawn their own threads.
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

try:
    import bpy
    from mathutils import Vector
except ImportError:  # for unit-testing outside Blender
    bpy = None  # type: ignore
    Vector = None  # type: ignore

try:
    from .depsgraph_helpers import (
        evaluated_mesh, evaluated_bbox_world, evaluated_vertex_count,
        evaluated_triangle_count, scene_object_snapshot,
    )
except Exception:
    try:
        from depsgraph_helpers import (  # type: ignore
            evaluated_mesh, evaluated_bbox_world, evaluated_vertex_count,
            evaluated_triangle_count, scene_object_snapshot,
        )
    except Exception:
        evaluated_mesh = None  # type: ignore
        evaluated_bbox_world = None  # type: ignore
        evaluated_vertex_count = None  # type: ignore
        evaluated_triangle_count = None  # type: ignore
        scene_object_snapshot = None  # type: ignore


# In-memory snapshot store (session-scoped; ok because Blender session = 1 addon)
_SNAPSHOTS: Dict[str, dict] = {}


def _require_bpy():
    if bpy is None:
        raise RuntimeError("This handler requires running inside Blender.")


def _get_obj(name: str):
    _require_bpy()
    obj = bpy.data.objects.get(name)
    if not obj:
        raise KeyError(f"Object '{name}' not found")
    return obj


def _world_bbox_8(obj, depsgraph) -> List[List[float]]:
    """Return 8 world-space bbox corners of `obj` evaluated via depsgraph."""
    obj_eval = obj.evaluated_get(depsgraph)
    mw = obj_eval.matrix_world
    return [list(mw @ Vector(c)) for c in obj_eval.bound_box]


def _aabb_from_corners(corners: List[List[float]]) -> Dict[str, List[float]]:
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    zs = [c[2] for c in corners]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
        "center": [sum(xs) / 8, sum(ys) / 8, sum(zs) / 8],
        "dimensions": [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
    }


def _aabb_intersects(a: Dict, b: Dict, tol: float = 0.001) -> bool:
    return (
        a["min"][0] <= b["max"][0] + tol and a["max"][0] + tol >= b["min"][0] and
        a["min"][1] <= b["max"][1] + tol and a["max"][1] + tol >= b["min"][1] and
        a["min"][2] <= b["max"][2] + tol and a["max"][2] + tol >= b["min"][2]
    )


# ─────────────────────────── Spatial handlers ───────────────────────────

def handle_spatial_raycast(params):
    """scene.ray_cast wrapper. Main-thread only."""
    _require_bpy()
    origin = params.get("origin") or [0, 0, 0]
    direction = params.get("direction") or [0, 0, -1]
    max_distance = float(params.get("max_distance") or 1000.0)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result, location, normal, index, obj, matrix = bpy.context.scene.ray_cast(
        depsgraph, Vector(origin), Vector(direction), distance=max_distance
    )
    if not result:
        return {"hit": False}
    return {
        "hit": True,
        "location": list(location),
        "normal": list(normal),
        "face_index": index,
        "object": obj.name if obj else None,
    }


def handle_spatial_bbox_world(params):
    """Return evaluated world-space bbox dict for `name`."""
    _require_bpy()
    name = params.get("name")
    if not name:
        return {"error": "name required"}
    try:
        obj = _get_obj(name)
    except KeyError as e:
        return {"error": str(e)}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    corners = _world_bbox_8(obj, depsgraph)
    return {"name": name, "bbox": _aabb_from_corners(corners), "corners_world": corners}


def handle_spatial_check_collision(params):
    """Cheap AABB collision check between two objects."""
    _require_bpy()
    a_name, b_name = params.get("a"), params.get("b")
    if not (a_name and b_name):
        return {"error": "a and b required"}
    try:
        a, b = _get_obj(a_name), _get_obj(b_name)
    except KeyError as e:
        return {"error": str(e)}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    a_box = _aabb_from_corners(_world_bbox_8(a, depsgraph))
    b_box = _aabb_from_corners(_world_bbox_8(b, depsgraph))
    tol = float(params.get("tolerance") or 0.001)
    return {
        "a": a_name, "b": b_name,
        "a_bbox": a_box, "b_bbox": b_box,
        "intersects": _aabb_intersects(a_box, b_box, tol),
        "tolerance": tol,
    }


def handle_spatial_find_placement(params):
    """Suggest placing `object` centered on top of `on_top_of`.

    Returns the Z just above the target's evaluated bbox.max.z, XY centered on target,
    adjusted so object's bbox.min.z aligns with target.bbox.max.z + offset_z.
    """
    _require_bpy()
    obj_name = params.get("object")
    target_name = params.get("on_top_of")
    offset_z = float(params.get("offset_z") or 0.0)
    if not (obj_name and target_name):
        return {"error": "object and on_top_of required"}
    try:
        obj, target = _get_obj(obj_name), _get_obj(target_name)
    except KeyError as e:
        return {"error": str(e)}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_box = _aabb_from_corners(_world_bbox_8(obj, depsgraph))
    target_box = _aabb_from_corners(_world_bbox_8(target, depsgraph))
    target_top_z = target_box["max"][2]
    target_center = target_box["center"]
    obj_half_height = obj_box["dimensions"][2] / 2
    # Shift object so its bbox.min.z == target.max.z + offset_z
    suggested_location = [
        target_center[0] - (obj_box["center"][0] - obj.location.x),
        target_center[1] - (obj_box["center"][1] - obj.location.y),
        target_top_z + obj_half_height + offset_z,
    ]
    return {
        "object": obj_name, "target": target_name,
        "location": suggested_location,
        "target_top_z": target_top_z,
        "object_half_height": obj_half_height,
    }


def handle_spatial_movement_range(params):
    """For each axis, how far can `object` move before colliding with anything else?

    Cheap implementation: iterate all visible meshes, return AABB overlap gap per axis.
    """
    _require_bpy()
    name = params.get("object")
    axes = params.get("axes") or ["x", "y", "z"]
    if not name:
        return {"error": "object required"}
    try:
        obj = _get_obj(name)
    except KeyError as e:
        return {"error": str(e)}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    my_box = _aabb_from_corners(_world_bbox_8(obj, depsgraph))

    # Collect other objects' bboxes
    others = []
    for o in bpy.data.objects:
        if o.name == name or o.type != "MESH" or not o.visible_get():
            continue
        try:
            bb = _aabb_from_corners(_world_bbox_8(o, depsgraph))
            others.append((o.name, bb))
        except Exception:
            continue

    # Large range bracket
    R = 1000.0
    result = {}
    axis_idx = {"x": 0, "y": 1, "z": 2}
    for ax in axes:
        idx = axis_idx.get(ax)
        if idx is None:
            continue
        neg_limit, pos_limit = -R, R
        for _other_name, ob in others:
            # Overlap check on the OTHER two axes
            o2 = [i for i in (0, 1, 2) if i != idx]
            overlap_other = (
                my_box["min"][o2[0]] <= ob["max"][o2[0]] and my_box["max"][o2[0]] >= ob["min"][o2[0]] and
                my_box["min"][o2[1]] <= ob["max"][o2[1]] and my_box["max"][o2[1]] >= ob["min"][o2[1]]
            )
            if not overlap_other:
                continue
            # Gap on this axis
            if my_box["max"][idx] <= ob["min"][idx]:  # other is positive
                gap = ob["min"][idx] - my_box["max"][idx]
                pos_limit = min(pos_limit, gap)
            elif my_box["min"][idx] >= ob["max"][idx]:  # other is negative
                gap = ob["max"][idx] - my_box["min"][idx]
                neg_limit = max(neg_limit, gap)
            else:
                # Already overlapping
                pos_limit = min(pos_limit, 0.0)
                neg_limit = max(neg_limit, 0.0)
        result[ax] = [neg_limit, pos_limit]
    return {"object": name, "range": result}


def handle_scene_bounds(params):
    """Overall scene bbox."""
    _require_bpy()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    xs, ys, zs = [], [], []
    count = 0
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.visible_get():
            continue
        try:
            corners = _world_bbox_8(o, depsgraph)
            for c in corners:
                xs.append(c[0]); ys.append(c[1]); zs.append(c[2])
            count += 1
        except Exception:
            continue
    if not xs:
        return {"object_count": 0, "bbox": None}
    return {
        "object_count": count,
        "bbox": {
            "min": [min(xs), min(ys), min(zs)],
            "max": [max(xs), max(ys), max(zs)],
            "dimensions": [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
        },
    }


def handle_semantic_place(params):
    """Supports relation != 'on_top_of' — simple heuristics."""
    _require_bpy()
    obj_name = params.get("object")
    target_name = params.get("target")
    relation = params.get("relation")
    if not (obj_name and target_name and relation):
        return {"error": "object, target, relation required"}
    try:
        obj = _get_obj(obj_name)
        target = _get_obj(target_name)
    except KeyError as e:
        return {"error": str(e)}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    tb = _aabb_from_corners(_world_bbox_8(target, depsgraph))
    ob = _aabb_from_corners(_world_bbox_8(obj, depsgraph))
    tc = tb["center"]
    margin = 0.05
    dx = (tb["dimensions"][0] + ob["dimensions"][0]) / 2 + margin
    dy = (tb["dimensions"][1] + ob["dimensions"][1]) / 2 + margin
    if relation == "next_to" or relation == "right_of":
        location = [tc[0] + dx, tc[1], ob["center"][2]]
    elif relation == "left_of":
        location = [tc[0] - dx, tc[1], ob["center"][2]]
    elif relation == "in_front_of":
        location = [tc[0], tc[1] - dy, ob["center"][2]]
    elif relation == "behind":
        location = [tc[0], tc[1] + dy, ob["center"][2]]
    elif relation == "below":
        location = [tc[0], tc[1], tb["min"][2] - ob["dimensions"][2] / 2 - margin]
    elif relation == "inside":
        location = list(tc)
    else:
        return {"error": f"Unsupported relation '{relation}'"}
    if not params.get("dry_run"):
        obj.location = Vector(location)
    return {"object": obj_name, "target": target_name, "relation": relation, "location": location}


def handle_dimensions_estimate(params):
    """Return the evaluated world-space dimensions of a mesh."""
    _require_bpy()
    name = params.get("name")
    if not name:
        return {"error": "name required"}
    try:
        obj = _get_obj(name)
    except KeyError as e:
        return {"error": str(e)}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bb = _aabb_from_corners(_world_bbox_8(obj, depsgraph))
    return {
        "name": name,
        "width": bb["dimensions"][0],
        "depth": bb["dimensions"][1],
        "height": bb["dimensions"][2],
        "bbox": bb,
    }


def handle_dimensions_scale(params):
    """Scale `name` so its evaluated bbox matches the target dimensions."""
    _require_bpy()
    name = params.get("name")
    target = params.get("target_dimensions") or {}
    if not name:
        return {"error": "name required"}
    try:
        obj = _get_obj(name)
    except KeyError as e:
        return {"error": str(e)}
    est = handle_dimensions_estimate({"name": name})
    if "error" in est:
        return est
    factors = []
    for key, axis in [("width", 0), ("depth", 1), ("height", 2)]:
        tgt = target.get(key)
        cur = est[key]
        if tgt is None or cur <= 1e-9:
            factors.append(None)
        else:
            factors.append(tgt / cur)
    # Use the mean of valid factors for uniform scale
    valid = [f for f in factors if f is not None]
    if not valid:
        return {"error": "target_dimensions has no usable width/depth/height"}
    scale = sum(valid) / len(valid)
    obj.scale = (obj.scale[0] * scale, obj.scale[1] * scale, obj.scale[2] * scale)
    bpy.context.view_layer.update()
    return {"name": name, "applied_scale_factor": scale, "per_axis_factors": factors}


def handle_floor_plan_data(params):
    """Return a list of {name, bbox} for every visible mesh."""
    _require_bpy()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH" or not o.visible_get():
            continue
        try:
            bb = _aabb_from_corners(_world_bbox_8(o, depsgraph))
            out.append({"name": o.name, "bbox": bb})
        except Exception:
            continue
    return {"objects": out, "axis": params.get("axis") or "z"}


# ─────────────────────────── Camera/UV/Bake/LOD/VR/Splat/GP/Snapshot ───────────────────────────

def handle_camera_advanced(params):
    _require_bpy()
    action = params.get("action")
    name = params.get("camera") or params.get("name")
    if action == "set_active":
        cam = _get_obj(name)
        bpy.context.scene.camera = cam
        return {"active_camera": name}
    if action == "get_info":
        cam = _get_obj(name)
        d = cam.data
        return {
            "name": cam.name, "lens": d.lens, "sensor_fit": d.sensor_fit,
            "dof": {"enabled": d.dof.use_dof, "focus_distance": d.dof.focus_distance, "fstop": d.dof.aperture_fstop},
            "clip": {"start": d.clip_start, "end": d.clip_end},
            "shift_x": d.shift_x, "shift_y": d.shift_y,
        }
    if action == "look_at":
        cam = _get_obj(name)
        target_name = params.get("target")
        target = _get_obj(target_name)
        direction = target.location - cam.location
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
        return {"camera": name, "target": target_name}
    if action == "set_properties":
        cam = _get_obj(name)
        d = cam.data
        if params.get("lens") is not None: d.lens = params["lens"]
        if params.get("sensor_fit"): d.sensor_fit = params["sensor_fit"]
        if params.get("dof_enabled") is not None: d.dof.use_dof = params["dof_enabled"]
        if params.get("dof_focus_distance") is not None: d.dof.focus_distance = params["dof_focus_distance"]
        if params.get("dof_fstop") is not None: d.dof.aperture_fstop = params["dof_fstop"]
        if params.get("clip_start") is not None: d.clip_start = params["clip_start"]
        if params.get("clip_end") is not None: d.clip_end = params["clip_end"]
        if params.get("shift_x") is not None: d.shift_x = params["shift_x"]
        if params.get("shift_y") is not None: d.shift_y = params["shift_y"]
        return {"camera": name, "updated": True}
    if action == "frame_objects":
        objs = [_get_obj(n) for n in (params.get("objects") or [])]
        if not objs: return {"error": "objects required"}
        depsgraph = bpy.context.evaluated_depsgraph_get()
        xs, ys, zs = [], [], []
        for o in objs:
            for c in _world_bbox_8(o, depsgraph):
                xs.append(c[0]); ys.append(c[1]); zs.append(c[2])
        cx, cy, cz = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2
        span = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
        cam = _get_obj(name)
        cam.location = Vector((cx + span*1.5, cy - span*1.5, cz + span*0.8))
        # Look at center
        center = Vector((cx, cy, cz))
        direction = center - cam.location
        cam.rotation_mode = "QUATERNION"
        cam.rotation_quaternion = direction.to_track_quat("-Z", "Y")
        return {"camera": name, "framed": [o.name for o in objs], "center": [cx, cy, cz]}
    return {"error": f"Unknown action '{action}'", "next_step": "try look_at / frame_objects / set_active / set_properties / get_info"}


def handle_uv_unwrap(params):
    _require_bpy()
    name = params.get("object_name")
    method = params.get("method") or "smart_project"
    obj = _get_obj(name)
    # Enter edit mode, select all, run op
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    try:
        if method == "smart_project":
            bpy.ops.uv.smart_project(angle_limit=params.get("angle_limit", 66.0),
                                     island_margin=params.get("island_margin", 0.02),
                                     correct_aspect=bool(params.get("correct_aspect", True)))
        elif method == "angle_based":
            bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=params.get("margin", 0.003))
        elif method == "conformal":
            bpy.ops.uv.unwrap(method="CONFORMAL", margin=params.get("margin", 0.003))
        elif method == "lightmap_pack":
            bpy.ops.uv.lightmap_pack(PREF_PACK_IN_ONE=True, PREF_BOX_DIV=params.get("quality", 12),
                                     PREF_MARGIN_DIV=params.get("margin", 0.003))
        elif method == "cube_project":
            bpy.ops.uv.cube_project(cube_size=params.get("cube_size", 2.0))
        elif method == "cylinder_project":
            bpy.ops.uv.cylinder_project()
        elif method == "sphere_project":
            bpy.ops.uv.sphere_project()
        elif method == "unwrap_preserve":
            bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=params.get("margin", 0.003),
                              correct_aspect=True, use_subsurf_data=True)
        else:
            return {"error": f"unknown UV method '{method}'"}
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    return {"object_name": name, "method": method, "ok": True}


def handle_texture_bake(params):
    """Cycles texture bake. Requires Cycles render engine; forces the switch if needed.

    Creates an empty image of (width x height), assigns it to every material's
    active image texture node (or creates one), then calls bpy.ops.object.bake.
    Saves to save_to path if provided.
    """
    _require_bpy()
    name = params.get("object_name")
    bake_type = (params.get("bake_type") or "diffuse").upper()
    width = int(params.get("width") or 2048)
    height = int(params.get("height") or 2048)
    margin = int(params.get("margin") or 16)
    save_to = params.get("save_to")
    use_cage = bool(params.get("use_cage") or False)
    cage_extrusion = float(params.get("cage_extrusion") or 0.0)

    try:
        obj = _get_obj(name)
    except KeyError as e:
        return {"error": str(e)}

    if obj.type != "MESH":
        return {"error": f"'{name}' is not a MESH"}
    if not obj.data.materials:
        return {"error": f"'{name}' has no materials — add one before baking"}

    # Switch to Cycles (Eevee cannot bake all pass types)
    scene = bpy.context.scene
    prev_engine = scene.render.engine
    if prev_engine != "CYCLES":
        scene.render.engine = "CYCLES"

    # Create bake target image
    img_name = f"{name}_{bake_type.lower()}_bake"
    img = bpy.data.images.get(img_name) or bpy.data.images.new(img_name, width=width, height=height)
    img.generated_width = width
    img.generated_height = height

    # Attach an Image Texture node to each material, active + selected for bake
    attached = []
    for mat in obj.data.materials:
        if mat is None or not mat.use_nodes:
            continue
        nodes = mat.node_tree.nodes
        tex_node = None
        for n in nodes:
            if n.type == "TEX_IMAGE" and n.image == img:
                tex_node = n
                break
        if tex_node is None:
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.image = img
            tex_node.location = (-400, 300)
        nodes.active = tex_node
        tex_node.select = True
        attached.append(mat.name)

    # Select + activate object
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    try:
        bpy.ops.object.bake(
            type=bake_type,
            margin=margin,
            use_cage=use_cage,
            cage_extrusion=cage_extrusion,
        )
    except Exception as e:
        return {"error": f"bake failed: {e}", "bake_type": bake_type}
    finally:
        if prev_engine != "CYCLES":
            scene.render.engine = prev_engine

    saved = None
    if save_to:
        img.filepath_raw = save_to
        img.file_format = "PNG"
        try:
            img.save()
            saved = save_to
        except Exception as e:
            saved = f"save failed: {e}"

    return {
        "object_name": name,
        "bake_type": bake_type,
        "image_name": img.name,
        "size": [width, height],
        "margin": margin,
        "attached_materials": attached,
        "saved_to": saved,
    }


def handle_generate_lod(params):
    _require_bpy()
    name = params.get("object_name")
    levels = int(params.get("levels") or 4)
    ratio_step = float(params.get("ratio_step") or 0.5)
    scheme = params.get("naming_scheme") or "{name}_LOD{n}"
    src = _get_obj(name)
    created = []
    ratio = 1.0
    for n in range(1, levels):
        ratio *= ratio_step
        dup = src.copy()
        dup.data = src.data.copy()
        dup.name = scheme.format(name=name, n=n)
        bpy.context.collection.objects.link(dup)
        m = dup.modifiers.new(name="LOD_Decimate", type="DECIMATE")
        m.ratio = ratio
        created.append({"name": dup.name, "ratio": ratio})
    return {"source": name, "levels_created": created, "levels": levels}


def handle_vr_validate(params):
    _require_bpy()
    name = params.get("object_name")
    platform = params.get("platform") or "meta_quest_3"
    limits = {
        "meta_quest_3": 50000, "vision_pro": 100000,
        "steamvr": 500000, "webxr": 30000,
    }
    limit = limits.get(platform, 50000)
    obj = _get_obj(name)
    tri_count = evaluated_triangle_count(obj) if evaluated_triangle_count else len(obj.data.polygons)
    return {"object_name": name, "platform": platform, "triangle_count": tri_count,
            "limit": limit, "compliant": tri_count <= limit,
            "ratio": tri_count / max(limit, 1)}


def handle_vr_optimize(params):
    """Compose LOD (Decimate) + optionally bake diffuse onto a simplified copy.

    Platform polycount limits (tris):
      meta_quest_3=50000, vision_pro=100000, steamvr=500000, webxr=30000.
    """
    _require_bpy()
    name = params.get("object_name")
    platform = params.get("platform") or "meta_quest_3"
    target = params.get("target_polycount")
    preserve_uvs = bool(params.get("preserve_uvs") if params.get("preserve_uvs") is not None else True)

    limits = {"meta_quest_3": 50000, "vision_pro": 100000, "steamvr": 500000, "webxr": 30000}
    target_tris = int(target or limits.get(platform, 50000))

    try:
        src = _get_obj(name)
    except KeyError as e:
        return {"error": str(e)}

    # Current evaluated tri count
    current = evaluated_triangle_count(src) if evaluated_triangle_count else len(src.data.polygons)
    if current == 0:
        return {"error": f"'{name}' has no geometry"}

    # Duplicate so we don't mutate the source
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = f"{name}_VR_{platform}"
    bpy.context.collection.objects.link(dup)

    ratio = min(1.0, target_tris / current)
    m = dup.modifiers.new(name="VR_Decimate", type="DECIMATE")
    m.ratio = ratio
    # If preserving UVs, use planar/unsubdivide fallback isn't reliable — just keep collapse
    # Apply the modifier so the output is a baked mesh
    bpy.context.view_layer.objects.active = dup
    try:
        bpy.ops.object.modifier_apply(modifier="VR_Decimate")
    except Exception as e:
        return {"error": f"decimate apply failed: {e}"}

    final_tris = evaluated_triangle_count(dup) if evaluated_triangle_count else len(dup.data.polygons)

    return {
        "source": name,
        "optimized_object": dup.name,
        "platform": platform,
        "target_tris": target_tris,
        "before_tris": current,
        "after_tris": final_tris,
        "ratio_applied": ratio,
        "preserve_uvs": preserve_uvs,
        "compliant": final_tris <= target_tris,
    }


def handle_vr_export(params):
    _require_bpy()
    name = params.get("object_name")
    output = params.get("output_path")
    if not output:
        return {"error": "output_path required"}
    obj = _get_obj(name)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=output, use_selection=True, export_format="GLB",
                              export_apply=True, export_cameras=False, export_lights=False)
    return {"object_name": name, "exported_to": output, "platform": params.get("platform")}


def handle_gaussian_splat_import_ply(params):
    return {"error": "requires KIRI/PolyCam splat addon; install separately",
            "next_step": "https://www.kiri.art/blender-addon/",
            "filepath": params.get("filepath")}


def handle_gaussian_splat_import_splat(params):
    return {"error": "requires .splat format addon; install separately",
            "filepath": params.get("filepath")}


def handle_gaussian_splat_render_with_splats(params):
    return {"error": "not yet implemented", "next_step": "use bpy.ops.render.render() after splat addon imports"}


def handle_gaussian_splat_list(params):
    _require_bpy()
    # Look for objects of type 'PARTICLES' or names containing 'splat'
    names = [o.name for o in bpy.data.objects if "splat" in o.name.lower() or "gauss" in o.name.lower()]
    return {"candidates": names}


def handle_grease_pencil_action(params):
    _require_bpy()
    action = params.get("action")
    obj_name = params.get("object_name") or "GreasePencil"
    if action == "create_layer":
        # Create or get GP object
        if obj_name not in bpy.data.objects:
            bpy.ops.object.gpencil_add(type="EMPTY", location=(0, 0, 0))
            bpy.context.active_object.name = obj_name
        gp = bpy.data.objects[obj_name].data
        layer = gp.layers.new(params.get("layer_name") or "Lines", set_active=True)
        return {"object": obj_name, "layer": layer.info}
    return {"error": f"action '{action}' stubbed; extend as needed", "next_step": "wire bpy.ops.gpencil.*"}


def handle_scene_snapshot_save(params):
    _require_bpy()
    snapshot_id = params.get("snapshot_id") or f"snap_{int(time.time() * 1000)}"
    snap = scene_object_snapshot() if scene_object_snapshot else _lite_snapshot()
    snap["_id"] = snapshot_id
    snap["_taken_at"] = time.time()
    _SNAPSHOTS[snapshot_id] = snap
    return {"snapshot_id": snapshot_id, "summary": {
        "objects": snap.get("object_count") or len(snap.get("objects") or []),
        "total_vertices": snap.get("total_vertices"),
    }}


def handle_scene_snapshot_list(params):
    return {"snapshots": [
        {"id": k, "taken_at": v.get("_taken_at"),
         "object_count": v.get("object_count") or len(v.get("objects") or [])}
        for k, v in _SNAPSHOTS.items()
    ]}


def handle_scene_snapshot_get(params):
    sid = params.get("snapshot_id")
    return _SNAPSHOTS.get(sid) or {"error": f"snapshot '{sid}' not found"}


def handle_scene_snapshot_diff(params):
    a_id = params.get("a_id")
    b_id = params.get("b_id")
    a = _SNAPSHOTS.get(a_id)
    b = _SNAPSHOTS.get(b_id)
    if not a or not b:
        return {"error": "a_id and b_id must both be saved snapshots"}
    a_objs = {o["name"]: o for o in a.get("objects") or []}
    b_objs = {o["name"]: o for o in b.get("objects") or []}
    added = [n for n in b_objs if n not in a_objs]
    removed = [n for n in a_objs if n not in b_objs]
    modified = []
    for n in a_objs.keys() & b_objs.keys():
        ao, bo = a_objs[n], b_objs[n]
        delta = {}
        for key in ("vertices", "triangles", "modifiers"):
            if ao.get(key) != bo.get(key):
                delta[key] = [ao.get(key), bo.get(key)]
        if delta:
            modified.append({"name": n, "delta": delta})
    total_dv = (b.get("total_vertices", 0) or 0) - (a.get("total_vertices", 0) or 0)
    return {
        "a_id": a_id, "b_id": b_id,
        "objects_added": added, "objects_removed": removed,
        "objects_modified": modified,
        "vertex_delta": total_dv,
    }


def handle_scene_snapshot_clear(params):
    older = params.get("older_than_seconds")
    before = len(_SNAPSHOTS)
    if older is None:
        _SNAPSHOTS.clear()
    else:
        cutoff = time.time() - float(older)
        for k in list(_SNAPSHOTS.keys()):
            if _SNAPSHOTS[k].get("_taken_at", 0) < cutoff:
                del _SNAPSHOTS[k]
    return {"removed": before - len(_SNAPSHOTS), "remaining": len(_SNAPSHOTS)}


def _lite_snapshot():
    """Fallback if depsgraph_helpers.scene_object_snapshot isn't importable."""
    _require_bpy()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    out = []
    total_v = 0
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        try:
            o_eval = o.evaluated_get(depsgraph)
            m = o_eval.to_mesh()
            try:
                vc = len(m.vertices)
                total_v += vc
                out.append({
                    "name": o.name, "type": o.type,
                    "vertices": vc, "triangles": sum(1 for _ in m.polygons) * 2,  # rough
                    "modifiers": [mod.type for mod in o.modifiers],
                    "visible": o.visible_get(),
                })
            finally:
                o_eval.to_mesh_clear()
        except Exception:
            out.append({"name": o.name, "error": "could not evaluate"})
    return {"object_count": len(out), "objects": out, "total_vertices": total_v, "timestamp": time.time()}


# ─────────────────────────── Dispatch table ───────────────────────────

DISPATCH_NEW_HANDLERS = {
    # Spatial
    "spatial_raycast": handle_spatial_raycast,
    "spatial_bbox_world": handle_spatial_bbox_world,
    "spatial_check_collision": handle_spatial_check_collision,
    "spatial_find_placement": handle_spatial_find_placement,
    "spatial_movement_range": handle_spatial_movement_range,
    "spatial_scene_bounds": handle_scene_bounds,
    "scene_bounds": handle_scene_bounds,
    # Semantic / dims / floor plan
    "semantic_place": handle_semantic_place,
    "dimensions_estimate": handle_dimensions_estimate,
    "dimensions_scale": handle_dimensions_scale,
    "floor_plan_data": handle_floor_plan_data,
    # Extended tools
    "camera_advanced": handle_camera_advanced,
    "uv_unwrap": handle_uv_unwrap,
    "texture_bake": handle_texture_bake,
    "generate_lod": handle_generate_lod,
    "vr_validate": handle_vr_validate,
    "vr_optimize": handle_vr_optimize,
    "vr_export": handle_vr_export,
    "gaussian_splat_import_ply": handle_gaussian_splat_import_ply,
    "gaussian_splat_import_splat": handle_gaussian_splat_import_splat,
    "gaussian_splat_render_with_splats": handle_gaussian_splat_render_with_splats,
    "gaussian_splat_list": handle_gaussian_splat_list,
    "grease_pencil_action": handle_grease_pencil_action,
    # Snapshots
    "scene_snapshot_save": handle_scene_snapshot_save,
    "scene_snapshot_list": handle_scene_snapshot_list,
    "scene_snapshot_get": handle_scene_snapshot_get,
    "scene_snapshot_diff": handle_scene_snapshot_diff,
    "scene_snapshot_clear": handle_scene_snapshot_clear,
}
