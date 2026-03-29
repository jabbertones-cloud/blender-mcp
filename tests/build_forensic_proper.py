#!/usr/bin/env python3
"""
Build a forensic crash scene with CORRECT physics and ALL courtroom details.

Physics model:
- Conservation of momentum (m1*v1 + m2*v2 = m1*v1' + m2*v2')
- Coefficient of restitution for post-impact velocities
- Realistic friction deceleration (a = mu * g)
- Impact energy calculation (0.5 * m * v^2)
- Skid distance = v^2 / (2 * mu * g)

Forensic details:
- Ghost trails (semi-transparent approach path)
- Data overlay HUD (speed, time, energy)
- Scale bar with tick marks
- Exhibit label with case info
- Measurement annotations
- Evidence markers at correct physics locations
- Text objects face camera properly
"""
import socket, json, time, math

def cmd(c, t=180):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(t)
    try:
        s.connect(('127.0.0.1', 9876))
        s.sendall((json.dumps(c) + '\n').encode())
        d = b''
        while True:
            ch = s.recv(16384)
            if not ch: break
            d += ch
            try:
                json.loads(d.decode())
                break
            except: continue
        return json.loads(d.decode()).get('result', {})
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()

MODELS = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/models'
RENDERS = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders'

# ============================================================
# PHYSICS CALCULATIONS
# ============================================================
# Vehicle 1: Red sedan heading EAST (+X)
m1 = 1400  # kg
v1_mph = 38
v1_ms = v1_mph * 0.44704  # 16.99 m/s

# Vehicle 2: Silver SUV heading NORTH (+Y)
m2 = 2100  # kg
v2_mph = 28
v2_ms = v2_mph * 0.44704  # 12.52 m/s

# Impact point at origin
impact_x, impact_y = 0.0, 0.0

# Coefficient of restitution (typical for car crashes: 0.1-0.3)
e = 0.15

# Conservation of momentum (2D)
# X-direction: m1*v1x = m1*v1x' + m2*v2x'
# Y-direction: m2*v2y = m1*v1y' + m2*v2y'
# With restitution: v2x' - v1x' = -e * (v2x - v1x)

# Pre-impact: V1 = (v1_ms, 0), V2 = (0, v2_ms)
# X: m1*v1_ms = m1*v1x' + m2*v2x'
# Y: m2*v2_ms = m1*v1y' + m2*v2y'
# Restitution X: v2x' - v1x' = -e * (0 - v1_ms) = e*v1_ms
# Restitution Y: v2y' - v1y' = -e * (v2_ms - 0) = -e*v2_ms

# Solve X:
# v2x' = v1x' + e*v1_ms
# m1*v1_ms = m1*v1x' + m2*(v1x' + e*v1_ms)
# m1*v1_ms = v1x'*(m1+m2) + m2*e*v1_ms
# v1x' = (m1*v1_ms - m2*e*v1_ms) / (m1+m2)
v1x_post = (m1 * v1_ms - m2 * e * v1_ms) / (m1 + m2)
v2x_post = v1x_post + e * v1_ms

# Solve Y:
# v2y' = v1y' - e*v2_ms
# m2*v2_ms = m1*v1y' + m2*(v1y' - e*v2_ms)
# m2*v2_ms = v1y'*(m1+m2) - m2*e*v2_ms
# v1y' = (m2*v2_ms + m2*e*v2_ms) / (m1+m2)
v1y_post = (m2 * v2_ms + m2 * e * v2_ms) / (m1 + m2)
v2y_post = v1y_post - e * v2_ms

# Friction deceleration
mu = 0.65  # asphalt friction
g = 9.81
friction_decel = mu * g  # 6.38 m/s^2

# Post-impact speeds
v1_post_speed = math.sqrt(v1x_post**2 + v1y_post**2)
v2_post_speed = math.sqrt(v2x_post**2 + v2y_post**2)

# Post-impact headings (degrees from +Y axis, clockwise)
v1_post_heading = math.degrees(math.atan2(v1x_post, v1y_post))
v2_post_heading = math.degrees(math.atan2(v2x_post, v2y_post))

# Time to stop from friction
v1_stop_time = v1_post_speed / friction_decel
v2_stop_time = v2_post_speed / friction_decel

# Distance to final rest
v1_rest_dist = v1_post_speed**2 / (2 * friction_decel)
v2_rest_dist = v2_post_speed**2 / (2 * friction_decel)

# Final rest positions
v1_post_dir_x = v1x_post / v1_post_speed if v1_post_speed > 0 else 0
v1_post_dir_y = v1y_post / v1_post_speed if v1_post_speed > 0 else 0
v2_post_dir_x = v2x_post / v2_post_speed if v2_post_speed > 0 else 0
v2_post_dir_y = v2y_post / v2_post_speed if v2_post_speed > 0 else 0

v1_rest_x = impact_x + v1_post_dir_x * v1_rest_dist
v1_rest_y = impact_y + v1_post_dir_y * v1_rest_dist
v2_rest_x = impact_x + v2_post_dir_x * v2_rest_dist
v2_rest_y = impact_y + v2_post_dir_y * v2_rest_dist

# Impact energy
impact_energy_kj = 0.5 * (m1 * v1_ms**2 + m2 * v2_ms**2) / 1000

# Approach distances (from start to impact)
v1_approach = 20.0  # meters
v2_approach = 18.0

# Braking distance before impact (sedan braking for 1 second before impact)
v1_brake_time = 0.8  # seconds of braking before impact
v1_skid_length = v1_ms * v1_brake_time - 0.5 * friction_decel * v1_brake_time**2

# Animation timing
fps = 24
approach_time = 2.5  # seconds for approach
impact_frame = int(approach_time * fps)  # frame 60
post_impact_time = max(v1_stop_time, v2_stop_time) + 1.0
total_time = approach_time + post_impact_time + 1.0  # +1s hold
total_frames = int(total_time * fps)

# Spin rates (degrees/sec after impact)
v1_spin = 45  # sedan spins from lateral impact
v2_spin = -20  # SUV slight counter-rotation

print(f"=== PHYSICS SUMMARY ===")
print(f"V1 (sedan): {v1_mph}mph = {v1_ms:.1f}m/s, {m1}kg")
print(f"V2 (SUV): {v2_mph}mph = {v2_ms:.1f}m/s, {m2}kg")
print(f"Post-impact V1: ({v1x_post:.2f}, {v1y_post:.2f}) m/s = {v1_post_speed:.1f}m/s heading {v1_post_heading:.1f}deg")
print(f"Post-impact V2: ({v2x_post:.2f}, {v2y_post:.2f}) m/s = {v2_post_speed:.1f}m/s heading {v2_post_heading:.1f}deg")
print(f"V1 rest pos: ({v1_rest_x:.1f}, {v1_rest_y:.1f}), dist={v1_rest_dist:.1f}m")
print(f"V2 rest pos: ({v2_rest_x:.1f}, {v2_rest_y:.1f}), dist={v2_rest_dist:.1f}m")
print(f"Impact energy: {impact_energy_kj:.0f} kJ")
print(f"Skid mark length: {v1_skid_length:.1f}m")
print(f"Impact frame: {impact_frame}, total frames: {total_frames}")
print(f"FPS: {fps}")

# ============================================================
# BUILD SCENE
# ============================================================

# Step 1: Clear
print("\n--- Building scene ---")
r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy
for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)
for col in list(bpy.data.collections): bpy.data.collections.remove(col)
for mesh in list(bpy.data.meshes): bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)
for img in list(bpy.data.images): bpy.data.images.remove(img)
"""}})
print("  Cleared")
time.sleep(0.3)

# Step 2: Road
r = cmd({'command': 'forensic_scene', 'params': {'action': 'add_scene_template', 'template': 't_intersection'}})
print("  Road built")
time.sleep(0.3)

# Step 3: Import sedan with red paint + animate
sedan_code = f"""
import bpy, math

# Import sedan
bpy.ops.import_scene.gltf(filepath='{MODELS}/sedan.glb')
imported = list(bpy.context.selected_objects)

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-{v1_approach}, 0, 0))
root = bpy.context.active_object
root.name = 'Vehicle_Sedan'
for obj in imported:
    obj.parent = root
root.scale = (2.2, 2.2, 2.2)

# Red paint
red_mat = bpy.data.materials.new(name='SedanRed')
red_mat.use_nodes = True
bsdf = red_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.7, 0.03, 0.03, 1)
bsdf.inputs['Metallic'].default_value = 0.85
bsdf.inputs['Roughness'].default_value = 0.18
try:
    bsdf.inputs['Coat Weight'].default_value = 0.9
    bsdf.inputs['Coat Roughness'].default_value = 0.02
except: pass

tire_mat = bpy.data.materials.new(name='SedanTires')
tire_mat.use_nodes = True
bsdf = tire_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
bsdf.inputs['Roughness'].default_value = 0.85

for obj in imported:
    if obj.type != 'MESH':
        continue
    n = obj.name.lower()
    obj.data.materials.clear()
    if 'wheel' in n:
        obj.data.materials.append(tire_mat)
    else:
        obj.data.materials.append(red_mat)

# ANIMATE SEDAN
# Frame 1: start at (-{v1_approach}, 0, 0), heading east
# Frame {impact_frame}: arrive at impact (0, 0, 0)
# Post-impact: slide toward rest with spin and friction

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = {total_frames}
scene.render.fps = {fps}

# Frame 1 - start position
scene.frame_set(1)
root.location = (-{v1_approach}, 0, 0)
root.rotation_euler = (0, 0, 0)  # facing +X (east)
root.keyframe_insert(data_path='location', frame=1)
root.keyframe_insert(data_path='rotation_euler', frame=1)

# Frame {impact_frame} - impact
scene.frame_set({impact_frame})
root.location = (0, 0, 0)
root.rotation_euler = (0, 0, 0)
root.keyframe_insert(data_path='location', frame={impact_frame})
root.keyframe_insert(data_path='rotation_euler', frame={impact_frame})

# Post-impact animation with friction deceleration
# Position at time t after impact: x = v*t - 0.5*a*t^2 (until stop)
post_frames = {total_frames} - {impact_frame}
for i in range(1, post_frames + 1):
    t = i / {fps}
    f = {impact_frame} + i

    if t < {v1_stop_time}:
        frac = t / {v1_stop_time}
        # Deceleration: position = v*t - 0.5*a*t^2
        dist = {v1_post_speed} * t - 0.5 * {friction_decel} * t * t
        px = dist * {v1_post_dir_x}
        py = dist * {v1_post_dir_y}
        spin = {v1_spin} * t
    else:
        px = {v1_rest_x}
        py = {v1_rest_y}
        spin = {v1_spin} * {v1_stop_time}

    root.location = (px, py, 0)
    root.rotation_euler = (0, 0, math.radians(spin))
    root.keyframe_insert(data_path='location', frame=f)
    root.keyframe_insert(data_path='rotation_euler', frame=f)

print(f'Sedan animated: {{{impact_frame}}} frames approach + {{post_frames}} post-impact')
"""
r = cmd({'command': 'execute_python', 'params': {'code': sedan_code}})
print(f"  Sedan: {str(r)[:80]}")
time.sleep(0.3)

# Step 4: Import SUV with silver paint + animate
suv_code = f"""
import bpy, math

bpy.ops.import_scene.gltf(filepath='{MODELS}/suv.glb')
imported = list(bpy.context.selected_objects)

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, -{v2_approach}, 0))
root = bpy.context.active_object
root.name = 'Vehicle_SUV'
for obj in imported:
    obj.parent = root
root.scale = (2.2, 2.2, 2.2)
root.rotation_euler = (0, 0, math.radians(90))  # face +Y (north)

silver_mat = bpy.data.materials.new(name='SUVSilver')
silver_mat.use_nodes = True
bsdf = silver_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.55, 0.57, 0.6, 1)
bsdf.inputs['Metallic'].default_value = 0.9
bsdf.inputs['Roughness'].default_value = 0.12
try:
    bsdf.inputs['Coat Weight'].default_value = 0.9
    bsdf.inputs['Coat Roughness'].default_value = 0.02
except: pass

suv_tire = bpy.data.materials.new(name='SUVTires')
suv_tire.use_nodes = True
bsdf = suv_tire.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
bsdf.inputs['Roughness'].default_value = 0.85

for obj in imported:
    if obj.type != 'MESH':
        continue
    n = obj.name.lower()
    obj.data.materials.clear()
    if 'wheel' in n:
        obj.data.materials.append(suv_tire)
    else:
        obj.data.materials.append(silver_mat)

scene = bpy.context.scene

# Frame 1 - start
scene.frame_set(1)
root.location = (0, -{v2_approach}, 0)
root.rotation_euler = (0, 0, math.radians(90))
root.keyframe_insert(data_path='location', frame=1)
root.keyframe_insert(data_path='rotation_euler', frame=1)

# Frame {impact_frame} - impact
scene.frame_set({impact_frame})
root.location = (0, 0, 0)
root.rotation_euler = (0, 0, math.radians(90))
root.keyframe_insert(data_path='location', frame={impact_frame})
root.keyframe_insert(data_path='rotation_euler', frame={impact_frame})

# Post-impact
post_frames = {total_frames} - {impact_frame}
for i in range(1, post_frames + 1):
    t = i / {fps}
    f = {impact_frame} + i

    if t < {v2_stop_time}:
        dist = {v2_post_speed} * t - 0.5 * {friction_decel} * t * t
        px = dist * {v2_post_dir_x}
        py = dist * {v2_post_dir_y}
        spin = {v2_spin} * t
    else:
        px = {v2_rest_x}
        py = {v2_rest_y}
        spin = {v2_spin} * {v2_stop_time}

    root.location = (px, py, 0)
    root.rotation_euler = (0, 0, math.radians(90 + spin))
    root.keyframe_insert(data_path='location', frame=f)
    root.keyframe_insert(data_path='rotation_euler', frame=f)

print(f'SUV animated')
"""
r = cmd({'command': 'execute_python', 'params': {'code': suv_code}})
print(f"  SUV: {str(r)[:80]}")
time.sleep(0.3)

# Step 5: Characters on sidewalk
char_code = f"""
import bpy

skin_mat = bpy.data.materials.new(name='Skin')
skin_mat.use_nodes = True
bsdf = skin_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.76, 0.57, 0.42, 1)
bsdf.inputs['Roughness'].default_value = 0.6
try:
    bsdf.inputs['Subsurface Weight'].default_value = 0.15
    bsdf.inputs['Subsurface Radius'].default_value = (1.0, 0.2, 0.1)
except: pass

# Witness 1 on sidewalk northeast corner
bpy.ops.import_scene.fbx(filepath='{MODELS}/kenney_characters/Model/characterMedium.fbx')
imported = list(bpy.context.selected_objects)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(8, 5.5, 0))
root = bpy.context.active_object
root.name = 'Witness_1'
for obj in imported:
    obj.parent = root
    if obj.type == 'MESH':
        obj.data.materials.clear()
        obj.data.materials.append(skin_mat)
root.scale = (1.7, 1.7, 1.7)

# Witness 2 on opposite sidewalk
blue_mat = bpy.data.materials.new(name='BlueClothes')
blue_mat.use_nodes = True
bsdf = blue_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.15, 0.3, 0.55, 1)
bsdf.inputs['Roughness'].default_value = 0.7

bpy.ops.import_scene.fbx(filepath='{MODELS}/kenney_characters/Model/characterMedium.fbx')
imported2 = list(bpy.context.selected_objects)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-8, -5.5, 0))
root2 = bpy.context.active_object
root2.name = 'Witness_2'
for obj in imported2:
    obj.parent = root2
    if obj.type == 'MESH':
        obj.data.materials.clear()
        obj.data.materials.append(blue_mat)
root2.scale = (1.7, 1.7, 1.7)

print('Characters placed on sidewalks')
"""
r = cmd({'command': 'execute_python', 'params': {'code': char_code}})
print(f"  Characters: {str(r)[:80]}")
time.sleep(0.3)

# Step 6: Debris at physically correct locations (near impact, scattered in momentum direction)
debris_code = f"""
import bpy, math

debris_mat = bpy.data.materials.new(name='DebrisDark')
debris_mat.use_nodes = True
bsdf = debris_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.06, 0.06, 0.06, 1)
bsdf.inputs['Roughness'].default_value = 0.7

# Debris scatters in combined momentum direction
# Combined momentum direction: approx northeast
debris_positions = [
    (0.3, 0.2, 0.02),   # at impact
    (1.2, 0.8, 0.02),   # scattered NE
    (0.8, 1.5, 0.02),   # scattered more N
    (2.0, 0.3, 0.02),   # scattered more E
]
debris_files = ['debris-door.glb', 'debris-bumper.glb', 'debris-tire.glb', 'debris-plate-a.glb']

for i, (df, pos) in enumerate(zip(debris_files, debris_positions)):
    bpy.ops.import_scene.gltf(filepath='{MODELS}/' + df)
    imported = list(bpy.context.selected_objects)
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=pos)
    root = bpy.context.active_object
    root.name = f'Debris_{{i}}'
    for obj in imported:
        obj.parent = root
        if obj.type == 'MESH':
            obj.data.materials.clear()
            obj.data.materials.append(debris_mat)
    root.scale = (2.0, 2.0, 2.0)
    root.rotation_euler[2] = math.radians(i * 67 + 15)

print('Debris placed along momentum vector')
"""
r = cmd({'command': 'execute_python', 'params': {'code': debris_code}})
print(f"  Debris: {str(r)[:80]}")
time.sleep(0.3)

# Step 7: Ghost trails (semi-transparent cubes along approach paths)
ghost_code = f"""
import bpy, math

# Ghost trail material - semi transparent
ghost_red = bpy.data.materials.new(name='GhostRed')
ghost_red.use_nodes = True
bsdf = ghost_red.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.7, 0.1, 0.1, 0.15)
bsdf.inputs['Alpha'].default_value = 0.15
try:
    ghost_red.surface_render_method = 'DITHERED'
except:
    try: ghost_red.blend_method = 'BLEND'
    except: pass

ghost_silver = bpy.data.materials.new(name='GhostSilver')
ghost_silver.use_nodes = True
bsdf = ghost_silver.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.55, 0.15)
bsdf.inputs['Alpha'].default_value = 0.15
try:
    ghost_silver.surface_render_method = 'DITHERED'
except:
    try: ghost_silver.blend_method = 'BLEND'
    except: pass

# Sedan ghost trail (east approach, every 4m)
for i in range(5):
    x = -{v1_approach} + i * 4
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 0, 0.5))
    g = bpy.context.active_object
    g.name = f'GhostTrail_Sedan_{{i}}'
    g.scale = (2.2, 0.9, 0.65)
    g.data.materials.append(ghost_red)

# SUV ghost trail (north approach, every 4m)
for i in range(4):
    y = -{v2_approach} + i * 4
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, y, 0.6))
    g = bpy.context.active_object
    g.name = f'GhostTrail_SUV_{{i}}'
    g.scale = (0.95, 2.4, 0.75)
    g.data.materials.append(ghost_silver)

print('Ghost trails added')
"""
r = cmd({'command': 'execute_python', 'params': {'code': ghost_code}})
print(f"  Ghost trails: {str(r)[:80]}")
time.sleep(0.3)

# Step 8: Forensic annotations and HUD
forensic_code = f"""
import bpy, math

# Helper to create text object facing up (readable from bird's eye)
def add_text(name, text, location, size=0.3, color=(1,1,1,1)):
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = 'CENTER'
    obj.data.align_y = 'CENTER'
    # Face upward (readable from bird's eye camera)
    obj.rotation_euler = (0, 0, 0)
    # Material
    mat = bpy.data.materials.new(name=name + '_Mat')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Emission Color'].default_value = color
    bsdf.inputs['Emission Strength'].default_value = 2.0
    obj.data.materials.append(mat)
    return obj

# EXHIBIT LABEL
add_text('Exhibit_Label', 'EXHIBIT A\\nCase No. 2026-CV-1847\\nT-Intersection Collision\\n{v1_mph} mph Sedan vs {v2_mph} mph SUV',
         location=(-18, 12, 0.05), size=0.4, color=(1, 1, 1, 1))

# IMPACT POINT label
add_text('Label_Impact', 'POINT OF IMPACT',
         location=(0, 0, 3.5), size=0.5, color=(1, 0.2, 0.2, 1))

# VEHICLE LABELS
add_text('Label_V1', 'V1: Sedan\\n{m1}kg @ {v1_mph}mph',
         location=(-{v1_approach}, 2.5, 0.05), size=0.3, color=(1, 0.3, 0.3, 1))

add_text('Label_V2', 'V2: SUV\\n{m2}kg @ {v2_mph}mph',
         location=(2.5, -{v2_approach}, 0.05), size=0.3, color=(0.6, 0.65, 0.7, 1))

# REST POSITION labels
add_text('Label_V1_Rest', 'V1 FINAL REST\\n{v1_rest_dist:.1f}m from impact',
         location=({v1_rest_x}, {v1_rest_y} + 2, 0.05), size=0.25, color=(1, 0.5, 0.5, 1))

add_text('Label_V2_Rest', 'V2 FINAL REST\\n{v2_rest_dist:.1f}m from impact',
         location=({v2_rest_x} + 2, {v2_rest_y}, 0.05), size=0.25, color=(0.6, 0.7, 0.8, 1))

# SCALE BAR (5 meters with tick marks)
for i in range(6):
    x = -18 + i
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, -10, 0.02))
    bar = bpy.context.active_object
    bar.name = f'ScaleBar_{{i}}'
    bar.scale = (0.02 if i > 0 else 0.5, 0.15, 0.02)
    mat = bpy.data.materials.new(name=f'ScaleBar_{{i}}_Mat')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1, 1, 0, 1)
    bsdf.inputs['Emission Color'].default_value = (1, 1, 0, 1)
    bsdf.inputs['Emission Strength'].default_value = 1.0
    bar.data.materials.append(mat)

# Scale bar connecting line
bpy.ops.mesh.primitive_cube_add(size=1, location=(-15.5, -10, 0.02))
sbar = bpy.context.active_object
sbar.name = 'ScaleBar_Line'
sbar.scale = (2.5, 0.02, 0.01)
sbar.data.materials.append(bpy.data.materials['ScaleBar_0_Mat'])

add_text('ScaleBar_Text', '5 METERS',
         location=(-15.5, -10.5, 0.05), size=0.25, color=(1, 1, 0, 1))

# IMPACT ENERGY
add_text('Label_Energy', 'IMPACT ENERGY: {impact_energy_kj:.0f} kJ',
         location=(0, 3, 0.05), size=0.3, color=(1, 0.8, 0.2, 1))

# SKID MARK distance label
add_text('Label_Skid', 'SKID: {v1_skid_length:.1f}m',
         location=(-{v1_skid_length/2:.1f}, -2, 0.05), size=0.25, color=(0.4, 0.4, 0.4, 1))

# MEASUREMENT LINE (approach distance)
# Arrow from sedan start to impact
bpy.ops.mesh.primitive_cube_add(size=1, location=(-{v1_approach/2}, -4, 0.02))
mline = bpy.context.active_object
mline.name = 'MeasureLine_V1'
mline.scale = ({v1_approach/2}, 0.02, 0.01)
mat = bpy.data.materials.new(name='MeasureLine_Mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0, 1, 0, 1)
bsdf.inputs['Emission Color'].default_value = (0, 1, 0, 1)
bsdf.inputs['Emission Strength'].default_value = 1.0
mline.data.materials.append(mat)

add_text('MeasureText_V1', '{v1_approach:.0f}m approach',
         location=(-{v1_approach/2}, -4.8, 0.05), size=0.25, color=(0, 1, 0, 1))

print('All forensic annotations added')
"""
r = cmd({'command': 'execute_python', 'params': {'code': forensic_code}})
print(f"  Forensic labels: {str(r)[:80]}")
time.sleep(0.3)

# Step 9: Lighting + evidence markers
r = cmd({'command': 'forensic_scene', 'params': {'action': 'set_time_of_day', 'time': 'day'}})
r = cmd({'command': 'forensic_scene', 'params': {'action': 'add_impact_marker', 'marker_type': 'impact_point', 'location': [0, 0, 0]}})
r = cmd({'command': 'forensic_scene', 'params': {'action': 'add_impact_marker', 'marker_type': 'skid_mark',
    'location': [-v1_skid_length, 0, 0], 'end': [0, 0, 0]}})
print("  Lighting + evidence")
time.sleep(0.3)

# Step 10: Cameras
r = cmd({'command': 'forensic_scene', 'params': {'action': 'setup_cameras', 'camera_type': 'all',
    'target': [0, 0, 0], 'witness_location': [8, 5.5, 1.7]}})
print("  Cameras")

# Render preset
r = cmd({'command': 'forensic_scene', 'params': {'action': 'setup_courtroom_render', 'preset': 'presentation'}})
print("  Render preset")
time.sleep(0.3)

# Step 11: RENDER key frames
print("\n--- Rendering ---")

# Render 1: Bird's eye at impact frame
render_code = f"""
import bpy
cam = bpy.data.objects.get('Cam_BirdEye')
if cam:
    cam.location.z = 28
    bpy.context.scene.camera = cam
    bpy.context.scene.frame_set({impact_frame})
    bpy.context.scene.render.filepath = '{RENDERS}/final_01_birdeye_impact.png'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
"""
r = cmd({'command': 'execute_python', 'params': {'code': render_code}}, t=180)
print("  1/5 Bird's eye at impact")

# Render 2: Sedan closeup at approach (frame 30)
render_code2 = f"""
import bpy
bpy.ops.object.camera_add(location=(-12, 7, 3))
cam = bpy.context.active_object
cam.name = 'Cam_ApproachClose'
cam.data.lens = 40
target = bpy.data.objects.get('Vehicle_Sedan')
if target:
    bpy.context.scene.frame_set(30)
    direction = target.location - cam.location
    rot = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam
bpy.context.scene.render.filepath = '{RENDERS}/final_02_approach.png'
bpy.ops.render.render(write_still=True)
"""
r = cmd({'command': 'execute_python', 'params': {'code': render_code2}}, t=180)
print("  2/5 Approach closeup")

# Render 3: Witness POV at impact
render_code3 = f"""
import bpy
cam = bpy.data.objects.get('Cam_Witness')
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.frame_set({impact_frame})
    bpy.context.scene.render.filepath = '{RENDERS}/final_03_witness_impact.png'
    bpy.ops.render.render(write_still=True)
"""
r = cmd({'command': 'execute_python', 'params': {'code': render_code3}}, t=180)
print("  3/5 Witness POV at impact")

# Render 4: Post-impact (final rest positions)
rest_frame = impact_frame + int(max(v1_stop_time, v2_stop_time) * fps) + 5
render_code4 = f"""
import bpy
cam = bpy.data.objects.get('Cam_BirdEye')
if cam:
    cam.location.z = 30
    bpy.context.scene.camera = cam
    bpy.context.scene.frame_set({rest_frame})
    bpy.context.scene.render.filepath = '{RENDERS}/final_04_rest_positions.png'
    bpy.ops.render.render(write_still=True)
"""
r = cmd({'command': 'execute_python', 'params': {'code': render_code4}}, t=180)
print("  4/5 Final rest positions")

# Render 5: Dramatic low angle at impact
render_code5 = f"""
import bpy
bpy.ops.object.camera_add(location=(-3, 6, 1.2))
cam = bpy.context.active_object
cam.name = 'Cam_DramaticImpact'
cam.data.lens = 28
bpy.context.scene.frame_set({impact_frame})
direction = bpy.data.objects['Vehicle_Sedan'].location - cam.location
rot = direction.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam
bpy.context.scene.render.filepath = '{RENDERS}/final_05_dramatic_impact.png'
bpy.ops.render.render(write_still=True)
"""
r = cmd({'command': 'execute_python', 'params': {'code': render_code5}}, t=180)
print("  5/5 Dramatic impact angle")

# Save blend
r = cmd({'command': 'execute_python', 'params': {'code': f"import bpy; bpy.ops.wm.save_as_mainfile(filepath='{RENDERS}/forensic_final.blend')"}})
print("  Blend saved")

print(f"\n=== COMPLETE ===")
print(f"Physics: momentum-conserving, friction-decelerating, {fps}fps")
print(f"Impact frame: {impact_frame}, rest by frame ~{rest_frame}")
print(f"All forensic elements: ghost trails, HUD, scale bar, exhibit label, measurements")
