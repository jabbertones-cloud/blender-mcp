"""
Perfume Bottle v2 - Complete scene builder.
Sends all commands to running Blender via bridge, saves .blend, then exit.
Render separately via CLI: blender -b /tmp/perfume_v2.blend -o /tmp/perfume_v2_ -f 1
"""
import socket, json, sys, time

def blender(code, timeout=30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(('127.0.0.1', 9876))
    payload = {'id': '1', 'command': 'execute_python', 'params': {'code': code}}
    s.sendall(json.dumps(payload).encode('utf-8'))
    chunks = []
    try:
        while True:
            chunk = s.recv(1048576)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                data = json.loads(b''.join(chunks).decode('utf-8'))
                s.close()
                if 'error' in data and data['error']:
                    return data
                return data.get('result', data)
            except json.JSONDecodeError:
                continue
    except socket.timeout:
        s.close()
        return {'error': 'timeout', 'partial': b''.join(chunks).decode('utf-8', errors='replace')[:500]}
    s.close()
    raw = b''.join(chunks).decode('utf-8', errors='replace')
    try:
        return json.loads(raw)
    except:
        return {'raw': raw[:500]}

def step(name, code):
    print(f"  [{name}]...", end=" ", flush=True)
    r = blender(code)
    if isinstance(r, dict) and 'error' in r:
        print(f"ERROR: {r['error']}")
        if 'traceback' in r:
            print(f"  TB: {r['traceback'][:300]}")
        return False
    print("OK")
    return True

print("=" * 50)
print("PERFUME BOTTLE v2 - Full Scene Build")
print("=" * 50)

# Step 1: Clear
ok = step("CLEAR", """
import bpy
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=True)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
for m in list(bpy.data.materials):
    bpy.data.materials.remove(m)
for i in list(bpy.data.images):
    bpy.data.images.remove(i)
bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
__result__ = {"cleared": True}
""")
if not ok:
    sys.exit(1)

# Step 2: Bottle body via lathe
ok = step("BOTTLE BODY", """
import bpy, math, bmesh

curve_data = bpy.data.curves.new("BottleProfile", type="CURVE")
curve_data.dimensions = "2D"
spline = curve_data.splines.new("BEZIER")

points = [
    (0.0, 0.0),
    (0.32, 0.0),
    (0.38, 0.15),
    (0.35, 0.6),
    (0.28, 1.2),
    (0.18, 1.5),
    (0.12, 1.7),
    (0.10, 1.9),
    (0.10, 2.05),
    (0.0, 2.05),
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
bmesh.ops.spin(bm, geom=bm.verts[:]+bm.edges[:], axis=(0,0,1), cent=(0,0,0), steps=64, angle=math.radians(360))
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.001)
bm.to_mesh(profile_obj.data)
bm.free()

profile_obj.name = "Bottle_Body"
bpy.ops.object.shade_smooth()
sub = profile_obj.modifiers.new("Sub","SUBSURF")
sub.levels = 2
sub.render_levels = 3

__result__ = {"verts": len(profile_obj.data.vertices)}
""")
if not ok:
    sys.exit(1)

# Step 3: Cap + Neck ring + Liquid
ok = step("CAP + LIQUID", """
import bpy, math, bmesh

# Cap - tapered
bpy.ops.mesh.primitive_cylinder_add(radius=0.16, depth=0.5, location=(0,0,2.3), vertices=48)
cap = bpy.context.active_object
cap.name = "Bottle_Cap"
bpy.ops.object.shade_smooth()

bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(cap.data)
bm.verts.ensure_lookup_table()
for v in bm.verts:
    if v.co.z > 0.2:
        factor = 1.0 - (v.co.z - 0.2) * 0.3
        v.co.x *= max(factor, 0.7)
        v.co.y *= max(factor, 0.7)
bmesh.update_edit_mesh(cap.data)
bpy.ops.object.mode_set(mode="OBJECT")

sub = cap.modifiers.new("Sub","SUBSURF"); sub.levels=2; sub.render_levels=3
bev = cap.modifiers.new("Bevel","BEVEL"); bev.width=0.015; bev.segments=4

# Neck ring
bpy.ops.mesh.primitive_torus_add(major_radius=0.13, minor_radius=0.02, location=(0,0,2.05), major_segments=48, minor_segments=12)
ring = bpy.context.active_object
ring.name = "Neck_Ring"
bpy.ops.object.shade_smooth()

# Liquid
bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=1.1, location=(0,0,0.6), vertices=48)
liq = bpy.context.active_object
liq.name = "Liquid"
bpy.ops.object.shade_smooth()
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(liq.data)
bm.verts.ensure_lookup_table()
for v in bm.verts:
    h = v.co.z + 0.55
    if h > 0.7:
        factor = 1.0 - (h - 0.7) * 0.5
        v.co.x *= max(factor, 0.6)
        v.co.y *= max(factor, 0.6)
bmesh.update_edit_mesh(liq.data)
bpy.ops.object.mode_set(mode="OBJECT")

__result__ = {"cap": True, "ring": True, "liquid": True}
""")
if not ok:
    sys.exit(1)

# Step 4: Materials
ok = step("GLASS MATERIAL", """
import bpy

mat = bpy.data.materials.new("PerfumeGlass")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.97, 0.98, 1.0, 1.0)
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.0
bsdf.inputs["Transmission Weight"].default_value = 1.0
bsdf.inputs["IOR"].default_value = 1.52
bsdf.inputs["Coat Weight"].default_value = 1.0
bsdf.inputs["Coat Roughness"].default_value = 0.0
bsdf.inputs["Coat IOR"].default_value = 1.6
bsdf.inputs["Specular IOR Level"].default_value = 0.8

noise = nt.nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 200
noise.inputs["Detail"].default_value = 8
mr = nt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = 0.0
mr.inputs["From Max"].default_value = 1.0
mr.inputs["To Min"].default_value = 0.0
mr.inputs["To Max"].default_value = 0.02
nt.links.new(noise.outputs["Fac"], mr.inputs["Value"])
nt.links.new(mr.outputs["Result"], bsdf.inputs["Roughness"])

bpy.data.objects["Bottle_Body"].data.materials.append(mat)
__result__ = {"ok": True}
""")

ok = step("GOLD + LIQUID MATERIALS", """
import bpy

# Gold
mat_gold = bpy.data.materials.new("GoldCap")
mat_gold.use_nodes = True
b = mat_gold.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.83, 0.69, 0.22, 1.0)
b.inputs["Metallic"].default_value = 1.0
b.inputs["Roughness"].default_value = 0.2
b.inputs["Coat Weight"].default_value = 0.8
b.inputs["Coat Roughness"].default_value = 0.1
b.inputs["Anisotropic"].default_value = 0.3
bpy.data.objects["Bottle_Cap"].data.materials.append(mat_gold)
bpy.data.objects["Neck_Ring"].data.materials.append(mat_gold)

# Liquid
mat_liq = bpy.data.materials.new("AmberLiquid")
mat_liq.use_nodes = True
b = mat_liq.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1.0, 0.7, 0.35, 1.0)
b.inputs["Roughness"].default_value = 0.0
b.inputs["Transmission Weight"].default_value = 0.9
b.inputs["IOR"].default_value = 1.36
b.inputs["Subsurface Weight"].default_value = 0.4
b.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.1)
b.inputs["Subsurface Scale"].default_value = 0.5
bpy.data.objects["Liquid"].data.materials.append(mat_liq)

__result__ = {"gold": True, "liquid": True}
""")

# Step 5: Lighting
ok = step("LIGHTING", """
import bpy, math

# Key - warm, dramatic
bpy.ops.object.light_add(type="AREA", location=(3.0, -2.5, 4.0))
k = bpy.context.active_object; k.name="Key"
k.data.energy = 200; k.data.size = 1.5; k.data.color = (1.0, 0.95, 0.9)
k.rotation_euler = (math.radians(55), math.radians(5), math.radians(30))

# Fill - cool, soft
bpy.ops.object.light_add(type="AREA", location=(-3.5, 2.0, 2.0))
f = bpy.context.active_object; f.name="Fill"
f.data.energy = 40; f.data.size = 4.0; f.data.color = (0.9, 0.92, 1.0)
f.rotation_euler = (math.radians(60), 0, math.radians(-140))

# Rim - tight, punchy, behind
bpy.ops.object.light_add(type="AREA", location=(-0.5, -4.0, 5.0))
r = bpy.context.active_object; r.name="Rim"
r.data.energy = 350; r.data.size = 0.5; r.data.color = (1.0, 1.0, 1.0)
r.rotation_euler = (math.radians(25), 0, math.radians(-175))

# Bottom fill for glass
bpy.ops.object.light_add(type="AREA", location=(0, 2.0, -0.3))
bf = bpy.context.active_object; bf.name="BottomFill"
bf.data.energy = 30; bf.data.size = 3.0
bf.rotation_euler = (math.radians(-90), 0, 0)

__result__ = {"lights": 4}
""")

# Step 6: Cyclorama
ok = step("CYCLORAMA", """
import bpy, bmesh

bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 3, 0))
ground = bpy.context.active_object
ground.name = "Cyclorama"

bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(ground.data)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=20)
bmesh.update_edit_mesh(ground.data)
bpy.ops.object.mode_set(mode="OBJECT")

for v in ground.data.vertices:
    y = v.co.y
    if y > 1.0:
        v.co.z += (y - 1.0) ** 1.5 * 0.4
bpy.ops.object.shade_smooth()

mat = bpy.data.materials.new("CycMat")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.93, 0.96, 1.0)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
ground.data.materials.append(mat)

__result__ = {"cyclorama": True}
""")

# Step 7: World
ok = step("WORLD", """
import bpy

world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()

tc = nt.nodes.new("ShaderNodeTexCoord")
mp = nt.nodes.new("ShaderNodeMapping")
gr = nt.nodes.new("ShaderNodeTexGradient")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.3
ramp.color_ramp.elements[0].color = (0.92, 0.90, 0.95, 1.0)
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (0.80, 0.78, 0.85, 1.0)

bg = nt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 0.8
out = nt.nodes.new("ShaderNodeOutputWorld")

nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], gr.inputs["Vector"])
nt.links.new(gr.outputs["Color"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

__result__ = {"world": True}
""")

# Step 8: Camera + Render settings
ok = step("CAMERA + RENDER", """
import bpy, math, mathutils

bpy.ops.object.camera_add(location=(2.8, -3.0, 0.8))
cam = bpy.context.active_object
cam.name = "HeroCam"
cam.data.lens = 85
cam.data.sensor_width = 36

target = mathutils.Vector((0, 0, 1.0))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 1.8
cam.data.dof.focus_distance = direction.length
bpy.context.scene.camera = cam

s = bpy.context.scene
s.render.engine = "CYCLES"
s.cycles.device = "GPU"
s.cycles.samples = 256
s.cycles.use_denoising = True
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.01
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 50
s.render.image_settings.file_format = "PNG"
s.render.filepath = "/tmp/perfume_v2"
s.view_settings.view_transform = "AgX"

__result__ = {"camera": True, "engine": "CYCLES", "samples": 256}
""")

# Step 9: Save
ok = step("SAVE BLEND", """
import bpy, os
bpy.ops.wm.save_as_mainfile(filepath="/tmp/perfume_v2.blend")
__result__ = {"saved": os.path.exists("/tmp/perfume_v2.blend")}
""")

print("\n" + "=" * 50)
print("Scene built and saved to /tmp/perfume_v2.blend")
print("Render with:")
print("  /Applications/Blender.app/Contents/MacOS/Blender -b /tmp/perfume_v2.blend -o /tmp/perfume_v2_ -f 1")
print("=" * 50)
