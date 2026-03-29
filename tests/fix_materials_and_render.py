#!/usr/bin/env python3
"""Fix missing textures on Kenney car models and re-render the forensic scene."""
import socket
import json
import time

def cmd(c, t=120):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(t)
    try:
        s.connect(('127.0.0.1', 9876))
        s.sendall((json.dumps(c) + '\n').encode())
        d = b''
        while True:
            ch = s.recv(16384)
            if not ch:
                break
            d += ch
            try:
                json.loads(d.decode())
                break
            except:
                continue
        r = json.loads(d.decode())
        return r.get('result', r)
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()


# Step 1: Inspect objects
code_inspect = """
import bpy
info = []
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mats = []
        for s in obj.material_slots:
            if s.material:
                mats.append(s.material.name)
            else:
                mats.append('NONE')
        info.append(obj.name + ' -> ' + ', '.join(mats))
for line in info:
    print(line)
"""
r = cmd({'command': 'execute_python', 'params': {'code': code_inspect}})
print("INSPECT:", str(r)[:2000])

time.sleep(0.5)

# Step 2: Force-replace ALL materials on imported car/character objects
code_fix = """
import bpy

# Create clean materials
def make_mat(name, color, metallic=0.0, roughness=0.5):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return mat

tire_mat = make_mat('FixTire', (0.02, 0.02, 0.02), 0.0, 0.85)
rim_mat = make_mat('FixRim', (0.7, 0.7, 0.72), 0.95, 0.15)
glass_mat = make_mat('FixGlass', (0.15, 0.2, 0.25), 0.0, 0.0)
glass_mat.node_tree.nodes['Principled BSDF'].inputs['Alpha'].default_value = 0.3
try:
    glass_mat.surface_render_method = 'DITHERED'
except:
    pass

dark_mat = make_mat('FixDark', (0.04, 0.04, 0.04), 0.0, 0.65)
chrome_mat = make_mat('FixChrome', (0.85, 0.85, 0.87), 1.0, 0.03)

red_paint = make_mat('FixRedPaint', (0.72, 0.04, 0.04), 0.85, 0.15)
try:
    red_paint.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 0.9
    red_paint.node_tree.nodes['Principled BSDF'].inputs['Coat Roughness'].default_value = 0.02
except:
    pass

silver_paint = make_mat('FixSilverPaint', (0.6, 0.62, 0.65), 0.9, 0.12)
try:
    silver_paint.node_tree.nodes['Principled BSDF'].inputs['Coat Weight'].default_value = 0.9
    silver_paint.node_tree.nodes['Principled BSDF'].inputs['Coat Roughness'].default_value = 0.02
except:
    pass

skin_mat = make_mat('FixSkin', (0.76, 0.57, 0.42), 0.0, 0.6)
shirt_mat = make_mat('FixShirt', (0.2, 0.35, 0.6), 0.0, 0.7)
pants_mat = make_mat('FixPants', (0.12, 0.12, 0.18), 0.0, 0.7)

headlight_mat = make_mat('FixHeadlight', (1.0, 0.95, 0.8), 0.0, 0.1)
headlight_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 0.95, 0.8, 1)
headlight_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 3.0

taillight_mat = make_mat('FixTaillight', (0.9, 0.02, 0.02), 0.0, 0.2)
taillight_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.9, 0.02, 0.02, 1)
taillight_mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0

# Determine if an object is part of sedan or SUV by tracing parents
def get_vehicle_root(obj):
    current = obj
    while current.parent:
        current = current.parent
    return current.name

fixed = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue

    root_name = get_vehicle_root(obj)
    is_sedan = 'Sedan' in root_name
    is_suv = 'SUV' in root_name
    is_char = 'Witness' in root_name or 'character' in root_name.lower()
    is_debris = 'Debris' in root_name

    if not (is_sedan or is_suv or is_char or is_debris):
        continue

    n = obj.name.lower()

    # Replace ALL materials on this object
    for i, slot in enumerate(obj.material_slots):
        if is_debris:
            slot.material = dark_mat
            fixed += 1
        elif is_char:
            # Character parts
            if 'head' in n or 'face' in n:
                slot.material = skin_mat
            elif 'hand' in n or 'arm' in n:
                slot.material = skin_mat
            elif 'leg' in n or 'foot' in n:
                slot.material = pants_mat
            else:
                slot.material = shirt_mat
            fixed += 1
        elif 'wheel' in n or 'tire' in n:
            slot.material = tire_mat
            fixed += 1
        elif 'window' in n or 'glass' in n or 'windshield' in n:
            slot.material = glass_mat
            fixed += 1
        elif 'light' in n and ('rear' in n or 'tail' in n or 'back' in n):
            slot.material = taillight_mat
            fixed += 1
        elif 'light' in n or 'headlight' in n:
            slot.material = headlight_mat
            fixed += 1
        elif 'bumper' in n or 'grille' in n or 'trim' in n:
            slot.material = chrome_mat
            fixed += 1
        elif 'body' in n or 'chassis' in n or 'roof' in n or 'hood' in n or 'fender' in n or 'door' in n:
            if is_sedan:
                slot.material = red_paint
            else:
                slot.material = silver_paint
            fixed += 1
        else:
            # For Kenney models, the main mesh is often just named after the model
            # like 'sedan' or 'suv' - apply paint to those too
            if is_sedan:
                slot.material = red_paint
            elif is_suv:
                slot.material = silver_paint
            elif is_char:
                slot.material = shirt_mat
            else:
                slot.material = dark_mat
            fixed += 1

    # If object has no material slots at all, add one
    if len(obj.material_slots) == 0:
        obj.data.materials.append(dark_mat)
        fixed += 1

print(f'Fixed {fixed} material assignments')
"""
r = cmd({'command': 'execute_python', 'params': {'code': code_fix}})
print("FIX:", str(r)[:200])

time.sleep(0.5)

# Step 3: Re-render all 4 cameras
cameras = [
    ('Cam_BirdEye', 'real_01_birdeye.png'),
    ('Cam_SedanClose', 'real_02_sedan_closeup.png'),
    ('Cam_Witness', 'real_03_witness.png'),
    ('Cam_DramaticLow', 'real_04_dramatic.png'),
]

for cam_name, fname in cameras:
    code_render = f"""
import bpy
cam = bpy.data.objects.get('{cam_name}')
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/{fname}'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print('RENDERED {cam_name}')
else:
    print('CAMERA NOT FOUND: {cam_name}')
"""
    r = cmd({'command': 'execute_python', 'params': {'code': code_render}}, t=120)
    print(f"  {cam_name}: {str(r)[:60]}")
    time.sleep(0.3)

# Step 4: Save blend
code_save = "import bpy; bpy.ops.wm.save_as_mainfile(filepath='/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/real_models_scene.blend')"
r = cmd({'command': 'execute_python', 'params': {'code': code_save}})
print("SAVED:", str(r)[:60])

print("\nALL DONE")
