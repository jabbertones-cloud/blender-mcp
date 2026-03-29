#!/usr/bin/env python3
"""
QUALITY PUSH v2 — Load known-good scene, apply enhancements, render.
Fixes from v1: don't rebuild scene (load saved blend), fix brightness, keep cameras.
"""
import socket, json, os, time

HOST, PORT, TIMEOUT = "127.0.0.1", 9876, 60.0
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
            err = result.get("error", str(result))[:300]
            print(f"        {err}")
    return ok

def main():
    print("=" * 70)
    print("QUALITY PUSH v2")
    print("=" * 70)

    # Step 1: Load the saved scene from bridge test
    print("\n[1] Loading saved scene...")
    blend_path = os.path.join(RENDER_DIR, "bridge_test_scene.blend")
    if not os.path.exists(blend_path):
        print(f"  ERROR: {blend_path} not found. Run test_bridge_forensic.py first.")
        return
    run_py(f"""
import bpy
bpy.ops.wm.open_mainfile(filepath="{blend_path}")
print(f"Loaded: {{len(bpy.data.objects)}} objects")
""", "Load bridge_test_scene.blend")

    # Verify cameras exist
    run_py("""
import bpy
cams = [o.name for o in bpy.data.objects if o.type == 'CAMERA']
out = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v2_cameras.txt"
with open(out, "w") as f:
    f.write(f"Cameras: {cams}\\nTotal: {len(bpy.data.objects)}\\n")
""", "Verify scene")

    time.sleep(0.5)
    try:
        with open(os.path.join(RENDER_DIR, "v2_cameras.txt")) as f:
            print(f"  Scene: {f.read().strip()}")
    except:
        pass

    # Step 2: Apply visual enhancements
    print("\n[2] Applying quality enhancements...")

    # 2a: Sky environment — CAREFUL with brightness
    run_py("""
import bpy, math

world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree
tree.nodes.clear()

output = tree.nodes.new("ShaderNodeOutputWorld")
output.location = (400, 0)
bg = tree.nodes.new("ShaderNodeBackground")
bg.location = (200, 0)
sky = tree.nodes.new("ShaderNodeTexSky")
sky.location = (0, 0)
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_elevation = math.radians(32)
sky.sun_rotation = math.radians(220)
sky.ground_albedo = 0.3
tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.8  # LOWER than v1 to avoid blowout
tree.links.new(bg.outputs["Background"], output.inputs["Surface"])
""", "Sky environment (controlled brightness)")

    # 2b: Improve sun — moderate energy, warm color
    run_py("""
import bpy, math

for obj in bpy.data.objects:
    if obj.type == 'LIGHT' and obj.data.type == 'SUN':
        obj.data.energy = 4  # Moderate, not blown out
        obj.data.color = (1.0, 0.95, 0.88)
        obj.rotation_euler = (math.radians(38), math.radians(8), math.radians(220))
        obj.data.use_shadow = True
        try:
            obj.data.shadow_cascade_count = 4
            obj.data.shadow_cascade_max_distance = 120
            obj.data.shadow_soft_size = 0.015
        except: pass
        break

# Add sky fill light (opposite, blue, no shadow)
fill = bpy.data.lights.new(name="Fill_Sky", type='SUN')
fill.energy = 1.0
fill.color = (0.75, 0.85, 1.0)
fill.use_shadow = False
fill_obj = bpy.data.objects.new("Fill_Sky", fill)
bpy.context.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(55), 0, math.radians(40))
""", "Sun + fill light")

    # 2c: Shadow catcher ground
    run_py("""
import bpy
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.01))
ground = bpy.context.active_object
ground.name = "ShadowCatcher_Ground"
ground.is_shadow_catcher = True
""", "Shadow catcher ground")

    # 2d: Procedural asphalt
    run_py("""
import bpy

for mat in bpy.data.materials:
    if mat.name != 'Asphalt_Main': continue
    if not mat.use_nodes: continue
    tree = mat.node_tree
    bsdf = tree.nodes.get("Principled BSDF")
    if not bsdf: continue

    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 80
    noise.inputs["Detail"].default_value = 12
    noise.inputs["Roughness"].default_value = 0.7

    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 0)
    ramp.color_ramp.elements[0].color = (0.04, 0.04, 0.045, 1)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[1].color = (0.1, 0.1, 0.11, 1)
    ramp.color_ramp.elements[1].position = 0.7

    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # Bump for surface texture
    noise3 = tree.nodes.new("ShaderNodeTexNoise")
    noise3.location = (-400, -300)
    noise3.inputs["Scale"].default_value = 200
    noise3.inputs["Detail"].default_value = 16
    bump = tree.nodes.new("ShaderNodeBump")
    bump.location = (-100, -300)
    bump.inputs["Strength"].default_value = 0.12
    tree.links.new(noise3.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    break
""", "Procedural asphalt")

    # 2e: Multi-material vehicles
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

window = mk("V_Window", (0.15, 0.2, 0.3, 0.7), roughness=0.02, alpha=0.7, transmission=0.85)
chrome = mk("V_Chrome", (0.9, 0.9, 0.92, 1), metallic=1.0, roughness=0.05)
headlight = mk("V_Headlight", (1, 0.98, 0.9, 1), roughness=0.02, emission=0.2, transmission=0.9)
taillight = mk("V_Taillight", (0.8, 0.05, 0.02, 1), roughness=0.1, emission=0.3)

for veh in bpy.data.objects:
    if veh.type != 'EMPTY' or ('V1' not in veh.name and 'V2' not in veh.name):
        continue
    for child in veh.children_recursive:
        if child.type != 'MESH': continue
        n = child.name.lower()
        if 'window' in n or 'windshield' in n:
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

# Clearcoat on body paint
for mat in bpy.data.materials:
    if '_Body' in mat.name and mat.use_nodes:
        b = mat.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Roughness"].default_value = 0.15
            try:
                b.inputs["Coat Weight"].default_value = 0.8
                b.inputs["Coat Roughness"].default_value = 0.05
            except: pass
""", "Multi-material vehicles + clearcoat")

    # 2f: Billboard text
    run_py("""
import bpy

cam = bpy.context.scene.camera
if not cam:
    cams = [o for o in bpy.data.objects if o.type == 'CAMERA' and 'BirdEye' in o.name]
    if cams:
        cam = cams[0]
        bpy.context.scene.camera = cam

if cam:
    for obj in bpy.data.objects:
        if obj.type == 'FONT':
            for c in list(obj.constraints):
                if c.type == 'TRACK_TO':
                    obj.constraints.remove(c)
            tc = obj.constraints.new('TRACK_TO')
            tc.target = cam
            tc.track_axis = 'TRACK_Z'
            tc.up_axis = 'UP_Y'
            # Emissive text for readability
            for slot in obj.material_slots:
                if slot.material and slot.material.use_nodes:
                    b = slot.material.node_tree.nodes.get("Principled BSDF")
                    if b:
                        try: b.inputs["Emission Strength"].default_value = 0.4
                        except: pass
""", "Billboard text")

    # 2g: Depth of field
    run_py("""
import bpy
for obj in bpy.data.objects:
    if obj.type != 'CAMERA': continue
    n = obj.name.lower()
    if 'driver' in n or 'witness' in n:
        obj.data.dof.use_dof = True
        obj.data.dof.focus_distance = 15.0
        obj.data.dof.aperture_fstop = 2.8
    elif 'orbit' in n:
        obj.data.dof.use_dof = True
        obj.data.dof.focus_distance = 22.0
        obj.data.dof.aperture_fstop = 5.6
    elif 'bird' in n:
        obj.data.dof.use_dof = False
""", "Depth of field")

    # 2h: Courtroom overlay
    run_py("""
import bpy

def add_text(name, text, location, size=0.3, color=(1,1,1,1), align='LEFT'):
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = align
    mat = bpy.data.materials.new(f"{name}_Mat")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Emission Strength"].default_value = 0.6
    b.inputs["Emission Color"].default_value = color
    obj.data.materials.append(mat)
    return obj

# Exhibit label
add_text("Exhibit_Label",
    "EXHIBIT A  —  Collision Reconstruction\\nCase No. 2024-CV-03847  |  Smith v. Johnson",
    location=(0, 0, 7), size=0.45, color=(1, 1, 1, 1), align='CENTER')

# Scale bar (5m)
bar_mat = bpy.data.materials.new("ScaleBar_Mat")
bar_mat.use_nodes = True
b = bar_mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1, 1, 1, 1)
b.inputs["Emission Strength"].default_value = 0.8
b.inputs["Emission Color"].default_value = (1, 1, 1, 1)

bpy.ops.mesh.primitive_cube_add(size=1, location=(18, -18, 0.05))
bar = bpy.context.active_object
bar.name = "ScaleBar_5m"
bar.scale = (5.0, 0.06, 0.03)
bar.data.materials.append(bar_mat)
for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(18 - 2.5 + i, -18, 0.1))
    tick = bpy.context.active_object
    tick.name = f"ScaleBar_Tick_{i}"
    tick.scale = (0.015, 0.12, 0.05)
    tick.data.materials.append(bar_mat)
add_text("ScaleBar_Label", "5 meters", location=(18, -18.4, 0.12), size=0.22, align='CENTER')

# North arrow
bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=1.0, location=(20, 16, 0.5))
arrow = bpy.context.active_object
arrow.name = "Compass_North"
a_mat = bpy.data.materials.new("Compass_Mat")
a_mat.use_nodes = True
b = a_mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1, 0.2, 0.2, 1)
b.inputs["Emission Strength"].default_value = 0.4
b.inputs["Emission Color"].default_value = (1, 0.2, 0.2, 1)
arrow.data.materials.append(a_mat)
add_text("Compass_N", "N", location=(20, 17.2, 0.5), size=0.35, color=(1, 0.2, 0.2, 1), align='CENTER')

# Disclaimer
add_text("Disclaimer",
    "This animation is a demonstrative exhibit prepared for litigation purposes.\\n"
    "Vehicle positions and speeds based on police report and physical evidence.",
    location=(0, -22, 0.12), size=0.16, color=(0.6, 0.6, 0.6, 1), align='CENTER')

# Billboard all new text
cam = bpy.context.scene.camera
if cam:
    for nm in ["Exhibit_Label", "ScaleBar_Label", "Compass_N", "Disclaimer"]:
        obj = bpy.data.objects.get(nm)
        if obj:
            tc = obj.constraints.new('TRACK_TO')
            tc.target = cam
            tc.track_axis = 'TRACK_Z'
            tc.up_axis = 'UP_Y'
""", "Courtroom overlay")

    # 2i: Dramatic low camera
    run_py("""
import bpy, math
bpy.ops.object.camera_add(location=(10, -8, 1.5))
cam = bpy.context.active_object
cam.name = "Cam_Dramatic"
cam.data.lens = 35
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 12
cam.data.dof.aperture_fstop = 2.0
tc = cam.constraints.new('TRACK_TO')
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'
# Create a target empty at the impact zone
bpy.ops.object.empty_add(location=(0, 0, 0.5))
target = bpy.context.active_object
target.name = "Cam_Dramatic_Target"
tc.target = target
""", "Dramatic low camera")

    # 2j: EEVEE render quality
    run_py("""
import bpy

scene = bpy.context.scene
eevee = scene.eevee
eevee.use_raytracing = True
eevee.ray_tracing_method = 'SCREEN'
eevee.use_shadows = True
eevee.shadow_ray_count = 3
eevee.shadow_step_count = 12
eevee.shadow_resolution_scale = 1.0
eevee.use_volumetric_shadows = True

try:
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'
except: pass
""", "EEVEE render quality")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 3: RENDER
    # ══════════════════════════════════════════════════════════════════════
    print("\n[3] Rendering...")

    render_code = """
import bpy, os

render_dir = "%s"
os.makedirs(render_dir, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'

cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
results = []
results.append(f"Found {len(cameras)} cameras: {[c.name for c in cameras]}")

for i, cam in enumerate(cameras[:6]):
    scene.camera = cam

    # Update billboard text to face THIS camera
    for obj in bpy.data.objects:
        if obj.type == 'FONT':
            for c in obj.constraints:
                if c.type == 'TRACK_TO':
                    c.target = cam
    bpy.context.view_layer.update()

    out_path = os.path.join(render_dir, f"q9v2_{i+1:02d}_{cam.name}.png")
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    results.append(f"Rendered: {cam.name} -> {out_path}")

blend_path = os.path.join(render_dir, "quality_push_v2.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
results.append(f"Saved: {blend_path}")

log_path = os.path.join(render_dir, "q9v2_render_log.txt")
with open(log_path, "w") as f:
    f.write("\\n".join(results))
""" % RENDER_DIR

    run_py(render_code, "Rendering all cameras")

    # Read render log
    time.sleep(1)
    try:
        with open(os.path.join(RENDER_DIR, "q9v2_render_log.txt")) as f:
            for line in f:
                print(f"  {line.strip()}")
    except:
        pass

    print("\n" + "=" * 70)
    print("QUALITY PUSH v2 COMPLETE")
    print(f"Renders: {RENDER_DIR}/q9v2_*.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
