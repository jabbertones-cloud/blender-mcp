#!/usr/bin/env python3
"""
v12_cameras.py - Optimized forensic animation camera setup
Fixes: positioning, focal length, clipping, and framing for all 4 scenes
Usage: blender --background scene.blend --python v12_cameras.py -- scene_num
"""

import bpy
import math
import sys
import mathutils

def get_scene_bounds():
    """Calculate bounding box of all mesh objects in scene."""
    bb_min = [float('inf')] * 3
    bb_max = [float('-inf')] * 3
    
    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            for vertex in [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]:
                for i in range(3):
                    bb_min[i] = min(bb_min[i], vertex[i])
                    bb_max[i] = max(bb_max[i], vertex[i])
    
    if bb_min[0] == float('inf'):
        return None, None
    
    center = [(bb_min[i] + bb_max[i]) / 2 for i in range(3)]
    size = [(bb_max[i] - bb_min[i]) / 2 for i in range(3)]
    return center, size

def create_camera(name, location, rotation_euler, focal_length=50, clip_start=0.1, clip_end=1000):
    """Create a new camera with specified parameters."""
    # Create camera data
    cam_data = bpy.data.cameras.new(name=name)
    cam_data.lens = focal_length
    cam_data.clip_start = clip_start
    cam_data.clip_end = clip_end
    cam_data.sensor_width = 36.0
    
    # Create camera object
    cam_obj = bpy.data.objects.new(name=name, object_data=cam_data)
    bpy.context.collection.objects.link(cam_obj)
    
    # Set position and rotation
    cam_obj.location = location
    cam_obj.rotation_euler = rotation_euler
    
    return cam_obj

def setup_scene_cameras(scene_num):
    """Setup optimized cameras for the specified scene."""
    
    # Remove all existing cameras
    for obj in list(bpy.data.objects):
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Get scene bounds to auto-frame
    center, size = get_scene_bounds()
    if center is None:
        print(f"ERROR: No mesh objects found in scene {scene_num}")
        return False
    
    print(f"\n{'='*60}")
    print(f"SETTING UP SCENE {scene_num} CAMERAS")
    print(f"{'='*60}")
    print(f"Scene bounds - Center: {[round(v, 1) for v in center]}, Size: {[round(v, 1) for v in size]}")
    
    # Scene-specific configurations
    if scene_num == 1:
        # Scene 1: Basic intersection
        scene_width = max(size[0], size[1]) * 2
        birdeye_height = min(30, scene_width * 0.5)
        
        cameras = [
            {
                "name": "Camera_BirdEye",
                "location": (center[0], center[1], center[2] + birdeye_height),
                "rotation": (-math.pi/2, 0, 0),  # -90° X
                "focal_length": 35,
                "description": "Overhead view of intersection"
            },
            {
                "name": "Camera_DriverPOV",
                "location": (center[0] + 5, center[1] - 3, center[2] + 1.2),
                "rotation": (math.radians(10), 0, 0),  # 10° downward
                "focal_length": 35,
                "description": "Inside vehicle dashboard view"
            },
            {
                "name": "Camera_Wide",
                "location": (center[0] + 25, center[1] + 15, center[2] + 5),
                "rotation": (math.radians(-35), 0, math.radians(45)),
                "focal_length": 28,
                "description": "Wide establishing shot"
            }
        ]
    
    elif scene_num == 2:
        # Scene 2: Pedestrian crossing
        scene_width = max(size[0], size[1]) * 2
        birdeye_height = min(25, scene_width * 0.4)
        
        cameras = [
            {
                "name": "Camera_BirdEye",
                "location": (center[0], center[1], center[2] + birdeye_height),
                "rotation": (-math.pi/2, 0, 0),
                "focal_length": 35,
                "description": "Overhead view of crossing"
            },
            {
                "name": "Camera_WitnessView",
                "location": (center[0] - 20, center[1] + 15, center[2] + 1.5),
                "rotation": (math.radians(-15), 0, math.radians(35)),
                "focal_length": 35,
                "description": "Witness perspective of event"
            },
            {
                "name": "Camera_Wide",
                "location": (center[0] + 22, center[1] - 18, center[2] + 4),
                "rotation": (math.radians(-32), 0, math.radians(-50)),
                "focal_length": 28,
                "description": "Wide establishing shot"
            }
        ]
    
    elif scene_num == 3:
        # Scene 3: Highway collision
        scene_width = max(size[0], size[1]) * 2
        birdeye_height = min(60, scene_width * 0.35)
        
        cameras = [
            {
                "name": "Camera_BirdEye",
                "location": (center[0], center[1], center[2] + birdeye_height),
                "rotation": (-math.pi/2, 0, 0),
                "focal_length": 35,
                "description": "Overhead view of highway collision"
            },
            {
                "name": "Camera_DriverPOV",
                "location": (center[0] - 8, center[1] + 2, center[2] + 1.2),
                "rotation": (math.radians(10), 0, 0),
                "focal_length": 35,
                "description": "Lead vehicle driver perspective"
            },
            {
                "name": "Camera_Wide",
                "location": (center[0] + 35, center[1] - 25, center[2] + 7),
                "rotation": (math.radians(-38), 0, math.radians(55)),
                "focal_length": 28,
                "description": "Wide establishing shot of highway"
            }
        ]
    
    elif scene_num == 4:
        # Scene 4: Parking lot (security camera scene)
        scene_width = max(size[0], size[1]) * 2
        birdeye_height = min(15, scene_width * 0.25)
        
        cameras = [
            {
                "name": "Camera_BirdEye",
                "location": (center[0], center[1], center[2] + birdeye_height),
                "rotation": (-math.pi/2, 0, 0),
                "focal_length": 35,
                "description": "Overhead view of parking lot"
            },
            {
                "name": "Camera_SecurityCam",
                "location": (center[0] - 12, center[1] - 10, center[2] + 4.5),
                "rotation": (math.radians(-40), 0, math.radians(45)),
                "focal_length": 5,  # Wide angle security lens
                "description": "Security camera dome view"
            },
            {
                "name": "Camera_Wide",
                "location": (center[0] + 18, center[1] + 12, center[2] + 5),
                "rotation": (math.radians(-30), 0, math.radians(-40)),
                "focal_length": 28,
                "description": "Wide establishing shot"
            }
        ]
    
    else:
        print(f"ERROR: Unknown scene number {scene_num}")
        return False
    
    # Create all cameras
    for cam_config in cameras:
        cam_obj = create_camera(
            name=cam_config["name"],
            location=cam_config["location"],
            rotation_euler=cam_config["rotation"],
            focal_length=cam_config["focal_length"],
            clip_start=0.1,
            clip_end=1000 if scene_num != 3 else 5000
        )
        
        print(f"\nCreated: {cam_config['name']}")
        print(f"  Location: {[round(v, 1) for v in cam_obj.location]}")
        print(f"  Rotation (deg): {[round(math.degrees(r), 1) for r in cam_obj.rotation_euler]}")
        print(f"  Focal length: {cam_config['focal_length']}mm")
        print(f"  Description: {cam_config['description']}")
    
    # Set the first camera as active
    if bpy.data.objects.get(cameras[0]["name"]):
        bpy.context.scene.camera = bpy.data.objects[cameras[0]["name"]]
        print(f"\nSet active camera: {cameras[0]['name']}")
    
    # Save the file
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
    print(f"\nSaved scene with new cameras")
    
    return True

if __name__ == "__main__":
    # Parse command line argument
    scene_num = None
    if len(sys.argv) > 1:
        try:
            # Last argument is scene number after -- separator
            scene_num = int(sys.argv[-1])
        except (ValueError, IndexError):
            scene_num = 1
    
    if scene_num is None:
        scene_num = 1
    
    print(f"\nStarting camera setup for scene {scene_num}...")
    success = setup_scene_cameras(scene_num)
    
    if success:
        print(f"\nCamera setup complete for scene {scene_num}!")
    else:
        print(f"\nFailed to setup cameras for scene {scene_num}")
