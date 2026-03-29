#!/usr/bin/env python3
'''
v22 3-Layer Denoising Pipeline
Connects to Blender MCP, applies render-time denoising settings,
and renders all cameras from 4 forensic scenes.
'''

import socket
import json
import os
import sys
import time

PROJECT_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp'
RENDERS_DIR = os.path.join(PROJECT_DIR, 'renders')
V22_OUTPUT_DIR = os.path.join(RENDERS_DIR, 'v22_final')

# Scene definitions
SCENES = {
    'scene1': {
        'blend_file': os.path.join(RENDERS_DIR, 'v11_scene1.blend'),
        'cameras': ['Cam_BirdEye', 'Cam_DriverPOV', 'Cam_WideAngle']
    },
    'scene2': {
        'blend_file': os.path.join(RENDERS_DIR, 'v11_scene2.blend'),
        'cameras': ['Cam_BirdEye', 'Cam_DriverPOV', 'Cam_SightLine', 'Cam_WideAngle']
    },
    'scene3': {
        'blend_file': os.path.join(RENDERS_DIR, 'v11_scene3.blend'),
        'cameras': ['Cam_BirdEye', 'Cam_DriverPOV', 'Cam_WideAngle']
    },
    'scene4': {
        'blend_file': os.path.join(RENDERS_DIR, 'v11_scene4.blend'),
        'cameras': ['Cam_BirdEye', 'Cam_DriverPOV', 'Cam_SecurityCam', 'Cam_WideAngle']
    }
}

class BlenderMCPClient:
    """TCP socket client for Blender MCP communication"""
    
    def __init__(self, host='127.0.0.1', port=9876):
        self.host = host
        self.port = port
        self.socket = None
        self.request_id = 0
        
    def connect(self):
        """Connect to Blender MCP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f'Connected to Blender MCP at {self.host}:{self.port}')
            return True
        except Exception as e:
            print(f'Failed to connect: {e}')
            return False
    
    def disconnect(self):
        """Close connection"""
        if self.socket:
            self.socket.close()
    
    def _read_response(self):
        """Read response by counting brace depth (JSON-based protocol)"""
        response_str = ''
        brace_count = 0
        in_response = False
        
        while True:
            try:
                char = self.socket.recv(1).decode('utf-8')
                if not char:
                    break
                
                response_str += char
                
                if char == '{':
                    in_response = True
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if in_response and brace_count == 0:
                        break
            except socket.timeout:
                break
            except Exception as e:
                print(f'Error reading response: {e}')
                break
        
        if response_str:
            try:
                return json.loads(response_str)
            except json.JSONDecodeError as e:
                print(f'Failed to parse JSON: {e}')
                print(f'Raw response: {response_str}')
                return None
        return None
    
    def execute_python(self, code):
        """Execute Python code in Blender"""
        self.request_id += 1
        request = {
            'id': self.request_id,
            'command': 'execute_python',
            'params': {'code': code}
        }
        
        try:
            self.socket.sendall(json.dumps(request).encode('utf-8'))
            response = self._read_response()
            
            if response and 'result' in response:
                result = response['result']
                if isinstance(result, dict) and 'result' in result:
                    return result['result']
                return result
            return response
        except Exception as e:
            print(f'Error executing Python: {e}')
            return None
    
    def save_file(self, filepath):
        """Save Blender file"""
        self.request_id += 1
        request = {
            'id': self.request_id,
            'command': 'save_file',
            'params': {'filepath': filepath}
        }
        
        try:
            self.socket.sendall(json.dumps(request).encode('utf-8'))
            response = self._read_response()
            return response
        except Exception as e:
            print(f'Error saving file: {e}')
            return None
    
    def render(self, output_path):
        """Render scene"""
        self.request_id += 1
        request = {
            'id': self.request_id,
            'command': 'render',
            'params': {'output_path': output_path}
        }
        
        try:
            self.socket.sendall(json.dumps(request).encode('utf-8'))
            response = self._read_response()
            return response
        except Exception as e:
            print(f'Error rendering: {e}')
            return None

def ensure_output_dir():
    """Create v22_final output directory if needed"""
    os.makedirs(V22_OUTPUT_DIR, exist_ok=True)
    print(f'Output directory: {V22_OUTPUT_DIR}')

def apply_denoising_settings(client, scene_name):
    """Apply v22 denoising settings to current scene"""
    code = '''
import bpy
scene = bpy.context.scene

# Cycles render settings
scene.cycles.samples = 256
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.002
scene.cycles.denoiser = 'OPENIMAGEDENOISE'

# Enable denoising data passes
scene.cycles.use_denoising_prefilter = True

# Disable caustics for cleaner results
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False

# Clamp indirect light
scene.cycles.sample_clamp_indirect = 10.0

# Filter glossy
scene.cycles.filter_glossy = 1.0

__result__ = {
    'status': 'success',
    'message': 'Denoising settings applied',
    'samples': scene.cycles.samples,
    'adaptive_threshold': scene.cycles.adaptive_threshold
}
'''
    
    print(f'Applying denoising settings to {scene_name}...')
    result = client.execute_python(code)
    print(f'  Result: {result}')
    return result

def open_blend_file(client, filepath):
    """Open a .blend file in Blender"""
    code = f'''
import bpy
bpy.ops.wm.open_mainfile(filepath='{filepath}')
__result__ = {{'status': 'opened', 'file': '{filepath}'}}
'''
    
    print(f'Opening {filepath}...')
    result = client.execute_python(code)
    print(f'  Opened: {result}')
    time.sleep(2)  # Give Blender time to load
    return result

def render_camera(client, scene_name, camera_name, output_path):
    """Render a specific camera"""
    code = f'''
import bpy
scene = bpy.context.scene
camera_obj = bpy.data.objects.get('{camera_name}')

if camera_obj:
    scene.camera = camera_obj
    scene.render.filepath = '{output_path}'
    bpy.ops.render.render(write_still=True)
    __result__ = {{'status': 'rendered', 'camera': '{camera_name}', 'output': '{output_path}'}}
else:
    __result__ = {{'status': 'error', 'message': 'Camera {camera_name} not found'}}
'''
    
    print(f'  Rendering {camera_name}...')
    result = client.execute_python(code)
    print(f'    Result: {result}')
    return result

def check_render_engine(client):
    """Check current render engine"""
    code = '''
import bpy
engine = bpy.context.scene.render.engine
__result__ = {'engine': engine}
'''
    
    result = client.execute_python(code)
    return result.get('engine') if result else None

def save_modified_blend(client, output_filepath):
    """Save modified .blend file"""
    code = f'''
import bpy
bpy.ops.wm.save_as_mainfile(filepath='{output_filepath}')
__result__ = {{'status': 'saved', 'filepath': '{output_filepath}'}}
'''
    
    print(f'Saving modified blend to {output_filepath}...')
    result = client.execute_python(code)
    print(f'  Saved: {result}')
    return result

def process_scene(client, scene_name, scene_config):
    """Process a single scene: open, apply settings, render all cameras, save"""
    blend_file = scene_config['blend_file']
    cameras = scene_config['cameras']
    
    print(f'\n--- Processing {scene_name} ---')
    
    # Open scene
    open_result = open_blend_file(client, blend_file)
    if not open_result:
        print(f'Failed to open {blend_file}')
        return False
    
    # Check engine
    engine = check_render_engine(client)
    print(f'Render engine: {engine}')
    
    # Apply denoising settings
    denoise_result = apply_denoising_settings(client, scene_name)
    if not denoise_result:
        print(f'Failed to apply denoising settings')
        return False
    
    # Render all cameras
    render_count = 0
    for camera_name in cameras:
        output_filename = f'{scene_name}_{camera_name}.png'
        output_path = os.path.join(V22_OUTPUT_DIR, output_filename)
        
        render_result = render_camera(client, scene_name, camera_name, output_path)
        if render_result and 'error' not in str(render_result):
            render_count += 1
        time.sleep(1)  # Delay between renders
    
    print(f'Rendered {render_count}/{len(cameras)} cameras')
    
    # Save modified blend
    output_blend = os.path.join(RENDERS_DIR, f'v22_{scene_name}.blend')
    save_result = save_modified_blend(client, output_blend)
    
    return render_count > 0

def main():
    """Main pipeline"""
    print('v22 3-Layer Denoising Pipeline')
    print(f'Project: {PROJECT_DIR}')
    print(f'Output: {V22_OUTPUT_DIR}')
    
    # Ensure output directory
    ensure_output_dir()
    
    # Connect to Blender MCP
    client = BlenderMCPClient()
    if not client.connect():
        print('Cannot connect to Blender MCP')
        sys.exit(1)
    
    try:
        # Process each scene
        results = {}
        for scene_name, scene_config in SCENES.items():
            success = process_scene(client, scene_name, scene_config)
            results[scene_name] = 'success' if success else 'failed'
        
        # Summary
        print('\n--- Pipeline Summary ---')
        for scene_name, status in results.items():
            print(f'{scene_name}: {status}')
        
        success_count = sum(1 for s in results.values() if s == 'success')
        print(f'\nCompleted: {success_count}/{len(SCENES)} scenes')
        
    finally:
        client.disconnect()
        print('Disconnected from Blender MCP')

if __name__ == '__main__':
    main()
