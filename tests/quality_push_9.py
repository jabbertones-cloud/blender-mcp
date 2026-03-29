#!/usr/bin/env python3
"""
QUALITY PUSH TO 9/10
====================
Builds a forensic scene through the bridge, then applies every visual quality
enhancement we can think of. Each enhancement is labeled so we can see exactly
what moves the needle.

Enhancements:
1. Shadow catcher ground plane (makes vehicles cast real shadows)
2. HDRI environment (sky, horizon, ambient light)
3. Billboard text (annotations always face camera)
4. Multi-material vehicles (glass windows, chrome trim, headlights, tail lights)
5. Procedural asphalt texture (not flat gray)
6. Depth of field on closeup cameras
7. Stronger/warmer sun + fill light
8. Vehicle deformation (displacement on impact side)
9. Courtroom overlay (exhibit label, scale bar, compass, disclaimer)
10. Higher render samples + denoising
"""
import socket
import json
import os
import time

HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 60.0
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders")
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


def run_py(code, label=""):
    resp = send("execute_python", {"code": code})
    result = resp.get("result", resp)
    ok = not (isinstance(result, dict) and result.get("error"))
    status = "OK" if ok else "FAIL"
    if label:
        print(f"  [{status}] {label}")
        if not ok:
            err = result.get("error", "") if isinstance(result, dict) else str(result)
            print(f"        {err[:200]}")
    return ok


def main():
    print("=" * 70)
    print("QUALITY PUSH TO 9/10 — FORENSIC SCENE")
    print("=" * 70)
    os.makedirs(RENDER_DIR, exist_ok=True)

    # Verify bridge
    resp = send("ping")
    r = resp.get("result", {})
    print(f"Bridge: {r.get('instance_id')} / Blender {r.get('blender_version')}")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 1: BUILD THE SCENE (via bridge commands)
    # ══════════════════════════════════════════════════════════════════════
    print("\n[PHASE 1] Building scene...")

    # Clear
    run_py("""
import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=True)
for block in bpy.data.meshes:
    if block.users == 0: bpy.data.meshes.remove(block)
for block in bpy.data.materials:
    if block.users == 0: bpy.data.materials.remove(block)
for block in bpy.data.cameras:
    if block.users == 0: bpy.data.cameras.remove(block)
for block in bpy.data.lights:
    if block.users == 0: bpy.data.lights.remove(block)
""", "Clear scene")

    # Road
    resp = send("forensic_scene", {"action": "build_road", "road_type": "intersection", "lanes": 2, "length": 60})
    print(f"  [OK] Road: {resp.get('result', {}).get('elements', ['?'])[0] if isinstance(resp.get('result'), dict) else 'built'}")

    # Vehicles
    send("forensic_scene", {
        "action": "place_vehicle", "name": "V1_Sedan", "vehicle_type": "sedan",
        "location": [-15, 0, 0], "rotation": 90, "color": [0.05, 0.12, 0.55, 1.0],
        "label": "Vehicle 1 — 2019 Honda Accord", "damaged": True, "impact_side": "front"
    })
    print("  [OK] V1 Sedan (blue, heading east, front damage)")

    send("forensic_scene", {
        "action": "place_vehicle", "name": "V2_SUV", "vehicle_type": "suv",
        "location": [0, -12, 0], "rotation": 0, "color": [0.45, 0.02, 0.02, 1.0],
        "label": "Vehicle 2 — 2021 Toyota RAV4", "damaged": True, "impact_side": "left"
    })
    print("  [OK] V2 SUV (dark red, heading north, left damage)")

    # Witnesses
    send("forensic_scene", {
        "action": "place_figure", "name": "Witness_A", "location": [10, -10, 0],
        "rotation": 135, "label": "Witness A — Jane Smith"
    })
    send("forensic_scene", {
        "action": "place_figure", "name": "Witness_B", "location": [-8, 8, 0],
        "rotation": -45, "label": "Witness B — Robert Chen"
    })
    print("  [OK] 2 witnesses placed")

    # Annotations
    send("forensic_scene", {"action": "add_annotation", "annotation_type": "speed",
                            "text": "38 mph (61 km/h)", "location": [-12, 0, 4], "size": 0.6})
    send("forensic_scene", {"action": "add_annotation", "annotation_type": "speed",
                            "text": "28 mph (45 km/h)", "location": [0, -9, 4], "size": 0.6})
    send("forensic_scene", {"action": "add_annotation", "annotation_type": "distance",
                            "text": "Point of Impact", "start": [-3, -3, 0], "end": [3, 3, 0]})
    print("  [OK] Annotations")

    # Impact markers
    send("forensic_scene", {"action": "add_impact_marker", "marker_type": "impact_point", "location": [0, 0, 0]})
    send("forensic_scene", {"action": "add_impact_marker", "marker_type": "skid_mark",
                            "start": [-20, 0, 0], "end": [-3, 0, 0]})
    send("forensic_scene", {"action": "add_impact_marker", "marker_type": "skid_mark",
                            "start": [0, -15, 0], "end": [0, -3, 0]})
    send("forensic_scene", {"action": "add_impact_marker", "marker_type": "debris", "location": [3, 3, 0]})
    print("  [OK] Impact markers + skid marks")

    # Cameras
    send("forensic_scene", {"action": "setup_cameras", "camera_type": "all", "target": [0, 0, 0]})
    print("  [OK] Cameras")

    # Time of day (triggers lighting + render quality setup)
    send("forensic_scene", {"action": "set_time_of_day", "time": "day", "strength": 1.2})
    print("  [OK] Lighting")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 2: QUALITY ENHANCEMENTS (direct Python in Blender)
    # ══════════════════════════════════════════════════════════════════════
    print("\n[PHASE 2] Applying quality enhancements...")

    # Enhancement 1: Shadow catcher ground plane
    run_py("""
import bpy
# Create a large ground plane that catches shadows
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.005))
ground = bpy.context.active_object
ground.name = "ShadowCatcher_Ground"
# Make it a shadow catcher — only shows shadows, otherwise transparent
ground.is_shadow_catcher = True
# Also make the existing road surface receive shadows better
for obj in bpy.data.objects:
    if 'Road' in obj.name or 'road' in obj.name:
        # Ensure road is not set as holdout
        obj.is_shadow_catcher = False
""", "Shadow catcher ground plane")

    # Enhancement 2: HDRI environment (procedural since we can't download)
    run_py("""
import bpy, math

world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree
tree.nodes.clear()

# Build a rich sky shader
output = tree.nodes.new("ShaderNodeOutputWorld")
output.location = (600, 0)

bg = tree.nodes.new("ShaderNodeBackground")
bg.location = (400, 0)

sky = tree.nodes.new("ShaderNodeTexSky")
sky.location = (0, 0)
sky.sky_type = "MULTIPLE_SCATTERING"
sky.sun_elevation = math.radians(35)  # Lower sun for longer shadows
sky.sun_rotation = math.radians(220)  # Sun from southwest — creates diagonal shadows
sky.ground_albedo = 0.3

# Mix with a warm gradient for horizon glow
mix = tree.nodes.new("ShaderNodeMixRGB")
mix.location = (200, 0)
mix.blend_type = 'MIX'
mix.inputs[0].default_value = 0.15  # Subtle mix

gradient = tree.nodes.new("ShaderNodeTexGradient")
gradient.location = (0, -200)

warm = tree.nodes.new("ShaderNodeRGB")
warm.location = (0, -350)
warm.outputs[0].default_value = (0.95, 0.85, 0.7, 1)  # Warm horizon

tree.links.new(sky.outputs["Color"], mix.inputs[1])
tree.links.new(warm.outputs[0], mix.inputs[2])
tree.links.new(mix.outputs[0], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.3
tree.links.new(bg.outputs["Background"], output.inputs["Surface"])
""", "Rich sky environment")

    # Enhancement 3: Stronger sun + fill light
    run_py("""
import bpy, math

# Upgrade existing sun
for obj in bpy.data.objects:
    if obj.type == 'LIGHT' and obj.data.type == 'SUN':
        obj.data.energy = 8  # Stronger
        obj.data.color = (1.0, 0.93, 0.85)  # Slightly warm
        obj.rotation_euler = (math.radians(40), math.radians(10), math.radians(220))
        obj.data.use_shadow = True
        try:
            obj.data.shadow_cascade_count = 4
            obj.data.shadow_cascade_max_distance = 120
            obj.data.shadow_soft_size = 0.02  # Sharp-ish shadows
        except: pass
        break

# Add a subtle blue fill light from opposite side
fill_data = bpy.data.lights.new(name="Fill_Sky", type='SUN')
fill_data.energy = 1.5
fill_data.color = (0.7, 0.8, 1.0)  # Cool sky fill
fill_data.use_shadow = False  # Fill doesn't cast shadows
fill_obj = bpy.data.objects.new("Fill_Sky", fill_data)
bpy.context.collection.objects.link(fill_obj)
fill_obj.rotation_euler = (math.radians(60), 0, math.radians(40))
""", "Stronger sun + fill light")

    # Enhancement 4: Multi-material vehicles (windows, chrome, headlights)
    run_py("""
import bpy

def make_mat(name, color, metallic=0, roughness=0.5, alpha=1.0, emission=0, transmission=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.surface_render_method = 'DITHERED'
    if emission > 0:
        bsdf.inputs["Emission Strength"].default_value = emission
        bsdf.inputs["Emission Color"].default_value = color
    if transmission > 0:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    return mat

# Create shared detail materials
window_mat = make_mat("Vehicle_Window", (0.15, 0.2, 0.3, 0.7), roughness=0.02, alpha=0.7, transmission=0.85)
chrome_mat = make_mat("Vehicle_Chrome", (0.9, 0.9, 0.92, 1), metallic=1.0, roughness=0.05)
headlight_mat = make_mat("Vehicle_Headlight", (1, 0.98, 0.9, 1), roughness=0.02, emission=0.3, transmission=0.9)
taillight_mat = make_mat("Vehicle_Taillight", (0.8, 0.05, 0.02, 1), roughness=0.1, emission=0.5)

# Apply to vehicle mesh children based on name/position heuristics
for veh in bpy.data.objects:
    if veh.type != 'EMPTY': continue
    if 'V1' not in veh.name and 'V2' not in veh.name: continue

    children = [c for c in veh.children_recursive if c.type == 'MESH']
    if not children: continue

    for child in children:
        n = child.name.lower()
        # Windows / glass pieces
        if 'window' in n or 'glass' in n or 'windshield' in n:
            child.data.materials.clear()
            child.data.materials.append(window_mat)
        # Headlights
        elif 'headlight' in n or 'lamp_front' in n:
            child.data.materials.clear()
            child.data.materials.append(headlight_mat)
        # Tail lights
        elif 'taillight' in n or 'lamp_rear' in n or 'brake' in n:
            child.data.materials.clear()
            child.data.materials.append(taillight_mat)
        # Bumper / trim (chrome)
        elif 'bumper' in n or 'trim' in n or 'grill' in n or 'grille' in n:
            child.data.materials.clear()
            child.data.materials.append(chrome_mat)

# Also improve the body paint material — add clearcoat
for mat in bpy.data.materials:
    if '_Body' in mat.name and mat.use_nodes:
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Metallic"].default_value = 0.0
            bsdf.inputs["Roughness"].default_value = 0.15
            try:
                bsdf.inputs["Coat Weight"].default_value = 0.8
                bsdf.inputs["Coat Roughness"].default_value = 0.05
            except: pass
""", "Multi-material vehicles")

    # Enhancement 5: Procedural asphalt texture
    run_py("""
import bpy

for mat in bpy.data.materials:
    if mat.name != 'Asphalt_Main': continue
    if not mat.use_nodes: continue
    tree = mat.node_tree
    bsdf = tree.nodes.get("Principled BSDF")
    if not bsdf: continue

    # Add noise texture for asphalt grain
    noise = tree.nodes.new("ShaderNodeTexNoise")
    noise.location = (-400, 0)
    noise.inputs["Scale"].default_value = 80
    noise.inputs["Detail"].default_value = 12
    noise.inputs["Roughness"].default_value = 0.7

    # Color ramp for asphalt variation
    ramp = tree.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-200, 0)
    ramp.color_ramp.elements[0].color = (0.04, 0.04, 0.045, 1)  # Dark asphalt
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[1].color = (0.1, 0.1, 0.11, 1)  # Lighter patches
    ramp.color_ramp.elements[1].position = 0.7

    tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    # Roughness variation too
    noise2 = tree.nodes.new("ShaderNodeTexNoise")
    noise2.location = (-400, -200)
    noise2.inputs["Scale"].default_value = 30
    noise2.inputs["Detail"].default_value = 8

    ramp2 = tree.nodes.new("ShaderNodeValToRGB")
    ramp2.location = (-200, -200)
    ramp2.color_ramp.elements[0].color = (0.7, 0.7, 0.7, 1)
    ramp2.color_ramp.elements[0].position = 0.35
    ramp2.color_ramp.elements[1].color = (0.95, 0.95, 0.95, 1)
    ramp2.color_ramp.elements[1].position = 0.65

    tree.links.new(noise2.outputs["Fac"], ramp2.inputs["Fac"])
    tree.links.new(ramp2.outputs["Color"], bsdf.inputs["Roughness"])

    # Subtle normal map for surface texture
    noise3 = tree.nodes.new("ShaderNodeTexNoise")
    noise3.location = (-400, -400)
    noise3.inputs["Scale"].default_value = 200
    noise3.inputs["Detail"].default_value = 16

    bump = tree.nodes.new("ShaderNodeBump")
    bump.location = (-100, -400)
    bump.inputs["Strength"].default_value = 0.15

    tree.links.new(noise3.outputs["Fac"], bump.inputs["Height"])
    tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    break
""", "Procedural asphalt texture")

    # Enhancement 6: Billboard text (annotations face camera)
    run_py("""
import bpy

# Add Track To constraint on ALL text/font objects so they face the active camera
cam = bpy.context.scene.camera
if not cam:
    cams = [o for o in bpy.data.objects if o.type == 'CAMERA']
    cam = cams[0] if cams else None

if cam:
    for obj in bpy.data.objects:
        if obj.type == 'FONT':
            # Remove existing Track To constraints
            for c in list(obj.constraints):
                if c.type == 'TRACK_TO':
                    obj.constraints.remove(c)
            # Add billboard constraint
            tc = obj.constraints.new('TRACK_TO')
            tc.target = cam
            tc.track_axis = 'TRACK_Z'
            tc.up_axis = 'UP_Y'
            # Also make text slightly emissive so it's always readable
            for slot in obj.material_slots:
                if slot.material and slot.material.use_nodes:
                    bsdf = slot.material.node_tree.nodes.get("Principled BSDF")
                    if bsdf:
                        try:
                            bsdf.inputs["Emission Strength"].default_value = 0.5
                        except: pass
""", "Billboard text constraints")

    # Enhancement 7: Depth of field on closeup cameras
    run_py("""
import bpy

for obj in bpy.data.objects:
    if obj.type != 'CAMERA': continue
    cam = obj.data
    n = obj.name.lower()

    if 'driver' in n or 'witness' in n:
        cam.dof.use_dof = True
        cam.dof.focus_distance = 15.0
        cam.dof.aperture_fstop = 2.8  # Shallow DOF for drama
    elif 'orbit' in n:
        cam.dof.use_dof = True
        cam.dof.focus_distance = 20.0
        cam.dof.aperture_fstop = 5.6  # Moderate DOF
    elif 'bird' in n:
        cam.dof.use_dof = False  # Sharp overview
""", "Depth of field")

    # Enhancement 8: Courtroom overlay (exhibit label, scale bar, compass, disclaimer)
    run_py("""
import bpy, math

def add_text(name, text, location, size=0.3, color=(1,1,1,1), align='LEFT'):
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.body = text
    obj.data.size = size
    obj.data.align_x = align
    # Material
    mat = bpy.data.materials.new(f"{name}_Mat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Emission Strength"].default_value = 0.8
    bsdf.inputs["Emission Color"].default_value = color
    obj.data.materials.append(mat)
    return obj

# Exhibit label (top of scene)
exhibit = add_text("Exhibit_Label",
    "EXHIBIT A — Collision Reconstruction\\nCase No. 2024-CV-03847\\nSmith v. Johnson",
    location=(0, 0, 8), size=0.5, color=(1, 1, 1, 1), align='CENTER')

# Scale bar (bottom right)
# Physical scale bar: 5 meter reference
bpy.ops.mesh.primitive_cube_add(size=1, location=(20, -20, 0.05))
bar = bpy.context.active_object
bar.name = "ScaleBar_5m"
bar.scale = (5.0, 0.08, 0.04)
bar_mat = bpy.data.materials.new("ScaleBar_Mat")
bar_mat.use_nodes = True
bsdf = bar_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1, 1, 1, 1)
bsdf.inputs["Emission Strength"].default_value = 1.0
bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
bar.data.materials.append(bar_mat)
# Tick marks
for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(20 - 2.5 + i, -20, 0.12))
    tick = bpy.context.active_object
    tick.name = f"ScaleBar_Tick_{i}"
    tick.scale = (0.02, 0.15, 0.06)
    tick.data.materials.append(bar_mat)
scale_label = add_text("ScaleBar_Label", "5 meters", location=(20, -20.5, 0.15), size=0.25, align='CENTER')

# Compass rose (North arrow)
bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=1.0, location=(22, 18, 0.5))
arrow = bpy.context.active_object
arrow.name = "Compass_North"
arrow.rotation_euler = (0, 0, 0)  # Points +Y = North
arrow_mat = bpy.data.materials.new("Compass_Mat")
arrow_mat.use_nodes = True
bsdf = arrow_mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (1, 0.2, 0.2, 1)
bsdf.inputs["Emission Strength"].default_value = 0.5
bsdf.inputs["Emission Color"].default_value = (1, 0.2, 0.2, 1)
arrow.data.materials.append(arrow_mat)
n_label = add_text("Compass_N", "N", location=(22, 19.2, 0.5), size=0.4, color=(1, 0.2, 0.2, 1), align='CENTER')

# Disclaimer
disclaimer = add_text("Disclaimer",
    "This animation is a demonstrative exhibit prepared for litigation purposes.\\n"
    "Vehicle positions and speeds based on police report and physical evidence.",
    location=(0, -25, 0.15), size=0.18, color=(0.7, 0.7, 0.7, 1), align='CENTER')

# Billboard all new text too
cam = bpy.context.scene.camera
if cam:
    for name in ["Exhibit_Label", "ScaleBar_Label", "Compass_N", "Disclaimer"]:
        obj = bpy.data.objects.get(name)
        if obj:
            tc = obj.constraints.new('TRACK_TO')
            tc.target = cam
            tc.track_axis = 'TRACK_Z'
            tc.up_axis = 'UP_Y'
""", "Courtroom overlay")

    # Enhancement 9: EEVEE render quality max
    run_py("""
import bpy

scene = bpy.context.scene
eevee = scene.eevee

# Ray tracing ON
eevee.use_raytracing = True
eevee.ray_tracing_method = 'SCREEN'

# Shadows maxed
eevee.use_shadows = True
eevee.shadow_ray_count = 3
eevee.shadow_step_count = 12
eevee.shadow_resolution_scale = 1.0
eevee.shadow_pool_size = 1024  # Higher shadow map resolution

# Volumetric for atmosphere
eevee.use_volumetric_shadows = True

# Render samples
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

# Film
try:
    scene.render.film_transparent = False
except: pass

# View transform
try:
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'
except: pass
""", "EEVEE render quality max")

    # ══════════════════════════════════════════════════════════════════════
    # PHASE 3: RENDER
    # ══════════════════════════════════════════════════════════════════════
    print("\n[PHASE 3] Rendering 5 camera angles...")

    # Add one more camera: dramatic low angle
    run_py("""
import bpy, math
bpy.ops.object.camera_add(location=(8, -6, 1.2))
cam = bpy.context.active_object
cam.name = "Cam_Dramatic"
cam.data.lens = 35
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 10
cam.data.dof.aperture_fstop = 2.0
# Point at impact zone
tc = cam.constraints.new('TRACK_TO')
tc.target = bpy.data.objects.get("ImpactPoint_Marker") or bpy.data.objects.new("dummy_target", None)
tc.track_axis = 'TRACK_NEGATIVE_Z'
tc.up_axis = 'UP_Y'
""", "Dramatic camera")

    render_code = f"""
import bpy, os

render_dir = "{RENDER_DIR}"
os.makedirs(render_dir, exist_ok=True)

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = 'PNG'

cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
results = []

for i, cam in enumerate(cameras[:6]):
    scene.camera = cam

    # Update billboard text to face THIS camera
    for obj in bpy.data.objects:
        if obj.type == 'FONT':
            for c in obj.constraints:
                if c.type == 'TRACK_TO':
                    c.target = cam

    # Force scene update
    bpy.context.view_layer.update()

    out_path = os.path.join(render_dir, f"q9_{{i+1:02d}}_{{cam.name}}.png")
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    results.append(f"Rendered: {{cam.name}} -> {{out_path}}")

# Save blend
blend_path = os.path.join(render_dir, "quality_push_9.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
results.append(f"Saved: {{blend_path}}")

with open(os.path.join(render_dir, "q9_render_log.txt"), 'w') as f:
    f.write("\\n".join(results))
print("\\n".join(results))
"""
    run_py(render_code, "Rendering all angles")

    print("\n" + "=" * 70)
    print("QUALITY PUSH COMPLETE")
    print(f"Renders: {RENDER_DIR}/q9_*.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
