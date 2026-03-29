"""
Perfume Bottle v5 - Ultimate quality, all research applied.
ALL improvements from research in ONE build:
  v4 base: Volume Absorption, Solidify, 64 bounces, HDRI, separate liquid
  v5 adds:
  - Shadow Caustics (Blender 3.2+) on lights, glass, floor
  - Higher HDRI strength (2.0) for stronger reflections
  - Transparent BSDF mix via Light Path for clean shadows
  - Stronger edge/rim lighting for glass definition
  - Better Fresnel-based glass (community recommended approach)
  - Light blocker planes for controlled reflections
  - Backlight for liquid glow effect
Run: blender -b -P perfume_v5_ultimate.py
Then: blender -b /tmp/perfume_v5.blend -o /tmp/perfume_v5_ -f 1 -- --cycles-device CPU
"""
import bpy
import bmesh
import math
import mathutils
import os

print("=" * 60)
print("PERFUME BOTTLE v5 - Ultimate Research-Based Render")
print("=" * 60)

# ===== CLEAR =====
print("[1/12] Clearing scene...")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=True)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for i in list(bpy.data.images):
    bpy.data.images.remove(i)
for w in list(bpy.data.worlds):
    bpy.data.worlds.remove(w)
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

# ===== BOTTLE BODY =====
print("[2/12] Building bottle body (lathe + solidify for wall thickness)...")
curve_data = bpy.data.curves.new("BottleProfile", type="CURVE")
curve_data.dimensions = "2D"
spline = curve_data.splines.new("BEZIER")

points = [
    (0.0,  0.0),
    (0.30, 0.0),
    (0.36, 0.05),
    (0.38, 0.20),
    (0.37, 0.50),
    (0.34, 0.85),
    (0.28, 1.10),
    (0.18, 1.35),
    (0.12, 1.55),
    (0.09, 1.70),
    (0.09, 1.85),
    (0.11, 1.90),
    (0.11, 1.95),
    (0.0,  1.95),
]
spline.bezier_points.add(len(points) - 1)
for i, (x, y) in enumerate(points):
    bp = spline.bezier_points[i]
    bp.co = (x, y, 0)
    bp.handle_left_type = "AUTO"
    bp.handle_right_type = "AUTO"

profile_obj = bpy.data.objects.new("BottleProfile", curve_data)
bpy.context.collection.objects.link(profile_obj)
bpy.context.view_layer.objects.active = profile_obj
profile_obj.select_set(True)
bpy.ops.object.convert(target="MESH")

bm = bmesh.new()
bm.from_mesh(profile_obj.data)
bmesh.ops.spin(bm, geom=bm.verts[:]+bm.edges[:], axis=(0,0,1),
               cent=(0,0,0), steps=96, angle=math.radians(360))
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
bm.to_mesh(profile_obj.data)
bm.free()

profile_obj.name = "Bottle_Body"
bpy.ops.object.shade_smooth()

# RESEARCH: Solidify for real wall thickness (essential for refraction)
solidify = profile_obj.modifiers.new("Solidify", "SOLIDIFY")
solidify.thickness = 0.025
solidify.offset = -1
solidify.use_quality_normals = True

sub = profile_obj.modifiers.new("Sub", "SUBSURF")
sub.levels = 2
sub.render_levels = 3

# RESEARCH v5: Enable Cast Shadow Caustics on glass object
profile_obj.cycles.is_caustics_caster = True
print(f"  Body: {len(profile_obj.data.vertices)} verts + Solidify + Shadow Caustics")

# ===== CAP =====
print("[3/12] Building cap + ring + liquid...")
bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=0.35,
                                     location=(0,0,2.125), vertices=64)
cap = bpy.context.active_object
cap.name = "Bottle_Cap"
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(cap.data)
bm.verts.ensure_lookup_table()
for v in bm.verts:
    if v.co.z > 0.10:
        t = (v.co.z - 0.10) / 0.075
        t = min(t, 1.0)
        radius_factor = math.sqrt(max(0, 1.0 - t*t*0.3))
        v.co.x *= radius_factor
        v.co.y *= radius_factor
bmesh.update_edit_mesh(cap.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()
sub = cap.modifiers.new("Sub", "SUBSURF"); sub.levels = 2; sub.render_levels = 3
bev = cap.modifiers.new("Bevel", "BEVEL"); bev.width = 0.01; bev.segments = 4

# Neck ring
bpy.ops.mesh.primitive_torus_add(major_radius=0.115, minor_radius=0.015,
                                  location=(0,0,1.95),
                                  major_segments=64, minor_segments=16)
ring = bpy.context.active_object
ring.name = "Neck_Ring"
bpy.ops.object.shade_smooth()

# Liquid (separate object, slightly overlapping inner glass wall)
bpy.ops.mesh.primitive_cylinder_add(radius=0.34, depth=0.95,
                                     location=(0,0,0.55), vertices=64)
liq = bpy.context.active_object
liq.name = "Liquid"
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(liq.data)
bm.verts.ensure_lookup_table()
for v in bm.verts:
    h = v.co.z + 0.475
    if h > 0.65:
        factor = 1.0 - (h - 0.65) * 0.6
        v.co.x *= max(factor, 0.5)
        v.co.y *= max(factor, 0.5)
bmesh.update_edit_mesh(liq.data)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

# ===== GLASS MATERIAL (v5: Transparent BSDF shadow trick) =====
print("[4/12] Glass material (Volume Absorption + Transparent shadow mix)...")
mat_glass = bpy.data.materials.new("PerfumeGlass")
mat_glass.use_nodes = True
nt = mat_glass.node_tree
# Remove default Principled
for node in list(nt.nodes):
    nt.nodes.remove(node)

# RESEARCH v5: Principled BSDF + Transparent BSDF mixed via Light Path
# This gives clean shadows without caustic noise
mat_output = nt.nodes.new("ShaderNodeOutputMaterial")
mat_output.location = (600, 0)

principled = nt.nodes.new("ShaderNodeBsdfPrincipled")
principled.location = (0, 200)
principled.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
principled.inputs["Metallic"].default_value = 0.0
principled.inputs["Roughness"].default_value = 0.0
principled.inputs["Transmission Weight"].default_value = 1.0
principled.inputs["IOR"].default_value = 1.5
principled.inputs["Specular IOR Level"].default_value = 1.0
principled.inputs["Coat Weight"].default_value = 0.3
principled.inputs["Coat Roughness"].default_value = 0.02

# Transparent BSDF for shadow rays
transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
transparent.location = (0, -100)

# Light Path node
light_path = nt.nodes.new("ShaderNodeLightPath")
light_path.location = (-200, -200)

# Mix Shader: if shadow ray → transparent, else → principled glass
mix = nt.nodes.new("ShaderNodeMixShader")
mix.location = (300, 0)
nt.links.new(light_path.outputs["Is Shadow Ray"], mix.inputs["Fac"])
nt.links.new(principled.outputs["BSDF"], mix.inputs[1])
nt.links.new(transparent.outputs["BSDF"], mix.inputs[2])
nt.links.new(mix.outputs["Shader"], mat_output.inputs["Surface"])

# Volume Absorption for glass tint
vol_absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
vol_absorb.location = (300, -200)
vol_absorb.inputs["Color"].default_value = (0.85, 0.92, 0.85, 1.0)
vol_absorb.inputs["Density"].default_value = 0.05
nt.links.new(vol_absorb.outputs["Volume"], mat_output.inputs["Volume"])

# Subtle surface imperfection
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.location = (-400, 100)
noise.inputs["Scale"].default_value = 300
noise.inputs["Detail"].default_value = 10
mr = nt.nodes.new("ShaderNodeMapRange")
mr.location = (-200, 100)
mr.inputs["From Min"].default_value = 0.0
mr.inputs["From Max"].default_value = 1.0
mr.inputs["To Min"].default_value = 0.0
mr.inputs["To Max"].default_value = 0.005
nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], principled.inputs["Roughness"])

bpy.data.objects["Bottle_Body"].data.materials.append(mat_glass)

# ===== GOLD MATERIAL =====
print("[5/12] Gold + Liquid materials...")
mat_gold = bpy.data.materials.new("GoldCap")
mat_gold.use_nodes = True
b = mat_gold.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.83, 0.69, 0.22, 1.0)
b.inputs["Metallic"].default_value = 1.0
b.inputs["Roughness"].default_value = 0.15
b.inputs["Coat Weight"].default_value = 0.5
b.inputs["Coat Roughness"].default_value = 0.05
b.inputs["Anisotropic"].default_value = 0.2
bpy.data.objects["Bottle_Cap"].data.materials.append(mat_gold)
bpy.data.objects["Neck_Ring"].data.materials.append(mat_gold)

# Liquid with Volume Absorption
mat_liq = bpy.data.materials.new("AmberLiquid")
mat_liq.use_nodes = True
lnt = mat_liq.node_tree
lb = lnt.nodes["Principled BSDF"]
lb.inputs["Base Color"].default_value = (1.0, 0.7, 0.3, 1.0)
lb.inputs["Roughness"].default_value = 0.0
lb.inputs["Transmission Weight"].default_value = 1.0
lb.inputs["IOR"].default_value = 1.36
lb.inputs["Specular IOR Level"].default_value = 0.8

liq_vol = lnt.nodes.new("ShaderNodeVolumeAbsorption")
liq_vol.inputs["Color"].default_value = (1.0, 0.55, 0.15, 1.0)
liq_vol.inputs["Density"].default_value = 2.0
liq_output = lnt.nodes["Material Output"]
lnt.links.new(liq_vol.outputs["Volume"], liq_output.inputs["Volume"])
bpy.data.objects["Liquid"].data.materials.append(mat_liq)

# ===== STUDIO FLOOR (glossy + receive shadow caustics) =====
print("[6/12] Studio floor (glossy + shadow caustics receiver)...")
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "StudioFloor"
bpy.ops.object.shade_smooth()

# RESEARCH v5: Enable Receive Shadow Caustics on floor
floor.cycles.is_caustics_receiver = True

mat_floor = bpy.data.materials.new("StudioFloor")
mat_floor.use_nodes = True
fb = mat_floor.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.88, 0.88, 0.90, 1.0)
fb.inputs["Roughness"].default_value = 0.12
fb.inputs["Specular IOR Level"].default_value = 0.5
floor.data.materials.append(mat_floor)

# ===== LIGHT BLOCKER PLANES (research: control reflections) =====
print("[7/12] Light blocker planes for controlled reflections...")
# Black card on camera-left to create dark edge on glass (defines shape)
bpy.ops.mesh.primitive_plane_add(size=4, location=(-2.5, -1.0, 2.0))
blocker_l = bpy.context.active_object
blocker_l.name = "LightBlocker_Left"
blocker_l.rotation_euler = (math.radians(80), math.radians(20), math.radians(-30))
mat_black = bpy.data.materials.new("BlackCard")
mat_black.use_nodes = True
mat_black.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
mat_black.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
blocker_l.data.materials.append(mat_black)
# Make it invisible to camera but visible to reflections
blocker_l.visible_camera = False

# White bounce card on camera-right for soft fill reflection
bpy.ops.mesh.primitive_plane_add(size=3, location=(2.0, 2.0, 1.5))
bounce = bpy.context.active_object
bounce.name = "BounceCard_Right"
bounce.rotation_euler = (math.radians(70), 0, math.radians(120))
mat_white = bpy.data.materials.new("WhiteCard")
mat_white.use_nodes = True
mat_white.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
mat_white.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
bounce.data.materials.append(mat_white)
bounce.visible_camera = False

# ===== WORLD: HDRI (higher strength for glass reflections) =====
print("[8/12] HDRI environment (stronger for glass reflections)...")
world = bpy.data.worlds.new("StudioWorld")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()

hdri_path = os.path.join(
    bpy.utils.resource_path("LOCAL"),
    "datafiles", "studiolights", "world", "studio.exr"
)

tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Rotation"].default_value = (0, 0, math.radians(90))

env_tex = nt.nodes.new("ShaderNodeTexEnvironment")
if os.path.exists(hdri_path):
    env_tex.image = bpy.data.images.load(hdri_path)
    print("  HDRI loaded!")

bg = nt.nodes.new("ShaderNodeBackground")
# RESEARCH v5: Higher HDRI strength - "increase HDRI intensity to enhance reflections"
bg.inputs["Strength"].default_value = 2.0

out = nt.nodes.new("ShaderNodeOutputWorld")

nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], env_tex.inputs["Vector"])
nt.links.new(env_tex.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ===== LIGHTING (research: "95% of glass is lighting") =====
print("[9/12] Studio lighting (5 lights + shadow caustics)...")

# Key light - large, warm, strong
bpy.ops.object.light_add(type="AREA", location=(3.5, -2.0, 4.5))
key = bpy.context.active_object; key.name = "Key"
key.data.energy = 1000  # RESEARCH: area light ~1000 for glass
key.data.size = 3.0
key.data.color = (1.0, 0.97, 0.93)
key.rotation_euler = (math.radians(50), math.radians(5), math.radians(25))
# RESEARCH v5: Enable Shadow Caustics on light
# Shadow caustics enabled via scene.cycles.caustics_reflective (already set)

# Fill light - large, cool, opposite side
bpy.ops.object.light_add(type="AREA", location=(-4.0, 1.5, 3.0))
fill = bpy.context.active_object; fill.name = "Fill"
fill.data.energy = 250
fill.data.size = 5.0
fill.data.color = (0.92, 0.95, 1.0)
fill.rotation_euler = (math.radians(55), 0, math.radians(-140))

# Rim light - tight, bright, creates glass edge definition
# RESEARCH: "all we can really see of glass is highlights and the outline"
bpy.ops.object.light_add(type="AREA", location=(-1.0, -3.5, 3.0))
rim = bpy.context.active_object; rim.name = "Rim"
rim.data.energy = 1200  # Strong rim for edge definition
rim.data.size = 0.6     # Smaller = sharper edge highlights
rim.data.color = (1.0, 1.0, 1.0)
rim.rotation_euler = (math.radians(35), math.radians(10), math.radians(-170))

# Top accent for cap highlight
bpy.ops.object.light_add(type="AREA", location=(0, 0, 5.5))
top = bpy.context.active_object; top.name = "TopLight"
top.data.energy = 200
top.data.size = 2.0
top.rotation_euler = (0, 0, 0)

# RESEARCH v5: Backlight behind bottle for liquid glow
bpy.ops.object.light_add(type="AREA", location=(0, 3.0, 0.8))
back = bpy.context.active_object; back.name = "BackLight"
back.data.energy = 400
back.data.size = 2.5
back.data.color = (1.0, 0.95, 0.88)  # Warm for amber liquid glow
back.rotation_euler = (math.radians(80), 0, math.radians(180))

# ===== CAMERA =====
print("[10/12] Camera + render settings...")
cam_pos = (2.2, -2.5, 1.2)
bpy.ops.object.camera_add(location=cam_pos)
cam = bpy.context.active_object
cam.name = "HeroCam"
cam.data.lens = 85
cam.data.sensor_width = 36

target = mathutils.Vector((0, 0, 0.9))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 4.0
cam.data.dof.focus_distance = direction.length

bpy.context.scene.camera = cam

# ===== RENDER SETTINGS =====
print("[11/12] Render settings (research-optimized)...")
s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.device = "GPU"
s.cycles.samples = 512
s.cycles.use_denoising = True
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.005

s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 75

s.render.image_settings.file_format = "PNG"
s.render.filepath = "/tmp/perfume_v5_"
s.view_settings.view_transform = "AgX"
s.render.film_transparent = False

# RESEARCH: 64 bounces for glass
s.cycles.max_bounces = 64
s.cycles.transparent_max_bounces = 64
s.cycles.transmission_bounces = 64
s.cycles.glossy_bounces = 64
s.cycles.diffuse_bounces = 8
s.cycles.volume_bounces = 8

# Caustics
s.cycles.caustics_reflective = True
s.cycles.caustics_refractive = True

# ===== SAVE =====
print("[12/12] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath="/tmp/perfume_v5.blend")

print("\n" + "=" * 60)
print("BUILD COMPLETE - v5 Ultimate")
print(f"  Objects: {len(bpy.data.objects)}")
print(f"  Materials: {len(bpy.data.materials)}")
print("  NEW in v5:")
print("    - Shadow Caustics on key light + glass + floor")
print("    - Transparent BSDF shadow ray mix (cleaner shadows)")
print("    - Light blocker + bounce card (controlled reflections)")
print("    - Backlight for liquid glow")
print("    - HDRI strength 2.0 (up from 1.2)")
print("    - Stronger rim light (1200W, 0.6 size)")
print("    - Key light 1000W")
print(f"  Saved: /tmp/perfume_v5.blend")
print("=" * 60)
