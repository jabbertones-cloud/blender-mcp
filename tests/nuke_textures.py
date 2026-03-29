#!/usr/bin/env python3
"""Nuclear fix: remove ALL image texture nodes from ALL materials, replace with solid colors."""
import socket, json, time

def cmd(c, t=120):
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

# Step 1: List all objects and their materials
r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mats = [s.material.name if s.material else 'NONE' for s in obj.material_slots]
        print(f"OBJ: {obj.name} MATS: {mats}")
"""}})
print("OBJECTS:", str(r)[:3000])

time.sleep(0.3)

# Step 2: Nuclear material fix - remove ALL image textures, replace with solid colors
r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy

fixed = 0
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue

    tree = mat.node_tree
    bsdf_nodes = [n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED']
    img_nodes = [n for n in tree.nodes if n.type == 'TEX_IMAGE']

    if not img_nodes:
        continue

    # Get the BSDF
    if not bsdf_nodes:
        continue
    bsdf = bsdf_nodes[0]

    # Check what the image texture was connected to
    for img_node in img_nodes:
        # Remove ALL links from this image node
        for link in list(tree.links):
            if link.from_node == img_node:
                tree.links.remove(link)
        # Remove the image node itself
        tree.nodes.remove(img_node)

    # Also remove any other intermediate nodes (Normal Map, etc)
    for node in list(tree.nodes):
        if node.type in ('NORMAL_MAP', 'BUMP', 'MAPPING', 'TEX_COORD', 'SEPARATE_COLOR', 'MIX'):
            for link in list(tree.links):
                if link.from_node == node or link.to_node == node:
                    tree.links.remove(link)
            tree.nodes.remove(node)

    # Now set a reasonable base color based on material name
    mn = mat.name.lower()

    if 'red' in mn or 'paint' in mn:
        bsdf.inputs['Base Color'].default_value = (0.72, 0.04, 0.04, 1)
        bsdf.inputs['Metallic'].default_value = 0.85
        bsdf.inputs['Roughness'].default_value = 0.15
    elif 'silver' in mn:
        bsdf.inputs['Base Color'].default_value = (0.6, 0.62, 0.65, 1)
        bsdf.inputs['Metallic'].default_value = 0.9
        bsdf.inputs['Roughness'].default_value = 0.12
    else:
        # Generic Kenney material - likely the atlas texture
        # Set a neutral dark gray as fallback
        bsdf.inputs['Base Color'].default_value = (0.15, 0.15, 0.17, 1)
        bsdf.inputs['Metallic'].default_value = 0.3
        bsdf.inputs['Roughness'].default_value = 0.5

    fixed += 1

print(f"Nuked image textures from {fixed} materials")

# Now do per-object material assignment based on parent hierarchy
# First, understand the hierarchy
for obj in bpy.data.objects:
    if obj.type == 'MESH' and obj.parent:
        root = obj
        while root.parent:
            root = root.parent
        rn = root.name

        # Kenney models: single mesh per vehicle, material atlas
        # We need to assign materials per-face, but that's complex
        # Instead, just make sure the single material looks good

        if 'Sedan' in rn:
            # Make sedan red metallic
            for slot in obj.material_slots:
                if slot.material:
                    bsdf = None
                    for n in slot.material.node_tree.nodes:
                        if n.type == 'BSDF_PRINCIPLED':
                            bsdf = n
                            break
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = (0.65, 0.04, 0.04, 1)
                        bsdf.inputs['Metallic'].default_value = 0.85
                        bsdf.inputs['Roughness'].default_value = 0.18
                        try:
                            bsdf.inputs['Coat Weight'].default_value = 0.8
                            bsdf.inputs['Coat Roughness'].default_value = 0.03
                        except: pass

        elif 'SUV' in rn:
            for slot in obj.material_slots:
                if slot.material:
                    bsdf = None
                    for n in slot.material.node_tree.nodes:
                        if n.type == 'BSDF_PRINCIPLED':
                            bsdf = n
                            break
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = (0.55, 0.57, 0.6, 1)
                        bsdf.inputs['Metallic'].default_value = 0.9
                        bsdf.inputs['Roughness'].default_value = 0.12
                        try:
                            bsdf.inputs['Coat Weight'].default_value = 0.85
                            bsdf.inputs['Coat Roughness'].default_value = 0.02
                        except: pass

        elif 'Witness' in rn or 'character' in rn.lower():
            for slot in obj.material_slots:
                if slot.material:
                    bsdf = None
                    for n in slot.material.node_tree.nodes:
                        if n.type == 'BSDF_PRINCIPLED':
                            bsdf = n
                            break
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = (0.72, 0.55, 0.4, 1)
                        bsdf.inputs['Roughness'].default_value = 0.65
                        bsdf.inputs['Metallic'].default_value = 0.0

        elif 'Debris' in rn:
            for slot in obj.material_slots:
                if slot.material:
                    bsdf = None
                    for n in slot.material.node_tree.nodes:
                        if n.type == 'BSDF_PRINCIPLED':
                            bsdf = n
                            break
                    if bsdf:
                        bsdf.inputs['Base Color'].default_value = (0.08, 0.08, 0.08, 1)
                        bsdf.inputs['Roughness'].default_value = 0.7

print("Per-object materials assigned")
"""}})
print("NUKE FIX:", str(r)[:200])

time.sleep(0.5)

# Step 3: Re-render
cameras = [
    ('Cam_BirdEye', 'real_01_birdeye.png'),
    ('Cam_SedanClose', 'real_02_sedan_closeup.png'),
    ('Cam_Witness', 'real_03_witness.png'),
    ('Cam_DramaticLow', 'real_04_dramatic.png'),
]

for cam_name, fname in cameras:
    code = f"""
import bpy
cam = bpy.data.objects.get('{cam_name}')
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/{fname}'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
    print('RENDERED {cam_name}')
"""
    r = cmd({'command': 'execute_python', 'params': {'code': code}}, t=120)
    print(f"  {cam_name}: done")
    time.sleep(0.3)

# Save
r = cmd({'command': 'execute_python', 'params': {'code': "import bpy; bpy.ops.wm.save_as_mainfile(filepath='/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/real_models_scene.blend')"}})
print("SAVED")
print("ALL DONE")
