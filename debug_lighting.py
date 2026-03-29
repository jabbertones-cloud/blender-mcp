#!/usr/bin/env python3
import socket
import json
import time

def mcp(cmd, params=None):
    """Send command to Blender MCP on port 9876"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(30)
    try:
        s.connect(('127.0.0.1', 9876))
        msg = json.dumps({'id': 1, 'command': cmd, 'params': params or {}})
        s.sendall(msg.encode())
        data = b''
        depth = 0
        while True:
            chunk = s.recv(4096)
            if not chunk: break
            data += chunk
            for c in chunk.decode(errors='ignore'):
                if c == '{': depth += 1
                elif c == '}': depth -= 1
            if depth == 0: break
        s.close()
        return json.loads(data.decode())
    except Exception as e:
        return {'error': str(e)}

def diagnose_scene(scene_num):
    """Diagnose a single scene"""
    print(f"\n{'='*60}")
    print(f"DIAGNOSING SCENE {scene_num}")
    print(f"{'='*60}")
    
    filepath = f'/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_scene{scene_num}.blend'
    
    # Open scene
    code = f"""
import bpy
bpy.ops.wm.open_mainfile(filepath='{filepath}')
time.sleep(1)

# Check objects
objs = {{o.name: {{'type': o.type, 'loc': tuple(o.location), 'size': tuple(o.scale)}} for o in bpy.data.objects}}
cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
meshes = [o for o in bpy.data.objects if o.type == 'MESH']

result = {{
    'objects': objs,
    'cameras': [(c.name, tuple(c.location), tuple(c.rotation_euler)) for c in cameras],
    'lights': [(l.name, l.data.type, l.data.energy if hasattr(l.data, 'energy') else None) for l in lights],
    'meshes': len(meshes)
}}
__result__ = result
"""
    
    resp = mcp('execute_python', {'code': code})
    
    if 'error' in resp:
        print(f"ERROR: {resp['error']}")
        return
    
    result = resp.get('result', {})
    print(f"Objects: {len(result.get('objects', {}))}")
    print(f"Cameras: {result.get('cameras', [])}")
    print(f"Lights: {result.get('lights', [])}")
    print(f"Meshes: {result.get('meshes', 0)}")

# Diagnose scenes 1-3
for scene_num in [1, 2, 3]:
    diagnose_scene(scene_num)

print("\n" + "="*60)
print("DIAGNOSIS COMPLETE")
print("="*60)
