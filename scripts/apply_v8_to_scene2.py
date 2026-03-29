#!/usr/bin/env python3
"""
Apply v8 Material Improvements to Scene 2 (Pedestrian Crosswalk)

This script:
1. Cleans the Blender scene
2. Builds Scene 2 geometry (road, crosswalk, vehicles, pedestrian)
3. Applies v8 pro_asphalt_material() to road surfaces
4. Applies v8 vehicle paint materials
5. Applies v8 glass materials to windows
6. Sets up forensic lighting (day rig)
7. Adds proper numbered forensic evidence markers (tents, not cartoonish)
8. Sets up camera angles
9. Applies v8 materials to all relevant objects
"""
import sys
import os
import socket
import json
import time

# Add scripts dir to path so we can import v8_materials
sys.path.insert(0, '/Users/tatsheen/claw-architect/openclaw-blender-mcp/scripts')
from v8_materials import (
    pro_asphalt_material,
    pro_vehicle_paint,
    pro_glass_material,
    pro_concrete_material,
    pro_rubber_material,
    pro_lane_marking
)

HOST = "127.0.0.1"
PORT = 9876

def send_to_blender(command, params=None):
    """Send a command to Blender via MCP wire protocol."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(60)
    try:
        sock.connect((HOST, PORT))
        msg = json.dumps({'id': 1, 'command': command, 'params': params or {}})
        sock.sendall(msg.encode())
        
        # Read response with brace-depth parsing
        data = b''
        depth = 0
        in_string = False
        escape = False
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                for byte in chunk:
                    c = chr(byte)
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"' and not escape:
                        in_string = not in_string
                        continue
                    if not in_string:
                        if c == '{': depth += 1
                        elif c == '}':
                            depth -= 1
                            if depth == 0:
                                return json.loads(data.decode())
            except socket.timeout:
                break
        if data:
            return json.loads(data.decode())
    finally:
        sock.close()
    return {'error': 'no response'}

def run_python(code):
    """Execute Python code in Blender and return result."""
    result = send_to_blender('execute_python', {'code': code})
    if 'result' in result:
        res = result['result']
        if isinstance(res, dict):
            if 'error' in res and res['error']:
                print(f"ERROR: {res['error']}")
                if 'traceback' in res:
                    print(f"TRACEBACK: {res['traceback']}")
                return None
            return res.get('result')
    return result

def clean_scene():
    """Clean Blender scene for fresh start."""
    print("[*] Cleaning scene...")
    code = """
import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for bt in [bpy.data.meshes, bpy.data.materials, bpy.data.textures,
           bpy.data.cameras, bpy.data.lights, bpy.data.curves]:
    for b in list(bt):
        if b.users == 0: bt.remove(b)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)
__result__ = 'cleaned'
"""
    return run_python(code)

def setup_render_settings():
    """Setup professional render settings."""
    print("[*] Setting render settings...")
    code = """
import bpy
s = bpy.context.scene
s.render.engine = 'CYCLES'
s.cycles.samples = 256
s.cycles.use_denoising = True
try:
    s.cycles.denoiser = 'OPENIMAGEDENOISE'
except:
    pass
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGBA'
s.view_settings.view_transform = 'Filmic'
s.view_settings.look = 'Medium High Contrast'
s.view_settings.exposure = 0.5
s.render.film_transparent = False
__result__ = 'render_settings_ready'
"""
    return run_python(code)

def build_scene_2_geometry():
    """Build Scene 2 geometry: road, crosswalk, curbs, sidewalks."""
    print("[*] Building Scene 2 geometry...")
    code = """
import bpy
# Road (simple plane for now)
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.02))
road = bpy.context.view_layer.objects.active
road.name = "Road"
road.scale = (1, 3.5, 1)

# Crosswalk stripes
mat = bpy.data.materials.new("Crosswalk")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.92, 0.92, 0.88, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.45
mat.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.7

for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -3 + i*1.2, 0.008))
    stripe = bpy.context.view_layer.objects.active
    stripe.name = f"Crosswalk_{i}"
    stripe.scale = (0.4, 0.5, 0.005)
    stripe.data.materials.append(mat)

# Curbs (concrete)
cm = bpy.data.materials.new("Curb")
cm.use_nodes = True
cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.50, 0.50, 0.47, 1)
cm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.75

for side in [-1, 1]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side*4.5, 0.08))
    curb = bpy.context.view_layer.objects.active
    curb.scale = (80, 0.15, 0.16)
    curb.name = f"Curb_{side}"
    curb.data.materials.append(cm)

# Sidewalk areas
sw = bpy.data.materials.new("Sidewalk")
sw.use_nodes = True
sw.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.62, 0.60, 0.57, 1)
sw.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.82

for side in [-1, 1]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side*6.5, -0.015))
    sidewalk = bpy.context.view_layer.objects.active
    sidewalk.scale = (80, 2.0, 0.01)
    sidewalk.name = f"Sidewalk_{side}"
    sidewalk.data.materials.append(sw)

__result__ = 'geometry_built'
"""
    return run_python(code)

def place_vehicles():
    """Place vehicles in Scene 2."""
    print("[*] Placing vehicles...")
    code = """
import bpy
# Delivery van (involved vehicle)
bpy.ops.mesh.primitive_cube_add(size=1, location=(6, -0.5, 0.4))
van = bpy.context.view_layer.objects.active
van.name = "V1_DeliveryVan"
van.scale = (2.2, 4.5, 2.0)

# Parked SUV
bpy.ops.mesh.primitive_cube_add(size=1, location=(-5, -4.2, 0.4))
suv = bpy.context.view_layer.objects.active
suv.name = "ParkedSUV"
suv.scale = (2.0, 4.2, 1.8)

__result__ = 'vehicles_placed'
"""
    return run_python(code)

def place_pedestrian():
    """Place pedestrian figure."""
    print("[*] Placing pedestrian...")
    code = """
import bpy
# Pedestrian (simple capsule approximation)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(1.5, -1.0, 0.9))
ped_head = bpy.context.view_layer.objects.active
ped_head.name = "Pedestrian_Head"
ped_head.scale = (0.35, 0.35, 0.4)

# Body
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(1.5, -1.0, 0.2))
ped_body = bpy.context.view_layer.objects.active
ped_body.name = "Pedestrian_Body"
ped_body.scale = (0.4, 0.35, 0.55)

# Parent to a root
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(1.5, -1.0, 0))
ped_root = bpy.context.view_layer.objects.active
ped_root.name = "Pedestrian"

ped_head.parent = ped_root
ped_body.parent = ped_root

__result__ = 'pedestrian_placed'
"""
    return run_python(code)

def apply_v8_asphalt():
    """Apply v8 pro_asphalt_material to road."""
    print("[*] Applying v8 asphalt material...")
    # Get the material creation code
    asphalt_code = pro_asphalt_material()
    result = run_python(asphalt_code)
    if result:
        print(f"  {result}")
    
    # Apply to road objects
    code = """
import bpy
mat = bpy.data.materials.get('Pro_Asphalt_v8')
if mat:
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            nm = obj.name.lower()
            if 'road' in nm and 'crosswalk' not in nm and 'curb' not in nm and 'sidewalk' not in nm:
                obj.data.materials.clear()
                obj.data.materials.append(mat)
__result__ = 'asphalt_applied'
"""
    return run_python(code)

def apply_v8_vehicle_materials():
    """Apply v8 vehicle paint and glass materials."""
    print("[*] Applying v8 vehicle materials...")
    
    # Create vehicle paints
    print("  Creating vehicle paints...")
    
    # Silver for van
    paint_code_silver = pro_vehicle_paint('silver', (0.85, 0.85, 0.83, 1.0))
    run_python(paint_code_silver)
    
    # Dark gray for SUV
    paint_code_gray = pro_vehicle_paint('dark_gray', (0.28, 0.28, 0.30, 1.0))
    run_python(paint_code_gray)
    
    # Create glass
    print("  Creating glass material...")
    glass_code = pro_glass_material()
    run_python(glass_code)
    
    # Apply to vehicles
    code = """
import bpy
van_paint = bpy.data.materials.get('VehiclePaint_v8_silver')
suv_paint = bpy.data.materials.get('VehiclePaint_v8_dark_gray')
glass = bpy.data.materials.get('Pro_Glass_v8')

for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    nm = obj.name.lower()
    if 'van' in nm or 'delivery' in nm:
        if van_paint:
            obj.data.materials.clear()
            obj.data.materials.append(van_paint)
    elif 'suv' in nm or 'parked' in nm:
        if suv_paint:
            obj.data.materials.clear()
            obj.data.materials.append(suv_paint)

# Add glass windows (simple planes on vehicles)
if glass:
    for x in [5.2, 6.8]:
        bpy.ops.mesh.primitive_plane_add(size=0.8, location=(x, -0.5, 1.2))
        window = bpy.context.view_layer.objects.active
        window.name = f"VanWindow_{x}"
        window.rotation_euler = (0, 0, 0)
        window.data.materials.clear()
        window.data.materials.append(glass)

__result__ = 'vehicle_materials_applied'
"""
    return run_python(code)

def apply_v8_pedestrian_materials():
    """Apply materials to pedestrian figure."""
    print("[*] Dressing pedestrian with v8 materials...")
    code = """
import bpy
# Create pedestrian clothing material (gray)
ped_mat = bpy.data.materials.new("Figure_Gray")
ped_mat.use_nodes = True
ped_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.45, 0.45, 0.48, 1)
ped_mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.65

for obj in bpy.data.objects:
    if obj.type == 'MESH' and ('pedestrian' in obj.name.lower() or 'figure' in obj.name.lower()):
        obj.data.materials.clear()
        obj.data.materials.append(ped_mat)

__result__ = 'pedestrian_dressed'
"""
    return run_python(code)

def setup_forensic_lighting():
    """Setup forensic lighting (day rig with sun)."""
    print("[*] Setting up forensic lighting...")
    code = """
import bpy, math

# Setup world with sky
world = bpy.data.worlds.get("World")
if not world:
    world = bpy.data.worlds.new("World")

world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links

# Clear existing
for n in list(wn):
    wn.remove(n)

# Create sky
sky = wn.new('ShaderNodeTexSky')
try:
    sky.sky_type = 'HOSEK_WILKIE'
except:
    pass
sky.sun_elevation = math.radians(45)
sky.sun_rotation = math.radians(160)
sky.turbidity = 2.5

bg = wn.new('ShaderNodeBackground')
bg.inputs['Strength'].default_value = 1.2

wo = wn.new('ShaderNodeOutputWorld')

wl.new(sky.outputs['Color'], bg.inputs['Color'])
wl.new(bg.outputs['Background'], wo.inputs['Surface'])

# Sun light
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20))
sun = bpy.context.view_layer.objects.active
sun.name = "ForensicSun"
sun.data.energy = 3.0
sun.data.angle = math.radians(0.5)
sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(160))

__result__ = 'lighting_setup'
"""
    return run_python(code)

def add_forensic_evidence_markers():
    """Add proper numbered forensic evidence markers (tents, not cartoonish)."""
    print("[*] Adding forensic evidence markers...")
    code = """
import bpy, math

# Evidence marker material (white with number)
marker_mat = bpy.data.materials.new("EvidenceMarker")
marker_mat.use_nodes = True
bs = marker_mat.node_tree.nodes["Principled BSDF"]
bs.inputs["Base Color"].default_value = (0.95, 0.95, 0.92, 1)
bs.inputs["Roughness"].default_value = 0.7

# POI marker 1 (impact point) - white tent pole base
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.8, location=(1.5, -1.0, 0))
marker1 = bpy.context.view_layer.objects.active
marker1.name = "EvidenceMarker_1"
marker1.data.materials.clear()
marker1.data.materials.append(marker_mat)

# Marker pole
bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=1.2, location=(1.5, -1.0, 0.6))
pole1 = bpy.context.view_layer.objects.active
pole1.name = "MarkerPole_1"
pole1.data.materials.clear()
pole1.data.materials.append(marker_mat)

# Add number label
bpy.ops.object.text_add(location=(1.5, -1.0, 1.3))
label1 = bpy.context.view_layer.objects.active
label1.data.body = "1"
label1.data.size = 0.3
label1.name = "MarkerLabel_1"
label_mat = bpy.data.materials.new("MarkerLabel")
label_mat.use_nodes = True
label_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1)
label1.data.materials.append(label_mat)

# POI marker 2 (van front impact) - similar setup
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.8, location=(6, -0.5, 0))
marker2 = bpy.context.view_layer.objects.active
marker2.name = "EvidenceMarker_2"
marker2.data.materials.clear()
marker2.data.materials.append(marker_mat)

bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=1.2, location=(6, -0.5, 0.6))
pole2 = bpy.context.view_layer.objects.active
pole2.name = "MarkerPole_2"
pole2.data.materials.clear()
pole2.data.materials.append(marker_mat)

bpy.ops.object.text_add(location=(6, -0.5, 1.3))
label2 = bpy.context.view_layer.objects.active
label2.data.body = "2"
label2.data.size = 0.3
label2.name = "MarkerLabel_2"
label2.data.materials.append(label_mat)

__result__ = 'evidence_markers_added'
"""
    return run_python(code)

def setup_cameras():
    """Setup forensic cameras for Scene 2."""
    print("[*] Setting up cameras...")
    code = """
import bpy, math

# Target point
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(1.5, -1.0, 0.5))
tgt = bpy.context.view_layer.objects.active
tgt.name = "S2_Target"
tgt.hide_viewport = True
tgt.hide_render = True

# Bird's Eye camera
bpy.ops.object.camera_add(location=(0, 0, 38))
cam_bird = bpy.context.view_layer.objects.active
cam_bird.name = "Cam_BirdEye"
cam_bird.data.lens = 38
cam_bird.rotation_euler = (0, 0, 0)

# Driver POV camera
bpy.ops.object.camera_add(location=(-18, -0.5, 1.4))
cam_driver = bpy.context.view_layer.objects.active
cam_driver.name = "Cam_DriverPOV"
cam_driver.data.lens = 35
cam_driver.data.dof.use_dof = True
cam_driver.data.dof.focus_distance = 16
cam_driver.data.dof.aperture_fstop = 5.6
t = cam_driver.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

# Sight line camera
bpy.ops.object.camera_add(location=(-6, 10, 4.5))
cam_sight = bpy.context.view_layer.objects.active
cam_sight.name = "Cam_SightLine"
cam_sight.data.lens = 40
cam_sight.data.dof.use_dof = True
cam_sight.data.dof.focus_distance = 12
cam_sight.data.dof.aperture_fstop = 4.0
t = cam_sight.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

# Wide camera
bpy.ops.object.camera_add(location=(18, -16, 12))
cam_wide = bpy.context.view_layer.objects.active
cam_wide.name = "Cam_Wide"
cam_wide.data.lens = 30
t = cam_wide.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

__result__ = 'cameras_setup'
"""
    return run_python(code)

def save_scene():
    """Save the scene."""
    print("[*] Saving scene...")
    code = """
import bpy, os
blend_path = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v8_scene2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
__result__ = f'saved to {blend_path}'
"""
    return run_python(code)

def main():
    """Main orchestration."""
    print("="*60)
    print("Scene 2 v8 Material Pipeline")
    print("="*60)
    
    try:
        # Verify Blender is running
        print("[*] Connecting to Blender on port 9876...")
        result = send_to_blender('execute_python', {'code': '__result__ = "pong"'})
        if 'error' in result:
            print(f"[!] Cannot reach Blender: {result['error']}")
            return False
        print("[+] Connected to Blender")
        
        # Execute pipeline
        clean_scene()
        build_scene_2_geometry()
        place_vehicles()
        place_pedestrian()
        
        apply_v8_asphalt()
        apply_v8_vehicle_materials()
        apply_v8_pedestrian_materials()
        
        setup_forensic_lighting()
        add_forensic_evidence_markers()
        setup_cameras()
        setup_render_settings()
        
        save_scene()
        
        print("\n" + "="*60)
        print("[+] SCENE 2 v8 MATERIALS PIPELINE COMPLETE")
        print("="*60)
        print("Scene saved: ~/claw-architect/openclaw-blender-mcp/renders/v8_scene2.blend")
        return True
        
    except Exception as e:
        print(f"[!] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
