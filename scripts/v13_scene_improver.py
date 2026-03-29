import bpy
import sys
import os
import math
import traceback
from mathutils import Vector, Euler
from pathlib import Path

# Configuration
SCENES_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders'
OUTPUT_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v13_renders'
MODELS_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/models'
BLENDER_HDRI_DIR = '/Applications/Blender.app/Contents/Resources/5.1/datafiles/studiolights/world'

SCENES = {
    'scene1': {'file': 'v12_scene1.blend', 'type': 'tbone', 'time': 'day', 'case': 'CASE-2024-0521'},
    'scene2': {'file': 'v12_scene2.blend', 'type': 'pedestrian', 'time': 'day', 'case': 'CASE-2024-0522'},
    'scene3': {'file': 'v12_scene3.blend', 'type': 'rearend', 'time': 'day', 'case': 'CASE-2024-0523'},
    'scene4': {'file': 'v12_scene4.blend', 'type': 'parking_night', 'time': 'night', 'case': 'CASE-2024-0524'},
}

def log(msg):
    print(f'[v13] {msg}', flush=True)

def safe_set_input(bsdf, name, value):
    """Safely set a Principled BSDF input, trying alternate names."""
    alternates = {
        'Transmission': ['Transmission Weight', 'Transmission'],
        'Transmission Weight': ['Transmission Weight', 'Transmission'],
        'Coat Weight': ['Coat Weight', 'Clearcoat'],
        'Coat Roughness': ['Coat Roughness', 'Clearcoat Roughness'],
        'Subsurface Weight': ['Subsurface Weight', 'Subsurface'],
        'Subsurface IOR': ['Subsurface IOR', 'Subsurface IOR'],
        'Subsurface Radius': ['Subsurface Radius'],
    }
    names_to_try = alternates.get(name, [name])
    for n in names_to_try:
        if n in bsdf.inputs:
            bsdf.inputs[n].default_value = value
            return True
    log(f'  WARNING: Could not set {name} on BSDF (tried {names_to_try})')
    return False

def get_scene_center_and_size():
    """Calculate bounding box center and size of all mesh objects."""
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

# ─── IMPROVEMENT FUNCTIONS ────────────────────────────────────────────────

def apply_subdivision_surface():
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            # Skip tiny objects (markers, text, scale bars)
            if any(skip in obj.name.lower() for skip in ['marker', 'scale', 'arrow', 'text', 'label', 'evidence', 'forensic', 'north']):
                continue
            has_subdiv = any(mod.type == 'SUBSURF' for mod in obj.modifiers)
            if not has_subdiv:
                mod = obj.modifiers.new(name='Subdiv', type='SUBSURF')
                mod.levels = 2
                mod.render_levels = 2
                count += 1
    log(f'Applied subdivision to {count} meshes')

def create_material(name, props):
    """Create a Principled BSDF material with given properties."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    if not bsdf:
        return mat
    for key, val in props.items():
        safe_set_input(bsdf, key, val)
    return mat

def assign_pbr_materials():
    """Create and assign PBR materials to all objects by name pattern."""
    # Car paint variants
    car_colors = {
        'red': (0.6, 0.05, 0.02, 1.0),
        'blue': (0.02, 0.05, 0.6, 1.0),
        'white': (0.85, 0.85, 0.88, 1.0),
        'black': (0.02, 0.02, 0.03, 1.0),
        'silver': (0.55, 0.56, 0.58, 1.0),
        'green': (0.02, 0.3, 0.05, 1.0),
    }
    
    mats = {}
    mats['car_red'] = create_material('CarPaint_Red', {
        'Base Color': car_colors['red'], 'Metallic': 0.85, 'Roughness': 0.25,
        'Coat Weight': 0.9, 'Coat Roughness': 0.05,
    })
    mats['car_blue'] = create_material('CarPaint_Blue', {
        'Base Color': car_colors['blue'], 'Metallic': 0.85, 'Roughness': 0.25,
        'Coat Weight': 0.9, 'Coat Roughness': 0.05,
    })
    mats['car_white'] = create_material('CarPaint_White', {
        'Base Color': car_colors['white'], 'Metallic': 0.7, 'Roughness': 0.3,
        'Coat Weight': 0.8, 'Coat Roughness': 0.1,
    })
    mats['car_black'] = create_material('CarPaint_Black', {
        'Base Color': car_colors['black'], 'Metallic': 0.85, 'Roughness': 0.2,
        'Coat Weight': 0.9, 'Coat Roughness': 0.05,
    })
    mats['car_silver'] = create_material('CarPaint_Silver', {
        'Base Color': car_colors['silver'], 'Metallic': 0.9, 'Roughness': 0.2,
        'Coat Weight': 0.85, 'Coat Roughness': 0.08,
    })
    mats['glass'] = create_material('Glass_PBR', {
        'Base Color': (1.0, 1.0, 1.0, 1.0), 'Roughness': 0.0,
        'Transmission Weight': 1.0, 'IOR': 1.45,
    })
    mats['asphalt'] = create_material('Asphalt_PBR', {
        'Base Color': (0.12, 0.12, 0.13, 1.0), 'Roughness': 0.88, 'Metallic': 0.0,
    })
    mats['concrete'] = create_material('Concrete_PBR', {
        'Base Color': (0.45, 0.44, 0.42, 1.0), 'Roughness': 0.9, 'Metallic': 0.0,
    })
    mats['rubber'] = create_material('Rubber_PBR', {
        'Base Color': (0.03, 0.03, 0.03, 1.0), 'Roughness': 0.82, 'Metallic': 0.0,
    })
    mats['chrome'] = create_material('Chrome_PBR', {
        'Base Color': (0.9, 0.9, 0.92, 1.0), 'Metallic': 1.0, 'Roughness': 0.05,
    })
    mats['skin'] = create_material('Skin_PBR', {
        'Base Color': (0.76, 0.57, 0.45, 1.0), 'Roughness': 0.45,
        'Subsurface Weight': 0.3,
    })
    mats['grass'] = create_material('Grass_PBR', {
        'Base Color': (0.12, 0.3, 0.08, 1.0), 'Roughness': 0.9, 'Metallic': 0.0,
    })
    mats['crosswalk'] = create_material('Crosswalk_PBR', {
        'Base Color': (0.9, 0.9, 0.85, 1.0), 'Roughness': 0.75, 'Metallic': 0.0,
    })
    mats['traffic_light'] = create_material('TrafficLight_PBR', {
        'Base Color': (0.15, 0.15, 0.1, 1.0), 'Metallic': 0.6, 'Roughness': 0.5,
    })
    
    # Vehicle color assignments per scene object index
    vehicle_color_cycle = ['car_red', 'car_blue', 'car_white', 'car_silver', 'car_black']
    veh_idx = 0
    
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        n = obj.name.lower()
        mat = None
        
        # Skip forensic overlay objects
        if any(skip in n for skip in ['scale', 'marker', 'evidence', 'forensic', 'north', 'arrow', 'disclaimer']):
            continue
        
        # Match by name
        if any(t in n for t in ['sedan', 'suv', 'police', 'van', 'truck', 'car', 'vehicle']):
            color_key = vehicle_color_cycle[veh_idx % len(vehicle_color_cycle)]
            mat = mats[color_key]
            veh_idx += 1
        elif any(t in n for t in ['glass', 'window', 'windshield']):
            mat = mats['glass']
        elif any(t in n for t in ['road', 'asphalt', 'street']):
            mat = mats['asphalt']
        elif any(t in n for t in ['sidewalk', 'curb', 'concrete']):
            mat = mats['concrete']
        elif any(t in n for t in ['tire', 'wheel', 'rubber']):
            mat = mats['rubber']
        elif any(t in n for t in ['chrome', 'bumper', 'trim', 'grill']):
            mat = mats['chrome']
        elif any(t in n for t in ['person', 'pedestrian', 'human', 'character', 'body']):
            mat = mats['skin']
        elif any(t in n for t in ['grass', 'lawn', 'vegetation']):
            mat = mats['grass']
        elif any(t in n for t in ['crosswalk', 'zebra', 'marking']):
            mat = mats['crosswalk']
        elif any(t in n for t in ['traffic', 'signal', 'light_pole']):
            mat = mats['traffic_light']
        elif 'ground' in n or 'plane' in n:
            mat = mats['asphalt']
        else:
            # For unmatched objects, check if they already have non-default materials
            if obj.data.materials and len(obj.data.materials) > 0:
                existing = obj.data.materials[0]
                if existing and existing.use_nodes:
                    bsdf = existing.node_tree.nodes.get('Principled BSDF')
                    if bsdf:
                        bc = bsdf.inputs['Base Color'].default_value
                        # If it's default grey (0.8, 0.8, 0.8), replace
                        if abs(bc[0] - 0.8) < 0.05 and abs(bc[1] - 0.8) < 0.05:
                            mat = mats['concrete']
            if not mat:
                continue  # Keep existing material
        
        if mat:
            if len(obj.data.materials) == 0:
                obj.data.materials.append(mat)
            else:
                obj.data.materials[0] = mat
            count += 1
    
    log(f'Assigned PBR materials to {count} objects')

def setup_environment(time_of_day):
    """Setup world environment."""
    scene = bpy.context.scene
    if not scene.world:
        scene.world = bpy.data.worlds.new('World')
    world = scene.world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    
    output = nodes.new(type='ShaderNodeOutputWorld')
    output.location = (400, 0)
    bg = nodes.new(type='ShaderNodeBackground')
    bg.location = (200, 0)
    links.new(bg.outputs['Background'], output.inputs['Surface'])
    
    if time_of_day == 'day':
        # Use city.exr HDRI for outdoor scenes
        hdri_path = os.path.join(BLENDER_HDRI_DIR, 'city.exr')
        if os.path.exists(hdri_path):
            env_tex = nodes.new(type='ShaderNodeTexEnvironment')
            env_tex.location = (0, 0)
            env_tex.image = bpy.data.images.load(hdri_path)
            links.new(env_tex.outputs['Color'], bg.inputs['Color'])
            bg.inputs['Strength'].default_value = 2.0
            log(f'Using city.exr HDRI for day environment')
        else:
            # Fallback: Nishita sky
            sky = nodes.new(type='ShaderNodeTexSky')
            sky.location = (0, 0)
            sky.sky_type = 'NISHITA'
            sky.sun_elevation = math.radians(45)
            sky.sun_rotation = math.radians(120)
            sky.turbidity = 2.2
            links.new(sky.outputs['Color'], bg.inputs['Color'])
            bg.inputs['Strength'].default_value = 1.5
            log('Using Nishita sky fallback')
    else:
        # Night: dark navy with very low strength
        hdri_path = os.path.join(BLENDER_HDRI_DIR, 'night.exr')
        if os.path.exists(hdri_path):
            env_tex = nodes.new(type='ShaderNodeTexEnvironment')
            env_tex.location = (0, 0)
            env_tex.image = bpy.data.images.load(hdri_path)
            links.new(env_tex.outputs['Color'], bg.inputs['Color'])
            bg.inputs['Strength'].default_value = 0.15
            log('Using night.exr HDRI')
        else:
            bg.inputs['Color'].default_value = (0.01, 0.02, 0.05, 1.0)
            bg.inputs['Strength'].default_value = 0.1
            log('Using dark sky fallback')

def setup_lighting(scene_type):
    """Setup scene lighting."""
    center, size = get_scene_center_and_size()
    
    if scene_type in ['tbone', 'pedestrian', 'rearend']:
        # Day: strong Sun lamp
        sun_data = bpy.data.lights.new(name='Sun_Main', type='SUN')
        sun_data.energy = 5.0
        sun_data.angle = math.radians(1.0)
        sun_data.color = (1.0, 0.98, 0.95)
        
        sun_obj = bpy.data.objects.new('Sun_Main', sun_data)
        bpy.context.collection.objects.link(sun_obj)
        sun_obj.rotation_euler = Euler((math.radians(50), 0, math.radians(135)), 'XYZ')
        
        # Fill light (area) for softer shadows
        fill_data = bpy.data.lights.new(name='Fill_Light', type='AREA')
        fill_data.energy = 100.0
        fill_data.size = size * 0.8
        fill_data.color = (0.85, 0.9, 1.0)
        
        fill_obj = bpy.data.objects.new('Fill_Light', fill_data)
        bpy.context.collection.objects.link(fill_obj)
        fill_obj.location = center + Vector((-size, size*0.5, size*0.7))
        
        log(f'Day lighting: Sun(5.0) + Fill area light')
    
    else:  # parking_night
        # Street lights
        for i, (pos, rot) in enumerate([
            ((-12, -8, 7), (math.radians(75), 0, math.radians(30))),
            ((10, 12, 7), (math.radians(75), 0, math.radians(210))),
            ((0, -20, 7), (math.radians(80), 0, 0)),
        ]):
            spot_data = bpy.data.lights.new(name=f'StreetLight_{i}', type='SPOT')
            spot_data.energy = 500.0
            spot_data.spot_size = math.radians(70)
            spot_data.spot_blend = 0.6
            spot_data.color = (1.0, 0.9, 0.7)  # Warm sodium
            spot_data.shadow_soft_size = 0.3
            
            spot_obj = bpy.data.objects.new(f'StreetLight_{i}', spot_data)
            bpy.context.collection.objects.link(spot_obj)
            spot_obj.location = pos
            spot_obj.rotation_euler = Euler(rot, 'XYZ')
        
        # Weak ambient fill
        amb_data = bpy.data.lights.new(name='AmbientFill', type='AREA')
        amb_data.energy = 20.0
        amb_data.size = size * 2
        amb_data.color = (0.6, 0.65, 0.8)  # Cool moonlight tint
        
        amb_obj = bpy.data.objects.new('AmbientFill', amb_data)
        bpy.context.collection.objects.link(amb_obj)
        amb_obj.location = center + Vector((0, 0, size * 1.5))
        
        log('Night lighting: 3 street spots + ambient fill')

def apply_impact_deformation(scene_type):
    """Apply vertex displacement to simulate crash damage."""
    vehicles = [o for o in bpy.context.scene.objects 
                if o.type == 'MESH' and any(t in o.name.lower() 
                for t in ['sedan', 'suv', 'car', 'truck', 'van', 'vehicle', 'police'])]
    
    if not vehicles:
        log('No vehicles found for deformation')
        return
    
    if scene_type == 'tbone' and len(vehicles) >= 2:
        # T-bone: side impact on first vehicle
        v1 = vehicles[0]
        # Use a lattice deformation for more control
        bpy.ops.object.select_all(action='DESELECT')
        v1.select_set(True)
        bpy.context.view_layer.objects.active = v1
        
        # Add displace modifier with procedural texture
        tex = bpy.data.textures.new('ImpactDent', type='CLOUDS')
        tex.noise_scale = 0.3
        
        disp = v1.modifiers.new('ImpactDamage', 'DISPLACE')
        disp.texture = tex
        disp.strength = -0.15  # Inward dent
        disp.mid_level = 0.5
        log(f'T-bone deformation on {v1.name}')
        
    elif scene_type == 'rearend' and len(vehicles) >= 2:
        v1, v2 = vehicles[0], vehicles[1]
        
        tex1 = bpy.data.textures.new('RearDent', type='CLOUDS')
        tex1.noise_scale = 0.25
        disp1 = v1.modifiers.new('RearDamage', 'DISPLACE')
        disp1.texture = tex1
        disp1.strength = -0.12
        
        tex2 = bpy.data.textures.new('FrontDent', type='CLOUDS')
        tex2.noise_scale = 0.3
        disp2 = v2.modifiers.new('FrontDamage', 'DISPLACE')
        disp2.texture = tex2
        disp2.strength = -0.1
        log(f'Rear-end deformation on {v1.name} and {v2.name}')

def add_forensic_overlays(case_number):
    """Add scale bar, disclaimer, evidence markers, north arrow."""
    center, size = get_scene_center_and_size()
    
    # Scale bar (1 meter)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(center.x - size*0.4, center.y - size*0.4, 0.05))
    bar = bpy.context.active_object
    bar.name = 'ScaleBar_1m'
    bar.scale = (1.0, 0.03, 0.03)
    
    bar_mat = bpy.data.materials.new('ScaleBar_Mat')
    bar_mat.use_nodes = True
    bsdf = bar_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 0.0, 1.0)  # Yellow
    bsdf.inputs['Roughness'].default_value = 0.3
    bar.data.materials.append(bar_mat)
    
    # Scale bar end caps
    for dx in [-0.5, 0.5]:
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(center.x - size*0.4 + dx, center.y - size*0.4, 0.05))
        cap = bpy.context.active_object
        cap.name = f'ScaleBar_Cap'
        cap.scale = (0.02, 0.08, 0.08)
        cap.data.materials.append(bar_mat)
    
    # Forensic disclaimer text
    font_data = bpy.data.curves.new(name='DisclaimerText', type='FONT')
    font_data.body = f'DEMONSTRATIVE AID - NOT DRAWN TO SCALE\n{case_number}\nExhibit A'
    font_data.align_x = 'LEFT'
    font_data.size = 0.25
    
    text_obj = bpy.data.objects.new('DisclaimerText', font_data)
    bpy.context.collection.objects.link(text_obj)
    text_obj.location = (center.x - size*0.45, center.y + size*0.45, 0.1)
    
    text_mat = bpy.data.materials.new('DisclaimerText_Mat')
    text_mat.use_nodes = True
    bsdf = text_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    text_obj.data.materials.append(text_mat)
    
    # Evidence markers (colored cones)
    marker_configs = [
        ('Evidence_A', (1.0, 0.0, 0.0, 1.0), center + Vector((-2, -1, 0))),
        ('Evidence_B', (0.0, 0.5, 1.0, 1.0), center + Vector((2, -1, 0))),
        ('Evidence_C', (1.0, 1.0, 0.0, 1.0), center + Vector((0, 2, 0))),
        ('Evidence_D', (0.0, 1.0, 0.0, 1.0), center + Vector((-1, 3, 0))),
    ]
    
    for name, color, loc in marker_configs:
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.15, depth=0.4, location=(loc.x, loc.y, 0.2))
        marker = bpy.context.active_object
        marker.name = name
        
        m_mat = bpy.data.materials.new(f'{name}_Mat')
        m_mat.use_nodes = True
        bsdf = m_mat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = 0.3
        marker.data.materials.append(m_mat)
    
    # North arrow
    font_n = bpy.data.curves.new(name='NorthArrow', type='FONT')
    font_n.body = 'N\n^'
    font_n.align_x = 'CENTER'
    font_n.size = 0.35
    
    north_obj = bpy.data.objects.new('NorthArrow', font_n)
    bpy.context.collection.objects.link(north_obj)
    north_obj.location = (center.x + size*0.45, center.y + size*0.45, 0.1)
    
    north_mat = bpy.data.materials.new('NorthArrow_Mat')
    north_mat.use_nodes = True
    bsdf = north_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1.0, 0.2, 0.2, 1.0)
    north_obj.data.materials.append(north_mat)
    
    log(f'Added forensic overlays: scale bar, disclaimer, 4 markers, north arrow')

def setup_cameras(scene_type):
    """Setup cameras for the scene. Point them at scene center."""
    center, size = get_scene_center_and_size()
    
    # Remove existing cameras
    for obj in list(bpy.context.scene.objects):
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)
    
    d = max(size * 1.2, 15.0)  # Camera distance
    
    cam_configs = {
        'Cam_BirdEye': {
            'loc': (center.x + 2, center.y - 2, d * 0.9),
            'lens': 35,
        },
        'Cam_DriverPOV': {
            'loc': (center.x - d*0.3, center.y - d*0.5, 1.7),
            'lens': 50,
        },
        'Cam_WideAngle': {
            'loc': (center.x - d*0.6, center.y - d*0.7, d*0.25),
            'lens': 24,
        },
    }
    
    # Add scene-specific cameras
    if scene_type == 'pedestrian':
        cam_configs['Cam_SightLine'] = {
            'loc': (center.x - d*0.4, center.y, 1.5),
            'lens': 35,
        }
    elif scene_type == 'parking_night':
        cam_configs['Cam_SecurityCam'] = {
            'loc': (center.x + d*0.5, center.y + d*0.5, 5.0),
            'lens': 12,
        }
    
    created = []
    for cam_name, cfg in cam_configs.items():
        cam_data = bpy.data.cameras.new(name=cam_name)
        cam_data.lens = cfg['lens']
        cam_data.clip_start = 0.1
        cam_data.clip_end = 500.0
        
        cam_obj = bpy.data.objects.new(cam_name, cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.location = cfg['loc']
        
        # Point camera at scene center
        direction = center - cam_obj.location
        rot = direction.to_track_quat('-Z', 'Y')
        cam_obj.rotation_euler = rot.to_euler()
        
        created.append(cam_name)
    
    log(f'Created {len(created)} cameras: {", ".join(created)}')

def setup_render_settings():
    """Configure render settings for EEVEE with AgX."""
    scene = bpy.context.scene
    
    # Engine: BLENDER_EEVEE for Blender 5.x
    if bpy.app.version >= (5, 0, 0):
        scene.render.engine = 'BLENDER_EEVEE'
    elif bpy.app.version >= (4, 0, 0):
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    else:
        scene.render.engine = 'BLENDER_EEVEE'
    
    # Resolution
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    
    # EEVEE samples
    if hasattr(scene, 'eevee'):
        eevee = scene.eevee
        if hasattr(eevee, 'taa_render_samples'):
            eevee.taa_render_samples = 64
        if hasattr(eevee, 'use_gtao'):
            eevee.use_gtao = True
        if hasattr(eevee, 'gtao_distance'):
            eevee.gtao_distance = 0.5
        if hasattr(eevee, 'use_bloom'):
            eevee.use_bloom = False
        if hasattr(eevee, 'use_ssr'):
            eevee.use_ssr = True
    
    # Color management
    scene.display_settings.display_device = 'sRGB'
    try:
        scene.view_settings.view_transform = 'AgX'
    except:
        try:
            scene.view_settings.view_transform = 'Filmic'
        except:
            pass
    
    # Try AgX Punchy look
    try:
        scene.view_settings.look = 'AgX - Punchy'
    except:
        try:
            scene.view_settings.look = 'Punchy'
        except:
            try:
                scene.view_settings.look = 'Medium High Contrast'
            except:
                pass
    
    scene.view_settings.exposure = 0.8
    scene.view_settings.gamma = 1.0
    
    # Film
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 15
    
    log(f'Render settings: {scene.render.engine}, 1920x1080, exposure=0.8')

def render_all_cameras(scene_key):
    """Render from every camera in the scene."""
    scene = bpy.context.scene
    cameras = [o for o in scene.objects if o.type == 'CAMERA']
    
    if not cameras:
        log('WARNING: No cameras found!')
        return []
    
    rendered = []
    for cam in cameras:
        scene.camera = cam
        out_path = os.path.join(OUTPUT_DIR, f'v13_{scene_key}_{cam.name}.png')
        scene.render.filepath = out_path
        
        log(f'  Rendering {cam.name}...')
        bpy.ops.render.render(write_still=True)
        
        if os.path.exists(out_path):
            fsize = os.path.getsize(out_path)
            log(f'  -> {cam.name}: {fsize/1024:.0f}KB')
            rendered.append(out_path)
        else:
            log(f'  -> WARNING: {cam.name} render file not found!')
    
    return rendered

def save_scene_v13(scene_key):
    """Save the improved scene as v13."""
    out_path = os.path.join(SCENES_DIR, f'v13_{scene_key}.blend')
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    log(f'Saved: {out_path}')

# ─── MAIN PIPELINE ────────────────────────────────────────────────────────

def process_scene(scene_key, scene_config):
    """Process one scene through all improvement steps."""
    log(f'\n{"="*60}')
    log(f'PROCESSING: {scene_key.upper()} ({scene_config["type"]})')
    log(f'{"="*60}')
    
    # Load
    filepath = os.path.join(SCENES_DIR, scene_config['file'])
    if not os.path.exists(filepath):
        log(f'ERROR: {filepath} not found!')
        return False, []
    
    bpy.ops.wm.open_mainfile(filepath=filepath)
    
    # Log scene contents
    objs = list(bpy.context.scene.objects)
    meshes = [o for o in objs if o.type == 'MESH']
    lights = [o for o in objs if o.type == 'LIGHT']
    cams = [o for o in objs if o.type == 'CAMERA']
    log(f'Scene loaded: {len(objs)} objects ({len(meshes)} meshes, {len(lights)} lights, {len(cams)} cameras)')
    for m in meshes:
        log(f'  MESH: {m.name} verts={len(m.data.vertices)} faces={len(m.data.polygons)}')
    
    # Apply improvements
    log('\n--- Step 1: Subdivision Surface ---')
    apply_subdivision_surface()
    
    log('\n--- Step 2: PBR Materials ---')
    assign_pbr_materials()
    
    log('\n--- Step 3: Environment ---')
    setup_environment(scene_config['time'])
    
    log('\n--- Step 4: Lighting ---')
    setup_lighting(scene_config['type'])
    
    log('\n--- Step 5: Impact Deformation ---')
    apply_impact_deformation(scene_config['type'])
    
    log('\n--- Step 6: Forensic Overlays ---')
    add_forensic_overlays(scene_config['case'])
    
    log('\n--- Step 7: Cameras ---')
    setup_cameras(scene_config['type'])
    
    log('\n--- Step 8: Render Settings ---')
    setup_render_settings()
    
    # Save scene
    log('\n--- Saving v13 scene ---')
    save_scene_v13(scene_key)
    
    # Render
    log('\n--- Rendering ---')
    rendered = render_all_cameras(scene_key)
    
    log(f'\n{scene_key} complete: {len(rendered)} renders')
    return True, rendered

def main():
    log('='*60)
    log('v13 FORENSIC SCENE IMPROVER')
    log(f'Blender {bpy.app.version_string}')
    log('='*60)
    
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
    
    # Summary
    log('\n' + '='*60)
    log('SUMMARY')
    log('='*60)
    ok = sum(1 for v in results.values() if v)
    for k, v in results.items():
        log(f'  {k}: {"OK" if v else "FAILED"}')
    log(f'\n{ok}/{len(results)} scenes processed, {len(all_renders)} total renders')
    log(f'Renders in: {OUTPUT_DIR}')
    log('DONE')

if __name__ == '__main__':
    main()
