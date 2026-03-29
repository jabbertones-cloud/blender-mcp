"""
v22 Standalone Render Script - 3-Layer Denoising
=================================================
Run with: blender --background <scene.blend> --python v22_render_standalone.py -- --scene <N> --output-dir <path>

This script applies render-time denoising optimizations and renders all cameras
in the loaded scene. Designed for headless Blender operation.
"""
import bpy
import sys
import os
import time

# Parse arguments after '--'
argv = sys.argv
args_start = argv.index('--') + 1 if '--' in argv else len(argv)
script_args = argv[args_start:]

scene_num = '1'
output_dir = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v22_final'

i = 0
while i < len(script_args):
    if script_args[i] == '--scene' and i + 1 < len(script_args):
        scene_num = script_args[i + 1]
        i += 2
    elif script_args[i] == '--output-dir' and i + 1 < len(script_args):
        output_dir = script_args[i + 1]
        i += 2
    else:
        i += 1

os.makedirs(output_dir, exist_ok=True)

scene = bpy.context.scene
print(f'[v22] Scene {scene_num} loaded. Engine: {scene.render.engine}')
print(f'[v22] Objects: {len(bpy.data.objects)}')

# List cameras
cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
print(f'[v22] Found {len(cameras)} cameras: {[c.name for c in cameras]}')

# ─── Auto-switch EEVEE to Cycles in background mode ─────────────────────────
engine = scene.render.engine
if bpy.app.background and 'EEVEE' in engine:
    print('[v22] WARNING: EEVEE detected in --background mode. Auto-switching to Cycles.')
    scene.render.engine = 'CYCLES'
    engine = 'CYCLES'

# ─── Apply Render-Time Denoising Settings (Layer 1) ────────────────────────
if 'CYCLES' in engine:
    print('[v22] Applying Cycles denoising settings...')
    scene.cycles.samples = 256
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.002
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.sample_clamp_indirect = 10.0
    scene.cycles.sample_clamp_direct = 0.0
    
    # Filter glossy
    if hasattr(scene.cycles, 'blur_glossy'):
        scene.cycles.blur_glossy = 1.0
    
    # Light path bounces
    scene.cycles.max_bounces = 16
    scene.cycles.diffuse_bounces = 8
    scene.cycles.glossy_bounces = 8
    scene.cycles.transmission_bounces = 12
    
    # Denoising data passes
    vl = bpy.context.view_layer
    if hasattr(vl, 'use_pass_denoising_normal'):
        vl.use_pass_denoising_normal = True
    if hasattr(vl, 'use_pass_denoising_albedo'):
        vl.use_pass_denoising_albedo = True
    
    # Film filter
    if hasattr(scene.cycles, 'pixel_filter_type'):
        scene.cycles.pixel_filter_type = 'BLACKMAN_HARRIS'
    
    # Use CPU (Metal GPU hangs per known issues)
    scene.cycles.device = 'CPU'
    
    print('[v22] Cycles denoising configured: 256 samples, OIDN, adaptive 0.002')

elif 'EEVEE' in engine:
    print('[v22] Applying EEVEE denoising settings...')
    # EEVEE uses TAA samples
    if hasattr(scene.eevee, 'taa_render_samples'):
        scene.eevee.taa_render_samples = 256
    elif hasattr(scene, 'eevee'):
        try:
            scene.eevee.taa_render_samples = 256
        except:
            pass
    print('[v22] EEVEE TAA samples set to 256')

# ─── Render Resolution ──────────────────────────────────────────────────────
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.compression = 15

# ─── Render Each Camera ─────────────────────────────────────────────────────
render_results = []

for cam in cameras:
    cam_name = cam.name.replace(' ', '_')
    output_path = os.path.join(output_dir, f'v22_scene{scene_num}_{cam_name}.png')
    
    print(f'[v22] Rendering camera: {cam_name} -> {output_path}')
    start = time.time()
    
    scene.camera = cam
    scene.render.filepath = output_path
    
    try:
        bpy.ops.render.render(write_still=True)
        elapsed = time.time() - start
        
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f'[v22] ✓ {cam_name}: {size/1024:.0f}KB in {elapsed:.1f}s')
            render_results.append({
                'camera': cam_name,
                'path': output_path,
                'size_kb': size / 1024,
                'time_s': elapsed,
                'success': True
            })
        else:
            print(f'[v22] ✗ {cam_name}: File not created!')
            render_results.append({
                'camera': cam_name,
                'success': False,
                'error': 'file_not_created'
            })
    except Exception as e:
        elapsed = time.time() - start
        print(f'[v22] ✗ {cam_name}: Error: {e} ({elapsed:.1f}s)')
        render_results.append({
            'camera': cam_name,
            'success': False,
            'error': str(e)
        })

# ─── Save modified .blend ───────────────────────────────────────────────────
blend_path = os.path.join(
    '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders',
    f'v22_scene{scene_num}.blend'
)
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f'[v22] Saved blend: {blend_path}')

# ─── Summary ────────────────────────────────────────────────────────────────
success_count = sum(1 for r in render_results if r.get('success'))
total = len(render_results)
print(f'\n[v22] Scene {scene_num} complete: {success_count}/{total} cameras rendered')
for r in render_results:
    status = '✓' if r.get('success') else '✗'
    extra = f" ({r.get('size_kb', 0):.0f}KB, {r.get('time_s', 0):.1f}s)" if r.get('success') else f" ({r.get('error', 'unknown')})"
    print(f'  {status} {r["camera"]}{extra}')
