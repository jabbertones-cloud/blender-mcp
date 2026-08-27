"""Objective scene diagnostics for quality control. Addon-only; not an MCP tool."""
from __future__ import annotations

try:
    import bpy
except ImportError:
    bpy = None  # type: ignore


def handle_scene_diagnostics(params):
    if bpy is None:
        raise RuntimeError("scene_diagnostics requires Blender")
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


QUALITY_HANDLERS = {"scene_diagnostics": handle_scene_diagnostics}
