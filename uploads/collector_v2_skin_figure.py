# --- PARAMETERS ---
# v3.1.1 figure rebuild — Skin Modifier on a CONNECTED vertex skeleton, then
# Subsurf level 2 + smooth shading, all joined into ONE mesh. No disconnected
# primitives. Matches the canonical pipeline from skill: blender-guru notebook.

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

# Figure proportions (metres). Reads as ~25cm tall.
FIG_TOTAL_H = 0.25
FIG_HEAD_R = 0.034            # head radius (skin vertex)
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

# Skin smoothing — Subsurf levels (viewport / render)
FIG_SUBSURF_VIEWPORT = 2
FIG_SUBSURF_RENDER = 3

# Pose offsets (raised hands)
FIG_HAND_FORWARD = -0.03
FIG_HAND_UP = 0.02

# Color-block painted via vertex groups → multi-material on the joined mesh
SKIN_COLOR = (0.78, 0.55, 0.39, 1.0)
HAIR_COLOR = (0.04, 0.04, 0.04, 1.0)
SHIRT_COLOR = (0.92, 0.92, 0.92, 1.0)
SUIT_COLOR = (0.05, 0.05, 0.05, 1.0)
TIE_COLOR = (0.04, 0.04, 0.04, 1.0)
SCARF_COLOR = (0.62, 0.10, 0.10, 1.0)
SHOE_COLOR = (0.95, 0.95, 0.95, 1.0)
PROXY_ROUGHNESS = 0.55

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

# Render — match reference 700x700 for pixel-overlay technique
RENDER_ENGINE = "CYCLES"
RENDER_SAMPLES = 96
RENDER_RES_X = 700
RENDER_RES_Y = 700
RENDER_USE_DENOISER = True       # turn off for calibration overlay
VIEW_TRANSFORM = "Standard"
VIEW_LOOK = "None"
VIEW_EXPOSURE = -0.4

RENDER_FILEPATH = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/uploads/collector_v2_skin_render.png"
SAVE_BLEND_PATH = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/uploads/collector_v2_skin_scene.blend"
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


# ─── 2. Materials ────────────────────────────────────────────────────────────

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

mat_acrylic = make_principled("Acrylic", CASE_GLASS_TINT, CASE_GLASS_ROUGHNESS,
                              transmission=CASE_GLASS_TRANSMISSION,
                              ior=CASE_GLASS_IOR)
mat_acrylic.blend_method = 'BLEND'
mat_acrylic.use_screen_refraction = True
mat_base = make_principled("CaseBase", CASE_BASE_COLOR, 0.45)

mat_skin = make_principled("Skin", SKIN_COLOR, PROXY_ROUGHNESS)
mat_hair = make_principled("Hair", HAIR_COLOR, PROXY_ROUGHNESS)
mat_shirt = make_principled("Shirt", SHIRT_COLOR, PROXY_ROUGHNESS)
mat_suit = make_principled("Suit", SUIT_COLOR, PROXY_ROUGHNESS)
mat_tie = make_principled("Tie", TIE_COLOR, PROXY_ROUGHNESS)
mat_scarf = make_principled("Scarf", SCARF_COLOR, PROXY_ROUGHNESS)
mat_shoe = make_principled("Shoe", SHOE_COLOR, 0.45)


# ─── 3. Display case (5 transparent panels + base) ───────────────────────────

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


# ─── 4. Figure — Skin Modifier on a CONNECTED vertex skeleton ───────────────
# Each vertex carries a skin radius which controls the tube thickness at that
# joint. The Skin modifier auto-generates a single connected mesh. Then Subsurf
# smooths it. The result is ONE object, ONE mesh, real topology.

bpy.ops.object.add(type='MESH', enter_editmode=False, location=(0, 0, bz))
fig = bpy.context.active_object
fig.name = "Figure"
fig.parent = case

# Build skeleton in bmesh
me = fig.data
bm = bmesh.new()

# joint positions (relative to fig.location at bz)
H = FIG_TOTAL_H
# helper local coords
joint_positions = {
    "head_top":   (0,            0,                 H * 0.99),
    "head":       (0,            0,                 H * 0.86),
    "neck":       (0,            0,                 H * 0.78),
    "torso_up":   (0,            0,                 H * 0.72),
    "torso_mid":  (0,            0,                 H * 0.55),
    "hip":        (0,            0,                 H * 0.42),
    # legs
    "thigh_l":    (-0.022,       0,                 H * 0.42),
    "knee_l":     (-0.022,       0,                 H * 0.22),
    "ankle_l":    (-0.024,       0,                 H * 0.05),
    "foot_l":     (-0.024,      -FIG_FOOT_R*0.5,    H * 0.02),
    "thigh_r":    ( 0.022,       0,                 H * 0.42),
    "knee_r":     ( 0.022,       0,                 H * 0.22),
    "ankle_r":    ( 0.024,       0,                 H * 0.05),
    "foot_r":     ( 0.024,      -FIG_FOOT_R*0.5,    H * 0.02),
    # arms — raised pose
    "shoulder_l": (-0.030,       0,                 H * 0.71),
    "elbow_l":    (-0.040,      -0.020,             H * 0.62),
    "wrist_l":    (-0.018,      -0.030,             H * 0.66),
    "hand_l":     (-0.005,      -0.040,             H * 0.66),
    "shoulder_r": ( 0.030,       0,                 H * 0.71),
    "elbow_r":    ( 0.040,      -0.020,             H * 0.62),
    "wrist_r":    ( 0.018,      -0.030,             H * 0.66),
    "hand_r":     ( 0.005,      -0.040,             H * 0.66),
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

# spine + head chain
edges = [
    ("hip", "torso_mid"), ("torso_mid", "torso_up"),
    ("torso_up", "neck"), ("neck", "head"), ("head", "head_top"),
    # legs
    ("hip", "thigh_l"), ("thigh_l", "knee_l"), ("knee_l", "ankle_l"), ("ankle_l", "foot_l"),
    ("hip", "thigh_r"), ("thigh_r", "knee_r"), ("knee_r", "ankle_r"), ("ankle_r", "foot_r"),
    # arms
    ("torso_up", "shoulder_l"), ("shoulder_l", "elbow_l"), ("elbow_l", "wrist_l"), ("wrist_l", "hand_l"),
    ("torso_up", "shoulder_r"), ("shoulder_r", "elbow_r"), ("elbow_r", "wrist_r"), ("wrist_r", "hand_r"),
]
for a, b in edges:
    bm.edges.new([vmap[a], vmap[b]])

bm.to_mesh(me)
bm.free()

# ── Skin modifier setup ──────────────────────────────────────────────────────
skin_mod = fig.modifiers.new("Skin", type='SKIN')
skin_mod.use_smooth_shade = True

# Apply per-vertex skin radii
me.skin_vertices[0].data[0].use_root = False
# Map by name → vertex index
name_to_idx = {n: i for i, n in enumerate(joint_positions.keys())}
for name, r in joint_radii.items():
    idx = name_to_idx[name]
    sv = me.skin_vertices[0].data[idx]
    sv.radius = (r, r)
# Mark hip as the skin root
hip_idx = name_to_idx["hip"]
me.skin_vertices[0].data[hip_idx].use_root = True

# ── Subdivision surface ──────────────────────────────────────────────────────
sub_mod = fig.modifiers.new("Subsurf", type='SUBSURF')
sub_mod.levels = FIG_SUBSURF_VIEWPORT
sub_mod.render_levels = FIG_SUBSURF_RENDER

# Apply both modifiers to bake the geometry
bpy.context.view_layer.objects.active = fig
bpy.ops.object.modifier_apply(modifier="Skin")
bpy.ops.object.modifier_apply(modifier="Subsurf")
bpy.ops.object.shade_smooth()


# ─── 5. Material slots — split mesh by region using vertex z + side ─────────

# Append all materials
for m in (mat_skin, mat_hair, mat_shirt, mat_suit, mat_tie, mat_scarf, mat_shoe):
    fig.data.materials.append(m)
slot_idx = {m.name: i for i, m in enumerate(fig.data.materials)}

# Region thresholds (world Z within figure)
HAIR_Z = bz + H * 0.86
HEAD_Z = bz + H * 0.74
SUIT_Z = bz + H * 0.42
HIP_Z = bz + H * 0.42
SHOE_Z = bz + H * 0.04

# Walk faces and assign material by face center Z (and front Y for shirt/tie)
me = fig.data
for f in me.polygons:
    cz = sum(me.vertices[i].co.z for i in f.vertices) / len(f.vertices) + fig.location.z
    cy = sum(me.vertices[i].co.y for i in f.vertices) / len(f.vertices) + fig.location.y
    cx = sum(me.vertices[i].co.x for i in f.vertices) / len(f.vertices) + fig.location.x
    if cz >= HAIR_Z:
        f.material_index = slot_idx["Hair"]
    elif cz >= HEAD_Z:
        f.material_index = slot_idx["Skin"]
    elif cz >= SUIT_Z + 0.005:
        # torso region — front center = shirt + tie + scarf, rest = suit
        if cy < -0.012 and abs(cx) < 0.012:
            f.material_index = slot_idx["Tie"]
        elif cy < -0.010 and abs(cx) < 0.022 and cz < bz + H * 0.70:
            f.material_index = slot_idx["Shirt"]
        elif cy < -0.008 and cz >= bz + H * 0.74 - 0.003 and cz < bz + H * 0.78 and abs(cx) < 0.025:
            f.material_index = slot_idx["Scarf"]
        else:
            f.material_index = slot_idx["Suit"]
    elif cz >= SHOE_Z:
        # legs region — suit color (pants)
        f.material_index = slot_idx["Suit"]
    else:
        # feet
        f.material_index = slot_idx["Shoe"]


# ─── 6. Lighting ─────────────────────────────────────────────────────────────

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


# ─── 7. World ────────────────────────────────────────────────────────────────

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


# ─── 8. Camera ───────────────────────────────────────────────────────────────

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


# ─── 9. Render config ────────────────────────────────────────────────────────

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


# ─── 10. Save + render ───────────────────────────────────────────────────────

bpy.ops.wm.save_as_mainfile(filepath=SAVE_BLEND_PATH)
bpy.ops.render.render(write_still=True)


# ─── 11. Mesh report — for verification ──────────────────────────────────────

fig_mesh = fig.data
__result__ = {
    "figure_object_count": 1,                       # ONE object — connected
    "figure_vertices": len(fig_mesh.vertices),
    "figure_polygons": len(fig_mesh.polygons),
    "figure_materials": len(fig.data.materials),
    "case_panels": len(panels) + 1,                 # 5 walls + base
    "lights": len([o for o in bpy.data.objects if o.type == 'LIGHT']),
    "cameras": len([o for o in bpy.data.objects if o.type == 'CAMERA']),
    "render_path": RENDER_FILEPATH,
    "blend_path": SAVE_BLEND_PATH,
    "resolution": (RENDER_RES_X, RENDER_RES_Y),
}
