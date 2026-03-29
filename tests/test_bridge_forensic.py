#!/usr/bin/env python3
"""
Test: Build a forensic scene THROUGH THE BRIDGE (not direct bpy).
This validates that the standardized addon works end-to-end.
Sends commands via TCP socket just like the MCP server would.
Then audits the scene and renders multiple angles.
"""
import socket
import json
import sys
import time
import os

HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 30.0
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders")
AUDIT_FILE = os.path.join(RENDER_DIR, "bridge_test_audit.txt")

_counter = 0

def send(command, params=None):
    global _counter
    _counter += 1
    payload = {"id": str(_counter), "command": command, "params": params or {}}

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    s.connect((HOST, PORT))
    s.sendall(json.dumps(payload).encode())

    raw = b""
    while True:
        chunk = s.recv(1048576)
        if not chunk:
            break
        raw += chunk
        try:
            resp = json.loads(raw.decode())
            s.close()
            return resp
        except json.JSONDecodeError:
            continue
    s.close()
    return json.loads(raw.decode())


def check(label, resp):
    """Check response and print status."""
    if "error" in resp:
        print(f"  FAIL  {label}: {resp['error']}")
        return False
    result = resp.get("result", resp)
    if isinstance(result, dict) and result.get("error"):
        print(f"  FAIL  {label}: {result['error']}")
        return False
    print(f"  OK    {label}")
    return True


def main():
    print("=" * 60)
    print("BRIDGE FORENSIC SCENE TEST")
    print("=" * 60)

    os.makedirs(RENDER_DIR, exist_ok=True)

    # Step 1: Ping
    print("\n[1] Ping bridge...")
    resp = send("ping")
    result = resp.get("result", {})
    print(f"  Instance: {result.get('instance_id', '?')}")
    print(f"  Blender:  {result.get('blender_version', '?')}")
    print(f"  Port:     {result.get('port', '?')}")

    # Step 2: Clear scene (delete all objects, but don't reset factory settings — that kills the bridge)
    print("\n[2] Clear scene...")
    check("clear", send("execute_python", {"code": """
import bpy
# Select and delete all objects
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=True)
# Clear orphan data
for block in bpy.data.meshes:
    if block.users == 0:
        bpy.data.meshes.remove(block)
for block in bpy.data.materials:
    if block.users == 0:
        bpy.data.materials.remove(block)
for block in bpy.data.cameras:
    if block.users == 0:
        bpy.data.cameras.remove(block)
for block in bpy.data.lights:
    if block.users == 0:
        bpy.data.lights.remove(block)
print(f'Scene cleared: {len(bpy.data.objects)} objects remaining')
"""}))

    # Step 3: Build road via forensic_scene
    print("\n[3] Build road...")
    check("road", send("forensic_scene", {
        "action": "build_road",
        "road_type": "intersection",
        "lanes": 2,
        "length": 60
    }))

    # Step 4: Place vehicles (this tests the standardized model import!)
    print("\n[4] Place vehicles...")

    # V1: Sedan approaching from west, heading east (90 degrees)
    resp_v1 = send("forensic_scene", {
        "action": "place_vehicle",
        "name": "V1_Sedan",
        "vehicle_type": "sedan",
        "location": [-15, 0, 0],
        "rotation": 90,
        "color": [0.1, 0.2, 0.7, 1.0],
        "label": "Vehicle 1 - Sedan",
        "damaged": True,
        "impact_side": "front"
    })
    v1_ok = check("V1 sedan", resp_v1)

    # V2: SUV approaching from south, heading north (0 degrees)
    resp_v2 = send("forensic_scene", {
        "action": "place_vehicle",
        "name": "V2_SUV",
        "vehicle_type": "suv",
        "location": [0, -12, 0],
        "rotation": 0,
        "color": [0.6, 0.05, 0.05, 1.0],
        "label": "Vehicle 2 - SUV",
        "damaged": True,
        "impact_side": "left"
    })
    v2_ok = check("V2 SUV", resp_v2)

    # Step 5: Place figures
    print("\n[5] Place figures...")
    check("witness", send("forensic_scene", {
        "action": "place_figure",
        "name": "Witness_1",
        "location": [8, -8, 0],
        "rotation": 45,
        "label": "Witness A"
    }))

    # Step 6: Add annotations
    print("\n[6] Add annotations...")
    check("speed_v1", send("forensic_scene", {
        "action": "add_annotation",
        "annotation_type": "speed",
        "text": "38 mph",
        "location": [-10, 0, 3],
        "size": 0.5
    }))

    check("speed_v2", send("forensic_scene", {
        "action": "add_annotation",
        "annotation_type": "speed",
        "text": "28 mph",
        "location": [0, -8, 3],
        "size": 0.5
    }))

    check("distance", send("forensic_scene", {
        "action": "add_annotation",
        "annotation_type": "distance",
        "text": "Impact Zone",
        "start": [-5, 0, 0],
        "end": [5, 0, 0]
    }))

    # Step 7: Add impact markers
    print("\n[7] Add impact markers...")
    check("impact", send("forensic_scene", {
        "action": "add_impact_marker",
        "marker_type": "impact_point",
        "location": [0, 0, 0]
    }))

    check("skid", send("forensic_scene", {
        "action": "add_impact_marker",
        "marker_type": "skid_mark",
        "start": [-15, 0, 0],
        "end": [-2, 0, 0]
    }))

    check("debris", send("forensic_scene", {
        "action": "add_impact_marker",
        "marker_type": "debris",
        "location": [2, 2, 0]
    }))

    # Step 8: Setup cameras
    print("\n[8] Setup cameras...")
    check("cameras", send("forensic_scene", {
        "action": "setup_cameras",
        "camera_type": "all",
        "target": [0, 0, 0]
    }))

    # Step 9: Set time of day
    print("\n[9] Set time of day...")
    check("lighting", send("forensic_scene", {
        "action": "set_time_of_day",
        "time": "day",
        "strength": 1.0
    }))

    # Step 10: AUDIT — run Python inside Blender to inspect what was actually created
    print("\n[10] Auditing scene...")
    audit_code = f"""
import bpy
import os

lines = []
lines.append("=" * 60)
lines.append("BRIDGE TEST SCENE AUDIT")
lines.append("=" * 60)

# Count objects by type
obj_types = {{}}
for obj in bpy.data.objects:
    t = obj.type
    obj_types[t] = obj_types.get(t, 0) + 1
lines.append(f"\\nTotal objects: {{len(bpy.data.objects)}}")
for t, c in sorted(obj_types.items()):
    lines.append(f"  {{t}}: {{c}}")

# Check for imported models vs primitives
lines.append("\\n--- VEHICLE CHECK ---")
for obj in bpy.data.objects:
    n = obj.name
    if 'V1' in n or 'V2' in n or 'sedan' in n.lower() or 'suv' in n.lower():
        mesh_type = "UNKNOWN"
        if obj.type == 'EMPTY':
            children = [c for c in obj.children_recursive if c.type == 'MESH']
            if children:
                # Check vertex count to distinguish imported vs procedural
                total_verts = sum(len(c.data.vertices) for c in children)
                mesh_type = f"IMPORTED ({{len(children)}} meshes, {{total_verts}} verts)" if total_verts > 100 else f"PROCEDURAL ({{total_verts}} verts)"
            else:
                mesh_type = "EMPTY (no mesh children)"
        elif obj.type == 'MESH':
            verts = len(obj.data.vertices)
            mesh_type = f"SINGLE MESH ({{verts}} verts)"
        lines.append(f"  {{n}}: {{obj.type}} -> {{mesh_type}}")
        lines.append(f"    Location: {{[round(v,2) for v in obj.location]}}")
        lines.append(f"    Rotation Z: {{round(obj.rotation_euler[2] * 57.2958, 1)}} deg")

# Check materials
lines.append("\\n--- MATERIAL CHECK ---")
for mat in bpy.data.materials:
    has_nodes = mat.use_nodes
    color = "?"
    if has_nodes and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                bc = node.inputs.get('Base Color')
                if bc and hasattr(bc, 'default_value'):
                    c = bc.default_value
                    color = f"({{c[0]:.2f}}, {{c[1]:.2f}}, {{c[2]:.2f}})"
                break
    lines.append(f"  {{mat.name}}: color={{color}}, nodes={{has_nodes}}")

# Check for magenta/pink materials (the old bug)
lines.append("\\n--- MAGENTA CHECK ---")
magenta_count = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    for slot in obj.material_slots:
        mat = slot.material
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    bc = node.inputs.get('Base Color')
                    if bc and hasattr(bc, 'default_value'):
                        r, g, b = bc.default_value[0], bc.default_value[1], bc.default_value[2]
                        if r > 0.8 and g < 0.1 and b > 0.5:
                            magenta_count += 1
                            lines.append(f"  MAGENTA on {{obj.name}} / {{mat.name}}")
if magenta_count == 0:
    lines.append("  No magenta materials found (GOOD)")

# Check cameras
lines.append("\\n--- CAMERAS ---")
for obj in bpy.data.objects:
    if obj.type == 'CAMERA':
        lines.append(f"  {{obj.name}}: loc={{[round(v,1) for v in obj.location]}}")

# Check text objects
lines.append("\\n--- TEXT/ANNOTATIONS ---")
for obj in bpy.data.objects:
    if obj.type == 'FONT':
        lines.append(f"  {{obj.name}}: '{{obj.data.body[:50]}}' at {{[round(v,1) for v in obj.location]}}")

# Check collections
lines.append("\\n--- COLLECTIONS ---")
for col in bpy.data.collections:
    lines.append(f"  {{col.name}}: {{len(col.objects)}} objects")

# Write audit
audit_path = "{AUDIT_FILE}"
os.makedirs(os.path.dirname(audit_path), exist_ok=True)
with open(audit_path, 'w') as f:
    f.write("\\n".join(lines))
print(f"Audit written to {{audit_path}}")
"""
    check("audit", send("execute_python", {"code": audit_code}))

    # Step 11: Render from multiple angles
    print("\n[11] Rendering...")

    render_code = f"""
import bpy
import os

render_dir = "{RENDER_DIR}"
os.makedirs(render_dir, exist_ok=True)

scene = bpy.context.scene
# Blender 5.x uses BLENDER_EEVEE (not EEVEE_NEXT)
scene.render.engine = 'BLENDER_EEVEE'

scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'

# Find cameras
cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
results = []

if not cameras:
    # Fallback: create a bird's eye camera
    bpy.ops.object.camera_add(location=(0, 0, 40))
    cam = bpy.context.active_object
    cam.name = "Fallback_BirdEye"
    cam.rotation_euler = (0, 0, 0)
    cam.data.lens = 24
    cameras = [cam]

for i, cam in enumerate(cameras[:5]):  # Max 5 renders
    scene.camera = cam
    out_path = os.path.join(render_dir, f"bridge_test_{{i+1:02d}}_{{cam.name}}.png")
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    results.append(f"Rendered: {{cam.name}} -> {{out_path}}")

# Also save the blend file
blend_path = os.path.join(render_dir, "bridge_test_scene.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
results.append(f"Scene saved: {{blend_path}}")

with open(os.path.join(render_dir, "bridge_test_render_log.txt"), 'w') as f:
    f.write("\\n".join(results))
print("\\n".join(results))
"""
    resp = send("execute_python", {"code": render_code})
    check("render", resp)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print(f"Audit: {AUDIT_FILE}")
    print(f"Renders: {RENDER_DIR}/bridge_test_*.png")
    print("=" * 60)


if __name__ == "__main__":
    main()
