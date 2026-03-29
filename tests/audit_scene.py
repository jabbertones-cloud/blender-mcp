#!/usr/bin/env python3
"""Audit every detail of the forensic scene and write findings to a file."""
import socket, json

def cmd(c, t=30):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(t)
    try:
        s.connect(('127.0.0.1', 9876))
        s.sendall((json.dumps(c) + '\n').encode())
        d = b''
        while True:
            ch = s.recv(16384)
            if not ch: break
            d += ch
            try:
                json.loads(d.decode())
                break
            except: continue
        return json.loads(d.decode()).get('result', {})
    except Exception as e:
        return {'error': str(e)}
    finally:
        s.close()

RENDERS = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders'

r = cmd({'command': 'execute_python', 'params': {'code': f"""
import bpy, math
out = []

out.append("=" * 60)
out.append("FORENSIC SCENE AUDIT")
out.append("=" * 60)

# 1. Vehicle positions and orientations
out.append("")
out.append("--- VEHICLES ---")
for obj in bpy.data.objects:
    if 'Vehicle' in obj.name and obj.type == 'EMPTY':
        loc = [round(x, 2) for x in obj.location]
        rot_deg = [round(math.degrees(r), 1) for r in obj.rotation_euler]
        scale = [round(s, 2) for s in obj.scale]
        children = [c.name for c in obj.children if c.type == 'MESH']
        out.append(f"{{obj.name}}:")
        out.append(f"  Location: {{loc}}")
        out.append(f"  Rotation (deg): {{rot_deg}}")
        out.append(f"  Scale: {{scale}}")
        out.append(f"  Children: {{children}}")
        # Check if animated
        has_anim = obj.animation_data is not None and obj.animation_data.action is not None
        out.append(f"  Animated: {{has_anim}}")

# Kenney sedan faces +X in local space by default
# heading 90 (east) = sedan should face +X = rotation_z = 0
# heading 0 (north) = sedan should face +Y = rotation_z = 90
out.append("")
out.append("ORIENTATION ANALYSIS:")
out.append("  Kenney car models face +X in local space")
out.append("  Sedan at (-20,0,0) should travel EAST toward (0,0,0)")
out.append("    Needs rotation_z = 0 to face +X (east)")
out.append("  SUV at (0,-18,0) should travel NORTH toward (0,0,0)")
out.append("    Needs rotation_z = 90 to face +Y (north)")

# 2. Characters
out.append("")
out.append("--- CHARACTERS ---")
for obj in bpy.data.objects:
    if 'Witness' in obj.name and obj.type == 'EMPTY':
        loc = [round(x, 2) for x in obj.location]
        out.append(f"{{obj.name}}: location={{loc}}")
        # Check if on sidewalk (x > 12 or y > 8 means on sidewalk)
        on_sidewalk = abs(loc[0]) > 10 or abs(loc[1]) > 8
        out.append(f"  On sidewalk: {{on_sidewalk}}")

# 3. Road layout
out.append("")
out.append("--- ROAD LAYOUT ---")
roads = [o for o in bpy.data.objects if 'Road' in o.name and o.type == 'MESH']
for r_obj in roads:
    dims = [round(d, 1) for d in r_obj.dimensions]
    loc = [round(x, 1) for x in r_obj.location]
    out.append(f"{{r_obj.name}}: loc={{loc}} dims={{dims}}")

# 4. Evidence markers
out.append("")
out.append("--- EVIDENCE ---")
for obj in bpy.data.objects:
    n = obj.name
    if any(x in n for x in ['Impact', 'Skid', 'Debris', 'Marker', 'Evidence']):
        loc = [round(x, 2) for x in obj.location]
        out.append(f"{{n}}: loc={{loc}} type={{obj.type}}")

# 5. Annotations
out.append("")
out.append("--- ANNOTATIONS ---")
for obj in bpy.data.objects:
    if obj.type == 'FONT':
        loc = [round(x, 2) for x in obj.location]
        rot_deg = [round(math.degrees(r), 1) for r in obj.rotation_euler]
        out.append(f"{{obj.name}}: loc={{loc}} rot={{rot_deg}}")
        try:
            out.append(f"  Text: '{{obj.data.body}}'")
        except:
            pass

# 6. Cameras
out.append("")
out.append("--- CAMERAS ---")
for obj in bpy.data.objects:
    if obj.type == 'CAMERA':
        loc = [round(x, 2) for x in obj.location]
        rot_deg = [round(math.degrees(r), 1) for r in obj.rotation_euler]
        out.append(f"{{obj.name}}: loc={{loc}} rot={{rot_deg}} lens={{obj.data.lens}}")
        has_anim = obj.animation_data is not None and obj.animation_data.action is not None
        out.append(f"  Animated: {{has_anim}}")

# 7. Lighting
out.append("")
out.append("--- LIGHTING ---")
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        out.append(f"{{obj.name}}: type={{obj.data.type}} energy={{obj.data.energy}}")

# 8. Render settings
out.append("")
out.append("--- RENDER SETTINGS ---")
scene = bpy.context.scene
out.append(f"Engine: {{scene.render.engine}}")
out.append(f"Resolution: {{scene.render.resolution_x}}x{{scene.render.resolution_y}}")
out.append(f"Frames: {{scene.frame_start}}-{{scene.frame_end}} @ {{scene.render.fps}}fps")
try:
    out.append(f"View Transform: {{scene.view_settings.view_transform}}")
except: pass

# 9. Frame range check
out.append("")
out.append("--- ANIMATION CHECK ---")
animated_objects = []
for obj in bpy.data.objects:
    if obj.animation_data and obj.animation_data.action:
        try:
            kf_count = sum(len(fc.keyframe_points) for fc in obj.animation_data.action.fcurves)
        except:
            kf_count = -1
        animated_objects.append(f"{{obj.name}}: {{kf_count}} keyframes")
if animated_objects:
    for a in animated_objects:
        out.append(f"  {{a}}")
else:
    out.append("  NO ANIMATED OBJECTS - cars are static!")

# 10. Missing elements checklist
out.append("")
out.append("--- MISSING ELEMENTS CHECKLIST ---")
checks = [
    ("Collision physics animation", len(animated_objects) > 0),
    ("Ghost trails (semi-transparent path)", any('ghost' in o.name.lower() or 'trail' in o.name.lower() for o in bpy.data.objects)),
    ("Data overlay HUD", any('hud' in o.name.lower() or 'overlay' in o.name.lower() or 'speed' in o.name.lower() for o in bpy.data.objects)),
    ("Scale bar", any('scale' in o.name.lower() and 'bar' in o.name.lower() for o in bpy.data.objects)),
    ("Exhibit label", any('exhibit' in o.name.lower() for o in bpy.data.objects)),
    ("Skid marks", any('skid' in o.name.lower() for o in bpy.data.objects)),
    ("Impact point marker", any('impact' in o.name.lower() for o in bpy.data.objects)),
    ("Debris field", any('debris' in o.name.lower() for o in bpy.data.objects)),
    ("Measurement annotation", any('measurement' in o.name.lower() or 'measure' in o.name.lower() for o in bpy.data.objects)),
    ("Traffic signals", any('traffic' in o.name.lower() for o in bpy.data.objects)),
    ("Stop signs", any('stop' in o.name.lower() for o in bpy.data.objects)),
    ("Street lights", any('streetlight' in o.name.lower() for o in bpy.data.objects)),
]
for name, present in checks:
    status = "OK" if present else "MISSING"
    out.append(f"  [{{status}}] {{name}}")

with open('{RENDERS}/scene_audit.txt', 'w') as f:
    f.write('\\n'.join(out))
"""}})
print("Audit:", r)
