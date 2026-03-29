#!/usr/bin/env python3
"""
Fix the two plateau cameras with render-level changes:

scene1_BirdEye (84): Noise score = 0/15. All other metrics perfect.
  Fix: Clamping indirect light to 10, denoiser with Albedo+Normal passes,
       512 samples, adaptive sampling with low noise threshold.

scene4_DriverPOV (84): Exposure score = 21/100. Brightness 0.1334 (target 0.45).
  Fix: Boost exposure in Filmic color management (+1.5 EV), increase all lights 3x,
       add large area fill lights, raise HDRI strength to 0.5.

Run via: blender --background --python fix-plateau-cameras.py -- --target <scene1_BirdEye|scene4_DriverPOV>
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
args = parser.parse_args(argv)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RENDERS_DIR = os.path.join(BASE_DIR, "renders", "hyperrealistic")

# ─── Load Scene ───────────────────────────────────────────────────────────────
if args.target == "scene1_BirdEye":
    blend_path = os.path.join(RENDERS_DIR, "hyperrealistic_scene1.blend")
    cam_keyword = "birdeye"
    scene_num = 1
elif args.target == "scene4_DriverPOV":
    blend_path = os.path.join(RENDERS_DIR, "hyperrealistic_scene4.blend")
    cam_keyword = "driverpov"
    scene_num = 4

print(f"\n{'='*60}")
print(f"  FIXING PLATEAU: {args.target}")
print(f"{'='*60}")
print(f"Loading {blend_path}...")
bpy.ops.wm.open_mainfile(filepath=blend_path)
scene = bpy.context.scene

# ─── Scene 1 BirdEye: NOISE FIX ──────────────────────────────────────────────
if scene_num == 1:
    print("\n[NOISE FIX] Applying anti-noise measures...")

    # 1. Higher samples with adaptive sampling
    scene.cycles.samples = 512
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.005  # Very low noise threshold
    scene.cycles.adaptive_min_samples = 64
    print(f"  Samples: 512 (adaptive, threshold 0.005)")

    # 2. Clamp indirect light to reduce fireflies
    scene.cycles.sample_clamp_indirect = 10.0
    scene.cycles.sample_clamp_direct = 0.0  # Don't clamp direct
    print(f"  Indirect clamp: 10.0")

    # 3. Reduce light bounces (less bounces = less noise)
    scene.cycles.max_bounces = 8  # Down from default 12
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    print(f"  Light bounces: max=8, diffuse=4, glossy=4")

    # 4. Denoiser with Albedo + Normal passes for better quality
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    # Enable denoising data passes
    view_layer = bpy.context.view_layer
    view_layer.cycles.denoising_store_passes = True
    print(f"  Denoiser: OpenImageDenoise with data passes")

    # 5. Slight exposure boost to keep brightness optimal
    scene.view_settings.exposure = 0.0  # Keep neutral

    # 6. Use caustics filter to reduce noise from glass/glossy
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    print(f"  Caustics: disabled (noise reduction)")

# ─── Scene 4 DriverPOV: DARKNESS FIX ─────────────────────────────────────────
elif scene_num == 4:
    print("\n[DARKNESS FIX] Boosting scene brightness...")

    # Current brightness: 0.1334, target: 0.45
    # Need roughly 3.4x brightness boost

    # 1. Boost Filmic exposure (+1.7 EV ≈ 3.2x brightness)
    scene.view_settings.exposure = 1.7
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'  # Slightly more contrast for night
    print(f"  Exposure: +1.7 EV (Filmic)")

    # 2. Boost all existing lights by 3x
    light_count = 0
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            old_energy = obj.data.energy
            obj.data.energy = old_energy * 3.0
            light_count += 1
            print(f"  Boosted {obj.name}: {old_energy:.0f}W → {obj.data.energy:.0f}W")
    print(f"  Boosted {light_count} lights by 3x")

    # 3. Add two large area lights as scene fill
    # Front fill light (from slightly above, large soft light)
    fill1_data = bpy.data.lights.new("FrontFill", "AREA")
    fill1_data.energy = 800
    fill1_data.color = (0.95, 0.92, 0.85)  # Warm white
    fill1_data.size = 15  # Large = soft shadows
    fill1_obj = bpy.data.objects.new("FrontFill", fill1_data)
    scene.collection.objects.link(fill1_obj)
    fill1_obj.location = (0, -12, 8)
    fill1_obj.rotation_euler = (math.radians(50), 0, 0)
    print(f"  Added FrontFill: 800W area light (15m, warm)")

    # Overhead ambient fill
    fill2_data = bpy.data.lights.new("OverheadFill", "AREA")
    fill2_data.energy = 400
    fill2_data.color = (0.8, 0.85, 1.0)  # Cool moonlight
    fill2_data.size = 20  # Very large = ambient
    fill2_obj = bpy.data.objects.new("OverheadFill", fill2_data)
    scene.collection.objects.link(fill2_obj)
    fill2_obj.location = (0, 0, 15)
    fill2_obj.rotation_euler = (0, 0, 0)  # Pointing straight down
    print(f"  Added OverheadFill: 400W area light (20m, cool)")

    # 4. Boost HDRI environment strength
    if scene.world and scene.world.node_tree:
        for node in scene.world.node_tree.nodes:
            if node.type == 'BACKGROUND':
                old_str = node.inputs["Strength"].default_value
                node.inputs["Strength"].default_value = 0.5
                print(f"  HDRI strength: {old_str:.2f} → 0.50")

    # 5. Good denoiser settings (night scenes are noisier)
    scene.cycles.samples = 256
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.sample_clamp_indirect = 10.0
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    print(f"  Samples: 256, denoiser: OIDN, clamp: 10")

# ─── Find and Render Target Camera ───────────────────────────────────────────
print(f"\nSearching for camera matching '{cam_keyword}'...")
target_cam = None
for obj in bpy.data.objects:
    if obj.type == 'CAMERA':
        print(f"  Found camera: {obj.name}")
        if cam_keyword in obj.name.lower().replace("_", "").replace(" ", ""):
            target_cam = obj

if not target_cam:
    # Fallback: try partial match
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA' and "bird" in obj.name.lower():
            target_cam = obj
        if obj.type == 'CAMERA' and "driver" in obj.name.lower():
            target_cam = obj

if not target_cam:
    print("ERROR: No matching camera found!")
    sys.exit(1)

print(f"  Selected: {target_cam.name}")
scene.camera = target_cam

# ─── Render ───────────────────────────────────────────────────────────────────
output_path = os.path.join(RENDERS_DIR, f"hyper_{args.target}_v3.png")
scene.render.filepath = output_path
print(f"\nRendering to: {output_path}")
print(f"  Engine: {scene.render.engine}")
print(f"  Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")

bpy.ops.render.render(write_still=True)
print(f"\nSaved: {output_path}")
print("DONE")
