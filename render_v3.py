#!/usr/bin/env python3
"""
Render all v11 scenes with v3 suffix after lighting fixes.
"""
import bpy
import os

def get_camera_angle_name(cam_name):
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
        return cam_name

def render_scene(scene_num):
    """Render all camera angles for a scene"""
    print(f"\n{'='*60}")
    print(f"RENDERING SCENE {scene_num}")
    print(f"{'='*60}")
    
    filepath = f'/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_scene{scene_num}.blend'
    print(f"Opening {filepath}...")
    bpy.ops.wm.open_mainfile(filepath=filepath)
    
    # Render directory
    render_dir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v11_renders'
    os.makedirs(render_dir, exist_ok=True)
    
    # Get all cameras
    cameras = [o for o in bpy.data.objects if o.type == 'CAMERA']
    print(f"Found {len(cameras)} cameras to render")
    
    if not cameras:
        print(f"WARNING: No cameras in scene {scene_num}")
        return
    
    # Render each camera
    for cam in cameras:
        angle_name = get_camera_angle_name(cam.name)
        output_name = f'v11_scene{scene_num}_{angle_name}_v3.png'
        output_path = os.path.join(render_dir, output_name)
        
        print(f"\nRendering {angle_name}...")
        print(f"  Camera: {cam.name}")
        print(f"  Output: {output_path}")
        
        # Set as active camera
        bpy.context.scene.camera = cam
        
        # Configure render
        bpy.context.scene.render.engine = 'BLENDER_EEVEE'
        bpy.context.scene.render.resolution_x = 1920
        bpy.context.scene.render.resolution_y = 1080
        bpy.context.scene.render.image_settings.color_depth = '8'
        bpy.context.scene.render.image_settings.file_format = 'PNG'
        bpy.context.scene.render.filepath = output_path
        
        # Render
        bpy.ops.render.render(write_still=True)
        
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024*1024)
            print(f"  SUCCESS: {output_path} ({size_mb:.2f} MB)")
        else:
            print(f"  FAILED: Output file not found")

# Main
if __name__ == '__main__':
    print("Starting render of v11 day scenes (v3)...")
    
    for scene_num in [1, 2, 3]:
        try:
            render_scene(scene_num)
        except Exception as e:
            print(f"ERROR in scene {scene_num}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("RENDERING COMPLETE")
    print("="*60)
