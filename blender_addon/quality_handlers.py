"""Objective scene diagnostics and bounded product setup handlers."""
from __future__ import annotations

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore


def _require_blender(operation: str):
    if bpy is None:
        raise RuntimeError(f"{operation} requires Blender")


def handle_scene_diagnostics(params):
    _require_blender("scene_diagnostics")
    scene = bpy.context.scene
    objects = [{"name": obj.name, "type": obj.type} for obj in scene.objects]
    camera_obj = scene.camera or next((obj for obj in scene.objects if obj.type == "CAMERA"), None)
    camera = None
    if camera_obj is not None:
        data = camera_obj.data
        dof = getattr(data, "dof", None)
        camera = {
            "name": camera_obj.name,
            "lens_mm": float(getattr(data, "lens", 0.0)),
            "clip_start": float(getattr(data, "clip_start", 0.0)),
            "clip_end": float(getattr(data, "clip_end", 0.0)),
            "dof_enabled": bool(getattr(dof, "use_dof", False)) if dof else False,
            "focus_object": getattr(getattr(dof, "focus_object", None), "name", None) if dof else None,
            "focus_distance": float(getattr(dof, "focus_distance", 0.0)) if dof else None,
            "aperture_fstop": float(getattr(dof, "aperture_fstop", 0.0)) if dof else None,
        }
    lights = []
    for obj in scene.objects:
        if obj.type == "LIGHT":
            data = obj.data
            lights.append({"name": obj.name, "type": str(getattr(data, "type", "")), "energy": float(getattr(data, "energy", 0.0))})
    world = scene.world
    world_info = {"present": world is not None, "name": world.name if world else None, "uses_nodes": bool(getattr(world, "use_nodes", False)) if world else False, "environment_textures": []}
    if world and world.use_nodes and world.node_tree:
        world_info["environment_textures"] = [node.image.filepath for node in world.node_tree.nodes if getattr(node, "type", "") == "TEX_ENVIRONMENT" and getattr(node, "image", None)]
    render = scene.render
    cycles = getattr(scene, "cycles", None)
    return {
        "objects": objects,
        "object_count": len(objects),
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
    preset = str(params.get("preset", "product_studio"))
    definition = LIGHTING_DEFS.get(preset)
    if definition is None:
        raise ValueError(f"Unsupported lighting preset: {preset}")

    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    created = []
    for light_def in definition["lights"]:
        data = bpy.data.lights.new(name=light_def["name"], type=light_def["type"])
        data.energy = light_def["energy"]
        if "size" in light_def and hasattr(data, "size"):
            data.size = light_def["size"]
        if "spot_size" in light_def and hasattr(data, "spot_size"):
            data.spot_size = math.radians(light_def["spot_size"])
        obj = bpy.data.objects.new(name=light_def["name"], object_data=data)
        bpy.context.collection.objects.link(obj)
        obj.location = light_def["loc"]
        obj.rotation_euler = [math.radians(value) for value in light_def["rot"]]
        created.append(obj.name)
    return {"status": "ok", "preset": preset, "lights": created}


def handle_product_camera(params):
    _require_blender("product_camera")
    scene = bpy.context.scene
    target_name = str(params.get("target_object", ""))
    target_obj = bpy.data.objects.get(target_name) if target_name else None
    if target_name and target_obj is None:
        raise ValueError(f"Target object not found: {target_name}")

    for obj in list(bpy.data.objects):
        if obj.name.startswith("Turntable_") or obj.name == "Product_Camera":
            bpy.data.objects.remove(obj, do_unlink=True)

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
    cam_data = bpy.data.cameras.new("Product_Camera")
    cam_data.lens = focal
    cam_data.dof.use_dof = use_dof
    cam_data.dof.aperture_fstop = fstop
    if target_obj:
        cam_data.dof.focus_object = target_obj
    cam_obj = bpy.data.objects.new("Product_Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    target = bpy.data.objects.new("Turntable_Target", None)
    bpy.context.collection.objects.link(target)
    if target_obj:
        target.location = target_obj.location
    constraint = cam_obj.constraints.new("TRACK_TO")
    constraint.target = target
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    cam_obj.location = (target.location.x, target.location.y - distance, target.location.z + height)
    return {"status": "ok", "camera": cam_obj.name, "target": target_name or None}


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
