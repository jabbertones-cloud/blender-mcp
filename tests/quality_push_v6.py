#!/usr/bin/env python3
"""
QUALITY PUSH v6 — Fix intersection z-fighting, clean up visual noise, polish.

v5 findings (Cycles 128spl):
  - SHADOWS WORK (Cycles confirmed)
  - BLACK SQUARE at intersection center = z-fighting: Road_Main and Road_Cross
    are co-planar planes at z=0. Cycles can't resolve → renders black.
  - Red crosshair = impact_point torus (emission=5.0) floating in the black area
  - Debris pieces scattered around impact point
  - Green floating lines = traffic signal poles extending beyond road into grass
  - Text mirrored from some camera angles (witness, orbit)
  - DriverPOV was best render (7.5/10) — only angle where intersection center not visible

v6 approach:
  - Load quality_push_v5.blend (already has materials, grass, lighting)
  - DIAGNOSE: List all objects, their z-positions, materials at intersection
  - FIX 1: Raise Road_Cross z by 0.003 to break z-fighting
  - FIX 2: Hide impact markers, debris (distracting for showcase renders)
  - FIX 3: Hide/remove traffic signal poles that extend into grass
  - FIX 4: Ensure asphalt material on BOTH road meshes (verify)
  - FIX 5: Add 2 more cameras (Cam_Dramatic close-up, Cam_Wide establishing)
  - FIX 6: Improve vehicle body color (less toy-like)
  - Render all cameras with Cycles 128spl + denoising
"""
import socket, json, os, time

HOST, PORT, TIMEOUT = "127.0.0.1", 9876, 300.0  # 5min timeout for Cycles
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
            err = result.get("error", str(result))[:500]
            print(f"        {err}")
    return result if not ok else result

def main():
    print("=" * 70)
    print("QUALITY PUSH v6 — Fix z-fighting + visual cleanup + polish")
    print("=" * 70)

    # Step 1: Load v5 blend (has materials, grass, lighting already)
    print("\n[1] Loading v5 scene...")
    blend_path = os.path.join(RENDER_DIR, "quality_push_v5.blend")
    run_py(f"""
import bpy
bpy.ops.wm.open_mainfile(filepath="{blend_path}")
print(f"Loaded: {{len(bpy.data.objects)}} objects")
""", "Load quality_push_v5.blend")

    # Step 2: DIAGNOSTIC — understand every object at/near the intersection
    print("\n[2] Running diagnostic on intersection objects...")
    diag = run_py(r"""
import bpy
report = []
for obj in sorted(bpy.data.objects, key=lambda o: o.name):
    mats = [m.name for m in obj.data.materials] if hasattr(obj, 'data') and hasattr(obj.data, 'materials') else []
    loc = obj.location
    report.append(f"{obj.name:40s} type={obj.type:8s} loc=({loc.x:.3f},{loc.y:.3f},{loc.z:.3f}) mats={mats}")
print('\n'.join(report))
""", "Scene inventory")
    if isinstance(diag, dict) and diag.get("output"):
        for line in diag["output"].split("\n")[:50]:
            print(f"    {line}")

    # Step 3: FIX Z-FIGHTING — raise Road_Cross above Road_Main
    print("\n[3] Fixing z-fighting (Road_Cross offset)...")
    run_py(r"""
import bpy

fixed = []
for obj in bpy.data.objects:
    n = obj.name
    # Road_Cross sits on top of Road_Main — raise it to break z-fighting
    if n == "Road_Cross":
        obj.location.z += 0.003
        fixed.append(f"Road_Cross: z raised to {obj.location.z:.4f}")
    # Also raise crosswalk stripes slightly above the roads
    elif "CrossStripe" in n:
        if obj.location.z < 0.015:
            obj.location.z = 0.018
            fixed.append(f"{n}: z raised to 0.018")
    # Raise stop bars
    elif "StopBar" in n:
        if obj.location.z < 0.015:
            obj.location.z = 0.016
            fixed.append(f"{n}: z raised to 0.016")

print(f"Z-fighting fixes: {len(fixed)}")
for f in fixed[:10]:
    print(f"  {f}")
""", "Z-fighting fix (Road_Cross + stripes + bars)")

    # Step 4: HIDE visual noise — impact markers, debris, signal poles
    print("\n[4] Hiding visual noise (impact markers, debris, signals)...")
    run_py(r"""
import bpy

hidden = []
for obj in bpy.data.objects:
    n = obj.name.lower()
    hide = False
    # Impact point markers (red crosshair torus + cross)
    if 'impactpoint' in n or 'impact_point' in n or 'impact' in n.replace(' ', ''):
        hide = True
    # Debris scattered pieces
    elif n.startswith('debris'):
        hide = True
    # Fluid spill circles
    elif 'spill' in n:
        hide = True
    # Traffic signal poles that stick into grass
    elif 'signal' in n or 'traffic' in n:
        hide = True
    # Lane markers/rulers that extend beyond road
    elif 'ruler' in n or 'measurement' in n or 'measure' in n:
        hide = True

    if hide:
        obj.hide_render = True
        obj.hide_viewport = True
        hidden.append(obj.name)

# Also hide any children of hidden objects
for obj in bpy.data.objects:
    if obj.parent and obj.parent.hide_render:
        obj.hide_render = True
        obj.hide_viewport = True
        if obj.name not in hidden:
            hidden.append(obj.name)

print(f"Hidden {len(hidden)} objects:")
for h in hidden:
    print(f"  {h}")
""", "Hide impact markers + debris + signals")

    # Step 5: Verify and fix materials on BOTH road meshes
    print("\n[5] Verifying road materials...")
    run_py(r"""
import bpy

# Find or create the v5 asphalt material
asphalt = None
for mat in bpy.data.materials:
    if 'asphalt' in mat.name.lower() and 'v5' in mat.name.lower():
        asphalt = mat
        break
    elif 'asphalt' in mat.name.lower():
        asphalt = mat

if not asphalt:
    # Create fresh Cycles-tuned asphalt
    asphalt = bpy.data.materials.new("Asphalt_v6")
    asphalt.use_nodes = True
    tree = asphalt.node_tree
    bsdf = tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.085, 1.0)  # Lighter for Cycles
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    # Noise texture for variation
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-500, 0)
    noise.inputs["Scale"].default_value = 120
    noise.inputs["Detail"].default_value = 14
    noise.inputs["Roughness"].default_value = 0.75
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-300, 0)
    ramp.color_ramp.elements[0].color = (0.06, 0.06, 0.065, 1)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[1].color = (0.12, 0.12, 0.125, 1)
    ramp.color_ramp.elements[1].position = 0.7
    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    # Micro bump for texture
    noise2 = tree.nodes.new("ShaderNodeTexNoise")
    noise2.location = (-500, -300)
    noise2.inputs["Scale"].default_value = 300
    noise2.inputs["Detail"].default_value = 16
    bump = tree.nodes.new("ShaderNodeBump")
    bump.location = (-200, -300)
    bump.inputs["Strength"].default_value = 0.10
    tree.links.new(noise2.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    print("Created Asphalt_v6 (lighter for Cycles)")
else:
    # Bump up existing asphalt material brightness for Cycles
    if asphalt.use_nodes:
        bsdf = asphalt.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Check if base color ramp exists
            has_ramp = any(n.type == 'VALTORGB' for n in asphalt.node_tree.nodes)
            if has_ramp:
                for node in asphalt.node_tree.nodes:
                    if node.type == 'VALTORGB':
                        # Lighten both ramp endpoints
                        node.color_ramp.elements[0].color = (0.06, 0.06, 0.065, 1)
                        node.color_ramp.elements[1].color = (0.12, 0.12, 0.125, 1)
                        print(f"Lightened color ramp on {asphalt.name}")
            else:
                bsdf.inputs["Base Color"].default_value = (0.08, 0.08, 0.085, 1.0)
                print(f"Lightened base color on {asphalt.name}")

# Ensure both road meshes have the asphalt material
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name
    if n in ('Road_Main', 'Road_Cross'):
        if not obj.data.materials or obj.data.materials[0] != asphalt:
            obj.data.materials.clear()
            obj.data.materials.append(asphalt)
            print(f"Applied asphalt to {n}")
        else:
            print(f"{n} already has {obj.data.materials[0].name}")

print(f"Using asphalt material: {asphalt.name}")
""", "Verify/fix road materials (lighter for Cycles)")

    # Step 6: Vehicle body color improvement — less toy-like
    print("\n[6] Improving vehicle appearance...")
    run_py(r"""
import bpy

for mat in bpy.data.materials:
    if '_Body' not in mat.name or not mat.use_nodes:
        continue
    b = mat.node_tree.nodes.get("Principled BSDF")
    if not b:
        continue
    bc = list(b.inputs["Base Color"].default_value)
    name = mat.name.lower()

    # Make sedan (V1) a deeper navy blue instead of bright toy blue
    if 'v1' in name or 'sedan' in name:
        b.inputs["Base Color"].default_value = (0.02, 0.06, 0.22, 1.0)  # Deep navy
        b.inputs["Metallic"].default_value = 0.15
        b.inputs["Roughness"].default_value = 0.10
        try:
            b.inputs["Coat Weight"].default_value = 1.0
            b.inputs["Coat Roughness"].default_value = 0.02
        except: pass
        print(f"V1 body -> deep navy with clearcoat")

    # Make SUV (V2) a deeper burgundy/maroon instead of bright pink
    elif 'v2' in name or 'suv' in name:
        b.inputs["Base Color"].default_value = (0.18, 0.02, 0.02, 1.0)  # Deep burgundy
        b.inputs["Metallic"].default_value = 0.12
        b.inputs["Roughness"].default_value = 0.10
        try:
            b.inputs["Coat Weight"].default_value = 1.0
            b.inputs["Coat Roughness"].default_value = 0.02
        except: pass
        print(f"V2 body -> deep burgundy with clearcoat")

print("Vehicle colors updated")
""", "Vehicle body colors (deeper, more realistic)")

    # Step 7: Fix text — remove problematic ones, keep only what works
    print("\n[7] Fixing text objects...")
    run_py(r"""
import bpy

for obj in bpy.data.objects:
    if obj.type != 'FONT':
        continue

    # Remove all constraints (cause mirroring)
    for c in list(obj.constraints):
        obj.constraints.remove(c)

    # Make text double-sided by converting to mesh and adding solidify
    # Actually — for courtroom, text should face the active camera
    # For now: hide text that reads backwards from most angles
    # Keep text visible but add emission so it's readable from any lighting
    for slot in obj.material_slots:
        if slot.material and slot.material.use_nodes:
            b = slot.material.node_tree.nodes.get("Principled BSDF")
            if b:
                try:
                    b.inputs["Emission Strength"].default_value = 1.2
                    bc = b.inputs["Base Color"].default_value
                    b.inputs["Emission Color"].default_value = (bc[0], bc[1], bc[2], 1)
                except: pass

    # Add solidify modifier to make text visible from both sides
    has_solidify = any(m.type == 'SOLIDIFY' for m in obj.modifiers)
    if not has_solidify:
        mod = obj.modifiers.new("Solidify", "SOLIDIFY")
        mod.thickness = 0.05
        mod.offset = 0

print("Text objects fixed (emission + solidify for readability)")
""", "Text emission + solidify")

    # Step 8: Add 2 more cameras for variety
    print("\n[8] Adding additional cameras...")
    run_py(r"""
import bpy, math

# Check existing cameras
existing = [o for o in bpy.data.objects if o.type == 'CAMERA']
existing_names = [o.name.lower() for o in existing]
print(f"Existing cameras: {[o.name for o in existing]}")

added = []

# Cam_Dramatic — low angle looking up at vehicles (shows authority/drama)
if not any('dramatic' in n for n in existing_names):
    cam_data = bpy.data.cameras.new("Cam_Dramatic")
    cam_data.lens = 28  # Wide for drama
    cam_data.clip_start = 0.1
    cam_data.clip_end = 500
    cam_obj = bpy.data.objects.new("Cam_Dramatic", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (8, -6, 1.2)  # Low, close to ground
    cam_obj.rotation_euler = (math.radians(82), 0, math.radians(50))
    # DOF for drama
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = 10.0
    cam_data.dof.aperture_fstop = 2.0
    added.append("Cam_Dramatic")

# Cam_Wide — wide establishing shot showing full intersection + context
if not any('wide' in n for n in existing_names):
    cam_data = bpy.data.cameras.new("Cam_Wide")
    cam_data.lens = 24  # Wide angle
    cam_data.clip_start = 0.1
    cam_data.clip_end = 500
    cam_obj = bpy.data.objects.new("Cam_Wide", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = (25, -20, 12)
    cam_obj.rotation_euler = (math.radians(60), 0, math.radians(50))
    # No DOF for establishing shot — everything sharp
    cam_data.dof.use_dof = False
    added.append("Cam_Wide")

print(f"Added cameras: {added}")
print(f"Total cameras: {len([o for o in bpy.data.objects if o.type == 'CAMERA'])}")
""", "Add Cam_Dramatic + Cam_Wide")

    # Step 9: Render ALL cameras one at a time (separate commands to avoid timeout)
    print("\n[9] Rendering with Cycles (one camera at a time)...")

    # First, get camera list
    cam_resp = run_py(r"""
import bpy
cameras = [obj.name for obj in bpy.data.objects if obj.type == 'CAMERA']
print(','.join(cameras))
""", "Get camera list")

    camera_names = []
    if isinstance(cam_resp, dict) and cam_resp.get("output"):
        camera_names = [c.strip() for c in cam_resp["output"].strip().split(",") if c.strip()]
    print(f"  Cameras to render: {camera_names}")

    # Configure Cycles once
    run_py(f"""
import bpy, os
os.makedirs("{RENDER_DIR}", exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'Filmic'
try:
    scene.view_settings.look = 'High Contrast'
except:
    scene.view_settings.look = 'Medium High Contrast'
scene.view_settings.exposure = 0.3
scene.view_settings.gamma = 1.0
print("Cycles configured: 128spl, Filmic High Contrast, 1920x1080")
""", "Configure Cycles renderer")

    # Render each camera separately (avoids timeout)
    for i, cam_name in enumerate(camera_names[:8]):
        print(f"\n  Rendering camera {i+1}/{len(camera_names)}: {cam_name}...")
        render_code = f"""
import bpy, os
scene = bpy.context.scene
cam = bpy.data.objects.get("{cam_name}")
if cam and cam.type == 'CAMERA':
    scene.camera = cam
    bpy.context.view_layer.update()
    out = os.path.join("{RENDER_DIR}", "q9v6_{i+1:02d}_{cam_name}.png")
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print(f"DONE: {{out}}")
else:
    print(f"Camera not found: {cam_name}")
"""
        result = run_py(render_code, f"Render {cam_name}")
        if isinstance(result, dict) and result.get("output"):
            print(f"    {result['output'].strip()}")

    # Save blend
    run_py(f"""
import bpy, os
blend = os.path.join("{RENDER_DIR}", "quality_push_v6.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend)
print(f"Saved: {{blend}}")
""", "Save v6 blend")

    # Write render log
    run_py(f"""
import os
render_dir = "{RENDER_DIR}"
renders = sorted([f for f in os.listdir(render_dir) if f.startswith("q9v6_") and f.endswith(".png")])
log = os.path.join(render_dir, "q9v6_log.txt")
with open(log, "w") as f:
    f.write(f"Quality Push v6 — Cycles 128spl\\n")
    f.write(f"Renders: {{len(renders)}}\\n")
    for r in renders:
        size = os.path.getsize(os.path.join(render_dir, r))
        f.write(f"  {{r}} ({{size//1024}} KB)\\n")
print(f"Log written: {{log}}")
print(f"Total renders: {{len(renders)}}")
""", "Write render log")

    print("\n" + "=" * 70)
    print("QUALITY PUSH v6 COMPLETE (Cycles)")
    print(f"Renders: {RENDER_DIR}/q9v6_*.png")
    print("Key fixes: z-fighting, impact markers hidden, lighter asphalt, vehicle colors")
    print("=" * 70)


if __name__ == "__main__":
    main()
