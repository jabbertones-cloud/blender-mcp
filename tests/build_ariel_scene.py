"""Build a portfolio-quality forensic crash scene from scratch for Ariel."""
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

def step(name, cmd):
    print(f"  [{name}]...", end=" ", flush=True)
    r = send_cmd(cmd)
    if isinstance(r, dict) and r.get('error'):
        print(f"ERROR: {r['error'][:100]}")
    else:
        print("OK")
    return r

print("=" * 60)
print("  BUILDING FORENSIC SCENE FOR ARIEL")
print("=" * 60)

# 1. Clear everything
step("clear_all", {'command': 'execute_python', 'params': {'code':
    'import bpy\n'
    'for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\n'
    'for c in list(bpy.data.collections): bpy.data.collections.remove(c)\n'
    'for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)\n'
    'for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)\n'
    'for img in list(bpy.data.images): bpy.data.images.remove(img)\n'
    'print("SCENE_CLEARED")'
}})
time.sleep(0.5)

# 2. Build a T-intersection (classic crash scenario)
print("\n--- ROAD INFRASTRUCTURE ---")
step("intersection", {'command': 'forensic_scene', 'params': {
    'action': 'add_scene_template', 'template': 't_intersection'
}})

# 3. Place Vehicle 1: Red sedan — ran the stop sign, front-right severe damage
print("\n--- VEHICLES ---")
step("sedan_v1", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'sedan',
    'location': [-3, 3, 0],
    'rotation': 30,
    'color': [0.72, 0.04, 0.04],
    'label': 'Vehicle 1',
    'damage': {'side': 'front_right', 'severity': 'severe'}
}})

# 4. Place Vehicle 2: Silver SUV — had right of way, left-side moderate damage
step("suv_v2", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'suv',
    'location': [4, -2.5, 0],
    'rotation': 280,
    'color': [0.6, 0.62, 0.65],
    'label': 'Vehicle 2',
    'damage': {'side': 'left', 'severity': 'moderate'}
}})

# 5. Place Vehicle 3: Parked pickup (context vehicle, no damage)
step("pickup_parked", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle',
    'vehicle_type': 'pickup',
    'location': [18, 5.5, 0],
    'rotation': 90,
    'color': [0.15, 0.25, 0.4]
}})

# 6. Figures
print("\n--- FIGURES ---")
step("driver1", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure',
    'location': [-6, 5, 0],
    'pose': 'standing',
    'height': 1.78,
    'shirt_color': [0.6, 0.1, 0.1],
    'pants_color': [0.15, 0.15, 0.2]
}})

step("driver2", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure',
    'location': [7, -4, 0],
    'pose': 'standing',
    'height': 1.65,
    'shirt_color': [0.2, 0.3, 0.6],
    'pants_color': [0.1, 0.1, 0.12]
}})

step("witness_bystander", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure',
    'location': [14, 10, 0],
    'pose': 'standing',
    'height': 1.70,
    'shirt_color': [0.9, 0.85, 0.3],
    'pants_color': [0.3, 0.3, 0.32]
}})

# 7. Evidence markers
print("\n--- EVIDENCE ---")

# Skid marks from sedan approaching
step("skid_sedan", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'skid_mark',
    'location': [-18, -1, 0],
    'end': [-3, 3, 0]
}})

# Debris at impact zone
step("debris_glass", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'debris',
    'location': [0, 1, 0],
    'material': 'glass'
}})

step("debris_metal", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'debris',
    'location': [1, -1, 0],
    'material': 'metal'
}})

# Fluid spills
step("coolant_spill", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'fluid_spill',
    'location': [-2, 2, 0],
    'spill_type': 'coolant'
}})

step("oil_spill", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'fluid_spill',
    'location': [1, 0, 0],
    'spill_type': 'oil'
}})

# Impact point
step("impact_marker", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker',
    'marker_type': 'impact_point',
    'location': [0, 1, 0]
}})

# 8. Annotations
print("\n--- ANNOTATIONS ---")
step("label_poi", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'label',
    'location': [0, 1, 3.5],
    'text': 'POINT OF IMPACT'
}})

step("label_v1", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'label',
    'location': [-3, 3, 3],
    'text': 'V1 - Final Rest'
}})

step("label_v2", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'label',
    'location': [4, -2.5, 3],
    'text': 'V2 - Final Rest'
}})

step("measurement_skid", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'measurement',
    'location': [-18, -1, 0.15],
    'end': [-3, 3, 0.15],
    'text': '16.2m skid'
}})

step("measurement_v_dist", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation',
    'annotation_type': 'measurement',
    'location': [-3, 3, 0.15],
    'end': [4, -2.5, 0.15],
    'text': '9.1m separation'
}})

# 9. Measurement grid
print("\n--- GRID + OVERLAY ---")
step("grid", {'command': 'forensic_scene', 'params': {
    'action': 'add_measurement_grid',
    'size': 50,
    'spacing': 5
}})

# 10. Exhibit overlay
step("exhibit", {'command': 'forensic_scene', 'params': {
    'action': 'add_exhibit_overlay',
    'case_number': 'Case No. 2026-CV-08834',
    'exhibit_id': 'Exhibit A — Collision Overview',
    'expert_name': 'Scott M., Accident Reconstruction Specialist',
    'firm_name': 'OpenClaw Forensic Analytics',
    'disclaimer': 'FOR DEMONSTRATIVE PURPOSES ONLY — NOT DRAWN TO SCALE',
    'show_scale_bar': True,
    'scale_bar_length': 10,
    'show_timestamp': True
}})

# 11. Lighting — daytime
print("\n--- ENVIRONMENT ---")
step("time_day", {'command': 'forensic_scene', 'params': {
    'action': 'set_time_of_day',
    'time': 'day'
}})

# 12. All cameras
step("cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras',
    'camera_type': 'all',
    'target': [0, 1, 0],
    'witness_location': [20, 16, 1.7]
}})

# 13. Courtroom render preset (presentation quality)
step("render_preset", {'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render',
    'preset': 'presentation'
}})

print("\n" + "=" * 60)
print("  SCENE BUILT — NOW RENDERING 4 VIEWS")
print("=" * 60)

renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"

for cam_name in ["Cam_BirdEye", "Cam_Witness", "Cam_Closeup", "Cam_Orbit"]:
    filepath = f"{renders_dir}/ariel_{cam_name.lower()}.png"
    code = f"""
import bpy
cam = bpy.data.objects.get("{cam_name}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{filepath}"
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.resolution_percentage = 100
    bpy.ops.render.render(write_still=True)
    print("RENDERED: {cam_name}")
else:
    print("CAMERA NOT FOUND: {cam_name}")
"""
    print(f"  [render {cam_name}]...", end=" ", flush=True)
    r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=60)
    if isinstance(r, dict) and r.get('error'):
        print(f"SKIP ({r['error'][:50]})")
    else:
        print("OK")

# 14. Save .blend file
print("\n  [saving .blend]...", end=" ", flush=True)
blend_path = f"{renders_dir}/ariel_forensic_scene.blend"
save_code = f"""
import bpy
bpy.ops.wm.save_as_mainfile(filepath="{blend_path}")
print("SAVED")
"""
r = send_cmd({'command': 'execute_python', 'params': {'code': save_code}}, timeout=30)
print("OK" if not (isinstance(r, dict) and r.get('error')) else f"ERROR: {r.get('error','')[:60]}")

print(f"\n{'=' * 60}")
print(f"  DONE! Files saved to: {renders_dir}/")
print(f"  - ariel_forensic_scene.blend")
print(f"  - ariel_cam_birdeye.png")
print(f"  - ariel_cam_witness.png")
print(f"  - ariel_cam_closeup.png (if camera exists)")
print(f"  - ariel_cam_orbit.png")
print(f"{'=' * 60}")
