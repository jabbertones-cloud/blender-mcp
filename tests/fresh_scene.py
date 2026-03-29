#!/usr/bin/env python3
"""Build a complete fresh scene from scratch with imported Kenney models and clean materials."""
import socket, json, time

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
# STEP 1: NUKE EVERYTHING
# ============================================================
print("Step 1: Clearing scene...")
r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy
# Delete everything
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for img in list(bpy.data.images):
    bpy.data.images.remove(img)

# Write confirmation
with open('/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/step_log.txt', 'w') as f:
    f.write(f"After clear: {len(bpy.data.objects)} objects, {len(bpy.data.materials)} mats\\n")
"""}})
print(f"  Clear: {r}")
time.sleep(0.5)

# ============================================================
# STEP 2: BUILD ROAD
# ============================================================
print("Step 2: Building road...")
r = cmd({'command': 'forensic_scene', 'params': {
    'action': 'add_scene_template', 'template': 't_intersection'
}})
print(f"  Road: {str(r)[:60]}")
time.sleep(0.3)

# ============================================================
# STEP 3: IMPORT SEDAN + APPLY CLEAN RED MATERIAL
# ============================================================
print("Step 3: Importing sedan...")
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy, math

# Import
bpy.ops.import_scene.gltf(filepath='{MODELS}/sedan.glb')
imported = list(bpy.context.selected_objects)

# Create parent empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(-20, 0, 0.01))
root = bpy.context.active_object
root.name = 'Vehicle_Sedan'

for obj in imported:
    obj.parent = root

root.scale = (2.2, 2.2, 2.2)

# Create red paint material
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

# FORCE replace ALL materials on ALL imported meshes
for obj in imported:
    if obj.type != 'MESH':
        continue
    # Remove all existing materials
    obj.data.materials.clear()
    # Add our clean material
    obj.data.materials.append(red_mat)

with open('{RENDERS}/step_log.txt', 'a') as f:
    f.write(f"Sedan: {{len(imported)}} objects imported, all mats replaced with SedanRed\\n")
    for o in imported:
        f.write(f"  {{o.name}} type={{o.type}}\\n")
"""}})
print(f"  Sedan: {str(r)[:80]}")
time.sleep(0.3)

# ============================================================
# STEP 4: IMPORT SUV + APPLY CLEAN SILVER MATERIAL
# ============================================================
print("Step 4: Importing SUV...")
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy, math

bpy.ops.import_scene.gltf(filepath='{MODELS}/suv.glb')
imported = list(bpy.context.selected_objects)

bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, -18, 0.01))
root = bpy.context.active_object
root.name = 'Vehicle_SUV'
for obj in imported:
    obj.parent = root
root.scale = (2.2, 2.2, 2.2)
root.rotation_euler[2] = math.radians(90)

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

for obj in imported:
    if obj.type != 'MESH':
        continue
    obj.data.materials.clear()
    obj.data.materials.append(silver_mat)

with open('{RENDERS}/step_log.txt', 'a') as f:
    f.write(f"SUV: {{len(imported)}} objects imported\\n")
"""}})
print(f"  SUV: {str(r)[:80]}")
time.sleep(0.3)

# ============================================================
# STEP 5: IMPORT CHARACTERS
# ============================================================
print("Step 5: Importing characters...")
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy

# Character 1 - witness
bpy.ops.import_scene.fbx(filepath='{MODELS}/kenney_characters/Model/characterMedium.fbx')
imported = list(bpy.context.selected_objects)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(14, 10, 0))
root = bpy.context.active_object
root.name = 'Witness_1'
for obj in imported:
    obj.parent = root
root.scale = (1.7, 1.7, 1.7)

skin_mat = bpy.data.materials.new(name='Skin')
skin_mat.use_nodes = True
bsdf = skin_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.76, 0.57, 0.42, 1)
bsdf.inputs['Roughness'].default_value = 0.6

for obj in imported:
    if obj.type == 'MESH':
        obj.data.materials.clear()
        obj.data.materials.append(skin_mat)

# Character 2
bpy.ops.import_scene.fbx(filepath='{MODELS}/kenney_characters/Model/characterMedium.fbx')
imported2 = list(bpy.context.selected_objects)
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(12, -8, 0))
root2 = bpy.context.active_object
root2.name = 'Witness_2'
for obj in imported2:
    obj.parent = root2
root2.scale = (1.7, 1.7, 1.7)

blue_mat = bpy.data.materials.new(name='BlueShirt')
blue_mat.use_nodes = True
bsdf = blue_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.15, 0.3, 0.55, 1)
bsdf.inputs['Roughness'].default_value = 0.7

for obj in imported2:
    if obj.type == 'MESH':
        obj.data.materials.clear()
        obj.data.materials.append(blue_mat)

with open('{RENDERS}/step_log.txt', 'a') as f:
    f.write(f"Characters: {{len(imported)}} + {{len(imported2)}} objects\\n")
"""}})
print(f"  Chars: {str(r)[:80]}")
time.sleep(0.3)

# ============================================================
# STEP 6: IMPORT DEBRIS WITH DARK MATERIAL
# ============================================================
print("Step 6: Importing debris...")
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy, math

debris_mat = bpy.data.materials.new(name='DebrisDark')
debris_mat.use_nodes = True
bsdf = debris_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.06, 0.06, 0.06, 1)
bsdf.inputs['Roughness'].default_value = 0.7

debris_files = ['debris-door.glb', 'debris-bumper.glb', 'debris-tire.glb', 'debris-plate-a.glb']
for i, df in enumerate(debris_files):
    bpy.ops.import_scene.gltf(filepath='{MODELS}/' + df)
    imported = list(bpy.context.selected_objects)
    bpy.ops.object.empty_add(type='PLAIN_AXES',
        location=(0.5 + i*0.9, -0.5 + i*0.6, 0.05))
    root = bpy.context.active_object
    root.name = f'Debris_{{i}}'
    for obj in imported:
        obj.parent = root
        if obj.type == 'MESH':
            obj.data.materials.clear()
            obj.data.materials.append(debris_mat)
    root.scale = (2.0, 2.0, 2.0)
    root.rotation_euler[2] = math.radians(i * 73)

with open('{RENDERS}/step_log.txt', 'a') as f:
    f.write("Debris: 4 pieces\\n")
"""}})
print(f"  Debris: {str(r)[:80]}")
time.sleep(0.3)

# ============================================================
# STEP 7: LIGHTING + EVIDENCE + CAMERAS
# ============================================================
print("Step 7: Lighting, evidence, cameras...")
r = cmd({'command': 'forensic_scene', 'params': {'action': 'set_time_of_day', 'time': 'day'}})
print(f"  Light: {str(r)[:50]}")

r = cmd({'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'impact_point', 'location': [0, 0, 0]
}})
r = cmd({'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'skid_mark', 'location': [-18, 0, 0], 'end': [0, 0, 0]
}})
r = cmd({'command': 'forensic_scene', 'params': {
    'action': 'add_annotation', 'annotation_type': 'label', 'location': [0, 0, 4], 'text': 'POINT OF IMPACT'
}})
print("  Evidence markers done")

r = cmd({'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras', 'camera_type': 'all', 'target': [0, 0, 0],
    'witness_location': [20, 18, 1.7]
}})
print(f"  Cameras: {str(r)[:50]}")

r = cmd({'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render', 'preset': 'presentation'
}})
print(f"  Render preset: {str(r)[:50]}")
time.sleep(0.3)

# ============================================================
# STEP 8: VERIFY SCENE STATE
# ============================================================
print("Step 8: Verifying scene...")
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy
with open('{RENDERS}/step_log.txt', 'a') as f:
    f.write(f"\\nFINAL SCENE: {{len(bpy.data.objects)}} objects, {{len(bpy.data.materials)}} materials\\n")
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            mats = [s.material.name if s.material else 'NONE' for s in obj.material_slots]
            has_img = False
            for s in obj.material_slots:
                if s.material and s.material.use_nodes:
                    for n in s.material.node_tree.nodes:
                        if n.type == 'TEX_IMAGE':
                            has_img = True
            f.write(f"  MESH {{obj.name}} mats={{mats}} has_img_tex={{has_img}}\\n")
"""}})
print(f"  Verify: {str(r)[:60]}")
time.sleep(0.3)

# ============================================================
# STEP 9: RENDER
# ============================================================
print("Step 9: Rendering...")

# Lower bird's eye
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy
cam = bpy.data.objects.get('Cam_BirdEye')
if cam:
    cam.location.z = 25
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '{RENDERS}/fresh_01_birdeye.png'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
"""}}, t=180)
print("  Bird's eye done")

# Sedan closeup
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy
bpy.ops.object.camera_add(location=(-16, 6, 3))
cam = bpy.context.active_object
cam.name = 'Cam_SedanClose'
cam.data.lens = 50
target = bpy.data.objects.get('Vehicle_Sedan')
if target:
    direction = target.location - cam.location
    rot = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam
bpy.context.scene.render.filepath = '{RENDERS}/fresh_02_sedan.png'
bpy.ops.render.render(write_still=True)
"""}}, t=180)
print("  Sedan closeup done")

# Witness POV
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy
cam = bpy.data.objects.get('Cam_Witness')
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '{RENDERS}/fresh_03_witness.png'
    bpy.ops.render.render(write_still=True)
"""}}, t=180)
print("  Witness POV done")

# Dramatic low angle
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy
bpy.ops.object.camera_add(location=(-5, 8, 1.5))
cam = bpy.context.active_object
cam.name = 'Cam_Dramatic'
cam.data.lens = 35
target = bpy.data.objects.get('Vehicle_Sedan')
if target:
    direction = target.location - cam.location
    rot = direction.to_track_quat('-Z', 'Y')
    cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam
bpy.context.scene.render.filepath = '{RENDERS}/fresh_04_dramatic.png'
bpy.ops.render.render(write_still=True)
"""}}, t=180)
print("  Dramatic done")

# Save blend
r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy
bpy.ops.wm.save_as_mainfile(filepath='{RENDERS}/fresh_scene.blend')
"""}})
print("  Blend saved")

print("\nALL DONE - check renders/fresh_*.png")
