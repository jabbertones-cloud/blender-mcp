#!/usr/bin/env python3
"""
QUALITY PUSH v4 — Test baked addon defaults + try Cycles for shadows.

Goals:
1. Load bridge_test_scene.blend
2. Call set_time_of_day through the bridge (NOT manual Python) to verify addon defaults work
3. Apply dark asphalt + sidewalk/grass materials manually (still not in addon)
4. Test ONE frame with Cycles to see if shadows actually cast
5. Render EEVEE + Cycles comparison
"""
import socket, json, os, time

HOST, PORT, TIMEOUT = "127.0.0.1", 9876, 120.0
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders")
_counter = 0

def send(command, params=None):
    global _counter
    _counter += 1
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    s.connect((HOST, PORT))
    s.sendall(json.dumps({"id": str(_counter), "command": command, "params": params or {}}).encode())
    raw = b""
    while True:
        chunk = s.recv(1048576)
        if not chunk: break
        raw += chunk
        try:
            resp = json.loads(raw.decode())
            s.close()
            return resp
        except: continue
    s.close()
    return json.loads(raw.decode())

def run_py(code, label=""):
    resp = send("execute_python", {"code": code})
    result = resp.get("result", resp)
    ok = not (isinstance(result, dict) and result.get("error"))
    status = "OK" if ok else "FAIL"
    if label:
        print(f"  [{status}] {label}")
        if not ok:
            err = result.get("error", str(result))[:400]
            print(f"        {err}")
    return ok

def check(label, resp):
    if "error" in resp:
        print(f"  [FAIL] {label}: {resp['error'][:300]}")
        return False
    result = resp.get("result", resp)
    if isinstance(result, dict) and result.get("error"):
        print(f"  [FAIL] {label}: {result['error'][:300]}")
        return False
    print(f"  [OK]   {label}")
    if isinstance(result, dict):
        for k, v in result.items():
            if k not in ("status", "action"):
                print(f"         {k}: {v}")
    return True

def main():
    print("=" * 70)
    print("QUALITY PUSH v4 — Addon defaults + Cycles shadow test")
    print("=" * 70)

    # Step 1: Reload addon in Blender
    print("\n[1] Reloading addon...")
    run_py("""
import bpy
import importlib
# Disable and re-enable the addon to pick up new code
try:
    bpy.ops.preferences.addon_disable(module='openclaw_blender_bridge')
except: pass
try:
    bpy.ops.preferences.addon_enable(module='openclaw_blender_bridge')
except: pass
print("Addon reloaded")
""", "Reload addon")

    # Step 2: Load scene
    print("\n[2] Loading scene...")
    blend_path = os.path.join(RENDER_DIR, "bridge_test_scene.blend")
    run_py(f"""
import bpy
bpy.ops.wm.open_mainfile(filepath="{blend_path}")
print(f"Loaded: {{len(bpy.data.objects)}} objects")
""", "Load bridge_test_scene.blend")

    # Step 3: Call set_time_of_day through the BRIDGE (tests addon defaults)
    print("\n[3] Setting lighting via bridge (addon defaults)...")
    resp = send("forensic_scene", {
        "action": "set_time_of_day",
        "time": "day",
        "strength": 1.0  # This gets overridden by addon's sky_strength default now
    })
    check("set_time_of_day (day)", resp)

    # Step 4: Apply dark asphalt + sidewalk (manual — not yet in addon)
    print("\n[4] Applying materials...")

    run_py(r"""
import bpy

# Dark asphalt material
asphalt = bpy.data.materials.new("Dark_Asphalt_v4")
asphalt.use_nodes = True
tree = asphalt.node_tree
bsdf = tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.045, 0.045, 0.05, 1.0)
bsdf.inputs["Roughness"].default_value = 0.85
bsdf.inputs["Specular IOR Level"].default_value = 0.3

noise = tree.nodes.new("ShaderNodeTexNoise")
noise.location = (-500, 0)
noise.inputs["Scale"].default_value = 120
noise.inputs["Detail"].default_value = 14
noise.inputs["Roughness"].default_value = 0.75
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.location = (-300, 0)
ramp.color_ramp.elements[0].color = (0.03, 0.03, 0.035, 1)
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[1].color = (0.07, 0.07, 0.075, 1)
ramp.color_ramp.elements[1].position = 0.65
tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
noise2 = tree.nodes.new("ShaderNodeTexNoise")
noise2.location = (-500, -300)
noise2.inputs["Scale"].default_value = 300
noise2.inputs["Detail"].default_value = 16
bump = tree.nodes.new("ShaderNodeBump")
bump.location = (-200, -300)
bump.inputs["Strength"].default_value = 0.15
tree.links.new(noise2.outputs["Fac"], bump.inputs["Height"])
tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

# Sidewalk material (light concrete)
sidewalk = bpy.data.materials.new("Sidewalk_Concrete")
sidewalk.use_nodes = True
sw_bsdf = sidewalk.node_tree.nodes["Principled BSDF"]
sw_bsdf.inputs["Base Color"].default_value = (0.25, 0.24, 0.22, 1.0)
sw_bsdf.inputs["Roughness"].default_value = 0.9

# Grass material (dark green)
grass = bpy.data.materials.new("Grass_Ground")
grass.use_nodes = True
gr_bsdf = grass.node_tree.nodes["Principled BSDF"]
gr_bsdf.inputs["Base Color"].default_value = (0.05, 0.12, 0.03, 1.0)
gr_bsdf.inputs["Roughness"].default_value = 0.95

# Apply to objects
road_count = 0
sidewalk_count = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    # Road surfaces
    if any(kw in n for kw in ['road', 'intersection']) and not any(kw in n for kw in ['stripe', 'mark', 'line', 'crosswalk', 'curb']):
        obj.data.materials.clear()
        obj.data.materials.append(asphalt)
        road_count += 1
    # Sidewalk/curb
    elif any(kw in n for kw in ['sidewalk', 'curb', 'pavement']):
        obj.data.materials.clear()
        obj.data.materials.append(sidewalk)
        sidewalk_count += 1
    # Ground (areas beyond road)
    elif 'ground' in n:
        obj.data.materials.clear()
        obj.data.materials.append(grass)

print(f"Applied: {road_count} road, {sidewalk_count} sidewalk objects")
""", "Dark asphalt + sidewalk + grass")

    # Road markings: white
    run_py("""
import bpy
white = bpy.data.materials.new("Road_Marking_White_v4")
white.use_nodes = True
b = white.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)
b.inputs["Roughness"].default_value = 0.6
b.inputs["Emission Strength"].default_value = 0.05

c = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if any(kw in n for kw in ['stripe', 'crosswalk', 'marking']):
        obj.data.materials.clear()
        obj.data.materials.append(white)
        c += 1
print(f"Markings: {c}")
""", "White road markings")

    # Vehicle enhancements
    run_py("""
import bpy

def mk(name, color, metallic=0, roughness=0.5, alpha=1.0, emission=0, transmission=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = 'DITHERED'
    if emission > 0:
        b.inputs["Emission Strength"].default_value = emission
        b.inputs["Emission Color"].default_value = color
    if transmission > 0:
        b.inputs["Transmission Weight"].default_value = transmission
    return mat

window = mk("V4_Window", (0.1, 0.15, 0.25, 0.6), roughness=0.02, alpha=0.6, transmission=0.9)
chrome = mk("V4_Chrome", (0.85, 0.85, 0.9, 1), metallic=1.0, roughness=0.05)
headlight = mk("V4_Headlight", (1, 0.97, 0.85, 1), roughness=0.02, emission=0.3, transmission=0.85)
taillight = mk("V4_Taillight", (0.9, 0.04, 0.02, 1), roughness=0.08, emission=0.5)
tire = mk("V4_Tire", (0.02, 0.02, 0.02, 1), roughness=0.95)

for veh in bpy.data.objects:
    if veh.type != 'EMPTY' or ('V1' not in veh.name and 'V2' not in veh.name):
        continue
    for child in veh.children_recursive:
        if child.type != 'MESH': continue
        n = child.name.lower()
        if 'window' in n or 'windshield' in n or 'glass' in n:
            child.data.materials.clear()
            child.data.materials.append(window)
        elif 'headlight' in n or 'lamp_front' in n:
            child.data.materials.clear()
            child.data.materials.append(headlight)
        elif 'taillight' in n or 'lamp_rear' in n:
            child.data.materials.clear()
            child.data.materials.append(taillight)
        elif 'bumper' in n or 'grill' in n:
            child.data.materials.clear()
            child.data.materials.append(chrome)
        elif 'wheel' in n or 'tire' in n:
            child.data.materials.clear()
            child.data.materials.append(tire)

# Clearcoat
for mat in bpy.data.materials:
    if '_Body' in mat.name and mat.use_nodes:
        b = mat.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Roughness"].default_value = 0.12
            try:
                b.inputs["Coat Weight"].default_value = 0.9
                b.inputs["Coat Roughness"].default_value = 0.03
            except: pass
print("Vehicle materials applied")
""", "Vehicle materials")

    # Fix text: emissive, no constraints
    run_py("""
import bpy
for obj in bpy.data.objects:
    if obj.type == 'FONT':
        for c in list(obj.constraints):
            obj.constraints.remove(c)
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                b = slot.material.node_tree.nodes.get("Principled BSDF")
                if b:
                    try:
                        b.inputs["Emission Strength"].default_value = 0.8
                        bc = b.inputs["Base Color"].default_value
                        b.inputs["Emission Color"].default_value = (bc[0], bc[1], bc[2], 1)
                    except: pass
print("Text fixed")
""", "Text emission")

    # Step 5: RENDER — EEVEE orbit (best angle from v3)
    print("\n[5] Rendering EEVEE...")
    render_code = """
import bpy, os
render_dir = "%s"
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'

# Find orbit camera
cam = None
for obj in bpy.data.objects:
    if obj.type == 'CAMERA' and 'orbit' in obj.name.lower():
        cam = obj
        break
if not cam:
    cam = [o for o in bpy.data.objects if o.type == 'CAMERA'][0]

scene.camera = cam
out = os.path.join(render_dir, "q9v4_eevee_orbit.png")
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print(f"EEVEE rendered: {out}")
""" % RENDER_DIR
    run_py(render_code, "EEVEE orbit render")

    # Step 6: RENDER — Cycles orbit (shadow test!)
    print("\n[6] Rendering CYCLES (shadow test)...")
    cycles_code = """
import bpy, os
render_dir = "%s"
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64  # Low for speed, enough for shadows
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'

# Keep Filmic
scene.view_settings.view_transform = 'Filmic'
scene.view_settings.look = 'High Contrast'
scene.view_settings.exposure = 0.3

cam = None
for obj in bpy.data.objects:
    if obj.type == 'CAMERA' and 'orbit' in obj.name.lower():
        cam = obj
        break
if not cam:
    cam = [o for o in bpy.data.objects if o.type == 'CAMERA'][0]

scene.camera = cam
out = os.path.join(render_dir, "q9v4_cycles_orbit.png")
scene.render.filepath = out
bpy.ops.render.render(write_still=True)
print(f"Cycles rendered: {out}")
""" % RENDER_DIR
    run_py(cycles_code, "Cycles orbit render (may take 1-3 min)")

    # Step 7: Also render bird's eye in both engines
    print("\n[7] Rendering bird's eye comparison...")
    bird_code = """
import bpy, os
render_dir = "%s"
scene = bpy.context.scene

cam = None
for obj in bpy.data.objects:
    if obj.type == 'CAMERA' and 'bird' in obj.name.lower():
        cam = obj
        break
if not cam:
    print("No bird's eye camera found")
else:
    scene.camera = cam

    # EEVEE
    scene.render.engine = 'BLENDER_EEVEE'
    out1 = os.path.join(render_dir, "q9v4_eevee_birdeye.png")
    scene.render.filepath = out1
    bpy.ops.render.render(write_still=True)
    print(f"EEVEE bird's eye: {out1}")

    # Cycles
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    out2 = os.path.join(render_dir, "q9v4_cycles_birdeye.png")
    scene.render.filepath = out2
    bpy.ops.render.render(write_still=True)
    print(f"Cycles bird's eye: {out2}")

# Save
blend = os.path.join(render_dir, "quality_push_v4.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
print(f"Saved: {blend}")
""" % RENDER_DIR
    run_py(bird_code, "Bird's eye EEVEE + Cycles")

    print("\n" + "=" * 70)
    print("QUALITY PUSH v4 COMPLETE")
    print(f"Renders: {RENDER_DIR}/q9v4_*.png")
    print("Compare EEVEE vs Cycles — look for ground SHADOWS")
    print("=" * 70)


if __name__ == "__main__":
    main()
