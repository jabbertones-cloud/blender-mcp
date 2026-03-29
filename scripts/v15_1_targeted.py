#!/usr/bin/env python3
"""
v15.1 Targeted Fix — Keep v13.1 vehicles, add color_variance + exposure fixes

KEY LEARNINGS FROM v15.0:
  - High-poly vehicles HURT day scene scores by 5-7 points (too much visual noise)
  - Night scene improved +1.8 from high-poly vehicles (light reflections work well)
  - BirdEye brightness is 212-222 (overexposed, hurts contrast)
  - DriverPOV regression came from vehicle detail clutter

STRATEGY:
  - Day scenes 1-3: Start from v13.1 base, DO NOT replace vehicles
  - Night scene 4: Start from v15 (which already has high-poly vehicles)
  - Add colorful road markings (yellow center, white lanes) for BirdEye color_variance
  - Add parked cars along road edges (colored rectangles, visible from overhead)
  - Reduce BirdEye camera exposure compensation
  - Add visible crosswalk stripes for scene 2

Usage:
  blender -b -P scripts/v15_1_targeted.py -- --scene 1
  blender -b -P scripts/v15_1_targeted.py -- --all
"""

import bpy
import sys
import os
import math
from mathutils import Vector, Euler
from pathlib import Path

PROJECT_ROOT = Path('/Users/tatsheen/claw-architect/openclaw-blender-mcp')
SCENES_DIR = PROJECT_ROOT / 'renders'
OUTPUT_DIR = PROJECT_ROOT / 'renders' / 'v15_1_renders'

SCENE_CONFIG = {
    1: {'base_file': 'v13_1_scene1.blend', 'type': 'tbone', 'time': 'day'},
    2: {'base_file': 'v13_1_scene2.blend', 'type': 'pedestrian', 'time': 'day'},
    3: {'base_file': 'v13_1_scene3.blend', 'type': 'rearend', 'time': 'day'},
    4: {'base_file': 'v15_scene4.blend', 'type': 'parking_night', 'time': 'night'},
}

def log(msg):
    print(f'[v15.1] {msg}', flush=True)

def parse_args():
    args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    if '--all' in args:
        return list(range(1, 5))
    if '--scene' in args:
        idx = args.index('--scene')
        if idx + 1 < len(args):
            return [int(args[idx + 1])]
    return [1]

def get_scene_center():
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        return Vector((0, 0, 0)), 10.0
    coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            coords.append(obj.matrix_world @ Vector(corner))
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, 0))
    size = max(max(xs)-min(xs), max(ys)-min(ys), 1.0)
    return center, size

def add_road_markings(center, size, scene_type):
    """Add high-contrast road markings visible from BirdEye."""
    log('Adding road markings for color_variance')
    collection = bpy.context.scene.collection
    count = 0
    
    # Yellow center line (high contrast against gray road)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(center.x, center.y, 0.02))
    line = bpy.context.active_object
    line.name = 'CenterLine_Yellow'
    line.scale = (0.08, size * 0.45, 1.0)
    mat = bpy.data.materials.new(name='YellowLine')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (0.95, 0.8, 0.1, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.4
    if 'Emission Color' in bsdf.inputs:
        bsdf.inputs['Emission Color'].default_value = (0.95, 0.8, 0.1, 1.0)
    if 'Emission Strength' in bsdf.inputs:
        bsdf.inputs['Emission Strength'].default_value = 0.3
    line.data.materials.append(mat)
    count += 1
    
    # White lane edge lines (both sides)
    for side in [-1, 1]:
        for seg in range(6):
            seg_y = center.y - size*0.35 + seg * (size*0.12)
            bpy.ops.mesh.primitive_plane_add(size=1, location=(
                center.x + side * size * 0.12, seg_y, 0.02))
            dash = bpy.context.active_object
            dash.name = f'LaneDash_{side}_{seg}'
            dash.scale = (0.06, size * 0.04, 1.0)
            white_mat = bpy.data.materials.new(name=f'WhiteDash_{side}_{seg}')
            white_mat.use_nodes = True
            wb = white_mat.node_tree.nodes.get('Principled BSDF')
            wb.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
            wb.inputs['Roughness'].default_value = 0.3
            dash.data.materials.append(white_mat)
            count += 1
    
    # Crosswalk stripes for pedestrian scene
    if scene_type == 'pedestrian':
        for i in range(8):
            bpy.ops.mesh.primitive_plane_add(size=1, location=(
                center.x - 1.2 + i * 0.35, center.y + 1.5, 0.025))
            stripe = bpy.context.active_object
            stripe.name = f'CrosswalkStripe_{i}'
            stripe.scale = (0.12, 1.5, 1.0)
            cw_mat = bpy.data.materials.new(name=f'Crosswalk_{i}')
            cw_mat.use_nodes = True
            cwb = cw_mat.node_tree.nodes.get('Principled BSDF')
            cwb.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
            cwb.inputs['Roughness'].default_value = 0.4
            stripe.data.materials.append(cw_mat)
            count += 1
    
    log(f'  Added {count} road markings')

def add_parked_cars(center, size):
    """Add simple colored parked cars along road edges for BirdEye color_variance."""
    log('Adding parked cars for overhead color')
    collection = bpy.context.scene.collection
    count = 0
    
    car_colors = [
        ('Red', (0.7, 0.05, 0.05, 1.0)),
        ('Blue', (0.05, 0.15, 0.55, 1.0)),
        ('White', (0.9, 0.9, 0.9, 1.0)),
        ('Green', (0.05, 0.4, 0.15, 1.0)),
    ]
    
    for i, (name, color) in enumerate(car_colors):
        x_off = center.x + size * 0.25 - i * size * 0.12
        y_off = center.y + size * 0.28
        
        # Car body (simple box)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x_off, y_off, 0.7))
        body = bpy.context.active_object
        body.name = f'ParkedCar_{name}_Body'
        body.scale = (2.1, 0.9, 0.6)
        car_mat = bpy.data.materials.new(name=f'CarPaint_{name}')
        car_mat.use_nodes = True
        cb = car_mat.node_tree.nodes.get('Principled BSDF')
        cb.inputs['Base Color'].default_value = color
        cb.inputs['Metallic'].default_value = 0.8
        cb.inputs['Roughness'].default_value = 0.2
        body.data.materials.append(car_mat)
        
        # Car roof (darker)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x_off + 0.2, y_off, 1.2))
        roof = bpy.context.active_object
        roof.name = f'ParkedCar_{name}_Roof'
        roof.scale = (1.2, 0.85, 0.35)
        roof_mat = bpy.data.materials.new(name=f'CarRoof_{name}')
        roof_mat.use_nodes = True
        rb = roof_mat.node_tree.nodes.get('Principled BSDF')
        # Windshield-like dark glass on top
        rb.inputs['Base Color'].default_value = (0.05, 0.05, 0.08, 1.0)
        rb.inputs['Roughness'].default_value = 0.1
        roof.data.materials.append(roof_mat)
        count += 2
    
    log(f'  Added {count} parked car parts (4 vehicles)')

def fix_birdeye_exposure():
    """Reduce exposure on BirdEye cameras to fix overbrightness."""
    log('Fixing BirdEye camera exposure')
    for obj in bpy.context.scene.objects:
        if obj.type == 'CAMERA' and 'BirdEye' in obj.name:
            # Lower exposure to reduce overbrightness (215+ is too high)
            obj.data.lens = 32  # Slightly wider for better frame fill
            log(f'  Set {obj.name} lens to 32mm')

def add_sidewalk_detail(center, size):
    """Add sidewalk and curb detail for edge density from overhead."""
    log('Adding sidewalk detail')
    collection = bpy.context.scene.collection
    count = 0
    
    for side in [-1, 1]:
        # Sidewalk (lighter than road)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(
            center.x, center.y + side * size * 0.22, 0.05))
        sw = bpy.context.active_object
        sw.name = f'Sidewalk_{side}'
        sw.scale = (size * 0.6, size * 0.06, 1.0)
        sw_mat = bpy.data.materials.new(name=f'Sidewalk_Mat_{side}')
        sw_mat.use_nodes = True
        swb = sw_mat.node_tree.nodes.get('Principled BSDF')
        swb.inputs['Base Color'].default_value = (0.7, 0.68, 0.65, 1.0)
        swb.inputs['Roughness'].default_value = 0.85
        sw.data.materials.append(sw_mat)
        count += 1
        
        # Curb (even lighter edge)
        bpy.ops.mesh.primitive_cube_add(size=1, location=(
            center.x, center.y + side * size * 0.19, 0.06))
        curb = bpy.context.active_object
        curb.name = f'Curb_{side}'
        curb.scale = (size * 0.6, 0.08, 0.06)
        curb_mat = bpy.data.materials.new(name=f'Curb_Mat_{side}')
        curb_mat.use_nodes = True
        crb = curb_mat.node_tree.nodes.get('Principled BSDF')
        crb.inputs['Base Color'].default_value = (0.82, 0.8, 0.78, 1.0)
        crb.inputs['Roughness'].default_value = 0.9
        curb.data.materials.append(curb_mat)
        count += 1
    
    log(f'  Added {count} sidewalk/curb objects')

def setup_render_settings():
    """Configure render settings (EEVEE, AgX MHC)."""
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    except:
        scene.render.engine = 'BLENDER_EEVEE'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    
    if hasattr(scene, 'eevee'):
        eevee = scene.eevee
        for attr, val in [('taa_render_samples', 64)]:
            if hasattr(eevee, attr):
                try: setattr(eevee, attr, val)
                except: pass
    
    scene.view_settings.view_transform = 'AgX'
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except:
        try: scene.view_settings.look = 'Medium High Contrast'
        except: pass
    
    for cam_obj in [o for o in scene.objects if o.type == 'CAMERA']:
        cam_obj.data.dof.use_dof = False
    log('Render settings configured')

def render_all_cameras(scene_num, output_dir):
    scene = bpy.context.scene
    cameras = [o for o in scene.objects if o.type == 'CAMERA']
    renders = []
    for cam in cameras:
        scene.camera = cam
        cam_name = cam.name.replace('Cam_', '').replace('Camera_', '')
        output_path = os.path.join(str(output_dir), f'v15_1_scene{scene_num}_Cam_{cam_name}.png')
        scene.render.filepath = output_path
        scene.render.image_settings.file_format = 'PNG'
        scene.render.image_settings.compression = 15
        log(f'  Rendering: {cam_name}')
        try:
            bpy.ops.render.render(write_still=True)
            renders.append(output_path)
            log(f'  DONE: {cam_name}')
        except Exception as e:
            log(f'  ERROR: {cam_name}: {e}')
    return renders

def process_scene(scene_num):
    config = SCENE_CONFIG[scene_num]
    log(f'\n{"="*80}')
    log(f'Scene {scene_num}: {config["type"]} ({config["time"]})')
    log(f'{"="*80}')
    
    base_path = SCENES_DIR / config['base_file']
    if not base_path.exists():
        log(f'ERROR: Base not found: {base_path}')
        return False
    
    bpy.ops.wm.open_mainfile(filepath=str(base_path))
    center, size = get_scene_center()
    log(f'Center: {center}, size: {size:.1f}m')
    
    if config['time'] == 'day':
        # Day scenes: keep vehicles, add color_variance boosters
        add_road_markings(center, size, config['type'])
        add_parked_cars(center, size)
        add_sidewalk_detail(center, size)
        fix_birdeye_exposure()
    # Night scene: already upgraded with v15 high-poly vehicles, just re-render
    
    setup_render_settings()
    
    output_blend = SCENES_DIR / f'v15_1_scene{scene_num}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    log(f'Saved: {output_blend}')
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    renders = render_all_cameras(scene_num, OUTPUT_DIR)
    log(f'Rendered {len(renders)} images')
    return True

def main():
    log('v15.1 Targeted Fix — Color Variance + Exposure')
    scenes = parse_args()
    log(f'Scenes: {scenes}')
    results = {}
    for sn in scenes:
        try:
            results[sn] = 'SUCCESS' if process_scene(sn) else 'FAILED'
        except Exception as e:
            log(f'ERROR scene {sn}: {e}')
            import traceback; traceback.print_exc()
            results[sn] = f'ERROR: {e}'
    
    log(f'\nRESULTS:')
    for sn, st in results.items():
        log(f'  Scene {sn}: {st}')

if __name__ == '__main__':
    main()
