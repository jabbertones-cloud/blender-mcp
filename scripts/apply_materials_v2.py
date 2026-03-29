"""Apply v2 materials to perfume bottle scene via bridge."""
import socket, json

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
                return data
            except json.JSONDecodeError:
                continue
    except socket.timeout:
        pass
    s.close()
    raw = b''.join(chunks).decode('utf-8', errors='replace')
    try:
        return json.loads(raw)
    except:
        return {'raw': raw[:1000]}

# ===== GLASS MATERIAL =====
r1 = blender("""
import bpy

mat_glass = bpy.data.materials.new("PerfumeGlass")
mat_glass.use_nodes = True
nt = mat_glass.node_tree
nodes = nt.nodes
links = nt.links

bsdf = nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.97, 0.98, 1.0, 1.0)
bsdf.inputs["Metallic"].default_value = 0.0
bsdf.inputs["Roughness"].default_value = 0.0
bsdf.inputs["Transmission Weight"].default_value = 1.0
bsdf.inputs["IOR"].default_value = 1.52
bsdf.inputs["Coat Weight"].default_value = 1.0
bsdf.inputs["Coat Roughness"].default_value = 0.0
bsdf.inputs["Coat IOR"].default_value = 1.6
bsdf.inputs["Specular IOR Level"].default_value = 0.8

# Subtle noise for surface imperfection
noise = nodes.new("ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 200
noise.inputs["Detail"].default_value = 8
noise.inputs["Roughness"].default_value = 0.6

map_range = nodes.new("ShaderNodeMapRange")
map_range.inputs["From Min"].default_value = 0.0
map_range.inputs["From Max"].default_value = 1.0
map_range.inputs["To Min"].default_value = 0.0
map_range.inputs["To Max"].default_value = 0.02

links.new(noise.outputs["Fac"], map_range.inputs["Value"])
links.new(map_range.outputs["Result"], bsdf.inputs["Roughness"])

bpy.data.objects["Bottle_Body"].data.materials.append(mat_glass)

__result__ = {"glass": "applied"}
""")
print("Glass:", r1)

# ===== GOLD CAP =====
r2 = blender("""
import bpy

mat_gold = bpy.data.materials.new("GoldCap")
mat_gold.use_nodes = True
nt = mat_gold.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.83, 0.69, 0.22, 1.0)
bsdf.inputs["Metallic"].default_value = 1.0
bsdf.inputs["Roughness"].default_value = 0.2
bsdf.inputs["Coat Weight"].default_value = 0.8
bsdf.inputs["Coat Roughness"].default_value = 0.1
bsdf.inputs["Anisotropic"].default_value = 0.3

bpy.data.objects["Bottle_Cap"].data.materials.append(mat_gold)
bpy.data.objects["Neck_Ring"].data.materials.append(mat_gold)

__result__ = {"gold": "applied"}
""")
print("Gold:", r2)

# ===== AMBER LIQUID =====
r3 = blender("""
import bpy

mat_liq = bpy.data.materials.new("AmberLiquid")
mat_liq.use_nodes = True
nt = mat_liq.node_tree
bsdf = nt.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1.0, 0.7, 0.35, 1.0)
bsdf.inputs["Roughness"].default_value = 0.0
bsdf.inputs["Transmission Weight"].default_value = 0.9
bsdf.inputs["IOR"].default_value = 1.36
bsdf.inputs["Subsurface Weight"].default_value = 0.4
bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.4, 0.1)
bsdf.inputs["Subsurface Scale"].default_value = 0.5

bpy.data.objects["Liquid"].data.materials.append(mat_liq)

__result__ = {"liquid": "applied"}
""")
print("Liquid:", r3)

# ===== LIGHTING + ENVIRONMENT =====
r4 = blender("""
import bpy, math

# Key light - dramatic, slightly warm
bpy.ops.object.light_add(type="AREA", location=(3.0, -2.5, 4.0))
key = bpy.context.active_object
key.name = "Key"
key.data.energy = 200
key.data.size = 1.5
key.data.color = (1.0, 0.95, 0.9)
key.rotation_euler = (math.radians(55), math.radians(5), math.radians(30))

# Fill - cool, very soft, lower
bpy.ops.object.light_add(type="AREA", location=(-3.5, 2.0, 2.0))
fill = bpy.context.active_object
fill.name = "Fill"
fill.data.energy = 40
fill.data.size = 4.0
fill.data.color = (0.9, 0.92, 1.0)
fill.rotation_euler = (math.radians(60), 0, math.radians(-140))

# Rim - tight, strong, behind and above
bpy.ops.object.light_add(type="AREA", location=(-0.5, -4.0, 5.0))
rim = bpy.context.active_object
rim.name = "Rim"
rim.data.energy = 350
rim.data.size = 0.5
rim.data.color = (1.0, 1.0, 1.0)
rim.rotation_euler = (math.radians(25), 0, math.radians(-175))

# Bottom fill - subtle uplight for glass caustic feel
bpy.ops.object.light_add(type="AREA", location=(0, 2.0, -0.3))
bottom = bpy.context.active_object
bottom.name = "BottomFill"
bottom.data.energy = 30
bottom.data.size = 3.0
bottom.rotation_euler = (math.radians(-90), 0, 0)

# Ground - curved cyclorama (bent plane)
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 3, 0))
ground = bpy.context.active_object
ground.name = "Cyclorama"

# Add loop cuts and bend the back up
import bmesh
bpy.ops.object.mode_set(mode="EDIT")
bm = bmesh.from_edit_mesh(ground.data)
# Subdivide for bending
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=20)
bmesh.update_edit_mesh(ground.data)
bpy.ops.object.mode_set(mode="OBJECT")

# Bend back vertices upward for seamless curve
for v in ground.data.vertices:
    y = v.co.y
    if y > 1.0:
        curve_amount = (y - 1.0) ** 1.5 * 0.4
        v.co.z += curve_amount

bpy.ops.object.shade_smooth()

mat_cyc = bpy.data.materials.new("CycMat")
mat_cyc.use_nodes = True
bsdf = mat_cyc.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.95, 0.93, 0.96, 1.0)
bsdf.inputs["Roughness"].default_value = 0.6
ground.data.materials.append(mat_cyc)

# World - HDRI-like gradient
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
nt.nodes.clear()

texcoord = nt.nodes.new("ShaderNodeTexCoord")
mapping = nt.nodes.new("ShaderNodeMapping")
gradient = nt.nodes.new("ShaderNodeTexGradient")
ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].position = 0.3
ramp.color_ramp.elements[0].color = (0.92, 0.90, 0.95, 1.0)
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (0.80, 0.78, 0.85, 1.0)

bg = nt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 0.8
output = nt.nodes.new("ShaderNodeOutputWorld")

nt.links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
nt.links.new(mapping.outputs["Vector"], gradient.inputs["Vector"])
nt.links.new(gradient.outputs["Color"], ramp.inputs["Fac"])
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
nt.links.new(bg.outputs["Background"], output.inputs["Surface"])

__result__ = {"lights": 4, "cyclorama": True, "world": True}
""")
print("Lighting:", r4)

# ===== CAMERA =====
r5 = blender("""
import bpy, math, mathutils

# Low dramatic angle - hero shot
bpy.ops.object.camera_add(location=(2.8, -3.0, 0.8))
cam = bpy.context.active_object
cam.name = "HeroCam"
cam.data.lens = 85  # portrait lens, tighter
cam.data.sensor_width = 36

# Point at bottle center
target = mathutils.Vector((0, 0, 1.0))
direction = target - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

# DOF
cam.data.dof.use_dof = True
cam.data.dof.aperture_fstop = 1.8
cam.data.dof.focus_distance = direction.length

bpy.context.scene.camera = cam

# Render settings - Cycles for proper glass
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "GPU"
scene.cycles.samples = 256
scene.cycles.use_denoising = True
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.01
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 50  # half res for speed
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = "/tmp/perfume_v2"

# Color management
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"

# Film
scene.render.film_transparent = False

__result__ = {"camera": "HeroCam", "lens": 85, "samples": 256, "ready": True}
""")
print("Camera:", r5)
