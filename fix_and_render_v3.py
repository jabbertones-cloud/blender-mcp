#!/usr/bin/env python3
"""
Fix lighting and render all v11 day scenes (1-3) with v3 suffix.
Run via: blender -b v11_scene1.blend -P fix_and_render_v3.py
"""
import bpy
import mathutils
import os
import sys

def get_angle_name(cam_name):
    """Extract angle name from camera"""
    name_lower = cam_name.lower()
    if 'bird' in name_lower:
        return 'BirdEye'
    elif 'driver' in name_lower or 'pov' in name_lower:
        return 'DriverPOV'
    elif 'sight' in name_lower:
        return 'SightLine'
    elif 'witness' in name_lower:
        return 'Witness'
    elif 'security' in name_lower:
        return 'SecurityCam'
    elif 'wide' in name_lower:
        return 'Wide'
    else:
        return 'Other'

def fix_and_render_scene(scene_num):
    """Fix lighting and render a scene"""
    print(f"\n{'='*70}")
    print(f"PROCESSING SCENE {scene_num}")
    print(f"{'='*70}")
    
    filepath = f'/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_scene{scene_num}.blend'
    
    # Open scene
    print(f"Opening {filepath}...")
    try:
        bpy.ops.wm.open_mainfile(filepath=filepath)
    except Exception as e:
        print(f"ERROR opening file: {e}")
        return False
    
    # Configure render engine
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.image_settings.color_depth = '8'
    scene.render.image_settings.file_format = 'PNG'
    scene.view_settings.exposure = 0.5
    print("Set EEVEE engine, 1920x1080, PNG format")
    
    # Fix world background
    world = bpy.data.worlds.get('World')
    if world:
        world.use_nodes = True
        if world.node_tree:
            bg_node = world.node_tree.nodes.get('Background')
            if bg_node:
                bg_node.inputs[0].default_value = (0.4, 0.4, 0.45, 1.0)
                bg_node.inputs[1].default_value = 2.0
                print("World background: medium gray at 2.0 strength")
    
    # Get all objects
    meshes = [o for o in scene.objects if o.type == 'MESH']
    cameras = [o for o in scene.objects if o.type == 'CAMERA']
    lights = [o for o in scene.objects if o.type == 'LIGHT']
    
    print(f"Objects: {len(meshes)} meshes, {len(cameras)} cameras, {len(lights)} lights")
    
    if not meshes or not cameras:
        print("ERROR: Missing meshes or cameras")
        return False
    
    # Calculate bounding box
    min_pos = [float('inf')] * 3
    max_pos = [float('-inf')] * 3
    
    for mesh in meshes:
        if mesh.type == 'MESH' and mesh.data:
            for v in mesh.data.vertices:
                try:
                    wp = mesh.matrix_world @ v.co
                    for i in range(3):
                        min_pos[i] = min(min_pos[i], wp[i])
                        max_pos[i] = max(max_pos[i], wp[i])
                except:
                    pass
    
    bbox_center = mathutils.Vector([
        (min_pos[0] + max_pos[0]) / 2,
        (min_pos[1] + max_pos[1]) / 2,
        (min_pos[2] + max_pos[2]) / 2
    ])
    bbox_size = mathutils.Vector([
        max_pos[0] - min_pos[0],
        max_pos[1] - min_pos[1],
        max_pos[2] - min_pos[2]
    ])
    
    print(f"Bbox center: ({bbox_center.x:.2f}, {bbox_center.y:.2f}, {bbox_center.z:.2f})")
    print(f"Bbox size: ({bbox_size.x:.2f}, {bbox_size.y:.2f}, {bbox_size.z:.2f})")
    
    # Boost light energy
    sun_found = False
    for light in lights:
        if light.data.type == 'SUN':
            light.data.energy = 5.0
            sun_found = True
            print(f"  {light.name} (SUN): energy=5.0")
        elif light.data.type == 'AREA':
            light.data.energy = 500.0
            print(f"  {light.name} (AREA): energy=500.0")
        elif light.data.type == 'POINT':
            light.data.energy = 1000.0
            print(f"  {light.name} (POINT): energy=1000.0")
    
    if not sun_found:
        print("WARNING: No SUN light found - creating one")
        sun_data = bpy.data.lights.new(name="Sun_Added", type='SUN')
        sun_data.energy = 5.0
        sun_obj = bpy.data.objects.new(name="Sun_Added", object_data=sun_data)
        scene.collection.objects.link(sun_obj)
        sun_obj.location = bbox_center + mathutils.Vector([0, 0, 20])
        sun_obj.rotation_euler = (0.5, 0.5, 0)
    
    # Aim each camera at bbox center
    max_dim = max(bbox_size.x, bbox_size.y, bbox_size.z)
    distance = max(15, max_dim * 2.0)
    
    print(f"\nAiming {len(cameras)} cameras (distance={distance:.1f})...")
    
    for cam in cameras:
        angle_name = get_angle_name(cam.name)
        
        # Position based on camera type
        cam_name_lower = cam.name.lower()
        
        if 'bird' in cam_name_lower:
            # Overhead view
            cam.location = bbox_center + mathutils.Vector([0, 0, distance])
        elif 'driver' in cam_name_lower or 'pov' in cam_name_lower:
            # Driver's view - side angle
            cam.location = bbox_center + mathutils.Vector([distance*0.8, -distance*0.4, distance*0.35])
        elif 'sight' in cam_name_lower or 'witness' in cam_name_lower:
            # Witness view - elevated side
            cam.location = bbox_center + mathutils.Vector([-distance*0.6, distance*0.7, distance*0.4])
        elif 'security' in cam_name_lower:
            # Security camera - high corner
            cam.location = bbox_center + mathutils.Vector([distance*0.5, distance*0.5, distance*0.35])
        else:
            # Wide/default
            cam.location = bbox_center + mathutils.Vector([distance*0.6, distance*0.4, distance*0.35])
        
        # Point at bbox center
        direction = bbox_center - cam.location
        try:
            rot_quat = direction.to_track_quat('-Z', 'Y')
            cam.rotation_euler = rot_quat.to_euler()
        except:
            pass
        
        print(f"  {angle_name:15} at ({cam.location.x:7.1f}, {cam.location.y:7.1f}, {cam.location.z:7.1f})")
    
    # Unhide all meshes and ensure visibility
    for mesh in meshes:
        mesh.hide_set(False)
        mesh.hide_render = False
    
    # Save fixed scene
    print(f"\nSaving fixed scene...")
    bpy.ops.wm.save_mainfile()
    
    # Render each camera
    render_dir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_renders'
    os.makedirs(render_dir, exist_ok=True)
    
    print(f"\nRendering {len(cameras)} angles...")
    rendered_files = []
    
    for cam in cameras:
        angle_name = get_angle_name(cam.name)
        output_name = f'v11_scene{scene_num}_{angle_name}_v3.png'
        output_path = os.path.join(render_dir, output_name)
        
        print(f"\n  {angle_name}: {output_name}")
        
        # Set active camera
        scene.camera = cam
        
        # Set output path
        scene.render.filepath = output_path
        
        # Render
        try:
            bpy.ops.render.render(write_still=True)
            
            # Check if file was created
            if os.path.exists(output_path):
                size_mb = os.path.getsize(output_path) / (1024 * 1024)
                print(f"    SUCCESS: {size_mb:.2f} MB")
                rendered_files.append(output_path)
            else:
                print(f"    FAILED: File not created")
        except Exception as e:
            print(f"    ERROR: {e}")
    
    print(f"\nScene {scene_num} complete: {len(rendered_files)} files rendered")
    return True

# Main execution
if __name__ == '__main__':
    print("\n" + "="*70)
    print("V11 DAY SCENES FIX & RENDER (v3)")
    print("="*70)
    
    success_count = 0
    
    for scene_num in [1, 2, 3]:
        try:
            if fix_and_render_scene(scene_num):
                success_count += 1
        except Exception as e:
            print(f"\nEXCEPTION in scene {scene_num}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print(f"COMPLETE: {success_count}/3 scenes processed successfully")
    print(f"{'='*70}")
