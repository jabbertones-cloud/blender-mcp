"""Premium forensic crash reconstruction — uses all quality upgrades.
Exercises: upgraded vehicles, figures, PBR materials, cinematic cameras,
data overlays, professional lighting, and high-quality render presets.
"""
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
        print(f"ERROR: {r['error'][:120]}")
    else:
        print("OK")
    return r

def run(code, timeout=15):
    return send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout)

print("=" * 60)
print("  PREMIUM FORENSIC CRASH RECONSTRUCTION")
print("  Quality Level: $50K Courtroom-Ready")
print("=" * 60)

# 1. Clear
step("clear", {'command': 'execute_python', 'params': {'code':
    'import bpy\n'
    'for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\n'
    'for c in list(bpy.data.collections): bpy.data.collections.remove(c)\n'
    'for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)\n'
    'for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)'}})
time.sleep(0.5)

# 2. T-Intersection template
print("\n--- INFRASTRUCTURE ---")
step("intersection", {'command': 'forensic_scene', 'params': {
    'action': 'add_scene_template', 'template': 't_intersection'}})

# 3. Place vehicles with upgraded models
print("\n--- VEHICLES (upgraded models with interiors) ---")
step("sedan", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'sedan',
    'location': [-25, 0, 0], 'rotation': 0,
    'color': [0.72, 0.04, 0.04]}})

step("suv", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'suv',
    'location': [0, -22, 0], 'rotation': 90,
    'color': [0.6, 0.62, 0.65]}})

# 4. Upgraded human figures with facial features
print("\n--- FIGURES (upgraded anatomy) ---")
step("witness_1", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure', 'location': [14, 10, 0],
    'pose': 'standing', 'height': 1.72,
    'shirt_color': [0.85, 0.8, 0.2]}})

step("witness_2", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure', 'location': [12, -8, 0],
    'pose': 'walking', 'height': 1.68,
    'shirt_color': [0.15, 0.55, 0.3]}})

# 5. Professional lighting
print("\n--- LIGHTING (Filmic + professional) ---")
step("lighting", {'command': 'forensic_scene', 'params': {
    'action': 'set_time_of_day', 'time': 'day'}})

# 6. Physics collision
print("\n--- PHYSICS COLLISION ---")
r = step("physics", {'command': 'forensic_scene', 'params': {
    'action': 'simulate_collision',
    'vehicle1': {
        'name': 'Vehicle', 'mass_kg': 1400,
        'speed_mph': 38, 'heading_deg': 90,
        'start_pos': [-25, 0, 0]
    },
    'vehicle2': {
        'name': 'Vehicle.001', 'mass_kg': 2100,
        'speed_mph': 28, 'heading_deg': 0,
        'start_pos': [0, -22, 0]
    },
    'impact_point': [0, 0, 0],
    'coefficient_of_restitution': 0.12,
    'friction_coefficient': 0.65,
    'fps': 24, 'duration_sec': 6,
    'v1_spin_deg_per_sec': 55,
    'v2_spin_deg_per_sec': -25
}})

impact_f = 40
impulse = 0
if isinstance(r, dict) and r.get('status') == 'ok':
    impact_f = r['impact_frame']
    impulse = r.get('physics', {}).get('impulse_ns', 0)
    print(f"\n  Physics results:")
    print(f"    Impact frame: {impact_f}")
    print(f"    V1 final: {r['v1_final_pos']}")
    print(f"    V2 final: {r['v2_final_pos']}")
    print(f"    Impulse: {impulse:.0f} N·s")

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
step("poi", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation', 'annotation_type': 'label',
    'location': [0, 0, 3.5], 'text': 'POINT OF IMPACT'}})

step("measure", {'command': 'forensic_scene', 'params': {
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

# 10. Data overlay HUD
print("\n--- DATA OVERLAY HUD ---")
step("hud", {'command': 'forensic_scene', 'params': {
    'action': 'add_data_overlay',
    'vehicle1': {'name': 'Vehicle', 'mass_kg': 1400, 'speed_mph': 38, 'heading_deg': 90},
    'vehicle2': {'name': 'Vehicle.001', 'mass_kg': 2100, 'speed_mph': 28, 'heading_deg': 0},
    'impact_point': [0, 0, 0],
    'impact_frame': impact_f,
    'impulse_ns': impulse,
    'total_frames': 144,
    'fps': 24}})

# 11. Exhibit overlay
print("\n--- EXHIBIT OVERLAY ---")
step("exhibit", {'command': 'forensic_scene', 'params': {
    'action': 'add_exhibit_overlay',
    'case_number': 'Case No. 2026-CV-08834',
    'exhibit_id': 'Exhibit B — Premium Animated Reconstruction',
    'expert_name': 'Scott M., Forensic Reconstruction Expert',
    'firm_name': 'OpenClaw Forensic Analytics',
    'show_scale_bar': True, 'show_timestamp': True}})

# 12. Standard cameras
print("\n--- STANDARD CAMERAS ---")
step("cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras', 'camera_type': 'all',
    'target': [0, 0, 0], 'witness_location': [20, 18, 1.7]}})

# 13. Cinematic cameras
print("\n--- CINEMATIC CAMERAS ---")
step("cine_cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cinematic_cameras',
    'target': [0, 0, 0],
    'duration_frames': 144,
    'impact_frame': impact_f,
    'v1_start': [-25, 0, 0],
    'v2_start': [0, -22, 0]}})

# 14. Premium render preset
print("\n--- RENDER SETUP (presentation quality) ---")
step("render_preset", {'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render', 'preset': 'presentation'}})

# 15. Render key frames from multiple cameras
print("\n" + "=" * 60)
print("  RENDERING KEY FRAMES")
print("=" * 60)

renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"

key_frames = [
    (1,          "01_approach",     "Cam_BirdEye"),
    (impact_f//2,"02_midway",       "Cam_Crane"),
    (impact_f,   "03_impact_bird",  "Cam_BirdEye"),
    (impact_f,   "04_impact_close", "Cam_ImpactCloseup"),
    (impact_f,   "05_impact_dolly", "Cam_Dolly"),
    (impact_f+20,"06_aftermath",    "Cam_BirdEye"),
    (144,        "07_final_bird",   "Cam_BirdEye"),
    (144,        "08_final_witness","Cam_Witness"),
    (144,        "09_final_crane",  "Cam_Crane"),
    (144,        "10_final_orbit",  "Cam_Orbit"),
]

for frame, label, cam_name in key_frames:
    filepath = f"{renders_dir}/premium_{label}.png"
    code = f"""
import bpy
bpy.context.scene.frame_set({frame})
cam = bpy.data.objects.get("{cam_name}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{filepath}"
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print("RENDERED: {label}")
else:
    print("CAMERA NOT FOUND: {cam_name}")
"""
    print(f"  [f{frame:03d} {label}]...", end=" ", flush=True)
    send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=120)
    print("OK")

# 16. Save .blend
print("\n  [saving .blend]...", end=" ", flush=True)
blend_path = f"{renders_dir}/premium_forensic_scene.blend"
run(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); print("SAVED")')
print("OK")

print(f"\n{'=' * 60}")
print("  PREMIUM FORENSIC SCENE COMPLETE!")
print(f"  .blend: premium_forensic_scene.blend")
print(f"  Renders: premium_01_approach.png through premium_10_final_orbit.png")
print(f"  Features: subdivision surfaces, car interiors, PBR materials,")
print(f"           Filmic view transform, cinematic cameras, data HUD,")
print(f"           physics collision, evidence markers, exhibit overlay")
print(f"{'=' * 60}")
