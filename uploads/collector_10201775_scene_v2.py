# --- PARAMETERS ---
CASE_WIDTH_M = 0.16
CASE_HEIGHT_M = 0.3
CASE_DEPTH_M = 0.16
CASE_WALL_M = 0.0035
CASE_BASE_HEIGHT_M = 0.012
CASE_BASE_COLOR = (0.95, 0.95, 0.95, 1.0)
CASE_GLASS_IOR = 1.49
CASE_GLASS_ROUGHNESS = 0.04
CASE_GLASS_TRANSMISSION = 1.0
CASE_GLASS_TINT = (0.97, 0.99, 1.0, 1.0)
FIGURE_HEIGHT_M = 0.25
FIGURE_BASE_Z = 0.013
FIGURE_FACE_DIRECTION_DEG = 22.0
SKIN_COLOR = (0.78, 0.55, 0.39, 1.0)
HAIR_COLOR_BASE = (0.04, 0.04, 0.04, 1.0)
HAIR_COLOR_TIPS = (0.62, 0.43, 0.2, 1.0)
SHIRT_COLOR = (0.92, 0.92, 0.92, 1.0)
SUIT_COLOR = (0.04, 0.04, 0.04, 1.0)
TIE_COLOR = (0.04, 0.04, 0.04, 1.0)
SCARF_COLOR = (0.62, 0.1, 0.1, 1.0)
SHOE_TOE_COLOR = (0.95, 0.95, 0.95, 1.0)
SHOE_UPPER_COLOR = (0.06, 0.06, 0.06, 1.0)
EYE_WHITE = (0.95, 0.95, 0.95, 1.0)
EYE_PUPIL = (0.02, 0.02, 0.02, 1.0)
PROXY_ROUGHNESS = 0.55
KEY_LIGHT_ENERGY_W = 250.0
KEY_LIGHT_SIZE_M = 0.6
KEY_LIGHT_LOC = (0.45, -0.55, 0.55)
KEY_LIGHT_COLOR_K = 5600
FILL_LIGHT_ENERGY_W = 110.0
FILL_LIGHT_SIZE_M = 0.8
FILL_LIGHT_LOC = (-0.55, -0.5, 0.45)
RIM_LIGHT_ENERGY_W = 0.0
ENV_STRENGTH = 0.45
ENV_TOP_COLOR = (0.95, 0.95, 0.96, 1.0)
ENV_BOTTOM_COLOR = (0.78, 0.78, 0.8, 1.0)
CAM_LOC = (-0.32, -0.55, 0.2)
CAM_LOOK_AT = (0.0, 0.0, 0.16)
CAM_FOCAL_LEN_MM = 65.0
CAM_DOF_F_STOP = 8.0
CAM_DOF_USE = False
RENDER_ENGINE = 'CYCLES'
RENDER_SAMPLES = 128
RENDER_DENOISER = 'OPTIX'
RENDER_RES_X = 900
RENDER_RES_Y = 900
RENDER_FILM_TRANSPARENT = False
RENDER_FILEPATH = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/uploads/collector_10201775_render_v2.png'
SAVE_BLEND_PATH = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/uploads/collector_10201775_scene_v2.blend'
# --- /PARAMETERS ---

import bpy
from math import radians, pi, cos, sin
from mathutils import Vector


# ─── helpers ─────────────────────────────────────────────────────────────────

def kelvin_to_rgb(k):
    """Approximate Kelvin -> linear RGB (Tanner Helland)."""
    t = k / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * (max(t, 1) ** 0.0) * 0  # placeholder, real calc below
        g = 99.4708025861 * (t ** 0.0) - 161.1195681661 if False else max(0, min(255, 99.4708025861 * (max(t, 1)) ** 0.0))
    # Simpler stable version:
    if k >= 6600:
        return (1.0, 0.97, 0.95, 1.0)
    if k >= 5500:
        return (1.0, 1.0, 0.98, 1.0)
    if k >= 4500:
        return (1.0, 0.91, 0.78, 1.0)
    return (1.0, 0.78, 0.55, 1.0)


def make_principled(name, base_color, roughness, metallic=0.0,
                    transmission=0.0, ior=1.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior
    # Transmission key changed across versions
    for tname in ("Transmission Weight", "Transmission"):
        if tname in bsdf.inputs:
            bsdf.inputs[tname].default_value = transmission
            break
    return mat


def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def add_box(name, loc, dims, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (dims[0] / 2, dims[1] / 2, dims[2] / 2)
    if parent:
        o.parent = parent
    return o


def add_sphere(name, loc, radius, parent=None, segs=24, rings=12):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc,
                                         segments=segs, ring_count=rings)
    o = bpy.context.active_object
    o.name = name
    if parent:
        o.parent = parent
    return o


# ─── 1. Wipe scene ───────────────────────────────────────────────────────────

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
            bpy.data.worlds, bpy.data.images):
    for d in list(blk):
        if d.users == 0:
            blk.remove(d)


# ─── 2. Materials ────────────────────────────────────────────────────────────

mat_acrylic = make_principled("Acrylic", CASE_GLASS_TINT, CASE_GLASS_ROUGHNESS,
                              transmission=CASE_GLASS_TRANSMISSION,
                              ior=CASE_GLASS_IOR)
mat_acrylic.blend_method = 'BLEND'
mat_acrylic.use_screen_refraction = True

mat_base = make_principled("CaseBase", CASE_BASE_COLOR, 0.45)
mat_skin = make_principled("Skin", SKIN_COLOR, PROXY_ROUGHNESS)
mat_hair = make_principled("HairBase", HAIR_COLOR_BASE, PROXY_ROUGHNESS)
mat_hair_tip = make_principled("HairTips", HAIR_COLOR_TIPS, PROXY_ROUGHNESS)
mat_shirt = make_principled("Shirt", SHIRT_COLOR, PROXY_ROUGHNESS)
mat_suit = make_principled("Suit", SUIT_COLOR, PROXY_ROUGHNESS)
mat_tie = make_principled("Tie", TIE_COLOR, PROXY_ROUGHNESS)
mat_scarf = make_principled("Scarf", SCARF_COLOR, PROXY_ROUGHNESS)
mat_shoe_toe = make_principled("ShoeToe", SHOE_TOE_COLOR, 0.45)
mat_shoe_upper = make_principled("ShoeUpper", SHOE_UPPER_COLOR, 0.45)
mat_eye_w = make_principled("EyeWhite", EYE_WHITE, 0.30)
mat_eye_p = make_principled("EyePupil", EYE_PUPIL, 0.30)


# ─── 3. Display case (acrylic box) ───────────────────────────────────────────

# Outer transparent shell built from 5 thin panels (no top opening, rectangular display)
case = bpy.data.objects.new("DisplayCase", None)   # empty parent
bpy.context.collection.objects.link(case)
case.location = (0, 0, 0)

w, d, h, t = CASE_WIDTH_M, CASE_DEPTH_M, CASE_HEIGHT_M, CASE_WALL_M
bz = CASE_BASE_HEIGHT_M
inner_floor_z = bz                                  # top of base plate

# Solid base
base = add_box("Case_Base", (0, 0, bz / 2), (w, d, bz), parent=case)
assign(base, mat_base)

# Walls (acrylic)
front  = add_box("Case_Front",  (0,  d/2 - t/2, bz + (h - bz)/2), (w, t, h - bz), parent=case)
back   = add_box("Case_Back",   (0, -d/2 + t/2, bz + (h - bz)/2), (w, t, h - bz), parent=case)
left   = add_box("Case_Left",   (-w/2 + t/2, 0, bz + (h - bz)/2), (t, d, h - bz), parent=case)
right  = add_box("Case_Right",  ( w/2 - t/2, 0, bz + (h - bz)/2), (t, d, h - bz), parent=case)
top    = add_box("Case_Top",    (0, 0, h - t/2),                   (w, d, t),      parent=case)
for o in (front, back, left, right, top):
    assign(o, mat_acrylic)


# ─── 4. Figure proxy (low-poly stand-in) ─────────────────────────────────────
# Designed so an imported sculpt can swap in 1:1 by parenting to the FigureRoot empty.

figure = bpy.data.objects.new("FigureRoot", None)
bpy.context.collection.objects.link(figure)
figure.parent = case
figure.location = (0, 0, inner_floor_z + FIGURE_BASE_Z)
figure.rotation_euler = (0, 0, radians(FIGURE_FACE_DIRECTION_DEG))

# scale baseline: head ~ 0.07h, torso ~ 0.30h, legs ~ 0.42h
fh = FIGURE_HEIGHT_M
head_r = 0.045
torso_h, torso_w, torso_d = fh * 0.30, 0.060, 0.040
leg_h,  leg_w,  leg_d  = fh * 0.42, 0.022, 0.022
arm_l,  arm_r          = fh * 0.34, 0.014
foot_h, foot_w, foot_d = 0.024, 0.034, 0.060

# legs
leg_z = leg_h / 2 + foot_h
left_leg  = add_box("LegL", (-0.022, 0, leg_z), (leg_w, leg_d, leg_h), parent=figure)
right_leg = add_box("LegR", ( 0.022, 0, leg_z), (leg_w, leg_d, leg_h), parent=figure)
for o in (left_leg, right_leg): assign(o, mat_suit)

# torso
torso_z = leg_z + leg_h / 2 + torso_h / 2
torso = add_box("Torso", (0, 0, torso_z), (torso_w, torso_d, torso_h), parent=figure)
assign(torso, mat_suit)

# shirt panel (front V)
shirt = add_box("Shirt",
                (0, -torso_d / 2 - 0.001, torso_z + torso_h * 0.10),
                (torso_w * 0.55, 0.002, torso_h * 0.55),
                parent=figure)
assign(shirt, mat_shirt)

# tie
tie = add_box("Tie",
              (0, -torso_d / 2 - 0.0025, torso_z + torso_h * 0.05),
              (0.012, 0.002, torso_h * 0.45),
              parent=figure)
assign(tie, mat_tie)

# scarf
scarf = add_box("Scarf",
                (0, -torso_d / 2 - 0.001, torso_z + torso_h * 0.42),
                (torso_w * 0.85, 0.005, 0.010),
                parent=figure)
assign(scarf, mat_scarf)

# arms — raised pose (hands near chest)
shoulder_z = torso_z + torso_h * 0.40
arm_offset_x = torso_w / 2 + arm_r
arm_l_obj = add_box("ArmL", (-arm_offset_x, -0.020, shoulder_z - arm_l * 0.30),
                    (arm_r * 2, arm_r * 2, arm_l * 0.7), parent=figure)
arm_r_obj = add_box("ArmR", ( arm_offset_x, -0.020, shoulder_z - arm_l * 0.30),
                    (arm_r * 2, arm_r * 2, arm_l * 0.7), parent=figure)
arm_l_obj.rotation_euler = (radians(-30), 0, 0)
arm_r_obj.rotation_euler = (radians(-30), 0, 0)
for o in (arm_l_obj, arm_r_obj): assign(o, mat_suit)

# hands (skin)
hand_l = add_sphere("HandL", (-arm_offset_x * 0.7, -0.030, shoulder_z - arm_l * 0.05),
                    radius=0.018, parent=figure)
hand_r = add_sphere("HandR", ( arm_offset_x * 0.7, -0.030, shoulder_z - arm_l * 0.05),
                    radius=0.018, parent=figure)
for o in (hand_l, hand_r): assign(o, mat_skin)

# head
head_z = torso_z + torso_h / 2 + head_r * 1.05
head = add_sphere("Head", (0, 0, head_z), radius=head_r, parent=figure, segs=32, rings=20)
assign(head, mat_skin)

# eye (single visible large eye on right side from camera-pov, slightly forward)
eye = add_sphere("Eye", (0.020, -head_r * 0.85, head_z + head_r * 0.08),
                 radius=0.014, parent=figure, segs=24, rings=12)
assign(eye, mat_eye_w)
pupil = add_sphere("Pupil", (0.024, -head_r * 0.95, head_z + head_r * 0.08),
                   radius=0.007, parent=figure)
assign(pupil, mat_eye_p)

# hair sculpt — chunky strands sticking up + forward
hair_cap = add_sphere("HairCap", (0, 0, head_z + head_r * 0.35),
                      radius=head_r * 1.05, parent=figure, segs=32, rings=20)
assign(hair_cap, mat_hair)
import random
random.seed(7)
strand_count = 14
for i in range(strand_count):
    a = (i / strand_count) * 2 * pi
    sx, sy = head_r * 0.85 * cos(a), head_r * 0.85 * sin(a)
    sz = head_z + head_r * 0.55
    bpy.ops.mesh.primitive_cone_add(
        radius1=0.008 + random.random() * 0.004,
        radius2=0.001,
        depth=0.038 + random.random() * 0.016,
        location=(sx, sy, sz)
    )
    s = bpy.context.active_object
    s.name = f"HairStrand_{i:02d}"
    s.parent = figure
    s.rotation_euler = (radians(20 + random.random() * 30),
                        radians(-10 + random.random() * 20),
                        radians(random.random() * 360))
    # tan tip
    if i % 2 == 0:
        assign(s, mat_hair_tip)
    else:
        assign(s, mat_hair)

# feet (sneakers — white toe + sole, black upper)
def add_shoe(name, x):
    upper = add_box(f"{name}_Upper", (x, -0.005, foot_h / 2),
                    (foot_w, foot_d, foot_h), parent=figure)
    assign(upper, mat_shoe_upper)
    toe = add_box(f"{name}_Toe", (x, -foot_d / 2 - 0.005, foot_h * 0.30),
                  (foot_w, 0.020, foot_h * 0.55),
                  parent=figure)
    assign(toe, mat_shoe_toe)
    sole = add_box(f"{name}_Sole", (x, -0.005, 0.003),
                   (foot_w, foot_d, 0.006),
                   parent=figure)
    assign(sole, mat_shoe_toe)
add_shoe("ShoeL", -0.022)
add_shoe("ShoeR",  0.022)


# ─── 5. Lighting (3-point softbox) ───────────────────────────────────────────

def add_area(name, loc, energy, size, kelvin):
    bpy.ops.object.light_add(type='AREA', location=loc)
    o = bpy.context.active_object
    o.name = name
    o.data.energy = energy
    o.data.size = size
    o.data.color = kelvin_to_rgb(kelvin)[:3]
    # point at world origin (subject)
    direction = Vector((0, 0, 0.15)) - Vector(loc)
    o.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    return o

if KEY_LIGHT_ENERGY_W > 0:
    add_area("KeyLight",  KEY_LIGHT_LOC,  KEY_LIGHT_ENERGY_W,  KEY_LIGHT_SIZE_M, KEY_LIGHT_COLOR_K)
if FILL_LIGHT_ENERGY_W > 0:
    add_area("FillLight", FILL_LIGHT_LOC, FILL_LIGHT_ENERGY_W, FILL_LIGHT_SIZE_M, KEY_LIGHT_COLOR_K)
if RIM_LIGHT_ENERGY_W > 0:
    add_area("RimLight",  (0, 0.55, 0.45), RIM_LIGHT_ENERGY_W, 0.4, KEY_LIGHT_COLOR_K)


# ─── 6. World — bright soft white environment ───────────────────────────────

world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
out  = nt.nodes.new("ShaderNodeOutputWorld")
bg   = nt.nodes.new("ShaderNodeBackground")
grad = nt.nodes.new("ShaderNodeTexGradient")
mapn = nt.nodes.new("ShaderNodeMapping")
texc = nt.nodes.new("ShaderNodeTexCoord")
ramp = nt.nodes.new("ShaderNodeValToRGB")

bg.inputs["Strength"].default_value = ENV_STRENGTH
ramp.color_ramp.elements[0].color = ENV_BOTTOM_COLOR
ramp.color_ramp.elements[1].color = ENV_TOP_COLOR
mapn.inputs["Rotation"].default_value = (radians(90), 0, 0)
nt.links.new(texc.outputs["Generated"], mapn.inputs["Vector"])
nt.links.new(mapn.outputs["Vector"], grad.inputs["Vector"])
nt.links.new(grad.outputs["Fac"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


# ─── 7. Camera ───────────────────────────────────────────────────────────────

bpy.ops.object.camera_add(location=CAM_LOC)
cam = bpy.context.active_object
cam.name = "HeroCam"
cam.data.lens = CAM_FOCAL_LEN_MM
cam.data.dof.use_dof = CAM_DOF_USE
cam.data.dof.focus_distance = (Vector(CAM_LOOK_AT) - Vector(CAM_LOC)).length
cam.data.dof.aperture_fstop = CAM_DOF_F_STOP
direction = Vector(CAM_LOOK_AT) - Vector(CAM_LOC)
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam


# ─── 8. Render config ────────────────────────────────────────────────────────

scn = bpy.context.scene
scn.render.engine = RENDER_ENGINE
if RENDER_ENGINE == "CYCLES":
    scn.cycles.samples = RENDER_SAMPLES
    scn.cycles.use_denoising = True
    try:
        scn.cycles.denoiser = RENDER_DENOISER
    except Exception:
        scn.cycles.denoiser = "OPENIMAGEDENOISE"
    scn.cycles.use_adaptive_sampling = True
    scn.cycles.transmission_bounces = 16
    scn.cycles.transparent_max_bounces = 16
    scn.cycles.glossy_bounces = 8
scn.render.resolution_x = RENDER_RES_X
scn.render.resolution_y = RENDER_RES_Y
scn.render.resolution_percentage = 100
scn.render.film_transparent = RENDER_FILM_TRANSPARENT
scn.render.filepath = RENDER_FILEPATH
scn.view_settings.view_transform = "Filmic"
scn.view_settings.look = "None"


# ─── 9. Save .blend + render ─────────────────────────────────────────────────

bpy.ops.wm.save_as_mainfile(filepath=SAVE_BLEND_PATH)
bpy.ops.render.render(write_still=True)


# ─── return summary ─────────────────────────────────────────────────────────

__result__ = {
    "objects": [o.name for o in bpy.data.objects],
    "case_dimensions_cm": (CASE_WIDTH_M * 100, CASE_HEIGHT_M * 100, CASE_DEPTH_M * 100),
    "figure_height_cm": FIGURE_HEIGHT_M * 100,
    "render_path": RENDER_FILEPATH,
    "blend_path": SAVE_BLEND_PATH,
    "samples": RENDER_SAMPLES,
    "resolution": (RENDER_RES_X, RENDER_RES_Y),
}
