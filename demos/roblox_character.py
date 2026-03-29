"""
OpenClaw Blender — Roblox R15 Character with Walk Cycle
========================================================
Blocky R15 character with direct-animated body parts (Roblox Motor6D style).
NO subdivision — keeps the iconic Roblox blocky look with subtle bevel edges.
Walk cycle keyframed per-part. Studio lighting + turntable camera.
Runs: blender -b -P demos/roblox_character.py
"""
import bpy, math

print("\n" + "=" * 60)
print("  OpenClaw — Roblox R15 Character Demo")
print("=" * 60)

# ── CLEAR ────────────────────────────────────────────────────
print("[1/7] Clearing...")
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for act in list(bpy.data.actions):
    bpy.data.actions.remove(act)

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 48
scene.render.fps = 24
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

eevee = scene.eevee
eevee.use_raytracing = True
eevee.taa_render_samples = 128

# Screen-space effects (what makes the viewport look rich)
try:
    eevee.use_gtao = True            # Ambient Occlusion
    eevee.gtao_distance = 0.3
    eevee.gtao_factor = 1.2
except AttributeError:
    pass  # AO API may differ in 5.1

try:
    eevee.use_bloom = True            # Bloom / glow on bright areas
    eevee.bloom_threshold = 0.8
    eevee.bloom_intensity = 0.15
    eevee.bloom_radius = 6.0
except AttributeError:
    pass  # Bloom API may differ in 5.1

# AgX color management — matches viewport's punchy, rich colors
# Filmic gives the best balance: rich colors + good dynamic range
# (Standard is too literal, AgX crushes saturation on blues)
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = 0.3

# ── ENVIRONMENT ──────────────────────────────────────────────
print("[2/7] Studio setup with HDRI environment...")
world = bpy.data.worlds["World"]
world.use_nodes = True
wn = world.node_tree
wn.nodes.clear()

# HDRI environment — the exact file Blender's Material Preview uses
HDRI_PATH = "/Applications/Blender.app/Contents/Resources/5.1/datafiles/studiolights/world/studio.exr"
import os
hdri_exists = os.path.isfile(HDRI_PATH)

# Build world shader nodes
out_node = wn.nodes.new("ShaderNodeOutputWorld")
out_node.location = (600, 0)

if hdri_exists:
    # HDRI for lighting + reflections, dark backdrop for camera
    # This gives the rich environment reflections you see in viewport
    env_tex = wn.nodes.new("ShaderNodeTexEnvironment")
    env_tex.image = bpy.data.images.load(HDRI_PATH)
    env_tex.location = (-400, 200)

    # Rotate HDRI for better key light angle
    mapping = wn.nodes.new("ShaderNodeMapping")
    mapping.inputs["Rotation"].default_value = (0, 0, math.radians(120))
    mapping.location = (-600, 200)

    tex_coord = wn.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 200)

    # HDRI background (for lighting/reflections)
    bg_hdri = wn.nodes.new("ShaderNodeBackground")
    bg_hdri.inputs["Strength"].default_value = 2.5  # Strong for vivid reflections + ambient
    bg_hdri.location = (0, 200)

    # Dark studio backdrop (what camera sees)
    bg_dark = wn.nodes.new("ShaderNodeBackground")
    bg_dark.inputs["Color"].default_value = (0.025, 0.025, 0.05, 1)
    bg_dark.inputs["Strength"].default_value = 1.0
    bg_dark.location = (0, -100)

    # Light Path: use HDRI for everything EXCEPT direct camera rays
    light_path = wn.nodes.new("ShaderNodeLightPath")
    light_path.location = (0, 400)

    mix = wn.nodes.new("ShaderNodeMixShader")
    mix.location = (300, 0)

    # Connect: camera sees dark backdrop, everything else sees HDRI
    wn.links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    wn.links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
    wn.links.new(env_tex.outputs["Color"], bg_hdri.inputs["Color"])
    wn.links.new(light_path.outputs["Is Camera Ray"], mix.inputs["Fac"])
    wn.links.new(bg_hdri.outputs["Background"], mix.inputs[1])
    wn.links.new(bg_dark.outputs["Background"], mix.inputs[2])
    wn.links.new(mix.outputs["Shader"], out_node.inputs["Surface"])
    print("  * HDRI loaded: studio.exr (environment reflections + dark backdrop)")
else:
    # Fallback: gradient background if HDRI not found
    bg = wn.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.04, 0.04, 0.08, 1)
    bg.inputs["Strength"].default_value = 0.5
    wn.links.new(bg.outputs["Background"], out_node.inputs["Surface"])
    print("  * HDRI not found, using flat background")

# Floor — glossy dark surface for HDRI reflections
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "Floor"
fm = bpy.data.materials.new("FloorMat")
fm.use_nodes = True
fb = fm.node_tree.nodes.get("Principled BSDF")
fb.inputs["Base Color"].default_value = (0.06, 0.06, 0.1, 1)
fb.inputs["Roughness"].default_value = 0.08   # Very glossy for vivid reflections
fb.inputs["Metallic"].default_value = 0.4
floor.data.materials.append(fm)

# 3-point lighting (reduced energy — HDRI provides most of the lighting now)
bpy.ops.object.light_add(type="AREA", location=(3, -3, 5))
key = bpy.context.active_object
key.name = "Key"
key.data.energy = 250       # Main key light + HDRI ambient
key.data.color = (1, 0.95, 0.9)
key.data.size = 3
key.rotation_euler = (math.radians(55), 0, math.radians(35))

bpy.ops.object.light_add(type="AREA", location=(-4, -2, 3))
fill = bpy.context.active_object
fill.name = "Fill"
fill.data.energy = 60        # Reduced — HDRI provides fill bounce
fill.data.color = (0.7, 0.8, 1.0)
fill.data.size = 5
fill.rotation_euler = (math.radians(50), 0, math.radians(-45))

bpy.ops.object.light_add(type="AREA", location=(0, 4, 4))
rim = bpy.context.active_object
rim.name = "Rim"
rim.data.energy = 120        # Reduced slightly
rim.data.color = (0.85, 0.8, 1.0)
rim.data.size = 2
rim.rotation_euler = (math.radians(130), 0, 0)

# ── MATERIALS ────────────────────────────────────────────────
print("[3/7] Materials...")

def make_mat(name, col, emit_col=None, emit_str=0.0, roughness=0.45):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = col
    b.inputs["Roughness"].default_value = roughness
    if emit_col:
        b.inputs["Emission Color"].default_value = emit_col
        b.inputs["Emission Strength"].default_value = emit_str
    return m

M_SKIN    = make_mat("Skin",    (0.93, 0.72, 0.54, 1), roughness=0.45)
M_SHIRT   = make_mat("Shirt",   (0.08, 0.35, 0.95, 1), (0.1, 0.4, 1.0, 1), 0.8, 0.25)
M_PANTS   = make_mat("Pants",   (0.18, 0.2, 0.35, 1), roughness=0.5)
M_SHOES   = make_mat("Shoes",   (0.06, 0.06, 0.08, 1), roughness=0.2)    # Glossier shoes
M_HAIR    = make_mat("Hair",    (0.12, 0.06, 0.03, 1), roughness=0.55)
M_EYE_W   = make_mat("EyeWhite",(0.97, 0.97, 0.97, 1), roughness=0.05)   # More reflective
M_EYE_I   = make_mat("EyeIris", (0.08, 0.25, 0.65, 1), (0.15, 0.4, 0.9, 1), 0.8, 0.02)
M_MOUTH   = make_mat("Mouth",   (0.55, 0.28, 0.22, 1), roughness=0.45)

# ── CHARACTER PARTS ──────────────────────────────────────────
print("[4/7] Building character...")

# Roblox R15 proportions (Blender units, total height ~2.2 BU)
# The key: cubes only, NO subdivision, subtle bevel for nice edges

def make_block(name, location, dimensions, material, parent=None, pivot_top=False, bevel_width=0.015):
    """Create a blocky body part.

    dimensions: (width_x, depth_y, height_z) - FULL size
    pivot_top: if True, mesh origin is at the top of the block (for limbs that swing from shoulder/hip)
    """
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name

    # Scale to dimensions
    w, d, h = dimensions
    obj.scale = (w, d, h)
    bpy.ops.object.transform_apply(scale=True)

    # If pivot_top, shift mesh down so origin is at top edge
    if pivot_top:
        for v in obj.data.vertices:
            v.co.z -= 0.5  # mesh was -0.5 to +0.5, now -1.0 to 0.0 (scaled)

    # Subtle bevel for that polished Roblox look
    if bevel_width > 0:
        bev = obj.modifiers.new("Bevel", "BEVEL")
        bev.width = bevel_width
        bev.segments = 2
        bev.limit_method = 'ANGLE'

    obj.data.materials.append(material)
    obj.location = location

    if parent:
        obj.parent = parent

    return obj


# === ROOT EMPTY ===
root = bpy.data.objects.new("CharRoot", None)
bpy.context.collection.objects.link(root)
root.empty_display_type = 'PLAIN_AXES'
root.empty_display_size = 0.2
root.location = (0, 0, 0)

# === TORSO (center of the character) ===
# Lower torso: pivot is at its center (hips)
lower_torso = make_block("LowerTorso", (0, 0, 1.05), (0.75, 0.40, 0.30), M_PANTS, parent=root)

# Upper torso sits on top of lower torso
upper_torso = make_block("UpperTorso", (0, 0, 0.40), (0.80, 0.42, 0.55), M_SHIRT, parent=lower_torso)

# === HEAD ===
head = make_block("Head", (0, 0, 0.58), (0.70, 0.68, 0.70), M_SKIN, parent=upper_torso, bevel_width=0.04)

# Hair — sits on top of head, slightly oversized
hair = make_block("Hair", (0, 0.02, 0.30), (0.74, 0.72, 0.28), M_HAIR, parent=head, bevel_width=0.03)

# Eyes — flat boxes on face
for side, xoff in [("L", -0.16), ("R", 0.16)]:
    # White
    ew = make_block(f"EyeW_{side}", (xoff, -0.34, 0.06), (0.15, 0.02, 0.10), M_EYE_W,
                    parent=head, bevel_width=0.005)
    # Iris/pupil
    ei = make_block(f"EyeI_{side}", (xoff, -0.355, 0.04), (0.08, 0.02, 0.08), M_EYE_I,
                    parent=head, bevel_width=0.003)

# Mouth — small dark line
mouth = make_block("Mouth", (0, -0.34, -0.12), (0.20, 0.02, 0.04), M_MOUTH,
                   parent=head, bevel_width=0.003)

# === ARMS ===
# Upper arms: pivot at top (shoulder joint)
upper_arm_L = make_block("UpperArm_L", (-0.54, 0, 0.15), (0.30, 0.30, 0.45), M_SHIRT,
                         parent=upper_torso, pivot_top=True, bevel_width=0.012)
lower_arm_L = make_block("LowerArm_L", (0, 0, -0.45), (0.27, 0.27, 0.42), M_SKIN,
                         parent=upper_arm_L, pivot_top=True, bevel_width=0.012)
hand_L = make_block("Hand_L", (0, 0, -0.42), (0.20, 0.15, 0.15), M_SKIN,
                    parent=lower_arm_L, bevel_width=0.008)

upper_arm_R = make_block("UpperArm_R", (0.54, 0, 0.15), (0.30, 0.30, 0.45), M_SHIRT,
                         parent=upper_torso, pivot_top=True, bevel_width=0.012)
lower_arm_R = make_block("LowerArm_R", (0, 0, -0.45), (0.27, 0.27, 0.42), M_SKIN,
                         parent=upper_arm_R, pivot_top=True, bevel_width=0.012)
hand_R = make_block("Hand_R", (0, 0, -0.42), (0.20, 0.15, 0.15), M_SKIN,
                    parent=lower_arm_R, bevel_width=0.008)

# === LEGS ===
# Upper legs: pivot at top (hip joint)
upper_leg_L = make_block("UpperLeg_L", (-0.19, 0, -0.15), (0.32, 0.32, 0.48), M_PANTS,
                         parent=lower_torso, pivot_top=True, bevel_width=0.012)
lower_leg_L = make_block("LowerLeg_L", (0, 0, -0.48), (0.28, 0.28, 0.45), M_PANTS,
                         parent=upper_leg_L, pivot_top=True, bevel_width=0.012)
foot_L = make_block("Foot_L", (0, 0.06, -0.45), (0.30, 0.42, 0.14), M_SHOES,
                    parent=lower_leg_L, bevel_width=0.01)

upper_leg_R = make_block("UpperLeg_R", (0.19, 0, -0.15), (0.32, 0.32, 0.48), M_PANTS,
                         parent=lower_torso, pivot_top=True, bevel_width=0.012)
lower_leg_R = make_block("LowerLeg_R", (0, 0, -0.48), (0.28, 0.28, 0.45), M_PANTS,
                         parent=upper_leg_R, pivot_top=True, bevel_width=0.012)
foot_R = make_block("Foot_R", (0, 0.06, -0.45), (0.30, 0.42, 0.14), M_SHOES,
                    parent=lower_leg_R, bevel_width=0.01)

print("  * Character built (15 parts, blocky R15 style)")

# ── WALK CYCLE ───────────────────────────────────────────────
print("[5/7] Walk cycle animation...")

def set_rot(obj, frame, rx, ry, rz):
    """Set rotation in degrees at given frame."""
    obj.rotation_mode = 'XYZ'
    obj.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    obj.keyframe_insert(data_path="rotation_euler", frame=frame)

def set_loc(obj, frame, x, y, z):
    obj.location = (x, y, z)
    obj.keyframe_insert(data_path="location", frame=frame)

# Walk cycle: 48 frames = 2 full steps (24 per step)
# Key poses: Contact(1) → Down(6) → Passing(12) → Up(18) → Contact(24) → ...

# -- Lower torso: subtle vertical bounce and twist --
base_z = lower_torso.location.z
for f, rx, ry, rz, dz in [
    (1,   2, 0, -2,  0.00),
    (6,   0, 0, -1, -0.02),
    (12, -1, 0,  0,  0.01),
    (18,  0, 0,  1,  0.02),
    (24,  2, 0,  2,  0.00),
    (30,  0, 0,  1, -0.02),
    (36, -1, 0,  0,  0.01),
    (42,  0, 0, -1,  0.02),
    (48,  2, 0, -2,  0.00),
]:
    set_rot(lower_torso, f, rx, ry, rz)
    set_loc(lower_torso, f, 0, 0, base_z + dz)

# -- Upper torso: counter-twist --
for f, rx, ry, rz in [
    (1,   3,  0,  3),
    (12, -2,  0, -2),
    (24,  3,  0, -3),
    (36, -2,  0,  2),
    (48,  3,  0,  3),
]:
    set_rot(upper_torso, f, rx, ry, rz)

# -- Head: gentle bob and look --
for f, rx, ry, rz in [
    (1,  -2, 0,  2),
    (12,  3, 0,  0),
    (24, -2, 0, -2),
    (36,  3, 0,  0),
    (48, -2, 0,  2),
]:
    set_rot(head, f, rx, ry, rz)

# -- LEFT LEG --
for f, rx in [(1, -30), (6, -35), (12, 5), (18, 25), (24, 30), (30, 20), (36, -5), (42, -25), (48, -30)]:
    set_rot(upper_leg_L, f, rx, 0, 0)

for f, rx in [(1, -5), (6, -15), (12, -45), (18, -30), (24, -5), (30, -15), (36, -45), (42, -30), (48, -5)]:
    set_rot(lower_leg_L, f, rx, 0, 0)

for f, rx in [(1, 15), (6, 20), (12, 0), (18, -10), (24, -15), (30, 0), (36, 10), (42, 15), (48, 15)]:
    set_rot(foot_L, f, rx, 0, 0)

# -- RIGHT LEG (opposite phase, offset by 24 frames) --
for f, rx in [(1, 30), (6, 20), (12, -5), (18, -25), (24, -30), (30, -35), (36, 5), (42, 25), (48, 30)]:
    set_rot(upper_leg_R, f, rx, 0, 0)

for f, rx in [(1, -5), (6, -15), (12, -45), (18, -30), (24, -5), (30, -15), (36, -45), (42, -30), (48, -5)]:
    set_rot(lower_leg_R, f, rx, 0, 0)

for f, rx in [(1, -15), (6, 0), (12, 10), (18, 15), (24, 15), (30, 20), (36, 0), (42, -10), (48, -15)]:
    set_rot(foot_R, f, rx, 0, 0)

# -- LEFT ARM (swings opposite to left leg) --
for f, rx in [(1, 25), (12, -20), (24, -25), (36, 20), (48, 25)]:
    set_rot(upper_arm_L, f, rx, 0, 5)

for f, rx in [(1, -5), (12, -35), (24, -10), (36, -30), (48, -5)]:
    set_rot(lower_arm_L, f, rx, 0, 0)

# -- RIGHT ARM (swings opposite to right leg) --
for f, rx in [(1, -25), (12, 20), (24, 25), (36, -20), (48, -25)]:
    set_rot(upper_arm_R, f, rx, 0, -5)

for f, rx in [(1, -10), (12, -30), (24, -5), (36, -35), (48, -10)]:
    set_rot(lower_arm_R, f, rx, 0, 0)

# Smooth all keyframes + add cycle modifier for looping
for obj in bpy.data.objects:
    if obj.animation_data and obj.animation_data.action:
        try:
            for fc in obj.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'
                fc.modifiers.new(type='CYCLES')
        except Exception:
            pass

print("  * Walk cycle: 48 frames, looping")

# ── CAMERA ───────────────────────────────────────────────────
print("[6/7] Camera...")

# Camera orbits around the character
cam_radius = 5.5
cam_height = 1.15
cam_target_z = 1.1  # look at torso level

bpy.ops.object.camera_add(location=(0, -cam_radius, cam_height))
cam = bpy.context.active_object
cam.name = "Camera"
scene.camera = cam
cam.data.lens = 35
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = cam_radius
cam.data.dof.aperture_fstop = 3.2

# Track-to constraint so camera always faces character
track = cam.constraints.new(type='TRACK_TO')
track.target = lower_torso
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# Keyframe camera orbit
for f, angle_deg in [(1, 20), (16, 0), (32, -20), (48, 20)]:
    angle = math.radians(angle_deg)
    cx = math.sin(angle) * cam_radius
    cy = -math.cos(angle) * cam_radius
    # slight height variation
    cz = cam_height + 0.1 * math.sin(math.radians(angle_deg * 2))
    cam.location = (cx, cy, cz)
    cam.keyframe_insert(data_path="location", frame=f)

# Smooth camera keyframes
try:
    if cam.animation_data and cam.animation_data.action:
        for fc in cam.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = 'AUTO_CLAMPED'
                kp.handle_right_type = 'AUTO_CLAMPED'
except (AttributeError, RuntimeError):
    pass  # Blender 5.1 Action API may not expose fcurves

print("  * Turntable camera with DOF")

# ── RENDER ───────────────────────────────────────────────────
print("[7/7] Rendering...")
for f in [1, 16, 32]:
    scene.frame_set(f)
    scene.render.filepath = f"/tmp/roblox_char_f{f:03d}.png"
    bpy.ops.render.render(write_still=True)
    print(f"  * Frame {f}")

bpy.ops.wm.save_as_mainfile(filepath="/tmp/openclaw_roblox_character.blend")

n_objs = len([o for o in bpy.data.objects if o.type == 'MESH'])
print("\n" + "=" * 60)
print("  ROBLOX R15 CHARACTER DEMO COMPLETE!")
print(f"  Mesh objects: {n_objs}, Materials: {len(bpy.data.materials)}")
print("  Animation: 48-frame walk cycle (looping)")
print("=" * 60)
