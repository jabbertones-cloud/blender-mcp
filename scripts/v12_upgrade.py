#!/usr/bin/env python3
"""
V12 Forensic Render Pipeline Upgrade Script
Applies PBR materials, lighting fixes, and forensic markers to v11 scenes
"""

import bpy
import math
import sys
import os

def log(msg):
    """Print with timestamp"""
    print(f"[V12_UPGRADE] {msg}")

def get_scene_number():
    """Extract scene number from command line arguments"""
    try:
        if len(sys.argv) > 4:
            return int(sys.argv[4])
    except (IndexError, ValueError):
        pass
    return 1

def apply_pbr_materials():
    """Apply PBR materials to all mesh objects based on naming conventions"""
    log("Applying PBR materials...")
    
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        
        obj_name_lower = obj.name.lower()
        material = None
        
        # Vehicle materials (car paint)
        if any(x in obj_name_lower for x in ['vehicle', 'car', 'sedan', 'suv', 'truck']):
            material = create_car_paint_material()
        
        # Road/ground materials
        elif any(x in obj_name_lower for x in ['road', 'ground', 'asphalt', 'plane']):
            material = create_asphalt_material()
        
        # Glass materials
        elif any(x in obj_name_lower for x in ['glass', 'window', 'windshield']):
            material = create_glass_material()
        
        # Default gray material
        else:
            material = create_default_material()
        
        if material:
            if len(obj.data.materials) > 0:
                obj.data.materials[0] = material
            else:
                obj.data.materials.append(material)
    
    log("PBR materials applied")

def create_car_paint_material():
    """Create a metallic car paint material"""
    mat = bpy.data.materials.new('CarPaint_Metallic')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Metallic'].default_value = 0.9
    bsdf.inputs['Roughness'].default_value = 0.15
    bsdf.inputs['Base Color'].default_value = (0.2, 0.2, 0.25, 1.0)  # Dark metallic
    return mat

def create_asphalt_material():
    """Create a dark asphalt material"""
    mat = bpy.data.materials.new('Asphalt_Dark')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.7
    bsdf.inputs['Base Color'].default_value = (0.15, 0.15, 0.15, 1.0)  # Dark gray
    return mat

def create_glass_material():
    """Create a realistic glass material"""
    mat = bpy.data.materials.new('Glass_Transparent')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Transmission'].default_value = 1.0
    bsdf.inputs['IOR'].default_value = 1.5
    bsdf.inputs['Roughness'].default_value = 0.05
    bsdf.inputs['Base Color'].default_value = (0.95, 0.95, 1.0, 1.0)  # Light blue-tinted
    return mat

def create_default_material():
    """Create a generic gray material"""
    mat = bpy.data.materials.new('GenericGray')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Roughness'].default_value = 0.5
    bsdf.inputs['Base Color'].default_value = (0.5, 0.5, 0.5, 1.0)
    return mat

def apply_nishita_sky(scene_num):
    """Apply Nishita physical sky to day scenes (1-3)"""
    if scene_num >= 4:
        log("Scene 4 is night - skipping Nishita sky")
        return
    
    log("Applying Nishita physical sky...")
    
    # Get or create world
    if len(bpy.data.worlds) == 0:
        world = bpy.data.worlds.new('World')
    else:
        world = bpy.data.worlds[0]
    
    world.use_nodes = True
    tree = world.node_tree
    
    # Clear all nodes
    for n in tree.nodes:
        tree.nodes.remove(n)
    
    # Create nodes
    bg = tree.nodes.new('ShaderNodeBackground')
    out = tree.nodes.new('ShaderNodeOutputWorld')
    sky = tree.nodes.new('ShaderNodeTexSky')
    
    # Configure sky - use HOSEK_WILKIE (available in Blender 5.1)
    sky.sky_type = 'HOSEK_WILKIE'
    sky.sun_elevation = math.radians(45)
    sky.sun_rotation = math.radians(160)
    sky.sun_disc = True
    
    # Connect
    tree.links.new(sky.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 1.5
    tree.links.new(bg.outputs['Background'], out.inputs['Surface'])
    
    log("Nishita sky applied")

def apply_night_lighting(scene_num):
    """Boost lighting for night scenes with sodium vapor warmth"""
    if scene_num < 4:
        return
    
    log("Applying night lighting enhancement...")
    
    if len(bpy.data.worlds) > 0:
        world = bpy.data.worlds[0]
        world.use_nodes = True
        tree = world.node_tree
        
        # Look for background node and boost it
        for node in tree.nodes:
            if node.type == 'BACKGROUND':
                node.inputs['Strength'].default_value = min(node.inputs['Strength'].default_value * 1.5, 2.0)
    
    # Boost existing light sources
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            obj.data.energy = obj.data.energy * 1.5 if obj.data.energy > 0 else 100

def add_subdivision_surface():
    """Add subdivision surface modifier (level 1) to all mesh objects"""
    log("Adding subdivision surface modifiers...")
    
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        
        # Check if subsurf already exists
        has_subsurf = any(m.type == 'SUBSURF' for m in obj.modifiers)
        if has_subsurf:
            continue
        
        subsurf = obj.modifiers.new(name='Subdivision', type='SUBSURF')
        subsurf.levels = 1
        subsurf.render_levels = 1
    
    log("Subdivision surface modifiers added")

def add_evidence_markers():
    """Add forensic evidence markers (red cones) at origin"""
    log("Adding forensic evidence markers...")
    
    # Deselect all
    bpy.ops.object.select_all(action='DESELECT')
    
    # Create marker cone
    bpy.ops.mesh.primitive_cone_add(
        radius1=0.3,
        depth=0.8,
        location=(0, 0, 0.4),
        vertices=8
    )
    
    marker = bpy.context.active_object
    marker.name = 'Evidence_Marker_A'
    
    # Create red emissive material
    mat = bpy.data.materials.new('Marker_Red')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1, 0, 0, 1)
    bsdf.inputs['Emission Color'].default_value = (1, 0, 0, 1)
    bsdf.inputs['Emission Strength'].default_value = 2.0
    
    marker.data.materials.append(mat)
    log("Evidence marker added")

def add_exhibit_overlay_text():
    """Add case number and exhibit info as text overlay"""
    log("Adding exhibit overlay text...")
    
    bpy.ops.object.text_add(
        location=(0, -15, 0.01),
        rotation=(math.radians(90), 0, 0)
    )
    
    txt = bpy.context.active_object
    txt.data.body = 'Case #2026-CV-DEMO | DEMONSTRATIVE AID'
    txt.data.size = 1.0
    txt.scale = (0.5, 0.5, 0.5)
    txt.name = 'Exhibit_Overlay_Text'
    
    log("Exhibit text added")

def boost_light_energy():
    """Increase light energy by 50% for all existing lights"""
    log("Boosting light energy by 50%...")
    
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            obj.data.energy = obj.data.energy * 1.5
            log(f"  Boosted {obj.name}: {obj.data.energy}")
    
    log("Light energy boosted")

def set_render_settings():
    """Set render settings to CYCLES, 1920x1080, 24 samples"""
    log("Setting render parameters...")
    
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    
    # Set Cycles samples (reduced for faster renders)
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    
    log(f"Render engine: {scene.render.engine}")
    log(f"Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}")
    log(f"Samples: {scene.cycles.samples}")

def list_cameras():
    """List all cameras in the scene"""
    cameras = []
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            cameras.append(obj.name)
    return cameras

def render_all_cameras(scene_num):
    """Render each camera angle to file"""
    log("Starting camera renders...")
    
    cameras = list_cameras()
    if not cameras:
        log("WARNING: No cameras found in scene")
        return
    
    output_dir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v12_renders'
    os.makedirs(output_dir, exist_ok=True)
    
    scene = bpy.context.scene
    
    for cam_name in cameras:
        # Set as active camera
        scene.camera = bpy.data.objects[cam_name]
        
        # Set output filepath
        output_file = os.path.join(output_dir, f'v12_scene{scene_num}_{cam_name}.png')
        scene.render.filepath = output_file
        
        log(f"Rendering camera '{cam_name}' to {output_file}")
        
        # Render
        try:
            bpy.ops.render.render(write_still=True)
            log(f"  Success: {output_file}")
        except Exception as e:
            log(f"  ERROR: {e}")

def main():
    """Main upgrade flow"""
    scene_num = get_scene_number()
    log(f"Starting V12 upgrade for scene {scene_num}")
    
    # Apply all upgrades
    apply_pbr_materials()
    
    if scene_num < 4:
        apply_nishita_sky(scene_num)
    else:
        apply_night_lighting(scene_num)
    
    add_subdivision_surface()
    add_evidence_markers()
    add_exhibit_overlay_text()
    boost_light_energy()
    set_render_settings()
    
    # Render all cameras
    render_all_cameras(scene_num)
    
    # Save scene
    output_blend = f'/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v12_scene{scene_num}.blend'
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    log(f"Scene saved to {output_blend}")
    
    log("V12 upgrade complete!")

if __name__ == '__main__':
    main()
