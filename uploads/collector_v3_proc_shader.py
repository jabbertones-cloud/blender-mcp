# --- PARAMETERS ---
# v3 — Same Skin+Subsurf body (connected mesh) + procedural region shader.
# Avoids the polygon-Z-threshold material assignment failure entirely:
# instead of trying to map polygon centers to slots AFTER subsurf shifts
# them, the shader graph uses Texture Coordinate (Generated) → height + side
# masks → ColorRamp → mixed into a single Principled BSDF Base Color. Any
# point in the mesh just looks at its world-space position and gets the
# right color. Resolution-independent. Subsurf-proof.

CASE_WIDTH_M = 0.16
CASE_HEIGHT_M = 0.30
CASE_DEPTH_M = 0.16
CASE_WALL_M = 0.0035
CASE_BASE_HEIGHT_M = 0.012
CASE_BASE_COLOR = (0.95, 0.95, 0.95, 1.0)
CASE_GLASS_IOR = 1.49
CASE_GLASS_ROUGHNESS = 0.06
CASE_GLASS_TRANSMISSION = 0.92
CASE_GLASS_TINT = (0.97, 0.99, 1.0, 1.0)

FIG_TOTAL_H = 0.25
FIG_HEAD_R = 0.034
FIG_NECK_R = 0.012
FIG_TORSO_TOP_R = 0.024
FIG_TORSO_MID_R = 0.022
FIG_HIP_R = 0.020
FIG_THIGH_R = 0.014
FIG_KNEE_R = 0.012
FIG_ANKLE_R = 0.010
FIG_FOOT_R = 0.013
FIG_SHOULDER_R = 0.014
FIG_UPPER_ARM_R = 0.011
FIG_ELBOW_R = 0.010
FIG_WRIST_R = 0.0095
FIG_HAND_R = 0.013
FIG_SUBSURF_VIEWPORT = 2
FIG_SUBSURF_RENDER = 3

# Shader — region thresholds in LOCAL Z coordinates (figure root at z=0)
# Head zone: Z > HAIR_Z gets hair-black, Z in (FACE_Z, HAIR_Z) gets skin
HAIR_Z_LOCAL = 0.215           # ~0.86 of FIG_TOTAL_H
FACE_Z_LOCAL = 0.180           # ~0.72
NECK_Z_LOCAL = 0.190
TORSO_TOP_Z_LOCAL = 0.180
TORSO_BOT_Z_LOCAL = 0.105      # ~0.42
SHOE_Z_LOCAL = 0.020
SHIRT_Y_THRESH = -0.005        # front-of-torso Y < this gets shirt color
SHIRT_X_HALF_WIDTH = 0.018     # horizontal width of shirt panel

SKIN_COLOR = (0.78, 0.55, 0.39, 1.0)
HAIR_COLOR = (0.04, 0.04, 0.04, 1.0)
SHIRT_COLOR = (0.92, 0.92, 0.92, 1.0)
SUIT_COLOR = (0.05, 0.05, 0.05, 1.0)
TIE_COLOR = (0.04, 0.04, 0.04, 1.0)
SCARF_COLOR = (0.62, 0.10, 0.10, 1.0)
SHOE_COLOR = (0.95, 0.95, 0.95, 1.0)
EYE_BLACK = (0.02, 0.02, 0.02, 1.0)
PROXY_ROUGHNESS = 0.55

# Eye add-ons
EYE_RADIUS = 0.011
EYE_LOC = (0.022, -FIG_HEAD_R * 0.92, 0.197)  # local to figure
PUPIL_RADIUS = 0.0058
PUPIL_LOC = (0.024, -FIG_HEAD_R * 1.0, 0.197)

# Hair clump add-ons (chunky strands)
HAIR_CLUMP_COUNT = 9
HAIR_CLUMP_LEN = 0.022
HAIR_CLUMP_RAD = 0.007
HAIR_CLUMP_TIP_RAD = 0.001

# Lighting
KEY_LIGHT_ENERGY_W = 95.0
KEY_LIGHT_SIZE_M = 0.6
KEY_LIGHT_LOC = (0.45, -0.55, 0.55)
KEY_LIGHT_COLOR_K = 5600
FILL_LIGHT_ENERGY_W = 38.0
FILL_LIGHT_SIZE_M = 0.8
FILL_LIGHT_LOC = (-0.55, -0.50, 0.45)
ENV_STRENGTH = 0.20
ENV_TOP_COLOR = (0.92, 0.93, 0.94, 1.0)
ENV_BOTTOM_COLOR = (0.55, 0.55, 0.58, 1.0)

# Camera
CAM_LOC = (-0.42, -0.72, 0.21)
CAM_LOOK_AT = (0.0, 0.0, 0.16)
CAM_FOCAL_LEN_MM = 60.0
CAM_DOF_USE = False
CAM_DOF_F_STOP = 8.0

# Render — match reference resolution for pixel-overlay step
RENDER_ENGINE = "CYCLES"
RENDER_SAMPLES = 96
RENDER_RES_X = 700
RENDER_RES_Y = 700
RENDER_USE_DENOISER = True
VIEW_TRANSFORM = "Standard"
VIEW_LOOK = "None"
VIEW_EXPOSURE = -0.4

RENDER_FILEPATH = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/uploads/collector_v3_proc_render.png"
SAVE_BLEND_PATH = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/uploads/collector_v3_proc_scene.blend"

# DEBUG: hide acrylic case from render to isolate figure materials. When True,
# Case_* panels render-hidden but kept in the .blend. Use ONLY to debug
# material assignment then flip back to False.
HIDE_CASE_FOR_DEBUG = False
# --- /PARAMETERS ---

import bpy, bmesh
from math import radians
from mathutils import Vector


# ─── 1. Wipe ─────────────────────────────────────────────────────────────────
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for blk in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
            bpy.data.worlds, bpy.data.images):
    for d in list(blk):
        if d.users == 0:
            blk.remove(d)


# ─── 2. Helpers ──────────────────────────────────────────────────────────────

def make_principled(name, color, roughness, transmission=0.0, ior=1.45,
                    metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior
    for tn in ("Transmission Weight", "Transmission"):
        if tn in bsdf.inputs:
            bsdf.inputs[tn].default_value = transmission
            break
    return m


def make_region_shader_material():
    """Build a procedural region-color material — ONE material, ONE BSDF, but
    Base Color is driven by a node graph that reads world position and outputs
    different colors for hair/skin/shirt/suit/shoes. Subsurf-proof, mesh-split
    proof. The canonical 'stylized non-PBR' approach."""
    m = bpy.data.materials.new("FigureRegionShader")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = PROXY_ROUGHNESS

    # World-space coordinate
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Object"], sep.inputs[0])  # object-space Z

    # ── Region masks via Compare nodes ───────────────────────────────────────
    def gt(a_input, threshold):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = 'GREATER_THAN'
        nt.links.new(a_input, n.inputs[0])
        n.inputs[1].default_value = threshold
        return n.outputs[0]

    def lt(a_input, threshold):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = 'LESS_THAN'
        nt.links.new(a_input, n.inputs[0])
        n.inputs[1].default_value = threshold
        return n.outputs[0]

    def m_and(a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = 'MULTIPLY'
        nt.links.new(a, n.inputs[0])
        nt.links.new(b, n.inputs[1])
        return n.outputs[0]

    def m_or(a, b):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = 'MAXIMUM'
        nt.links.new(a, n.inputs[0])
        nt.links.new(b, n.inputs[1])
        return n.outputs[0]

    def abs_node(input):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = 'ABSOLUTE'
        nt.links.new(input, n.inputs[0])
        return n.outputs[0]

    # Z mask for HAIR (z > HAIR_Z)
    mask_hair = gt(sep.outputs["Z"], HAIR_Z_LOCAL)
    # Z mask for FACE/SKIN (FACE_Z < z <= HAIR_Z) -> face zone
    mask_face = m_and(gt(sep.outputs["Z"], FACE_Z_LOCAL), lt(sep.outputs["Z"], HAIR_Z_LOCAL))

    # Front-front mask (Y < SHIRT_Y_THRESH AND |X| < SHIRT_X_HALF_WIDTH AND torso z range)
    front_y = lt(sep.outputs["Y"], SHIRT_Y_THRESH)
    abs_x = abs_node(sep.outputs["X"])
    narrow_x = lt(abs_x, SHIRT_X_HALF_WIDTH)
    in_torso_z = m_and(gt(sep.outputs["Z"], TORSO_BOT_Z_LOCAL), lt(sep.outputs["Z"], TORSO_TOP_Z_LOCAL))
    mask_shirt = m_and(m_and(front_y, narrow_x), in_torso_z)

    # Shoes (z < SHOE_Z)
    mask_shoe = lt(sep.outputs["Z"], SHOE_Z_LOCAL)

    # Hand region — small spheres at ends of arms, below face but above torso top
    # Skip — let hands fall under skin via Y/Z heuristics; keep simple

    # Default = SUIT (everything not above)

    # ── Color mixing chain — start from SUIT, layer in shoe, then shirt, then face, then hair ──
    def mix(color_a_input, color_b_input_or_value, fac_input):
        """Mix node: A -> B by fac. fac=1 → use B."""
        mn = nt.nodes.new("ShaderNodeMix")
        mn.data_type = 'RGBA'
        mn.blend_type = 'MIX'
        if isinstance(color_a_input, tuple):
            mn.inputs["A"].default_value = color_a_input
        else:
            nt.links.new(color_a_input, mn.inputs["A"])
        if isinstance(color_b_input_or_value, tuple):
            mn.inputs["B"].default_value = color_b_input_or_value
        else:
            nt.links.new(color_b_input_or_value, mn.inputs["B"])
        nt.links.new(fac_input, mn.inputs["Factor"])
        return mn.outputs["Result"]

    base = mix(SUIT_COLOR, SHOE_COLOR, mask_shoe)
    base = mix(base, SHIRT_COLOR, mask_shirt)
    base = mix(base, SKIN_COLOR, mask_face)
    base = mix(base, HAIR_COLOR, mask_hair)

    nt.links.new(base, bsdf.inputs["Base Color"])
    return m


# ─── 3. Materials ────────────────────────────────────────────────────────────
mat_acrylic = make_principled("Acrylic", CASE_GLASS_TINT, CASE_GLASS_ROUGHNESS,
                              transmission=CASE_GLASS_TRANSMISSION, ior=CASE_GLASS_IOR)
mat_acrylic.blend_method = 'BLEND'
mat_acrylic.use_screen_refraction = True
mat_base = make_principled("CaseBase", CASE_BASE_COLOR, 0.45)
mat_figure = make_region_shader_material()
mat_eye = make_principled("Eye", EYE_BLACK, 0.30)
mat_scarf = make_principled("Scarf", SCARF_COLOR, PROXY_ROUGHNESS)


# ─── 4. Display case ─────────────────────────────────────────────────────────
case = bpy.data.objects.new("DisplayCase", None)
bpy.context.collection.objects.link(case)
w, d, h, t = CASE_WIDTH_M, CASE_DEPTH_M, CASE_HEIGHT_M, CASE_WALL_M
bz = CASE_BASE_HEIGHT_M

def add_box(name, loc, dims, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = (dims[0]/2, dims[1]/2, dims[2]/2)
    if parent: o.parent = parent
    return o

base_obj = add_box("Case_Base", (0, 0, bz/2), (w, d, bz), parent=case)
base_obj.data.materials.append(mat_base)

panels = []
panels.append(add_box("Case_Front",  (0,  d/2 - t/2, bz + (h - bz)/2), (w, t, h - bz), parent=case))
panels.append(add_box("Case_Back",   (0, -d/2 + t/2, bz + (h - bz)/2), (w, t, h - bz), parent=case))
panels.append(add_box("Case_Left",   (-w/2 + t/2, 0, bz + (h - bz)/2), (t, d, h - bz), parent=case))
panels.append(add_box("Case_Right",  ( w/2 - t/2, 0, bz + (h - bz)/2), (t, d, h - bz), parent=case))
panels.append(add_box("Case_Top",    (0, 0, h - t/2),                   (w, d, t), parent=case))
for o in panels:
    o.data.materials.append(mat_acrylic)


# ─── 5. Figure body — Skin + Subsurf on connected vertex skeleton ───────────
bpy.ops.object.add(type='MESH', enter_editmode=False, location=(0, 0, bz))
fig = bpy.context.active_object
fig.name = "FigureBody"
fig.parent = case

me = fig.data
bm = bmesh.new()
H = FIG_TOTAL_H

joint_positions = {
    "head_top":   (0, 0, H * 0.99),
    "head":       (0, 0, H * 0.86),
    "neck":       (0, 0, H * 0.78),
    "torso_up":   (0, 0, H * 0.72),
    "torso_mid":  (0, 0, H * 0.55),
    "hip":        (0, 0, H * 0.42),
    "thigh_l":    (-0.022, 0, H * 0.42),
    "knee_l":     (-0.022, 0, H * 0.22),
    "ankle_l":    (-0.024, 0, H * 0.05),
    "foot_l":     (-0.024, -FIG_FOOT_R*0.5, H * 0.02),
    "thigh_r":    ( 0.022, 0, H * 0.42),
    "knee_r":     ( 0.022, 0, H * 0.22),
    "ankle_r":    ( 0.024, 0, H * 0.05),
    "foot_r":     ( 0.024, -FIG_FOOT_R*0.5, H * 0.02),
    "shoulder_l": (-0.030, 0, H * 0.71),
    "elbow_l":    (-0.040, -0.020, H * 0.62),
    "wrist_l":    (-0.018, -0.030, H * 0.66),
    "hand_l":     (-0.005, -0.040, H * 0.66),
    "shoulder_r": ( 0.030, 0, H * 0.71),
    "elbow_r":    ( 0.040, -0.020, H * 0.62),
    "wrist_r":    ( 0.018, -0.030, H * 0.66),
    "hand_r":     ( 0.005, -0.040, H * 0.66),
}
joint_radii = {
    "head_top":   FIG_HEAD_R * 0.85,
    "head":       FIG_HEAD_R,
    "neck":       FIG_NECK_R,
    "torso_up":   FIG_TORSO_TOP_R,
    "torso_mid":  FIG_TORSO_MID_R,
    "hip":        FIG_HIP_R,
    "thigh_l":    FIG_THIGH_R, "knee_l": FIG_KNEE_R, "ankle_l": FIG_ANKLE_R, "foot_l": FIG_FOOT_R,
    "thigh_r":    FIG_THIGH_R, "knee_r": FIG_KNEE_R, "ankle_r": FIG_ANKLE_R, "foot_r": FIG_FOOT_R,
    "shoulder_l": FIG_SHOULDER_R, "elbow_l": FIG_ELBOW_R, "wrist_l": FIG_WRIST_R, "hand_l": FIG_HAND_R,
    "shoulder_r": FIG_SHOULDER_R, "elbow_r": FIG_ELBOW_R, "wrist_r": FIG_WRIST_R, "hand_r": FIG_HAND_R,
}

vmap = {}
for name, pos in joint_positions.items():
    v = bm.verts.new(pos)
    vmap[name] = v
bm.verts.ensure_lookup_table()

edges = [
    ("hip", "torso_mid"), ("torso_mid", "torso_up"),
    ("torso_up", "neck"), ("neck", "head"), ("head", "head_top"),
    ("hip", "thigh_l"), ("thigh_l", "knee_l"), ("knee_l", "ankle_l"), ("ankle_l", "foot_l"),
    ("hip", "thigh_r"), ("thigh_r", "knee_r"), ("knee_r", "ankle_r"), ("ankle_r", "foot_r"),
    ("torso_up", "shoulder_l"), ("shoulder_l", "elbow_l"), ("elbow_l", "wrist_l"), ("wrist_l", "hand_l"),
    ("torso_up", "shoulder_r"), ("shoulder_r", "elbow_r"), ("elbow_r", "wrist_r"), ("wrist_r", "hand_r"),
]
for a, b in edges:
    bm.edges.new([vmap[a], vmap[b]])

bm.to_mesh(me)
bm.free()

skin_mod = fig.modifiers.new("Skin", type='SKIN')
skin_mod.use_smooth_shade = True
name_to_idx = {n: i for i, n in enumerate(joint_positions.keys())}
for name, r in joint_radii.items():
    idx = name_to_idx[name]
    sv = me.skin_vertices[0].data[idx]
    sv.radius = (r, r)
me.skin_vertices[0].data[name_to_idx["hip"]].use_root = True

sub_mod = fig.modifiers.new("Subsurf", type='SUBSURF')
sub_mod.levels = FIG_SUBSURF_VIEWPORT
sub_mod.render_levels = FIG_SUBSURF_RENDER

bpy.context.view_layer.objects.active = fig
bpy.ops.object.modifier_apply(modifier="Skin")
bpy.ops.object.modifier_apply(modifier="Subsurf")
bpy.ops.object.shade_smooth()

# ── ASSIGN THE PROCEDURAL REGION SHADER (one material slot, one mesh) ──
fig.data.materials.append(mat_figure)


# ─── 6. Hair clumps — chunky strands sticking up + forward ──────────────────
import random
random.seed(11)
from math import pi, cos, sin
hair_parent = bpy.data.objects.new("HairClumps", None)
bpy.context.collection.objects.link(hair_parent)
hair_parent.parent = case
hair_parent.location = (0, 0, bz + H * 0.86)

for i in range(HAIR_CLUMP_COUNT):
    a = (i / HAIR_CLUMP_COUNT) * 2 * pi
    sx = (FIG_HEAD_R * 0.85) * cos(a)
    sy = (FIG_HEAD_R * 0.85) * sin(a)
    sz = 0.0
    bpy.ops.mesh.primitive_cone_add(
        radius1=HAIR_CLUMP_RAD + random.random() * 0.003,
        radius2=HAIR_CLUMP_TIP_RAD,
        depth=HAIR_CLUMP_LEN + random.random() * 0.010,
        location=(sx, sy, sz)
    )
    s = bpy.context.active_object
    s.name = f"Hair_{i:02d}"
    s.parent = hair_parent
    s.rotation_euler = (radians(15 + random.random() * 35),
                        radians(-8 + random.random() * 16),
                        radians(random.random() * 360))
    bpy.ops.object.shade_smooth()
    hair_mat = make_principled(f"HairMat_{i:02d}", HAIR_COLOR, PROXY_ROUGHNESS)
    s.data.materials.append(hair_mat)


# ─── 7. Eye (single visible black-pupil) ─────────────────────────────────────
bpy.ops.mesh.primitive_uv_sphere_add(radius=EYE_RADIUS,
                                     location=(EYE_LOC[0], EYE_LOC[1], bz + EYE_LOC[2]),
                                     segments=24, ring_count=12)
eye_obj = bpy.context.active_object
eye_obj.name = "Eye"
eye_obj.parent = case
mat_eye_white = make_principled("EyeWhite", (0.97, 0.97, 0.97, 1.0), 0.25)
eye_obj.data.materials.append(mat_eye_white)
bpy.ops.object.shade_smooth()

bpy.ops.mesh.primitive_uv_sphere_add(radius=PUPIL_RADIUS,
                                     location=(PUPIL_LOC[0], PUPIL_LOC[1], bz + PUPIL_LOC[2]),
                                     segments=20, ring_count=10)
pupil = bpy.context.active_object
pupil.name = "Pupil"
pupil.parent = case
pupil.data.materials.append(mat_eye)
bpy.ops.object.shade_smooth()


# ─── 8. Scarf (red torus around the neck) ───────────────────────────────────
bpy.ops.mesh.primitive_torus_add(major_radius=FIG_NECK_R + 0.004,
                                 minor_radius=0.003,
                                 location=(0, 0, bz + H * 0.78))
scarf = bpy.context.active_object
scarf.name = "Scarf"
scarf.parent = case
scarf.data.materials.append(mat_scarf)
bpy.ops.object.shade_smooth()


# ─── 9. Lighting ─────────────────────────────────────────────────────────────
def kelvin_color(k):
    if k >= 6600: return (1.0, 0.97, 0.95)
    if k >= 5500: return (1.0, 1.0, 0.98)
    if k >= 4500: return (1.0, 0.91, 0.78)
    return (1.0, 0.78, 0.55)

def add_area(name, loc, energy, size, kelvin):
    bpy.ops.object.light_add(type='AREA', location=loc)
    o = bpy.context.active_object
    o.name = name
    o.data.energy = energy
    o.data.size = size
    o.data.color = kelvin_color(kelvin)
    direction = Vector((0, 0, 0.15)) - Vector(loc)
    o.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

if KEY_LIGHT_ENERGY_W > 0:
    add_area("KeyLight",  KEY_LIGHT_LOC,  KEY_LIGHT_ENERGY_W,  KEY_LIGHT_SIZE_M, KEY_LIGHT_COLOR_K)
if FILL_LIGHT_ENERGY_W > 0:
    add_area("FillLight", FILL_LIGHT_LOC, FILL_LIGHT_ENERGY_W, FILL_LIGHT_SIZE_M, KEY_LIGHT_COLOR_K)


# ─── 10. World ────────────────────────────────────────────────────────────────
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
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


# ─── 11. Camera ──────────────────────────────────────────────────────────────
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


# ─── 12. Render config ───────────────────────────────────────────────────────
scn = bpy.context.scene
scn.render.engine = RENDER_ENGINE
if RENDER_ENGINE == "CYCLES":
    scn.cycles.samples = RENDER_SAMPLES
    scn.cycles.use_denoising = RENDER_USE_DENOISER
    scn.cycles.use_adaptive_sampling = True
    scn.cycles.transmission_bounces = 16
    scn.cycles.transparent_max_bounces = 16
    scn.cycles.glossy_bounces = 8
scn.render.resolution_x = RENDER_RES_X
scn.render.resolution_y = RENDER_RES_Y
scn.render.resolution_percentage = 100
scn.render.film_transparent = False
scn.render.filepath = RENDER_FILEPATH
scn.view_settings.view_transform = VIEW_TRANSFORM
scn.view_settings.look = VIEW_LOOK
scn.view_settings.exposure = VIEW_EXPOSURE


# ─── 13. Optional: hide case for debug ──────────────────────────────────────
if HIDE_CASE_FOR_DEBUG:
    for o in bpy.data.objects:
        if o.name.startswith("Case_") or o.name == "DisplayCase":
            o.hide_render = True


# ─── 14. Save + render ───────────────────────────────────────────────────────
bpy.ops.wm.save_as_mainfile(filepath=SAVE_BLEND_PATH)
bpy.ops.render.render(write_still=True)


# ─── 14. Mesh report ─────────────────────────────────────────────────────────
__result__ = {
    "figure_body_vertices": len(fig.data.vertices),
    "figure_body_polygons": len(fig.data.polygons),
    "figure_body_materials": len(fig.data.materials),
    "hair_clumps": HAIR_CLUMP_COUNT,
    "case_panels": len(panels) + 1,
    "lights": len([o for o in bpy.data.objects if o.type == 'LIGHT']),
    "render_path": RENDER_FILEPATH,
    "blend_path": SAVE_BLEND_PATH,
    "shader_approach": "procedural region-coloring on single material slot",
}
