#!/usr/bin/env python3
"""
Re-render specific problem cameras with higher quality settings.
Scene1 BirdEye: noise issue → 256 samples
Scene4 DriverPOV: too dark → boost street lights + add fill light + 256 samples
"""
import bpy
import os
import sys
import math

argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--target", required=True, choices=["scene1_BirdEye", "scene4_DriverPOV"])
parser.add_argument("--samples", type=int, default=256)
args = parser.parse_args(argv)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RENDERS_DIR = os.path.join(BASE_DIR, "renders", "hyperrealistic")

if args.target == "scene1_BirdEye":
    blend_path = os.path.join(RENDERS_DIR, "hyperrealistic_scene1.blend")
    cam_name = "BirdEye"
    scene_num = 1
elif args.target == "scene4_DriverPOV":
    blend_path = os.path.join(RENDERS_DIR, "hyperrealistic_scene4.blend")
    cam_name = "DriverPOV"
    scene_num = 4

print(f"Loading {blend_path}...")
bpy.ops.wm.open_mainfile(filepath=blend_path)
scene = bpy.context.scene

# Higher samples + denoising
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'

# For scene4 night: boost lighting significantly
if scene_num == 4:
    print("Boosting night scene lighting...")
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            if 'StreetLight' in obj.name:
                obj.data.energy = 2000  # 4x boost from 500
                print(f"  Boosted {obj.name} to 2000W")

    # Add fill light from camera angle
    fill_data = bpy.data.lights.new("FillLight", "AREA")
    fill_data.energy = 300
    fill_data.color = (0.9, 0.9, 1.0)  # Slightly cool
    fill_data.size = 10
    fill_obj = bpy.data.objects.new("FillLight", fill_data)
    scene.collection.objects.link(fill_obj)
    fill_obj.location = (-5, -8, 6)
    fill_obj.rotation_euler = (math.radians(60), 0, math.radians(-30))
    print("  Added area fill light")

    # Increase HDRI strength slightly
    if scene.world and scene.world.node_tree:
        for node in scene.world.node_tree.nodes:
            if node.type == 'BACKGROUND':
                node.inputs["Strength"].default_value = 0.3  # Up from 0.15
                print(f"  HDRI strength → 0.3")

# For scene1: also bump exposure slightly
if scene_num == 1:
    scene.view_settings.exposure = 0.3  # Slight boost
    print(f"  Exposure boost → 0.3")

# Find matching camera
target_cam = None
for obj in bpy.data.objects:
    if obj.type == 'CAMERA' and cam_name.lower() in obj.name.lower():
        target_cam = obj
        break

if not target_cam:
    # Try partial match
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            print(f"  Available camera: {obj.name}")
    print(f"ERROR: Camera '{cam_name}' not found!")
    sys.exit(1)

print(f"Rendering camera: {target_cam.name} at {args.samples} samples...")
scene.camera = target_cam
output_path = os.path.join(RENDERS_DIR, f"hyper_{args.target}_v2.png")
scene.render.filepath = output_path
bpy.ops.render.render(write_still=True)
print(f"Saved: {output_path}")
print("DONE")
