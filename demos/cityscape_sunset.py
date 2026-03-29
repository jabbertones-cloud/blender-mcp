#!/usr/bin/env python3
"""
OpenClaw Blender MCP — Animated Cityscape with Sunset over Water
=================================================================
The grand finale demo: procedural city skyline, sunset sky, animated
ocean, volumetric atmosphere, camera dolly, and cinematic compositing.
All built entirely via MCP commands.

Blender 5.1 compatible. Uses EEVEE with raytracing for fast cinematic output.
AgX color management with "Very High Contrast" look.
Procedural window textures with correct Brick Fac inversion.

Run: python3 demos/cityscape_sunset.py
"""

import json
import socket
import sys
import time
import math
import random

HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 60.0

_id = 0


def send(command, params=None):
    global _id
    _id += 1
    payload = {"id": str(_id), "command": command, "params": params or {}}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    sock.connect((HOST, PORT))
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
            return data.get("result", data)
        except json.JSONDecodeError:
            continue
    sock.close()
    return json.loads(b"".join(chunks).decode("utf-8"))


def step(msg, command, params=None):
    print(f"  → {msg}...", end=" ", flush=True)
    result = send(command, params)
    if isinstance(result, dict) and "error" in result:
        print(f"⚠ {result['error']}")
    else:
        print("✓")
    return result


def run_py(msg, code):
    print(f"  → {msg}...", end=" ", flush=True)
    result = send("execute_python", {"code": code})
    if isinstance(result, dict) and "error" in result:
        print(f"⚠ {result['error']}")
    else:
        print("✓")
    return result


def main():
    t0 = time.time()
    random.seed(42)

    print()
    print("▓" * 72)
    print("▓  OpenClaw Blender MCP — Sunset Cityscape over Water")
    print("▓  The Grand Finale (v11 — All Fixes Baked In)")
    print("▓" * 72)
    print()

    # ── 1. SCENE SETUP + RENDER ENGINE ──────────────────────────────────
    print("[1/13] Scene Setup + EEVEE Raytracing + AgX Color")
    run_py("Clear scene and configure EEVEE with AgX", """
import bpy
# Clear everything
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for img in list(bpy.data.images):
    bpy.data.images.remove(img)

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 240
scene.render.fps = 24

# --- EEVEE with raytracing ---
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

eevee = scene.eevee
# Raytracing (replaces old SSR in 5.1)
try:
    eevee.use_raytracing = True
    eevee.ray_tracing_method = 'SCREEN'
except:
    pass
# Shadows
try:
    eevee.shadow_ray_count = 2
    eevee.shadow_step_count = 6
except:
    pass
# Volumetrics
try:
    eevee.volumetric_start = 0.1
    eevee.volumetric_end = 200.0
    eevee.volumetric_tile_size = '8'
    eevee.volumetric_samples = 128
    eevee.use_volumetric_lights = True
    eevee.use_volumetric_shadows = True
except:
    pass
# Bloom
try:
    eevee.use_bloom = True
    eevee.bloom_intensity = 0.12
    eevee.bloom_radius = 5.0
    eevee.bloom_threshold = 0.8
except:
    pass
# Ambient occlusion
try:
    eevee.use_gtao = True
    eevee.gtao_distance = 0.5
except:
    pass

# Render samples
scene.eevee.taa_render_samples = 128
scene.eevee.taa_samples = 32

# --- AgX Color Management ---
scene.display_settings.display_device = 'sRGB'
scene.view_settings.view_transform = 'AgX'
# IMPORTANT: In Blender 5.x the look must be prefixed with "AgX - "
try:
    scene.view_settings.look = 'AgX - Very High Contrast'
except:
    try:
        scene.view_settings.look = 'Very High Contrast'
    except:
        pass
scene.view_settings.exposure = 0.0
scene.view_settings.gamma = 1.0

# PNG output
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'
scene.render.image_settings.color_mode = 'RGBA'

__result__ = "EEVEE + AgX configured"
""")

    # ── 2. SUNSET SKY ─────────────────────────────────────────────────
    print("\n[2/13] Procedural Sunset Sky")
    run_py("Build sunset gradient world shader", """
import bpy
world = bpy.data.worlds["World"]
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
nodes.clear()

# Texture coordinate -> separate Z for height
coord = nodes.new(type="ShaderNodeTexCoord")
coord.location = (-800, 0)

sep = nodes.new(type="ShaderNodeSeparateXYZ")
sep.location = (-600, 0)
links.new(coord.outputs["Generated"], sep.inputs["Vector"])

# Map Z to color ramp for sunset gradient
ramp = nodes.new(type="ShaderNodeValToRGB")
ramp.location = (-300, 0)
cr = ramp.color_ramp
# Deep purple at bottom
cr.elements[0].position = 0.0
cr.elements[0].color = (0.12, 0.04, 0.2, 1.0)
# Warm orange at horizon
e1 = cr.elements.new(0.35)
e1.color = (1.0, 0.45, 0.12, 1.0)
# Golden yellow at sun position
e2 = cr.elements.new(0.45)
e2.color = (1.0, 0.8, 0.3, 1.0)
# Pale sky
e3 = cr.elements.new(0.6)
e3.color = (0.5, 0.65, 0.85, 1.0)
# Dark blue zenith
cr.elements[1].position = 1.0
cr.elements[1].color = (0.05, 0.08, 0.18, 1.0)

links.new(sep.outputs["Z"], ramp.inputs["Fac"])

bg = nodes.new(type="ShaderNodeBackground")
bg.location = (0, 0)
bg.inputs["Strength"].default_value = 4.0
links.new(ramp.outputs["Color"], bg.inputs["Color"])

output = nodes.new(type="ShaderNodeOutputWorld")
output.location = (200, 0)
links.new(bg.outputs["Background"], output.inputs["Surface"])

__result__ = "sunset sky built"
""")

    # ── 3. SUN LIGHT ──────────────────────────────────────────────────
    print("\n[3/13] Sunset Sun Light")
    run_py("Add low-angle sunset sun", """
import bpy, math
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.name = "SunsetSun"
sun.data.energy = 8.0
sun.data.color = (1.0, 0.65, 0.35)
sun.data.angle = 0.05
# Low angle for sunset (15 degrees above horizon)
sun.rotation_euler = (math.radians(75), math.radians(15), math.radians(-30))
try:
    sun.data.shadow_cascade_count = 4
except:
    pass

# Add warm fill light from front
bpy.ops.object.light_add(type="AREA", location=(0, -10, 8))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = 200
fill.data.color = (1.0, 0.85, 0.6)
fill.data.size = 15
fill.rotation_euler = (math.radians(45), 0, 0)

__result__ = "sunset sun + fill light added"
""")

    # ── 4. WATER PLANE WITH OCEAN ─────────────────────────────────────
    print("\n[4/13] Animated Ocean Water")
    run_py("Create ocean with water material", """
import bpy
bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 0, 0))
obj = bpy.context.active_object
obj.name = "Ocean"

# Add ocean modifier
ocean = obj.modifiers.new(name="OceanWaves", type="OCEAN")
ocean.geometry_mode = "GENERATE"
ocean.repeat_x = 2
ocean.repeat_y = 2
ocean.resolution = 8
ocean.spatial_size = 50
ocean.wave_scale = 0.5
ocean.choppiness = 0.8
ocean.time = 0.0
# Animate ocean time
ocean.keyframe_insert(data_path="time", frame=1)
ocean.time = 10.0
ocean.keyframe_insert(data_path="time", frame=240)

# Water material - deep blue with reflections
mat = bpy.data.materials.new("OceanWater")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.02, 0.12, 0.25, 1.0)
bsdf.inputs["Roughness"].default_value = 0.03
bsdf.inputs["IOR"].default_value = 1.33
bsdf.inputs["Metallic"].default_value = 0.0
try:
    bsdf.inputs["Transmission Weight"].default_value = 0.85
except:
    try:
        bsdf.inputs["Transmission"].default_value = 0.85
    except:
        pass
try:
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
except:
    pass
obj.data.materials.append(mat)
__result__ = "ocean created"
""")

    # ── 5. PROCEDURAL CITY BUILDINGS WITH WINDOW TEXTURES ─────────────
    print("\n[5/13] Procedural City Skyline with Window Textures")
    run_py("Generate buildings with procedural window materials", """
import bpy, random, math
random.seed(42)

# --- Create 3 procedural window materials ---
# KEY LEARNINGS from research:
# 1. Brick Texture Fac output is INVERTED (1.0 = mortar, 0.0 = brick face)
# 2. Must invert Fac with Math(SUBTRACT: 1.0 - Fac) before using
# 3. Use Object coordinates (not Generated) to handle non-uniform scale
# 4. Match Noise scale to Brick scale exactly
# 5. ShaderNodeValToRGB (NOT ShaderNodeValRamp) for ColorRamp

def create_window_material(name, wall_color, window_color, emission_color, emission_strength, brick_scale=3.0, mortar_size=0.03):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Texture Coordinate (Object) -> Brick Texture
    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-900, 0)

    brick = nodes.new("ShaderNodeTexBrick")
    brick.location = (-600, 0)
    brick.inputs["Scale"].default_value = brick_scale
    brick.inputs["Mortar Size"].default_value = mortar_size
    brick.offset = 0.5
    brick.squash = 1.0
    try:
        brick.inputs["Color1"].default_value = (0.4, 0.4, 0.4, 1)
        brick.inputs["Color2"].default_value = (0.35, 0.35, 0.35, 1)
        brick.inputs["Mortar"].default_value = (0.1, 0.1, 0.1, 1)
    except:
        pass

    # Connect Object coords to Brick
    links.new(tex_coord.outputs["Object"], brick.inputs["Vector"])

    # INVERT Fac: Math(SUBTRACT) -> 1.0 - Fac
    invert = nodes.new("ShaderNodeMath")
    invert.location = (-350, 0)
    invert.operation = "SUBTRACT"
    invert.inputs[0].default_value = 1.0
    links.new(brick.outputs["Fac"], invert.inputs[1])

    # Noise texture (same scale as brick, Detail=0 for clean)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-600, -200)
    noise.inputs["Scale"].default_value = brick_scale
    noise.inputs["Detail"].default_value = 0.0
    links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])

    # Multiply inverted Fac * Noise for window randomness
    multiply = nodes.new("ShaderNodeMath")
    multiply.location = (-150, 0)
    multiply.operation = "MULTIPLY"
    links.new(invert.outputs["Value"], multiply.inputs[0])
    links.new(noise.outputs["Fac"], multiply.inputs[1])

    # ColorRamp to threshold lit vs dark windows
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.location = (50, 0)
    ramp.color_ramp.interpolation = "LINEAR"
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 0.6
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(multiply.outputs["Value"], ramp.inputs["Fac"])

    # Wall BSDF
    wall_bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    wall_bsdf.location = (50, -300)
    wall_bsdf.inputs["Base Color"].default_value = wall_color
    wall_bsdf.inputs["Roughness"].default_value = 0.85
    wall_bsdf.inputs["Metallic"].default_value = 0.0

    # Window BSDF (dark reflective glass + emission for lit windows)
    win_bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    win_bsdf.location = (50, -600)
    win_bsdf.inputs["Base Color"].default_value = window_color
    win_bsdf.inputs["Roughness"].default_value = 0.05
    win_bsdf.inputs["Metallic"].default_value = 0.3
    win_bsdf.inputs["Emission Color"].default_value = emission_color
    win_bsdf.inputs["Emission Strength"].default_value = emission_strength

    # Mix Shader: wall vs window
    mix = nodes.new("ShaderNodeMixShader")
    mix.location = (350, 0)
    links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    links.new(wall_bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(win_bsdf.outputs["BSDF"], mix.inputs[2])

    # Output
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (550, 0)
    links.new(mix.outputs["Shader"], output.inputs["Surface"])

    return mat

# Create 3 building material variants
mat_glass = create_window_material(
    "Bldg_Glass",
    wall_color=(0.12, 0.15, 0.22, 1),     # Dark steel wall
    window_color=(0.08, 0.12, 0.2, 1),     # Dark blue glass
    emission_color=(0.9, 0.85, 0.6, 1),    # Warm yellow glow
    emission_strength=2.0,
    brick_scale=4.0, mortar_size=0.02
)
mat_concrete = create_window_material(
    "Bldg_Concrete",
    wall_color=(0.42, 0.40, 0.38, 1),      # Concrete grey
    window_color=(0.15, 0.18, 0.25, 1),    # Dark window
    emission_color=(1.0, 0.9, 0.65, 1),    # Bright warm
    emission_strength=1.5,
    brick_scale=3.0, mortar_size=0.04
)
mat_brick = create_window_material(
    "Bldg_Brick",
    wall_color=(0.50, 0.30, 0.20, 1),      # Warm brick
    window_color=(0.1, 0.12, 0.18, 1),     # Very dark window
    emission_color=(1.0, 0.85, 0.5, 1),    # Amber glow
    emission_strength=1.8,
    brick_scale=3.5, mortar_size=0.03
)
material_variants = [mat_glass, mat_concrete, mat_brick]

# --- Generate buildings ---
grid_x = 10
grid_z = 5
spacing_x = 8
spacing_z = 8
offset_y = 15

count = 0
for gx in range(grid_x):
    for gz in range(grid_z):
        if random.random() < 0.12:
            continue  # Empty lot

        height = random.uniform(5, 38)
        width = random.uniform(2.5, 5.5)
        depth = random.uniform(2.5, 5.5)

        x = (gx - grid_x / 2) * spacing_x + random.uniform(-1, 1)
        y = offset_y + gz * spacing_z + random.uniform(-1, 1)
        z = height / 2

        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z))
        bldg = bpy.context.active_object
        bldg.scale = (width / 2, depth / 2, height / 2)
        bldg.name = f"Bldg_{gx}_{gz}"

        # Apply scale immediately so Object coords work correctly
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        # Assign material variant
        variant = random.randint(0, 2)
        bldg.data.materials.append(material_variants[variant])

        count += 1

__result__ = f"{count} buildings with procedural window textures"
""")

    # ── 6. ATMOSPHERIC FOG VOLUME ─────────────────────────────────────
    print("\n[6/13] Atmospheric Sunset Fog")
    run_py("Create warm sunset fog volume", """
import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 25, 10))
obj = bpy.context.active_object
obj.name = "Atmosphere"
obj.scale = (100, 60, 25)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

mat = bpy.data.materials.new("SunsetFog")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()

vol = nodes.new(type="ShaderNodeVolumePrincipled")
vol.location = (0, 0)
vol.inputs["Color"].default_value = (1.0, 0.75, 0.5, 1.0)
vol.inputs["Density"].default_value = 0.003

# Noise for variation (very subtle)
noise = nodes.new(type="ShaderNodeTexNoise")
noise.location = (-200, 0)
noise.inputs["Scale"].default_value = 0.5
noise.inputs["Detail"].default_value = 3.0

math_n = nodes.new(type="ShaderNodeMath")
math_n.location = (-50, 0)
math_n.operation = "MULTIPLY"
math_n.inputs[1].default_value = 0.005
links.new(noise.outputs["Fac"], math_n.inputs[0])
links.new(math_n.outputs[0], vol.inputs["Density"])

output = nodes.new(type="ShaderNodeOutputMaterial")
output.location = (200, 0)
links.new(vol.outputs[0], output.inputs["Volume"])

obj.data.materials.append(mat)
__result__ = "fog applied"
""")

    # ── 7. SPOTLIGHT GOD RAYS ─────────────────────────────────────────
    print("\n[7/13] Volumetric God Rays Through Buildings")
    run_py("Add god ray spotlight behind city", """
import bpy, math
bpy.ops.object.light_add(type="SPOT", location=(0, 60, 8))
spot = bpy.context.active_object
spot.name = "GodRaySpot"
spot.data.energy = 3000
spot.data.color = (1.0, 0.7, 0.4)
spot.data.spot_size = 1.2
spot.data.shadow_soft_size = 1.0
spot.rotation_euler = (math.radians(90), 0, 0)
__result__ = "god ray spot added"
""")

    # ── 8. FOREGROUND ELEMENTS ────────────────────────────────────────
    print("\n[8/13] Foreground Elements — Lamp Posts & Railing")
    run_py("Create lamp posts, bulbs, and railing", """
import bpy, math

# Dark metal material for posts and rails
metal_mat = bpy.data.materials.new("DarkMetal")
metal_mat.use_nodes = True
bsdf = metal_mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.15, 0.15, 0.17, 1)
bsdf.inputs["Metallic"].default_value = 0.9
bsdf.inputs["Roughness"].default_value = 0.35

# Lamp glow material
glow_mat = bpy.data.materials.new("LampGlow")
glow_mat.use_nodes = True
bsdf_g = glow_mat.node_tree.nodes.get("Principled BSDF")
bsdf_g.inputs["Base Color"].default_value = (1, 0.9, 0.6, 1)
bsdf_g.inputs["Emission Color"].default_value = (1, 0.85, 0.5, 1)
bsdf_g.inputs["Emission Strength"].default_value = 15.0

# Lamp posts along waterfront
for i in range(5):
    x = -20 + i * 10
    # Post
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=4, location=(x, 5, 2))
    post = bpy.context.active_object
    post.name = f"LampPost_{i}"
    post.data.materials.append(metal_mat)
    # Bulb
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=(x, 5, 4.2))
    bulb = bpy.context.active_object
    bulb.name = f"LampBulb_{i}"
    bulb.data.materials.append(glow_mat)
    # Point light at each lamp
    bpy.ops.object.light_add(type="POINT", location=(x, 5, 4.2))
    lamp_light = bpy.context.active_object
    lamp_light.name = f"LampLight_{i}"
    lamp_light.data.energy = 50
    lamp_light.data.color = (1, 0.85, 0.5)

# Railing
for i in range(16):
    x = -30 + i * 4
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 4, 0.5))
    rail = bpy.context.active_object
    rail.name = f"Rail_{i}"
    rail.scale = (0.05, 0.05, 0.5)
    bpy.ops.object.transform_apply(scale=True)
    rail.data.materials.append(metal_mat)

# Horizontal rail bar
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4, 1.0))
bar = bpy.context.active_object
bar.name = "RailBar"
bar.scale = (30, 0.03, 0.03)
bpy.ops.object.transform_apply(scale=True)
bar.data.materials.append(metal_mat)

__result__ = "foreground elements created"
""")

    # ── 9. CAMERA ANIMATION ───────────────────────────────────────────
    print("\n[9/13] Camera Dolly Animation (240 frames)")
    run_py("Create smooth dolly camera path", """
import bpy, math

# Delete ALL existing cameras so we start fresh
for obj in list(bpy.data.objects):
    if obj.type == "CAMERA":
        bpy.data.objects.remove(obj, do_unlink=True)

# Create new camera
bpy.ops.object.camera_add()
cam = bpy.context.active_object
cam.name = "CityCamera"
bpy.context.scene.camera = cam

# Camera dolly: sweeps left-to-right along waterfront
# Camera at Y ~ -2 (near water edge), looking toward buildings at Y=15+
# X rotation ~83 deg = looking slightly up toward skyline horizon
keyframes = [
    (1,   (-35, -2, 4),  (math.radians(83), 0, math.radians(-15)), 28),
    (80,  (-10, -3, 5),  (math.radians(82), 0, math.radians(-3)),  32),
    (160, (10,  -3, 6),  (math.radians(81), 0, math.radians(3)),   35),
    (240, (35,  -2, 4),  (math.radians(83), 0, math.radians(15)),  28),
]

for frame, loc, rot, lens in keyframes:
    bpy.context.scene.frame_set(frame)
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.lens = lens
    cam.keyframe_insert(data_path="location")
    cam.keyframe_insert(data_path="rotation_euler")
    cam.data.keyframe_insert(data_path="lens")

# Smooth bezier interpolation (Blender 5.1: use fcurve_ensure_for_datablock)
if cam.animation_data and cam.animation_data.action:
    action = cam.animation_data.action
    for dp in ["location", "rotation_euler"]:
        for idx in range(3):
            fc = action.fcurve_ensure_for_datablock(cam, dp, index=idx)
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO"
                kp.handle_right_type = "AUTO"
    # Lens focal length fcurve
    fc_lens = action.fcurve_ensure_for_datablock(cam.data, "lens", index=0)
    for kp in fc_lens.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = "AUTO"
        kp.handle_right_type = "AUTO"

# Depth of field
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 35.0
cam.data.dof.aperture_fstop = 2.8
cam.data.dof.aperture_blades = 7

__result__ = "camera animated"
""")

    # ── 10. COMPOSITING ───────────────────────────────────────────────
    print("\n[10/13] Cinematic Compositing")
    run_py("Build compositor (glare + lens distortion)", """
import bpy
scene = bpy.context.scene
scene.use_nodes = True

# Blender 5.1: use compositing_node_group
ng = scene.compositing_node_group
if ng is None:
    ng = bpy.data.node_groups.new("Compositing Nodetree", "CompositorNodeTree")
    scene.compositing_node_group = ng
nodes = ng.nodes
links = ng.links
nodes.clear()

rl = nodes.new(type="CompositorNodeRLayers")
rl.location = (0, 0)

# Glare for bloom on lights and sun
glare = nodes.new(type="CompositorNodeGlare")
glare.location = (300, 0)
for inp in glare.inputs:
    if inp.name == "Threshold" and inp.type == "VALUE":
        inp.default_value = 0.6
    if inp.name == "Strength" and inp.type == "VALUE":
        inp.default_value = 0.4

# Lens distortion for chromatic aberration
lens = nodes.new(type="CompositorNodeLensdist")
lens.location = (600, 0)
# Blender 5.1: Jitter/Fit/Dispersion are socket inputs
for inp in lens.inputs:
    if inp.name == "Jitter" and inp.type == "VALUE":
        inp.default_value = 1.0
    if inp.name == "Dispersion" and inp.type == "VALUE":
        inp.default_value = 0.02

# Blender 5.1: CompositorNodeComposite removed; use NodeGroupOutput + Viewer
group_out = nodes.new(type="NodeGroupOutput")
group_out.location = (900, 0)
viewer = nodes.new(type="CompositorNodeViewer")
viewer.location = (900, -200)

links.new(rl.outputs["Image"], glare.inputs["Image"])
links.new(glare.outputs["Image"], lens.inputs["Image"])
links.new(lens.outputs["Image"], viewer.inputs["Image"])
try:
    links.new(lens.outputs["Image"], group_out.inputs[0])
except:
    pass

__result__ = "compositor built"
""")

    # ── 11. MOTION BLUR ───────────────────────────────────────────────
    print("\n[11/13] Motion Blur + Denoising")
    run_py("Enable motion blur", """
import bpy
scene = bpy.context.scene
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.35
__result__ = "motion blur enabled"
""")

    # ── 12. TITLE TEXT ────────────────────────────────────────────────
    print("\n[12/13] Title Overlay")
    step("Create title text", "text_object", {
        "action": "create", "text": "OpenClaw — Sunset City",
        "location": [0, -2, 12], "size": 2.0, "extrude": 0.1
    })
    run_py("Apply emissive glass material to title", """
import bpy
title = None
for obj in bpy.data.objects:
    if obj.type == 'FONT':
        title = obj
        break
if title:
    mat = bpy.data.materials.new("TitleGlass")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.9, 0.85, 0.7, 1)
    bsdf.inputs["Metallic"].default_value = 0.3
    bsdf.inputs["Roughness"].default_value = 0.1
    bsdf.inputs["Emission Color"].default_value = (1, 0.9, 0.6, 1)
    bsdf.inputs["Emission Strength"].default_value = 3.0
    title.data.materials.append(mat)
__result__ = "title styled"
""")

    # ── 13. AUTO-RENDER TEST FRAMES ──────────────────────────────────
    print("\n[13/13] Rendering Test Frames")
    run_py("Render frame 1 at preview resolution", """
import bpy
scene = bpy.context.scene
# Lower res for fast preview
scene.render.resolution_percentage = 50
scene.frame_set(1)
scene.render.filepath = "/tmp/city_v11_frame001.png"
bpy.ops.render.render(write_still=True)
__result__ = "frame 1 rendered"
""")
    run_py("Render frame 120", """
import bpy
scene = bpy.context.scene
scene.frame_set(120)
scene.render.filepath = "/tmp/city_v11_frame120.png"
bpy.ops.render.render(write_still=True)
# Restore full res
scene.render.resolution_percentage = 100
__result__ = "frame 120 rendered"
""")

    # ── FINAL SCENE ANALYSIS ──────────────────────────────────────────
    print("\n" + "═" * 50)
    print("  FINAL SCENE ANALYSIS")
    print("═" * 50)
    analysis = send("scene_analyze", {})
    stats = analysis.get("statistics", {})
    elapsed = time.time() - t0

    print(f"  Objects:    {stats.get('total_objects', '?')}")
    print(f"  Vertices:   {stats.get('total_vertices', '?')}")
    print(f"  Faces:      {stats.get('total_faces', '?')}")
    print(f"  Lights:     {stats.get('total_lights', '?')}")
    print(f"  Cameras:    {stats.get('total_cameras', '?')}")
    print(f"  Materials:  {stats.get('materials_count', '?')}")
    print(f"  Animation:  240 frames @ 24fps = 10 seconds")
    print(f"  Build time: {elapsed:.1f}s")

    print()
    print("▓" * 72)
    print("▓")
    print("▓  ✓  SUNSET CITYSCAPE v11 COMPLETE!")
    print("▓")
    print("▓  Renders saved to:")
    print("▓    /tmp/city_v11_frame001.png")
    print("▓    /tmp/city_v11_frame120.png")
    print("▓")
    print("▓  Features:")
    print("▓    • EEVEE with raytracing + AgX Very High Contrast")
    print("▓    • Procedural sunset gradient sky")
    print("▓    • Animated ocean with realistic water shader")
    print("▓    • 40+ buildings with procedural window textures")
    print("▓    • Inverted Brick Fac + Object coords (no scale bugs)")
    print("▓    • 3 building material variants (glass, concrete, brick)")
    print("▓    • Volumetric sunset fog atmosphere")
    print("▓    • God ray spotlight + 5 lamp posts with point lights")
    print("▓    • Waterfront railing with horizontal bar")
    print("▓    • Smooth 10-second camera dolly with bezier curves")
    print("▓    • Depth of field (f/2.8, 7 blades)")
    print("▓    • Compositing: glare bloom + chromatic aberration")
    print("▓    • Motion blur + emissive glass title")
    print("▓")
    print("▓  Press SPACE to play animation, F12 to render full res")
    print("▓" * 72)
    print()


if __name__ == "__main__":
    main()
