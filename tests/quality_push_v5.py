#!/usr/bin/env python3
"""
QUALITY PUSH v5 — Cycles primary, grass ground plane, fixed asphalt for Cycles.

v4 findings:
  - Cycles PRODUCES VISIBLE SHADOWS (EEVEE does not)
  - Road_Cross + Road_Main both got Dark_Asphalt_v4 — but Cycles renders it MUCH darker
  - Black void around road = no geometry beyond curbs → need large ground plane
  - Asphalt base color 0.045 is too dark for Cycles (renders nearly black)
  - Sidewalk/curb got concrete material correctly

v5 approach:
  - Load bridge_test_scene.blend
  - Set lighting via bridge (tests addon baked defaults)
  - Add large grass ground plane (z=-0.02)
  - Asphalt material slightly lighter for Cycles (0.065 base)
  - Cycles 128 samples + denoising for quality-speed balance
  - Render all 6 cameras with Cycles
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

def main():
    print("=" * 70)
    print("QUALITY PUSH v5 — Cycles + grass ground + shadow showcase")
    print("=" * 70)

    # Load scene
    print("\n[1] Loading scene...")
    blend_path = os.path.join(RENDER_DIR, "bridge_test_scene.blend")
    run_py(f"""
import bpy
bpy.ops.wm.open_mainfile(filepath="{blend_path}")
print(f"Loaded: {{len(bpy.data.objects)}} objects")
""", "Load bridge_test_scene.blend")

    # Set lighting via bridge (tests baked addon defaults)
    print("\n[2] Setting lighting via addon...")
    resp = send("forensic_scene", {"action": "set_time_of_day", "time": "day"})
    result = resp.get("result", resp)
    print(f"  Lighting: {result}")

    # Apply materials
    print("\n[3] Applying materials...")

    # Asphalt — slightly lighter for Cycles (0.065 vs 0.045)
    run_py(r"""
import bpy

asphalt = bpy.data.materials.new("Asphalt_v5")
asphalt.use_nodes = True
tree = asphalt.node_tree
bsdf = tree.nodes["Principled BSDF"]
# Cycles renders darker than EEVEE — bump base color up
bsdf.inputs["Base Color"].default_value = (0.065, 0.065, 0.07, 1.0)
bsdf.inputs["Roughness"].default_value = 0.85
bsdf.inputs["Specular IOR Level"].default_value = 0.3

noise = tree.nodes.new("ShaderNodeTexNoise")
noise.location = (-500, 0)
noise.inputs["Scale"].default_value = 120
noise.inputs["Detail"].default_value = 14
noise.inputs["Roughness"].default_value = 0.75
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.location = (-300, 0)
ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.055, 1)
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[1].color = (0.09, 0.09, 0.095, 1)
ramp.color_ramp.elements[1].position = 0.65
tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
noise2 = tree.nodes.new("ShaderNodeTexNoise")
noise2.location = (-500, -300)
noise2.inputs["Scale"].default_value = 300
noise2.inputs["Detail"].default_value = 16
bump = tree.nodes.new("ShaderNodeBump")
bump.location = (-200, -300)
bump.inputs["Strength"].default_value = 0.12
tree.links.new(noise2.outputs["Fac"], bump.inputs["Height"])
tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

# Apply to road surfaces
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if 'road' in n:
        obj.data.materials.clear()
        obj.data.materials.append(asphalt)

# Sidewalk — light warm concrete
sidewalk = bpy.data.materials.new("Sidewalk_v5")
sidewalk.use_nodes = True
sw = sidewalk.node_tree.nodes["Principled BSDF"]
sw.inputs["Base Color"].default_value = (0.28, 0.26, 0.24, 1.0)
sw.inputs["Roughness"].default_value = 0.92

for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if 'curb' in n or 'sidewalk' in n:
        obj.data.materials.clear()
        obj.data.materials.append(sidewalk)

# White markings
white = bpy.data.materials.new("Marking_v5")
white.use_nodes = True
wb = white.node_tree.nodes["Principled BSDF"]
wb.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)
wb.inputs["Roughness"].default_value = 0.6

for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if any(kw in n for kw in ['stripe', 'crossstripe', 'stopbar']):
        obj.data.materials.clear()
        obj.data.materials.append(white)

print("Road materials applied")
""", "Asphalt + sidewalk + markings (Cycles-tuned)")

    # Grass ground plane
    run_py(r"""
import bpy

# Create large grass ground plane below road
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.03))
ground = bpy.context.active_object
ground.name = "Ground_Grass"

grass = bpy.data.materials.new("Grass_v5")
grass.use_nodes = True
tree = grass.node_tree
bsdf = tree.nodes["Principled BSDF"]
bsdf.inputs["Roughness"].default_value = 0.95

# Procedural grass color variation
noise = tree.nodes.new("ShaderNodeTexNoise")
noise.location = (-500, 0)
noise.inputs["Scale"].default_value = 15
noise.inputs["Detail"].default_value = 8
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.location = (-300, 0)
ramp.color_ramp.elements[0].color = (0.03, 0.08, 0.02, 1)
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[1].color = (0.06, 0.15, 0.04, 1)
ramp.color_ramp.elements[1].position = 0.65
tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

ground.data.materials.append(grass)
print("Grass ground plane added")
""", "Grass ground plane")

    # Vehicle materials
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

window = mk("V5_Window", (0.1, 0.15, 0.25, 0.6), roughness=0.02, alpha=0.6, transmission=0.9)
chrome = mk("V5_Chrome", (0.85, 0.85, 0.9, 1), metallic=1.0, roughness=0.05)
headlight = mk("V5_Headlight", (1, 0.97, 0.85, 1), roughness=0.02, emission=0.3, transmission=0.85)
taillight = mk("V5_Taillight", (0.9, 0.04, 0.02, 1), roughness=0.08, emission=0.5)
tire = mk("V5_Tire", (0.02, 0.02, 0.02, 1), roughness=0.95)

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
""", "Vehicle materials + clearcoat")

    # Text fix
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
""", "Text emission")

    # DOF
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
""", "DOF")

    # Render with CYCLES
    print("\n[4] Rendering with Cycles (all cameras)...")
    render_code = """
import bpy, os

render_dir = "%s"
os.makedirs(render_dir, exist_ok=True)
scene = bpy.context.scene

# Cycles config
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False

# Color management
scene.view_settings.view_transform = 'Filmic'
try:
    scene.view_settings.look = 'High Contrast'
except:
    scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = 0.3
scene.view_settings.gamma = 1.0

cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
results = []
results.append(f"Cycles 128spl, {len(cameras)} cameras")

for i, cam in enumerate(cameras[:6]):
    scene.camera = cam
    bpy.context.view_layer.update()
    out = os.path.join(render_dir, f"q9v5_{i+1:02d}_{cam.name}.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    results.append(f"Rendered: {cam.name} -> {out}")

blend = os.path.join(render_dir, "quality_push_v5.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
results.append(f"Saved: {blend}")

log = os.path.join(render_dir, "q9v5_log.txt")
with open(log, "w") as f:
    f.write("\\n".join(results))
""" % RENDER_DIR
    run_py(render_code, "Cycles render (may take 3-8 min for 6 cameras)")

    time.sleep(1)
    try:
        with open(os.path.join(RENDER_DIR, "q9v5_log.txt")) as f:
            for line in f:
                print(f"  {line.strip()}")
    except: pass

    print("\n" + "=" * 70)
    print("QUALITY PUSH v5 COMPLETE (Cycles)")
    print(f"Renders: {RENDER_DIR}/q9v5_*.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
