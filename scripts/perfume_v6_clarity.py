"""
Perfume Bottle v6 - Clarity & Polish
Research-driven fixes for ALL v5 flaws:
  1. Glass Volume Absorption density 0.05->0.008, color near-white (was too dark/green)
  2. Coat Weight removed (was 0.3, dimming transmission)
  3. Liquid Volume Absorption density 2.0->0.6, color lightened (was too opaque)
  4. Noise texture on roughness removed (0.005 max was imperceptible)
  5. Resolution 75%->100% (full 1920x1080)
  6. Samples 512->1024 for cleaner glass convergence
  7. Clamp indirect set to 10 (0=fireflies, too high=dark glass)
  8. Gradient backdrop for professional studio look
  9. Light blocker repositioned + sized for better edge definition
  10. Backlight boosted for liquid glow-through
  11. Added second rim light for symmetrical edge highlights
  12. Floor material slightly more reflective for product photography feel

Sources:
  - renderguide.com: glass IOR 1.5, transmission 1.0, roughness 0.0, Volume Absorption for tint
  - gregzaal.com: liquid overlap method, IOR 1.33 for water-like liquids
  - blenderartists.org: clamp=0 helps dark glass, Light Path trick for shadows
  - creativeshrimp.com: uber glass = principled + volume absorption + transparent shadow mix
  - vagon.io: 3-point lighting + rim for glass edge definition + light blockers

Run: blender -b -P perfume_v6_clarity.py
Then: blender -b /tmp/perfume_v6.blend -o /tmp/perfume_v6_ -f 1 -- --cycles-device CPU
"""
import bpy
import bmesh
import math
import mathutils
import os

print("=" * 60)
print("PERFUME BOTTLE v6 - Clarity & Polish")
print("=" * 60)

# ===== CLEAR =====
print("[1/13] Clearing scene...")
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
print("[2/13] Building bottle body (lathe + solidify for wall thickness)...")
curve_data = bpy.data.curves.new("BottleProfile", type="CURVE")
curve_data.dimensions = "2D"
spline = curve_data.splines.new("BEZIER")

# Slightly refined profile with smoother shoulder transition
points = [
    (0.0,  0.0),
    (0.30, 0.0),
    (0.36, 0.05),
    (0.38, 0.20),
    (0.375, 0.40),
    (0.37, 0.55),
    (0.355, 0.75),
    (0.33, 0.90),
    (0.28, 1.10),
    (0.20, 1.30),
    (0.14, 1.50),
    (0.10, 1.65),
    (0.09, 1.75),
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

# Solidify for real wall thickness (essential for correct refraction + volume absorption)
solidify = profile_obj.modifiers.new("Solidify", "SOLIDIFY")
solidify.thickness = 0.025
solidify.offset = -1
solidify.use_quality_normals = True

sub = profile_obj.modifiers.new("Sub", "SUBSURF")
sub.levels = 2
sub.render_levels = 3

profile_obj.cycles.is_caustics_caster = True
print(f"  Body: {len(profile_obj.data.vertices)} verts + Solidify + Shadow Caustics")

# ===== CAP =====
print("[3/13] Building cap + ring + liquid...")
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

# ===== GLASS MATERIAL (v6: FIXED for clarity) =====
print("[4/13] Glass material (v6: reduced absorption, no coat, transparent shadow mix)...")
mat_glass = bpy.data.materials.new("PerfumeGlass")
mat_glass.use_nodes = True
nt = mat_glass.node_tree
for node in list(nt.nodes):
    nt.nodes.remove(node)

mat_output = nt.nodes.new("ShaderNodeOutputMaterial")
mat_output.location = (600, 0)

principled = nt.nodes.new("ShaderNodeBsdfPrincipled")
principled.location = (0, 200)
principled.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
principled.inputs["Metallic"].default_value = 0.0
principled.inputs["Roughness"].default_value = 0.0
principled.inputs["Transmission Weight"].default_value = 1.0
principled.inputs["IOR"].default_value = 1.5
principled.inputs["Specular IOR Level"].default_value = 0.5
# v6 FIX: Coat Weight 0.0 (was 0.3 in v5, dimming transmission)
principled.inputs["Coat Weight"].default_value = 0.0
principled.inputs["Coat Roughness"].default_value = 0.0

# Transparent BSDF for clean shadow rays
transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
transparent.location = (0, -100)

light_path = nt.nodes.new("ShaderNodeLightPath")
light_path.location = (-200, -200)

mix = nt.nodes.new("ShaderNodeMixShader")
mix.location = (300, 0)
nt.links.new(light_path.outputs["Is Shadow Ray"], mix.inputs["Fac"])
nt.links.new(principled.outputs["BSDF"], mix.inputs[1])
nt.links.new(transparent.outputs["BSDF"], mix.inputs[2])
nt.links.new(mix.outputs["Shader"], mat_output.inputs["Surface"])

# v6 FIX: Volume Absorption near-zero density for CLEAR glass
vol_absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
vol_absorb.location = (300, -200)
vol_absorb.inputs["Color"].default_value = (0.97, 0.98, 0.97, 1.0)
vol_absorb.inputs["Density"].default_value = 0.008
nt.links.new(vol_absorb.outputs["Volume"], mat_output.inputs["Volume"])

# v6: REMOVED noise texture on roughness (imperceptible at 0.005 max)

bpy.data.objects["Bottle_Body"].data.materials.append(mat_glass)

# ===== GOLD MATERIAL =====
print("[5/13] Gold + Liquid materials...")
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

# ===== LIQUID MATERIAL (v6: FIXED lighter, more translucent) =====
print("[6/13] Liquid material (v6: lighter amber, reduced absorption density)...")
mat_liq = bpy.data.materials.new("AmberLiquid")
mat_liq.use_nodes = True
lnt = mat_liq.node_tree
lb = lnt.nodes["Principled BSDF"]
lb.inputs["Base Color"].default_value = (1.0, 0.85, 0.55, 1.0)
lb.inputs["Roughness"].default_value = 0.0
lb.inputs["Transmission Weight"].default_value = 1.0
lb.inputs["IOR"].default_value = 1.36
lb.inputs["Specular IOR Level"].default_value = 0.5

# v6 FIX: density 2.0 was making liquid opaque
liq_vol = lnt.nodes.new("ShaderNodeVolumeAbsorption")
liq_vol.inputs["Color"].default_value = (1.0, 0.72, 0.35, 1.0)
liq_vol.inputs["Density"].default_value = 0.6
liq_output = lnt.nodes["Material Output"]
lnt.links.new(liq_vol.outputs["Volume"], liq_output.inputs["Volume"])
bpy.data.objects["Liquid"].data.materials.append(mat_liq)

# ===== STUDIO FLOOR + GRADIENT BACKDROP =====
print("[7/13] Studio floor + gradient backdrop...")
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "StudioFloor"
bpy.ops.object.shade_smooth()
floor.cycles.is_caustics_receiver = True

mat_floor = bpy.data.materials.new("StudioFloor")
mat_floor.use_nodes = True
fb = mat_floor.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.92, 0.92, 0.93, 1.0)
fb.inputs["Roughness"].default_value = 0.08
fb.inputs["Specular IOR Level"].default_value = 0.5
floor.data.materials.append(mat_floor)

# v6 NEW: Gradient backdrop
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 6, 5))
backdrop = bpy.context.active_object
backdrop.name = "Backdrop"
backdrop.rotation_euler = (math.radians(70), 0, 0)
bpy.ops.object.shade_smooth()

mat_backdrop = bpy.data.materials.new("GradientBackdrop")
mat_backdrop.use_nodes = True
bnt = mat_backdrop.node_tree
bb = bnt.nodes["Principled BSDF"]
bb.inputs["Roughness"].default_value = 1.0

tex_coord = bnt.nodes.new("ShaderNodeTexCoord")
tex_coord.location = (-600, 0)
gradient = bnt.nodes.new("ShaderNodeTexGradient")
gradient.location = (-400, 0)
gradient.gradient_type = "LINEAR"
color_ramp = bnt.nodes.new("ShaderNodeValToRGB")
color_ramp.location = (-200, 0)
color_ramp.color_ramp.elements[0].position = 0.2
color_ramp.color_ramp.elements[0].color = (0.75, 0.75, 0.78, 1.0)
color_ramp.color_ramp.elements[1].position = 0.9
color_ramp.color_ramp.elements[1].color = (0.45, 0.45, 0.50, 1.0)

bnt.links.new(tex_coord.outputs["UV"], gradient.inputs["Vector"])
bnt.links.new(gradient.outputs["Color"], color_ramp.inputs["Fac"])
bnt.links.new(color_ramp.outputs["Color"], bb.inputs["Base Color"])
backdrop.data.materials.append(mat_backdrop)
backdrop.visible_glossy = False

# ===== LIGHT BLOCKERS (v6: repositioned) =====
print("[8/13] Light blockers (v6: repositioned, larger)...")
bpy.ops.mesh.primitive_plane_add(size=5, location=(-2.0, -0.5, 1.8))
blocker_l = bpy.context.active_object
blocker_l.name = "LightBlocker_Left"
blocker_l.rotation_euler = (math.radians(85), math.radians(10), math.radians(-20))
mat_black = bpy.data.materials.new("BlackCard")
mat_black.use_nodes = True
mat_black.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.02, 0.02, 1.0)
mat_black.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
blocker_l.data.materials.append(mat_black)
blocker_l.visible_camera = False

bpy.ops.mesh.primitive_plane_add(size=4, location=(2.5, 1.5, 1.5))
bounce = bpy.context.active_object
bounce.name = "BounceCard_Right"
bounce.rotation_euler = (math.radians(75), 0, math.radians(110))
mat_white = bpy.data.materials.new("WhiteCard")
mat_white.use_nodes = True
mat_white.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1.0)
mat_white.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
bounce.data.materials.append(mat_white)
bounce.visible_camera = False

# v6 NEW: Back flag for dark center line in glass
bpy.ops.mesh.primitive_plane_add(size=1.5, location=(0, 2.0, 1.0))
flag = bpy.context.active_object
flag.name = "BackFlag"
flag.rotation_euler = (math.radians(90), 0, 0)
flag.data.materials.append(mat_black)
flag.visible_camera = False

# ===== WORLD: HDRI =====
print("[9/13] HDRI environment...")
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
bg.inputs["Strength"].default_value = 1.8

out = nt.nodes.new("ShaderNodeOutputWorld")

nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], env_tex.inputs["Vector"])
nt.links.new(env_tex.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ===== LIGHTING (v6: 6 lights) =====
print("[10/13] Studio lighting (6 lights for glass definition)...")

# Key light
bpy.ops.object.light_add(type="AREA", location=(3.5, -2.0, 4.5))
key = bpy.context.active_object; key.name = "Key"
key.data.energy = 800
key.data.size = 3.0
key.data.color = (1.0, 0.97, 0.93)
key.rotation_euler = (math.radians(50), math.radians(5), math.radians(25))

# Fill light
bpy.ops.object.light_add(type="AREA", location=(-4.0, 1.5, 3.0))
fill = bpy.context.active_object; fill.name = "Fill"
fill.data.energy = 300
fill.data.size = 5.0
fill.data.color = (0.92, 0.95, 1.0)
fill.rotation_euler = (math.radians(55), 0, math.radians(-140))

# Rim light LEFT
bpy.ops.object.light_add(type="AREA", location=(-1.5, -3.5, 2.5))
rim_l = bpy.context.active_object; rim_l.name = "RimLeft"
rim_l.data.energy = 1000
rim_l.data.size = 0.8
rim_l.data.color = (1.0, 1.0, 1.0)
rim_l.rotation_euler = (math.radians(40), math.radians(10), math.radians(-170))

# v6 NEW: Rim light RIGHT
bpy.ops.object.light_add(type="AREA", location=(1.5, -3.0, 2.5))
rim_r = bpy.context.active_object; rim_r.name = "RimRight"
rim_r.data.energy = 600
rim_r.data.size = 0.8
rim_r.data.color = (1.0, 1.0, 1.0)
rim_r.rotation_euler = (math.radians(40), math.radians(-10), math.radians(170))

# Top accent
bpy.ops.object.light_add(type="AREA", location=(0, 0, 5.5))
top = bpy.context.active_object; top.name = "TopLight"
top.data.energy = 250
top.data.size = 2.0
top.rotation_euler = (0, 0, 0)

# Backlight for liquid glow
bpy.ops.object.light_add(type="AREA", location=(0, 3.5, 0.8))
back = bpy.context.active_object; back.name = "BackLight"
back.data.energy = 600
back.data.size = 3.0
back.data.color = (1.0, 0.95, 0.88)
back.rotation_euler = (math.radians(80), 0, math.radians(180))

# ===== CAMERA =====
print("[11/13] Camera setup...")
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
print("[12/13] Render settings (v6: full res, 1024 samples, tuned clamp)...")
s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.device = "GPU"
s.cycles.samples = 1024
s.cycles.use_denoising = True
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.003

# v6 FIX: Full resolution
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100

s.render.image_settings.file_format = "PNG"
s.render.filepath = "/tmp/perfume_v6_"
s.view_settings.view_transform = "AgX"
# FIX: Use correct enum value (was "AgX - Medium Contrast" which doesn't exist)
s.view_settings.look = "AgX - Punchy"
s.render.film_transparent = False

# 64 bounces for glass
s.cycles.max_bounces = 64
s.cycles.transparent_max_bounces = 64
s.cycles.transmission_bounces = 64
s.cycles.glossy_bounces = 64
s.cycles.diffuse_bounces = 8
s.cycles.volume_bounces = 8

# v6: Clamp settings
s.cycles.sample_clamp_direct = 0
s.cycles.sample_clamp_indirect = 10

# Caustics
s.cycles.caustics_reflective = True
s.cycles.caustics_refractive = True

# ===== SAVE =====
print("[13/13] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath="/tmp/perfume_v6.blend")

print("\n" + "=" * 60)
print("BUILD COMPLETE - v6 Clarity & Polish")
print(f"  Objects: {len(bpy.data.objects)}")
print(f"  Materials: {len(bpy.data.materials)}")
print("  v6 CHANGES from v5:")
print("    - Glass Volume Absorption: density 0.05->0.008, color near-white")
print("    - Coat Weight: 0.3->0.0 (was dimming glass)")
print("    - Liquid absorption: density 2.0->0.6, lighter amber color")
print("    - Noise texture on roughness: REMOVED (imperceptible)")
print("    - Resolution: 75%->100% (full 1920x1080)")
print("    - Samples: 512->1024, adaptive threshold 0.005->0.003")
print("    - Clamp indirect: 0->10 (prevents fireflies)")
print("    - Gradient backdrop added (professional studio look)")
print("    - 6th light: second rim light for symmetrical glass edges")
print("    - Backlight boosted 400->600W, size 2.5->3.0")
print("    - Floor roughness 0.12->0.08 (more reflective)")
print("    - Back flag card for dark center line in glass")
print("    - AgX Punchy look")
print(f"  Saved: /tmp/perfume_v6.blend")
print("=" * 60)
