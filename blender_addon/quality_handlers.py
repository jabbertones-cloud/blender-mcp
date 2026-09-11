"""Objective scene diagnostics and bounded product setup handlers.

This module is addon-only. It deliberately avoids arbitrary code execution and
keeps generated product-scene resources isolated from user-authored scene data.
"""
from __future__ import annotations

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore


DIAGNOSTICS_SCHEMA_VERSION = 2
MAX_DIAGNOSTIC_OBJECTS = 2000
OWNER_KEY = "openclaw_owner"
OWNER_VALUE = "product_workflow"
ROLE_KEY = "openclaw_role"


def _require_blender(operation: str):
    if bpy is None:
        raise RuntimeError(f"{operation} requires Blender")


def _vec(values):
    return [float(v) for v in values]


def _owned(obj, role: str | None = None) -> bool:
    if obj.get(OWNER_KEY) != OWNER_VALUE:
        return False
    return role is None or obj.get(ROLE_KEY) == role


def _tag(obj, role: str):
    obj[OWNER_KEY] = OWNER_VALUE
    obj[ROLE_KEY] = role


def _scene_collection(scene):
    """Use the scene root collection, never context-dependent active collection."""
    return scene.collection


def _remove_owned(role: str):
    for obj in list(bpy.data.objects):
        if _owned(obj, role):
            bpy.data.objects.remove(obj, do_unlink=True)


def _object_center_world(obj):
    """Return evaluated world-space bounding-box center, falling back to origin."""
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        corners = [evaluated.matrix_world @ __import__("mathutils").Vector(corner) for corner in evaluated.bound_box]
        if corners:
            return sum(corners, __import__("mathutils").Vector()) / len(corners)
    except Exception:
        pass
    return obj.matrix_world.translation.copy()


def _material_names(obj):
    slots = getattr(obj, "material_slots", None) or []
    return [slot.material.name for slot in slots if getattr(slot, "material", None)]


def _object_snapshot(obj):
    matrix = obj.matrix_world
    return {
        "name": obj.name,
        "type": obj.type,
        "location_world": _vec(matrix.translation),
        "rotation_euler": _vec(obj.rotation_euler),
        "scale": _vec(obj.scale),
        "dimensions": _vec(obj.dimensions),
        "materials": _material_names(obj),
        "parent": obj.parent.name if obj.parent else None,
        "owned": _owned(obj),
        "role": obj.get(ROLE_KEY) if _owned(obj) else None,
    }


def handle_scene_diagnostics(params):
    _require_blender("scene_diagnostics")
    scene = bpy.context.scene
    all_objects = sorted(list(scene.objects), key=lambda obj: obj.name)
    truncated = len(all_objects) > MAX_DIAGNOSTIC_OBJECTS
    listed = all_objects[:MAX_DIAGNOSTIC_OBJECTS]
    objects = [_object_snapshot(obj) for obj in listed]

    camera_obj = scene.camera or next((obj for obj in scene.objects if obj.type == "CAMERA"), None)
    camera = None
    if camera_obj is not None:
        data = camera_obj.data
        dof = getattr(data, "dof", None)
        camera = {
            "name": camera_obj.name,
            "location_world": _vec(camera_obj.matrix_world.translation),
            "rotation_euler": _vec(camera_obj.rotation_euler),
            "lens_mm": float(getattr(data, "lens", 0.0)),
            "clip_start": float(getattr(data, "clip_start", 0.0)),
            "clip_end": float(getattr(data, "clip_end", 0.0)),
            "dof_enabled": bool(getattr(dof, "use_dof", False)) if dof else False,
            "focus_object": getattr(getattr(dof, "focus_object", None), "name", None) if dof else None,
            "focus_distance": float(getattr(dof, "focus_distance", 0.0)) if dof else None,
            "aperture_fstop": float(getattr(dof, "aperture_fstop", 0.0)) if dof else None,
            "owned": _owned(camera_obj),
            "role": camera_obj.get(ROLE_KEY) if _owned(camera_obj) else None,
        }

    lights = []
    for obj in sorted((obj for obj in scene.objects if obj.type == "LIGHT"), key=lambda obj: obj.name):
        data = obj.data
        lights.append({
            "name": obj.name,
            "type": str(getattr(data, "type", "")),
            "energy": float(getattr(data, "energy", 0.0)),
            "color": _vec(getattr(data, "color", (1.0, 1.0, 1.0))),
            "location_world": _vec(obj.matrix_world.translation),
            "rotation_euler": _vec(obj.rotation_euler),
            "owned": _owned(obj),
            "role": obj.get(ROLE_KEY) if _owned(obj) else None,
        })

    world = scene.world
    world_info = {
        "present": world is not None,
        "name": world.name if world else None,
        "uses_nodes": bool(getattr(world, "use_nodes", False)) if world else False,
        "environment_textures": [],
    }
    if world and world.use_nodes and world.node_tree:
        world_info["environment_textures"] = [
            node.image.filepath
            for node in world.node_tree.nodes
            if getattr(node, "type", "") == "TEX_ENVIRONMENT" and getattr(node, "image", None)
        ]

    render = scene.render
    cycles = getattr(scene, "cycles", None)
    image_settings = getattr(render, "image_settings", None)
    return {
        "schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "scene": scene.name,
        "frame_current": int(scene.frame_current),
        "frame_start": int(scene.frame_start),
        "frame_end": int(scene.frame_end),
        "object_count": len(all_objects),
        "objects_listed": len(objects),
        "objects_truncated": truncated,
        "objects": objects,
        "camera_present": camera is not None,
        "camera": camera,
        "light_count": len(lights),
        "lights": lights,
        "world": world_info,
        "render": {
            "engine": str(getattr(render, "engine", "")),
            "resolution_x": int(getattr(render, "resolution_x", 0)),
            "resolution_y": int(getattr(render, "resolution_y", 0)),
            "resolution_percentage": int(getattr(render, "resolution_percentage", 0)),
            "film_transparent": bool(getattr(render, "film_transparent", False)),
            "filepath": str(getattr(render, "filepath", "")),
            "file_format": str(getattr(image_settings, "file_format", "")) if image_settings else None,
            "samples": int(getattr(cycles, "samples", 0)) if cycles else None,
        },
    }


LIGHTING_DEFS = {
    "product_studio": {
        "lights": [
            {"name": "Key", "type": "AREA", "loc": (3, -4, 5), "rot": (50, 0, 25), "energy": 600, "size": 2.0},
            {"name": "Fill", "type": "AREA", "loc": (-3, -2, 3), "rot": (35, 0, -40), "energy": 250, "size": 3.0},
            {"name": "Back", "type": "AREA", "loc": (0, 3, 4), "rot": (-20, 0, 180), "energy": 350, "size": 1.5},
        ]
    },
    "dramatic": {
        "lights": [
            {"name": "Key", "type": "SPOT", "loc": (2, -3, 4), "rot": (45, 0, 30), "energy": 1000, "size": 0.5, "spot_size": 45},
            {"name": "Rim", "type": "AREA", "loc": (-2, 3, 3), "rot": (-30, 0, -145), "energy": 800, "size": 1.0},
        ]
    },
    "soft_box": {
        "lights": [
            {"name": "Top", "type": "AREA", "loc": (0, 0, 5), "rot": (0, 0, 0), "energy": 800, "size": 4.0},
            {"name": "Front", "type": "AREA", "loc": (0, -4, 2), "rot": (75, 0, 0), "energy": 300, "size": 3.0},
        ]
    },
}


def handle_product_lighting(params):
    import math

    _require_blender("product_lighting")
    scene = bpy.context.scene
    preset = str(params.get("preset", "product_studio"))
    definition = LIGHTING_DEFS.get(preset)
    if definition is None:
        raise ValueError(f"Unsupported lighting preset: {preset}")

    # Replace only resources created by this workflow. User-authored lights and
    # lights created by other addons remain untouched.
    _remove_owned("product_light")

    created = []
    collection = _scene_collection(scene)
    for light_def in definition["lights"]:
        data = bpy.data.lights.new(name=f"OpenClaw_{light_def['name']}", type=light_def["type"])
        data.energy = light_def["energy"]
        if "size" in light_def and hasattr(data, "size"):
            data.size = light_def["size"]
        if "spot_size" in light_def and hasattr(data, "spot_size"):
            data.spot_size = math.radians(light_def["spot_size"])
        obj = bpy.data.objects.new(name=f"OpenClaw_{light_def['name']}", object_data=data)
        _tag(obj, "product_light")
        collection.objects.link(obj)
        obj.location = light_def["loc"]
        obj.rotation_euler = [math.radians(value) for value in light_def["rot"]]
        created.append(obj.name)
    return {"status": "ok", "preset": preset, "lights": created, "ownership": OWNER_VALUE}


def handle_product_camera(params):
    _require_blender("product_camera")
    scene = bpy.context.scene
    target_name = str(params.get("target_object", ""))
    target_obj = bpy.data.objects.get(target_name) if target_name else None
    if target_name and target_obj is None:
        raise ValueError(f"Target object not found: {target_name}")

    _remove_owned("product_camera")
    _remove_owned("product_camera_target")

    frames = int(params.get("frames", 120))
    distance = float(params.get("camera_distance", 4.0))
    height = float(params.get("camera_height", 1.2))
    focal = float(params.get("focal_length", 50.0))
    fstop = float(params.get("f_stop", 2.8))
    use_dof = bool(params.get("use_dof", True))
    fps = int(params.get("fps", 24))
    if frames < 1 or distance <= 0 or focal <= 0 or fstop <= 0 or fps <= 0:
        raise ValueError("Invalid camera setup parameters")

    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frames
    collection = _scene_collection(scene)

    cam_data = bpy.data.cameras.new("OpenClaw_Product_Camera")
    cam_data.lens = focal
    cam_data.dof.use_dof = use_dof
    cam_data.dof.aperture_fstop = fstop
    if target_obj:
        cam_data.dof.focus_object = target_obj
    cam_obj = bpy.data.objects.new("OpenClaw_Product_Camera", cam_data)
    _tag(cam_obj, "product_camera")
    collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target = bpy.data.objects.new("OpenClaw_Product_Target", None)
    _tag(target, "product_camera_target")
    collection.objects.link(target)
    if target_obj:
        target.location = _object_center_world(target_obj)

    constraint = cam_obj.constraints.new("TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    cam_obj.location = (target.location.x, target.location.y - distance, target.location.z + height)
    return {
        "status": "ok",
        "camera": cam_obj.name,
        "target": target_name or None,
        "target_world": _vec(target.location),
        "ownership": OWNER_VALUE,
    }


def _unsupported(operation: str):
    raise NotImplementedError(
        f"{operation} is not implemented by the native quality handler; refusing to report success"
    )


def handle_product_material(params):
    _require_blender("product_material")
    return _unsupported("product_material")


def handle_product_render_setup(params):
    _require_blender("product_render_setup")
    return _unsupported("product_render_setup")


QUALITY_HANDLERS = {
    "scene_diagnostics": handle_scene_diagnostics,
    "product_lighting": handle_product_lighting,
    "product_camera": handle_product_camera,
    "product_material": handle_product_material,
    "product_render_setup": handle_product_render_setup,
}
