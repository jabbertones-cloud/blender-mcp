import socket, json, sys, time

def send_cmd(cmd, timeout=15):
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

def clear_scene():
    send_cmd({'command': 'execute_python', 'params': {'code': 'import bpy\nfor o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)\nfor c in list(bpy.data.collections): bpy.data.collections.remove(c)'}})
    time.sleep(0.3)

passed = 0
failed = 0
errors = []

def test(name, cmd, check_fn=None):
    global passed, failed, errors
    try:
        r = send_cmd(cmd)
        if isinstance(r, dict) and 'error' in r and r['error']:
            failed += 1
            errors.append(f'FAIL {name}: {r["error"][:120]}')
            return r
        if check_fn and not check_fn(r):
            failed += 1
            errors.append(f'FAIL {name}: check failed, got {str(r)[:120]}')
            return r
        passed += 1
        return r
    except Exception as e:
        failed += 1
        errors.append(f'ERROR {name}: {e}')
        return None

# ========== WITNESS CAMERA FIX ==========
clear_scene()
test('witness_camera',
    {'command': 'forensic_scene', 'params': {'action': 'setup_cameras', 'camera_type': 'witness', 'target': [0,0,0], 'witness_location': [15,15,1.7]}},
    lambda r: 'Cam_Witness' in r.get('cameras', []))

# Verify TRACK_TO constraint
r = send_cmd({'command': 'execute_python', 'params': {'code': 'import bpy\ncam = bpy.data.objects.get("Cam_Witness")\nif cam:\n    cs = [c.type for c in cam.constraints]\n    print("HAS_TRACK_TO:", "TRACK_TO" in cs)\nelse:\n    print("NO_CAM")'}})
has_track = 'True' in str(r)
test('witness_track_to_constraint', {'command': 'execute_python', 'params': {'code': 'print(1)'}}, lambda _: has_track)

# Verify hidden target empty via get_object_data
r2 = send_cmd({'command': 'get_object_data', 'params': {'name': 'Cam_Witness_Target'}})
target_ok = r2.get('name') == 'Cam_Witness_Target' or 'Cam_Witness_Target' in str(r2)
test('witness_target_empty', {'command': 'get_object_data', 'params': {'name': 'Cam_Witness_Target'}}, lambda r: 'Cam_Witness_Target' in str(r))

# ========== ALL CAMERAS ==========
clear_scene()
test('all_cameras',
    {'command': 'forensic_scene', 'params': {'action': 'setup_cameras', 'camera_type': 'all', 'target': [0,0,0]}},
    lambda r: len(r.get('cameras', [])) >= 4)

# ========== SCENE TEMPLATES (NEW) ==========
for tpl in ['t_intersection', 'highway_straight', 'residential', 'parking_lot']:
    clear_scene()
    test(f'template_{tpl}',
        {'command': 'forensic_scene', 'params': {'action': 'add_scene_template', 'template': tpl}},
        lambda r: r.get('status') == 'ok' and len(r.get('elements', [])) > 0)

# ========== MEASUREMENT GRID (NEW) ==========
clear_scene()
test('measurement_grid',
    {'command': 'forensic_scene', 'params': {'action': 'add_measurement_grid', 'size': 20, 'spacing': 5}},
    lambda r: r.get('status') == 'ok' and r.get('lines', 0) > 0)

# ========== EXHIBIT OVERLAY (NEW) ==========
clear_scene()
test('exhibit_overlay',
    {'command': 'forensic_scene', 'params': {'action': 'add_exhibit_overlay', 'case_number': 'Case 2026-TEST-001', 'exhibit_id': 'Exhibit B', 'expert_name': 'Dr. Test', 'show_scale_bar': True, 'show_timestamp': True}},
    lambda r: r.get('status') == 'ok' and len(r.get('overlay_items', [])) > 0)

# ========== COURTROOM RENDER PRESETS (NEW) ==========
for preset in ['draft', 'presentation', 'print', 'high_quality']:
    test(f'render_{preset}',
        {'command': 'forensic_scene', 'params': {'action': 'setup_courtroom_render', 'preset': preset}},
        lambda r: r.get('status') == 'ok')

# ========== VEHICLES (regression) ==========
for vtype in ['sedan', 'suv', 'truck', 'pickup', 'motorcycle', 'bicycle', 'bus', 'semi']:
    clear_scene()
    test(f'vehicle_{vtype}',
        {'command': 'forensic_scene', 'params': {'action': 'place_vehicle', 'vehicle_type': vtype, 'location': [0,0,0], 'color': [0.8,0.1,0.1]}},
        lambda r, vt=vtype: r.get('type') == vt)

# ========== DAMAGE (regression) ==========
for side in ['front', 'rear', 'left', 'right', 'front_left', 'front_right', 'rear_left', 'rear_right']:
    clear_scene()
    test(f'damage_{side}',
        {'command': 'forensic_scene', 'params': {'action': 'place_vehicle', 'vehicle_type': 'sedan', 'location': [0,0,0], 'color': [0.5,0.5,0.5], 'damage': {'side': side, 'severity': 'moderate'}}},
        lambda r: r.get('type') == 'sedan')

# ========== FIGURES (regression) ==========
for pose in ['standing', 'walking']:
    clear_scene()
    test(f'figure_{pose}',
        {'command': 'forensic_scene', 'params': {'action': 'place_figure', 'pose': pose, 'location': [5,0,0]}},
        lambda r, p=pose: r.get('pose') == p)

# ========== ROADS (regression) ==========
clear_scene()
test('road_straight',
    {'command': 'forensic_scene', 'params': {'action': 'build_road', 'type': 'straight', 'start': [-20,0,0], 'end': [20,0,0], 'lanes': 2, 'width': 7}},
    lambda r: r.get('type') == 'straight')

test('road_intersection',
    {'command': 'forensic_scene', 'params': {'action': 'build_road', 'type': 'intersection', 'center': [0,0,0], 'lanes': 2, 'width': 7}},
    lambda r: 'elements' in r)

# ========== MARKERS (regression) ==========
clear_scene()
for mtype in ['skid_mark', 'debris', 'fluid_spill', 'impact_point']:
    test(f'marker_{mtype}',
        {'command': 'forensic_scene', 'params': {'action': 'add_impact_marker', 'marker_type': mtype, 'location': [0,0,0]}},
        lambda r, mt=mtype: r.get('type') == mt)

# ========== ANNOTATIONS (regression) ==========
for atype in ['label', 'arrow', 'measurement']:
    test(f'annotation_{atype}',
        {'command': 'forensic_scene', 'params': {'action': 'add_annotation', 'annotation_type': atype, 'location': [0,0,0], 'text': 'Test', 'end': [5,0,0]}},
        lambda r: not r.get('error'))

# ========== TIME OF DAY (regression) ==========
for tod in ['day', 'night', 'dusk', 'dawn', 'overcast']:
    test(f'time_{tod}',
        {'command': 'forensic_scene', 'params': {'action': 'set_time_of_day', 'time': tod}},
        lambda r, t=tod: r.get('time_of_day') == t)

# ========== FULL SCENE (regression) ==========
clear_scene()
test('full_scene',
    {'command': 'forensic_scene', 'params': {'action': 'build_full_scene',
        'road': {'type': 'intersection', 'center': [0,0,0], 'lanes': 2, 'width': 7},
        'vehicles': [
            {'vehicle_type': 'sedan', 'location': [-5,2,0], 'rotation': 15, 'color': [0.8,0.1,0.1], 'damage': {'side': 'front_right', 'severity': 'severe'}},
            {'vehicle_type': 'suv', 'location': [3,-4,0], 'rotation': 280, 'color': [0.1,0.2,0.6], 'damage': {'side': 'left', 'severity': 'moderate'}}
        ],
        'figures': [{'location': [8,5,0], 'pose': 'standing'}],
        'markers': [{'marker_type': 'skid_mark', 'location': [-12,1,0], 'end': [-5,2,0]}],
        'annotations': [{'annotation_type': 'label', 'location': [0,0,3], 'text': 'Point of Impact'}],
        'cameras': {'camera_type': 'all', 'target': [0,0,0]},
        'time_of_day': 'day'}},
    lambda r: r.get('total_elements', 0) > 5)

# ========== RESULTS ==========
print(f'\n=== RESULTS: {passed}/{passed+failed} passed ({failed} failed) ===')
for e in errors:
    print(e)
if failed == 0:
    print('ALL TESTS PASSED')
