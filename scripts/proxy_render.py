#!/usr/bin/env python3
"""
Proxy Render Script for Blender
Renders at configurable resolution percentages while preserving all other scene settings.

Usage:
  blender --background scene.blend --python proxy_render.py -- --percent 25 --camera Cam_BirdEye --output /path/to/output.png
  blender --background scene.blend --python proxy_render.py -- --percent 50 --all-cameras --output-dir /path/to/output
"""

import bpy
import json
import time
import argparse
import sys
import os
from pathlib import Path


def parse_args(argv):
    """Parse command-line arguments from Blender's argv."""
    # Blender passes the script path and everything after '--' to argv
    if '--' in argv:
        argv = argv[argv.index('--') + 1:]
    
    parser = argparse.ArgumentParser(description='Proxy render at configurable resolution')
    parser.add_argument('--percent', type=int, default=100, 
                       choices=[25, 50, 100],
                       help='Resolution percentage (25/50/100)')
    parser.add_argument('--camera', type=str, default='all',
                       help='Camera name to render, or "all" for every camera')
    parser.add_argument('--all-cameras', action='store_true',
                       help='Render all cameras in scene')
    parser.add_argument('--output', type=str, default='',
                       help='Output file path (single camera)')
    parser.add_argument('--output-dir', type=str, default='',
                       help='Output directory (multiple cameras)')
    parser.add_argument('--scene-num', type=int, default=1,
                       choices=[1, 2, 3, 4],
                       help='Scene number (1-4)')
    
    return parser.parse_args(argv)


def get_cameras_to_render(scene, camera_arg, all_cameras_flag):
    """Determine which cameras to render."""
    if all_cameras_flag or camera_arg == 'all':
        cameras = [obj for obj in scene.objects if obj.type == 'CAMERA']
        return cameras
    else:
        # Find specific camera
        camera = bpy.data.objects.get(camera_arg)
        if camera and camera.type == 'CAMERA':
            return [camera]
        else:
            print(f"ERROR: Camera '{camera_arg}' not found in scene")
            return []


def ensure_cycles_for_background(scene):
    """Switch EEVEE to Cycles when running in --background mode.
    EEVEE requires GPU context unavailable in headless mode, producing black/flat frames.
    Cycles with CPU works reliably in headless mode."""
    if not bpy.app.background:
        return False  # GUI mode, EEVEE works fine
    
    engine = scene.render.engine
    if 'EEVEE' in engine:
        print(f'[proxy] WARNING: EEVEE detected in --background mode. Auto-switching to Cycles.')
        print(f'[proxy] (EEVEE cannot render headlessly - produces black/flat frames)')
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 64  # Low samples for proxy speed
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = 0.05  # Aggressive for proxy
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False
        scene.cycles.max_bounces = 8
        scene.cycles.sample_clamp_indirect = 10.0
        # Enable denoising data passes
        vl = bpy.context.view_layer
        if hasattr(vl, 'use_pass_denoising_normal'):
            vl.use_pass_denoising_normal = True
        if hasattr(vl, 'use_pass_denoising_albedo'):
            vl.use_pass_denoising_albedo = True
        return True
    return False


def render_camera(scene, camera, output_path, percent, render_start_time):
    """Render a single camera and return metadata."""
    # Set camera as active
    scene.camera = camera
    
    # Set output path
    scene.render.filepath = output_path
    
    # Apply resolution percentage
    original_percent = scene.render.resolution_percentage
    scene.render.resolution_percentage = percent
    
    try:
        # Perform render
        bpy.ops.render.render(write_still=True)
        
        render_time = time.time() - render_start_time
        
        # Get file size
        if os.path.exists(output_path):
            file_size_bytes = os.path.getsize(output_path)
            file_size_kb = file_size_bytes / 1024.0
        else:
            file_size_kb = 0
            print(f"WARNING: Output file not found at {output_path}")
        
        result = {
            "camera": camera.name,
            "percent": percent,
            "output": output_path,
            "render_time_s": round(render_time, 3),
            "file_size_kb": round(file_size_kb, 2),
            "status": "success"
        }
        
        return result
    
    except Exception as e:
        render_time = time.time() - render_start_time
        return {
            "camera": camera.name,
            "percent": percent,
            "output": output_path,
            "render_time_s": round(render_time, 3),
            "file_size_kb": 0,
            "status": "failed",
            "error": str(e)
        }
    
    finally:
        # Restore original resolution percentage
        scene.render.resolution_percentage = original_percent


def main():
    args = parse_args(sys.argv)
    
    # Get the active scene
    scene = bpy.context.scene
    
    print(f"Proxy Render Starting")
    print(f"  Scene: {scene.name}")
    print(f"  Resolution: {args.percent}%")
    
    # Determine output configuration
    if args.all_cameras or args.camera == 'all':
        if not args.output_dir:
            print("ERROR: --output-dir required when rendering multiple cameras")
            sys.exit(1)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        if not args.output:
            print("ERROR: --output required when rendering single camera")
            sys.exit(1)
        output_dir = Path(args.output).parent
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Auto-switch EEVEE to Cycles in background mode
    switched = ensure_cycles_for_background(scene)
    if switched:
        # Adjust samples based on proxy percentage for speed
        if args.percent == 25:
            scene.cycles.samples = 32
        elif args.percent == 50:
            scene.cycles.samples = 48
        else:
            scene.cycles.samples = 64
    
    # Get cameras to render
    cameras = get_cameras_to_render(scene, args.camera, args.all_cameras)
    
    if not cameras:
        print("ERROR: No cameras to render")
        sys.exit(1)
    
    # Render each camera
    results = []
    total_start = time.time()
    
    for camera in cameras:
        render_start = time.time()
        
        if args.all_cameras or args.camera == 'all':
            # Generate output path from camera name
            safe_name = camera.name.replace(' ', '_').replace('/', '_')
            output_path = str(output_dir / f"{safe_name}_{args.percent}pct.png")
        else:
            output_path = args.output
        
        print(f"Rendering camera: {camera.name}")
        result = render_camera(scene, camera, output_path, args.percent, render_start)
        results.append(result)
        
        print(f"  Time: {result['render_time_s']}s, Size: {result['file_size_kb']}KB, Status: {result['status']}")
    
    total_time = time.time() - total_start
    
    # Print JSON summary
    summary = {
        "scene": scene.name,
        "percent": args.percent,
        "cameras_rendered": len([r for r in results if r['status'] == 'success']),
        "total_render_time_s": round(total_time, 3),
        "results": results
    }
    
    print("\n--- PROXY RENDER SUMMARY ---")
    print(json.dumps(summary, indent=2))
    
    # Write summary to file if output-dir specified
    if args.output_dir:
        summary_path = Path(args.output_dir) / "render_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"Summary written to {summary_path}")


if __name__ == '__main__':
    main()
