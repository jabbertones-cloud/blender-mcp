"""Clean physics crash — focus on verifying cars drive straight, not sideways."""
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

print("=" * 60)
print("  CLEAN PHYSICS CRASH TEST")
print("=" * 60)

# Clear
step("clear", {'command': 'execute_python', 'params': {'code':
    'import bpy\n'
    'for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\n'
    'for c in list(bpy.data.collections): bpy.data.collections.remove(c)\n'
    'for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)\n'
    'for mat in list(bpy.data.materials): bpy.data.materials.remove(mat)'}})
time.sleep(0.5)

# Simple straight road + cross road
step("road_ew", {'command': 'forensic_scene', 'params': {
    'action': 'build_road', 'type': 'straight',
    'start': [-40, 0, 0], 'end': [40, 0, 0], 'lanes': 2, 'width': 7}})

step("road_ns", {'command': 'forensic_scene', 'params': {
    'action': 'build_road', 'type': 'straight',
    'start': [0, -40, 0], 'end': [0, 40, 0], 'lanes': 2, 'width': 7}})

# Sedan starts west, drives east (+X direction) → heading 90°
step("sedan", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'sedan',
    'location': [-25, 0, 0], 'rotation': 0,
    'color': [0.8, 0.05, 0.05]}})

# SUV starts south, drives north (+Y direction) → heading 0°
step("suv", {'command': 'forensic_scene', 'params': {
    'action': 'place_vehicle', 'vehicle_type': 'suv',
    'location': [0, -25, 0], 'rotation': 90,
    'color': [0.15, 0.25, 0.6]}})

# Lighting
step("lighting", {'command': 'forensic_scene', 'params': {
    'action': 'set_time_of_day', 'time': 'day'}})

# Physics collision
# Sedan: heading 90° (east, +X), starts at [-25, 0]
# SUV: heading 0° (north, +Y), starts at [0, -25]
r = step("physics", {'command': 'forensic_scene', 'params': {
    'action': 'simulate_collision',
    'vehicle1': {
        'name': 'Vehicle',
        'mass_kg': 1400,
        'speed_mph': 35,
        'heading_deg': 90,
        'start_pos': [-25, 0, 0]
    },
    'vehicle2': {
        'name': 'Vehicle.001',
        'mass_kg': 2000,
        'speed_mph': 25,
        'heading_deg': 0,
        'start_pos': [0, -25, 0]
    },
    'impact_point': [0, 0, 0],
    'coefficient_of_restitution': 0.15,
    'friction_coefficient': 0.65,
    'fps': 24,
    'duration_sec': 5,
    'v1_spin_deg_per_sec': 40,
    'v2_spin_deg_per_sec': -20
}})

if isinstance(r, dict) and r.get('impact_frame'):
    print(f"  Impact at frame {r['impact_frame']}")
    print(f"  V1 final: {r.get('v1_final_pos')}")
    print(f"  V2 final: {r.get('v2_final_pos')}")

# Cameras
step("cameras", {'command': 'forensic_scene', 'params': {
    'action': 'setup_cameras', 'camera_type': 'all',
    'target': [0, 0, 0]}})

step("render_preset", {'command': 'forensic_scene', 'params': {
    'action': 'setup_courtroom_render', 'preset': 'presentation'}})

# Render 4 key moments: approach, mid, impact, final
renders_dir = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders"
impact_f = r.get('impact_frame', 30) if isinstance(r, dict) else 30

for frame, label, cam in [
    (1, "approach", "Cam_BirdEye"),
    (impact_f // 2, "midway", "Cam_BirdEye"),
    (impact_f, "impact", "Cam_BirdEye"),
    (impact_f + 20, "post_impact", "Cam_BirdEye"),
    (120, "final", "Cam_BirdEye"),
    (120, "final_orbit", "Cam_Orbit"),
]:
    filepath = f"{renders_dir}/clean_{label}.png"
    code = f"""
import bpy
bpy.context.scene.frame_set({frame})
cam = bpy.data.objects.get("{cam}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{filepath}"
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
"""
    print(f"  [f{frame:03d} {label}]...", end=" ", flush=True)
    send_cmd({'command': 'execute_python', 'params': {'code': code}}, timeout=60)
    print("OK")

# Save blend
blend_path = f"{renders_dir}/clean_crash.blend"
send_cmd({'command': 'execute_python', 'params': {'code': f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}")'}})

print(f"\nDone! Check renders/clean_*.png")
