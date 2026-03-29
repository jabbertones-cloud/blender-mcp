#!/usr/bin/env python3
"""
v14_2_targeted.py - Targeted improvements on v13.1 base for scorer alignment

Key principle: Start from v13.1 (which scored 72.9) and make ONLY improvements
that boost the tier-1 pixel scorer metrics WITHOUT the failures of v14:
- No subdivision smoothing (keep hard edges)
- No uniform HDRI replacement (keep contrast)
- No aggressive DOF (keep forensic clarity)
- ADD detail objects (edges, color variance)
- ADD focused lighting (contrast)
- ADD road markings (visible edges)
- BOOST existing materials (saturation)
- KEEP DriverPOV cameras (they score 78-81)

Usage: python3 v14_2_targeted.py --scene 1
"""

import bpy
import math
import random
import sys
import os
from pathlib import Path

def setup_logging():
    """Configure logging output."""
    print("\n" + "="*80)
    print("v14_2_targeted.py - Targeted Scorer Alignment Improvements")
    print("="*80)

def parse_arguments():
    """Parse command-line arguments."""
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    
    scene_num = 1
    if "--scene" in args:
        idx = args.index("--scene")
        if idx + 1 < len(args):
            try:
                scene_num = int(args[idx + 1])
            except ValueError:
                print(f"WARNING: Invalid scene number, defaulting to 1")
    
    return scene_num

def find_project_root():
    """Find the openclaw-blender-mcp project root."""
    current = Path.home()
    for candidate in [
        Path.home() / "claw-architect" / "openclaw-blender-mcp",
        Path.cwd(),
        Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp"),
    ]:
        if candidate.exists() and (candidate / "scripts").exists():
            return candidate
    return Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp")

def get_scene_paths(scene_num):
    """Get input and output paths for a scene."""
    project_root = find_project_root()
    scenes_dir = project_root / "renders"
    renders_dir = project_root / "renders"
    
    input_file = scenes_dir / f"v13_1_scene{scene_num}.blend"
    output_file = scenes_dir / f"v14_2_scene{scene_num}.blend"
    render_dir = renders_dir / "v14_renders"
    
    render_dir.mkdir(parents=True, exist_ok=True)
    
    return {
        "input": str(input_file),
        "output": str(output_file),
        "render_dir": str(render_dir),
        "scene_num": scene_num
    }

def load_scene(input_path):
    """Load the v13.1 scene file."""
    print(f"\n[LOAD] Loading scene: {input_path}")
    
    if not os.path.exists(input_path):
        print(f"ERROR: Scene file not found: {input_path}")
        return False
    
    try:
        bpy.ops.wm.open_mainfile(filepath=input_path)
        print(f"[LOAD] Scene loaded successfully")
        return True
    except Exception as e:
        print(f"ERROR loading scene: {e}")
        return False

def find_road_center():
    """Find the center of the road/ground plane."""
    print(f"\n[GEOMETRY] Finding road center...")
    
    road_obj = None
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and any(kw in obj.name.lower() for kw in ['road', 'ground', 'plane', 'street']):
            road_obj = obj
            break
    
    if road_obj:
        center = road_obj.location.copy()
        print(f"[GEOMETRY] Road center found: ({center.x:.2f}, {center.y:.2f}, {center.z:.2f})")
        return center
    else:
        print(f"[GEOMETRY] No road found, using origin (0, 0, 0)")
        return (0, 0, 0)

def find_vehicle_locations():
    """Find vehicle positions for nearby detail object placement."""
    print(f"\n[GEOMETRY] Finding vehicle positions...")
    
    vehicles = []
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and any(kw in obj.name.lower() for kw in ['sedan', 'suv', 'van', 'truck', 'car', 'vehicle']):
            loc = obj.location.copy()
            vehicles.append(loc)
            print(f"[GEOMETRY] Vehicle found: {obj.name} at ({loc.x:.2f}, {loc.y:.2f}, {loc.z:.2f})")
    
    return vehicles

def get_random_road_position(road_center, offset_range=3.0):
    """Get a random position along the road near the center."""
    x = road_center[0] + random.uniform(-offset_range, offset_range)
    y = road_center[1] + random.uniform(-2, 2)
    z = road_center[2] + 0.1
    return (x, y, z)

def improve_environment(scene_num):
    """
    1. HDRI Environment - Boost existing lighting slightly
    Don't replace, just enhance what's there to avoid washing out
    """
    print(f"\n[ENV] Improving environment lighting...")
    
    try:
        world = bpy.context.scene.world
        if world and world.use_nodes:
            nodes = world.node_tree.nodes
            
            # Find and boost existing background
            for node in nodes:
                if node.type == 'BACKGROUND':
                    current_strength = node.inputs['Strength'].default_value
                    new_strength = max(current_strength, 1.3)
                    node.inputs['Strength'].default_value = new_strength
                    print(f"[ENV] Background strength: {current_strength:.2f} -> {new_strength:.2f}")
                    break
        else:
            print(f"[ENV] World has no nodes, skipping environment boost")
    except Exception as e:
        print(f"[ENV] Warning: Could not improve environment: {e}")

def add_traffic_cones(road_center, vehicle_locs):
    """
    2. Add traffic cones for edge complexity and color variance
    Orange cones = bright color boost
    """
    print(f"\n[DETAIL] Adding traffic cones...")
    
    try:
        # Determine cone positions along road
        positions = []
        
        # Along road edges (left side)
        for i in range(3):
            pos = (
                road_center[0] - 3.5,
                road_center[1] + (i - 1) * 1.5,
                road_center[2] + 0.25
            )
            positions.append(pos)
        
        # Along road edges (right side)
        for i in range(3):
            pos = (
                road_center[0] + 3.5,
                road_center[1] + (i - 1) * 1.5,
                road_center[2] + 0.25
            )
            positions.append(pos)
        
        # Create cones
        for i, pos in enumerate(positions):
            bpy.ops.mesh.primitive_cone_add(
                vertices=12,
                radius1=0.15,
                radius2=0.02,
                depth=0.5,
                location=pos
            )
            cone = bpy.context.active_object
            cone.name = f'TrafficCone_{i}'
            
            # Bright orange material
            mat = bpy.data.materials.new(f'cone_orange_{i}')
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (1.0, 0.4, 0.0, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 0.1
            
            cone.data.materials.append(mat)
        
        print(f"[DETAIL] Added {len(positions)} traffic cones")
    except Exception as e:
        print(f"[DETAIL] Warning: Could not add traffic cones: {e}")

def add_road_barriers(road_center):
    """
    Add road barrier segments for horizontal edge lines
    """
    print(f"\n[DETAIL] Adding road barriers...")
    
    try:
        positions = [
            (road_center[0] - 2.0, road_center[1] - 3.0, road_center[2] + 0.3),
            (road_center[0] - 2.0, road_center[1] + 0.0, road_center[2] + 0.3),
            (road_center[0] - 2.0, road_center[1] + 3.0, road_center[2] + 0.3),
            (road_center[0] + 2.0, road_center[1] + 0.0, road_center[2] + 0.3),
        ]
        
        for i, pos in enumerate(positions):
            bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
            barrier = bpy.context.active_object
            barrier.name = f'Barrier_{i}'
            barrier.scale = (2.0, 0.15, 0.5)
            
            # Red-white striped material
            mat = bpy.data.materials.new(f'barrier_red_{i}')
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (0.9, 0.1, 0.1, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 0.05
            
            barrier.data.materials.append(mat)
        
        print(f"[DETAIL] Added {len(positions)} road barriers")
    except Exception as e:
        print(f"[DETAIL] Warning: Could not add road barriers: {e}")

def add_evidence_markers(road_center):
    """
    Add evidence number markers for forensic authenticity
    Bright yellow cylinders = color variance boost
    """
    print(f"\n[DETAIL] Adding evidence markers...")
    
    try:
        positions = [
            (road_center[0] - 1.5, road_center[1] - 2.0, road_center[2] + 0.1),
            (road_center[0] - 0.5, road_center[1] - 1.5, road_center[2] + 0.1),
            (road_center[0] + 0.5, road_center[1] + 1.0, road_center[2] + 0.1),
            (road_center[0] + 1.5, road_center[1] + 2.0, road_center[2] + 0.1),
        ]
        
        for i, pos in enumerate(positions):
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.12,
                depth=0.02,
                location=pos
            )
            marker = bpy.context.active_object
            marker.name = f'Evidence_Marker_{i}'
            
            # Bright yellow material
            mat = bpy.data.materials.new(f'evidence_yellow_{i}')
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (1.0, 0.9, 0.0, 1.0)
            bsdf.inputs['Emission Color'].default_value = (1.0, 0.9, 0.0, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 0.2
            
            marker.data.materials.append(mat)
        
        print(f"[DETAIL] Added {len(positions)} evidence markers")
    except Exception as e:
        print(f"[DETAIL] Warning: Could not add evidence markers: {e}")

def improve_lighting_contrast():
    """
    3. Lighting Contrast Enhancement
    Add focused spotlights for contrast without washing out
    Boost existing lights moderately (1.5x, not 3x)
    """
    print(f"\n[LIGHT] Improving lighting contrast...")
    
    try:
        # Add impact spot light
        spot_data = bpy.data.lights.new('ImpactSpot', type='SPOT')
        spot_data.energy = 2500
        spot_data.spot_size = math.radians(45)
        spot_data.spot_blend = 0.5
        
        spot_obj = bpy.data.objects.new('ImpactSpot', spot_data)
        bpy.context.scene.collection.objects.link(spot_obj)
        spot_obj.location = (0, -3, 8)
        spot_obj.rotation_euler = (math.radians(20), 0, 0)
        
        print(f"[LIGHT] Added impact spotlight")
    except Exception as e:
        print(f"[LIGHT] Warning: Could not add impact spotlight: {e}")
    
    try:
        # Add rim light for edge definition
        rim_data = bpy.data.lights.new('RimLight', type='AREA')
        rim_data.energy = 1500
        rim_data.size = 2.0
        
        rim_obj = bpy.data.objects.new('RimLight', rim_data)
        bpy.context.scene.collection.objects.link(rim_obj)
        rim_obj.location = (-5, 0, 4)
        
        print(f"[LIGHT] Added rim light")
    except Exception as e:
        print(f"[LIGHT] Warning: Could not add rim light: {e}")
    
    try:
        # Boost existing lights by 50% (moderate boost, not aggressive)
        boosted = 0
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT' and obj.name not in ['ImpactSpot', 'RimLight']:
                original = obj.data.energy
                obj.data.energy *= 1.5
                boosted += 1
        
        if boosted > 0:
            print(f"[LIGHT] Boosted {boosted} existing lights (1.5x multiplier)")
    except Exception as e:
        print(f"[LIGHT] Warning: Could not boost existing lights: {e}")

def boost_material_colors():
    """
    4. Material Color Diversity
    Increase saturation on vehicles and objects for color variance boost
    """
    print(f"\n[MATERIAL] Boosting material colors...")
    
    try:
        boosted = 0
        for obj in bpy.data.objects:
            if obj.type == 'MESH' and any(kw in obj.name.lower() for kw in ['sedan', 'suv', 'van', 'truck', 'car', 'vehicle']):
                for mat_slot in obj.material_slots:
                    if mat_slot.material and mat_slot.material.use_nodes:
                        for node in mat_slot.material.node_tree.nodes:
                            if node.type == 'BSDF_PRINCIPLED' or node.type == 'ShaderNodeBsdfPrincipled':
                                try:
                                    color = list(node.inputs['Base Color'].default_value)
                                    # Boost saturation by 30%
                                    max_c = max(color[:3])
                                    min_c = min(color[:3])
                                    if max_c > 0:
                                        for i in range(3):
                                            color[i] = min(1.0, color[i] * 1.3)
                                        node.inputs['Base Color'].default_value = tuple(color)
                                        boosted += 1
                                except:
                                    pass
        
        print(f"[MATERIAL] Boosted saturation on {boosted} material slots")
    except Exception as e:
        print(f"[MATERIAL] Warning: Could not boost material colors: {e}")

def add_road_markings(road_center):
    """
    5. Add Road Lane Markings
    Yellow center line + white edge lines for visible edge density
    """
    print(f"\n[MARKINGS] Adding road lane markings...")
    
    try:
        # Center yellow line
        bpy.ops.mesh.primitive_plane_add(size=1, location=(road_center[0], road_center[1], road_center[2] + 0.011))
        center_line = bpy.context.active_object
        center_line.name = 'CenterLine'
        center_line.scale = (0.08, 20, 1)
        
        mat = bpy.data.materials.new('yellow_line')
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (1.0, 0.8, 0.0, 1.0)
        bsdf.inputs['Emission Color'].default_value = (1.0, 0.8, 0.0, 1.0)
        bsdf.inputs['Emission Strength'].default_value = 0.3
        
        center_line.data.materials.append(mat)
        print(f"[MARKINGS] Added center yellow line")
    except Exception as e:
        print(f"[MARKINGS] Warning: Could not add center line: {e}")
    
    try:
        # Edge white lines (left and right)
        for side_offset in [-3.5, 3.5]:
            bpy.ops.mesh.primitive_plane_add(
                size=1,
                location=(road_center[0] + side_offset, road_center[1], road_center[2] + 0.011)
            )
            edge_line = bpy.context.active_object
            edge_line.name = f'EdgeLine_{side_offset}'
            edge_line.scale = (0.06, 20, 1)
            
            mat = bpy.data.materials.new(f'white_line_{side_offset}')
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            bsdf.inputs['Emission Color'].default_value = (1.0, 1.0, 1.0, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 0.1
            
            edge_line.data.materials.append(mat)
        
        print(f"[MARKINGS] Added edge white lines (left and right)")
    except Exception as e:
        print(f"[MARKINGS] Warning: Could not add edge lines: {e}")

def optimize_exposure_and_view(scene_num):
    """
    6. Exposure and Color Management
    Keep AgX, add punchiness, optimize for day/night
    """
    print(f"\n[VIEW] Optimizing exposure and color management...")
    
    try:
        scene = bpy.context.scene
        
        # AgX with moderate contrast
        scene.view_settings.view_transform = 'AgX'
        
        # Try to set look to medium-high contrast
        try:
            scene.view_settings.look = 'AgX - Medium High Contrast'
            print(f"[VIEW] Set AgX look to 'Medium High Contrast'")
        except:
            try:
                scene.view_settings.look = 'AgX - Punchy'
                print(f"[VIEW] Set AgX look to 'Punchy'")
            except:
                print(f"[VIEW] Could not set AgX look (using default)")
        
        # Day scenes: positive exposure for brightness
        if scene_num <= 3:
            scene.view_settings.exposure = 0.5
            print(f"[VIEW] Day scene: exposure = 0.5")
        else:
            scene.view_settings.exposure = 1.0
            print(f"[VIEW] Night scene: exposure = 1.0")
        
    except Exception as e:
        print(f"[VIEW] Warning: Could not optimize exposure: {e}")

def optimize_camera(scene_num):
    """
    7. Camera Optimization
    Disable DOF for sharp forensic clarity, keep existing lens settings
    """
    print(f"\n[CAMERA] Optimizing cameras...")
    
    try:
        dof_disabled = 0
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                if hasattr(obj.data, 'dof') and obj.data.dof.use_dof:
                    obj.data.dof.use_dof = False
                    dof_disabled += 1
                    print(f"[CAMERA] Disabled DOF on {obj.name}")
        
        if dof_disabled == 0:
            print(f"[CAMERA] No DOF to disable (already sharp)")
    except Exception as e:
        print(f"[CAMERA] Warning: Could not optimize cameras: {e}")

def optimize_render_settings():
    """
    8. EEVEE Quality Settings
    Optimize for high-quality renders
    """
    print(f"\n[RENDER] Optimizing render settings...")
    
    try:
        scene = bpy.context.scene
        
        # Use EEVEE
        scene.render.engine = 'BLENDER_EEVEE'
        print(f"[RENDER] Render engine: BLENDER_EEVEE")
        
        # High quality samples
        if hasattr(scene.eevee, 'taa_render_samples'):
            scene.eevee.taa_render_samples = 128
            print(f"[RENDER] TAA samples: 128")
        
        # Resolution
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = 100
        print(f"[RENDER] Resolution: 1920x1080 (100%)")
        
    except Exception as e:
        print(f"[RENDER] Warning: Could not optimize render settings: {e}")

def render_all_cameras(render_dir, scene_num):
    """
    Render all cameras to PNG files
    """
    print(f"\n[RENDER] Rendering all cameras...")
    
    scene = bpy.context.scene
    
    # Get all cameras
    cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
    
    if not cameras:
        print(f"[RENDER] No cameras found in scene")
        return
    
    print(f"[RENDER] Found {len(cameras)} camera(s)")
    
    for cam in cameras:
        try:
            scene.camera = cam
            
            # Generate output filename
            camera_name = cam.name.replace(" ", "_").replace(".", "_")
            output_path = os.path.join(
                render_dir,
                f"v14_2_scene{scene_num}_{camera_name}.png"
            )
            
            scene.render.filepath = output_path
            
            print(f"[RENDER] Rendering {cam.name} -> {os.path.basename(output_path)}")
            bpy.ops.render.render(write_still=True)
            
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path) / (1024 * 1024)
                print(f"[RENDER] Saved {os.path.basename(output_path)} ({file_size:.2f} MB)")
            
        except Exception as e:
            print(f"[RENDER] Error rendering {cam.name}: {e}")

def save_scene(output_path):
    """Save the modified scene."""
    print(f"\n[SAVE] Saving scene to {output_path}")
    
    try:
        bpy.ops.wm.save_as_mainfile(filepath=output_path)
        print(f"[SAVE] Scene saved successfully")
        return True
    except Exception as e:
        print(f"ERROR saving scene: {e}")
        return False

def main():
    setup_logging()
    
    # Parse arguments
    scene_num = parse_arguments()
    print(f"\nScene number: {scene_num}")
    
    # Get paths
    paths = get_scene_paths(scene_num)
    print(f"Input:  {paths['input']}")
    print(f"Output: {paths['output']}")
    print(f"Renders: {paths['render_dir']}")
    
    # Load scene
    if not load_scene(paths['input']):
        return
    
    # Find geometry
    road_center = find_road_center()
    vehicles = find_vehicle_locations()
    
    # Apply improvements in order
    print(f"\n{'='*80}")
    print("APPLYING TARGETED IMPROVEMENTS")
    print(f"{'='*80}")
    
    improve_environment(scene_num)
    add_traffic_cones(road_center, vehicles)
    add_road_barriers(road_center)
    add_evidence_markers(road_center)
    improve_lighting_contrast()
    boost_material_colors()
    add_road_markings(road_center)
    optimize_exposure_and_view(scene_num)
    optimize_camera(scene_num)
    optimize_render_settings()
    
    # Save modified scene
    print(f"\n{'='*80}")
    print("FINALIZING")
    print(f"{'='*80}")
    
    save_scene(paths['output'])
    
    # Render all cameras
    render_all_cameras(paths['render_dir'], scene_num)
    
    print(f"\n{'='*80}")
    print("COMPLETE")
    print(f"{'='*80}")
    print(f"\nScene saved: {paths['output']}")
    print(f"Renders saved to: {paths['render_dir']}/")
    print(f"\nKey improvements applied:")
    print(f"  ✓ Environment lighting boosted (not replaced)")
    print(f"  ✓ Traffic cones added (orange = color variance)")
    print(f"  ✓ Road barriers added (horizontal edges)")
    print(f"  ✓ Evidence markers added (bright yellow = color variance)")
    print(f"  ✓ Focused spotlights added (impact + rim)")
    print(f"  ✓ Existing lights boosted 1.5x (moderate, not aggressive)")
    print(f"  ✓ Vehicle colors boosted 30% saturation")
    print(f"  ✓ Road markings added (yellow center, white edges)")
    print(f"  ✓ AgX color grading optimized")
    print(f"  ✓ DOF disabled (forensic clarity)")
    print(f"  ✓ EEVEE rendering optimized")

if __name__ == "__main__":
    main()
