#!/usr/bin/env python3
"""
Product Commercial Sequence Builder
=====================================
Creates multi-shot product commercial animations — the kind you see from
Apple, Samsung, Dyson, etc. Each "commercial" is a sequence of shots with
different camera angles, timings, and focal lengths, all rendered as one
continuous animation or as separate shot files.

Shot Types Available:
  - establishing: Wide static shot showing product in context
  - hero_turntable: Classic 360° rotation (full or partial)
  - hero_reveal: Dolly-in with zoom for dramatic entrance
  - detail_closeup: Macro detail with shallow DOF
  - feature_callout: Orbit to specific angle + hold for text overlay
  - lifestyle_context: Medium shot, product in environment
  - final_hero: Pull-back or spin to closing angle

Usage:
  python product_commercial_sequence.py --object MyProduct --preset apple_style
  python product_commercial_sequence.py --object MyProduct --preset ecommerce_quick
"""

import json
import socket
import sys
import argparse
import math
from typing import List, Dict, Any, Optional

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 9876
_counter = 0

def send(command: str, params: dict = None) -> dict:
    global _counter
    _counter += 1
    payload = {"id": str(_counter), "command": command, "params": params or {}}
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(120.0)
        sock.connect((BLENDER_HOST, BLENDER_PORT))
        sock.sendall(json.dumps(payload).encode("utf-8"))
        chunks = []
        while True:
            chunk = sock.recv(1048576)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
                sock.close()
                if data.get("error"):
                    return {"error": data["error"]}
                return data.get("result", data)
            except json.JSONDecodeError:
                continue
        sock.close()
        raw = b"".join(chunks).decode("utf-8")
        return json.loads(raw) if raw else {"error": "Empty response"}
    except ConnectionRefusedError:
        print("ERROR: Blender not running or bridge not enabled on port 9876")
        sys.exit(1)
    except Exception as e:
        return {"error": str(e)}

def run_python(code: str) -> dict:
    return send("execute_python", {"code": code})


# ═══════════════════════════════════════════════════════════════════════════════
# SHOT DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

def gen_shot_code(shot: dict, target: str, frame_start: int, fps: int = 24) -> str:
    """Generate Python code for a single shot within a sequence.
    
    Each shot creates its own camera and keyframes within its frame range.
    Uses NLA-style approach: each shot has frame_start..frame_end within the 
    global timeline.
    """
    style = shot.get("style", "hero_turntable")
    frames = shot.get("frames", 120)
    focal = shot.get("focal_length", 50)
    fstop = shot.get("f_stop", 2.8)
    distance = shot.get("distance", 4.0)
    height = shot.get("height", 1.2)
    angle = shot.get("angle", 0)  # starting angle in degrees
    orbit_degrees = shot.get("orbit_degrees", 360)
    hold_frames = shot.get("hold_frames", 0)  # extra hold at end
    
    frame_end = frame_start + frames - 1
    cam_name = f"Shot_{frame_start}_Camera"
    
    if style == "hero_turntable":
        return f"""
# === Shot: hero_turntable (frames {frame_start}-{frame_end}) ===
import bpy, math

target = bpy.data.objects.get("{target}")
tc = target.location.copy() if target else (0,0,0)

# Orbit empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=tc if hasattr(tc, 'x') else (0,0,0))
orbit = bpy.context.active_object
orbit.name = "Orbit_{frame_start}"

# Camera
cd = bpy.data.cameras.new("{cam_name}_Data")
cd.lens = {focal}
cd.dof.use_dof = True
if target: cd.dof.focus_object = target
cd.dof.aperture_fstop = {fstop}

co = bpy.data.objects.new("{cam_name}", cd)
bpy.context.collection.objects.link(co)
start_rad = math.radians({angle})
co.location = (tc.x + {distance} * math.cos(start_rad), tc.y + {distance} * math.sin(start_rad), tc.z + {height})
co.parent = orbit

tr = co.constraints.new('TRACK_TO')
if target: tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'

# Keyframe orbit
orbit.rotation_euler = (0, 0, 0)
orbit.keyframe_insert(data_path="rotation_euler", index=2, frame={frame_start})
orbit.rotation_euler = (0, 0, math.radians({orbit_degrees}))
orbit.keyframe_insert(data_path="rotation_euler", index=2, frame={frame_end})

if orbit.animation_data and orbit.animation_data.action:
    for fc in orbit.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'LINEAR'

# Bind camera to timeline via markers
bpy.context.scene.timeline_markers.new("{cam_name}", frame={frame_start})
bpy.context.scene.timeline_markers["{cam_name}"].camera = co
"""

    elif style == "hero_reveal":
        start_dist = shot.get("start_distance", 8.0)
        end_dist = shot.get("end_distance", 3.5)
        start_focal = shot.get("start_focal", 35)
        end_focal = shot.get("end_focal", 85)
        return f"""
# === Shot: hero_reveal (frames {frame_start}-{frame_end}) ===
import bpy, math

target = bpy.data.objects.get("{target}")
tc = target.location.copy() if target else (0,0,0)

cd = bpy.data.cameras.new("{cam_name}_Data")
cd.lens = {start_focal}
cd.dof.use_dof = True
if target: cd.dof.focus_object = target
cd.dof.aperture_fstop = {fstop}

co = bpy.data.objects.new("{cam_name}", cd)
bpy.context.collection.objects.link(co)

tr = co.constraints.new('TRACK_TO')
if target: tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'

# Start: far, wide
co.location = (tc.x + {start_dist}, tc.y, tc.z + 0.5)
co.keyframe_insert(data_path="location", frame={frame_start})
cd.lens = {start_focal}
cd.keyframe_insert(data_path="lens", frame={frame_start})

# End: close, tight
co.location = (tc.x + {end_dist}, tc.y + 0.8, tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_end})
cd.lens = {end_focal}
cd.keyframe_insert(data_path="lens", frame={frame_end})

for obj in [co]:
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'BEZIER'
                kf.easing = 'EASE_OUT'
if cd.animation_data and cd.animation_data.action:
    for fc in cd.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'BEZIER'
            kf.easing = 'EASE_OUT'

bpy.context.scene.timeline_markers.new("{cam_name}", frame={frame_start})
bpy.context.scene.timeline_markers["{cam_name}"].camera = co
"""

    elif style == "detail_closeup":
        return f"""
# === Shot: detail_closeup (frames {frame_start}-{frame_end}) ===
import bpy, math

target = bpy.data.objects.get("{target}")
tc = target.location.copy() if target else (0,0,0)

cd = bpy.data.cameras.new("{cam_name}_Data")
cd.lens = {focal}
cd.dof.use_dof = True
if target: cd.dof.focus_object = target
cd.dof.aperture_fstop = {max(fstop - 1, 1.0)}

co = bpy.data.objects.new("{cam_name}", cd)
bpy.context.collection.objects.link(co)

tr = co.constraints.new('TRACK_TO')
if target: tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'

start_rad = math.radians({angle})
# Start close, end slightly closer with slight orbit
co.location = (tc.x + {distance} * math.cos(start_rad), tc.y + {distance} * math.sin(start_rad), tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_start})

end_rad = math.radians({angle} + 15)  # subtle 15° drift
co.location = (tc.x + ({distance} * 0.85) * math.cos(end_rad), tc.y + ({distance} * 0.85) * math.sin(end_rad), tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_end})

if co.animation_data and co.animation_data.action:
    for fc in co.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'BEZIER'
            kf.easing = 'EASE_IN_OUT'

bpy.context.scene.timeline_markers.new("{cam_name}", frame={frame_start})
bpy.context.scene.timeline_markers["{cam_name}"].camera = co
"""

    elif style == "establishing":
        return f"""
# === Shot: establishing (frames {frame_start}-{frame_end}) ===
import bpy, math

target = bpy.data.objects.get("{target}")
tc = target.location.copy() if target else (0,0,0)

cd = bpy.data.cameras.new("{cam_name}_Data")
cd.lens = {focal}
cd.dof.use_dof = True
if target: cd.dof.focus_object = target
cd.dof.aperture_fstop = {fstop}

co = bpy.data.objects.new("{cam_name}", cd)
bpy.context.collection.objects.link(co)

tr = co.constraints.new('TRACK_TO')
if target: tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'

# Static or very slow drift
start_rad = math.radians({angle})
co.location = (tc.x + {distance} * math.cos(start_rad), tc.y + {distance} * math.sin(start_rad), tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_start})

# Micro drift (2-3° over entire hold)
end_rad = math.radians({angle} + 3)
co.location = (tc.x + {distance} * math.cos(end_rad), tc.y + {distance} * math.sin(end_rad), tc.z + {height} + 0.05)
co.keyframe_insert(data_path="location", frame={frame_end})

if co.animation_data and co.animation_data.action:
    for fc in co.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'BEZIER'
            kf.easing = 'EASE_IN_OUT'

bpy.context.scene.timeline_markers.new("{cam_name}", frame={frame_start})
bpy.context.scene.timeline_markers["{cam_name}"].camera = co
"""

    elif style == "feature_callout":
        return f"""
# === Shot: feature_callout (frames {frame_start}-{frame_end}) ===
import bpy, math

target = bpy.data.objects.get("{target}")
tc = target.location.copy() if target else (0,0,0)

cd = bpy.data.cameras.new("{cam_name}_Data")
cd.lens = {focal}
cd.dof.use_dof = True
if target: cd.dof.focus_object = target
cd.dof.aperture_fstop = {fstop}

co = bpy.data.objects.new("{cam_name}", cd)
bpy.context.collection.objects.link(co)

tr = co.constraints.new('TRACK_TO')
if target: tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'

# Quick orbit to angle, then hold
move_frames = min(60, frames // 2)
start_rad = math.radians({angle} - 30)
end_rad = math.radians({angle})

co.location = (tc.x + {distance} * math.cos(start_rad), tc.y + {distance} * math.sin(start_rad), tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_start})

co.location = (tc.x + {distance} * math.cos(end_rad), tc.y + {distance} * math.sin(end_rad), tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_start} + move_frames)
co.keyframe_insert(data_path="location", frame={frame_end})  # hold

if co.animation_data and co.animation_data.action:
    for fc in co.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'BEZIER'
            kf.easing = 'EASE_OUT'

bpy.context.scene.timeline_markers.new("{cam_name}", frame={frame_start})
bpy.context.scene.timeline_markers["{cam_name}"].camera = co
"""

    elif style == "final_hero":
        return f"""
# === Shot: final_hero (frames {frame_start}-{frame_end}) ===
import bpy, math

target = bpy.data.objects.get("{target}")
tc = target.location.copy() if target else (0,0,0)

cd = bpy.data.cameras.new("{cam_name}_Data")
cd.lens = {focal}
cd.dof.use_dof = True
if target: cd.dof.focus_object = target
cd.dof.aperture_fstop = {fstop}

co = bpy.data.objects.new("{cam_name}", cd)
bpy.context.collection.objects.link(co)

tr = co.constraints.new('TRACK_TO')
if target: tr.target = target
tr.track_axis = 'TRACK_NEGATIVE_Z'
tr.up_axis = 'UP_Y'

# Pull back: close → far, slight rise
start_rad = math.radians({angle})
co.location = (tc.x + {distance * 0.7} * math.cos(start_rad), tc.y + {distance * 0.7} * math.sin(start_rad), tc.z + {height})
co.keyframe_insert(data_path="location", frame={frame_start})

co.location = (tc.x + {distance * 1.2} * math.cos(start_rad), tc.y + {distance * 1.2} * math.sin(start_rad), tc.z + {height + 0.5})
co.keyframe_insert(data_path="location", frame={frame_end})

if co.animation_data and co.animation_data.action:
    for fc in co.animation_data.action.fcurves:
        for kf in fc.keyframe_points:
            kf.interpolation = 'BEZIER'
            kf.easing = 'EASE_IN'

bpy.context.scene.timeline_markers.new("{cam_name}", frame={frame_start})
bpy.context.scene.timeline_markers["{cam_name}"].camera = co
"""
    
    return f'__result__ = {{"error": "Unknown shot style: {style}"}}'


# ═══════════════════════════════════════════════════════════════════════════════
# COMMERCIAL PRESETS
# ═══════════════════════════════════════════════════════════════════════════════

COMMERCIAL_PRESETS = {
    "apple_style": {
        "description": "Apple-style product reveal: slow, deliberate, premium feel",
        "fps": 24,
        "shots": [
            {"style": "establishing", "frames": 72, "focal_length": 50, "f_stop": 4.0, "distance": 6.0, "height": 1.5, "angle": 30},
            {"style": "hero_reveal", "frames": 144, "f_stop": 2.0, "start_distance": 8, "end_distance": 3.5, "start_focal": 35, "end_focal": 85, "height": 1.2},
            {"style": "hero_turntable", "frames": 240, "focal_length": 50, "f_stop": 2.8, "distance": 4.0, "height": 1.2, "orbit_degrees": 360},
            {"style": "detail_closeup", "frames": 120, "focal_length": 100, "f_stop": 1.8, "distance": 2.0, "height": 0.8, "angle": 45},
            {"style": "detail_closeup", "frames": 120, "focal_length": 100, "f_stop": 1.8, "distance": 2.0, "height": 1.5, "angle": -60},
            {"style": "final_hero", "frames": 96, "focal_length": 50, "f_stop": 2.8, "distance": 4.0, "height": 1.2, "angle": 0},
        ],
    },
    "tech_product": {
        "description": "Electronics/tech product showcase: clean, sharp, modern",
        "fps": 30,
        "shots": [
            {"style": "hero_reveal", "frames": 90, "f_stop": 2.8, "start_distance": 6, "end_distance": 3, "start_focal": 35, "end_focal": 65, "height": 1.0},
            {"style": "hero_turntable", "frames": 150, "focal_length": 50, "f_stop": 4.0, "distance": 3.5, "height": 1.0, "orbit_degrees": 360},
            {"style": "feature_callout", "frames": 90, "focal_length": 85, "f_stop": 2.8, "distance": 2.5, "height": 0.5, "angle": 90},
            {"style": "feature_callout", "frames": 90, "focal_length": 85, "f_stop": 2.8, "distance": 2.5, "height": 1.5, "angle": -45},
            {"style": "detail_closeup", "frames": 75, "focal_length": 100, "f_stop": 2.0, "distance": 1.8, "height": 0.8, "angle": 30},
            {"style": "final_hero", "frames": 60, "focal_length": 50, "f_stop": 2.8, "distance": 4.0, "height": 1.2, "angle": 15},
        ],
    },
    "luxury_jewelry": {
        "description": "Jewelry/luxury item: slow, intimate, sparkle-focused",
        "fps": 24,
        "shots": [
            {"style": "establishing", "frames": 96, "focal_length": 85, "f_stop": 2.0, "distance": 3.0, "height": 1.0, "angle": 45},
            {"style": "hero_turntable", "frames": 360, "focal_length": 85, "f_stop": 2.0, "distance": 2.5, "height": 0.8, "orbit_degrees": 360},
            {"style": "detail_closeup", "frames": 144, "focal_length": 135, "f_stop": 1.4, "distance": 1.5, "height": 0.5, "angle": 0},
            {"style": "detail_closeup", "frames": 144, "focal_length": 135, "f_stop": 1.4, "distance": 1.5, "height": 1.0, "angle": 120},
            {"style": "final_hero", "frames": 96, "focal_length": 85, "f_stop": 2.0, "distance": 3.0, "height": 1.0, "angle": -30},
        ],
    },
    "ecommerce_quick": {
        "description": "Quick e-commerce product spin + 2 angles",
        "fps": 30,
        "shots": [
            {"style": "hero_turntable", "frames": 120, "focal_length": 50, "f_stop": 5.6, "distance": 3.5, "height": 1.0, "orbit_degrees": 360},
            {"style": "feature_callout", "frames": 60, "focal_length": 65, "f_stop": 4.0, "distance": 3.0, "height": 0.5, "angle": 45},
            {"style": "feature_callout", "frames": 60, "focal_length": 65, "f_stop": 4.0, "distance": 3.0, "height": 1.5, "angle": -30},
        ],
    },
    "cosmetics_beauty": {
        "description": "Beauty/cosmetics product: warm, soft, aspirational",
        "fps": 24,
        "shots": [
            {"style": "hero_reveal", "frames": 120, "f_stop": 2.0, "start_distance": 7, "end_distance": 3, "start_focal": 35, "end_focal": 75, "height": 1.0},
            {"style": "hero_turntable", "frames": 180, "focal_length": 65, "f_stop": 2.8, "distance": 3.5, "height": 1.0, "orbit_degrees": 270},
            {"style": "detail_closeup", "frames": 120, "focal_length": 100, "f_stop": 1.8, "distance": 2.0, "height": 0.6, "angle": 30},
            {"style": "establishing", "frames": 72, "focal_length": 50, "f_stop": 2.8, "distance": 5.0, "height": 1.5, "angle": -45},
            {"style": "final_hero", "frames": 72, "focal_length": 65, "f_stop": 2.0, "distance": 3.5, "height": 1.0, "angle": 0},
        ],
    },
    "social_media_short": {
        "description": "Fast 5-8 second reel for TikTok/Instagram",
        "fps": 30,
        "shots": [
            {"style": "hero_reveal", "frames": 45, "f_stop": 2.8, "start_distance": 5, "end_distance": 3, "start_focal": 35, "end_focal": 50, "height": 1.0},
            {"style": "hero_turntable", "frames": 90, "focal_length": 50, "f_stop": 2.8, "distance": 3.5, "height": 1.0, "orbit_degrees": 270},
            {"style": "detail_closeup", "frames": 45, "focal_length": 85, "f_stop": 2.0, "distance": 2.0, "height": 0.8, "angle": 45},
        ],
    },
}


def build_commercial(
    object_name: str,
    preset_name: str = "apple_style",
    custom_shots: List[Dict] = None,
    lighting_rig: str = "product_studio",
    quality: str = "balanced",
    resolution: str = "1080p",
    output_dir: str = "/tmp/product_commercial",
):
    """Build a full multi-shot commercial sequence."""
    
    preset = COMMERCIAL_PRESETS.get(preset_name, COMMERCIAL_PRESETS["apple_style"])
    shots = custom_shots or preset["shots"]
    fps = preset.get("fps", 24)
    
    print(f"═══ Building Commercial: {preset.get('description', preset_name)} ═══")
    print(f"    Object: {object_name}")
    print(f"    Shots: {len(shots)}")
    print(f"    FPS: {fps}")
    
    # 1. Clean scene of old shot cameras/orbits/markers
    clean_code = """
import bpy
# Remove old shot cameras and orbits
for obj in list(bpy.data.objects):
    if obj.name.startswith("Shot_") or obj.name.startswith("Orbit_") or obj.name.startswith("Detail_"):
        bpy.data.objects.remove(obj, do_unlink=True)
# Remove old timeline markers
for m in list(bpy.context.scene.timeline_markers):
    if m.name.startswith("Shot_"):
        bpy.context.scene.timeline_markers.remove(m)
__result__ = {"status": "ok", "cleaned": True}
"""
    print("  [1] Cleaning old shot elements...")
    run_python(clean_code)
    
    # 2. Set up lighting
    from product_animation_recipes import setup_lighting, configure_render, setup_compositor_product
    print(f"  [2] Setting up lighting: {lighting_rig}")
    setup_lighting(lighting_rig)
    
    # 3. Build each shot
    frame_cursor = 1
    shot_manifest = []
    
    for i, shot in enumerate(shots):
        frames = shot.get("frames", 120)
        print(f"  [3.{i+1}] Shot {i+1}/{len(shots)}: {shot['style']} ({frames} frames, {frame_cursor}-{frame_cursor+frames-1})")
        
        code = gen_shot_code(shot, object_name, frame_cursor, fps)
        result = run_python(code)
        
        shot_manifest.append({
            "index": i + 1,
            "style": shot["style"],
            "frame_start": frame_cursor,
            "frame_end": frame_cursor + frames - 1,
            "duration_sec": round(frames / fps, 2),
        })
        
        frame_cursor += frames
    
    total_frames = frame_cursor - 1
    total_duration = round(total_frames / fps, 2)
    
    # 4. Set frame range and set first camera as active
    setup_code = f"""
import bpy
scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = {total_frames}
scene.render.fps = {fps}

# Set first shot camera as active
for m in scene.timeline_markers:
    if m.camera:
        scene.camera = m.camera
        break

__result__ = {{"status": "ok", "total_frames": {total_frames}, "fps": {fps}}}
"""
    run_python(setup_code)
    
    # 5. Render settings
    print(f"  [4] Configuring render: {quality} @ {resolution}")
    configure_render(quality=quality, resolution=resolution, output_path=f"{output_dir}/frame_####")
    
    # 6. Compositor
    print(f"  [5] Setting up compositor")
    setup_compositor_product(bloom=True, vignette=True)
    
    print(f"\n═══ Commercial Built! ═══")
    print(f"    Total frames: {total_frames}")
    print(f"    Duration: {total_duration} seconds")
    print(f"    Shots: {len(shots)}")
    print(f"\n    Shot manifest:")
    for s in shot_manifest:
        print(f"      {s['index']}. {s['style']}: frames {s['frame_start']}-{s['frame_end']} ({s['duration_sec']}s)")
    print(f"\n    To render: blender_render(type='animation')")
    
    return {
        "status": "ok",
        "preset": preset_name,
        "total_frames": total_frames,
        "total_duration_sec": total_duration,
        "fps": fps,
        "shots": shot_manifest,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Product Commercial Sequence Builder")
    parser.add_argument("--object", required=True, help="Blender object name")
    parser.add_argument("--preset", default="apple_style", choices=COMMERCIAL_PRESETS.keys())
    parser.add_argument("--lighting", default="product_studio")
    parser.add_argument("--quality", default="balanced")
    parser.add_argument("--resolution", default="1080p")
    parser.add_argument("--output", default="/tmp/product_commercial")
    parser.add_argument("--render", action="store_true", help="Start rendering after build")
    args = parser.parse_args()
    
    # Add scripts dir to path for imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import os
    
    result = build_commercial(
        object_name=args.object,
        preset_name=args.preset,
        lighting_rig=args.lighting,
        quality=args.quality,
        resolution=args.resolution,
        output_dir=args.output,
    )
    
    print(json.dumps(result, indent=2))
    
    if args.render:
        print("\n═══ Starting render... ═══")
        send("render", {"type": "animation", "output_path": f"{args.output}/frame_####"})
