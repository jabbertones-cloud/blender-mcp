#!/usr/bin/env python3
"""
QUALITY PUSH v7 — Polish pass for 9.5/10 target.

v6 assessment (average 7.75/10):
  + Z-fighting FIXED — intersection center renders correctly
  + Shadows casting properly (Cycles)
  + Grass ground plane works well
  + 6 camera angles all usable
  - Green floating lines (signal poles) still visible in grass
  - Text mirrored from some camera angles
  - Vehicle body colors didn't change (V2 still pink, not burgundy)
  - Sharp road-to-grass edge looks unrealistic
  - Signal pole (gray cylinder) dominates some shots
  - Pedestrian figure is ghostly white — needs proper material

v7 approach:
  - Load quality_push_v6.blend
  - FIX 1: Hide ALL signal/pole objects + any thin elongated objects in grass
  - FIX 2: Force vehicle body colors (deep navy V1, burgundy V2)
  - FIX 3: Pedestrian material (neutral human skin/clothing)
  - FIX 4: Curb/sidewalk strip between road and grass for realistic edge
  - FIX 5: Hide mirrored text — use only bird's-eye-safe labels
  - FIX 6: Add subtle environment fog/mist for depth
  - Render all 6 cameras
"""
import socket, json, os, time

HOST, PORT = "127.0.0.1", 9876
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders")
LOG = os.path.join(RENDER_DIR, "q9v7_render_progress.log")
_counter = 0

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def send(command, params=None):
    global _counter
    _counter += 1
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(600)
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
        log(f"  [{status}] {label}")
        if not ok:
            err_str = str(result.get("error", result))[:400]
            log(f"        {err_str}")
    return result

def main():
    with open(LOG, "w") as f:
        f.write("")

    log("=" * 60)
    log("QUALITY PUSH v7 — Polish for 9.5/10")
    log("=" * 60)

    # Load v6 blend
    log("\n[1] Loading v6 scene...")
    blend_path = os.path.join(RENDER_DIR, "quality_push_v6.blend")
    run_py(f"""
import bpy
bpy.ops.wm.open_mainfile(filepath="{blend_path}")
__result__ = {{"objects": len(bpy.data.objects), "cameras": [o.name for o in bpy.data.objects if o.type == "CAMERA"]}}
""", "Load quality_push_v6.blend")

    # FIX 1: Hide ALL signal poles, thin elongated objects, and visual noise
    log("\n[2] Hiding signal poles and visual noise...")
    run_py(r"""
import bpy

hidden = []
for obj in bpy.data.objects:
    n = obj.name.lower()
    hide = False

    # Traffic signals and poles
    if any(kw in n for kw in ['signal', 'traffic', 'pole', 'post']):
        hide = True
    # Impact markers (should already be hidden from v6, but ensure)
    elif any(kw in n for kw in ['impact', 'debris', 'spill']):
        hide = True
    # Thin elongated objects that look like floating lines
    # These are typically signal-related empties or meshes
    elif obj.type == 'MESH' and obj.dimensions.z < 0.1:
        # Check if it's far from the road (likely floating in grass)
        if abs(obj.location.x) > 12 or abs(obj.location.y) > 12:
            if obj.dimensions.x < 0.5 or obj.dimensions.y < 0.5:
                hide = True
    # Light probe objects
    elif obj.type == 'LIGHT_PROBE':
        hide = True

    if hide:
        obj.hide_render = True
        obj.hide_viewport = True
        hidden.append(obj.name)

# Also hide children of hidden objects
for obj in bpy.data.objects:
    if obj.parent and obj.parent.hide_render:
        obj.hide_render = True
        obj.hide_viewport = True
        if obj.name not in hidden:
            hidden.append(obj.name)

__result__ = {"hidden": len(hidden), "names": hidden[:20]}
""", "Hide signal poles + floating objects")

    # FIX 2: Force vehicle body colors
    log("\n[3] Fixing vehicle body colors...")
    run_py(r"""
import bpy

fixed = []

# Find all vehicle body materials and force correct colors
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    n = obj.name

    # V1 = sedan (blue vehicle)
    is_v1_body = False
    is_v2_body = False

    # Check parent hierarchy for V1/V2
    parent = obj.parent
    while parent:
        if 'V1' in parent.name:
            is_v1_body = True
            break
        elif 'V2' in parent.name:
            is_v2_body = True
            break
        parent = parent.parent

    nl = n.lower()
    # Skip non-body parts
    if any(kw in nl for kw in ['window', 'windshield', 'glass', 'headlight',
                                 'taillight', 'lamp', 'bumper', 'grill',
                                 'wheel', 'tire', 'chrome']):
        continue

    if is_v1_body and obj.data.materials:
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                b = slot.material.node_tree.nodes.get("Principled BSDF")
                if b:
                    b.inputs["Base Color"].default_value = (0.02, 0.06, 0.22, 1.0)
                    b.inputs["Metallic"].default_value = 0.15
                    b.inputs["Roughness"].default_value = 0.08
                    try:
                        b.inputs["Coat Weight"].default_value = 1.0
                        b.inputs["Coat Roughness"].default_value = 0.02
                    except: pass
                    fixed.append(f"{n} -> deep navy")

    elif is_v2_body and obj.data.materials:
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                b = slot.material.node_tree.nodes.get("Principled BSDF")
                if b:
                    b.inputs["Base Color"].default_value = (0.22, 0.03, 0.03, 1.0)
                    b.inputs["Metallic"].default_value = 0.12
                    b.inputs["Roughness"].default_value = 0.08
                    try:
                        b.inputs["Coat Weight"].default_value = 1.0
                        b.inputs["Coat Roughness"].default_value = 0.02
                    except: pass
                    fixed.append(f"{n} -> deep burgundy")

__result__ = {"fixed": len(fixed), "details": fixed[:15]}
""", "Vehicle body colors (navy + burgundy)")

    # FIX 3: Pedestrian material
    log("\n[4] Fixing pedestrian material...")
    run_py(r"""
import bpy

# Find pedestrian/character objects
fixed = []
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    nl = obj.name.lower()
    if any(kw in nl for kw in ['person', 'pedestrian', 'character', 'human', 'figure', 'witness_fig']):
        # Create a basic human material
        mat = bpy.data.materials.new(f"{obj.name}_Skin")
        mat.use_nodes = True
        b = mat.node_tree.nodes["Principled BSDF"]
        # Medium skin tone
        b.inputs["Base Color"].default_value = (0.35, 0.22, 0.16, 1.0)
        b.inputs["Roughness"].default_value = 0.65
        b.inputs["Subsurface Weight"].default_value = 0.15
        b.inputs["Subsurface Color"].default_value = (0.5, 0.2, 0.12, 1.0)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        fixed.append(obj.name)

# Also try Kenney character models (they use atlas textures)
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    # Characters imported from Kenney often have generic names
    # Check if it's human-sized and has the atlas material
    if obj.dimensions.z > 1.0 and obj.dimensions.z < 3.0:
        has_atlas = False
        for slot in obj.material_slots:
            if slot.material and ('atlas' in slot.material.name.lower() or
                                  'kenney' in slot.material.name.lower() or
                                  'material' == slot.material.name.lower()):
                has_atlas = True
                break
        if has_atlas and obj.name not in fixed:
            # This is likely a character model — give it clothing material
            clothing = bpy.data.materials.new(f"{obj.name}_Clothing")
            clothing.use_nodes = True
            b = clothing.node_tree.nodes["Principled BSDF"]
            b.inputs["Base Color"].default_value = (0.12, 0.12, 0.15, 1.0)  # Dark clothing
            b.inputs["Roughness"].default_value = 0.75
            obj.data.materials.clear()
            obj.data.materials.append(clothing)
            fixed.append(obj.name)

__result__ = {"fixed": len(fixed), "names": fixed}
""", "Pedestrian/character materials")

    # FIX 4: Add curb/sidewalk border between road and grass
    log("\n[5] Adding road edge definition...")
    run_py(r"""
import bpy, math

# Find the road bounds to place curbs correctly
road_main = bpy.data.objects.get("Road_Main")
road_cross = bpy.data.objects.get("Road_Cross")

if road_main:
    # Road_Main is scaled plane: actual size = scale * size(1)
    road_half_w = abs(road_main.scale.y)  # Half-width of main road
    road_half_l = abs(road_main.scale.x)  # Half-length of main road
    loc = road_main.location

    # Get curb material
    curb_mat = None
    for mat in bpy.data.materials:
        if 'sidewalk' in mat.name.lower() or 'curb' in mat.name.lower():
            curb_mat = mat
            break
    if not curb_mat:
        curb_mat = bpy.data.materials.new("Curb_v7")
        curb_mat.use_nodes = True
        b = curb_mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.32, 0.30, 0.28, 1.0)
        b.inputs["Roughness"].default_value = 0.88

    # Add thin curb strips along road edges (only where there isn't cross road)
    curbs_added = 0
    curb_h = 0.08  # Curb height
    curb_w = 0.15  # Curb width

    # Main road edges (left and right, excluding intersection area)
    for side in [-1, 1]:
        for seg in [-1, 1]:
            # Skip the intersection zone
            seg_start = road_half_w + 2 if seg == 1 else -(road_half_l)
            seg_end = road_half_l if seg == 1 else -(road_half_w + 2)
            seg_len = abs(seg_end - seg_start)
            if seg_len < 1:
                continue
            cx = loc[0] + (seg_start + seg_end) / 2
            cy = loc[1] + side * road_half_w
            bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, loc[2] + curb_h/2))
            curb = bpy.context.active_object
            curb.name = f"Curb_Main_{side}_{seg}"
            curb.scale = (seg_len/2, curb_w/2, curb_h/2)
            curb.data.materials.append(curb_mat)
            curbs_added += 1

    __result__ = {"curbs_added": curbs_added}
else:
    __result__ = {"error": "Road_Main not found"}
""", "Road edge curbs")

    # FIX 5: Fix text — hide mirrored ones, keep only useful ones
    log("\n[6] Cleaning up text objects...")
    run_py(r"""
import bpy

text_actions = []
for obj in bpy.data.objects:
    if obj.type != 'FONT':
        continue
    n = obj.name.lower()

    # Hide small measurement labels that mirror badly
    # Keep "Impact Zone" and timestamp labels
    if 'mph' in n or 'speed' in n or 'timeline' in n:
        # These labels mirror — hide them
        obj.hide_render = True
        obj.hide_viewport = True
        text_actions.append(f"HIDDEN: {obj.name}")
    else:
        # Ensure remaining text has emission for visibility
        for slot in obj.material_slots:
            if slot.material and slot.material.use_nodes:
                b = slot.material.node_tree.nodes.get("Principled BSDF")
                if b:
                    try:
                        b.inputs["Emission Strength"].default_value = 0.5
                        bc = b.inputs["Base Color"].default_value
                        b.inputs["Emission Color"].default_value = (bc[0], bc[1], bc[2], 1)
                    except: pass
        text_actions.append(f"KEPT: {obj.name}")

__result__ = {"actions": text_actions}
""", "Text cleanup")

    # FIX 6: Atmospheric depth (volume scatter for subtle fog)
    log("\n[7] Adding atmospheric depth...")
    run_py(r"""
import bpy

scene = bpy.context.scene
world = scene.world
if not world:
    world = bpy.data.worlds.new("World_v7")
    scene.world = world
world.use_nodes = True
tree = world.node_tree
nodes = tree.nodes
links = tree.links

# Check if volume scatter already exists
has_volume = False
for node in nodes:
    if node.type == 'VOLUME_SCATTER':
        has_volume = True
        break

if not has_volume:
    # Add subtle volume scatter for atmospheric depth
    vol = nodes.new("ShaderNodeVolumeScatter")
    vol.location = (0, -200)
    vol.inputs["Color"].default_value = (0.85, 0.9, 1.0, 1.0)  # Slightly blue haze
    vol.inputs["Density"].default_value = 0.003  # Very subtle
    vol.inputs["Anisotropy"].default_value = 0.3

    # Connect to World Output volume input
    output = None
    for node in nodes:
        if node.type == 'OUTPUT_WORLD':
            output = node
            break
    if output:
        links.new(vol.outputs["Volume"], output.inputs["Volume"])

__result__ = "Atmosphere added" if not has_volume else "Already exists"
""", "Atmospheric fog")

    # RENDER
    log("\n[8] Configuring Cycles 128spl...")
    run_py(f"""
import bpy, os
os.makedirs("{RENDER_DIR}", exist_ok=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.view_settings.view_transform = "Filmic"
try:
    scene.view_settings.look = "High Contrast"
except:
    scene.view_settings.look = "Medium High Contrast"
scene.view_settings.exposure = 0.3
scene.view_settings.gamma = 1.0
__result__ = "configured"
""", "Cycles config")

    cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness", "Cam_Dramatic", "Cam_Wide"]

    for i, cam in enumerate(cameras):
        log(f"Rendering {i+1}/{len(cameras)}: {cam}...")
        t0 = time.time()
        outpath = os.path.join(RENDER_DIR, f"q9v7_{i+1:02d}_{cam}.png")
        resp = send("execute_python", {"code": f"""
import bpy, os
scene = bpy.context.scene
cam = bpy.data.objects.get("{cam}")
if cam and cam.type == "CAMERA":
    scene.camera = cam
    bpy.context.view_layer.update()
    scene.render.filepath = "{outpath}"
    bpy.ops.render.render(write_still=True)
    size = os.path.getsize("{outpath}") if os.path.exists("{outpath}") else 0
    __result__ = {{"rendered": "{cam}", "size_kb": size // 1024}}
else:
    __result__ = {{"error": "Camera not found: {cam}"}}
"""})
        elapsed = time.time() - t0
        result = resp.get("result", {}).get("result", resp)
        log(f"  Done: {cam} in {elapsed:.0f}s -> {result}")

    # Save
    log("Saving blend...")
    run_py(f"""
import bpy
bpy.ops.wm.save_as_mainfile(filepath="{os.path.join(RENDER_DIR, 'quality_push_v7.blend')}")
__result__ = "saved"
""", "Save v7 blend")

    log("=== QUALITY PUSH v7 COMPLETE ===")


if __name__ == "__main__":
    main()
