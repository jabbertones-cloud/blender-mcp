#!/usr/bin/env python3
"""Fix wheels to black tires, fix floating, re-render."""
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

RENDERS = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders'

# Fix wheel materials + ground placement
r = cmd({'command': 'execute_python', 'params': {'code': """
import bpy

# Create proper tire material
tire_mat = bpy.data.materials.new(name='BlackTire')
tire_mat.use_nodes = True
bsdf = tire_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.85

# Apply to all wheel objects
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    n = obj.name.lower()
    if 'wheel' in n:
        obj.data.materials.clear()
        obj.data.materials.append(tire_mat)

# Fix floating: nudge vehicles down slightly
for obj in bpy.data.objects:
    if obj.name == 'Vehicle_Sedan':
        obj.location.z = -0.15
    elif obj.name == 'Vehicle_SUV':
        obj.location.z = -0.15

print('Wheels fixed, ground adjusted')
"""}})
print("Fix:", r)
time.sleep(0.3)

# Re-render all 4
cameras = [
    ('Cam_BirdEye', 'fresh_01_birdeye.png'),
    ('Cam_SedanClose', 'fresh_02_sedan.png'),
    ('Cam_Witness', 'fresh_03_witness.png'),
    ('Cam_Dramatic', 'fresh_04_dramatic.png'),
]

for cam_name, fname in cameras:
    code = f"""
import bpy
cam = bpy.data.objects.get('{cam_name}')
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '{RENDERS}/{fname}'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.ops.render.render(write_still=True)
"""
    r = cmd({'command': 'execute_python', 'params': {'code': code}}, t=180)
    print(f"  {cam_name}: done")

# Save
r = cmd({'command': 'execute_python', 'params': {'code': f"import bpy; bpy.ops.wm.save_as_mainfile(filepath='{RENDERS}/fresh_scene.blend')"}})
print("SAVED. DONE.")
