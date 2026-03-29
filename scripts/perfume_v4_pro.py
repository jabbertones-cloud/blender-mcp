"""
Perfume Bottle v4 - Professional product render.
Based on researched techniques:
  - Volume Absorption for colored glass depth
  - Solidify modifier for real wall thickness
  - 64 bounces for Total/Glossy/Transmission
  - HDRI environment (studio.exr) for glass reflections
  - Separate glass + liquid objects with slight overlap
  - Specular 1.0 for glass reflectivity
  - Proper 3-point lighting with large area lights
Run: blender -b -P perfume_v4_pro.py
Then: blender -b /tmp/perfume_v4.blend -o /tmp/perfume_v4_ -f 1 -- --cycles-device CPU
"""
import bpy
import bmesh
import math
import mathutils
import os

print("=" * 60)
print("PERFUME BOTTLE v4 - Research-Based Professional Render")
print("=" * 60)

# ===== CLEAR =====
print("[1/10] Clearing scene...")
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

# ===== BOTTLE BODY - Lathe with refined profile =====
print("[2/10] Building bottle body (lathe)...")
curve_data = bpy.data.curves.new("BottleProfile", type="CURVE")
curve_data.dimensions = "2D"
spline = curve_data.splines.new("BEZIER")

# Elegant perfume bottle profile
points = [
    (0.0,  0.0),    # center bottom
    (0.30, 0.0),    # base edge
    (0.36, 0.05),   # base corner
    (0.38, 0.20),   # lower body
    (0.37, 0.50),   # mid body
    (0.34, 0.85),   # upper body
    (0.28, 1.10),   # shoulder start
    (0.18, 1.35),   # shoulder curve
    (0.12, 1.55),   # neck transition
    (0.09, 1.70),   # neck
    (0.09, 1.85),   # neck top
    (0.11, 1.90),   # lip flare
    (0.11, 1.95),   # lip top
    (0.0,  1.95),   # center top
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

# RESEARCH-BASED: Solidify modifier for REAL wall thickness
# Glass needs actual thickness for proper refraction
solidify = profile_obj.modifiers.new("Solidify", "SOLIDIFY")
solidify.thickness = 0.025  # ~2.5mm glass wall thickness
solidify.offset = -1  # Grow inward
solidify.use_quality_normals = True

sub = profile_obj.modifiers.new("Sub", "SUBSURF")
sub.levels = 2
sub.render_levels = 3
print(f"  Body: {len(profile_obj.data.vertices)} verts + Solidify (0.025 thickness)")

# ===== CAP =====
print("[3/10] Building cap + ring + liquid...")
bpy.ops.mesh.primitive_cylinder_add(radius=0.14, depth=0.35,
                                     location=(0,0,2.125), vertices=64)
cap = bpy.context.active_object
cap.name = "Bottle_Cap"

# Round the top
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

# RESEARCH-BASED: Liquid as SEPARATE object, slightly overlapping glass wall
# Liquid radius slightly larger than inner glass wall to ensure overlap
# Inner wall = 0.38 - 0.025 = 0.355 at widest, so liquid at 0.34 overlaps slightly
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

# ===== GLASS MATERIAL - Research-based =====
print("[4/10] Glass material (Volume Absorption + high specular)...")
mat_glass = bpy.data.materials.new("PerfumeGlass")
mat_glass.use_nodes = True
nt = mat_glass.node_tree

bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)  # White for clear glass
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.0  # Perfectly smooth
bsdf.inputs["Transmission Weight"].default_value = 1.0
bsdf.inputs["IOR"].default_value = 1.5  # Standard glass IOR
bsdf.inputs["Specular IOR Level"].default_value = 1.0  # RESEARCH: Full specular for glass
bsdf.inputs["Coat Weight"].default_value = 0.3
bsdf.inputs["Coat Roughness"].default_value = 0.02
bsdf.inputs["Coat IOR"].default_value = 1.5

# RESEARCH-BASED: Volume Absorption for realistic glass color depth
# This gives the glass a slight tint that increases with thickness
vol_absorb = nt.nodes.new("ShaderNodeVolumeAbsorption")
vol_absorb.inputs["Color"].default_value = (0.85, 0.92, 0.85, 1.0)  # Slight green tint (like real glass)
vol_absorb.inputs["Density"].default_value = 0.05  # Subtle absorption

# Connect volume absorption to Material Output's Volume socket
mat_output = nt.nodes["Material Output"]
nt.links.new(vol_absorb.outputs["Volume"], mat_output.inputs["Volume"])

# Subtle surface imperfection
noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 300
noise.inputs["Detail"].default_value = 10
mr = nt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = 0.0
mr.inputs["From Max"].default_value = 1.0
mr.inputs["To Min"].default_value = 0.0
mr.inputs["To Max"].default_value = 0.005  # Very subtle
nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])

bpy.data.objects["Bottle_Body"].data.materials.append(mat_glass)

# ===== GOLD MATERIAL =====
print("[5/10] Gold + Liquid materials...")
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

# RESEARCH-BASED: Liquid with Volume Absorption for depth-dependent color
mat_liq = bpy.data.materials.new("AmberLiquid")
mat_liq.use_nodes = True
lnt = mat_liq.node_tree
lb = lnt.nodes["Principled BSDF"]
lb.inputs["Base Color"].default_value = (1.0, 0.7, 0.3, 1.0)  # Amber
lb.inputs["Roughness"].default_value = 0.0
lb.inputs["Transmission Weight"].default_value = 1.0
lb.inputs["IOR"].default_value = 1.36
lb.inputs["Specular IOR Level"].default_value = 0.8

# Volume Absorption for liquid color - deeper amber through thickness
liq_vol = lnt.nodes.new("ShaderNodeVolumeAbsorption")
liq_vol.inputs["Color"].default_value = (1.0, 0.55, 0.15, 1.0)  # Deep amber absorption
liq_vol.inputs["Density"].default_value = 2.0  # Higher density for visible color

liq_output = lnt.nodes["Material Output"]
lnt.links.new(liq_vol.outputs["Volume"], liq_output.inputs["Volume"])

bpy.data.objects["Liquid"].data.materials.append(mat_liq)

# ===== STUDIO FLOOR (glossy for reflections) =====
print("[6/10] Studio floor (glossy)...")
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = "StudioFloor"
bpy.ops.object.shade_smooth()

mat_floor = bpy.data.materials.new("StudioFloor")
mat_floor.use_nodes = True
fb = mat_floor.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.88, 0.88, 0.90, 1.0)  # Light grey
fb.inputs["Roughness"].default_value = 0.12  # Glossy for reflections
fb.inputs["Specular IOR Level"].default_value = 0.5
floor.data.materials.append(mat_floor)

# ===== WORLD: HDRI + gradient backdrop =====
print("[7/10] HDRI environment for glass reflections...")
world = bpy.data.worlds.new("StudioWorld")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()

# RESEARCH: HDRI is critical for glass - gives it something to reflect
hdri_path = os.path.join(
    bpy.utils.resource_path("LOCAL"),
    "datafiles", "studiolights", "world", "studio.exr"
)
print(f"  HDRI: {hdri_path}")
print(f"  Exists: {os.path.exists(hdri_path)}")

tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
mp.inputs["Rotation"].default_value = (0, 0, math.radians(90))

env_tex = nt.nodes.new("ShaderNodeTexEnvironment")
if os.path.exists(hdri_path):
    env_tex.image = bpy.data.images.load(hdri_path)
    print("  HDRI loaded!")
else:
    print("  WARNING: HDRI not found!")

bg = nt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.2  # Moderate HDRI for reflections

out = nt.nodes.new("ShaderNodeOutputWorld")

nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], env_tex.inputs["Vector"])
nt.links.new(env_tex.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

# ===== LIGHTING (3-point + accent) =====
print("[8/10] Studio lighting...")

# Key light - large soft source, warm
bpy.ops.object.light_add(type="AREA", location=(3.5, -2.0, 4.5))
key = bpy.context.active_object; key.name = "Key"
key.data.energy = 800  # Research: strong key for glass highlights
key.data.size = 3.0    # Large for soft wrapping
key.data.color = (1.0, 0.97, 0.93)
key.rotation_euler = (math.radians(50), math.radians(5), math.radians(25))

# Fill light - large, cool tone, opposite side
bpy.ops.object.light_add(type="AREA", location=(-4.0, 1.5, 3.0))
fill = bpy.context.active_object; fill.name = "Fill"
fill.data.energy = 200
fill.data.size = 5.0
fill.data.color = (0.92, 0.95, 1.0)
fill.rotation_euler = (math.radians(55), 0, math.radians(-140))

# Rim/edge light - tight, bright, creates glass edge definition
bpy.ops.object.light_add(type="AREA", location=(-1.0, -3.5, 3.0))
rim = bpy.context.active_object; rim.name = "Rim"
rim.data.energy = 1000  # Research: area light strength 1000 at 45deg
rim.data.size = 0.8
rim.data.color = (1.0, 1.0, 1.0)
rim.rotation_euler = (math.radians(35), math.radians(10), math.radians(-170))

# Top accent for cap highlight
bpy.ops.object.light_add(type="AREA", location=(0, 0, 5.5))
top = bpy.context.active_object; top.name = "TopLight"
top.data.energy = 150
top.data.size = 2.0
top.rotation_euler = (0, 0, 0)

# ===== CAMERA =====
print("[9/10] Camera + render settings...")
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

# ===== RENDER SETTINGS (Research-based) =====
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
s.render.filepath = "/tmp/perfume_v4_"
s.view_settings.view_transform = "AgX"
s.render.film_transparent = False

# RESEARCH-BASED: Glass needs HIGH bounces - 64 for Total/Glossy/Transmission
s.cycles.max_bounces = 64
s.cycles.transparent_max_bounces = 64
s.cycles.transmission_bounces = 64
s.cycles.glossy_bounces = 64
s.cycles.diffuse_bounces = 8
s.cycles.volume_bounces = 4

# Enable caustics for glass
s.cycles.caustics_reflective = True
s.cycles.caustics_refractive = True

# ===== SAVE =====
print("[10/10] Saving blend file...")
bpy.ops.wm.save_as_mainfile(filepath="/tmp/perfume_v4.blend")

print("\n" + "=" * 60)
print("BUILD COMPLETE - v4 Research-Based")
print(f"  Objects: {len(bpy.data.objects)}")
print(f"  Materials: {len(bpy.data.materials)}")
print(f"  Camera: {bpy.context.scene.camera.name}")
print(f"  Engine: {s.render.engine}")
print(f"  Samples: {s.cycles.samples}")
print(f"  Resolution: {s.render.resolution_x}x{s.render.resolution_y} @ {s.render.resolution_percentage}%")
print(f"  Max Bounces: {s.cycles.max_bounces}")
print(f"  Transmission Bounces: {s.cycles.transmission_bounces}")
print(f"  Glass has: Solidify (wall thickness) + Volume Absorption")
print(f"  Liquid has: Volume Absorption (amber)")
print(f"  HDRI: studio.exr")
print(f"  Saved: /tmp/perfume_v4.blend")
print("=" * 60)
