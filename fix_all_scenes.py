#!/usr/bin/env python3
"""
Fix lighting and camera issues for v11 day scenes (1-3).
Issues: Models not visible, low contrast, cameras not aimed.
"""
import bpy
import mathutils
import os

def fix_scene(scene_num, scene_name):
    """Fix a single scene"""
    print(f"\n{'='*60}")
    print(f"FIXING SCENE {scene_num}")
    print(f"{'='*60}")
    
    # Open scene file
    filepath = f'/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_scene{scene_num}.blend'
    print(f"Opening {filepath}...")
    bpy.ops.wm.open_mainfile(filepath=filepath)
    
    # Set render engine to EEVEE
    bpy.context.scene.render.engine = 'BLENDER_EEVEE'
    bpy.context.scene.render.resolution_x = 1920
    bpy.context.scene.render.resolution_y = 1080
    bpy.context.scene.render.image_settings.color_depth = '8'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    
    # Fix world background - set to medium gray for better lighting
    world = bpy.data.worlds['World']
    world.use_nodes = True
    bg_node = world.node_tree.nodes['Background']
    bg_node.inputs[0].default_value = (0.3, 0.35, 0.4, 1.0)  # Medium gray
    bg_node.inputs[1].default_value = 1.5  # Boost brightness
    
    # Get all mesh objects to find bounding box center
    meshes = [o for o in bpy.data.objects if o.type == 'MESH']
    cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
    lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
    
    print(f"Found {len(meshes)} meshes, {len(cameras)} cameras, {len(lights)} lights")
    
    if not meshes:
        print("WARNING: No mesh objects found!")
        return
    
    # Calculate bounding box center of all meshes
    min_pos = [float('inf')] * 3
    max_pos = [float('-inf')] * 3
    
    for mesh in meshes:
        for vertex in mesh.data.vertices:
            world_pos = mesh.matrix_world @ vertex.co
            for i in range(3):
                min_pos[i] = min(min_pos[i], world_pos[i])
                max_pos[i] = max(max_pos[i], world_pos[i])
    
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
    
    print(f"Bounding box center: {bbox_center}")
    print(f"Bounding box size: {bbox_size}")
    
    # Boost existing lights or create new ones
    if lights:
        for light in lights:
            if light.data.type == 'SUN':
                light.data.energy = 5.0
                print(f"Set {light.name} energy to 5.0")
            elif light.data.type == 'AREA':
                light.data.energy = 500.0
                print(f"Set {light.name} energy to 500.0")
    else:
        # Create sun light if none exists
        sun_data = bpy.data.lights.new(name="Sun", type='SUN')
        sun_data.energy = 5.0
        sun_obj = bpy.data.objects.new(name="Sun", object_data=sun_data)
        bpy.context.collection.objects.link(sun_obj)
        sun_obj.location = bbox_center + mathutils.Vector([0, 0, 10])
        sun_obj.rotation_euler = (0.5, 0.5, 0)
        print("Created new Sun light")
    
    # Fix camera positioning - aim each camera at bbox center
    if cameras:
        for cam in cameras:
            print(f"\nFixing camera {cam.name}...")
            
            # Calculate distance based on scene size
            max_dim = max(bbox_size.x, bbox_size.y, bbox_size.z)
            distance = max(10, max_dim * 1.5)
            
            # Position camera based on name/type
            cam_name_lower = cam.name.lower()
            
            if 'bird' in cam_name_lower or 'overhead' in cam_name_lower:
                # Bird's eye view - overhead
                cam.location = bbox_center + mathutils.Vector([0, 0, distance])
                cam.rotation_euler = (0, 0, 0)
            elif 'pov' in cam_name_lower or 'driver' in cam_name_lower:
                # Driver's perspective - slightly elevated, off to side
                cam.location = bbox_center + mathutils.Vector([distance*0.7, -distance*0.5, distance*0.3])
                cam.rotation_euler = (0.3, 0, 0.4)
            elif 'sight' in cam_name_lower or 'witness' in cam_name_lower:
                # Witness/sight line - elevated side angle
                cam.location = bbox_center + mathutils.Vector([-distance*0.6, distance*0.8, distance*0.4])
                cam.rotation_euler = (0.2, 0, -0.6)
            elif 'security' in cam_name_lower:
                # Security camera - elevated corner
                cam.location = bbox_center + mathutils.Vector([distance*0.5, distance*0.5, distance*0.3])
                cam.rotation_euler = (0.4, 0, 0.3)
            else:
                # Wide/default - elevated distance
                cam.location = bbox_center + mathutils.Vector([distance*0.5, distance*0.5, distance*0.4])
                cam.rotation_euler = (0.3, 0, 0.2)
            
            # Point camera at bbox center
            direction = bbox_center - cam.location
            rot_quat = direction.to_track_quat('-Z', 'Y')
            cam.rotation_euler = rot_quat.to_euler()
            
            print(f"  Position: {cam.location}")
            print(f"  Rotation: {cam.rotation_euler}")
    else:
        print("WARNING: No cameras found!")
    
    # Make sure all mesh materials are visible (not transparent/hidden)
    for mesh in meshes:
        mesh.hide_set(False)
        mesh.hide_render = False
        mesh.data.use_auto_smooth = True
        
        # Check materials
        if mesh.data.materials:
            for mat in mesh.data.materials:
                if mat.use_nodes:
                    mat.shadow_method = 'HASHED'
                    print(f"  Enabled material on {mesh.name}")
    
    # Save the fixed scene
    bpy.ops.wm.save_mainfile()
    print(f"Saved fixed scene to {filepath}")

# Main execution
if __name__ == '__main__':
    print("Starting scene fixes...")
    
    for scene_num in [1, 2, 3]:
        try:
            fix_scene(scene_num, f"Scene {scene_num}")
        except Exception as e:
            print(f"ERROR in scene {scene_num}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("ALL SCENES FIXED")
    print("="*60)
