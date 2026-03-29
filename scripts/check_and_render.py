#!/usr/bin/env python3
"""Check scene state and render test frames."""
import socket
import json
import sys

def send_cmd(code):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(120)
    sock.connect(('127.0.0.1', 9876))
    cmd = {'command': 'execute_python', 'code': code}
    sock.sendall(json.dumps(cmd).encode('utf-8'))
    data = b''
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        data += chunk
    sock.close()
    return json.loads(data.decode('utf-8'))

# Step 1: Check scene state
print("=== CHECKING SCENE STATE ===")
result = send_cmd("""
import bpy
scene = bpy.context.scene
cam = scene.camera
objs = [o.name for o in bpy.data.objects if o.type == 'MESH']
mats = [m.name for m in bpy.data.materials]
lights = [o.name for o in bpy.data.objects if o.type == 'LIGHT']
print(f'Camera: {cam.name if cam else "NONE"}')
print(f'Mesh objects: {len(objs)}')
print(f'Materials: {len(mats)}')
print(f'Lights: {len(lights)} - {lights[:5]}')
print(f'Render engine: {scene.render.engine}')
print(f'Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}')
print(f'Frame range: {scene.frame_start}-{scene.frame_end}')
print(f'Color mgmt: {scene.view_settings.view_transform}')
print(f'Look: {scene.view_settings.look}')
# Check if buildings have materials
bldg_count = 0
textured_count = 0
for o in bpy.data.objects:
    if o.type == 'MESH' and 'uild' in o.name:
        bldg_count += 1
        if o.data.materials:
            textured_count += 1
result = f'Buildings: {bldg_count}, With materials: {textured_count}, Total meshes: {len(objs)}'
""")
print(result)

# Step 2: Render frame 1 at lower res for quick test
print("\n=== RENDERING TEST FRAME ===")
result = send_cmd("""
import bpy
scene = bpy.context.scene
# Lower res for quick test
scene.render.resolution_x = 960
scene.render.resolution_y = 540
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.frame_set(1)
scene.render.filepath = '/tmp/city_v10_frame001.png'
bpy.ops.render.render(write_still=True)
result = 'Rendered frame 1 to /tmp/city_v10_frame001.png'
""")
print(result)

# Step 3: Render frame 120
print("\n=== RENDERING FRAME 120 ===")
result = send_cmd("""
import bpy
scene = bpy.context.scene
scene.frame_set(120)
scene.render.filepath = '/tmp/city_v10_frame120.png'
bpy.ops.render.render(write_still=True)
result = 'Rendered frame 120 to /tmp/city_v10_frame120.png'
""")
print(result)

print("\n=== DONE ===")
print("Renders saved to /tmp/city_v10_frame001.png and /tmp/city_v10_frame120.png")
