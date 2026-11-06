"""Objective scene diagnostics and bounded product setup handlers.

This module is addon-only. It deliberately avoids arbitrary code execution and
keeps generated product-scene resources isolated from user-authored scene data.
"""
from __future__ import annotations

try:
    import bpy
    from mathutils import Vector
except ImportError:
    bpy = None  # type: ignore
    Vector = None  # type: ignore


DIAGNOSTICS_SCHEMA_VERSION = 2
MAX_DIAGNOSTIC_OBJECTS = 500
OWNER_KEY = "openclaw_owner"
OWNER_VALUE = "product_workflow"
ROLE_KEY = "openclaw_role"
PREVIOUS_CAMERA_KEY = "openclaw_previous_camera"


def _require_blender(operation: str):
    if bpy is None:
        raise RuntimeError(f"{operation} requires Blender")


def _vec(values):
    return [float(v) for v in values]


def _matrix(matrix):
    return [[float(value) for value in row] for row in matrix]


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


def _remove_owned(scene, role: str):
    """Remove only this workflow's objects in this scene and clean orphan data."""
    removed = []
    for obj in list(scene.objects):
        if not _owned(obj, role):
            continue
        data = getattr(obj, "data", None)
        data_type = getattr(obj, "type", None)
        removed.append(obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and getattr(data, "users", 1) == 0:
            if data_type == "LIGHT":
                bpy.data.lights.remove(data)
            elif data_type == "CAMERA":
                bpy.data.cameras.remove(data)
    return removed


def _evaluated_object(obj):
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        return obj.evaluated_get(depsgraph)
    except Exception:
        return obj


def _object_center_world(obj):
    """Return evaluated world-space bounding-box center, falling back to origin."""
    evaluated = _evaluated_object(obj)
    try:
        corners = [evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box]
        if corners:
            return sum(corners, Vector()) / len(corners)
    except Exception:
        pass
    return evaluated.matrix_world.translation.copy()


def _material_names(obj):
    slots = getattr(obj, "material_slots", None) or []
    return [slot.material.name for slot in slots if getattr(slot, "material", None)]


def _object_snapshot(obj):
    evaluated = _evaluated_object(obj)
    matrix = evaluated.matrix_world
    return {
        "name": obj.name,
        "type": obj.type,
        "location_world": _vec(matrix.translation),
        "matrix_world": _matrix(matrix),
        "rotation_euler_local": _vec(obj.rotation_euler),
        "scale_local": _vec(obj.scale),
        "dimensions_evaluated": _vec(evaluated.dimensions),
        "materials": _material_names(obj),
        "parent": obj.parent.name if obj.parent else None,
        "owned": _owned(obj),
        "role": obj.get(ROLE_KEY) if _owned(obj) else None,
    }


def handle_scene_diagnostics(params):
    _require_blender("scene_diagnostics")
    scene = bpy.context.scene
    requested_limit = int(params.get("object_limit", MAX_DIAGNOSTIC_OBJECTS))
    object_limit = max(1, min(requested_limit, MAX_DIAGNOSTIC_OBJECTS))
    all_objects = sorted(list(scene.objects), key=lambda obj: obj.name)
    truncated = len(all_objects) > object_limit
    listed = all_objects[:object_limit]
    objects = [_object_snapshot(obj) for obj in listed]

    camera_obj = scene.camera or next((obj for obj in scene.objects if obj.type == "CAMERA"), None)
    camera = None
    if camera_obj is not None:
        data = camera_obj.data
        dof = getattr(data, "dof", None)
        camera = {
            "name": camera_obj.name,
            "location_world": _vec(camera_obj.matrix_world.translation),
            "matrix_world": _matrix(camera_obj.matrix_world),
            "rotation_euler_local": _vec(camera_obj.rotation_euler),
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
            "matrix_world": _matrix(obj.matrix_world),
            "rotation_euler_local": _vec(obj.rotation_euler),
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
        "object_limit": object_limit,
        "objects_listed": len(objects),
        "objects_truncated": truncated,
        "objects": objects,
        "camera_present": camera is not None,
        "camera": camera,
        "previous_camera": scene.get(PREVIOUS_CAMERA_KEY),
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
    "product_studio": {"lights": [
        {"name": "Key", "type": "AREA", "loc": (3, -4, 5), "rot": (50, 0, 25), "energy": 600, "size": 2.0},
        {"name": "Fill", "type": "AREA", "loc": (-3, -2, 3), "rot": (35, 0, -40), "energy": 250, "size": 3.0},
        {"name": "Back", "type": "AREA", "loc": (0, 3, 4), "rot": (-20, 0, 180), "energy": 350, "size": 1.5},
    ]},
    "dramatic": {"lights": [
        {"name": "Key", "type": "SPOT", "loc": (2, -3, 4), "rot": (45, 0, 30), "energy": 1000, "size": 0.5, "spot_size": 45},
        {"name": "Rim", "type": "AREA", "loc": (-2, 3, 3), "rot": (-30, 0, -145), "energy": 800, "size": 1.0},
    ]},
    "soft_box": {"lights": [
        {"name": "Top", "type": "AREA", "loc": (0, 0, 5), "rot": (0, 0, 0), "energy": 800, "size": 4.0},
        {"name": "Front", "type": "AREA", "loc": (0, -4, 2), "rot": (75, 0, 0), "energy": 300, "size": 3.0},
    ]},
}


def handle_product_lighting(params):
    import math
    _require_blender("product_lighting")
    scene = bpy.context.scene
    preset = str(params.get("preset", "product_studio"))
    definition = LIGHTING_DEFS.get(preset)
    if definition is None:
        raise ValueError(f"Unsupported lighting preset: {preset}")
    _remove_owned(scene, "product_light")
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

    previous_active = scene.camera
    if previous_active is not None and not _owned(previous_active, "product_camera"):
        scene[PREVIOUS_CAMERA_KEY] = previous_active.name
    previous_camera = scene.get(PREVIOUS_CAMERA_KEY)
    _remove_owned(scene, "product_camera")
    _remove_owned(scene, "product_camera_target")

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
        "previous_camera": previous_camera,
        "target": target_name or None,
        "target_world": _vec(target.location),
        "ownership": OWNER_VALUE,
    }


def _set_bsdf_input(bsdf, name_4x, value, name_3x=None):
    """Set a Principled BSDF input, tolerating Blender 3.x/4.x renames."""
    if name_4x in bsdf.inputs:
        bsdf.inputs[name_4x].default_value = value
    elif name_3x and name_3x in bsdf.inputs:
        bsdf.inputs[name_3x].default_value = value


def handle_product_material(params):
    """Create (or adopt) a Principled-BSDF product material and assign it.

    Ported from the bridge's native implementation; generated materials are
    tagged with this workflow's ownership key so later passes can tell
    workflow-owned resources apart from user-authored scene data.
    """
    _require_blender("product_material")
    obj_name = params.get("object_name")
    if not obj_name:
        return {"error": "object_name is required"}
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"error": f"Object {obj_name} not found"}

    mat_name = params.get("material_name", "ProductMaterial")
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return {"error": "Material does not have Principled BSDF"}

    if "color" in params:
        bsdf.inputs["Base Color"].default_value = params["color"]
    if "roughness" in params:
        bsdf.inputs["Roughness"].default_value = params["roughness"]
    if "metallic" in params:
        bsdf.inputs["Metallic"].default_value = params["metallic"]
    if "transmission" in params:
        _set_bsdf_input(bsdf, "Transmission Weight", params["transmission"], "Transmission")
    if "ior" in params:
        bsdf.inputs["IOR"].default_value = params["ior"]
    if "coat_weight" in params:
        _set_bsdf_input(bsdf, "Coat Weight", params["coat_weight"])
    if "coat_roughness" in params:
        _set_bsdf_input(bsdf, "Coat Roughness", params["coat_roughness"])
    if "subsurface" in params:
        _set_bsdf_input(bsdf, "Subsurface Weight", params["subsurface"], "Subsurface")

    if params.get("add_imperfections"):
        tc = nodes.new("ShaderNodeTexCoord")
        tc.location = (-800, 0)
        fp = nodes.new("ShaderNodeTexNoise")
        fp.location = (-600, 100)
        fp.inputs["Scale"].default_value = 800
        fp.inputs["Detail"].default_value = 8
        fp_s = nodes.new("ShaderNodeMath")
        fp_s.location = (-400, 100)
        fp_s.operation = "MULTIPLY"
        fp_s.inputs[1].default_value = 0.5
        fp_a = nodes.new("ShaderNodeMath")
        fp_a.location = (-200, 100)
        fp_a.operation = "ADD"
        fp_a.inputs[1].default_value = params.get("roughness", 0.15)

        links = mat.node_tree.links
        links.new(tc.outputs["Object"], fp.inputs["Vector"])
        links.new(fp.outputs["Fac"], fp_s.inputs[0])
        links.new(fp_s.outputs["Value"], fp_a.inputs[0])
        links.new(fp_a.outputs["Value"], bsdf.inputs["Roughness"])

    _tag(mat, "product_material")

    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat

    return {
        "status": "ok",
        "material": mat.name,
        "object": obj.name,
        "ownership": OWNER_VALUE,
    }


def handle_product_render_setup(params):
    """Configure bounded render settings for product shots.

    Ported from the bridge's native implementation: allowlisted engines,
    fixed quality/resolution maps, Cycles tuning, and an optional
    bloom/vignette compositor chain.
    """
    _require_blender("product_render_setup")
    scene = bpy.context.scene

    engine = params.get("engine", "CYCLES").upper()
    if engine not in ["CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]:
        return {"error": f"Engine {engine} not allowed"}
    scene.render.engine = engine

    QUALITY_MAP = {
        "fast": {"samples": 128, "bounces": 6, "threshold": 0.1},
        "balanced": {"samples": 256, "bounces": 8, "threshold": 0.05},
        "premium": {"samples": 512, "bounces": 12, "threshold": 0.01},
    }

    RES_MAP = {
        "720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160),
        "square_1080": (1080, 1080), "vertical": (1080, 1920), "instagram": (1080, 1350),
    }

    q = QUALITY_MAP.get(params.get("quality", "balanced"), QUALITY_MAP["balanced"])
    w, h = RES_MAP.get(params.get("resolution", "1080p"), RES_MAP["1080p"])

    if engine == "CYCLES":
        scene.cycles.device = "GPU"
        scene.cycles.samples = q["samples"]
        scene.cycles.preview_samples = 64
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = q["threshold"]
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
        scene.cycles.max_bounces = q["bounces"]
        scene.cycles.diffuse_bounces = 3
        scene.cycles.glossy_bounces = 4
        scene.cycles.transmission_bounces = 8
        scene.cycles.volume_bounces = 0
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False
        scene.cycles.use_persistent_data = True

    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = bool(params.get("transparent_bg", True))

    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Punchy"
    except Exception:
        scene.view_settings.view_transform = "Filmic"
        scene.view_settings.look = "Medium High Contrast"

    scene.render.image_settings.file_format = params.get("output_format", "PNG")
    scene.render.image_settings.color_mode = "RGBA"

    if "output_path" in params:
        scene.render.filepath = params["output_path"]

    # Compositor
    scene.use_nodes = True
    tree = scene.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)

    rl = tree.nodes.new("CompositorNodeRLayers")
    rl.location = (0, 0)
    comp = tree.nodes.new("CompositorNodeComposite")
    comp.location = (800, 0)
    last = rl.outputs["Image"]
    x = 200

    if params.get("bloom", True):
        gl = tree.nodes.new("CompositorNodeGlare")
        gl.location = (x, 0)
        gl.glare_type = "FOG_GLOW"
        gl.threshold = 0.8
        gl.quality = "HIGH"
        gl.mix = -0.7
        gl.size = 6
        tree.links.new(last, gl.inputs[0])
        last = gl.outputs[0]
        x += 200

    if params.get("vignette", True):
        mask = tree.nodes.new("CompositorNodeEllipseMask")
        mask.location = (x, -200)
        mask.width = 0.85
        mask.height = 0.85
        blur = tree.nodes.new("CompositorNodeBlur")
        blur.location = (x + 200, -200)
        blur.size_x = 200
        blur.size_y = 200
        blur.use_relative = True
        mix = tree.nodes.new("CompositorNodeMixRGB")
        mix.location = (x + 400, 0)
        mix.blend_type = "MULTIPLY"
        tree.links.new(mask.outputs[0], blur.inputs[0])
        tree.links.new(last, mix.inputs[1])
        tree.links.new(blur.outputs[0], mix.inputs[2])
        last = mix.outputs[0]

    tree.links.new(last, comp.inputs["Image"])

    return {"status": "ok", "ownership": OWNER_VALUE}


QUALITY_HANDLERS = {
    "scene_diagnostics": handle_scene_diagnostics,
    "product_lighting": handle_product_lighting,
    "product_camera": handle_product_camera,
    "product_material": handle_product_material,
    "product_render_setup": handle_product_render_setup,
}
