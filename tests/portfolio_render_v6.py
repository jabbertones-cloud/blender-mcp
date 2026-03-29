#!/usr/bin/env python3
"""Portfolio Scene Renderer v6 — Professional Forensic Quality
Fixes from v5: per-vehicle colors, proper DriverPOV cameras, environment context,
road markings, curbs, Cam_Orbit (not Cam_Wide), glass shards without transmission,
128spl Cycles with denoiser, simplified compositor."""
import socket, json, time, os, subprocess, sys

HOST = "127.0.0.1"
PORT = 9876
LOG = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v6_render_log.txt")
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v6/")
BLEND_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/")
os.makedirs(RENDER_DIR, exist_ok=True)
with open(LOG, "w") as f: f.write("")

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

def bridge(command, params=None, timeout=600):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((HOST, PORT))
    msg = json.dumps({"command": command, "params": params or {}})
    s.sendall(msg.encode() + b"\n")
    data = b""
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk: break
            data += chunk
            try:
                json.loads(data.decode())
                break
            except json.JSONDecodeError:
                continue
        except socket.timeout:
            break
    s.close()
    if data:
        try: return json.loads(data.decode())
        except: return {"error": data[:300].decode()}
    return {"error": "no response"}

def run_py(code, timeout=600):
    return bridge("execute_python", {"code": code}, timeout=timeout)

def forensic(action, params=None, timeout=600):
    return bridge("forensic_scene", {"action": action, **(params or {})}, timeout=timeout)

def render_camera(cam_name, out_path, timeout=900):
    code = f"""
import bpy
cam = bpy.data.objects.get('{cam_name}')
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '{out_path}'
    bpy.ops.render.render(write_still=True)
    __result__ = '{out_path}'
else:
    __result__ = 'CAMERA_NOT_FOUND'
"""
    r = run_py(code, timeout=timeout)
    return r

def clean_scene():
    """Delete all objects and data blocks WITHOUT resetting factory settings (preserves addon socket)."""
    run_py("""
import bpy
# Delete all objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=True)
# Purge orphan data
for block in [bpy.data.meshes, bpy.data.materials, bpy.data.textures,
              bpy.data.images, bpy.data.cameras, bpy.data.lights,
              bpy.data.curves, bpy.data.worlds]:
    for item in block:
        block.remove(item)
__result__ = 'clean'
""")

# ─── RENDER SETTINGS ───
def setup_render_settings():
    run_py("""
import bpy
s = bpy.context.scene
s.render.engine = 'CYCLES'
s.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    prefs.preferences.compute_device_type = 'METAL'
    prefs.preferences.get_devices()
    for d in prefs.preferences.devices:
        d.use = True
s.cycles.samples = 128
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.02
s.cycles.max_bounces = 6
s.cycles.diffuse_bounces = 4
s.cycles.glossy_bounces = 4
s.cycles.transmission_bounces = 1
s.cycles.volume_bounces = 0
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGBA'
s.render.film_transparent = False
s.view_settings.view_transform = 'Filmic'
s.view_settings.look = 'Medium High Contrast'
s.view_settings.exposure = 0.5
__result__ = 'render_settings_ok'
""")

# ─── COMPOSITOR ───
def setup_compositor():
    run_py("""
import bpy
s = bpy.context.scene
s.use_nodes = True
tree = s.node_tree
for n in tree.nodes:
    tree.nodes.remove(n)
rl = tree.nodes.new('CompositorNodeRLayers')
rl.location = (0, 300)
comp = tree.nodes.new('CompositorNodeComposite')
comp.location = (900, 300)
# Glare for slight bloom on lights
glare = tree.nodes.new('CompositorNodeGlare')
glare.glare_type = 'FOG_GLOW'
glare.quality = 'HIGH'
glare.mix = 0.05
glare.threshold = 2.0
glare.location = (300, 300)
# Lens distortion for realism
lens = tree.nodes.new('CompositorNodeLensdist')
lens.inputs['Distort'].default_value = -0.01
lens.inputs['Dispersion'].default_value = 0.005
lens.location = (600, 300)
tree.links.new(rl.outputs['Image'], glare.inputs['Image'])
tree.links.new(glare.outputs['Image'], lens.inputs['Image'])
tree.links.new(lens.outputs['Image'], comp.inputs['Image'])
__result__ = 'compositor_ok'
""")

# ─── VEHICLE COLORS ───
VEHICLE_COLORS = {
    'silver': (0.55, 0.55, 0.58, 1.0),
    'dark_red': (0.45, 0.02, 0.02, 1.0),
    'navy': (0.02, 0.1, 0.35, 1.0),
    'black': (0.03, 0.03, 0.04, 1.0),
    'white': (0.85, 0.85, 0.82, 1.0),
    'dark_green': (0.02, 0.18, 0.05, 1.0),
    'charcoal': (0.08, 0.08, 0.09, 1.0),
    'dark_blue': (0.01, 0.05, 0.25, 1.0),
    'beige': (0.65, 0.55, 0.40, 1.0),
    'maroon': (0.30, 0.02, 0.05, 1.0),
}

def apply_vehicle_color(vehicle_name, color_key):
    """Apply specific color to a named vehicle. Searches exact name and startswith."""
    rgba = VEHICLE_COLORS.get(color_key, VEHICLE_COLORS['silver'])
    r, g, b, a = rgba
    run_py(f"""
import bpy
target = '{vehicle_name}'
rgba = ({r}, {g}, {b}, {a})
found = False
for obj in bpy.data.objects:
    if obj.name == target or obj.name.startswith(target + '.'):
        found = True
        mat = bpy.data.materials.new(name=f'VehiclePaint_{{obj.name}}')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        if bsdf:
            bsdf.inputs['Base Color'].default_value = rgba
            bsdf.inputs['Metallic'].default_value = 0.85
            bsdf.inputs['Roughness'].default_value = 0.15
            bsdf.inputs['Coat Weight'].default_value = 1.0
            bsdf.inputs['Coat Roughness'].default_value = 0.05
        if obj.data and hasattr(obj.data, 'materials'):
            obj.data.materials.clear()
            obj.data.materials.append(mat)
        # Also color child meshes (GLB imports have children)
        for child in obj.children:
            if child.type == 'MESH' and child.data:
                child.data.materials.clear()
                child.data.materials.append(mat)
__result__ = f'colored {{target}} found={{found}}'
""")

# ─── ENVIRONMENT CONTEXT ───
def add_environment_context(scene_type, center, radius):
    """Add buildings, trees around the scene for realism."""
    cx, cy = center
    run_py(f"""
import bpy, random, math
random.seed(42)
cx, cy = {cx}, {cy}
radius = {radius}
# Buildings (6-8) around perimeter
for i in range(8):
    angle = (i / 8) * 2 * math.pi + random.uniform(-0.2, 0.2)
    dist = radius + random.uniform(2, 8)
    bx = cx + math.cos(angle) * dist
    by = cy + math.sin(angle) * dist
    w = random.uniform(4, 10)
    d = random.uniform(4, 8)
    h = random.uniform(6, 18)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(bx, by, h/2))
    bldg = bpy.context.view_layer.objects.active
    bldg.scale = (w, d, h)
    bldg.name = f'Building_{{i}}'
    mat = bpy.data.materials.new(name=f'Bldg_Mat_{{i}}')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    gray = random.uniform(0.3, 0.7)
    if bsdf:
        bsdf.inputs['Base Color'].default_value = (gray, gray*0.95, gray*0.9, 1)
        bsdf.inputs['Roughness'].default_value = 0.85
        # Add noise bump for texture
        tex = mat.node_tree.nodes.new('ShaderNodeTexNoise')
        tex.inputs['Scale'].default_value = random.uniform(15, 40)
        bump = mat.node_tree.nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.15
        mat.node_tree.links.new(tex.outputs['Fac'], bump.inputs['Height'])
        mat.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bldg.data.materials.append(mat)
    # Windows (dark rectangles on facade)
    win_mat = bpy.data.materials.new(name=f'Window_{{i}}')
    win_mat.use_nodes = True
    wn = win_mat.node_tree.nodes.get('Principled BSDF')
    if wn:
        wn.inputs['Base Color'].default_value = (0.1, 0.12, 0.18, 1)
        wn.inputs['Roughness'].default_value = 0.1
        wn.inputs['Metallic'].default_value = 0.3
    floors = int(h / 3.0)
    for fl in range(floors):
        for wi in range(max(1, int(w / 3))):
            wx = bx - w/2 + 1.5 + wi * 2.5
            wz = 2.0 + fl * 3.0
            bpy.ops.mesh.primitive_cube_add(size=1, location=(wx, by + d/2 + 0.01, wz))
            win = bpy.context.view_layer.objects.active
            win.scale = (1.0, 0.02, 1.2)
            win.name = f'Window_{{i}}_{{fl}}_{{wi}}'
            win.data.materials.append(win_mat)
# Trees (10-12) scattered
for i in range(12):
    angle = random.uniform(0, 2 * math.pi)
    dist = radius + random.uniform(1, 12)
    tx = cx + math.cos(angle) * dist
    ty = cy + math.sin(angle) * dist
    # Trunk
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=3, location=(tx, ty, 1.5))
    trunk = bpy.context.view_layer.objects.active
    trunk.name = f'TreeTrunk_{{i}}'
    tmat = bpy.data.materials.new(name=f'Bark_{{i}}')
    tmat.use_nodes = True
    tb = tmat.node_tree.nodes.get('Principled BSDF')
    if tb:
        tb.inputs['Base Color'].default_value = (0.25, 0.15, 0.08, 1)
        tb.inputs['Roughness'].default_value = 0.95
    trunk.data.materials.append(tmat)
    # Canopy
    bpy.ops.mesh.primitive_uv_sphere_add(radius=random.uniform(1.5, 3.0), location=(tx, ty, 3.5 + random.uniform(0, 1)))
    canopy = bpy.context.view_layer.objects.active
    canopy.name = f'TreeCanopy_{{i}}'
    lmat = bpy.data.materials.new(name=f'Leaf_{{i}}')
    lmat.use_nodes = True
    lb = lmat.node_tree.nodes.get('Principled BSDF')
    if lb:
        g = random.uniform(0.15, 0.35)
        lb.inputs['Base Color'].default_value = (0.05, g, 0.03, 1)
        lb.inputs['Roughness'].default_value = 0.7
    canopy.data.materials.append(lmat)
__result__ = 'environment_ok'
""")

# ─── ROAD MARKINGS ───
def add_road_markings(road_type, road_length, lane_width=3.5, lanes=4):
    """Yellow dashed center line + white edge lines."""
    run_py(f"""
import bpy
road_length = {road_length}
lane_width = {lane_width}
lanes = {lanes}
road_width = lane_width * lanes
# Yellow center dashes
y_mat = bpy.data.materials.new(name='YellowLine')
y_mat.use_nodes = True
yb = y_mat.node_tree.nodes.get('Principled BSDF')
if yb:
    yb.inputs['Base Color'].default_value = (0.8, 0.65, 0.0, 1)
    yb.inputs['Roughness'].default_value = 0.6
dash_len = 3.0
gap = 10.0
x = -road_length / 2
while x < road_length / 2:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x + dash_len/2, 0, 0.005))
    d = bpy.context.view_layer.objects.active
    d.scale = (dash_len, 0.12, 0.005)
    d.name = 'CenterDash'
    d.data.materials.append(y_mat)
    x += dash_len + gap
# White edge lines
w_mat = bpy.data.materials.new(name='WhiteLine')
w_mat.use_nodes = True
wb = w_mat.node_tree.nodes.get('Principled BSDF')
if wb:
    wb.inputs['Base Color'].default_value = (0.9, 0.9, 0.9, 1)
    wb.inputs['Roughness'].default_value = 0.5
for side in [-1, 1]:
    edge_y = side * road_width / 2
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, edge_y, 0.005))
    el = bpy.context.view_layer.objects.active
    el.scale = (road_length, 0.12, 0.005)
    el.name = 'EdgeLine'
    el.data.materials.append(w_mat)
__result__ = 'road_markings_ok'
""")

# ─── CURBS AND SIDEWALKS ───
def add_curbs_and_sidewalks(road_length, road_width):
    run_py(f"""
import bpy
rl = {road_length}
rw = {road_width}
# Concrete material
c_mat = bpy.data.materials.new(name='Concrete')
c_mat.use_nodes = True
cb = c_mat.node_tree.nodes.get('Principled BSDF')
if cb:
    cb.inputs['Base Color'].default_value = (0.6, 0.58, 0.55, 1)
    cb.inputs['Roughness'].default_value = 0.9
    tex = c_mat.node_tree.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = 30
    bump = c_mat.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.1
    c_mat.node_tree.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    c_mat.node_tree.links.new(bump.outputs['Normal'], cb.inputs['Normal'])
for side in [-1, 1]:
    y = side * (rw / 2 + 0.15)
    # Curb
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, 0.075))
    curb = bpy.context.view_layer.objects.active
    curb.scale = (rl, 0.3, 0.15)
    curb.name = 'Curb_L' if side < 0 else 'Curb_R'
    curb.data.materials.append(c_mat)
    # Sidewalk
    sw_y = side * (rw / 2 + 2.0)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, sw_y, 0.01))
    sw = bpy.context.view_layer.objects.active
    sw.scale = (rl, 3.0, 0.02)
    sw.name = 'Sidewalk_L' if side < 0 else 'Sidewalk_R'
    sw.data.materials.append(c_mat)
__result__ = 'curbs_ok'
""")

# ─── STREET LIGHTS ───
def add_street_lights(positions):
    """Place street light poles with area lights at given (x,y) positions."""
    pos_str = str(positions)
    run_py(f"""
import bpy, math
positions = {pos_str}
pole_mat = bpy.data.materials.new(name='MetalPole')
pole_mat.use_nodes = True
pb = pole_mat.node_tree.nodes.get('Principled BSDF')
if pb:
    pb.inputs['Base Color'].default_value = (0.3, 0.3, 0.32, 1)
    pb.inputs['Metallic'].default_value = 0.9
    pb.inputs['Roughness'].default_value = 0.4
for i, (px, py) in enumerate(positions):
    # Vertical pole
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=6, location=(px, py, 3))
    pole = bpy.context.view_layer.objects.active
    pole.name = f'LightPole_{{i}}'
    pole.data.materials.append(pole_mat)
    # Horizontal arm
    bpy.ops.mesh.primitive_cylinder_add(radius=0.04, depth=2, location=(px, py + 1, 5.8))
    arm = bpy.context.view_layer.objects.active
    arm.rotation_euler = (0, math.radians(90), 0)
    arm.name = f'LightArm_{{i}}'
    arm.data.materials.append(pole_mat)
    # Area light
    bpy.ops.object.light_add(type='AREA', location=(px, py + 1.8, 5.6))
    light = bpy.context.view_layer.objects.active
    light.name = f'StreetLight_{{i}}'
    light.data.energy = 500
    light.data.size = 0.5
    light.data.color = (1.0, 0.95, 0.85)
    light.rotation_euler = (math.radians(90), 0, 0)
__result__ = 'street_lights_ok'
""")

# ─── STOP SIGNS ───
def add_stop_signs(positions_and_rotations):
    """Place stop signs. Each entry: (x, y, rotation_z_degrees)."""
    data_str = str(positions_and_rotations)
    run_py(f"""
import bpy, math
data = {data_str}
red_mat = bpy.data.materials.new(name='StopSignRed')
red_mat.use_nodes = True
rb = red_mat.node_tree.nodes.get('Principled BSDF')
if rb:
    rb.inputs['Base Color'].default_value = (0.8, 0.02, 0.02, 1)
    rb.inputs['Roughness'].default_value = 0.3
for i, (sx, sy, rot) in enumerate(data):
    # Post
    bpy.ops.mesh.primitive_cylinder_add(radius=0.05, depth=2.5, location=(sx, sy, 1.25))
    post = bpy.context.view_layer.objects.active
    post.name = f'StopPost_{{i}}'
    post.data.materials.append(bpy.data.materials.get('MetalPole') or red_mat)
    # Octagon sign
    bpy.ops.mesh.primitive_circle_add(vertices=8, radius=0.35, fill_type='NGON', location=(sx, sy, 2.6))
    sign = bpy.context.view_layer.objects.active
    sign.name = f'StopSign_{{i}}'
    sign.rotation_euler = (math.radians(90), 0, math.radians(rot))
    sign.data.materials.append(red_mat)
__result__ = 'stop_signs_ok'
""")

# ─── TRAFFIC LIGHTS ───
def add_traffic_light(position, rotation_z=0):
    px, py = position
    run_py(f"""
import bpy, math
px, py, rz = {px}, {py}, {rotation_z}
# Housing
box_mat = bpy.data.materials.new(name='TrafficBox')
box_mat.use_nodes = True
bb = box_mat.node_tree.nodes.get('Principled BSDF')
if bb:
    bb.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1)
    bb.inputs['Metallic'].default_value = 0.8
# Pole
bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=4.5, location=(px, py, 2.25))
pole = bpy.context.view_layer.objects.active
pole.name = 'TL_Pole'
pole.data.materials.append(box_mat)
# Housing box
bpy.ops.mesh.primitive_cube_add(size=1, location=(px, py, 4.8))
housing = bpy.context.view_layer.objects.active
housing.scale = (0.25, 0.25, 0.6)
housing.name = 'TL_Housing'
housing.rotation_euler = (0, 0, math.radians(rz))
housing.data.materials.append(box_mat)
# Lights (red=top, yellow=mid, green=bottom)
colors = [(0.9, 0.05, 0.05), (0.9, 0.7, 0.0), (0.05, 0.8, 0.1)]
offsets = [0.35, 0, -0.35]
for ci, (col, oz) in enumerate(zip(colors, offsets)):
    emit_mat = bpy.data.materials.new(name=f'TL_Light_{{ci}}')
    emit_mat.use_nodes = True
    eb = emit_mat.node_tree.nodes.get('Principled BSDF')
    if eb:
        eb.inputs['Base Color'].default_value = (*col, 1)
        eb.inputs['Emission Color'].default_value = (*col, 1)
        eb.inputs['Emission Strength'].default_value = 2.0 if ci == 0 else 0.3
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.08, location=(px, py + 0.13, 4.8 + oz))
    bulb = bpy.context.view_layer.objects.active
    bulb.name = f'TL_Bulb_{{ci}}'
    bulb.data.materials.append(emit_mat)
__result__ = 'traffic_light_ok'
""")

# ─── PRO ENVIRONMENT (SKY + GROUND + LIGHTING) ───
def apply_pro_environment(time_of_day='afternoon'):
    """HOSEK_WILKIE sky, asphalt ground plane, sun + fill light."""
    is_night = time_of_day == 'night'
    sun_elev = 0.15 if is_night else (0.6 if time_of_day == 'afternoon' else 0.35)
    sun_energy = 0.5 if is_night else 5.0
    sky_turb = 3.0 if is_night else 2.5
    run_py(f"""
import bpy, math
# Sky
world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree
for n in tree.nodes:
    tree.nodes.remove(n)
bg = tree.nodes.new('ShaderNodeBackground')
bg.location = (0, 0)
sky = tree.nodes.new('ShaderNodeTexSky')
sky.sky_type = 'HOSEK_WILKIE'
sky.sun_elevation = {sun_elev}
sky.sun_rotation = 1.2
sky.turbidity = {sky_turb}
sky.location = (-300, 0)
out = tree.nodes.new('ShaderNodeOutputWorld')
out.location = (300, 0)
tree.links.new(sky.outputs['Color'], bg.inputs['Color'])
tree.links.new(bg.outputs['Background'], out.inputs['Surface'])
# Ground plane (asphalt)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
ground = bpy.context.view_layer.objects.active
ground.name = 'Ground'
g_mat = bpy.data.materials.new(name='Asphalt')
g_mat.use_nodes = True
gb = g_mat.node_tree.nodes.get('Principled BSDF')
if gb:
    gb.inputs['Base Color'].default_value = (0.08, 0.08, 0.08, 1)
    gb.inputs['Roughness'].default_value = 0.92
    tex = g_mat.node_tree.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = 80
    tex.inputs['Detail'].default_value = 8
    bump = g_mat.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.08
    g_mat.node_tree.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    g_mat.node_tree.links.new(bump.outputs['Normal'], gb.inputs['Normal'])
ground.data.materials.append(g_mat)
# Sun light
bpy.ops.object.light_add(type='SUN', location=(10, -10, 20))
sun = bpy.context.view_layer.objects.active
sun.name = 'Sun'
sun.data.energy = {sun_energy}
sun.data.angle = 0.02
sun.data.color = (1.0, 0.95, 0.85)
sun.rotation_euler = (0.8, 0.2, 0.5)
# Fill light
bpy.ops.object.light_add(type='AREA', location=(-8, 8, 12))
fill = bpy.context.view_layer.objects.active
fill.name = 'FillLight'
fill.data.energy = {150 if is_night else 80}
fill.data.size = 5
fill.data.color = (0.85, 0.9, 1.0)
__result__ = 'environment_ok'
""")

# ─── EVIDENCE FUNCTIONS ───
def add_skid_marks(marks):
    for m in marks:
        forensic("add_skid_marks", {
            "start": m["start"], "end": m["end"],
            "width": m.get("width", 0.2), "intensity": m.get("intensity", 0.8)
        })

def add_glass_shards(positions, count_per=5):
    for pos in positions:
        forensic("add_glass_shards", {
            "center": pos, "count": min(count_per, 5), "radius": 1.5
        })

def add_fluid_stain(position, fluid_type="oil", radius=1.0):
    forensic("add_fluid_stain", {
        "center": position, "fluid_type": fluid_type, "radius": radius
    })

def add_distance_markers(pairs):
    for p in pairs:
        forensic("add_distance_marker", {
            "start": p["start"], "end": p["end"],
            "label": p.get("label", ""), "height": p.get("height", 0.5)
        })

def add_vehicle_damage(impact_point, severity="moderate"):
    """Add impact damage geometry: crumpled metal, broken parts, bumper fragments."""
    ix, iy, iz = impact_point
    run_py(f"""
import bpy, random, math
random.seed(77)
ix, iy, iz = {ix}, {iy}, {iz}
# Crumpled metal material
metal_mat = bpy.data.materials.new(name='CrumpledMetal')
metal_mat.use_nodes = True
mb = metal_mat.node_tree.nodes.get('Principled BSDF')
if mb:
    mb.inputs['Base Color'].default_value = (0.35, 0.35, 0.38, 1)
    mb.inputs['Metallic'].default_value = 0.9
    mb.inputs['Roughness'].default_value = 0.7
# Plastic debris material
plastic_mat = bpy.data.materials.new(name='BrokenPlastic')
plastic_mat.use_nodes = True
pb = plastic_mat.node_tree.nodes.get('Principled BSDF')
if pb:
    pb.inputs['Base Color'].default_value = (0.08, 0.08, 0.08, 1)
    pb.inputs['Roughness'].default_value = 0.6
# Crumpled panel pieces (3-5 deformed cubes)
for i in range(4):
    ox = ix + random.uniform(-0.8, 0.8)
    oy = iy + random.uniform(-0.8, 0.8)
    oz = iz + random.uniform(0.05, 0.4)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(ox, oy, oz))
    piece = bpy.context.view_layer.objects.active
    piece.scale = (random.uniform(0.2, 0.5), random.uniform(0.1, 0.3), random.uniform(0.02, 0.06))
    piece.rotation_euler = (random.uniform(-0.5, 0.5), random.uniform(-0.3, 0.3), random.uniform(-1, 1))
    piece.name = f'Damage_Metal_{{i}}'
    piece.data.materials.append(metal_mat)
# Bumper/trim fragments
for i in range(3):
    ox = ix + random.uniform(-1.2, 1.2)
    oy = iy + random.uniform(-1.2, 1.2)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(ox, oy, 0.03))
    frag = bpy.context.view_layer.objects.active
    frag.scale = (random.uniform(0.3, 0.8), random.uniform(0.05, 0.15), random.uniform(0.02, 0.05))
    frag.rotation_euler = (0, 0, random.uniform(-2, 2))
    frag.name = f'Damage_Plastic_{{i}}'
    frag.data.materials.append(plastic_mat)
__result__ = 'damage_ok'
""")

def add_evidence_cones(positions):
    """Add bright orange/yellow evidence marker cones at key locations for visibility."""
    pos_str = str(positions)
    run_py(f"""
import bpy, math
positions = {pos_str}
cone_mat = bpy.data.materials.new(name='EvidenceCone')
cone_mat.use_nodes = True
cb = cone_mat.node_tree.nodes.get('Principled BSDF')
if cb:
    cb.inputs['Base Color'].default_value = (1.0, 0.6, 0.0, 1)
    cb.inputs['Emission Color'].default_value = (1.0, 0.5, 0.0, 1)
    cb.inputs['Emission Strength'].default_value = 0.5
    cb.inputs['Roughness'].default_value = 0.4
num_mat = bpy.data.materials.new(name='ConeNumber')
num_mat.use_nodes = True
nb = num_mat.node_tree.nodes.get('Principled BSDF')
if nb:
    nb.inputs['Base Color'].default_value = (0.05, 0.05, 0.05, 1)
for idx, (px, py, pz) in enumerate(positions):
    # Cone body
    bpy.ops.mesh.primitive_cone_add(radius1=0.15, radius2=0.02, depth=0.35, location=(px, py, pz + 0.175))
    cone = bpy.context.view_layer.objects.active
    cone.name = f'EvidenceCone_{{idx}}'
    cone.data.materials.append(cone_mat)
    # Number plate (small cube at base)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(px, py, pz + 0.38))
    plate = bpy.context.view_layer.objects.active
    plate.scale = (0.12, 0.12, 0.04)
    plate.name = f'ConeNumber_{{idx}}'
    plate.data.materials.append(num_mat)
__result__ = f'evidence_cones_{{len(positions)}}'
""")

def add_evidence_lights(positions):
    """Small warm point lights near evidence markers."""
    pos_str = str(positions)
    run_py(f"""
import bpy
positions = {pos_str}
for i, (ex, ey, ez) in enumerate(positions):
    bpy.ops.object.light_add(type='POINT', location=(ex, ey, ez + 0.8))
    el = bpy.context.view_layer.objects.active
    el.name = f'EvidenceLight_{{i}}'
    el.data.energy = 30
    el.data.color = (1.0, 0.92, 0.7)
    el.data.shadow_soft_size = 0.3
__result__ = 'evidence_lights_ok'
""")

# ─── CUSTOM DRIVER POV CAMERA ───
def setup_driver_pov(vehicle_pos, target_pos, name="Cam_DriverPOV", lens=50, height=1.05):
    """Place camera at driver eye height with TRACK_TO constraint. Replaces addon's default."""
    vx, vy, vz = vehicle_pos
    tx, ty, tz = target_pos
    run_py(f"""
import bpy, math
# Remove addon's default DriverPOV if it exists (ours is better positioned)
old = bpy.data.objects.get('{name}')
if old:
    bpy.data.objects.remove(old, do_unlink=True)
cam_data = bpy.data.cameras.new(name='{name}')
cam_data.lens = {lens}
cam_data.clip_start = 0.1
cam_data.clip_end = 500
cam_obj = bpy.data.objects.new('{name}', cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = ({vx}, {vy}, {height})
# Track to target
track = cam_obj.constraints.new(type='TRACK_TO')
empty = bpy.data.objects.new('DriverTarget_{name}', None)
bpy.context.scene.collection.objects.link(empty)
empty.location = ({tx}, {ty}, {tz})
track.target = empty
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'
__result__ = 'driver_pov_ok'
""")

# ─── EXHIBIT FRAME (PIL overlay for courtroom labels) ───
def add_exhibit_frame(image_path, scene_title, exhibit_num):
    """Add courtroom-style exhibit label bar at bottom of rendered image using PIL."""
    run_py(f"""
import sys
sys.path.insert(0, '/Users/tatsheen/.local/lib/python3.13/site-packages')
from PIL import Image, ImageDraw, ImageFont
img = Image.open('{image_path}')
w, h = img.size
bar_h = int(h * 0.06)
bar = Image.new('RGBA', (w, bar_h), (20, 20, 25, 230))
draw = ImageDraw.Draw(bar)
try:
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size=int(bar_h * 0.5))
    font_sm = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', size=int(bar_h * 0.35))
except:
    font = ImageFont.load_default()
    font_sm = font
label = f'EXHIBIT {exhibit_num}'
draw.text((20, bar_h * 0.15), label, fill=(200, 170, 50), font=font)
draw.text((w // 3, bar_h * 0.25), '{scene_title}', fill=(220, 220, 220), font=font_sm)
draw.text((w - 280, bar_h * 0.25), 'OpenClaw Forensic', fill=(150, 150, 160), font=font_sm)
comp = Image.new('RGBA', (w, h), (0, 0, 0, 0))
comp.paste(img, (0, 0))
comp.paste(bar, (0, h - bar_h), bar)
comp.convert('RGB').save('{image_path}')
__result__ = 'exhibit_frame_ok'
""")

# ─── IMPORT VEHICLE ───
def import_vehicle(model_name, location, rotation_z=0, name_override=None):
    """Import a Kenney GLB car model."""
    model_path = os.path.expanduser(f"~/claw-architect/openclaw-blender-mcp/models/kenney_cars/Models/GLB format/{model_name}")
    if not os.path.exists(model_path):
        log(f"WARNING: Model not found: {model_path}")
        return
    vname = name_override or model_name.replace('.glb', '')
    x, y, z = location
    run_py(f"""
import bpy, math
bpy.ops.import_scene.gltf(filepath='{model_path}')
imported = [o for o in bpy.context.selected_objects]
if imported:
    parent = imported[0]
    parent.name = '{vname}'
    parent.location = ({x}, {y}, {z})
    parent.rotation_euler = (0, 0, math.radians({rotation_z}))
__result__ = f'imported {vname}'
""")

# ─── SETUP CAMERAS (via addon) ───
def setup_orbit_cam(focus_point, scene_radius=15):
    """Custom orbit camera at ~40° elevation, scene_radius distance, with TRACK_TO."""
    fx, fy, fz = focus_point
    import math as _m
    dist = scene_radius * 0.8
    height = scene_radius * 0.6
    # Place at 45° around the scene (front-right quarter view)
    cx = fx + dist * _m.cos(_m.radians(35))
    cy = fy + dist * _m.sin(_m.radians(35))
    run_py(f"""
import bpy, math
# Remove addon's default if it exists
old = bpy.data.objects.get('Cam_Orbit')
if old:
    bpy.data.objects.remove(old, do_unlink=True)
cam_data = bpy.data.cameras.new(name='Cam_Orbit')
cam_data.lens = 35
cam_data.clip_start = 0.1
cam_data.clip_end = 500
cam_obj = bpy.data.objects.new('Cam_Orbit', cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = ({cx}, {cy}, {height})
# Track to focus point
empty = bpy.data.objects.new('OrbitTarget', None)
bpy.context.scene.collection.objects.link(empty)
empty.location = ({fx}, {fy}, {fz})
empty.hide_viewport = True
empty.hide_render = True
track = cam_obj.constraints.new(type='TRACK_TO')
track.target = empty
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'
__result__ = 'orbit_cam_ok'
""")

def setup_witness_cam(focus_point, scene_radius=15, witness_offset=None):
    """Custom witness camera at human eye height, at edge of scene, looking at incident."""
    fx, fy, fz = focus_point
    import math as _m
    dist = scene_radius * 0.9
    # Default position: front-left of scene (like a bystander on the sidewalk)
    if witness_offset:
        wx, wy = witness_offset
    else:
        wx = fx + dist * _m.cos(_m.radians(160))
        wy = fy + dist * _m.sin(_m.radians(160))
    run_py(f"""
import bpy
# Remove addon's default if it exists
old = bpy.data.objects.get('Cam_Witness')
if old:
    bpy.data.objects.remove(old, do_unlink=True)
cam_data = bpy.data.cameras.new(name='Cam_Witness')
cam_data.lens = 35
cam_data.clip_start = 0.1
cam_data.clip_end = 500
cam_obj = bpy.data.objects.new('Cam_Witness', cam_data)
bpy.context.scene.collection.objects.link(cam_obj)
cam_obj.location = ({wx}, {wy}, 1.65)
# Track to incident
empty = bpy.data.objects.new('WitnessTarget', None)
bpy.context.scene.collection.objects.link(empty)
empty.location = ({fx}, {fy}, {fz + 0.5})
empty.hide_viewport = True
empty.hide_render = True
track = cam_obj.constraints.new(type='TRACK_TO')
track.target = empty
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'
__result__ = 'witness_cam_ok'
""")

def setup_cameras(focus_point, scene_radius=15):
    """Create all 4 cameras: BirdEye (addon), custom DriverPOV, custom Orbit, custom Witness."""
    fx, fy, fz = focus_point
    # Only use addon for BirdEye (it works well)
    forensic("setup_cameras", {
        "camera_type": "bird_eye",
        "target": [fx, fy, fz],
        "height": max(scene_radius * 1.5, 25),
        "ortho_scale": scene_radius * 3
    })
    # Custom orbit and witness (addon's versions are broken)
    setup_orbit_cam(focus_point, scene_radius)
    setup_witness_cam(focus_point, scene_radius)

# ─── RENDER ALL CAMERAS FOR A SCENE ───
def render_scene_cameras(scene_num, scene_title, exhibit_base, cameras=None):
    if cameras is None:
        cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness"]
    for i, cam in enumerate(cameras, 1):
        out_path = os.path.join(RENDER_DIR, f"scene{scene_num}_{i:02d}_{cam}.png")
        log(f"  Rendering {cam} -> {out_path}")
        r = render_camera(cam, out_path)
        log(f"  Result: {r}")
        if os.path.exists(out_path):
            exhibit = f"{exhibit_base}-{chr(64+i)}"
            add_exhibit_frame(out_path, scene_title, exhibit)
            log(f"  Exhibit frame added: {exhibit}")

# ═══════════════════════════════════════════════════════════════
# SCENE 1: T-Bone Intersection Collision
# ═══════════════════════════════════════════════════════════════
def build_scene_1():
    log("=== SCENE 1: T-Bone Intersection Collision ===")
    clean_scene()
    setup_render_settings()
    setup_compositor()
    apply_pro_environment('afternoon')

    # Road — intersection
    bridge("forensic_scene", {"action": "create_road", "road_type": "intersection", "lanes": 4, "lane_width": 3.5})

    # Vehicles
    import_vehicle("sedan.glb", location=(2.5, -1.5, 0), rotation_z=15, name_override="V1_Sedan")
    import_vehicle("suv-luxury.glb", location=(-1.0, 2.0, 0), rotation_z=280, name_override="V2_SUV")

    # Apply specific realistic colors
    apply_vehicle_color("V1_Sedan", "silver")
    apply_vehicle_color("V2_SUV", "dark_red")

    # Environment context
    add_environment_context("intersection", (0, 0), 20)
    add_road_markings("intersection", 60, lane_width=3.5, lanes=4)
    add_curbs_and_sidewalks(60, 14)

    # Traffic infrastructure
    add_traffic_light((8, 8), rotation_z=45)
    add_traffic_light((-8, -8), rotation_z=225)
    add_stop_signs([(9, -9, 0), (-9, 9, 180)])
    add_street_lights([(-12, 12), (12, -12), (-12, -12), (12, 12)])

    # Evidence
    impact_point = (1.0, 0.5, 0)
    add_skid_marks([
        {"start": [8, -12, 0.01], "end": [2, -2, 0.01], "width": 0.25, "intensity": 0.9},
        {"start": [-10, 3, 0.01], "end": [-2, 1.5, 0.01], "width": 0.2, "intensity": 0.7},
    ])
    add_glass_shards([(1.0, 0.5, 0.01), (1.5, 0.0, 0.01)], count_per=5)
    add_fluid_stain(impact_point, "coolant", radius=1.2)
    add_distance_markers([
        {"start": [8, -12, 0.01], "end": [2, -2, 0.01], "label": "32.4 ft skid", "height": 0.5},
        {"start": [2.5, -1.5, 0.3], "end": [-1.0, 2.0, 0.3], "label": "Impact 14.2 ft", "height": 0.8},
    ])
    add_vehicle_damage((1.0, 0.5, 0.2), severity="moderate")
    add_evidence_cones([(1.0, 0.5, 0.01), (5, -7, 0.01), (2.5, -1.5, 0.01), (-1, 2, 0.01)])
    add_evidence_lights([(1.0, 0.5, 0.01), (5, -7, 0.01)])

    # Cameras
    setup_cameras((1.0, 0.5, 0.5), scene_radius=18)
    # Custom DriverPOV from V1's perspective approaching intersection
    setup_driver_pov(
        vehicle_pos=(8, -14, 0), target_pos=(1.0, 0.5, 0.5),
        name="Cam_DriverPOV", lens=50, height=1.05
    )

    render_scene_cameras(1, "T-Bone Intersection — Vehicle vs SUV", "1")

# ═══════════════════════════════════════════════════════════════
# SCENE 2: Pedestrian Crosswalk Incident
# ═══════════════════════════════════════════════════════════════
def build_scene_2():
    log("=== SCENE 2: Pedestrian Crosswalk Incident ===")
    clean_scene()
    setup_render_settings()
    setup_compositor()
    apply_pro_environment('afternoon')

    # Road — straight with crosswalk
    bridge("forensic_scene", {"action": "create_road", "road_type": "straight", "lanes": 4, "lane_width": 3.5})

    # Crosswalk stripes
    run_py("""
import bpy
cw_mat = bpy.data.materials.new(name='CrosswalkWhite')
cw_mat.use_nodes = True
cwb = cw_mat.node_tree.nodes.get('Principled BSDF')
if cwb:
    cwb.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1)
    cwb.inputs['Roughness'].default_value = 0.5
for i in range(8):
    y = -4.9 + i * 1.3
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, 0.006))
    stripe = bpy.context.view_layer.objects.active
    stripe.scale = (3.0, 0.45, 0.005)
    stripe.name = f'CrosswalkStripe_{{i}}'
    stripe.data.materials.append(cw_mat)
__result__ = 'crosswalk_ok'
""")

    # Vehicle — stopped after impact
    import_vehicle("sedan.glb", location=(3, -2, 0), rotation_z=5, name_override="V1_Sedan")
    apply_vehicle_color("V1_Sedan", "navy")

    # Pedestrian stand-in (simple mannequin)
    run_py("""
import bpy
# Simple human figure using primitives
# Torso
bpy.ops.mesh.primitive_cube_add(size=1, location=(-0.5, 1.5, 0.5))
torso = bpy.context.view_layer.objects.active
torso.scale = (0.3, 0.2, 0.5)
torso.name = 'Pedestrian_Torso'
torso.rotation_euler = (0.4, 0.1, 0.3)  # fallen pose
# Head
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=(-0.5, 1.7, 0.15))
head = bpy.context.view_layer.objects.active
head.name = 'Pedestrian_Head'
# Material
p_mat = bpy.data.materials.new(name='PedClothing')
p_mat.use_nodes = True
pb = p_mat.node_tree.nodes.get('Principled BSDF')
if pb:
    pb.inputs['Base Color'].default_value = (0.15, 0.15, 0.4, 1)
    pb.inputs['Roughness'].default_value = 0.8
torso.data.materials.append(p_mat)
skin_mat = bpy.data.materials.new(name='Skin')
skin_mat.use_nodes = True
sb = skin_mat.node_tree.nodes.get('Principled BSDF')
if sb:
    sb.inputs['Base Color'].default_value = (0.65, 0.45, 0.35, 1)
    sb.inputs['Roughness'].default_value = 0.6
    sb.inputs['Subsurface Weight'].default_value = 0.3
head.data.materials.append(skin_mat)
__result__ = 'pedestrian_ok'
""")

    # Environment
    add_environment_context("straight", (0, 0), 18)
    add_road_markings("straight", 80, lane_width=3.5, lanes=4)
    add_curbs_and_sidewalks(80, 14)
    add_street_lights([(-15, 10), (15, -10), (-15, -10), (15, 10)])

    # Evidence
    add_skid_marks([
        {"start": [15, -3, 0.01], "end": [4, -2, 0.01], "width": 0.22, "intensity": 0.85},
    ])
    add_glass_shards([(1.5, 0, 0.01)], count_per=4)
    add_fluid_stain((-0.5, 1.5, 0.01), "blood", radius=0.6)
    add_distance_markers([
        {"start": [15, -3, 0.01], "end": [4, -2, 0.01], "label": "28.1 ft braking", "height": 0.5},
        {"start": [3, -2, 0.3], "end": [-0.5, 1.5, 0.1], "label": "Throw dist 12.8 ft", "height": 0.6},
    ])
    add_vehicle_damage((2.0, -0.5, 0.3), severity="moderate")
    add_evidence_cones([(2.0, -0.5, 0.01), (-0.5, 1.5, 0.01), (1.5, 0, 0.01)])
    add_evidence_lights([(1.5, 0, 0.01), (-0.5, 1.5, 0.01)])

    # Cameras
    setup_cameras((1.0, 0, 0.5), scene_radius=16)
    setup_driver_pov(
        vehicle_pos=(16, -3, 0), target_pos=(0, 1, 0.5),
        name="Cam_DriverPOV", lens=50, height=1.05
    )

    render_scene_cameras(2, "Pedestrian Crosswalk — Vehicle vs Pedestrian", "2")

# ═══════════════════════════════════════════════════════════════
# SCENE 3: Workplace Scaffolding Collapse (non-vehicle diversity)
# ═══════════════════════════════════════════════════════════════
def build_scene_3():
    log("=== SCENE 3: Workplace Scaffolding Collapse ===")
    clean_scene()
    setup_render_settings()
    setup_compositor()
    apply_pro_environment('afternoon')

    # Construction site ground
    run_py("""
import bpy
# Dirt/gravel ground overlay
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0.002))
dirt = bpy.context.view_layer.objects.active
dirt.name = 'DirtGround'
d_mat = bpy.data.materials.new(name='Dirt')
d_mat.use_nodes = True
db = d_mat.node_tree.nodes.get('Principled BSDF')
if db:
    db.inputs['Base Color'].default_value = (0.35, 0.28, 0.18, 1)
    db.inputs['Roughness'].default_value = 0.95
    tex = d_mat.node_tree.nodes.new('ShaderNodeTexNoise')
    tex.inputs['Scale'].default_value = 15
    tex.inputs['Detail'].default_value = 10
    bump = d_mat.node_tree.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.2
    d_mat.node_tree.links.new(tex.outputs['Fac'], bump.inputs['Height'])
    d_mat.node_tree.links.new(bump.outputs['Normal'], db.inputs['Normal'])
dirt.data.materials.append(d_mat)
__result__ = 'dirt_ground_ok'
""")

    # Building under construction (concrete frame)
    run_py("""
import bpy
c_mat = bpy.data.materials.new(name='RawConcrete')
c_mat.use_nodes = True
cb = c_mat.node_tree.nodes.get('Principled BSDF')
if cb:
    cb.inputs['Base Color'].default_value = (0.55, 0.53, 0.50, 1)
    cb.inputs['Roughness'].default_value = 0.9
# Floor slabs
for floor in range(3):
    h = floor * 3.5
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-5, 0, h))
    slab = bpy.context.view_layer.objects.active
    slab.scale = (12, 8, 0.25)
    slab.name = f'FloorSlab_{{floor}}'
    slab.data.materials.append(c_mat)
    # Columns
    for cx in [-10, -5, 0, 5]:
        for cy in [-3, 3]:
            bpy.ops.mesh.primitive_cylinder_add(radius=0.25, depth=3.5, location=(cx, cy, h + 1.75))
            col = bpy.context.view_layer.objects.active
            col.name = f'Column_{{floor}}_{{cx}}_{{cy}}'
            col.data.materials.append(c_mat)
__result__ = 'building_frame_ok'
""")

    # Scaffolding (intact section + collapsed section)
    run_py("""
import bpy, math, random
random.seed(99)
s_mat = bpy.data.materials.new(name='Scaffold_Metal')
s_mat.use_nodes = True
sb = s_mat.node_tree.nodes.get('Principled BSDF')
if sb:
    sb.inputs['Base Color'].default_value = (0.45, 0.45, 0.48, 1)
    sb.inputs['Metallic'].default_value = 0.95
    sb.inputs['Roughness'].default_value = 0.5
plank_mat = bpy.data.materials.new(name='Scaffold_Wood')
plank_mat.use_nodes = True
wb = plank_mat.node_tree.nodes.get('Principled BSDF')
if wb:
    wb.inputs['Base Color'].default_value = (0.45, 0.30, 0.15, 1)
    wb.inputs['Roughness'].default_value = 0.85
# Intact scaffolding (left side)
for level in range(3):
    h = level * 2.0 + 0.5
    for x in [6, 8]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=2.0, location=(x, -4, h))
        p = bpy.context.view_layer.objects.active
        p.name = f'ScaffPole_intact_{{level}}_{{x}}'
        p.data.materials.append(s_mat)
    # Plank
    bpy.ops.mesh.primitive_cube_add(size=1, location=(7, -4, h + 1.0))
    plank = bpy.context.view_layer.objects.active
    plank.scale = (2.5, 0.3, 0.04)
    plank.name = f'ScaffPlank_intact_{{level}}'
    plank.data.materials.append(plank_mat)
# Collapsed scaffolding (right side) — key forensic evidence
collapse_pieces = [
    (3, -4, 0.3, 15, 30, 5),
    (4.5, -3.5, 0.1, -20, 10, 45),
    (2, -5, 0.5, 40, -15, 20),
    (3.5, -4.5, 0.15, -5, 60, 10),
    (4, -3, 0.8, 25, 5, -30),
]
for i, (cx, cy, cz, rx, ry, rz) in enumerate(collapse_pieces):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=2.0, location=(cx, cy, cz))
    piece = bpy.context.view_layer.objects.active
    piece.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    piece.name = f'ScaffCollapsed_{{i}}'
    piece.data.materials.append(s_mat)
# Fallen planks
for i in range(3):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(2.5 + i*0.8, -4 + random.uniform(-1, 1), 0.05))
    fp = bpy.context.view_layer.objects.active
    fp.scale = (2.0, 0.3, 0.04)
    fp.rotation_euler = (random.uniform(-0.1, 0.1), random.uniform(-0.05, 0.05), random.uniform(-0.5, 0.5))
    fp.name = f'FallenPlank_{{i}}'
    fp.data.materials.append(plank_mat)
# Safety helmet on ground
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(2.0, -3.5, 0.15))
helmet = bpy.context.view_layer.objects.active
helmet.name = 'SafetyHelmet'
h_mat = bpy.data.materials.new(name='HelmetYellow')
h_mat.use_nodes = True
hb = h_mat.node_tree.nodes.get('Principled BSDF')
if hb:
    hb.inputs['Base Color'].default_value = (0.9, 0.75, 0.0, 1)
    hb.inputs['Roughness'].default_value = 0.3
helmet.data.materials.append(h_mat)
__result__ = 'scaffolding_ok'
""")

    # Environment context — construction site buildings nearby
    add_environment_context("construction", (-5, 0), 22)

    # Distance markers for the collapse
    add_distance_markers([
        {"start": [6, -4, 3.0], "end": [2.5, -4, 0.1], "label": "Fall height 9.8 ft", "height": 1.0},
        {"start": [2.0, -3.5, 0.15], "end": [3.5, -4.5, 0.15], "label": "Debris field 6.2 ft", "height": 0.4},
    ])
    add_evidence_cones([(2.5, -4, 0.1), (2.0, -3.5, 0.15), (4, -3, 0.1)])
    add_evidence_lights([(2.5, -4, 0.1), (2.0, -3.5, 0.15), (4, -3, 0.8)])

    # Cameras
    setup_cameras((3, -4, 1.5), scene_radius=15)
    # Override DriverPOV to be a "worker POV" looking up at collapse
    setup_driver_pov(
        vehicle_pos=(1, -6, 0), target_pos=(4, -4, 3),
        name="Cam_DriverPOV", lens=35, height=1.65
    )

    render_scene_cameras(3, "Construction Site — Scaffolding Collapse", "3")

# ═══════════════════════════════════════════════════════════════
# SCENE 4: Nighttime Parking Lot Hit-and-Run
# ═══════════════════════════════════════════════════════════════
def build_scene_4():
    log("=== SCENE 4: Nighttime Parking Lot Hit-and-Run ===")
    clean_scene()
    setup_render_settings()
    setup_compositor()
    apply_pro_environment('night')

    # Parking lot surface
    run_py("""
import bpy
# Parking lot lines
line_mat = bpy.data.materials.new(name='ParkingLine')
line_mat.use_nodes = True
lb = line_mat.node_tree.nodes.get('Principled BSDF')
if lb:
    lb.inputs['Base Color'].default_value = (0.85, 0.85, 0.85, 1)
    lb.inputs['Roughness'].default_value = 0.5
# Draw parking space lines
for i in range(8):
    x = -14 + i * 3.0
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 5, 0.006))
    line = bpy.context.view_layer.objects.active
    line.scale = (0.08, 2.5, 0.005)
    line.name = f'ParkLine_{{i}}'
    line.data.materials.append(line_mat)
# Second row
for i in range(8):
    x = -14 + i * 3.0
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -5, 0.006))
    line = bpy.context.view_layer.objects.active
    line.scale = (0.08, 2.5, 0.005)
    line.name = f'ParkLine2_{{i}}'
    line.data.materials.append(line_mat)
# Handicap symbol area (blue rectangle)
h_mat = bpy.data.materials.new(name='HandicapBlue')
h_mat.use_nodes = True
hb = h_mat.node_tree.nodes.get('Principled BSDF')
if hb:
    hb.inputs['Base Color'].default_value = (0.1, 0.2, 0.7, 1)
    hb.inputs['Roughness'].default_value = 0.4
bpy.ops.mesh.primitive_cube_add(size=1, location=(-14, 5, 0.007))
hspot = bpy.context.view_layer.objects.active
hspot.scale = (2.5, 4.5, 0.005)
hspot.name = 'HandicapSpot'
hspot.data.materials.append(h_mat)
__result__ = 'parking_lot_ok'
""")

    # Vehicles — parked cars + incident vehicles
    import_vehicle("sedan.glb", location=(-11, 5, 0), rotation_z=90, name_override="Parked_1")
    import_vehicle("suv.glb", location=(-8, 5, 0), rotation_z=90, name_override="Parked_2")
    import_vehicle("van.glb", location=(-5, -5, 0), rotation_z=270, name_override="Parked_3")
    import_vehicle("sedan.glb", location=(2, 5, 0), rotation_z=90, name_override="Parked_4")

    # Incident vehicles
    import_vehicle("suv.glb", location=(5, 0, 0), rotation_z=30, name_override="HitRun_Vehicle")
    import_vehicle("sedan.glb", location=(3, 3, 0), rotation_z=350, name_override="Victim_Vehicle")

    # Colors
    apply_vehicle_color("Parked_1", "charcoal")
    apply_vehicle_color("Parked_2", "white")
    apply_vehicle_color("Parked_3", "beige")
    apply_vehicle_color("Parked_4", "dark_green")
    apply_vehicle_color("HitRun_Vehicle", "black")
    apply_vehicle_color("Victim_Vehicle", "silver")

    # Night lighting — parking lot lights
    add_street_lights([(-12, 0), (-4, 0), (4, 0), (12, 0), (-12, 10), (12, 10), (-12, -10), (12, -10)])

    # Security camera light (harsh overhead)
    run_py("""
import bpy
bpy.ops.object.light_add(type='SPOT', location=(0, 0, 8))
spot = bpy.context.view_layer.objects.active
spot.name = 'SecuritySpot'
spot.data.energy = 800
spot.data.spot_size = 1.2
spot.data.spot_blend = 0.3
spot.data.color = (1.0, 0.95, 0.8)
spot.rotation_euler = (0, 0, 0)
__result__ = 'security_light_ok'
""")

    # Environment — nearby buildings (commercial)
    add_environment_context("parking", (0, 0), 20)

    # Evidence
    add_skid_marks([
        {"start": [12, -5, 0.01], "end": [6, -1, 0.01], "width": 0.3, "intensity": 0.95},
    ])
    add_glass_shards([(4, 1.5, 0.01)], count_per=5)
    add_fluid_stain((4.5, 1, 0.01), "oil", radius=0.8)

    # Paint transfer evidence marker
    run_py("""
import bpy
# Paint scrape on victim vehicle area
bpy.ops.mesh.primitive_cube_add(size=1, location=(3.5, 2.5, 0.6))
scrape = bpy.context.view_layer.objects.active
scrape.scale = (0.4, 0.02, 0.08)
scrape.name = 'PaintTransfer'
sc_mat = bpy.data.materials.new(name='PaintScrape')
sc_mat.use_nodes = True
scb = sc_mat.node_tree.nodes.get('Principled BSDF')
if scb:
    scb.inputs['Base Color'].default_value = (0.02, 0.02, 0.03, 1)  # black paint from hit-run vehicle
    scb.inputs['Metallic'].default_value = 0.6
    scb.inputs['Roughness'].default_value = 0.3
scrape.data.materials.append(sc_mat)
__result__ = 'paint_transfer_ok'
""")

    add_distance_markers([
        {"start": [12, -5, 0.01], "end": [6, -1, 0.01], "label": "Approach 22.3 ft", "height": 0.5},
        {"start": [5, 0, 0.3], "end": [3, 3, 0.3], "label": "Impact offset 8.4 ft", "height": 0.6},
    ])
    add_vehicle_damage((4, 1.5, 0.3), severity="moderate")
    add_evidence_cones([(4, 1.5, 0.01), (3.5, 2.5, 0.01), (6, -1, 0.01), (5, 0, 0.01)])
    add_evidence_lights([(4, 1.5, 0.01), (3.5, 2.5, 0.6), (6, -1, 0.01)])

    # Cameras
    setup_cameras((4, 1, 0.5), scene_radius=18)
    # Security camera angle (high, wide angle)
    setup_driver_pov(
        vehicle_pos=(0, -15, 6), target_pos=(4, 1, 0),
        name="Cam_DriverPOV", lens=24, height=6
    )

    render_scene_cameras(4, "Parking Lot — Nighttime Hit-and-Run", "4")

# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    log("Portfolio Render v6 — Professional Forensic Quality")
    log(f"Render dir: {RENDER_DIR}")
    log(f"Cycles 128spl, 4 cameras per scene, 4 scenes")
    log("")

    scenes = [build_scene_1, build_scene_2, build_scene_3, build_scene_4]
    for i, build_fn in enumerate(scenes, 1):
        try:
            log(f"--- Starting Scene {i} ---")
            build_fn()
            # Save .blend after each scene
            blend_path = os.path.join(BLEND_DIR, f"v6_scene{i}.blend")
            run_py(f"import bpy; bpy.ops.wm.save_as_mainfile(filepath='{blend_path}')")
            log(f"Saved: {blend_path}")
        except Exception as e:
            log(f"ERROR in Scene {i}: {e}")
            import traceback
            log(traceback.format_exc())
        log("")

    log("=== ALL SCENES COMPLETE ===")
    # Summary
    import glob
    renders = glob.glob(os.path.join(RENDER_DIR, "*.png"))
    log(f"Total renders: {len(renders)}")
    for r in sorted(renders):
        size = os.path.getsize(r)
        log(f"  {os.path.basename(r)} ({size // 1024}KB)")

if __name__ == "__main__":
    main()
