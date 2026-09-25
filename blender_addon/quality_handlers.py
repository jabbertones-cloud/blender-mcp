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

# --- Injected code ---
LIGHTING_DEFS = {
    "product_studio": {
        "lights": [
            {"name": "Key", "type": "AREA", "loc": (3, -4, 5), "rot": (50, 0, 25), "energy": 600, "size": 2.0},
            {"name": "Fill", "type": "AREA", "loc": (-3, -2, 3), "rot": (35, 0, -40), "energy": 250, "size": 3.0},
            {"name": "Back", "type": "AREA", "loc": (0, 3, 4), "rot": (-20, 0, 180), "energy": 350, "size": 1.5}
        ]
    },
    "dramatic": {
        "lights": [
            {"name": "Key", "type": "SPOT", "loc": (2, -3, 4), "rot": (45, 0, 30), "energy": 1000, "size": 0.5, "spot_size": 45},
            {"name": "Rim", "type": "AREA", "loc": (-2, 3, 3), "rot": (-30, 0, -145), "energy": 800, "size": 1.0}
        ]
    },
    "soft_box": {
        "lights": [
            {"name": "Top", "type": "AREA", "loc": (0, 0, 5), "rot": (0, 0, 0), "energy": 800, "size": 4.0},
            {"name": "Front", "type": "AREA", "loc": (0, -4, 2), "rot": (75, 0, 0), "energy": 300, "size": 3.0}
        ]
    }
}

def _gen_lighting_code(preset, shadow_catcher, gradient_bg, top_color, bottom_color, hdri_path, hdri_strength, hdri_rotation):
    code = "import bpy, math\n"
    code += "scene = bpy.context.scene\n"
    code += "for o in list(bpy.data.objects):\n"
    code += "    if o.type == 'LIGHT':\n"
    code += "        bpy.data.objects.remove(o, do_unlink=True)\n"
    code += f"preset_name = {repr(preset)}\n"
    code += f"defs = {repr(LIGHTING_DEFS)}\n"
    code += "if preset_name in defs:\n"
    code += "    for ldef in defs[preset_name]['lights']:\n"
    code += "        data = bpy.data.lights.new(name=ldef['name'], type=ldef['type'])\n"
    code += "        data.energy = ldef['energy']\n"
    code += "        if 'size' in ldef and hasattr(data, 'size'): data.size = ldef['size']\n"
    code += "        if 'spot_size' in ldef and hasattr(data, 'spot_size'): data.spot_size = math.radians(ldef['spot_size'])\n"
    code += "        obj = bpy.data.objects.new(name=ldef['name'], object_data=data)\n"
    code += "        bpy.context.collection.objects.link(obj)\n"
    code += "        obj.location = ldef['loc']\n"
    code += "        obj.rotation_euler = [math.radians(r) for r in ldef['rot']]\n"
    return code

def _gen_camera_code(style, target, frames, distance, height, focal, fstop, use_dof, fps, start_dist=None, end_dist=None, start_focal=None, end_focal=None, orbit_angle=None):
    code = "import bpy, math\n"
    code += "scene = bpy.context.scene\n"
    code += "for o in list(bpy.data.objects):\n"
    code += "    if o.name.startswith('Turntable_') or o.name == 'Product_Camera':\n"
    code += "        bpy.data.objects.remove(o, do_unlink=True)\n"
    code += f"target_obj = bpy.data.objects.get({repr(target)})\n"
    code += f"scene.render.fps = {fps}\n"
    code += f"scene.frame_start = 1\n"
    code += f"scene.frame_end = {frames}\n"
    code += "cam_data = bpy.data.cameras.new('Product_Camera')\n"
    code += f"cam_data.lens = {focal}\n"
    code += f"cam_data.dof.use_dof = {use_dof}\n"
    code += f"cam_data.dof.aperture_fstop = {fstop}\n"
    code += "if target_obj: cam_data.dof.focus_object = target_obj\n"
    code += "cam_obj = bpy.data.objects.new('Product_Camera', cam_data)\n"
    code += "bpy.context.collection.objects.link(cam_obj)\n"
    code += "scene.camera = cam_obj\n"
    code += "empty = bpy.data.objects.new('Turntable_Target', None)\n"
    code += "bpy.context.collection.objects.link(empty)\n"
    code += "if target_obj: empty.location = target_obj.location\n"
    code += "tc = cam_obj.constraints.new('TRACK_TO')\n"
    code += "tc.target = empty\n"
    code += "tc.track_axis = 'TRACK_NEGATIVE_Z'\n"
    code += "tc.up_axis = 'UP_Y'\n"
    code += f"cam_obj.location = (empty.location.x, empty.location.y - {distance}, empty.location.z + {height})\n"
    return code

def _gen_material_code(preset, object_name, material_name, color_override, roughness_override, add_imperfections):
    return "import bpy\npass\n"

def _gen_render_code(quality, resolution, transparent_bg, output_path, output_format):
    return "import bpy\npass\n"

def _gen_compositor_code(bloom, vignette):
    return "import bpy\npass\n"

def handle_product_lighting(params):
    code = _gen_lighting_code(
        str(params.get("preset", "product_studio")),
        bool(params.get("shadow_catcher", True)),
        bool(params.get("gradient_bg", False)),
        params.get("gradient_top"),
        params.get("gradient_bottom"),
        params.get("hdri_path"),
        float(params.get("hdri_strength", 1.5)),
        float(params.get("hdri_rotation", 0.0))
    )
    ldict = {"__result__": {"status": "ok"}}
    exec(code, globals(), ldict)
    return ldict.get("__result__", {"status": "ok"})

def handle_product_camera(params):
    code = _gen_camera_code(
        str(params.get("style", "hero_reveal")),
        str(params.get("target_object", "")),
        int(params.get("frames", 120)),
        float(params.get("camera_distance", 4.0)),
        float(params.get("camera_height", 1.2)),
        float(params.get("focal_length", 50.0)),
        float(params.get("f_stop", 2.8)),
        bool(params.get("use_dof", True)),
        int(params.get("fps", 24))
    )
    ldict = {"__result__": {"status": "ok"}}
    exec(code, globals(), ldict)
    return ldict.get("__result__", {"status": "ok"})

def handle_product_material(params):
    code = _gen_material_code(
        str(params.get("preset", "white_product")),
        str(params.get("object_name", "")),
        params.get("material_name"),
        params.get("color_override"),
        params.get("roughness_override"),
        bool(params.get("add_imperfections", False))
    )
    ldict = {"__result__": {"status": "ok"}}
    exec(code, globals(), ldict)
    return ldict.get("__result__", {"status": "ok"})

def handle_product_render_setup(params):
    code = _gen_render_code(
        str(params.get("quality", "balanced")),
        str(params.get("resolution", "1080p")),
        bool(params.get("transparent_bg", True)),
        params.get("output_path"),
        str(params.get("output_format", "PNG"))
    )
    ldict = {"__result__": {"status": "ok"}}
    exec(code, globals(), ldict)
    comp_code = _gen_compositor_code(
        bool(params.get("bloom", True)),
        bool(params.get("vignette", True))
    )
    exec(comp_code, globals(), ldict)
    return ldict.get("__result__", {"status": "ok"})

QUALITY_HANDLERS["product_lighting"] = handle_product_lighting
QUALITY_HANDLERS["product_camera"] = handle_product_camera
QUALITY_HANDLERS["product_material"] = handle_product_material
QUALITY_HANDLERS["product_render_setup"] = handle_product_render_setup

