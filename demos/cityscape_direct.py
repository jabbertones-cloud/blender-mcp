#!/usr/bin/env python3
"""
OpenClaw Blender — Animated Cityscape with Sunset over Water (DIRECT MODE)
===========================================================================
Runs directly inside Blender via: blender -P demos/cityscape_direct.py
No TCP bridge needed. Uses bpy directly.

Blender 5.1 compatible. EEVEE raytracing + AgX color management.
Procedural window textures with correct Brick Fac inversion.
"""

import bpy
import math
import random

random.seed(42)

print()
print("=" * 60)
print("  OpenClaw — Sunset Cityscape v19 (Direct Mode)")
print("=" * 60)

# ── 1. CLEAR SCENE ──────────────────────────────────────────────────
print("[1/13] Clearing scene...")
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

# ── EEVEE + AgX ────────────────────────────────────────────────────
print("[1/13] Configuring EEVEE + AgX...")
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

eevee = scene.eevee
# Raytracing (Blender 5.1 verified attributes)
eevee.use_raytracing = True
eevee.ray_tracing_method = 'SCREEN'
eevee.shadow_ray_count = 2
eevee.shadow_step_count = 6
# Volumetrics
eevee.volumetric_start = 0.1
eevee.volumetric_end = 200.0
eevee.volumetric_tile_size = '8'
eevee.volumetric_samples = 128
eevee.use_volumetric_shadows = True
# Render quality
eevee.taa_render_samples = 128
eevee.taa_samples = 32
# Fast GI (global illumination)
eevee.use_fast_gi = True

# Screen-space effects — matches viewport richness
try:
    eevee.use_gtao = True            # Ambient Occlusion — depth on building edges
    eevee.gtao_distance = 1.0
    eevee.gtao_factor = 1.5
except AttributeError:
    pass

try:
    eevee.use_bloom = True            # Bloom — lit windows glow!
    eevee.bloom_threshold = 0.6
    eevee.bloom_intensity = 0.25
    eevee.bloom_radius = 8.0
except AttributeError:
    pass

# Filmic color management — rich colors + good dynamic range
scene.display_settings.display_device = 'sRGB'
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = 0.2
scene.view_settings.gamma = 1.0

# PNG output
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'
scene.render.image_settings.color_mode = 'RGBA'
print("  ✓ EEVEE + AgX configured")

# ── 2. SUNSET SKY ──────────────────────────────────────────────────
print("\n[2/13] Building sunset sky...")
world = bpy.data.worlds["World"]
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
nodes.clear()

# Sky gradient using Generated coords
coord = nodes.new(type="ShaderNodeTexCoord")
coord.location = (-800, 0)
sep = nodes.new(type="ShaderNodeSeparateXYZ")
sep.location = (-600, 0)
links.new(coord.outputs["Generated"], sep.inputs["Vector"])

# Map range: Generated Z goes -1 to +1. Remap to 0-1 for ColorRamp
map_range = nodes.new(type="ShaderNodeMapRange")
map_range.location = (-400, 0)
map_range.inputs["From Min"].default_value = -0.3
map_range.inputs["From Max"].default_value = 0.5
map_range.inputs["To Min"].default_value = 0.0
map_range.inputs["To Max"].default_value = 1.0
map_range.clamp = True
links.new(sep.outputs["Z"], map_range.inputs["Value"])

ramp = nodes.new(type="ShaderNodeValToRGB")
ramp.location = (-200, 0)
cr = ramp.color_ramp
# Fac 0 = below horizon, Fac 1 = above
cr.elements[0].position = 0.0
cr.elements[0].color = (0.5, 0.2, 0.05, 1.0)     # warm amber (below/at horizon)
e1 = cr.elements.new(0.3)
e1.color = (0.3, 0.1, 0.15, 1.0)                  # dusky rose
e2 = cr.elements.new(0.5)
e2.color = (0.1, 0.06, 0.25, 1.0)                 # purple
e3 = cr.elements.new(0.7)
e3.color = (0.04, 0.05, 0.2, 1.0)                 # deep blue
cr.elements[1].position = 1.0
cr.elements[1].color = (0.02, 0.03, 0.1, 1.0)     # dark indigo
links.new(map_range.outputs["Result"], ramp.inputs["Fac"])

bg = nodes.new(type="ShaderNodeBackground")
bg.location = (100, 0)
bg.inputs["Strength"].default_value = 1.5
links.new(ramp.outputs["Color"], bg.inputs["Color"])

output = nodes.new(type="ShaderNodeOutputWorld")
output.location = (600, 0)

# HDRI for reflections/lighting — the "secret sauce" that makes viewport look rich
import os
HDRI_PATH = "/Applications/Blender.app/Contents/Resources/5.1/datafiles/studiolights/world/sunset.exr"
hdri_exists = os.path.isfile(HDRI_PATH)

if hdri_exists:
    # Load sunset HDRI for environment lighting
    env_tex = nodes.new(type="ShaderNodeTexEnvironment")
    env_tex.image = bpy.data.images.load(HDRI_PATH)
    env_tex.location = (-400, -300)

    mapping = nodes.new(type="ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0, 0, math.radians(60))
    mapping.location = (-600, -300)

    tex_coord2 = nodes.new(type="ShaderNodeTexCoord")
    tex_coord2.location = (-800, -300)

    bg_hdri = nodes.new(type="ShaderNodeBackground")
    bg_hdri.inputs["Strength"].default_value = 2.0
    bg_hdri.location = (100, -300)

    links.new(tex_coord2.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
    links.new(env_tex.outputs["Color"], bg_hdri.inputs["Color"])

    # Light Path: camera sees our procedural sky, reflections/lighting use HDRI
    light_path = nodes.new(type="ShaderNodeLightPath")
    light_path.location = (100, 200)

    mix = nodes.new(type="ShaderNodeMixShader")
    mix.location = (400, 0)

    links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    links.new(bg_hdri.outputs["Background"], mix.inputs[1])  # non-camera: HDRI
    links.new(bg.outputs["Background"], mix.inputs[2])        # camera: procedural sky
    links.new(mix.outputs["Shader"], output.inputs["Surface"])
    print("  ✓ Sunset sky + HDRI environment (sunset.exr)")
else:
    links.new(bg.outputs["Background"], output.inputs["Surface"])
    print("  ✓ Sunset sky built (no HDRI found)")

# ── 3. SUN + FILL LIGHT ──────────────────────────────────────────
print("\n[3/13] Lighting...")
# Very dim sun at extreme low angle — just enough for rim highlights
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.name = "SunsetSun"
sun.data.energy = 0.3
sun.data.color = (1.0, 0.6, 0.3)
sun.data.angle = 0.05
sun.rotation_euler = (math.radians(88), math.radians(15), math.radians(-30))
try:
    sun.data.shadow_cascade_count = 4
except:
    pass

# Cool blue fill for ambient "blue hour" look
bpy.ops.object.light_add(type="AREA", location=(0, -10, 8))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = 15
fill.data.color = (0.4, 0.5, 0.9)
fill.data.size = 20
fill.rotation_euler = (math.radians(45), 0, 0)
print("  ✓ Sun + fill light")

# ── 4. OCEAN ──────────────────────────────────────────────────────
print("\n[4/13] Animated ocean...")
bpy.ops.mesh.primitive_plane_add(size=160, location=(0, 0, 0))
ocean_obj = bpy.context.active_object
ocean_obj.name = "Ocean"

ocean_mod = ocean_obj.modifiers.new(name="OceanWaves", type="OCEAN")
ocean_mod.geometry_mode = "GENERATE"
ocean_mod.repeat_x = 2
ocean_mod.repeat_y = 2
ocean_mod.resolution = 8
ocean_mod.spatial_size = 50
ocean_mod.wave_scale = 0.5
ocean_mod.choppiness = 0.8
ocean_mod.time = 0.0
ocean_mod.keyframe_insert(data_path="time", frame=1)
ocean_mod.time = 10.0
ocean_mod.keyframe_insert(data_path="time", frame=240)

water_mat = bpy.data.materials.new("OceanWater")
water_mat.use_nodes = True
bsdf = water_mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.01, 0.04, 0.12, 1.0)
bsdf.inputs["Roughness"].default_value = 0.03
bsdf.inputs["IOR"].default_value = 1.33
try:
    bsdf.inputs["Transmission Weight"].default_value = 0.85
except:
    pass
try:
    bsdf.inputs["Specular IOR Level"].default_value = 0.5
except:
    pass
ocean_obj.data.materials.append(water_mat)
print("  ✓ Ocean created")

# ── 5. PROCEDURAL BUILDINGS WITH WINDOW TEXTURES ──────────────────
print("\n[5/13] Building city skyline with procedural windows...")


def create_window_material(name, win_per_unit=1.5, frame_pct=0.15,
                           wall_color=(0.02, 0.025, 0.04, 1),
                           emit_color=(1.0, 0.9, 0.6, 1), emit_str=12.0,
                           lit_pct=0.5):
    """Math-based window grid using Object X+Z coordinates.

    PROVEN APPROACH (via math_windows3.py diagnostic):
    - Object coords + SeparateXYZ + FRACT + GREATER_THAN/LESS_THAN
    - X axis = window columns, Z axis = window rows
    - FLOOR-based cell indexing for per-window noise randomization
    - Works on ALL vertical cube faces (front, back, sides)
    - Brick Texture is 3D volumetric and FAILS on vertical faces — do NOT use

    win_per_unit: window cells per world unit (after scale apply)
    frame_pct: fraction of each cell that is dark frame border
    lit_pct: fraction of windows that are emissive
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()

    tc = nd.new("ShaderNodeTexCoord")
    sep = nd.new("ShaderNodeSeparateXYZ")
    lk.new(tc.outputs["Object"], sep.inputs["Vector"])

    # === X axis: columns ===
    x_sc = nd.new("ShaderNodeMath"); x_sc.operation = "MULTIPLY"
    lk.new(sep.outputs["X"], x_sc.inputs[0]); x_sc.inputs[1].default_value = win_per_unit

    x_frac = nd.new("ShaderNodeMath"); x_frac.operation = "FRACT"
    lk.new(x_sc.outputs["Value"], x_frac.inputs[0])

    x_gt = nd.new("ShaderNodeMath"); x_gt.operation = "GREATER_THAN"
    lk.new(x_frac.outputs["Value"], x_gt.inputs[0]); x_gt.inputs[1].default_value = frame_pct

    x_lt = nd.new("ShaderNodeMath"); x_lt.operation = "LESS_THAN"
    lk.new(x_frac.outputs["Value"], x_lt.inputs[0]); x_lt.inputs[1].default_value = 1.0 - frame_pct

    x_win = nd.new("ShaderNodeMath"); x_win.operation = "MULTIPLY"
    lk.new(x_gt.outputs["Value"], x_win.inputs[0]); lk.new(x_lt.outputs["Value"], x_win.inputs[1])

    # === Z axis: rows (windows slightly taller than wide) ===
    z_sc = nd.new("ShaderNodeMath"); z_sc.operation = "MULTIPLY"
    lk.new(sep.outputs["Z"], z_sc.inputs[0]); z_sc.inputs[1].default_value = win_per_unit * 0.7

    z_frac = nd.new("ShaderNodeMath"); z_frac.operation = "FRACT"
    lk.new(z_sc.outputs["Value"], z_frac.inputs[0])

    z_gt = nd.new("ShaderNodeMath"); z_gt.operation = "GREATER_THAN"
    lk.new(z_frac.outputs["Value"], z_gt.inputs[0]); z_gt.inputs[1].default_value = frame_pct

    z_lt = nd.new("ShaderNodeMath"); z_lt.operation = "LESS_THAN"
    lk.new(z_frac.outputs["Value"], z_lt.inputs[0]); z_lt.inputs[1].default_value = 1.0 - frame_pct

    z_win = nd.new("ShaderNodeMath"); z_win.operation = "MULTIPLY"
    lk.new(z_gt.outputs["Value"], z_win.inputs[0]); lk.new(z_lt.outputs["Value"], z_win.inputs[1])

    # Window mask = X grid AND Z grid
    win_mask = nd.new("ShaderNodeMath"); win_mask.operation = "MULTIPLY"
    lk.new(x_win.outputs["Value"], win_mask.inputs[0])
    lk.new(z_win.outputs["Value"], win_mask.inputs[1])

    # === PER-CELL NOISE using FLOOR of grid coords ===
    x_floor = nd.new("ShaderNodeMath"); x_floor.operation = "FLOOR"
    lk.new(x_sc.outputs["Value"], x_floor.inputs[0])

    z_floor = nd.new("ShaderNodeMath"); z_floor.operation = "FLOOR"
    lk.new(z_sc.outputs["Value"], z_floor.inputs[0])

    combine = nd.new("ShaderNodeCombineXYZ")
    lk.new(x_floor.outputs["Value"], combine.inputs["X"])
    lk.new(z_floor.outputs["Value"], combine.inputs["Y"])
    combine.inputs["Z"].default_value = 0.0

    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0
    noise.inputs["Detail"].default_value = 0.0
    noise.inputs["Roughness"].default_value = 1.0
    lk.new(combine.outputs["Vector"], noise.inputs["Vector"])

    lit_thresh = nd.new("ShaderNodeMath"); lit_thresh.operation = "GREATER_THAN"
    lk.new(noise.outputs["Fac"], lit_thresh.inputs[0])
    lit_thresh.inputs[1].default_value = 1.0 - lit_pct

    # Final mask: window shape AND lit
    final_mask = nd.new("ShaderNodeMath"); final_mask.operation = "MULTIPLY"
    lk.new(win_mask.outputs["Value"], final_mask.inputs[0])
    lk.new(lit_thresh.outputs["Value"], final_mask.inputs[1])

    # === SHADERS ===
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = wall_color
    wall.inputs["Roughness"].default_value = 0.85

    win = nd.new("ShaderNodeBsdfPrincipled")
    win.inputs["Base Color"].default_value = emit_color
    win.inputs["Emission Color"].default_value = emit_color
    win.inputs["Emission Strength"].default_value = emit_str
    win.inputs["Roughness"].default_value = 0.05

    mix = nd.new("ShaderNodeMixShader")
    lk.new(final_mask.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["BSDF"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


# Create 3 material variants
mat_glass = create_window_material(
    "Bldg_Glass", win_per_unit=1.5, frame_pct=0.12,
    wall_color=(0.02, 0.03, 0.05, 1), emit_color=(0.95, 0.88, 0.6, 1),
    emit_str=12.0, lit_pct=0.55
)
mat_concrete = create_window_material(
    "Bldg_Concrete", win_per_unit=1.2, frame_pct=0.18,
    wall_color=(0.06, 0.05, 0.04, 1), emit_color=(1.0, 0.92, 0.7, 1),
    emit_str=10.0, lit_pct=0.4
)
mat_brick = create_window_material(
    "Bldg_Brick", win_per_unit=1.8, frame_pct=0.1,
    wall_color=(0.08, 0.04, 0.03, 1), emit_color=(1.0, 0.8, 0.4, 1),
    emit_str=14.0, lit_pct=0.6
)
variants = [mat_glass, mat_concrete, mat_brick]

# Generate buildings
grid_x, grid_z = 10, 5
spacing_x, spacing_z = 8, 8
offset_y = 15
count = 0

for gx in range(grid_x):
    for gz in range(grid_z):
        if random.random() < 0.12:
            continue

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

        # Apply scale so Object coords work correctly
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        bldg.data.materials.append(variants[random.randint(0, 2)])
        count += 1

print(f"  ✓ {count} buildings with procedural window textures")

# ── 6. THIN ATMOSPHERIC HAZE (very subtle, not overpowering) ─────
print("\n[6/13] Subtle atmospheric haze...")
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 35, 15))
atmo = bpy.context.active_object
atmo.name = "Atmosphere"
atmo.scale = (80, 40, 20)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

fog_mat = bpy.data.materials.new("SunsetHaze")
fog_mat.use_nodes = True
fn = fog_mat.node_tree.nodes
fl = fog_mat.node_tree.links
fn.clear()
vol = fn.new("ShaderNodeVolumePrincipled")
vol.inputs["Color"].default_value = (0.3, 0.25, 0.4, 1.0)  # cooler haze (purple tint)
# Extremely subtle — atmospheric depth only
vol.inputs["Density"].default_value = 0.00015
out_f = fn.new("ShaderNodeOutputMaterial")
fl.new(vol.outputs[0], out_f.inputs["Volume"])
atmo.data.materials.append(fog_mat)
print("  ✓ Subtle haze applied")

# ── 7. GOD RAYS ──────────────────────────────────────────────────
print("\n[7/13] God ray spotlight...")
bpy.ops.object.light_add(type="SPOT", location=(0, 60, 8))
spot = bpy.context.active_object
spot.name = "GodRaySpot"
spot.data.energy = 3000
spot.data.color = (1.0, 0.7, 0.4)
spot.data.spot_size = 1.2
spot.data.shadow_soft_size = 1.0
spot.rotation_euler = (math.radians(90), 0, 0)
print("  ✓ God rays")

# ── 8. FOREGROUND (LAMPS + RAILING) ──────────────────────────────
print("\n[8/13] Foreground elements...")
metal_mat = bpy.data.materials.new("DarkMetal")
metal_mat.use_nodes = True
m_bsdf = metal_mat.node_tree.nodes.get("Principled BSDF")
m_bsdf.inputs["Base Color"].default_value = (0.15, 0.15, 0.17, 1)
m_bsdf.inputs["Metallic"].default_value = 0.9
m_bsdf.inputs["Roughness"].default_value = 0.35

glow_mat = bpy.data.materials.new("LampGlow")
glow_mat.use_nodes = True
g_bsdf = glow_mat.node_tree.nodes.get("Principled BSDF")
g_bsdf.inputs["Base Color"].default_value = (1, 0.9, 0.6, 1)
g_bsdf.inputs["Emission Color"].default_value = (1, 0.85, 0.5, 1)
g_bsdf.inputs["Emission Strength"].default_value = 15.0

for i in range(5):
    x = -20 + i * 10
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=4, location=(x, 5, 2))
    post = bpy.context.active_object
    post.name = f"LampPost_{i}"
    post.data.materials.append(metal_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=(x, 5, 4.2))
    bulb = bpy.context.active_object
    bulb.name = f"LampBulb_{i}"
    bulb.data.materials.append(glow_mat)

    bpy.ops.object.light_add(type="POINT", location=(x, 5, 4.2))
    ll = bpy.context.active_object
    ll.name = f"LampLight_{i}"
    ll.data.energy = 50
    ll.data.color = (1, 0.85, 0.5)

for i in range(16):
    x = -30 + i * 4
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 4, 0.5))
    rail = bpy.context.active_object
    rail.name = f"Rail_{i}"
    rail.scale = (0.05, 0.05, 0.5)
    bpy.ops.object.transform_apply(scale=True)
    rail.data.materials.append(metal_mat)

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4, 1.0))
bar = bpy.context.active_object
bar.name = "RailBar"
bar.scale = (30, 0.03, 0.03)
bpy.ops.object.transform_apply(scale=True)
bar.data.materials.append(metal_mat)
print("  ✓ Foreground elements")

# ── 9. CAMERA ANIMATION ─────────────────────────────────────────
print("\n[9/13] Camera dolly animation...")
for obj in list(bpy.data.objects):
    if obj.type == "CAMERA":
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.object.camera_add()
cam = bpy.context.active_object
cam.name = "CityCamera"
scene.camera = cam

keyframes = [
    (1,   (-35, -2, 4),  (math.radians(83), 0, math.radians(-15)), 28),
    (80,  (-10, -3, 5),  (math.radians(82), 0, math.radians(-3)),  32),
    (160, (10,  -3, 6),  (math.radians(81), 0, math.radians(3)),   35),
    (240, (35,  -2, 4),  (math.radians(83), 0, math.radians(15)),  28),
]

for frame, loc, rot, lens_val in keyframes:
    scene.frame_set(frame)
    cam.location = loc
    cam.rotation_euler = rot
    cam.data.lens = lens_val
    cam.keyframe_insert(data_path="location")
    cam.keyframe_insert(data_path="rotation_euler")
    cam.data.keyframe_insert(data_path="lens")

# Smooth interpolation (Blender 5.1: fcurve_ensure_for_datablock)
if cam.animation_data and cam.animation_data.action:
    action = cam.animation_data.action
    for dp in ["location", "rotation_euler"]:
        for idx in range(3):
            fc = action.fcurve_ensure_for_datablock(cam, dp, index=idx)
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = "AUTO"
                kp.handle_right_type = "AUTO"
    fc_lens = action.fcurve_ensure_for_datablock(cam.data, "lens", index=0)
    for kp in fc_lens.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = "AUTO"
        kp.handle_right_type = "AUTO"

cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 35.0
cam.data.dof.aperture_fstop = 2.8
cam.data.dof.aperture_blades = 7
print("  ✓ Camera dolly with DOF")

# ── 10. COMPOSITING ─────────────────────────────────────────────
print("\n[10/13] Compositing...")
scene.use_nodes = True
ng = scene.compositing_node_group
if ng is None:
    ng = bpy.data.node_groups.new("Compositing Nodetree", "CompositorNodeTree")
    scene.compositing_node_group = ng
cn = ng.nodes
cl = ng.links
cn.clear()

rl = cn.new(type="CompositorNodeRLayers")
rl.location = (0, 0)

glare = cn.new(type="CompositorNodeGlare")
glare.location = (300, 0)
for inp in glare.inputs:
    if inp.name == "Threshold" and inp.type == "VALUE":
        inp.default_value = 0.6
    if inp.name == "Strength" and inp.type == "VALUE":
        inp.default_value = 0.4

lens_d = cn.new(type="CompositorNodeLensdist")
lens_d.location = (600, 0)
for inp in lens_d.inputs:
    if inp.name == "Jitter" and inp.type == "VALUE":
        inp.default_value = 1.0
    if inp.name == "Dispersion" and inp.type == "VALUE":
        inp.default_value = 0.02

group_out = cn.new(type="NodeGroupOutput")
group_out.location = (900, 0)
viewer = cn.new(type="CompositorNodeViewer")
viewer.location = (900, -200)

cl.new(rl.outputs["Image"], glare.inputs["Image"])
cl.new(glare.outputs["Image"], lens_d.inputs["Image"])
cl.new(lens_d.outputs["Image"], viewer.inputs["Image"])
try:
    cl.new(lens_d.outputs["Image"], group_out.inputs[0])
except:
    pass
print("  ✓ Compositor (glare + lens distortion)")

# ── 11. MOTION BLUR ─────────────────────────────────────────────
print("\n[11/13] Motion blur...")
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.35
print("  ✓ Motion blur")

# ── 12. TITLE TEXT ───────────────────────────────────────────────
print("\n[12/13] Title text...")
bpy.ops.object.text_add(location=(0, -2, 12))
title = bpy.context.active_object
title.data.body = "OpenClaw - Sunset City"
title.data.size = 2.0
title.data.extrude = 0.1
title.data.align_x = 'CENTER'
title.data.align_y = 'CENTER'

title_mat = bpy.data.materials.new("TitleGlass")
title_mat.use_nodes = True
t_bsdf = title_mat.node_tree.nodes.get("Principled BSDF")
t_bsdf.inputs["Base Color"].default_value = (0.9, 0.85, 0.7, 1)
t_bsdf.inputs["Metallic"].default_value = 0.3
t_bsdf.inputs["Roughness"].default_value = 0.1
t_bsdf.inputs["Emission Color"].default_value = (1, 0.9, 0.6, 1)
t_bsdf.inputs["Emission Strength"].default_value = 3.0
title.data.materials.append(title_mat)
print("  ✓ Title text")

# ── 13. RENDER TEST FRAMES ──────────────────────────────────────
print("\n[13/13] Rendering test frames at 75% resolution...")
scene.render.resolution_percentage = 75

scene.frame_set(1)
scene.render.filepath = "/tmp/city_v19_frame001.png"
bpy.ops.render.render(write_still=True)
print("  ✓ Frame 1 rendered")

scene.frame_set(120)
scene.render.filepath = "/tmp/city_v19_frame120.png"
bpy.ops.render.render(write_still=True)
print("  ✓ Frame 120 rendered")

scene.render.resolution_percentage = 100

# Save .blend file
bpy.ops.wm.save_as_mainfile(filepath="/tmp/openclaw_cityscape_v11.blend")

print()
print("=" * 60)
print("  ✓ SUNSET CITYSCAPE v11 COMPLETE!")
print(f"  Objects: {len(bpy.data.objects)}")
print(f"  Materials: {len(bpy.data.materials)}")
print("  Renders: /tmp/city_v19_frame001.png, /tmp/city_v19_frame120.png")
print("  Blend: /tmp/openclaw_cityscape_v11.blend")
print("=" * 60)
