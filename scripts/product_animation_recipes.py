#!/usr/bin/env python3
"""
Product Animation Recipes — Executable MCP Sequences
=====================================================
Each recipe is a sequence of MCP tool calls that produces a professional
product animation. These are meant to be called by Claude directing the
Blender MCP, or executed directly via the MCP server's execute_python tool.

Usage from Claude:
    1. Import product into Blender (or use existing object)
    2. Call the recipe function with the object name
    3. The recipe sets up materials, lighting, camera, animation, render

Usage standalone:
    python product_animation_recipes.py --recipe luxury_turntable --object MyProduct
"""

import json
import socket
import sys
import argparse
from typing import Optional, List, Dict, Any

# ─── MCP Communication ──────────────────────────────────────────────────────

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 9876

_counter = 0

def send(command: str, params: dict = None) -> dict:
    """Send command to Blender bridge, return result or raise."""
    global _counter
    _counter += 1
    payload = {"id": str(_counter), "command": command, "params": params or {}}
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(60.0)  # longer timeout for renders
        sock.connect((BLENDER_HOST, BLENDER_PORT))
        sock.sendall(json.dumps(payload).encode("utf-8"))
        
        chunks = []
        while True:
            chunk = sock.recv(1048576)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
                sock.close()
                if data.get("error"):
                    print(f"  [ERR] {command}: {data['error']}")
                    return data
                return data.get("result", data)
            except json.JSONDecodeError:
                continue
        sock.close()
        raw = b"".join(chunks).decode("utf-8")
        return json.loads(raw) if raw else {"error": "Empty response"}
    except ConnectionRefusedError:
        print("ERROR: Blender not running or bridge addon not enabled on port 9876")
        sys.exit(1)
    except Exception as e:
        return {"error": str(e)}


def run_python(code: str) -> dict:
    """Execute arbitrary Python in Blender. The escape hatch for anything MCP tools can't do."""
    return send("execute_python", {"code": code})


# ═══════════════════════════════════════════════════════════════════════════════
# MATERIAL PRESETS — Professional product materials via Principled BSDF
# ═══════════════════════════════════════════════════════════════════════════════

MATERIAL_PRESETS = {
    "glossy_plastic": {
        "color": [0.1, 0.1, 0.1, 1.0], "metallic": 0.0, "roughness": 0.15,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.2\nbsdf.inputs['Coat Roughness'].default_value = 0.05"
    },
    "matte_plastic": {
        "color": [0.2, 0.2, 0.2, 1.0], "metallic": 0.0, "roughness": 0.65,
        "extra": ""
    },
    "brushed_aluminum": {
        "color": [0.92, 0.92, 0.92, 1.0], "metallic": 1.0, "roughness": 0.35,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.2"
    },
    "polished_chrome": {
        "color": [0.77, 0.78, 0.78, 1.0], "metallic": 1.0, "roughness": 0.08,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.5\nbsdf.inputs['Coat Roughness'].default_value = 0.02"
    },
    "gold": {
        "color": [1.0, 0.84, 0.0, 1.0], "metallic": 1.0, "roughness": 0.15,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.3"
    },
    "rose_gold": {
        "color": [0.95, 0.77, 0.69, 1.0], "metallic": 1.0, "roughness": 0.18,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.3"
    },
    "copper": {
        "color": [0.96, 0.63, 0.48, 1.0], "metallic": 1.0, "roughness": 0.2,
        "extra": ""
    },
    "clear_glass": {
        "color": [1.0, 1.0, 1.0, 1.0], "metallic": 0.0, "roughness": 0.02,
        "extra": "bsdf.inputs['Transmission Weight'].default_value = 1.0\nbsdf.inputs['IOR'].default_value = 1.52"
    },
    "frosted_glass": {
        "color": [0.95, 0.97, 1.0, 1.0], "metallic": 0.0, "roughness": 0.25,
        "extra": "bsdf.inputs['Transmission Weight'].default_value = 1.0\nbsdf.inputs['IOR'].default_value = 1.52"
    },
    "tinted_glass": {
        "color": [0.3, 0.6, 0.4, 1.0], "metallic": 0.0, "roughness": 0.02,
        "extra": "bsdf.inputs['Transmission Weight'].default_value = 1.0\nbsdf.inputs['IOR'].default_value = 1.52"
    },
    "ceramic_glazed": {
        "color": [0.92, 0.88, 0.80, 1.0], "metallic": 0.0, "roughness": 0.45,
        "extra": "bsdf.inputs['Subsurface Weight'].default_value = 0.2\nbsdf.inputs['Coat Weight'].default_value = 0.8\nbsdf.inputs['Coat Roughness'].default_value = 0.1"
    },
    "rubber_matte": {
        "color": [0.1, 0.1, 0.1, 1.0], "metallic": 0.0, "roughness": 0.95,
        "extra": ""
    },
    "fabric_cotton": {
        "color": [0.85, 0.80, 0.75, 1.0], "metallic": 0.0, "roughness": 0.80,
        "extra": "bsdf.inputs['Subsurface Weight'].default_value = 0.08"
    },
    "leather": {
        "color": [0.35, 0.2, 0.1, 1.0], "metallic": 0.0, "roughness": 0.55,
        "extra": "bsdf.inputs['Subsurface Weight'].default_value = 0.05\nbsdf.inputs['Coat Weight'].default_value = 0.15"
    },
    "cosmetics_gold_cap": {
        "color": [1.0, 0.84, 0.0, 1.0], "metallic": 1.0, "roughness": 0.2,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.5\nbsdf.inputs['Coat Roughness'].default_value = 0.05"
    },
    "silk_satin": {
        "color": [0.85, 0.75, 0.8, 1.0], "metallic": 0.0, "roughness": 0.35,
        "extra": "bsdf.inputs['Subsurface Weight'].default_value = 0.1\nbsdf.inputs['Anisotropic'].default_value = 0.5"
    },
    "white_product": {
        "color": [0.95, 0.95, 0.95, 1.0], "metallic": 0.0, "roughness": 0.3,
        "extra": "bsdf.inputs['Coat Weight'].default_value = 0.1"
    },
}


def apply_material(object_name: str, preset_name: str, material_name: str = None):
    """Apply a professional material preset to an object via execute_python."""
    preset = MATERIAL_PRESETS.get(preset_name)
    if not preset:
        print(f"Unknown material preset: {preset_name}")
        return {"error": f"Unknown preset: {preset_name}"}
    
    mat_name = material_name or f"Product_{preset_name}"
    c = preset["color"]
    extra = preset.get("extra", "")
    
    code = f"""
import bpy

obj = bpy.data.objects.get("{object_name}")
if not obj:
    __result__ = {{"error": "Object '{object_name}' not found"}}
else:
    mat = bpy.data.materials.new("{mat_name}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = ({c[0]}, {c[1]}, {c[2]}, {c[3]})
        bsdf.inputs['Metallic'].default_value = {preset['metallic']}
        bsdf.inputs['Roughness'].default_value = {preset['roughness']}
        {extra}
    if obj.data and hasattr(obj.data, 'materials'):
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    __result__ = {{"status": "ok", "material": "{mat_name}", "preset": "{preset_name}"}}
"""
    return run_python(code)


# ═══════════════════════════════════════════════════════════════════════════════
# LIGHTING RIGS — Professional product lighting setups
# ═══════════════════════════════════════════════════════════════════════════════

LIGHTING_RIGS = {
    "product_studio": {
        "description": "Universal 3-point product studio",
        "lights": [
            {"name": "Key_Light", "type": "AREA", "location": [2.5, 0.5, 1.8], "energy": 100, "size": 1.5, "color": [1.0, 0.97, 0.92]},
            {"name": "Fill_Light", "type": "AREA", "location": [-2.0, 1.2, 0.8], "energy": 40, "size": 2.0, "color": [0.95, 0.93, 0.90]},
            {"name": "Rim_Light", "type": "AREA", "location": [0.0, -3.0, 2.5], "energy": 150, "size": 1.2, "color": [0.92, 0.95, 1.0]},
        ],
        "world_color": [0.05, 0.05, 0.06],
        "world_strength": 0.3,
    },
    "jewelry": {
        "description": "Jewelry/gemstone sparkle lighting",
        "lights": [
            {"name": "Sparkle_Key", "type": "AREA", "location": [1.5, 0.8, 2.5], "energy": 200, "size": 0.8, "color": [0.92, 0.95, 1.0]},
            {"name": "Fill_Warm", "type": "AREA", "location": [-1.2, -0.5, 1.0], "energy": 30, "size": 1.5, "color": [1.0, 0.95, 0.88]},
            {"name": "Rim_Cool", "type": "AREA", "location": [-2.0, 2.0, 1.8], "energy": 100, "size": 1.0, "color": [0.88, 0.92, 1.0]},
        ],
        "world_color": [0.02, 0.02, 0.03],
        "world_strength": 0.1,
    },
    "cosmetics": {
        "description": "Beauty/cosmetics product lighting",
        "lights": [
            {"name": "Key_Beauty", "type": "AREA", "location": [2.2, 0.3, 1.0], "energy": 85, "size": 1.8, "color": [1.0, 0.97, 0.93]},
            {"name": "Fill_Label", "type": "AREA", "location": [-2.5, 1.5, 0.9], "energy": 50, "size": 2.5, "color": [1.0, 0.96, 0.90]},
            {"name": "Rim_Luxury", "type": "AREA", "location": [0.2, -2.8, 1.5], "energy": 110, "size": 1.0, "color": [0.95, 0.97, 1.0]},
        ],
        "world_color": [0.08, 0.08, 0.09],
        "world_strength": 0.2,
    },
    "electronics": {
        "description": "Tech/electronics product lighting",
        "lights": [
            {"name": "Key_Screen", "type": "AREA", "location": [2.5, 0.5, 1.8], "energy": 110, "size": 2.0, "color": [1.0, 0.98, 0.95]},
            {"name": "Top_Edge", "type": "AREA", "location": [-1.0, -0.2, 2.3], "energy": 70, "size": 1.5, "color": [0.95, 0.97, 1.0]},
            {"name": "Rim_Sep", "type": "AREA", "location": [0.0, 3.0, 1.5], "energy": 130, "size": 1.2, "color": [0.92, 0.95, 1.0]},
        ],
        "world_color": [0.04, 0.04, 0.05],
        "world_strength": 0.15,
    },
    "automotive": {
        "description": "Automotive/reflective surface lighting",
        "lights": [
            {"name": "Key_Paint", "type": "AREA", "location": [2.0, -1.0, 1.2], "energy": 120, "size": 2.5, "color": [1.0, 0.98, 0.95]},
            {"name": "Accent_Flake", "type": "AREA", "location": [-3.5, 0.0, 2.0], "energy": 60, "size": 1.8, "color": [0.95, 0.97, 1.0]},
            {"name": "Rim_Define", "type": "AREA", "location": [0.5, 3.0, 2.2], "energy": 140, "size": 1.5, "color": [0.90, 0.94, 1.0]},
        ],
        "world_color": [0.03, 0.03, 0.04],
        "world_strength": 0.2,
    },
    "food_product": {
        "description": "Food/beverage product lighting",
        "lights": [
            {"name": "Key_Warm", "type": "AREA", "location": [2.0, 0.0, 1.5], "energy": 90, "size": 2.0, "color": [1.0, 0.95, 0.85]},
            {"name": "Fill_Soft", "type": "AREA", "location": [-1.5, 1.0, 0.8], "energy": 45, "size": 2.5, "color": [1.0, 0.97, 0.90]},
            {"name": "Rim_Appetite", "type": "AREA", "location": [0.0, -2.5, 2.0], "energy": 80, "size": 1.5, "color": [1.0, 0.93, 0.80]},
        ],
        "world_color": [0.06, 0.05, 0.04],
        "world_strength": 0.25,
    },
}


def setup_lighting(rig_name: str, shadow_catcher: bool = True):
    """Set up a professional lighting rig. Clears existing lights first."""
    rig = LIGHTING_RIGS.get(rig_name)
    if not rig:
        print(f"Unknown lighting rig: {rig_name}")
        return {"error": f"Unknown rig: {rig_name}"}
    
    # Build Python code that creates the full rig
    lights_code = ""
    for light in rig["lights"]:
        loc = light["location"]
        col = light["color"]
        lights_code += f"""
light_data = bpy.data.lights.new(name="{light['name']}", type='{light['type']}')
light_data.energy = {light['energy']}
light_data.color = ({col[0]}, {col[1]}, {col[2]})
if hasattr(light_data, 'size'):
    light_data.size = {light['size']}
light_obj = bpy.data.objects.new(name="{light['name']}", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.location = ({loc[0]}, {loc[1]}, {loc[2]})
import mathutils
direction = mathutils.Vector((0,0,0)) - mathutils.Vector(({loc[0]}, {loc[1]}, {loc[2]}))
rot = direction.to_track_quat('-Z', 'Y').to_euler()
light_obj.rotation_euler = rot
"""

    wc = rig["world_color"]
    shadow_code = ""
    if shadow_catcher:
        shadow_code = """
# Shadow catcher plane
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.01))
catcher = bpy.context.active_object
catcher.name = "Shadow_Catcher"
catcher.is_shadow_catcher = True
"""

    code = f"""
import bpy
import mathutils

# Delete existing lights
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

# Delete existing shadow catchers
for obj in list(bpy.data.objects):
    if obj.name.startswith("Shadow_Catcher"):
        bpy.data.objects.remove(obj, do_unlink=True)

{lights_code}

# World/environment
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = ({wc[0]}, {wc[1]}, {wc[2]}, 1.0)
    bg.inputs['Strength'].default_value = {rig['world_strength']}

{shadow_code}

__result__ = {{"status": "ok", "rig": "{rig_name}", "lights": {len(rig['lights'])}, "description": "{rig['description']}"}}
"""
    return run_python(code)


# ═══════════════════════════════════════════════════════════════════════════════
# CAMERA ANIMATION SYSTEMS
# ═══════════════════════════════════════════════════════════════════════════════

def setup_turntable_camera(
    target_object: str,
    frames: int = 240,
    camera_distance: float = 4.0,
    camera_height: float = 1.2,
    focal_length: float = 50.0,
    f_stop: float = 2.8,
    use_dof: bool = True,
    fps: int = 24,
):
    """Create a professional turntable camera animation orbiting the target object."""
    code = f"""
import bpy
import math

scene = bpy.context.scene

# Delete existing cameras and empties named Turntable_*
for obj in list(bpy.data.objects):
    if obj.name.startswith("Turntable_") or (obj.type == 'CAMERA' and obj.name.startswith("Product_Camera")):
        bpy.data.objects.remove(obj, do_unlink=True)

# Get target object center
target = bpy.data.objects.get("{target_object}")
if not target:
    __result__ = {{"error": "Object '{target_object}' not found"}}
else:
    target_center = target.location.copy()
    
    # Create orbit empty at target center
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=target_center)
    orbit_empty = bpy.context.active_object
    orbit_empty.name = "Turntable_Orbit"
    
    # Create camera
    cam_data = bpy.data.cameras.new("Product_Camera_Data")
    cam_data.lens = {focal_length}
    cam_data.sensor_width = 36.0
    
    # Depth of Field
    cam_data.dof.use_dof = {use_dof}
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = {f_stop}
    
    cam_obj = bpy.data.objects.new("Product_Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.location = (target_center.x + {camera_distance}, target_center.y, target_center.z + {camera_height})
    
    # Parent camera to orbit empty
    cam_obj.parent = orbit_empty
    
    # Track-to constraint so camera always points at product
    track = cam_obj.constraints.new('TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    
    # Set as active camera
    scene.camera = cam_obj
    
    # Animate orbit: 360° rotation over frame range
    scene.frame_start = 1
    scene.frame_end = {frames}
    scene.render.fps = {fps}
    
    orbit_empty.rotation_euler = (0, 0, 0)
    orbit_empty.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    
    orbit_empty.rotation_euler = (0, 0, math.radians(360))
    orbit_empty.keyframe_insert(data_path="rotation_euler", index=2, frame={frames})
    
    # Set LINEAR interpolation for constant speed
    if orbit_empty.animation_data and orbit_empty.animation_data.action:
        for fc in orbit_empty.animation_data.action.fcurves:
            if "rotation_euler" in fc.data_path:
                for kf in fc.keyframe_points:
                    kf.interpolation = 'LINEAR'
    
    __result__ = {{
        "status": "ok",
        "camera": "Product_Camera",
        "orbit": "Turntable_Orbit",
        "frames": {frames},
        "duration_sec": {frames} / {fps},
        "focal_length": {focal_length},
        "f_stop": {f_stop},
        "distance": {camera_distance}
    }}
"""
    return run_python(code)


def setup_hero_reveal_camera(
    target_object: str,
    frames: int = 180,
    start_distance: float = 8.0,
    end_distance: float = 3.5,
    start_height: float = 0.5,
    end_height: float = 1.5,
    start_focal: float = 35.0,
    end_focal: float = 85.0,
    f_stop: float = 2.0,
    fps: int = 24,
):
    """Create a cinematic hero reveal: dolly in + zoom + rise for dramatic product entrance."""
    code = f"""
import bpy
import math

scene = bpy.context.scene

# Cleanup
for obj in list(bpy.data.objects):
    if obj.name.startswith("Hero_") or (obj.type == 'CAMERA' and obj.name.startswith("Product_Camera")):
        bpy.data.objects.remove(obj, do_unlink=True)

target = bpy.data.objects.get("{target_object}")
if not target:
    __result__ = {{"error": "Object '{target_object}' not found"}}
else:
    tc = target.location.copy()
    
    # Camera
    cam_data = bpy.data.cameras.new("Hero_Camera_Data")
    cam_data.lens = {start_focal}
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = {f_stop}
    
    cam_obj = bpy.data.objects.new("Product_Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    scene.camera = cam_obj
    
    # Track to target
    track = cam_obj.constraints.new('TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    
    # Frame range
    scene.frame_start = 1
    scene.frame_end = {frames}
    scene.render.fps = {fps}
    
    # Keyframe 1: far away, low, wide
    scene.frame_set(1)
    cam_obj.location = (tc.x + {start_distance}, tc.y, tc.z + {start_height})
    cam_obj.keyframe_insert(data_path="location", frame=1)
    cam_data.lens = {start_focal}
    cam_data.keyframe_insert(data_path="lens", frame=1)
    
    # Keyframe end: close, higher, telephoto
    cam_obj.location = (tc.x + {end_distance}, tc.y + 1.0, tc.z + {end_height})
    cam_obj.keyframe_insert(data_path="location", frame={frames})
    cam_data.lens = {end_focal}
    cam_data.keyframe_insert(data_path="lens", frame={frames})
    
    # Set BEZIER easing for cinematic feel (ease-out approach)
    if cam_obj.animation_data and cam_obj.animation_data.action:
        for fc in cam_obj.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'BEZIER'
                kf.easing = 'EASE_OUT'
    
    if cam_data.animation_data and cam_data.animation_data.action:
        for fc in cam_data.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'BEZIER'
                kf.easing = 'EASE_OUT'
    
    __result__ = {{
        "status": "ok",
        "camera": "Product_Camera",
        "frames": {frames},
        "duration_sec": {frames} / {fps},
        "start_focal": {start_focal},
        "end_focal": {end_focal},
        "motion": "dolly_in + zoom + rise"
    }}
"""
    return run_python(code)


def setup_orbit_detail_camera(
    target_object: str,
    frames: int = 300,
    orbit_angle: float = 120.0,
    start_distance: float = 5.0,
    end_distance: float = 2.0,
    height: float = 1.0,
    focal_length: float = 85.0,
    f_stop: float = 1.8,
    fps: int = 24,
):
    """Slow partial orbit with dolly-in for detail inspection. Premium quality."""
    code = f"""
import bpy
import math

scene = bpy.context.scene

for obj in list(bpy.data.objects):
    if obj.name.startswith("Detail_") or (obj.type == 'CAMERA' and obj.name.startswith("Product_Camera")):
        bpy.data.objects.remove(obj, do_unlink=True)

target = bpy.data.objects.get("{target_object}")
if not target:
    __result__ = {{"error": "Object '{target_object}' not found"}}
else:
    tc = target.location.copy()
    
    # Orbit empty
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=tc)
    orbit = bpy.context.active_object
    orbit.name = "Detail_Orbit"
    
    # Camera
    cam_data = bpy.data.cameras.new("Detail_Camera_Data")
    cam_data.lens = {focal_length}
    cam_data.dof.use_dof = True
    cam_data.dof.focus_object = target
    cam_data.dof.aperture_fstop = {f_stop}
    
    cam_obj = bpy.data.objects.new("Product_Camera", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.parent = orbit
    scene.camera = cam_obj
    
    track = cam_obj.constraints.new('TRACK_TO')
    track.target = target
    track.track_axis = 'TRACK_NEGATIVE_Z'
    track.up_axis = 'UP_Y'
    
    scene.frame_start = 1
    scene.frame_end = {frames}
    scene.render.fps = {fps}
    
    # Start: far, angle 0
    cam_obj.location = (tc.x + {start_distance}, tc.y, tc.z + {height})
    cam_obj.keyframe_insert(data_path="location", frame=1)
    orbit.rotation_euler = (0, 0, 0)
    orbit.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    
    # End: close, orbited
    cam_obj.location = (tc.x + {end_distance}, tc.y, tc.z + {height})
    cam_obj.keyframe_insert(data_path="location", frame={frames})
    orbit.rotation_euler = (0, 0, math.radians({orbit_angle}))
    orbit.keyframe_insert(data_path="rotation_euler", index=2, frame={frames})
    
    # Smooth easing
    for obj in [cam_obj, orbit]:
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kf in fc.keyframe_points:
                    kf.interpolation = 'BEZIER'
                    kf.easing = 'EASE_IN_OUT'
    
    __result__ = {{
        "status": "ok", "camera": "Product_Camera", "frames": {frames},
        "orbit_angle": {orbit_angle}, "motion": "partial_orbit + dolly_in"
    }}
"""
    return run_python(code)


# ═══════════════════════════════════════════════════════════════════════════════
# RENDER PIPELINE PRESETS
# ═══════════════════════════════════════════════════════════════════════════════

def configure_render(
    quality: str = "balanced",
    resolution: str = "1080p",
    transparent_bg: bool = True,
    output_path: str = "/tmp/product_render/frame_####",
    output_format: str = "PNG",
):
    """Configure render settings for professional product output."""
    
    quality_map = {
        "fast":     {"samples": 128, "bounces": 6, "denoise_thresh": 0.1},
        "balanced": {"samples": 256, "bounces": 8, "denoise_thresh": 0.05},
        "premium":  {"samples": 512, "bounces": 12, "denoise_thresh": 0.01},
    }
    
    res_map = {
        "720p":       (1280, 720),
        "1080p":      (1920, 1080),
        "4k":         (3840, 2160),
        "square_1080":(1080, 1080),
        "vertical":   (1080, 1920),
        "instagram":  (1080, 1350),
    }
    
    q = quality_map.get(quality, quality_map["balanced"])
    w, h = res_map.get(resolution, res_map["1080p"])
    
    code = f"""
import bpy

scene = bpy.context.scene

# Engine: Cycles
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'

# Sampling
scene.cycles.samples = {q['samples']}
scene.cycles.preview_samples = 64
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = {q['denoise_thresh']}

# Denoising
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'

# Light bounces
scene.cycles.max_bounces = {q['bounces']}
scene.cycles.diffuse_bounces = 3
scene.cycles.glossy_bounces = 4
scene.cycles.transmission_bounces = 8
scene.cycles.volume_bounces = 0
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False

# Performance
scene.cycles.use_persistent_data = True

# Resolution
scene.render.resolution_x = {w}
scene.render.resolution_y = {h}
scene.render.resolution_percentage = 100

# Film
scene.render.film_transparent = {transparent_bg}

# Color management
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Punchy'
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

# Output
scene.render.image_settings.file_format = '{output_format}'
scene.render.image_settings.color_mode = 'RGBA'
if '{output_format}' == 'PNG':
    scene.render.image_settings.compression = 15
scene.render.filepath = "{output_path}"

__result__ = {{
    "status": "ok",
    "engine": "CYCLES",
    "samples": {q['samples']},
    "resolution": "{resolution} ({w}x{h})",
    "quality": "{quality}",
    "transparent": {transparent_bg},
    "output": "{output_path}"
}}
"""
    return run_python(code)


def setup_compositor_product(bloom: bool = True, vignette: bool = True):
    """Set up compositor for professional product post-processing (bloom + vignette)."""
    code = f"""
import bpy

scene = bpy.context.scene
scene.use_nodes = True
tree = scene.node_tree

# Clear existing nodes
for node in list(tree.nodes):
    tree.nodes.remove(node)

# Create nodes
render_node = tree.nodes.new('CompositorNodeRLayers')
render_node.location = (0, 0)

composite = tree.nodes.new('CompositorNodeComposite')
composite.location = (800, 0)

viewer = tree.nodes.new('CompositorNodeViewer')
viewer.location = (800, -200)

last_output = render_node.outputs['Image']
x_pos = 200

bloom_setup = {bloom}
vignette_setup = {vignette}

if bloom_setup:
    # Glare node for bloom
    glare = tree.nodes.new('CompositorNodeGlare')
    glare.location = (x_pos, 0)
    glare.glare_type = 'FOG_GLOW'
    glare.threshold = 0.8
    glare.quality = 'HIGH'
    glare.mix = -0.7  # subtle
    glare.size = 6
    
    tree.links.new(last_output, glare.inputs[0])
    last_output = glare.outputs[0]
    x_pos += 200

if vignette_setup:
    # Lens distortion for vignette
    lens = tree.nodes.new('CompositorNodeLensdist')
    lens.location = (x_pos, 0)
    lens.inputs['Distort'].default_value = 0.0
    lens.inputs['Dispersion'].default_value = 0.0
    # Note: vignette is via Jitter=0 + compositing mix
    # Alternative: use ellipse mask + multiply
    
    # Ellipse Mask approach
    mask = tree.nodes.new('CompositorNodeEllipseMask')
    mask.location = (x_pos, -200)
    mask.width = 0.85
    mask.height = 0.85
    
    blur = tree.nodes.new('CompositorNodeBlur')
    blur.location = (x_pos + 200, -200)
    blur.size_x = 200
    blur.size_y = 200
    blur.use_relative = True
    blur.factor_x = 1.0
    blur.factor_y = 1.0
    
    mix = tree.nodes.new('CompositorNodeMixRGB')
    mix.location = (x_pos + 400, 0)
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 0.3  # vignette strength
    
    tree.links.new(mask.outputs[0], blur.inputs[0])
    tree.links.new(last_output, mix.inputs[1])
    tree.links.new(blur.outputs[0], mix.inputs[2])
    last_output = mix.outputs[0]
    x_pos += 600

# Connect to output
tree.links.new(last_output, composite.inputs[0])
tree.links.new(last_output, viewer.inputs[0])

__result__ = {{"status": "ok", "bloom": bloom_setup, "vignette": vignette_setup}}
"""
    return run_python(code)


# ═══════════════════════════════════════════════════════════════════════════════
# FULL RECIPE: LUXURY TURNTABLE
# ═══════════════════════════════════════════════════════════════════════════════

def recipe_luxury_turntable(
    object_name: str,
    material_preset: str = None,
    lighting_rig: str = "product_studio",
    frames: int = 240,
    camera_distance: float = 4.0,
    focal_length: float = 50.0,
    quality: str = "balanced",
    resolution: str = "1080p",
    output_dir: str = "/tmp/product_turntable",
):
    """
    FULL RECIPE: Professional luxury turntable animation.
    Sets up materials → lighting → camera → render → compositor in one call.
    """
    print(f"═══ Luxury Turntable Recipe for '{object_name}' ═══")
    results = {}
    
    # 1. Material (optional)
    if material_preset:
        print(f"  [1/5] Applying material: {material_preset}")
        results["material"] = apply_material(object_name, material_preset)
    else:
        print(f"  [1/5] Skipping material (using existing)")
    
    # 2. Lighting
    print(f"  [2/5] Setting up lighting: {lighting_rig}")
    results["lighting"] = setup_lighting(lighting_rig)
    
    # 3. Camera
    print(f"  [3/5] Setting up turntable camera ({frames} frames)")
    results["camera"] = setup_turntable_camera(
        target_object=object_name,
        frames=frames,
        camera_distance=camera_distance,
        focal_length=focal_length,
    )
    
    # 4. Render settings
    print(f"  [4/5] Configuring render: {quality} @ {resolution}")
    results["render"] = configure_render(
        quality=quality,
        resolution=resolution,
        output_path=f"{output_dir}/frame_####",
    )
    
    # 5. Compositor
    print(f"  [5/5] Setting up compositor (bloom + vignette)")
    results["compositor"] = setup_compositor_product(bloom=True, vignette=True)
    
    print(f"═══ Recipe complete! Ready to render. ═══")
    print(f"    Run: blender_render(type='animation', output_path='{output_dir}/frame_####')")
    
    return results


def recipe_hero_reveal(
    object_name: str,
    material_preset: str = None,
    lighting_rig: str = "product_studio",
    frames: int = 180,
    quality: str = "balanced",
    resolution: str = "1080p",
    output_dir: str = "/tmp/product_hero",
):
    """
    FULL RECIPE: Cinematic hero reveal.
    Camera dollies in + zooms + rises for dramatic entrance.
    """
    print(f"═══ Hero Reveal Recipe for '{object_name}' ═══")
    results = {}
    
    if material_preset:
        print(f"  [1/5] Material: {material_preset}")
        results["material"] = apply_material(object_name, material_preset)
    
    print(f"  [2/5] Lighting: {lighting_rig}")
    results["lighting"] = setup_lighting(lighting_rig)
    
    print(f"  [3/5] Hero camera ({frames} frames)")
    results["camera"] = setup_hero_reveal_camera(
        target_object=object_name, frames=frames,
    )
    
    print(f"  [4/5] Render: {quality} @ {resolution}")
    results["render"] = configure_render(
        quality=quality, resolution=resolution,
        output_path=f"{output_dir}/frame_####",
    )
    
    print(f"  [5/5] Compositor")
    results["compositor"] = setup_compositor_product(bloom=True, vignette=False)
    
    print(f"═══ Recipe complete! Ready to render. ═══")
    return results


def recipe_detail_inspection(
    object_name: str,
    material_preset: str = None,
    lighting_rig: str = "jewelry",
    frames: int = 300,
    quality: str = "premium",
    resolution: str = "4k",
    output_dir: str = "/tmp/product_detail",
):
    """
    FULL RECIPE: Slow orbit detail inspection. 
    Partial orbit with dolly-in, shallow DOF, premium quality.
    """
    print(f"═══ Detail Inspection Recipe for '{object_name}' ═══")
    results = {}
    
    if material_preset:
        results["material"] = apply_material(object_name, material_preset)
    
    results["lighting"] = setup_lighting(lighting_rig)
    results["camera"] = setup_orbit_detail_camera(
        target_object=object_name, frames=frames,
    )
    results["render"] = configure_render(
        quality=quality, resolution=resolution,
        output_path=f"{output_dir}/frame_####",
    )
    results["compositor"] = setup_compositor_product(bloom=True, vignette=True)
    
    return results


def recipe_ecommerce_360(
    object_name: str,
    material_preset: str = None,
    frames: int = 72,
    output_dir: str = "/tmp/product_360",
):
    """
    FULL RECIPE: E-commerce 360° spin.
    72 frames = one image per 5° for web 360 viewers.
    White background, clean studio lighting, fast render.
    """
    print(f"═══ E-commerce 360° Recipe for '{object_name}' ═══")
    results = {}
    
    if material_preset:
        results["material"] = apply_material(object_name, material_preset)
    
    results["lighting"] = setup_lighting("product_studio")
    results["camera"] = setup_turntable_camera(
        target_object=object_name,
        frames=frames,
        camera_distance=3.5,
        focal_length=50.0,
        use_dof=False,  # everything sharp for ecommerce
    )
    results["render"] = configure_render(
        quality="fast",
        resolution="square_1080",
        transparent_bg=True,
        output_path=f"{output_dir}/spin_####",
    )
    
    return results


def recipe_social_media_reel(
    object_name: str,
    material_preset: str = None,
    lighting_rig: str = "cosmetics",
    frames: int = 150,
    output_dir: str = "/tmp/product_reel",
):
    """
    FULL RECIPE: Social media reel (vertical 1080x1920).
    Fast hero reveal, punchy look, optimized for TikTok/Reels.
    """
    print(f"═══ Social Media Reel Recipe for '{object_name}' ═══")
    results = {}
    
    if material_preset:
        results["material"] = apply_material(object_name, material_preset)
    
    results["lighting"] = setup_lighting(lighting_rig)
    results["camera"] = setup_hero_reveal_camera(
        target_object=object_name,
        frames=frames,
        start_distance=6.0,
        end_distance=3.0,
        start_focal=35.0,
        end_focal=65.0,
        f_stop=2.8,
    )
    results["render"] = configure_render(
        quality="balanced",
        resolution="vertical",
        output_path=f"{output_dir}/reel_####",
    )
    results["compositor"] = setup_compositor_product(bloom=True, vignette=True)
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY: Add surface imperfections for realism
# ═══════════════════════════════════════════════════════════════════════════════

def add_imperfections(object_name: str, fingerprints: bool = True, dust: bool = True, scratches: bool = False):
    """Add subtle surface imperfections to a material for photorealism."""
    code = f"""
import bpy

obj = bpy.data.objects.get("{object_name}")
if not obj or not obj.data.materials:
    __result__ = {{"error": "Object '{object_name}' not found or has no materials"}}
else:
    mat = obj.data.materials[0]
    tree = mat.node_tree
    bsdf = tree.nodes.get("Principled BSDF")
    if not bsdf:
        __result__ = {{"error": "No Principled BSDF found"}}
    else:
        base_roughness = bsdf.inputs['Roughness'].default_value
        effects = []
        
        # Texture coordinate
        tex_coord = tree.nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-800, 0)
        
        last_roughness = None
        
        if {fingerprints}:
            # Fingerprint: high-frequency noise
            fp_noise = tree.nodes.new('ShaderNodeTexNoise')
            fp_noise.location = (-600, 100)
            fp_noise.inputs['Scale'].default_value = 800.0
            fp_noise.inputs['Detail'].default_value = 8.0
            fp_noise.inputs['Roughness'].default_value = 0.7
            
            fp_ramp = tree.nodes.new('ShaderNodeValToRGB')
            fp_ramp.location = (-400, 100)
            fp_ramp.color_ramp.elements[0].position = 0.45
            fp_ramp.color_ramp.elements[1].position = 0.55
            
            fp_mix = tree.nodes.new('ShaderNodeMath')
            fp_mix.location = (-200, 100)
            fp_mix.operation = 'ADD'
            fp_mix.inputs[0].default_value = base_roughness
            # Scale the fingerprint effect to be subtle
            fp_scale = tree.nodes.new('ShaderNodeMath')
            fp_scale.location = (-300, 100)
            fp_scale.operation = 'MULTIPLY'
            fp_scale.inputs[1].default_value = 0.08  # subtle
            
            tree.links.new(tex_coord.outputs['Object'], fp_noise.inputs['Vector'])
            tree.links.new(fp_noise.outputs['Fac'], fp_ramp.inputs['Fac'])
            tree.links.new(fp_ramp.outputs['Color'], fp_scale.inputs[0])
            tree.links.new(fp_scale.outputs[0], fp_mix.inputs[1])
            
            last_roughness = fp_mix.outputs[0]
            effects.append("fingerprints")
        
        if {dust}:
            # Dust: larger scale noise
            dust_noise = tree.nodes.new('ShaderNodeTexNoise')
            dust_noise.location = (-600, -100)
            dust_noise.inputs['Scale'].default_value = 200.0
            dust_noise.inputs['Detail'].default_value = 4.0
            
            dust_scale = tree.nodes.new('ShaderNodeMath')
            dust_scale.location = (-400, -100)
            dust_scale.operation = 'MULTIPLY'
            dust_scale.inputs[1].default_value = 0.04
            
            tree.links.new(tex_coord.outputs['Object'], dust_noise.inputs['Vector'])
            tree.links.new(dust_noise.outputs['Fac'], dust_scale.inputs[0])
            
            if last_roughness:
                dust_add = tree.nodes.new('ShaderNodeMath')
                dust_add.location = (-100, 0)
                dust_add.operation = 'ADD'
                tree.links.new(last_roughness, dust_add.inputs[0])
                tree.links.new(dust_scale.outputs[0], dust_add.inputs[1])
                last_roughness = dust_add.outputs[0]
            else:
                dust_add = tree.nodes.new('ShaderNodeMath')
                dust_add.location = (-100, 0)
                dust_add.operation = 'ADD'
                dust_add.inputs[0].default_value = base_roughness
                tree.links.new(dust_scale.outputs[0], dust_add.inputs[1])
                last_roughness = dust_add.outputs[0]
            effects.append("dust")
        
        if last_roughness:
            tree.links.new(last_roughness, bsdf.inputs['Roughness'])
        
        __result__ = {{"status": "ok", "effects": effects, "object": "{object_name}"}}
"""
    return run_python(code)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY: Gradient background (infinite cyclorama look)
# ═══════════════════════════════════════════════════════════════════════════════

def setup_gradient_background(
    top_color: List[float] = [0.88, 0.90, 0.92],
    bottom_color: List[float] = [1.0, 1.0, 1.0],
    strength: float = 1.0,
):
    """Set up a gradient world background (white-to-gray cyclorama look)."""
    code = f"""
import bpy

world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree

# Clear
for node in list(tree.nodes):
    tree.nodes.remove(node)

# Build gradient
tex_coord = tree.nodes.new('ShaderNodeTexCoord')
tex_coord.location = (-600, 0)

mapping = tree.nodes.new('ShaderNodeMapping')
mapping.location = (-400, 0)

gradient = tree.nodes.new('ShaderNodeTexGradient')
gradient.location = (-200, 0)
gradient.gradient_type = 'LINEAR'

ramp = tree.nodes.new('ShaderNodeValToRGB')
ramp.location = (0, 0)
ramp.color_ramp.elements[0].color = ({bottom_color[0]}, {bottom_color[1]}, {bottom_color[2]}, 1.0)
ramp.color_ramp.elements[1].color = ({top_color[0]}, {top_color[1]}, {top_color[2]}, 1.0)

bg = tree.nodes.new('ShaderNodeBackground')
bg.location = (200, 0)
bg.inputs['Strength'].default_value = {strength}

output = tree.nodes.new('ShaderNodeOutputWorld')
output.location = (400, 0)

tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
tree.links.new(mapping.outputs['Vector'], gradient.inputs['Vector'])
tree.links.new(gradient.outputs['Color'], ramp.inputs['Fac'])
tree.links.new(ramp.outputs['Color'], bg.inputs['Color'])
tree.links.new(bg.outputs['Background'], output.inputs['Surface'])

__result__ = {{"status": "ok", "background": "gradient", "top": {top_color}, "bottom": {bottom_color}}}
"""
    return run_python(code)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

RECIPES = {
    "luxury_turntable": recipe_luxury_turntable,
    "hero_reveal": recipe_hero_reveal,
    "detail_inspection": recipe_detail_inspection,
    "ecommerce_360": recipe_ecommerce_360,
    "social_media_reel": recipe_social_media_reel,
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Product Animation Recipes")
    parser.add_argument("--recipe", choices=RECIPES.keys(), required=True)
    parser.add_argument("--object", required=True, help="Blender object name")
    parser.add_argument("--material", default=None, choices=MATERIAL_PRESETS.keys())
    parser.add_argument("--lighting", default="product_studio", choices=LIGHTING_RIGS.keys())
    parser.add_argument("--quality", default="balanced", choices=["fast", "balanced", "premium"])
    parser.add_argument("--resolution", default="1080p")
    parser.add_argument("--frames", type=int, default=None)
    parser.add_argument("--output", default="/tmp/product_render")
    parser.add_argument("--render", action="store_true", help="Also trigger render")
    args = parser.parse_args()
    
    kwargs = {
        "object_name": args.object,
        "material_preset": args.material,
        "lighting_rig": args.lighting,
        "quality": args.quality,
        "resolution": args.resolution,
        "output_dir": args.output,
    }
    if args.frames:
        kwargs["frames"] = args.frames
    
    # Filter kwargs that the recipe accepts
    import inspect
    sig = inspect.signature(RECIPES[args.recipe])
    valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters and v is not None}
    
    result = RECIPES[args.recipe](**valid_kwargs)
    print(json.dumps(result, indent=2, default=str))
    
    if args.render:
        print("\n═══ Starting render... ═══")
        render_result = send("render", {"type": "animation", "output_path": f"{args.output}/frame_####"})
        print(json.dumps(render_result, indent=2, default=str))
