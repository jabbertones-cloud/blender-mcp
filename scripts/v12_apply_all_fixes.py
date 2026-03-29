import bpy, math, sys

# Get scene number from command line
argv = sys.argv
scene_num = int(argv[argv.index('--') + 1]) if '--' in argv else 1
is_night = (scene_num == 4)

print(f'=== V12 UPGRADE: Scene {scene_num} ===')

# 1. RENDER ENGINE: Keep EEVEE (proven to work with v11 scenes)
scene = bpy.context.scene
# Try EEVEE NEXT first, fall back to EEVEE
try:
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
except:
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except:
        scene.render.engine = 'EEVEE'
print(f'Engine: {scene.render.engine}')

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

# 3. COLOR MANAGEMENT: AgX for better dynamic range
try:
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'None'
except:
    try:
        scene.view_settings.view_transform = 'Filmic'
    except:
        pass
scene.view_settings.exposure = 0.5 if not is_night else 1.0
print(f'Color: {scene.view_settings.view_transform}, exposure={scene.view_settings.exposure}')

# 4. WORLD BACKGROUND
world = scene.world
if not world:
    world = bpy.data.worlds.new('World')
    scene.world = world
world.use_nodes = True
tree = world.node_tree
# Find or create background node
bg_node = None
for n in tree.nodes:
    if n.type == 'BACKGROUND':
        bg_node = n
        break
if not bg_node:
    for n in tree.nodes:
        tree.nodes.remove(n)
    bg_node = tree.nodes.new('ShaderNodeBackground')
    out_node = tree.nodes.new('ShaderNodeOutputWorld')
    tree.links.new(bg_node.outputs['Background'], out_node.inputs['Surface'])

if is_night:
    bg_node.inputs['Color'].default_value = (0.01, 0.01, 0.02, 1.0)
    bg_node.inputs['Strength'].default_value = 0.05
else:
    bg_node.inputs['Color'].default_value = (0.6, 0.7, 0.8, 1.0)
    bg_node.inputs['Strength'].default_value = 1.5
print(f'World: night={is_night}')

# 5. BOOST EXISTING LIGHTS SLIGHTLY (not 10x — that was proven bad)
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.data.energy < 1.0:
            obj.data.energy = 5.0  # Fix any broken zero-energy lights
        obj.data.energy *= 1.3  # Gentle 30% boost
        print(f'Light {obj.name}: energy={obj.data.energy:.1f}')

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
        try:
            bsdf.inputs['Clear Coat Weight'].default_value = 1.0
            bsdf.inputs['Clear Coat Roughness'].default_value = 0.1
        except:
            pass
    return mat

def make_asphalt():
    mat = bpy.data.materials.new('Asphalt_v12')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.055, 1)
    bsdf.inputs['Roughness'].default_value = 0.75
    bsdf.inputs['Metallic'].default_value = 0.0
    return mat

def make_glass():
    mat = bpy.data.materials.new('Glass_v12')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.8, 0.85, 0.9, 1)
    try:
        bsdf.inputs['Transmission Weight'].default_value = 0.8
    except:
        try:
            bsdf.inputs['Coat Weight'].default_value = 0.8
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

# Assign materials based on object names
colors = [paint_red, paint_blue, paint_white, paint_black]
color_idx = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    name = obj.name.lower()
    
    # Check if object has default/no material
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
        print(f'  Material: {obj.name} -> asphalt')
    elif 'glass' in name or 'window' in name or 'windshield' in name:
        if obj.data.materials:
            obj.data.materials[0] = glass
        else:
            obj.data.materials.append(glass)
        print(f'  Material: {obj.name} -> glass')
    elif ('vehicle' in name or 'car' in name or 'sedan' in name or 'suv' in name or 
          'truck' in name or 'van' in name or 'police' in name) and not has_real_mat:
        paint = colors[color_idx % len(colors)]
        color_idx += 1
        if obj.data.materials:
            obj.data.materials[0] = paint
        else:
            obj.data.materials.append(paint)
        print(f'  Material: {obj.name} -> {paint.name}')
    elif not has_real_mat:
        # Generic gray for anything else with default material
        generic = bpy.data.materials.new('Generic_v12')
        generic.use_nodes = True
        bsdf = generic.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (0.3, 0.3, 0.32, 1)
        bsdf.inputs['Roughness'].default_value = 0.5
        if obj.data.materials:
            obj.data.materials[0] = generic
        else:
            obj.data.materials.append(generic)

# 7. SUBDIVISION SURFACE for edge detail
for obj in bpy.data.objects:
    if obj.type == 'MESH' and len(obj.data.vertices) > 10:
        # Don't add if already has one
        has_subsurf = any(m.type == 'SUBSURF' for m in obj.modifiers)
        if not has_subsurf:
            mod = obj.modifiers.new('Subdivide_v12', 'SUBSURF')
            mod.levels = 1
            mod.render_levels = 2

# 8. EVIDENCE MARKERS
marker_positions = {
    1: [(0, 0, 0.4), (3, -2, 0.4), (-2, 1, 0.4)],  # T-bone impact
    2: [(0, 0, 0.4), (2, 0, 0.4)],  # Crosswalk
    3: [(0, 0, 0.4), (-5, 0, 0.4)],  # Highway
    4: [(0, 0, 0.4), (3, 3, 0.4)],  # Parking lot
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
        bsdf.inputs['Emission'].default_value = col
    m.data.materials.append(mat)
    print(f'Marker {m.name} at {pos}')

# 9. EXHIBIT LABEL (3D text on ground)
bpy.ops.object.text_add(location=(0, -12, 0.01), rotation=(math.radians(-90), 0, 0))
txt = bpy.context.active_object
txt.name = 'Exhibit_Label'
txt.data.body = f'Case #2026-CV-DEMO  Exhibit {scene_num}-A\nDEMONSTRATIVE AID - NOT TO SCALE'
txt.data.size = 0.8
txt.scale = (1, 1, 1)
label_mat = bpy.data.materials.new('Label_White')
label_mat.use_nodes = True
bsdf = label_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (1, 1, 1, 1)
try:
    bsdf.inputs['Emission Color'].default_value = (1, 1, 1, 1)
    bsdf.inputs['Emission Strength'].default_value = 1.0
except:
    bsdf.inputs['Emission'].default_value = (1, 1, 1, 1)
txt.data.materials.append(label_mat)

# 10. SCALE BAR
bpy.ops.mesh.primitive_cube_add(size=1, location=(8, -12, 0.05))
bar = bpy.context.active_object
bar.name = 'Scale_Bar_1m'
bar.scale = (1.0, 0.05, 0.02)
bar_mat = bpy.data.materials.new('ScaleBar')
bar_mat.use_nodes = True
bsdf = bar_mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (1, 1, 0, 1)
try:
    bsdf.inputs['Emission Color'].default_value = (1, 1, 0, 1)
    bsdf.inputs['Emission Strength'].default_value = 2.0
except:
    bsdf.inputs['Emission'].default_value = (1, 1, 0, 1)
bar.data.materials.append(bar_mat)

print(f'=== V12 UPGRADE COMPLETE for Scene {scene_num} ===')
