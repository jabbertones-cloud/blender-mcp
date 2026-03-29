#!/usr/bin/env python3
"""
Hyperrealistic Scene Upgrade — Blender Python Script
Run via: blender --background --python hyperrealistic-upgrade.py -- --scene <N> [--render]

Transforms forensic accident scenes from basic geometry to photorealistic quality:
1. Swaps placeholder vehicles with OpenX production models (.blend)
2. Applies real HDRI environment lighting (Polyhaven CC0)
3. Sets up PBR materials (asphalt, glass, metal) from texture maps
4. Configures Cycles renderer with denoising
5. Re-renders all camera angles at high quality

This is the geometry-level improvement that post-processing can never achieve.
"""

import bpy
import os
import sys
import math
import json
import time

# ─── Parse Arguments ──────────────────────────────────────────────────────────
# Blender passes everything after "--" to the script
argv = sys.argv
if "--" in argv:
    argv = argv[argv.index("--") + 1:]
else:
    argv = []

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--scene", type=int, required=True, help="Scene number (1-4)")
parser.add_argument("--render", action="store_true", help="Render after upgrade")
parser.add_argument("--engine", default="CYCLES", choices=["CYCLES", "BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"],
                    help="Render engine")
parser.add_argument("--samples", type=int, default=128, help="Cycles samples")
parser.add_argument("--resolution", type=int, default=1920, help="Render width")
parser.add_argument("--output-dir", default="", help="Output directory for renders")
parser.add_argument("--hdri", default="urban_street_01", help="HDRI to use")
parser.add_argument("--vehicle-1", default="m1_bmw_x1_2016", help="Vehicle 1 model")
parser.add_argument("--vehicle-2", default="m1_volvo_v60_polestar_2013", help="Vehicle 2 model")
args = parser.parse_args(argv)

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(BASE_DIR, "assets", "free_models")
OPENX_DIR = os.path.join(ASSETS_DIR, "openx-assets", "src", "vehicles", "main")
HDRI_DIR = os.path.join(BASE_DIR, "models", "hdri")
RENDERS_DIR = args.output_dir or os.path.join(BASE_DIR, "renders", "hyperrealistic")
SCENES_DIR = os.path.join(BASE_DIR, "renders")

os.makedirs(RENDERS_DIR, exist_ok=True)

# ─── Scene Configuration ─────────────────────────────────────────────────────
SCENE_CONFIG = {
    1: {
        "name": "T-Bone Collision",
        "base_file": "v9_scene1.blend",
        "hdri": "urban_street_01_2k.exr",
        "vehicles": [
            {"model": args.vehicle_1, "position": (0, 0, 0), "rotation": (0, 0, 0), "role": "striking"},
            {"model": args.vehicle_2, "position": (8, -3, 0), "rotation": (0, 0, math.radians(90)), "role": "struck"},
        ],
        "time_of_day": "day",
        "cameras": ["BirdEye", "DriverPOV", "WideAngle"],
    },
    2: {
        "name": "Pedestrian Crosswalk",
        "base_file": "v9_scene2.blend",
        "hdri": "crosswalk_2k.exr",  # Polyhaven crosswalk — perfect pedestrian scene match
        "vehicles": [
            {"model": "m1_hyundai_tucson_2015", "position": (0, 0, 0), "rotation": (0, 0, 0), "role": "approaching"},
        ],
        "time_of_day": "day",
        "cameras": ["BirdEye", "DriverPOV", "SightLine", "WideAngle"],
    },
    3: {
        "name": "Highway Rear-End",
        "base_file": "v9_scene3.blend",
        "hdri": "derelict_overpass_2k.exr",  # Polyhaven highway overpass — ideal rear-end scene
        "vehicles": [
            {"model": "m1_audi_q7_2015", "position": (0, 0, 0), "rotation": (0, 0, 0), "role": "rear_vehicle"},
            {"model": "m1_dacia_duster_2010", "position": (0, 12, 0), "rotation": (0, 0, 0), "role": "front_vehicle"},
        ],
        "time_of_day": "dusk",
        "cameras": ["BirdEye", "DriverPOV", "WideAngle"],
    },
    4: {
        "name": "Parking Lot Hit-and-Run",
        "base_file": "v9_scene4.blend",
        "hdri": "cobblestone_street_night_2k.exr",  # Polyhaven night street — dark urban scene
        "vehicles": [
            {"model": "n2_gmc_hummer_2021_pickup", "position": (0, 0, 0), "rotation": (0, 0, math.radians(15)), "role": "fleeing"},
            {"model": "m1_mini_countryman_2016", "position": (5, -2, 0), "rotation": (0, 0, math.radians(-10)), "role": "parked_victim"},
        ],
        "time_of_day": "night",
        "cameras": ["BirdEye", "DriverPOV", "SecurityCam", "WideAngle"],
    },
}

scene_cfg = SCENE_CONFIG[args.scene]
print(f"\n{'='*70}")
print(f"  HYPERREALISTIC UPGRADE — Scene {args.scene}: {scene_cfg['name']}")
print(f"{'='*70}\n")


# ─── Step 1: Load or Create Base Scene ────────────────────────────────────────
print("[1/6] Loading base scene...")

base_path = os.path.join(SCENES_DIR, scene_cfg["base_file"])
if os.path.exists(base_path):
    bpy.ops.wm.open_mainfile(filepath=base_path)
    print(f"  Loaded: {base_path}")
else:
    print(f"  Base file not found: {base_path}")
    print(f"  Creating fresh scene...")
    # Clear default scene
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.scene.new(type='NEW')

scene = bpy.context.scene
scene.name = f"Forensic_Scene_{args.scene}"


# ─── Step 2: Set Up HDRI Environment ─────────────────────────────────────────
print("[2/6] Setting up HDRI environment lighting...")

hdri_path = os.path.join(HDRI_DIR, scene_cfg["hdri"])
if os.path.exists(hdri_path):
    # Enable nodes for world
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear existing nodes
    nodes.clear()

    # Create Environment Texture → Background → Output
    env_tex = nodes.new("ShaderNodeTexEnvironment")
    env_tex.image = bpy.data.images.load(hdri_path)
    env_tex.location = (-400, 300)

    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 300)

    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 300)

    bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    bg.location = (-100, 300)

    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (200, 300)

    links.new(tex_coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], env_tex.inputs["Vector"])
    links.new(env_tex.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], output.inputs["Surface"])

    # Adjust strength — target 0.45 brightness in final render
    # Previous renders were 0.76 brightness with 1.2 strength
    # Scale down: 0.45/0.76 * 1.2 ≈ 0.71 for day scenes
    if scene_cfg["time_of_day"] == "night":
        bg.inputs["Strength"].default_value = 0.15
    elif scene_cfg["time_of_day"] == "dusk":
        bg.inputs["Strength"].default_value = 0.4
    else:
        bg.inputs["Strength"].default_value = 0.7

    print(f"  HDRI loaded: {scene_cfg['hdri']}")
    print(f"  Strength: {bg.inputs['Strength'].default_value}")
else:
    print(f"  WARNING: HDRI not found at {hdri_path}")
    print(f"  Using default sky instead")
    # Fallback: create a procedural sky
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type = 'NISHITA'
    sky.sun_elevation = math.radians(30)
    sky.location = (-300, 300)
    bg = nodes.new("ShaderNodeBackground")
    bg.location = (0, 300)
    output = nodes.new("ShaderNodeOutputWorld")
    output.location = (300, 300)
    links.new(sky.outputs["Color"], bg.inputs["Color"])
    links.new(bg.outputs["Background"], output.inputs["Surface"])


# ─── Step 3: Import OpenX Vehicle Models ──────────────────────────────────────
print("[3/6] Importing production vehicle models...")

def import_vehicle(model_name, position, rotation, role):
    """Import an OpenX vehicle .blend file and position it."""
    model_dir = os.path.join(OPENX_DIR, model_name)
    blend_file = os.path.join(model_dir, f"{model_name}.blend")

    if not os.path.exists(blend_file):
        print(f"  WARNING: Vehicle not found: {blend_file}")
        return None

    # Get objects before import
    before = set(bpy.data.objects.keys())

    # Append all objects from the vehicle .blend file
    with bpy.data.libraries.load(blend_file, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
        data_to.materials = data_from.materials
        if hasattr(data_from, 'collections'):
            data_to.collections = data_from.collections

    # Link imported objects to scene
    imported = []
    for obj in data_to.objects:
        if obj is not None:
            # Link to active collection
            if obj.name not in scene.collection.objects:
                scene.collection.objects.link(obj)
            imported.append(obj)

    if not imported:
        print(f"  WARNING: No objects imported from {blend_file}")
        return None

    # Create empty parent for positioning
    parent = bpy.data.objects.new(f"Vehicle_{role}_{model_name}", None)
    scene.collection.objects.link(parent)
    parent.location = position
    parent.rotation_euler = rotation

    # Parent all imported objects
    for obj in imported:
        obj.parent = parent

    print(f"  Imported: {model_name} ({len(imported)} objects) → {role}")
    print(f"    Position: {position}, Rotation: {[math.degrees(r) for r in rotation]}")
    return parent

# Remove existing placeholder vehicles (objects with "vehicle" or "car" in name)
placeholders_removed = 0
for obj in list(bpy.data.objects):
    name_lower = obj.name.lower()
    if any(kw in name_lower for kw in ["vehicle", "car", "truck", "suv", "sedan", "placeholder"]):
        bpy.data.objects.remove(obj, do_unlink=True)
        placeholders_removed += 1
if placeholders_removed:
    print(f"  Removed {placeholders_removed} placeholder vehicles")

# Import new vehicles
for v_cfg in scene_cfg["vehicles"]:
    import_vehicle(v_cfg["model"], v_cfg["position"], v_cfg["rotation"], v_cfg["role"])


# ─── Step 4: Apply PBR Road Materials ────────────────────────────────────────
print("[4/6] Applying PBR materials...")

def create_pbr_asphalt():
    """Create a physically-based asphalt material from texture maps."""
    mat = bpy.data.materials.new("PBR_Asphalt")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    # Principled BSDF
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (0, 0)
    bsdf.inputs["Metallic"].default_value = 0.0
    bsdf.inputs["Specular IOR Level"].default_value = 0.3

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    # Texture coordinate + mapping
    tex_coord = nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-800, 0)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.location = (-600, 0)
    mapping.inputs["Scale"].default_value = (4, 4, 4)  # Tile 4x
    links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    # Diffuse texture
    diff_path = os.path.join(HDRI_DIR, "asphalt_04_diff_1k.jpg")
    if os.path.exists(diff_path):
        diff_tex = nodes.new("ShaderNodeTexImage")
        diff_tex.image = bpy.data.images.load(diff_path)
        diff_tex.location = (-300, 200)
        links.new(mapping.outputs["Vector"], diff_tex.inputs["Vector"])
        links.new(diff_tex.outputs["Color"], bsdf.inputs["Base Color"])

    # Normal map
    nor_path = os.path.join(HDRI_DIR, "asphalt_04_nor_gl_1k.jpg")
    if os.path.exists(nor_path):
        nor_tex = nodes.new("ShaderNodeTexImage")
        nor_tex.image = bpy.data.images.load(nor_path)
        nor_tex.image.colorspace_settings.name = "Non-Color"
        nor_tex.location = (-300, -100)
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.inputs["Strength"].default_value = 1.0
        normal_map.location = (-100, -100)
        links.new(mapping.outputs["Vector"], nor_tex.inputs["Vector"])
        links.new(nor_tex.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])

    # Roughness map
    rough_path = os.path.join(HDRI_DIR, "asphalt_04_rough_1k.jpg")
    if os.path.exists(rough_path):
        rough_tex = nodes.new("ShaderNodeTexImage")
        rough_tex.image = bpy.data.images.load(rough_path)
        rough_tex.image.colorspace_settings.name = "Non-Color"
        rough_tex.location = (-300, -400)
        links.new(mapping.outputs["Vector"], rough_tex.inputs["Vector"])
        links.new(rough_tex.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.7

    return mat

# Apply asphalt to ground/road objects
asphalt_mat = create_pbr_asphalt()
applied_count = 0
for obj in bpy.data.objects:
    name_lower = obj.name.lower()
    if obj.type == 'MESH' and any(kw in name_lower for kw in ["road", "ground", "plane", "floor", "asphalt", "pavement"]):
        if obj.data.materials:
            obj.data.materials[0] = asphalt_mat
        else:
            obj.data.materials.append(asphalt_mat)
        applied_count += 1
        print(f"  Applied PBR asphalt to: {obj.name}")

if applied_count == 0:
    print(f"  No ground objects found to apply asphalt material")


# ─── Step 5: Configure Render Engine ─────────────────────────────────────────
print("[5/6] Configuring render engine...")

# Set render engine
try:
    scene.render.engine = args.engine
except:
    scene.render.engine = "CYCLES"

# Resolution
scene.render.resolution_x = args.resolution
scene.render.resolution_y = int(args.resolution * 9 / 16)  # 16:9
scene.render.resolution_percentage = 100

# Cycles settings
if scene.render.engine == "CYCLES":
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'

    # Try to use GPU
    prefs = bpy.context.preferences.addons.get('cycles')
    if prefs:
        try:
            prefs.preferences.compute_device_type = 'METAL'  # macOS
            bpy.context.preferences.addons['cycles'].preferences.get_devices()
            scene.cycles.device = 'GPU'
            print(f"  Using GPU (Metal) rendering")
        except:
            scene.cycles.device = 'CPU'
            print(f"  Using CPU rendering")

    # Film settings for realism
    scene.render.film_transparent = False
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium Contrast'
    scene.view_settings.exposure = 0.0

    # Denoising
    scene.cycles.use_denoising = True
    scene.cycles.preview_denoiser = 'AUTO'

elif "EEVEE" in scene.render.engine:
    # EEVEE settings for speed
    scene.eevee.taa_render_samples = 64
    scene.eevee.use_gtao = True  # Ambient occlusion
    scene.eevee.use_bloom = False
    scene.eevee.use_ssr = True  # Screen space reflections

# Color management for photorealism
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'Medium Contrast'

# Add supplementary lighting for night/dusk scenes
if scene_cfg["time_of_day"] == "night":
    # Add street lights
    for i, x in enumerate([-10, 0, 10]):
        light_data = bpy.data.lights.new(f"StreetLight_{i}", "POINT")
        light_data.energy = 500
        light_data.color = (1.0, 0.9, 0.7)  # Warm sodium vapor
        light_data.shadow_soft_size = 0.5
        light_obj = bpy.data.objects.new(f"StreetLight_{i}", light_data)
        scene.collection.objects.link(light_obj)
        light_obj.location = (x, 0, 8)
    print(f"  Added 3 street lights for night scene")

elif scene_cfg["time_of_day"] == "dusk":
    # Add sun light at low angle
    sun_data = bpy.data.lights.new("Sun_Dusk", "SUN")
    sun_data.energy = 3.0
    sun_data.color = (1.0, 0.8, 0.5)  # Warm dusk
    sun_obj = bpy.data.objects.new("Sun_Dusk", sun_data)
    scene.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(15), 0, math.radians(-30))
    print(f"  Added dusk sun light")

print(f"  Engine: {scene.render.engine}")
print(f"  Samples: {args.samples}")
print(f"  Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
print(f"  Color: Filmic + Medium Contrast")


# ─── Step 6: Save and Render ──────────────────────────────────────────────────
print("[6/6] Saving upgraded scene...")

# Save the upgraded .blend file
save_path = os.path.join(RENDERS_DIR, f"hyperrealistic_scene{args.scene}.blend")
bpy.ops.wm.save_as_mainfile(filepath=save_path)
print(f"  Saved: {save_path}")

if args.render:
    print(f"\n  Rendering all cameras...")

    # Find cameras in scene
    cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
    if not cameras:
        # Create default cameras if none exist
        print(f"  No cameras found — creating default set...")
        cam_configs = {
            "BirdEye": {"loc": (0, 0, 25), "rot": (0, 0, 0)},
            "DriverPOV": {"loc": (-5, -8, 1.5), "rot": (math.radians(80), 0, math.radians(-30))},
            "WideAngle": {"loc": (-15, -10, 5), "rot": (math.radians(70), 0, math.radians(-50))},
        }
        if args.scene == 2:
            cam_configs["SightLine"] = {"loc": (0, -15, 1.5), "rot": (math.radians(88), 0, 0)}
        if args.scene == 4:
            cam_configs["SecurityCam"] = {"loc": (15, 10, 6), "rot": (math.radians(60), 0, math.radians(120))}

        for cam_name, cfg in cam_configs.items():
            cam_data = bpy.data.cameras.new(f"Cam_{cam_name}")
            if cam_name == "WideAngle":
                cam_data.lens = 24  # Wide angle
            elif cam_name == "BirdEye":
                cam_data.lens = 35
                cam_data.type = 'ORTHO'
                cam_data.ortho_scale = 30
            else:
                cam_data.lens = 50  # Standard

            cam_obj = bpy.data.objects.new(f"Cam_{cam_name}", cam_data)
            scene.collection.objects.link(cam_obj)
            cam_obj.location = cfg["loc"]
            cam_obj.rotation_euler = cfg["rot"]
            cameras.append(cam_obj)

    # Render each camera
    for cam in cameras:
        cam_name = cam.name.replace("Cam_", "")
        scene.camera = cam
        output_path = os.path.join(RENDERS_DIR, f"hyper_scene{args.scene}_{cam_name}.png")
        scene.render.filepath = output_path
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.color_depth = '16'

        print(f"  Rendering: {cam_name} → {output_path}")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        elapsed = time.time() - t0
        print(f"    Done in {elapsed:.1f}s")

    print(f"\n  All renders complete → {RENDERS_DIR}")

# ─── Summary ──────────────────────────────────────────────────────────────────
summary = {
    "scene": args.scene,
    "name": scene_cfg["name"],
    "hdri": scene_cfg["hdri"],
    "vehicles": [v["model"] for v in scene_cfg["vehicles"]],
    "engine": scene.render.engine,
    "samples": args.samples,
    "resolution": f"{scene.render.resolution_x}x{scene.render.resolution_y}",
    "blend_file": save_path,
    "rendered": args.render,
    "time_of_day": scene_cfg["time_of_day"],
}

summary_path = os.path.join(RENDERS_DIR, f"upgrade_summary_scene{args.scene}.json")
with open(summary_path, "w") as f:
    json.dump(summary, f, indent=2)

print(f"\n{'='*70}")
print(f"  UPGRADE COMPLETE — Scene {args.scene}: {scene_cfg['name']}")
print(f"  HDRI: {scene_cfg['hdri']}")
print(f"  Vehicles: {', '.join(v['model'] for v in scene_cfg['vehicles'])}")
print(f"  Engine: {scene.render.engine} @ {args.samples} samples")
print(f"  Saved: {save_path}")
print(f"{'='*70}\n")
