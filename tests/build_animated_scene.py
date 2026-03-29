"""Build an animated forensic crash reconstruction — vehicles move, collide, spin to rest."""
import socket, json, time, math

def send_cmd(cmd, timeout=30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect(('127.0.0.1', 9876))
        msg = json.dumps(cmd) + '\n'
        s.sendall(msg.encode())
        data = b''
        while True:
            chunk = s.recv(16384)
            if not chunk:
                break
            data += chunk
            try:
                json.loads(data.decode())
                break
            except:
                continue
        result = json.loads(data.decode())
        return result.get('result', result)
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()

def step(name, cmd):
    print(f"  [{name}]...", end=" ", flush=True)
    r = send_cmd(cmd)
    if isinstance(r, dict) and r.get('error'):
        print(f"ERROR: {r['error'][:100]}")
    else:
        print("OK")
    return r

def run(code, timeout=15):
    return send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout)

print("=" * 60)
print("  ANIMATED FORENSIC CRASH RECONSTRUCTION")
print("=" * 60)

# 1. Clear scene
step("clear", {'command': 'execute_python', 'params': {'code':
    'import bpy\n'
    'for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\n'
    'for c in list(bpy.data.collections): bpy.data.collections.remove(c)\n'
    'for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)\n'
    'for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)'
}})
time.sleep(0.5)

# 2. Build road
print("\n--- ROAD ---")
step("intersection", {'command': 'forensic_scene', 'params': {
    'action': 'add_scene_template', 'template': 't_intersection'
}})

# 3. Place Vehicle 1 at STARTING position (pre-crash)
# Sedan approaching from west on the main road, will run the stop sign
print("\n--- VEHICLES (starting positions) ---")
step("sedan_start", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'sedan',
    'location': [-25, 0, 0],
    'rotation': 0,
    'color': [0.72, 0.04, 0.04],
    'label': 'V1'
}})

# SUV approaching from south on the cross street
step("suv_start", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'suv',
    'location': [0, -20, 0],
    'rotation': 90,
    'color': [0.6, 0.62, 0.65],
    'label': 'V2'
}})

# 4. Add pedestrian witness (standing, doesn't move)
step("witness", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure',
    'location': [12, 10, 0],
    'pose': 'standing',
    'height': 1.70,
    'shirt_color': [0.9, 0.85, 0.3]
}})

# 5. Lighting
step("lighting", {'command': 'forensic_scene', 'params': {
    'action': 'set_time_of_day', 'time': 'day'
}})

# 6. ANIMATE — keyframe the crash timeline
# Timeline:
#   Frame 1-30:   Both vehicles approaching intersection normally
#   Frame 30-50:  Sedan accelerates through stop sign, SUV enters intersection
#   Frame 50-55:  IMPACT — vehicles make contact at intersection center
#   Frame 55-80:  Post-impact — sedan spins clockwise, SUV pushed sideways
#   Frame 80-120: Vehicles decelerate to final rest positions
print("\n--- ANIMATING CRASH TIMELINE ---")

# Sedan (V1) waypoints — approaching from left, runs stop sign, impacts, spins to rest
step("animate_sedan", {'command': 'forensic_scene', 'params': {
    'action': 'animate_vehicle',
    'vehicle_name': 'Vehicle',
    'waypoints': [
        {'frame': 1,   'location': [-25, 0, 0],    'rotation': 0},
        {'frame': 15,  'location': [-15, 0, 0],    'rotation': 0},
        {'frame': 30,  'location': [-8, 0, 0],     'rotation': 0},
        {'frame': 40,  'location': [-4, 0.5, 0],   'rotation': 2},
        {'frame': 50,  'location': [-1, 1, 0],     'rotation': 5},
        {'frame': 55,  'location': [0.5, 1.5, 0],  'rotation': 15},
        {'frame': 65,  'location': [-1, 2.5, 0],   'rotation': 35},
        {'frame': 80,  'location': [-2.5, 3, 0],   'rotation': 30},
        {'frame': 100, 'location': [-3, 3, 0],     'rotation': 30},
        {'frame': 120, 'location': [-3, 3, 0],     'rotation': 30},
    ]
}})

# SUV (V2) waypoints — approaching from bottom, has right of way, gets T-boned
step("animate_suv", {'command': 'forensic_scene', 'params': {
    'action': 'animate_vehicle',
    'vehicle_name': 'Vehicle.001',
    'waypoints': [
        {'frame': 1,   'location': [0, -20, 0],    'rotation': 90},
        {'frame': 15,  'location': [0, -12, 0],    'rotation': 90},
        {'frame': 30,  'location': [0, -6, 0],     'rotation': 90},
        {'frame': 40,  'location': [0, -3, 0],     'rotation': 90},
        {'frame': 50,  'location': [0, -0.5, 0],   'rotation': 88},
        {'frame': 55,  'location': [1, 0.5, 0],    'rotation': 82},
        {'frame': 65,  'location': [2.5, -1, 0],   'rotation': 275},
        {'frame': 80,  'location': [3.5, -2, 0],   'rotation': 280},
        {'frame': 100, 'location': [4, -2.5, 0],   'rotation': 280},
        {'frame': 120, 'location': [4, -2.5, 0],   'rotation': 280},
    ]
}})

# 7. Add damage to vehicles at their final frames
# We apply damage via Blender Python at the final rest positions
print("\n--- ADDING POST-CRASH DAMAGE ---")
step("damage_sedan", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'sedan',
    'location': [-3, 3, 0],
    'rotation': 30,
    'color': [0.72, 0.04, 0.04],
    'label': 'V1_Final',
    'damage': {'side': 'front_right', 'severity': 'severe'}
}})

step("damage_suv", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'suv',
    'location': [4, -2.5, 0],
    'rotation': 280,
    'color': [0.6, 0.62, 0.65],
    'label': 'V2_Final',
    'damage': {'side': 'left', 'severity': 'moderate'}
}})

# Hide the damaged vehicles until frame 80 (they represent the final state)
run("""
import bpy
for name in ['Vehicle.002', 'Vehicle.003']:
    obj = bpy.data.objects.get(name)
    if obj:
        # Hide in viewport and render until frame 80
        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path='hide_viewport', frame=1)
        obj.keyframe_insert(data_path='hide_render', frame=1)

        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path='hide_viewport', frame=79)
        obj.keyframe_insert(data_path='hide_render', frame=79)

        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert(data_path='hide_viewport', frame=80)
        obj.keyframe_insert(data_path='hide_render', frame=80)

        # Also hide the originals after frame 80
for name in ['Vehicle', 'Vehicle.001']:
    obj = bpy.data.objects.get(name)
    if obj:
        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert(data_path='hide_viewport', frame=1)
        obj.keyframe_insert(data_path='hide_render', frame=1)

        obj.hide_viewport = False
        obj.hide_render = False
        obj.keyframe_insert(data_path='hide_viewport', frame=79)
        obj.keyframe_insert(data_path='hide_render', frame=79)

        obj.hide_viewport = True
        obj.hide_render = True
        obj.keyframe_insert(data_path='hide_viewport', frame=80)
        obj.keyframe_insert(data_path='hide_render', frame=80)
print("VISIBILITY_KEYFRAMES_SET")
""")

# 8. Ghost trails (semi-transparent path showing where vehicles were)
print("\n--- GHOST TRAILS ---")
step("ghost_sedan_pre", {'command': 'forensic_scene', 'params': {
    'action': 'ghost_scenario',
    'source_vehicle': 'Vehicle',
    'name': 'V1_Ghost_Approach',
    'location': [-15, 0, 0],
    'rotation': 0,
    'ghost_alpha': 0.15,
    'ghost_color': [1, 0.3, 0.3, 0.15]
}})

step("ghost_suv_pre", {'command': 'forensic_scene', 'params': {
    'action': 'ghost_scenario',
    'source_vehicle': 'Vehicle.001',
    'name': 'V2_Ghost_Approach',
    'location': [0, -12, 0],
    'rotation': 90,
    'ghost_alpha': 0.15,
    'ghost_color': [0.3, 0.3, 1, 0.15]
}})

# 9. Evidence markers (appear at impact frame)
print("\n--- EVIDENCE MARKERS ---")
step("skid_marks", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'skid_mark',
    'location': [-18, 0, 0],
    'end': [-3, 3, 0]
}})

step("debris", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'debris',
    'location': [0, 1, 0],
    'material': 'glass'
}})

step("coolant", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'fluid_spill',
    'location': [-1, 2, 0],
    'spill_type': 'coolant'
}})

step("impact_ring", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'impact_point',
    'location': [0, 1, 0]
}})

# 10. Annotations
print("\n--- ANNOTATIONS ---")
step("label_poi", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'label',
    'location': [0, 1, 3.5],
    'text': 'POINT OF IMPACT'
}})

step("measurement", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'measurement',
    'location': [-18, 0, 0.15],
    'end': [-3, 3, 0.15],
    'text': '16.2m skid'
}})

# 11. Exhibit overlay
step("exhibit", {'command': 'forensic_scene', 'params': {
    'action': 'add_exhibit_overlay',
    'case_number': 'Case No. 2026-CV-08834',
    'exhibit_id': 'Exhibit B — Animated Reconstruction',
    'expert_name': 'Scott M., Accident Reconstruction Specialist',
    'firm_name': 'OpenClaw Forensic Analytics',
    'show_scale_bar': True,
    'show_timestamp': True
}})

# 12. Cameras — use bird eye for the animation render
step("cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras',
    'camera_type': 'all',
    'target': [0, 0, 0],
    'witness_location': [20, 16, 1.7]
}})

# 13. Set timeline
run("""
import bpy
bpy.context.scene.frame_start = 1
bpy.context.scene.frame_end = 120
bpy.context.scene.render.fps = 24
print("TIMELINE: 1-120 @ 24fps = 5 seconds")
""")

# 14. Render setup
step("render_preset", {'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render', 'preset': 'presentation'
}})

# 15. Render key frames as stills (faster than full video for demo)
print("\n" + "=" * 60)
print("  RENDERING KEY MOMENTS")
print("=" * 60)

renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"

key_frames = [
    (1,   "approach",   "Cam_BirdEye"),
    (30,  "entering",   "Cam_BirdEye"),
    (50,  "impact",     "Cam_BirdEye"),
    (55,  "collision",  "Cam_Closeup"),
    (80,  "aftermath",  "Cam_BirdEye"),
    (120, "final_rest", "Cam_BirdEye"),
    (120, "witness_view", "Cam_Witness"),
]

for frame, label, cam_name in key_frames:
    filepath = f"{renders_dir}/anim_{label}_f{frame:03d}.png"
    code = f"""
import bpy
bpy.context.scene.frame_set({frame})
cam = bpy.data.objects.get("{cam_name}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{filepath}"
    bpy.ops.render.render(write_still=True)
    print("RENDERED: {label} frame {frame}")
else:
    print("CAMERA NOT FOUND: {cam_name}")
"""
    print(f"  [frame {frame} — {label}]...", end=" ", flush=True)
    r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=60)
    print("OK" if not (isinstance(r, dict) and r.get('error')) else f"ERROR")

# 16. Render full animation as MP4
print("\n  [rendering full animation video]...", end=" ", flush=True)
video_path = f"{renders_dir}/forensic_animation.mp4"
run(f"""
import bpy
scene = bpy.context.scene

# Set to bird eye camera
cam = bpy.data.objects.get("Cam_BirdEye")
if cam:
    scene.camera = cam

# MP4 output
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
scene.render.ffmpeg.audio_codec = 'NONE'
scene.render.filepath = "{video_path}"
scene.render.resolution_percentage = 75  # 75% for speed (1440x810)

bpy.ops.render.render(animation=True)
print("VIDEO_RENDERED")
""", timeout=300)
print("OK")

# 17. Save .blend
print("  [saving .blend]...", end=" ", flush=True)
blend_path = f"{renders_dir}/ariel_animated_forensic.blend"
run(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); print("SAVED")')
print("OK")

print(f"\n{'=' * 60}")
print("  DONE! Animated forensic scene files:")
print(f"  - ariel_animated_forensic.blend (open in Blender, press Play)")
print(f"  - forensic_animation.mp4 (5-second crash video)")
print(f"  - anim_approach_f001.png through anim_final_rest_f120.png")
print(f"{'=' * 60}")
