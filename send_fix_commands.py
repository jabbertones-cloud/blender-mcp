#!/usr/bin/env python3
"""
Send fix commands to Blender MCP via JSON-RPC.
"""
import socket
import json
import time
import sys

def send_command(cmd_name, script_code):
    """Send a Python script to Blender via MCP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(120)
    
    try:
        print(f"\nConnecting to Blender MCP on port 9876...")
        s.connect(('127.0.0.1', 9876))
        print("Connected!")
        
        # Prepare request
        request = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'execute_python',
            'params': {'code': script_code}
        }
        
        msg = json.dumps(request) + '\n'
        
        print(f"Sending command: {cmd_name}")
        print(f"Script length: {len(script_code)} chars")
        
        s.sendall(msg.encode())
        
        # Read response - with timeout
        response_data = b''
        timeout_count = 0
        max_timeouts = 10
        
        while timeout_count < max_timeouts:
            try:
                chunk = s.recv(16384)
                if not chunk:
                    break
                response_data += chunk
                timeout_count = 0  # Reset on successful read
                print(f"Received {len(chunk)} bytes...")
            except socket.timeout:
                timeout_count += 1
                if timeout_count < max_timeouts:
                    print(f"Waiting for response (timeout {timeout_count}/{max_timeouts})...")
                    time.sleep(1)
                else:
                    break
        
        s.close()
        
        if response_data:
            try:
                resp = json.loads(response_data.decode())
                print(f"Response received: {json.dumps(resp, indent=2)[:500]}...")
                return resp
            except json.JSONDecodeError as e:
                print(f"Failed to parse response: {e}")
                print(f"Raw response: {response_data[:500]}")
                return None
        else:
            print("No response received")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None
    finally:
        try:
            s.close()
        except:
            pass

# Script to fix scene 1
fix_scene_1_code = '''
import bpy
import mathutils

print("\\n=== FIXING SCENE 1 ===")

# Get current scene
scene = bpy.context.scene
print(f"Current scene: {scene.name}")

# Set render engine
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
print("Set EEVEE engine and 1920x1080 resolution")

# Fix world background
world = bpy.data.worlds.get('World')
if world:
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs[0].default_value = (0.3, 0.35, 0.4, 1.0)
        bg_node.inputs[1].default_value = 1.5
        print("Set world background to medium gray (0.3, 0.35, 0.4)")

# Get objects
meshes = [o for o in scene.objects if o.type == 'MESH']
cameras = [o for o in scene.objects if o.type == 'CAMERA']
lights = [o for o in scene.objects if o.type == 'LIGHT']

print(f"Found: {len(meshes)} meshes, {len(cameras)} cameras, {len(lights)} lights")

# Calculate bbox
if meshes:
    min_pos = [float('inf')] * 3
    max_pos = [float('-inf')] * 3
    
    for mesh in meshes:
        for v in mesh.data.vertices:
            wp = mesh.matrix_world @ v.co
            for i in range(3):
                min_pos[i] = min(min_pos[i], wp[i])
                max_pos[i] = max(max_pos[i], wp[i])
    
    bbox_center = mathutils.Vector([(min_pos[i] + max_pos[i]) / 2 for i in range(3)])
    bbox_size = mathutils.Vector([max_pos[i] - min_pos[i] for i in range(3)])
    
    print(f"Bbox center: {bbox_center}")
    print(f"Bbox size: {bbox_size}")
    
    # Boost lights
    for light in lights:
        if light.data.type == 'SUN':
            light.data.energy = 5.0
            print(f"Set {light.name} (SUN) energy to 5.0")
        elif light.data.type == 'AREA':
            light.data.energy = 500.0
            print(f"Set {light.name} (AREA) energy to 500.0")
    
    # Fix cameras
    max_dim = max(bbox_size.x, bbox_size.y, bbox_size.z)
    distance = max(10, max_dim * 1.5)
    
    for cam in cameras:
        cam_name = cam.name.lower()
        
        if 'bird' in cam_name:
            cam.location = bbox_center + mathutils.Vector([0, 0, distance])
        else:
            cam.location = bbox_center + mathutils.Vector([distance*0.5, distance*0.5, distance*0.4])
        
        direction = bbox_center - cam.location
        rot_quat = direction.to_track_quat('-Z', 'Y')
        cam.rotation_euler = rot_quat.to_euler()
        print(f"Aimed {cam.name} at bbox center")

print("\\n=== SCENE 1 FIX COMPLETE ===")
bpy.ops.wm.save_mainfile()
print("Saved scene file")

__result__ = {"status": "fixed", "scene": "1"}
'''

if __name__ == '__main__':
    print("="*60)
    print("SENDING FIX COMMANDS TO BLENDER")
    print("="*60)
    
    # First, open scene 1
    open_scene_code = '''
import bpy
filepath = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_scene1.blend'
bpy.ops.wm.open_mainfile(filepath=filepath)
__result__ = {"status": "opened", "file": filepath}
'''
    
    print("\n1. Opening Scene 1...")
    resp = send_command("Open Scene 1", open_scene_code)
    time.sleep(3)
    
    print("\n2. Fixing Scene 1...")
    resp = send_command("Fix Scene 1", fix_scene_1_code)
    
    print("\n" + "="*60)
    print("DONE")
    print("="*60)
