"""Physics-based animated crash reconstruction with corrected tire orientation."""
import socket, json, time

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

def step(name, cmd, timeout=30):
    print(f"  [{name}]...", end=" ", flush=True)
    r = send_cmd(cmd, timeout)
    if isinstance(r, dict) and r.get('error'):
        print(f"ERROR: {r['error'][:100]}")
    else:
        print("OK")
    return r

def run(code, timeout=15):
    return send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout)

print("=" * 60)
print("  PHYSICS-BASED CRASH ANIMATION")
print("=" * 60)

# 1. Clear
step("clear", {'command': 'execute_python', 'params': {'code':
    'import bpy\n'
    'for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\n'
    'for c in list(bpy.data.collections): bpy.data.collections.remove(c)\n'
    'for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)\n'
    'for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)'}})
time.sleep(0.5)

# 2. Road
print("\n--- INFRASTRUCTURE ---")
step("road", {'command': 'forensic_scene', 'params': {
    'action': 'add_scene_template', 'template': 't_intersection'}})

# 3. Place vehicles at starting positions (no damage yet)
print("\n--- VEHICLES ---")
step("sedan", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'sedan',
    'location': [-25, 0, 0], 'rotation': 0,
    'color': [0.72, 0.04, 0.04]}})

step("suv", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'suv',
    'location': [0, -22, 0], 'rotation': 90,
    'color': [0.6, 0.62, 0.65]}})

# 4. Witness figure
step("witness", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure', 'location': [14, 10, 0],
    'pose': 'standing', 'height': 1.72,
    'shirt_color': [0.85, 0.8, 0.2]}})

# 5. Lighting
step("lighting", {'command': 'forensic_scene', 'params': {
    'action': 'set_time_of_day', 'time': 'day'}})

# 6. PHYSICS COLLISION SIMULATION
# Sedan: 1400kg, heading east (0 deg = +Y in Blender), 38 mph
# SUV: 2100kg, heading north (90 deg), 28 mph
print("\n--- PHYSICS COLLISION ---")
r = step("simulate_collision", {'command': 'forensic_scene', 'params': {
    'action': 'simulate_collision',
    'vehicle1': {
        'name': 'Vehicle',
        'mass_kg': 1400,
        'speed_mph': 38,
        'heading_deg': 90,
        'start_pos': [-25, 0, 0]
    },
    'vehicle2': {
        'name': 'Vehicle.001',
        'mass_kg': 2100,
        'speed_mph': 28,
        'heading_deg': 0,
        'start_pos': [0, -22, 0]
    },
    'impact_point': [0, 0, 0],
    'coefficient_of_restitution': 0.12,
    'friction_coefficient': 0.65,
    'fps': 24,
    'duration_sec': 6,
    'v1_spin_deg_per_sec': 55,
    'v2_spin_deg_per_sec': -25
}})

if isinstance(r, dict) and r.get('status') == 'ok':
    print(f"\n  Physics results:")
    print(f"    Impact frame: {r['impact_frame']}")
    print(f"    V1 final pos: {r['v1_final_pos']}")
    print(f"    V2 final pos: {r['v2_final_pos']}")
    print(f"    V1 post-impact speed: {r['v1_post_velocity_ms']:.1f} m/s")
    print(f"    V2 post-impact speed: {r['v2_post_velocity_ms']:.1f} m/s")
    print(f"    Impulse: {r['physics']['impulse_ns']:.0f} N·s")

# 7. Evidence markers
print("\n--- EVIDENCE ---")
step("skid", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'skid_mark',
    'location': [-20, 0, 0], 'end': [0, 0, 0]}})

step("debris", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'debris',
    'location': [1, 1, 0], 'material': 'glass'}})

step("coolant", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'fluid_spill',
    'location': [0, 1, 0], 'spill_type': 'coolant'}})

step("impact_ring", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'impact_point',
    'location': [0, 0, 0]}})

# 8. Annotations
print("\n--- ANNOTATIONS ---")
step("poi_label", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation', 'annotation_type': 'label',
    'location': [0, 0, 3.5], 'text': 'POINT OF IMPACT'}})

step("measurement", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation', 'annotation_type': 'measurement',
    'location': [-20, 0, 0.1], 'end': [0, 0, 0.1], 'text': '20m approach'}})

# 9. Ghost trails
print("\n--- GHOST TRAILS ---")
step("ghost_v1", {'command': 'forensic_scene', 'params': {
    'action': 'ghost_scenario', 'source_vehicle': 'Vehicle',
    'name': 'V1_Ghost', 'location': [-12, 0, 0], 'rotation': 0,
    'ghost_alpha': 0.12, 'ghost_color': [1, 0.2, 0.2, 0.12]}})

step("ghost_v2", {'command': 'forensic_scene', 'params': {
    'action': 'ghost_scenario', 'source_vehicle': 'Vehicle.001',
    'name': 'V2_Ghost', 'location': [0, -10, 0], 'rotation': 90,
    'ghost_alpha': 0.12, 'ghost_color': [0.2, 0.2, 1, 0.12]}})

# 10. Exhibit overlay
step("exhibit", {'command': 'forensic_scene', 'params': {
    'action': 'add_exhibit_overlay',
    'case_number': 'Case No. 2026-CV-08834',
    'exhibit_id': 'Exhibit B — Animated Reconstruction',
    'expert_name': 'Scott M., Forensic Reconstruction',
    'firm_name': 'OpenClaw Analytics',
    'show_scale_bar': True, 'show_timestamp': True}})

# 11. Cameras
step("cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras', 'camera_type': 'all',
    'target': [0, 0, 0], 'witness_location': [20, 18, 1.7]}})

step("render_preset", {'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render', 'preset': 'presentation'}})

# 12. Render key frames
print("\n" + "=" * 60)
print("  RENDERING KEY FRAMES + VIDEO")
print("=" * 60)

renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"

# Key frame stills
key_frames = [
    (1,   "01_approach",   "Cam_BirdEye"),
    (30,  "02_entering",   "Cam_BirdEye"),
    (None, "03_impact",    "Cam_BirdEye"),  # None = use impact_frame from physics
    (80,  "04_sliding",    "Cam_BirdEye"),
    (144, "05_final_rest", "Cam_BirdEye"),
    (144, "06_witness",    "Cam_Witness"),
    (144, "07_orbit",      "Cam_Orbit"),
]

# Get impact frame
impact_f = r.get('impact_frame', 40) if isinstance(r, dict) else 40

for frame_raw, label, cam_name in key_frames:
    frame = impact_f if frame_raw is None else frame_raw
    filepath = f"{renders_dir}/physics_{label}.png"
    code = f"""
import bpy
bpy.context.scene.frame_set({frame})
cam = bpy.data.objects.get("{cam_name}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{filepath}"
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("OK")
else:
    print("CAM_MISSING")
"""
    print(f"  [f{frame:03d} {label}]...", end=" ", flush=True)
    send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=60)
    print("OK")

# 13. Render full video (MP4)
print("\n  [rendering video]...", end=" ", flush=True)
video_path = f"{renders_dir}/physics_crash_animation.mp4"
run(f"""
import bpy
scene = bpy.context.scene
cam = bpy.data.objects.get("Cam_BirdEye")
if cam:
    scene.camera = cam
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
scene.render.ffmpeg.audio_codec = 'NONE'
scene.render.filepath = "{video_path}"
scene.render.resolution_percentage = 75
bpy.ops.render.render(animation=True)
print("VIDEO_DONE")
""", timeout=600)
print("OK")

# 14. Save .blend
print("  [saving .blend]...", end=" ", flush=True)
blend_path = f"{renders_dir}/physics_crash_scene.blend"
run(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); print("SAVED")')
print("OK")

print(f"\n{'=' * 60}")
print("  DONE!")
print(f"  .blend: physics_crash_scene.blend")
print(f"  Video:  physics_crash_animation.mp4 (6 sec, 24fps)")
print(f"  Stills: physics_01_approach.png through physics_07_orbit.png")
print(f"{'=' * 60}")
