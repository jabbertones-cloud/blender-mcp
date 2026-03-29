#!/usr/bin/env python3
"""
v14.1 Fix Script for Underexposed Forensic Renders

Fixes applied:
1. EEVEE Engine & Quality settings (was using wrong EEVEE_NEXT)
2. Boost HDRI strength (day: 2.5, night: 0.8)
3. Boost all existing lights by 3x
4. Add strong fill lights for day scenes
5. Massive night scene lighting boost
6. Exposure adjustment (day: 1.5, night: 2.5)
7. Fix camera DOF settings

Usage: blender --background scene_file.blend --python v14_1_fix.py -- --scene N
"""

import bpy
import sys
import os
from pathlib import Path

def log(message):
    """Print progress messages"""
    print(f"[v14.1 FIX] {message}")

def parse_arguments():
    """Parse command line arguments"""
    try:
        argv = sys.argv
        argv = argv[argv.index("--") + 1:]  # Get args after --
        
        scene_num = None
        for i, arg in enumerate(argv):
            if arg == "--scene" and i + 1 < len(argv):
                scene_num = int(argv[i + 1])
        
        if not scene_num or scene_num not in [1, 2, 3, 4]:
            log("ERROR: Invalid or missing --scene argument. Use --scene [1-4]")
            return None
        
        return scene_num
    except Exception as e:
        log(f"ERROR parsing arguments: {e}")
        return None

def load_blend_file(scene_num):
    """Load the blend file for the specified scene"""
    base_path = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders")
    blend_file = base_path / f"v14_scene{scene_num}.blend"
    
    if not blend_file.exists():
        log(f"ERROR: Blend file not found: {blend_file}")
        return False
    
    try:
        bpy.ops.wm.open_mainfile(filepath=str(blend_file))
        log(f"Loaded: {blend_file}")
        return True
    except Exception as e:
        log(f"ERROR loading blend file: {e}")
        return False

def fix_eevee_engine_and_quality(scene_num):
    """FIX 1: Set EEVEE engine and quality settings"""
    try:
        scene = bpy.context.scene
        
        # Set EEVEE (NOT EEVEE_NEXT for Blender 5.1)
        scene.render.engine = 'BLENDER_EEVEE'
        log("Set render engine to BLENDER_EEVEE")
        
        # Enable SSR
        try:
            scene.eevee.use_ssr = True
            scene.eevee.ssr_thickness = 0.2
            scene.eevee.use_ssr_refraction = True
            log("Enabled SSR and refraction")
        except Exception as e:
            log(f"WARNING: Could not set SSR: {e}")
        
        # Enable GTAO
        try:
            scene.eevee.use_gtao = True
            scene.eevee.gtao_distance = 1.0
            log("Enabled GTAO")
        except Exception as e:
            log(f"WARNING: Could not set GTAO: {e}")
        
        # Enable Bloom
        try:
            scene.eevee.use_bloom = True
            scene.eevee.bloom_threshold = 5.0
            scene.eevee.bloom_intensity = 0.02
            log("Enabled bloom")
        except Exception as e:
            log(f"WARNING: Could not set bloom: {e}")
        
        # TAA samples
        scene.eevee.taa_render_samples = 128
        log("Set TAA render samples to 128")
        
        # Resolution
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = 100
        log("Set resolution to 1920x1080")
        
        # Color management - AgX
        scene.view_settings.view_transform = 'AgX'
        try:
            scene.view_settings.look = 'AgX - Medium High Contrast'
            log("Set color transform to AgX - Medium High Contrast")
        except:
            try:
                scene.view_settings.look = 'AgX - Punchy'
                log("Set color transform to AgX - Punchy")
            except:
                log("WARNING: Could not set AgX look")
        
        return True
    except Exception as e:
        log(f"ERROR in fix_eevee_engine_and_quality: {e}")
        return False

def fix_hdri_strength(scene_num):
    """FIX 2: Boost HDRI strength"""
    try:
        scene = bpy.context.scene
        world = scene.world
        
        if not world or not world.use_nodes:
            log("WARNING: World nodes not enabled")
            return False
        
        found_background = False
        for node in world.node_tree.nodes:
            if node.type == 'BACKGROUND':
                if scene_num <= 3:
                    node.inputs['Strength'].default_value = 2.5
                    log(f"Set HDRI strength to 2.5 (day scene)")
                else:
                    node.inputs['Strength'].default_value = 0.8
                    log(f"Set HDRI strength to 0.8 (night scene)")
                found_background = True
                break
        
        if not found_background:
            log("WARNING: BACKGROUND node not found in world")
            return False
        
        return True
    except Exception as e:
        log(f"ERROR in fix_hdri_strength: {e}")
        return False

def boost_existing_lights():
    """FIX 3: Boost all existing lights by 3x"""
    try:
        lights_boosted = 0
        for obj in bpy.data.objects:
            if obj.type == 'LIGHT':
                obj.data.energy *= 3.0
                if obj.data.energy < 100:
                    obj.data.energy = 500
                lights_boosted += 1
        
        log(f"Boosted {lights_boosted} existing lights by 3x")
        return True
    except Exception as e:
        log(f"ERROR in boost_existing_lights: {e}")
        return False

def add_fill_lights_day_scenes(scene_num):
    """FIX 4: Add strong fill lights for day scenes (1-3)"""
    if scene_num > 3:
        return True
    
    try:
        scene = bpy.context.scene
        
        # Add overhead ambient area light
        bpy.ops.object.light_add(type='AREA', location=(0, 0, 15))
        overhead_light = bpy.context.active_object
        overhead_light.data.energy = 2000
        overhead_light.data.size = 20
        overhead_light.name = "OverheadFill_Ambient"
        log(f"Added overhead ambient area light (energy=2000, size=20)")
        
        # Add center fill point light
        bpy.ops.object.light_add(type='POINT', location=(0, 0, 5))
        center_light = bpy.context.active_object
        center_light.data.energy = 500
        center_light.name = "CenterFill_Point"
        log(f"Added center fill point light (energy=500)")
        
        return True
    except Exception as e:
        log(f"ERROR in add_fill_lights_day_scenes: {e}")
        return False

def add_night_scene_lighting(scene_num):
    """FIX 5: Add massive lighting boost for night scene (scene 4)"""
    if scene_num != 4:
        return True
    
    try:
        scene = bpy.context.scene
        
        # Add 4 street light spots at corners
        corner_positions = [
            (10, 10, 8),
            (-10, 10, 8),
            (10, -10, 8),
            (-10, -10, 8),
        ]
        
        for i, pos in enumerate(corner_positions):
            bpy.ops.object.light_add(type='SPOT', location=pos)
            spot = bpy.context.active_object
            spot.data.energy = 8000
            spot.data.angle = 1.0
            spot.data.spot_blend = 0.3
            spot.name = f"StreetLight_Spot{i+1}"
            log(f"Added street light spot {i+1} at {pos} (energy=8000)")
        
        # Add 2 vehicle headlights
        headlight_positions = [
            (5, 0, 0.5),
            (-5, 0, 0.5),
        ]
        
        for i, pos in enumerate(headlight_positions):
            bpy.ops.object.light_add(type='SPOT', location=pos)
            headlight = bpy.context.active_object
            headlight.data.energy = 2000
            headlight.data.angle = 0.8
            headlight.name = f"VehicleHeadlight_{i+1}"
            log(f"Added vehicle headlight {i+1} at {pos} (energy=2000)")
        
        # Add moon light (SUN with blue tint)
        bpy.ops.object.light_add(type='SUN', location=(5, 5, 10))
        moon_light = bpy.context.active_object
        moon_light.data.energy = 0.5
        moon_light.data.color = (0.7, 0.8, 1.0)  # Slightly blue
        moon_light.name = "MoonLight_Sun"
        log(f"Added moon light (energy=0.5, blue tint)")
        
        # Enable volumetric fog
        try:
            scene.eevee.volumetric_start = 0.1
            scene.eevee.volumetric_end = 100.0
            scene.eevee.volumetric_tile_size = 8
            scene.eevee.volumetric_samples = 64
            scene.eevee.use_volumetric_lights = True
            scene.eevee.volumetric_light_clamp = 0.0
            # Set volumetric density via shader if available
            log(f"Enabled volumetric fog")
        except Exception as e:
            log(f"WARNING: Could not enable volumetric fog: {e}")
        
        return True
    except Exception as e:
        log(f"ERROR in add_night_scene_lighting: {e}")
        return False

def fix_exposure(scene_num):
    """FIX 6: Adjust exposure"""
    try:
        scene = bpy.context.scene
        
        if scene_num <= 3:
            scene.view_settings.exposure = 1.5
            log(f"Set exposure to 1.5 (day scene)")
        else:
            scene.view_settings.exposure = 2.5
            log(f"Set exposure to 2.5 (night scene)")
        
        return True
    except Exception as e:
        log(f"ERROR in fix_exposure: {e}")
        return False

def fix_camera_dof():
    """FIX 7: Fix camera DOF settings"""
    try:
        cameras_fixed = 0
        for obj in bpy.data.objects:
            if obj.type == 'CAMERA':
                # Enable DOF with safer settings for forensic clarity
                obj.data.dof.use_dof = True
                obj.data.dof.focus_distance = 10.0  # 10m
                obj.data.dof.aperture_fstop = 8.0   # f/8.0
                obj.data.dof.aperture_blades = 0    # Circular aperture
                cameras_fixed += 1
        
        log(f"Fixed DOF on {cameras_fixed} cameras (distance=10m, f/8.0)")
        return True
    except Exception as e:
        log(f"ERROR in fix_camera_dof: {e}")
        return False

def get_all_cameras():
    """Get all camera objects in the scene"""
    cameras = []
    for obj in bpy.data.objects:
        if obj.type == 'CAMERA':
            cameras.append(obj)
    return cameras

def render_all_cameras(scene_num):
    """Render all cameras to PNG files"""
    try:
        output_dir = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v14_renders")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cameras = get_all_cameras()
        if not cameras:
            log("WARNING: No cameras found in scene")
            return True
        
        scene = bpy.context.scene
        original_camera = scene.camera
        
        for camera in cameras:
            try:
                # Set as active camera
                scene.camera = camera
                
                # Prepare output path
                camera_name = camera.name.replace(" ", "_")
                output_file = output_dir / f"v14_1_scene{scene_num}_{camera_name}.png"
                
                # Set output path in render settings
                scene.render.filepath = str(output_file)
                
                # Render
                log(f"Rendering {camera.name} -> {output_file.name}")
                bpy.ops.render.render(write_still=True)
                log(f"Completed: {output_file.name}")
                
            except Exception as e:
                log(f"ERROR rendering camera {camera.name}: {e}")
        
        # Restore original camera
        if original_camera:
            scene.camera = original_camera
        
        return True
    except Exception as e:
        log(f"ERROR in render_all_cameras: {e}")
        return False

def save_blend_file(scene_num):
    """Save the fixed blend file"""
    try:
        base_path = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders")
        output_file = base_path / f"v14_1_scene{scene_num}.blend"
        
        bpy.ops.wm.save_as_mainfile(filepath=str(output_file))
        log(f"Saved: {output_file}")
        return True
    except Exception as e:
        log(f"ERROR saving blend file: {e}")
        return False

def main():
    """Main execution"""
    log("=" * 60)
    log("Starting v14.1 Forensic Render Fix")
    log("=" * 60)
    
    # Parse arguments
    scene_num = parse_arguments()
    if not scene_num:
        sys.exit(1)
    
    log(f"Target scene: {scene_num}")
    
    # Load blend file
    if not load_blend_file(scene_num):
        sys.exit(1)
    
    # Apply fixes
    fixes = [
        ("EEVEE Engine & Quality", lambda: fix_eevee_engine_and_quality(scene_num)),
        ("HDRI Strength Boost", lambda: fix_hdri_strength(scene_num)),
        ("Boost Existing Lights", lambda: boost_existing_lights()),
        ("Fill Lights (Day)", lambda: add_fill_lights_day_scenes(scene_num)),
        ("Night Lighting (Scene 4)", lambda: add_night_scene_lighting(scene_num)),
        ("Exposure Adjustment", lambda: fix_exposure(scene_num)),
        ("Camera DOF Fix", lambda: fix_camera_dof()),
    ]
    
    for fix_name, fix_func in fixes:
        log(f"\nApplying: {fix_name}...")
        try:
            if fix_func():
                log(f"✓ {fix_name} completed")
            else:
                log(f"✗ {fix_name} failed")
        except Exception as e:
            log(f"✗ {fix_name} exception: {e}")
    
    # Save blend file
    log(f"\nSaving fixed blend file...")
    if not save_blend_file(scene_num):
        log("WARNING: Could not save blend file")
    
    # Render all cameras
    log(f"\nRendering all cameras...")
    if not render_all_cameras(scene_num):
        log("WARNING: Rendering had issues")
    
    log("=" * 60)
    log("v14.1 Fix completed")
    log("=" * 60)

if __name__ == "__main__":
    main()
