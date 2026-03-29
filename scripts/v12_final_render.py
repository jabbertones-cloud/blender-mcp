#!/usr/bin/env python3
"""Quick v12 render script that properly names output files"""
import bpy
import sys

def main():
    scene_num = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    scene = bpy.context.scene
    
    # Set render settings
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    
    # Get cameras
    cameras = [obj.name for obj in bpy.data.objects if obj.type == 'CAMERA']
    print(f"Scene {scene_num}: Found cameras: {cameras}")
    
    output_dir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v12_renders'
    
    for cam_name in cameras:
        scene.camera = bpy.data.objects[cam_name]
        output_file = f'{output_dir}/v12_scene{scene_num}_{cam_name}.png'
        scene.render.filepath = output_file
        print(f"Rendering {cam_name} -> {output_file}")
        bpy.ops.render.render(write_still=True)
        print(f"  Done")

if __name__ == '__main__':
    main()
