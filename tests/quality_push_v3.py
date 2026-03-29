#!/usr/bin/env python3
"""
QUALITY PUSH v3 — Aggressive fixes for blown-out scene.

v2 problems diagnosed:
  1. Sky strength 0.8 + sun energy 4 = still blown out (white void)
  2. Shadow catcher alone doesn't produce visible shadows — need opaque dark ground
  3. Billboard TRACK_TO to active camera = mirrored text from some angles
  4. Courtroom overlay as 3D ground text = unreadable when viewed from wrong angle
  5. Asphalt material 'Asphalt_Main' may not exist on the road mesh
  6. No visible blue sky — Nishita sky washed to white at high strength

v3 fixes:
  - Sun energy 1.5, sky strength 0.25 — dramatically darker
  - DELETE shadow catcher, replace road surface material with dark asphalt directly
  - Remove billboard constraints — fix text orientation per-render via rotation
  - Courtroom overlay: camera-parented plane with transparent text texture
  - Force dark asphalt on ALL road meshes regardless of material name
  - Add visible gradient sky at low strength
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
            err = result.get("error", str(result))[:400]
            print(f"        {err}")
    return ok

def main():
    print("=" * 70)
    print("QUALITY PUSH v3 — Aggressive lighting & material fix")
    print("=" * 70)

    # Step 1: Load the ORIGINAL bridge test scene (not the blown-out v2)
    print("\n[1] Loading original bridge_test_scene.blend...")
    blend_path = os.path.join(RENDER_DIR, "bridge_test_scene.blend")
    if not os.path.exists(blend_path):
        print(f"  ERROR: {blend_path} not found.")
        return
    run_py(f"""
import bpy
bpy.ops.wm.open_mainfile(filepath="{blend_path}")
print(f"Loaded: {{len(bpy.data.objects)}} objects")
""", "Load scene")

    # Verify
    run_py("""
import bpy
cams = [o.name for o in bpy.data.objects if o.type == 'CAMERA']
objs = len(bpy.data.objects)
out = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v3_check.txt"
with open(out, "w") as f:
    f.write(f"Cameras: {cams}\\nObjects: {objs}\\n")
    for m in bpy.data.materials:
        f.write(f"  Mat: {m.name}\\n")
""", "Verify scene")

    time.sleep(0.5)
    try:
        with open(os.path.join(RENDER_DIR, "v3_check.txt")) as f:
            for line in f.readlines()[:6]:
                print(f"  {line.strip()}")
    except: pass

    # ══════════════════════════════════════════════════════════════════════
    # Step 2: ENHANCEMENTS (fixed)
    # ══════════════════════════════════════════════════════════════════════
    print("\n[2] Applying v3 enhancements...")

    # 2a: SKY — low strength, visible blue gradient
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
sky.sun_elevation = math.radians(35)
sky.sun_rotation = math.radians(220)
sky.ground_albedo = 0.15  # Dark ground reflection
tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.25  # MUCH LOWER — v2 was 0.8
tree.links.new(bg.outputs["Background"], output.inputs["Surface"])
""", "Sky (strength=0.25)")

    # 2b: SUN — energy 1.5 (v2 was 4, v1 was 8)
    run_py("""
import bpy, math

for obj in bpy.data.objects:
    if obj.type == 'LIGHT' and obj.data.type == 'SUN':
        obj.data.energy = 1.5  # MUCH LOWER
        obj.data.color = (1.0, 0.95, 0.88)
        obj.rotation_euler = (math.radians(42), math.radians(10), math.radians(220))
        obj.data.use_shadow = True
        try:
            obj.data.shadow_soft_size = 0.02
        except: pass
        break

# Fill light — very subtle
fill = bpy.data.lights.new(name="Fill_Sky", type='SUN')
fill.energy = 0.3  # Very subtle fill
fill.color = (0.7, 0.8, 1.0)
fill.use_shadow = False
fill_obj = bpy.data.objects.new("Fill_Sky", fill)
bpy.context.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(60), 0, math.radians(40))
""", "Sun (energy=1.5) + subtle fill")

    # 2c: DARK ASPHALT on ALL road surfaces (no shadow catcher — real ground)
    run_py(r"""
import bpy

# Create a proper dark asphalt material
asphalt = bpy.data.materials.new("Dark_Asphalt_v3")
asphalt.use_nodes = True
tree = asphalt.node_tree
bsdf = tree.nodes["Principled BSDF"]

# Base color: dark gray asphalt
bsdf.inputs["Base Color"].default_value = (0.045, 0.045, 0.05, 1.0)
bsdf.inputs["Roughness"].default_value = 0.85
bsdf.inputs["Specular IOR Level"].default_value = 0.3

# Noise texture for asphalt grain
noise = tree.nodes.new("ShaderNodeTexNoise")
noise.location = (-500, 0)
noise.inputs["Scale"].default_value = 120
noise.inputs["Detail"].default_value = 14
noise.inputs["Roughness"].default_value = 0.75

# Color ramp for subtle variation
ramp = tree.nodes.new("ShaderNodeValToRGB")
ramp.location = (-300, 0)
ramp.color_ramp.elements[0].color = (0.03, 0.03, 0.035, 1)
ramp.color_ramp.elements[0].position = 0.35
ramp.color_ramp.elements[1].color = (0.07, 0.07, 0.075, 1)
ramp.color_ramp.elements[1].position = 0.65

tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

# Bump for micro surface
noise2 = tree.nodes.new("ShaderNodeTexNoise")
noise2.location = (-500, -300)
noise2.inputs["Scale"].default_value = 300
noise2.inputs["Detail"].default_value = 16
bump = tree.nodes.new("ShaderNodeBump")
bump.location = (-200, -300)
bump.inputs["Strength"].default_value = 0.15
tree.links.new(noise2.outputs["Fac"], bump.inputs["Height"])
tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

# Apply to ALL mesh objects that look like road/ground
applied = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    n = obj.name.lower()
    # Road surfaces, lane markers parent mesh, ground
    if any(kw in n for kw in ['road', 'asphalt', 'ground', 'lane', 'intersection']):
        # Don't touch lane marking strips — only the main road body
        if 'stripe' in n or 'mark' in n or 'line' in n or 'crosswalk' in n:
            continue
        obj.data.materials.clear()
        obj.data.materials.append(asphalt)
        applied += 1

print(f"Applied dark asphalt to {applied} objects")
""", "Dark asphalt (0.045 base color)")

    # 2d: Ensure crosswalk/lane markings stay white and crisp
    run_py("""
import bpy

white_mat = bpy.data.materials.new("Road_Marking_White")
white_mat.use_nodes = True
b = white_mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1.0)
b.inputs["Roughness"].default_value = 0.6
b.inputs["Emission Strength"].default_value = 0.05  # Very slight glow for visibility

applied = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if any(kw in n for kw in ['stripe', 'crosswalk', 'marking', 'line_', 'lane_mark']):
        obj.data.materials.clear()
        obj.data.materials.append(white_mat)
        applied += 1

print(f"Applied white marking to {applied} objects")
""", "White road markings")

    # 2e: Vehicle multi-material (windows, chrome, lights) + clearcoat
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

window = mk("V3_Window", (0.1, 0.15, 0.25, 0.6), roughness=0.02, alpha=0.6, transmission=0.9)
chrome = mk("V3_Chrome", (0.85, 0.85, 0.9, 1), metallic=1.0, roughness=0.05)
headlight = mk("V3_Headlight", (1, 0.97, 0.85, 1), roughness=0.02, emission=0.3, transmission=0.85)
taillight = mk("V3_Taillight", (0.9, 0.04, 0.02, 1), roughness=0.08, emission=0.5)
tire_mat = mk("V3_Tire", (0.02, 0.02, 0.02, 1), roughness=0.95)

for veh in bpy.data.objects:
    if veh.type != 'EMPTY' or ('V1' not in veh.name and 'V2' not in veh.name):
        continue
    for child in veh.children_recursive:
        if child.type != 'MESH': continue
        n = child.name.lower()
        if 'window' in n or 'windshield' in n or 'glass' in n:
            child.data.materials.clear()
            child.data.materials.append(window)
        elif 'headlight' in n or 'lamp_front' in n or 'light_front' in n:
            child.data.materials.clear()
            child.data.materials.append(headlight)
        elif 'taillight' in n or 'lamp_rear' in n or 'light_rear' in n:
            child.data.materials.clear()
            child.data.materials.append(taillight)
        elif 'bumper' in n or 'grill' in n or 'grille' in n:
            child.data.materials.clear()
            child.data.materials.append(chrome)
        elif 'wheel' in n or 'tire' in n:
            child.data.materials.clear()
            child.data.materials.append(tire_mat)

# Clearcoat on body paint
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
""", "Vehicle materials + clearcoat + tires")

    # 2f: Text annotations — emissive, no billboard (fixed orientation)
    # Remove existing TRACK_TO constraints that cause mirroring
    run_py("""
import bpy

for obj in bpy.data.objects:
    if obj.type == 'FONT':
        # Remove broken TRACK_TO constraints
        for c in list(obj.constraints):
            obj.constraints.remove(c)
        # Make text emissive so it's readable against any background
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                b = slot.material.node_tree.nodes.get("Principled BSDF")
                if b:
                    try:
                        b.inputs["Emission Strength"].default_value = 0.8
                        bc = b.inputs["Base Color"].default_value
                        b.inputs["Emission Color"].default_value = (bc[0], bc[1], bc[2], 1)
                    except: pass
print("Text constraints removed, emission added")
""", "Fix text (remove TRACK_TO, add emission)")

    # 2g: Depth of field on select cameras
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

    # 2h: Courtroom HUD — parent to EACH camera as a flat plane
    # Instead of ground text, we create a HUD overlay parented to camera
    run_py(r"""
import bpy

# Create exhibit label text
bpy.ops.object.text_add(location=(0, 0, 0))
label = bpy.context.active_object
label.name = "HUD_ExhibitLabel"
label.data.body = "EXHIBIT A — Collision Reconstruction\nCase No. 2024-CV-03847  |  Smith v. Johnson"
label.data.size = 0.018
label.data.align_x = 'LEFT'
label.data.align_y = 'TOP'

# White emissive material
mat = bpy.data.materials.new("HUD_Mat")
mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1, 1, 1, 1)
b.inputs["Emission Strength"].default_value = 2.0
b.inputs["Emission Color"].default_value = (1, 1, 1, 1)
label.data.materials.append(mat)

# Disclaimer text
bpy.ops.object.text_add(location=(0, 0, 0))
disc = bpy.context.active_object
disc.name = "HUD_Disclaimer"
disc.data.body = "Demonstrative exhibit — vehicle positions based on police report and physical evidence."
disc.data.size = 0.012
disc.data.align_x = 'CENTER'
disc.data.align_y = 'BOTTOM'

d_mat = bpy.data.materials.new("HUD_Disc_Mat")
d_mat.use_nodes = True
b2 = d_mat.node_tree.nodes["Principled BSDF"]
b2.inputs["Base Color"].default_value = (0.7, 0.7, 0.7, 1)
b2.inputs["Emission Strength"].default_value = 1.5
b2.inputs["Emission Color"].default_value = (0.7, 0.7, 0.7, 1)
disc.data.materials.append(d_mat)

# Scale bar in scene (3D, near origin) — flat on ground
bpy.ops.mesh.primitive_cube_add(size=1, location=(18, -18, 0.03))
bar = bpy.context.active_object
bar.name = "ScaleBar_5m"
bar.scale = (5.0, 0.08, 0.015)
bar_mat = bpy.data.materials.new("ScaleBar_Mat")
bar_mat.use_nodes = True
bm = bar_mat.node_tree.nodes["Principled BSDF"]
bm.inputs["Base Color"].default_value = (1, 1, 0.2, 1)
bm.inputs["Emission Strength"].default_value = 1.0
bm.inputs["Emission Color"].default_value = (1, 1, 0.2, 1)
bar.data.materials.append(bar_mat)

# Scale bar tick marks
for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(18 - 2.5 + i, -18, 0.06))
    tick = bpy.context.active_object
    tick.name = f"ScaleBar_Tick_{i}"
    tick.scale = (0.02, 0.15, 0.03)
    tick.data.materials.append(bar_mat)

# Scale label
bpy.ops.object.text_add(location=(18, -18.5, 0.1), rotation=(1.5708, 0, 0))
sl = bpy.context.active_object
sl.name = "ScaleBar_Text"
sl.data.body = "5 meters"
sl.data.size = 0.25
sl.data.align_x = 'CENTER'
sl_mat = bpy.data.materials.new("ScaleLabel_Mat")
sl_mat.use_nodes = True
sb = sl_mat.node_tree.nodes["Principled BSDF"]
sb.inputs["Base Color"].default_value = (1, 1, 0.2, 1)
sb.inputs["Emission Strength"].default_value = 1.0
sb.inputs["Emission Color"].default_value = (1, 1, 0.2, 1)
sl.data.materials.append(sl_mat)

# North arrow (3D compass in scene corner)
bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=1.2, location=(20, 16, 0.6))
arrow = bpy.context.active_object
arrow.name = "Compass_North"
a_mat = bpy.data.materials.new("Compass_Mat")
a_mat.use_nodes = True
ab = a_mat.node_tree.nodes["Principled BSDF"]
ab.inputs["Base Color"].default_value = (1, 0.15, 0.1, 1)
ab.inputs["Emission Strength"].default_value = 0.8
ab.inputs["Emission Color"].default_value = (1, 0.15, 0.1, 1)
arrow.data.materials.append(a_mat)

bpy.ops.object.text_add(location=(20, 17.3, 0.6), rotation=(1.5708, 0, 0))
cn = bpy.context.active_object
cn.name = "Compass_N"
cn.data.body = "N"
cn.data.size = 0.4
cn.data.align_x = 'CENTER'
cn.data.materials.append(a_mat)

print("Courtroom HUD + scene markers created")
""", "Courtroom HUD overlay")

    # 2i: Dramatic low camera
    run_py("""
import bpy, math
# Check if it already exists
existing = bpy.data.objects.get("Cam_Dramatic")
if existing:
    bpy.data.objects.remove(existing, do_unlink=True)

bpy.ops.object.camera_add(location=(12, -10, 1.8))
cam = bpy.context.active_object
cam.name = "Cam_Dramatic"
cam.data.lens = 35
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 14
cam.data.dof.aperture_fstop = 2.0

# Point at impact zone
target = bpy.data.objects.get("Cam_Dramatic_Target")
if not target:
    bpy.ops.object.empty_add(location=(0, 0, 0.5))
    target = bpy.context.active_object
    target.name = "Cam_Dramatic_Target"

tc = cam.constraints.new('TRACK_TO')
tc.target = target
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'

# Also add a wide establishing shot
existing2 = bpy.data.objects.get("Cam_Wide")
if existing2:
    bpy.data.objects.remove(existing2, do_unlink=True)

bpy.ops.object.camera_add(location=(25, -25, 18))
wide = bpy.context.active_object
wide.name = "Cam_Wide"
wide.data.lens = 28
wide.data.dof.use_dof = False

tc2 = wide.constraints.new('TRACK_TO')
tc2.target = target
tc2.track_axis = 'TRACK_NEGATIVE_Z'
tc2.up_axis = 'UP_Y'
""", "Dramatic + wide cameras")

    # 2j: EEVEE render quality — Filmic, high contrast
    run_py("""
import bpy

scene = bpy.context.scene
eevee = scene.eevee
eevee.use_raytracing = True
eevee.ray_tracing_method = 'SCREEN'
eevee.use_shadows = True
eevee.shadow_ray_count = 3
eevee.shadow_step_count = 16
eevee.shadow_resolution_scale = 1.0
eevee.use_volumetric_shadows = True

# COLOR MANAGEMENT — critical for not looking washed out
scene.view_settings.view_transform = 'Filmic'
try:
    scene.view_settings.look = 'High Contrast'
except:
    try:
        scene.view_settings.look = 'Medium High Contrast'
    except: pass
scene.view_settings.exposure = 0.3  # Slight boost
scene.view_settings.gamma = 1.0

# Render settings
scene.render.film_transparent = False  # Solid sky background
scene.render.use_high_quality_normals = True
""", "EEVEE quality + Filmic High Contrast")

    # ══════════════════════════════════════════════════════════════════════
    # Step 3: RENDER
    # ══════════════════════════════════════════════════════════════════════
    print("\n[3] Rendering v3...")

    render_code = """
import bpy, os

render_dir = "%s"
os.makedirs(render_dir, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'

# Get HUD objects
hud_label = bpy.data.objects.get("HUD_ExhibitLabel")
hud_disc = bpy.data.objects.get("HUD_Disclaimer")

cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
results = []
results.append(f"Found {len(cameras)} cameras: {[c.name for c in cameras]}")

for i, cam in enumerate(cameras[:7]):
    scene.camera = cam

    # Parent HUD text to this camera for screen-space effect
    if hud_label:
        hud_label.parent = cam
        hud_label.location = (-0.16, -0.085, -0.3)  # Top-left in camera view
        hud_label.rotation_euler = (0, 0, 0)
        hud_label.scale = (1, 1, 1)
    if hud_disc:
        hud_disc.parent = cam
        hud_disc.location = (0, 0.095, -0.3)  # Bottom-center in camera view
        hud_disc.rotation_euler = (0, 0, 0)
        hud_disc.scale = (1, 1, 1)

    bpy.context.view_layer.update()

    out_path = os.path.join(render_dir, f"q9v3_{i+1:02d}_{cam.name}.png")
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    results.append(f"Rendered: {cam.name} -> {out_path}")

# Unparent HUD
if hud_label:
    hud_label.parent = None
if hud_disc:
    hud_disc.parent = None

blend_path = os.path.join(render_dir, "quality_push_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
results.append(f"Saved: {blend_path}")

log_path = os.path.join(render_dir, "q9v3_render_log.txt")
with open(log_path, "w") as f:
    f.write("\\n".join(results))
""" % RENDER_DIR

    run_py(render_code, "Rendering all cameras")

    time.sleep(1)
    try:
        with open(os.path.join(RENDER_DIR, "q9v3_render_log.txt")) as f:
            for line in f:
                print(f"  {line.strip()}")
    except: pass

    print("\n" + "=" * 70)
    print("QUALITY PUSH v3 COMPLETE")
    print(f"Renders: {RENDER_DIR}/q9v3_*.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
