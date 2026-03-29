#!/usr/bin/env python3
"""
V12 comprehensive fix and render script.
Applied in a single Blender session per scene.
"""
import bpy
import os
import sys

# Get scene number from command line
argv = sys.argv
scene_num = int(argv[argv.index('--') + 1]) if '--' in argv else 1
is_night = (scene_num == 4)

print(f'\n=== V12 FIX AND RENDER: Scene {scene_num} ===\n')

# 1. RENDER ENGINE: Keep EEVEE
scene = bpy.context.scene
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    print(f'Engine: BLENDER_EEVEE_NEXT')
except:
    try:
        scene.render.engine = 'BLENDER_EEVEE'
        print(f'Engine: BLENDER_EEVEE')
    except:
        scene.render.engine = 'EEVEE'
        print(f'Engine: EEVEE')

# 2. RENDER SETTINGS
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
try:
    scene.eevee.taa_render_samples = 64
except:
    try:
        scene.eevee_next.taa_samples = 64
    except:
        pass

# 3. COLOR MANAGEMENT: AgX
try:
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'None'
    print(f'Color: AgX')
except:
    try:
        scene.view_settings.view_transform = 'Filmic'
        print(f'Color: Filmic (AgX unavailable)')
    except:
        print(f'Color: Default')

scene.view_settings.exposure = 0.5 if not is_night else 1.0

# 4. WORLD BACKGROUND
world = scene.world
if not world:
    world = bpy.data.worlds.new('World')
    scene.world = world
world.use_nodes = True
tree = world.node_tree

# Clear existing nodes
for n in tree.nodes:
    tree.nodes.remove(n)

# Create new nodes
bg_node = tree.nodes.new('ShaderNodeBackground')
out_node = tree.nodes.new('ShaderNodeOutputWorld')
tree.links.new(bg_node.outputs['Background'], out_node.inputs['Surface'])

if is_night:
    bg_node.inputs['Color'].default_value = (0.01, 0.01, 0.02, 1.0)
    bg_node.inputs['Strength'].default_value = 0.05
    print(f'World: Night (RGB 0.01,0.01,0.02 @ 0.05x)')
else:
    bg_node.inputs['Color'].default_value = (0.6, 0.7, 0.8, 1.0)
    bg_node.inputs['Strength'].default_value = 1.5
    print(f'World: Day (RGB 0.6,0.7,0.8 @ 1.5x)')

# 5. BOOST LIGHTS SLIGHTLY
light_count = 0
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.data.energy < 1.0:
            obj.data.energy = 5.0
        obj.data.energy *= 1.3
        light_count += 1
        print(f'  Light {obj.name}: {obj.data.energy:.1f}W')

print(f'Adjusted {light_count} lights')

# 6. PBR MATERIALS
def make_car_paint(name, color):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = 0.9
    bsdf.inputs['Roughness'].default_value = 0.15
    try:
        bsdf.inputs['Coat Weight'].default_value = 1.0
        bsdf.inputs['Coat Roughness'].default_value = 0.1
    except:
        pass
    return mat

def make_asphalt():
    mat = bpy.data.materials.new('Asphalt_v12')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.055, 1)
    bsdf.inputs['Roughness'].default_value = 0.75
    return mat

def make_glass():
    mat = bpy.data.materials.new('Glass_v12')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.8, 0.85, 0.9, 1)
    try:
        bsdf.inputs['Transmission Weight'].default_value = 0.8
    except:
        pass
    bsdf.inputs['Roughness'].default_value = 0.05
    bsdf.inputs['IOR'].default_value = 1.5
    return mat

# Create materials
paint_red = make_car_paint('CarPaint_Red', (0.6, 0.05, 0.05, 1))
paint_blue = make_car_paint('CarPaint_Blue', (0.05, 0.1, 0.5, 1))
paint_white = make_car_paint('CarPaint_White', (0.8, 0.8, 0.82, 1))
paint_black = make_car_paint('CarPaint_Black', (0.02, 0.02, 0.02, 1))
asphalt = make_asphalt()
glass = make_glass()

print('Materials created')

# Assign materials
colors = [paint_red, paint_blue, paint_white, paint_black]
color_idx = 0
mat_count = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    name = obj.name.lower()
    
    has_real_mat = False
    if obj.data.materials:
        for m in obj.data.materials:
            if m and m.name != 'Material' and 'default' not in m.name.lower():
                has_real_mat = True
                break
    
    if 'road' in name or 'ground' in name or 'plane' in name or 'asphalt' in name or 'floor' in name:
        if obj.data.materials:
            obj.data.materials[0] = asphalt
        else:
            obj.data.materials.append(asphalt)
        mat_count += 1
    elif 'glass' in name or 'window' in name or 'windshield' in name:
        if obj.data.materials:
            obj.data.materials[0] = glass
        else:
            obj.data.materials.append(glass)
        mat_count += 1
    elif ('vehicle' in name or 'car' in name or 'sedan' in name or 'suv' in name or 
          'truck' in name or 'van' in name or 'police' in name) and not has_real_mat:
        paint = colors[color_idx % len(colors)]
        color_idx += 1
        if obj.data.materials:
            obj.data.materials[0] = paint
        else:
            obj.data.materials.append(paint)
        mat_count += 1

print(f'Materials assigned to {mat_count} objects')

# 7. EVIDENCE MARKERS
marker_positions = {
    1: [(0, 0, 0.4), (3, -2, 0.4), (-2, 1, 0.4)],
    2: [(0, 0, 0.4), (2, 0, 0.4)],
    3: [(0, 0, 0.4), (-5, 0, 0.4)],
    4: [(0, 0, 0.4), (3, 3, 0.4)],
}
marker_colors = [(1, 0, 0, 1), (0, 0, 1, 1), (1, 1, 0, 1)]
for i, pos in enumerate(marker_positions.get(scene_num, [(0,0,0.4)])):
    bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.8, location=pos)
    m = bpy.context.active_object
    m.name = f'Evidence_Marker_{chr(65+i)}'
    mat = bpy.data.materials.new(f'Marker_{chr(65+i)}')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    col = marker_colors[i % len(marker_colors)]
    bsdf.inputs['Base Color'].default_value = col
    try:
        bsdf.inputs['Emission Color'].default_value = col
        bsdf.inputs['Emission Strength'].default_value = 3.0
    except:
        pass
    m.data.materials.append(mat)

print(f'Added {len(marker_positions.get(scene_num, [(0,0,0.4)]))} evidence markers')

# 8. RENDER ALL CAMERAS
print('\nStarting renders...')
cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
print(f'Found {len(cameras)} cameras')

outdir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v12_renders'
os.makedirs(outdir, exist_ok=True)

for cam in cameras:
    scene.camera = cam
    cam_name = cam.name.replace('Camera_', '').replace(' ', '_')
    filepath = os.path.join(outdir, f'v12_scene{scene_num}_{cam_name}.png')
    scene.render.filepath = filepath
    print(f'  Rendering {cam.name}...')
    bpy.ops.render.render(write_still=True)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f'    OK: {size} bytes -> {filepath}')
    else:
        print(f'    FAILED: {filepath}')

print(f'\n=== Scene {scene_num} complete ===\n')
