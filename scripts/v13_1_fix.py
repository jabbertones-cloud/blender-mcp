"""
v13.1 Fix Pass — Addresses tier-1 scorer issues:
1. BirdEye cameras too high → lower to 12m, tighter angle
2. Night scene underexposed → 5x light energy boost
3. Low edge detail → add procedural road texture, more scene objects (poles, curbs)
4. Day BirdEye overexposed → reduce exposure for overhead views
"""
import bpy
import os
import math
import traceback
from mathutils import Vector, Euler

SCENES_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders'
OUTPUT_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v13_renders'

SCENES = {
    'scene1': {'file': 'v13_scene1.blend', 'type': 'tbone', 'time': 'day'},
    'scene2': {'file': 'v13_scene2.blend', 'type': 'pedestrian', 'time': 'day'},
    'scene3': {'file': 'v13_scene3.blend', 'type': 'rearend', 'time': 'day'},
    'scene4': {'file': 'v13_scene4.blend', 'type': 'parking_night', 'time': 'night'},
}

def log(msg):
    print(f'[v13.1] {msg}', flush=True)

def get_scene_center_and_size():
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        return Vector((0, 0, 0)), 10.0
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ Vector(corner)
            all_coords.append(wc)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs), 1.0)
    return center, size

def fix_birdeye_camera():
    """Lower BirdEye camera and tilt it for better frame filling."""
    center, size = get_scene_center_and_size()
    
    for obj in bpy.context.scene.objects:
        if obj.type == 'CAMERA' and 'BirdEye' in obj.name:
            # Lower from ~20m to 12m, offset slightly for dynamic composition
            obj.location = (center.x + size*0.15, center.y - size*0.15, 12.0)
            
            # Point at scene center with slight offset
            target = center + Vector((0, 0, 0.5))
            direction = target - obj.location
            rot = direction.to_track_quat('-Z', 'Y')
            obj.rotation_euler = rot.to_euler()
            
            # Use shorter focal length for wider view
            obj.data.lens = 28
            
            log(f'Fixed {obj.name}: height=12m, lens=28mm')

def fix_night_lighting():
    """Massively boost night scene lighting."""
    # Boost existing street lights
    for obj in bpy.context.scene.objects:
        if obj.type == 'LIGHT':
            light = obj.data
            if light.type == 'SPOT':
                light.energy = 3000.0  # Was 500, now 3000
                light.spot_size = math.radians(80)
                log(f'Boosted {obj.name} to 3000W')
            elif light.type == 'AREA' and 'Ambient' in obj.name:
                light.energy = 100.0  # Was 20
                log(f'Boosted {obj.name} to 100W')
    
    # Add additional strong lights for the night scene
    center, size = get_scene_center_and_size()
    
    # Overhead parking lot flood light
    flood_data = bpy.data.lights.new(name='FloodLight_Overhead', type='AREA')
    flood_data.energy = 2000.0
    flood_data.size = size * 0.5
    flood_data.color = (1.0, 0.95, 0.85)
    
    flood_obj = bpy.data.objects.new('FloodLight_Overhead', flood_data)
    bpy.context.collection.objects.link(flood_obj)
    flood_obj.location = center + Vector((0, 0, 12))
    flood_obj.rotation_euler = Euler((0, 0, 0), 'XYZ')  # Points straight down
    
    # Vehicle headlights (two point lights near ground level)
    for i, offset in enumerate([(3, -5, 0.8), (-3, 5, 0.8)]):
        hl_data = bpy.data.lights.new(name=f'Headlight_{i}', type='SPOT')
        hl_data.energy = 800.0
        hl_data.spot_size = math.radians(40)
        hl_data.spot_blend = 0.3
        hl_data.color = (1.0, 1.0, 0.95)  # Cool white headlights
        
        hl_obj = bpy.data.objects.new(f'Headlight_{i}', hl_data)
        bpy.context.collection.objects.link(hl_obj)
        hl_obj.location = center + Vector(offset)
        direction = center - hl_obj.location
        rot = direction.to_track_quat('-Z', 'Y')
        hl_obj.rotation_euler = rot.to_euler()
    
    # Boost world background slightly
    world = bpy.context.scene.world
    if world and world.use_nodes:
        for node in world.node_tree.nodes:
            if node.type == 'BACKGROUND':
                node.inputs['Strength'].default_value = 0.3  # Was 0.15
    
    # Increase exposure for night scene
    bpy.context.scene.view_settings.exposure = 1.5  # Was 0.8
    
    log('Night lighting boosted: 3x spots at 3000W, flood at 2000W, 2 headlights at 800W, exposure=1.5')

def add_scene_detail_objects():
    """Add poles, curbs, and texture to increase edge density."""
    center, size = get_scene_center_and_size()
    
    # Material for poles
    pole_mat = bpy.data.materials.new('Pole_Mat')
    pole_mat.use_nodes = True
    bsdf = pole_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.25, 0.25, 0.28, 1.0)
    bsdf.inputs['Metallic'].default_value = 0.6
    bsdf.inputs['Roughness'].default_value = 0.5
    
    # Add utility poles along the edges
    pole_positions = [
        (center.x - size*0.4, center.y - size*0.35, 0),
        (center.x + size*0.4, center.y - size*0.35, 0),
        (center.x - size*0.4, center.y + size*0.35, 0),
        (center.x + size*0.4, center.y + size*0.35, 0),
    ]
    
    for i, pos in enumerate(pole_positions):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.08, depth=6.0, 
                                             location=(pos[0], pos[1], 3.0))
        pole = bpy.context.active_object
        pole.name = f'UtilityPole_{i}'
        pole.data.materials.append(pole_mat)
    
    # Add curbs along road edges  
    curb_mat = bpy.data.materials.new('Curb_Mat')
    curb_mat.use_nodes = True
    bsdf = curb_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.55, 0.53, 0.5, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.85
    
    for i, y_off in enumerate([-size*0.25, size*0.25]):
        bpy.ops.mesh.primitive_cube_add(size=1.0, 
                                         location=(center.x, center.y + y_off, 0.075))
        curb = bpy.context.active_object
        curb.name = f'Curb_{i}'
        curb.scale = (size*0.45, 0.08, 0.075)
        curb.data.materials.append(curb_mat)
    
    # Add a procedural texture to the road surface for more detail
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and any(t in obj.name.lower() for t in ['road', 'highway', 'ground', 'asphalt']):
            if obj.data.materials:
                mat = obj.data.materials[0]
                if mat and mat.use_nodes:
                    nodes = mat.node_tree.nodes
                    links = mat.node_tree.links
                    bsdf = nodes.get('Principled BSDF')
                    if bsdf:
                        # Add noise texture for road detail
                        noise = nodes.new(type='ShaderNodeTexNoise')
                        noise.inputs['Scale'].default_value = 50.0
                        noise.inputs['Detail'].default_value = 8.0
                        noise.inputs['Roughness'].default_value = 0.7
                        
                        # Mix noise with base color
                        mix = nodes.new(type='ShaderNodeMixRGB')
                        mix.blend_type = 'OVERLAY'
                        mix.inputs['Fac'].default_value = 0.15
                        
                        # Get current base color
                        base_color = list(bsdf.inputs['Base Color'].default_value)
                        mix.inputs['Color1'].default_value = base_color
                        
                        links.new(noise.outputs['Fac'], mix.inputs['Color2'])
                        links.new(mix.outputs['Color'], bsdf.inputs['Base Color'])
                        
                        # Also add bump for surface detail
                        bump = nodes.new(type='ShaderNodeBump')
                        bump.inputs['Strength'].default_value = 0.3
                        bump.inputs['Distance'].default_value = 0.01
                        links.new(noise.outputs['Fac'], bump.inputs['Height'])
                        links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
                        
                        log(f'Added road texture and bump to {obj.name}')
    
    log(f'Added {len(pole_positions)} utility poles + 2 curbs + road texture')

def reduce_day_birdeye_exposure():
    """For day scenes, slightly reduce exposure for overhead shots."""
    # The exposure is scene-global, so we just need to make sure it's not too bright
    scene = bpy.context.scene
    if scene.view_settings.exposure > 0.5:
        scene.view_settings.exposure = 0.5
        log(f'Reduced day exposure to 0.5')

def render_all_cameras(scene_key, prefix='v13_1'):
    """Render from every camera."""
    scene = bpy.context.scene
    cameras = [o for o in scene.objects if o.type == 'CAMERA']
    
    rendered = []
    for cam in cameras:
        scene.camera = cam
        out_path = os.path.join(OUTPUT_DIR, f'{prefix}_{scene_key}_{cam.name}.png')
        scene.render.filepath = out_path
        
        log(f'  Rendering {cam.name}...')
        bpy.ops.render.render(write_still=True)
        
        if os.path.exists(out_path):
            fsize = os.path.getsize(out_path)
            log(f'  -> {cam.name}: {fsize/1024:.0f}KB')
            rendered.append(out_path)
    
    return rendered

def process_scene(scene_key, config):
    log(f'\n{"="*50}')
    log(f'FIX: {scene_key.upper()} ({config["type"]})')
    log(f'{"="*50}')
    
    filepath = os.path.join(SCENES_DIR, config['file'])
    if not os.path.exists(filepath):
        log(f'ERROR: {filepath} not found!')
        return False, []
    
    bpy.ops.wm.open_mainfile(filepath=filepath)
    log(f'Loaded {config["file"]}')
    
    # Fix 1: BirdEye camera positioning
    log('--- Fix 1: BirdEye camera ---')
    fix_birdeye_camera()
    
    # Fix 2: Add scene detail for edge density
    log('--- Fix 2: Scene detail ---')
    add_scene_detail_objects()
    
    # Fix 3: Scene-specific fixes
    if config['time'] == 'night':
        log('--- Fix 3: Night lighting boost ---')
        fix_night_lighting()
    else:
        log('--- Fix 3: Day exposure adjustment ---')
        reduce_day_birdeye_exposure()
    
    # Save
    save_path = os.path.join(SCENES_DIR, f'v13_1_{scene_key}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=save_path)
    log(f'Saved: {save_path}')
    
    # Render
    log('--- Rendering ---')
    rendered = render_all_cameras(scene_key)
    
    log(f'{scene_key} complete: {len(rendered)} renders')
    return True, rendered

def main():
    log('='*50)
    log('v13.1 FIX PASS')
    log(f'Blender {bpy.app.version_string}')
    log('='*50)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    results = {}
    all_renders = []
    
    for scene_key, config in SCENES.items():
        try:
            success, renders = process_scene(scene_key, config)
            results[scene_key] = success
            all_renders.extend(renders)
        except Exception as e:
            log(f'EXCEPTION in {scene_key}: {e}')
            traceback.print_exc()
            results[scene_key] = False
    
    log('\n' + '='*50)
    log('SUMMARY')
    log('='*50)
    ok = sum(1 for v in results.values() if v)
    for k, v in results.items():
        log(f'  {k}: {"OK" if v else "FAILED"}')
    log(f'\n{ok}/{len(results)} scenes fixed, {len(all_renders)} renders')
    log('DONE')

if __name__ == '__main__':
    main()
