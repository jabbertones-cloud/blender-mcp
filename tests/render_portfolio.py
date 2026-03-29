"""Render a portfolio-quality forensic scene with all new features."""
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
        print(f"ERROR: {r['error'][:80]}")
    else:
        print("OK")
    return r

print("=== BUILDING PORTFOLIO FORENSIC SCENE ===\n")

# 1. Clear scene
step("clear", {'command': 'execute_python', 'params': {'code': 'import bpy\nfor o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\nfor c in list(bpy.data.collections): bpy.data.collections.remove(c)'}})
time.sleep(0.5)

# 2. Build T-intersection template
step("template", {'command': 'forensic_scene', 'params': {'action': 'add_scene_template', 'template': 't_intersection'}})

# 3. Place vehicles with damage
step("vehicle_1_sedan", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'sedan',
    'location': [-4, 2.5, 0], 'rotation': 25,
    'color': [0.7, 0.05, 0.05],
    'damage': {'side': 'front_right', 'severity': 'severe'}
}})

step("vehicle_2_suv", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'suv',
    'location': [3, -3, 0], 'rotation': 285,
    'color': [0.15, 0.2, 0.55],
    'damage': {'side': 'left', 'severity': 'moderate'}
}})

# 4. Place figures
step("figure_witness", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure', 'pose': 'standing',
    'location': [10, 8, 0], 'height': 1.75
}})

step("figure_pedestrian", {'command': 'forensic_scene', 'params': {
    'action': 'place_figure', 'pose': 'walking',
    'location': [6, -1, 0], 'height': 1.65,
    'shirt_color': [0.2, 0.5, 0.8], 'pants_color': [0.1, 0.1, 0.15]
}})

# 5. Skid marks
step("skid_marks", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'skid_mark',
    'location': [-15, 1, 0], 'end': [-4, 2.5, 0]
}})

# 6. Debris field
step("debris", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'debris',
    'location': [-1, 0, 0]
}})

# 7. Fluid spill
step("fluid_coolant", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'fluid_spill',
    'location': [-3, 2, 0], 'spill_type': 'coolant'
}})

# 8. Impact point marker
step("impact_point", {'command': 'forensic_scene', 'params': {
    'action': 'add_impact_marker', 'marker_type': 'impact_point',
    'location': [-1, 0, 0]
}})

# 9. Annotations
step("label_poi", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation', 'annotation_type': 'label',
    'location': [-1, 0, 3], 'text': 'Point of Impact'
}})

step("measurement", {'command': 'forensic_scene', 'params': {
    'action': 'add_annotation', 'annotation_type': 'measurement',
    'location': [-15, 1, 0.1], 'end': [-4, 2.5, 0.1], 'text': '12.3m skid'
}})

# 10. Measurement grid
step("grid", {'command': 'forensic_scene', 'params': {
    'action': 'add_measurement_grid', 'size': 40, 'spacing': 5
}})

# 11. Exhibit overlay
step("exhibit", {'command': 'forensic_scene', 'params': {
    'action': 'add_exhibit_overlay',
    'case_number': 'Case No. 2026-CV-04521',
    'exhibit_id': 'Exhibit A — Collision Overview',
    'expert_name': 'Scott M., Forensic Reconstruction Specialist',
    'firm_name': 'OpenClaw Analytics',
    'show_scale_bar': True,
    'show_timestamp': True,
    'scale_bar_length': 10
}})

# 12. Time of day
step("time_day", {'command': 'forensic_scene', 'params': {
    'action': 'set_time_of_day', 'time': 'day'
}})

# 13. Setup cameras (all types)
step("cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras', 'camera_type': 'all',
    'target': [-1, 0, 0],
    'witness_location': [18, 15, 1.7]
}})

# 14. Courtroom render preset
step("render_preset", {'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render', 'preset': 'presentation'
}})

print("\n=== SCENE BUILT — RENDERING ===\n")

# Render from multiple cameras
renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"

for cam_name in ["Cam_BirdEye", "Cam_Witness", "Cam_Closeup", "Cam_Orbit"]:
    filepath = f"{renders_dir}/portfolio_{cam_name.lower()}.png"
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
    print(f"  [render_{cam_name}]...", end=" ", flush=True)
    r = send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=60)
    print("OK" if not r.get('error') else f"ERROR: {r.get('error','')[:60]}")

print(f"\n=== RENDERS SAVED to {renders_dir}/ ===")
print("  portfolio_cam_birdeye.png")
print("  portfolio_cam_witness.png")
print("  portfolio_cam_closeup.png")
print("  portfolio_cam_orbit.png")
print("\nDONE!")
