#!/usr/bin/env python3
"""
Portfolio Scene Renderer v2
Sends individual bridge commands instead of monolithic exec scripts.
Each forensic_scene command goes through the bridge protocol properly.
"""
import socket
import json
import time
import os

HOST = "127.0.0.1"
PORT = 9876
LOG = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_render_log.txt")
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio/")

os.makedirs(RENDER_DIR, exist_ok=True)

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def bridge(command, params=None, timeout=600):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((HOST, PORT))
    msg = json.dumps({"command": command, "params": params or {}})
    s.sendall(msg.encode() + b"\n")
    data = b""
    while True:
        try:
            chunk = s.recv(65536)
            if not chunk: break
            data += chunk
            try:
                json.loads(data.decode())
                break
            except json.JSONDecodeError:
                continue
        except socket.timeout:
            break
    s.close()
    if data:
        try:
            return json.loads(data.decode())
        except:
            return {"error": data[:300].decode()}
    return {"error": "no response"}

def run_py(code, timeout=600):
    """Execute Python in Blender, return __result__"""
    r = bridge("execute_python", {"code": code}, timeout=timeout)
    res = r.get("result", {})
    if "error" in res and res["error"]:
        log(f"  PY ERROR: {res['error'][:200]}")
        if "traceback" in res:
            log(f"  TRACEBACK: {res['traceback'][:300]}")
        return None
    return res.get("result")

def forensic(params, timeout=120):
    """Send forensic_scene command"""
    r = bridge("forensic_scene", params, timeout=timeout)
    res = r.get("result", {})
    if "error" in res:
        log(f"  FORENSIC ERROR: {res['error'][:200]}")
        return None
    return res

def render_camera(cam_name, output_path, timeout=600):
    """Set camera and render"""
    code = f"""
import bpy, os
cam = bpy.data.objects.get("{cam_name}")
if cam:
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = "{output_path}"
    bpy.ops.render.render(write_still=True)
    size = os.path.getsize("{output_path}") if os.path.exists("{output_path}") else 0
    __result__ = {{"rendered": "{cam_name}", "size_mb": round(size/1024/1024, 2)}}
else:
    __result__ = {{"error": "Camera {cam_name} not found"}}
"""
    return run_py(code, timeout=timeout)

# ══════════════════════════════════════════════════════════════
# SCENE 1: T-Bone Intersection Collision
# ══════════════════════════════════════════════════════════════
def build_scene_1():
    log("="*60)
    log("SCENE 1: T-Bone Intersection Collision")
    log("="*60)
    
    # Clean scene
    run_py("""
import bpy
pass
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
__result__ = "clean"
""")
    
    # Build intersection
    log("  Building intersection...")
    forensic({"action": "build_road", "road_type": "intersection", "lanes": 2, "width": 7, "length": 60})
    
    # Place vehicles
    log("  Placing vehicles...")
    forensic({
        "action": "place_vehicle", "name": "V1_Plaintiff_Sedan",
        "vehicle_type": "sedan", "location": [8.5, 4.2, 0], "rotation": 35,
        "color": [0.7, 0.08, 0.05, 1], "damaged": True,
        "impact_side": "front_right", "severity": "severe"
    })
    forensic({
        "action": "place_vehicle", "name": "V2_Defendant_SUV",
        "vehicle_type": "suv", "location": [5.0, 2.5, 0], "rotation": 340,
        "color": [0.05, 0.12, 0.55, 1], "damaged": True,
        "impact_side": "left", "severity": "severe"
    })
    
    # Skid marks
    log("  Adding evidence markers...")
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [-15, -1.8, 0.005], "end": [-2, -1.8, 0.005], "name": "V1_Skid"})
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [1.8, -18, 0.005], "end": [1.8, -3, 0.005], "name": "V2_Skid"})
    
    # Impact + debris
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [2.0, 0.5, 0], "name": "POI_Impact"})
    forensic({"action": "add_impact_marker", "marker_type": "debris",
              "location": [4, 2, 0], "count": 25, "radius": 4, "debris_type": "mixed"})
    forensic({"action": "add_impact_marker", "marker_type": "fluid_spill",
              "location": [6, 3, 0], "spill_type": "coolant", "radius": 1.8})
    
    # Measurement grid + exhibit overlay
    log("  Adding overlays...")
    forensic({"action": "add_measurement_grid", "size": 40, "spacing": 5})
    forensic({
        "action": "add_exhibit_overlay",
        "case_number": "Case No. 2026-CV-04521",
        "exhibit_id": "Exhibit A — Accident Reconstruction Overview",
        "expert_name": "OpenClaw Forensic Animation",
        "firm_name": "Certified Reconstruction Analysis",
        "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
        "show_scale_bar": True, "scale_bar_length": 10,
        "show_timestamp": True, "timestamp": "Incident: 2026-01-15 17:42 EST"
    })
    
    # Trajectory arrows + speed labels + legend (via Python)
    log("  Adding annotations...")
    run_py("""
import bpy, math

# V1 trajectory arrow (red, eastbound)
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=20, location=(-8, -1.8, 0.15),
    rotation=(math.radians(90), 0, math.radians(90)))
arr = bpy.context.view_layer.objects.active
arr.name = "V1_Trajectory"
mat = bpy.data.materials.new("V1_Path")
mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (1, 0.2, 0.1, 0.7)
b.inputs["Alpha"].default_value = 0.7
try: mat.surface_render_method = 'DITHERED'
except: pass
arr.data.materials.append(mat)

# V1 arrowhead
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.6, location=(-0.5, -1.8, 0.15),
    rotation=(0, math.radians(90), 0))
ah = bpy.context.view_layer.objects.active
ah.name = "V1_AH"
ah.data.materials.append(mat)

# V2 trajectory arrow (blue, northbound)
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=18, location=(1.8, -12, 0.15))
arr2 = bpy.context.view_layer.objects.active
arr2.name = "V2_Trajectory"
mat2 = bpy.data.materials.new("V2_Path")
mat2.use_nodes = True
b2 = mat2.node_tree.nodes["Principled BSDF"]
b2.inputs["Base Color"].default_value = (0.1, 0.3, 1, 0.7)
b2.inputs["Alpha"].default_value = 0.7
try: mat2.surface_render_method = 'DITHERED'
except: pass
arr2.data.materials.append(mat2)

# V2 arrowhead
bpy.ops.mesh.primitive_cone_add(radius1=0.25, depth=0.6, location=(1.8, -1.5, 0.15),
    rotation=(math.radians(-90), 0, 0))
ah2 = bpy.context.view_layer.objects.active
ah2.name = "V2_AH"
ah2.data.materials.append(mat2)

# Speed labels
for txt_data in [
    ("V1: 38 mph", (-12, -3.5, 0.3), (1, 0.2, 0.1, 1)),
    ("V2: 25 mph", (3.5, -15, 0.3), (0.1, 0.3, 1, 1)),
    ("RED = Vehicle 1 (Plaintiff)    BLUE = Vehicle 2 (Defendant)", (-19, -19, 0.03), (0.9, 0.9, 0.9, 1)),
]:
    bpy.ops.object.text_add(location=txt_data[1])
    t = bpy.context.view_layer.objects.active
    t.data.body = txt_data[0]
    t.data.size = 0.6 if "=" not in txt_data[0] else 0.45
    m = bpy.data.materials.new(f"Label_{txt_data[0][:8]}")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = txt_data[2]
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = txt_data[2]
    t.data.materials.append(m)

__result__ = "annotations_done"
""")
    
    # Lighting
    log("  Setting up lighting...")
    forensic({"action": "set_time_of_day", "time": "day",
              "sun_energy": 1.5, "sky_strength": 0.25, "fill_energy": 0.3})
    
    # Render settings
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    # Setup cameras
    log("  Setting up cameras...")
    run_py("""
import bpy, math

target_loc = (2, 0.5, 0.5)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=target_loc)
tgt = bpy.context.view_layer.objects.active
tgt.name = "Scene1_Target"
tgt.hide_viewport = True
tgt.hide_render = True

# Bird's Eye
bpy.ops.object.camera_add(location=(0, 0, 45))
c = bpy.context.view_layer.objects.active
c.name = "Cam_BirdEye"
c.data.lens = 35
c.rotation_euler = (0, 0, 0)

# V1 Driver POV
bpy.ops.object.camera_add(location=(-22, -1.8, 1.5))
c = bpy.context.view_layer.objects.active
c.name = "Cam_V1_DriverPOV"
c.data.lens = 35
t = c.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

# Witness
bpy.ops.object.camera_add(location=(-12, 12, 1.7))
c = bpy.context.view_layer.objects.active
c.name = "Cam_Witness"
c.data.lens = 50
t = c.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

# Impact close-up
bpy.ops.object.camera_add(location=(6, -4, 1.0))
c = bpy.context.view_layer.objects.active
c.name = "Cam_ImpactCloseup"
c.data.lens = 28
c.data.dof.use_dof = True
c.data.dof.focus_object = tgt
c.data.dof.aperture_fstop = 4.0
t = c.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

# Wide
bpy.ops.object.camera_add(location=(25, -20, 18))
c = bpy.context.view_layer.objects.active
c.name = "Cam_Wide"
c.data.lens = 24
t = c.constraints.new("TRACK_TO")
t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"
t.up_axis = "UP_Y"

# Hide signals
for obj in bpy.data.objects:
    if "Signal" in obj.name or "signal" in obj.name:
        obj.hide_render = True
        obj.hide_viewport = True

__result__ = "cameras_done"
""")
    
    # Save blend
    run_py(f"""
import bpy
bpy.ops.wm.save_as_mainfile(filepath="{os.path.expanduser('~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene1.blend')}")
__result__ = "saved"
""")
    
    # Render each camera
    cameras = ["Cam_BirdEye", "Cam_V1_DriverPOV", "Cam_Witness", "Cam_ImpactCloseup", "Cam_Wide"]
    for i, cam in enumerate(cameras):
        log(f"  Rendering {cam}...")
        path = os.path.join(RENDER_DIR, f"scene1_{i+1:02d}_{cam}.png")
        result = render_camera(cam, path, timeout=600)
        if result:
            log(f"    {cam}: {result.get('size_mb', '?')} MB")
        else:
            log(f"    {cam}: FAILED")
    
    log("SCENE 1 COMPLETE")

# ══════════════════════════════════════════════════════════════
# SCENE 2: Pedestrian Crosswalk Incident
# ══════════════════════════════════════════════════════════════
def build_scene_2():
    log("="*60)
    log("SCENE 2: Pedestrian Crosswalk Incident")
    log("="*60)
    
    run_py("""
import bpy
pass
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
__result__ = "clean"
""")
    
    log("  Building road...")
    forensic({"action": "build_road", "road_type": "straight", "lanes": 2, "width": 7,
              "start": [-40, 0, 0], "end": [40, 0, 0]})
    
    # Crosswalk stripes
    run_py("""
import bpy
mat = bpy.data.materials.new("Crosswalk")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.7
for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -3 + i*1.2, 0.008))
    s = bpy.context.view_layer.objects.active
    s.name = f"Crosswalk_{i}"
    s.scale = (0.4, 0.5, 0.005)
    s.data.materials.append(mat)
# Curbs
cm = bpy.data.materials.new("Curb")
cm.use_nodes = True
cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.5, 1)
for side in [-1, 1]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side*4.5, 0.08))
    c = bpy.context.view_layer.objects.active
    c.scale = (80, 0.15, 0.16)
    c.data.materials.append(cm)
__result__ = "crosswalk_done"
""")
    
    log("  Placing vehicles...")
    forensic({"action": "place_vehicle", "name": "V1_DeliveryVan",
              "vehicle_type": "van", "location": [12, -1.8, 0], "rotation": 265,
              "color": [0.85, 0.85, 0.82, 1], "damaged": True,
              "impact_side": "front", "severity": "moderate"})
    forensic({"action": "place_vehicle", "name": "Parked_SUV",
              "vehicle_type": "suv", "location": [-4, -4.5, 0], "rotation": 270,
              "color": [0.15, 0.15, 0.15, 1]})
    
    # Pedestrian figure
    log("  Adding pedestrian and sight lines...")
    forensic({"action": "place_figure", "name": "Ped_Martinez",
              "location": [1.5, -0.5, 0], "pose": "walking",
              "shirt_color": [0.8, 0.2, 0.1, 1], "pants_color": [0.15, 0.15, 0.25, 1]})
    
    # Sight lines + annotations via Python
    run_py("""
import bpy, math

# Obstructed sight line (red)
def make_line(name, start, end, color, alpha=0.5):
    mid = [(s+e)/2 for s, e in zip(start, end)]
    dx, dy, dz = end[0]-start[0], end[1]-start[1], end[2]-start[2]
    length = math.sqrt(dx*dx+dy*dy+dz*dz)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=length, location=mid)
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    angle_xy = math.atan2(dy, dx)
    angle_z = math.atan2(math.sqrt(dx*dx+dy*dy), dz)
    obj.rotation_euler = (angle_z, 0, angle_xy + math.radians(90))
    mat = bpy.data.materials.new(name + "_Mat")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color[:3], alpha)
    b.inputs["Alpha"].default_value = alpha
    b.inputs["Emission Strength"].default_value = 1.0
    b.inputs["Emission Color"].default_value = (*color[:3], 1)
    try: mat.surface_render_method = 'DITHERED'
    except: pass
    obj.data.materials.append(mat)

make_line("SightLine_Blocked", (-8, -1.8, 1.5), (1.5, -0.5, 1.0), (1, 0, 0))
make_line("SightLine_Clear", (-18, -1.8, 1.5), (1.5, -0.5, 1.0), (0, 1, 0.3))

# Labels
for txt, loc, color in [
    ("OBSTRUCTED\\nSIGHT LINE", (-14, -3.5, 2.0), (1, 0.2, 0.1, 1)),
    ("V1: 32 mph (7 over limit)", (-15, 0.5, 0.3), (1, 0.3, 0, 1)),
    ("SPEED LIMIT 25", (-25, -5, 2.0), (0.9, 0.9, 0.9, 1)),
]:
    bpy.ops.object.text_add(location=loc)
    t = bpy.context.view_layer.objects.active
    t.data.body = txt
    t.data.size = 0.5
    m = bpy.data.materials.new(f"L_{txt[:6]}")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = color
    t.data.materials.append(m)

__result__ = "sightlines_done"
""")
    
    # Evidence markers
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [18, -1.8, 0.005], "end": [5, -1.8, 0.005]})
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [1.5, -0.5, 0]})
    forensic({"action": "add_impact_marker", "marker_type": "debris",
              "location": [3, -1, 0], "count": 12, "radius": 2.5, "debris_type": "plastic"})
    
    forensic({"action": "add_measurement_grid", "size": 40, "spacing": 5})
    forensic({
        "action": "add_exhibit_overlay",
        "case_number": "Case No. 2026-CV-07833",
        "exhibit_id": "Exhibit B — Pedestrian Crosswalk Analysis",
        "expert_name": "OpenClaw Forensic Animation",
        "firm_name": "Certified Reconstruction Analysis",
        "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
        "show_scale_bar": True, "scale_bar_length": 10,
        "show_timestamp": True, "timestamp": "Incident: 2026-02-08 08:15 EST"
    })
    
    forensic({"action": "set_time_of_day", "time": "day", "sun_energy": 1.5, "sky_strength": 0.25})
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    # Cameras
    run_py("""
import bpy, math
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, -1, 0))
tgt = bpy.context.view_layer.objects.active
tgt.name = "S2_Target"
tgt.hide_viewport = True
tgt.hide_render = True

cams = [
    ("Cam_BirdEye", (0, 0, 40), 35, None),
    ("Cam_DriverPOV", (-15, -1.8, 1.5), 35, None),
    ("Cam_SightLine", (-5, -8, 12), 30, tgt),
    ("Cam_PedestrianPOV", (1.5, 4, 1.6), 35, None),
    ("Cam_Wide", (20, -15, 12), 24, tgt),
]
for name, loc, lens, target in cams:
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.view_layer.objects.active
    c.name = name
    c.data.lens = lens
    if name == "Cam_BirdEye":
        c.rotation_euler = (0, 0, 0)
    elif name == "Cam_DriverPOV":
        c.rotation_euler = (math.radians(88), 0, math.radians(-90))
    elif name == "Cam_PedestrianPOV":
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-8, -1.8, 1))
        pt = bpy.context.view_layer.objects.active
        pt.name = "PedTgt"
        pt.hide_viewport = True; pt.hide_render = True
        t = c.constraints.new("TRACK_TO")
        t.target = pt
        t.track_axis = "TRACK_NEGATIVE_Z"
        t.up_axis = "UP_Y"
    elif target:
        t = c.constraints.new("TRACK_TO")
        t.target = target
        t.track_axis = "TRACK_NEGATIVE_Z"
        t.up_axis = "UP_Y"

for obj in bpy.data.objects:
    if "Signal" in obj.name:
        obj.hide_render = True; obj.hide_viewport = True

__result__ = "cams_done"
""")
    
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene2.blend")}"); __result__ = "saved"')
    
    cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_SightLine", "Cam_PedestrianPOV", "Cam_Wide"]
    for i, cam in enumerate(cameras):
        log(f"  Rendering {cam}...")
        path = os.path.join(RENDER_DIR, f"scene2_{i+1:02d}_{cam}.png")
        result = render_camera(cam, path)
        if result: log(f"    {cam}: {result.get('size_mb', '?')} MB")

    log("SCENE 2 COMPLETE")

# ══════════════════════════════════════════════════════════════
# SCENE 3: Highway Rear-End Chain Reaction
# ══════════════════════════════════════════════════════════════
def build_scene_3():
    log("="*60)
    log("SCENE 3: Highway Rear-End Chain Reaction")
    log("="*60)
    
    run_py('import bpy\npass\n__result__ = "clean"')
    
    log("  Building highway...")
    forensic({"action": "add_scene_template", "template": "highway_straight"})
    
    log("  Placing 3 vehicles...")
    forensic({"action": "place_vehicle", "name": "V1_Sedan",
              "vehicle_type": "sedan", "location": [5, -1.8, 0], "rotation": 90,
              "color": [0.65, 0.07, 0.05, 1], "damaged": True, "impact_side": "rear", "severity": "moderate"})
    forensic({"action": "place_vehicle", "name": "V2_SUV",
              "vehicle_type": "suv", "location": [-2, -1.5, 0], "rotation": 85,
              "color": [0.6, 0.6, 0.58, 1], "damaged": True, "impact_side": "rear", "severity": "severe"})
    forensic({"action": "place_vehicle", "name": "V3_Truck",
              "vehicle_type": "truck", "location": [-12, -2.2, 0], "rotation": 88,
              "color": [0.05, 0.1, 0.5, 1], "damaged": True, "impact_side": "front", "severity": "severe"})
    
    log("  Adding evidence...")
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [-55, -2.2, 0.005], "end": [-14, -2.2, 0.005], "skid_width": 0.28})
    forensic({"action": "add_impact_marker", "marker_type": "impact_point", "location": [-7, -1.8, 0]})
    forensic({"action": "add_impact_marker", "marker_type": "impact_point", "location": [1, -1.7, 0]})
    forensic({"action": "add_impact_marker", "marker_type": "debris", "location": [-6, -2, 0],
              "count": 20, "radius": 3, "debris_type": "mixed"})
    forensic({"action": "add_impact_marker", "marker_type": "debris", "location": [2, -1.5, 0],
              "count": 15, "radius": 2.5})
    forensic({"action": "add_impact_marker", "marker_type": "fluid_spill",
              "location": [-9, -2.5, 0], "spill_type": "oil", "radius": 2.0})
    
    # Annotations
    run_py("""
import bpy, math

# V3 trajectory arrow
bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=40, location=(-35, -2.2, 0.2),
    rotation=(math.radians(90), 0, math.radians(90)))
a = bpy.context.view_layer.objects.active
a.name = "V3_Traj"
m = bpy.data.materials.new("V3P")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.2, 0.9, 0.6)
m.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.6
try: m.surface_render_method = 'DITHERED'
except: pass
a.data.materials.append(m)

for txt, loc, color in [
    ("V3 (Truck): 55 mph", (-40, -4.5, 0.3), (0.1, 0.2, 0.9, 1)),
    ("V1: STOPPED", (3, 0.5, 0.3), (0.9, 0.15, 0.1, 1)),
    ("V2: STOPPED", (-4, 0.5, 0.3), (0.5, 0.5, 0.48, 1)),
    ("Braking Distance: 131 ft (40m)", (-35, -5.5, 0.15), (1, 0.8, 0, 1)),
    ("RED=V1(Plaintiff) SILVER=V2 BLUE=V3(Defendant)", (-50, -9, 0.03), (0.9, 0.9, 0.9, 1)),
]:
    bpy.ops.object.text_add(location=loc)
    t = bpy.context.view_layer.objects.active
    t.data.body = txt
    t.data.size = 0.6
    lm = bpy.data.materials.new(f"L_{txt[:6]}")
    lm.use_nodes = True
    lm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    lm.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
    lm.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = color
    t.data.materials.append(lm)

__result__ = "annot_done"
""")
    
    forensic({"action": "add_measurement_grid", "size": 60, "spacing": 10})
    forensic({
        "action": "add_exhibit_overlay",
        "case_number": "Case No. 2026-CV-11290",
        "exhibit_id": "Exhibit C — Chain Reaction Analysis",
        "expert_name": "OpenClaw Forensic Animation",
        "firm_name": "Certified Reconstruction Analysis",
        "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
        "show_scale_bar": True, "scale_bar_length": 20,
        "show_timestamp": True, "timestamp": "Incident: 2025-11-22 16:05 EST"
    })
    
    forensic({"action": "set_time_of_day", "time": "day", "sun_energy": 1.5, "sky_strength": 0.25})
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    run_py("""
import bpy, math
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(-3, -1.8, 1))
tgt = bpy.context.view_layer.objects.active
tgt.name = "S3_Tgt"; tgt.hide_viewport = True; tgt.hide_render = True

for name, loc, lens in [
    ("Cam_BirdEye", (-5, 0, 50), 40),
    ("Cam_TruckPOV", (-50, -2.2, 2.0), 35),
    ("Cam_Witness", (-5, 12, 6), 50),
    ("Cam_ImpactCloseup", (-7, -6, 2), 35),
    ("Cam_Wide", (30, -25, 15), 24),
]:
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.view_layer.objects.active
    c.name = name; c.data.lens = lens
    if name == "Cam_BirdEye":
        c.rotation_euler = (0, 0, 0)
    elif name == "Cam_TruckPOV":
        c.rotation_euler = (math.radians(86), 0, math.radians(-90))
    else:
        t = c.constraints.new("TRACK_TO")
        t.target = tgt; t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

for obj in bpy.data.objects:
    if "Signal" in obj.name: obj.hide_render = True

__result__ = "cams_done"
""")
    
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene3.blend")}"); __result__ = "saved"')
    
    for i, cam in enumerate(["Cam_BirdEye", "Cam_TruckPOV", "Cam_Witness", "Cam_ImpactCloseup", "Cam_Wide"]):
        log(f"  Rendering {cam}...")
        r = render_camera(cam, os.path.join(RENDER_DIR, f"scene3_{i+1:02d}_{cam}.png"))
        if r: log(f"    {cam}: {r.get('size_mb', '?')} MB")
    log("SCENE 3 COMPLETE")

# ══════════════════════════════════════════════════════════════
# SCENE 4: Parking Lot Hit-and-Run (Night)
# ══════════════════════════════════════════════════════════════
def build_scene_4():
    log("="*60)
    log("SCENE 4: Parking Lot Hit-and-Run (Night)")
    log("="*60)
    
    run_py('import bpy\npass\n__result__ = "clean"')
    
    log("  Building parking lot...")
    forensic({"action": "add_scene_template", "template": "parking_lot"})
    
    # Parking lines + lot lights
    run_py("""
import bpy
mat = bpy.data.materials.new("ParkLine")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.95, 0.95, 0.95, 1)
for side in [-1, 1]:
    for i in range(8):
        x = -14 + i * 3.5
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, side*5, 0.008))
        s = bpy.context.view_layer.objects.active
        s.scale = (0.06, 2.5, 0.005)
        s.data.materials.append(mat)

# Parking lot lights
pm = bpy.data.materials.new("Pole")
pm.use_nodes = True
pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
pm.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.8
for x in [-10, 0, 10]:
    bpy.ops.object.light_add(type='POINT', location=(x, 0, 6))
    l = bpy.context.view_layer.objects.active
    l.data.energy = 800; l.data.color = (1, 0.95, 0.85)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=6, location=(x, 0, 3))
    p = bpy.context.view_layer.objects.active
    p.data.materials.append(pm)

__result__ = "lot_done"
""")
    
    log("  Placing vehicles...")
    forensic({"action": "place_vehicle", "name": "V1_ParkedSedan",
              "vehicle_type": "sedan", "location": [0, -5, 0], "rotation": 0,
              "color": [0.55, 0.55, 0.52, 1], "damaged": True, "impact_side": "rear_left", "severity": "moderate"})
    forensic({"action": "place_vehicle", "name": "V2_DarkTruck",
              "vehicle_type": "pickup", "location": [-1.5, -2, 0], "rotation": 200,
              "color": [0.08, 0.08, 0.1, 1], "damaged": True, "impact_side": "rear_right", "severity": "light"})
    
    # Context parked vehicles
    for idx, (c, vt, loc) in enumerate([
        ([0.3, 0.05, 0.05, 1], "sedan", [3.5, -5, 0]),
        ([0.1, 0.2, 0.4, 1], "suv", [7, -5, 0]),
        ([0.4, 0.35, 0.25, 1], "sedan", [-3.5, -5, 0]),
        ([0.15, 0.3, 0.15, 1], "suv", [-3.5, 5, 0]),
    ]):
        forensic({"action": "place_vehicle", "name": f"Parked_{idx}",
                  "vehicle_type": vt, "location": loc, "rotation": 0 if loc[1]<0 else 180, "color": c})
    
    # Escape path + annotations
    run_py("""
import bpy, math
# Escape path
em = bpy.data.materials.new("Escape")
em.use_nodes = True
em.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (1, 0.5, 0, 0.6)
em.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.6
em.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.8
em.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (1, 0.5, 0, 1)
try: em.surface_render_method = 'DITHERED'
except: pass

pts = [(-1.5, -2), (2, -1), (5, 0), (8, 0), (15, 0)]
for i in range(len(pts)-1):
    p1, p2 = pts[i], pts[i+1]
    mid = ((p1[0]+p2[0])/2, (p1[1]+p2[1])/2, 0.15)
    dx, dy = p2[0]-p1[0], p2[1]-p1[1]
    l = math.sqrt(dx*dx+dy*dy)
    a = math.atan2(dy, dx)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=l, location=mid, rotation=(math.radians(90), 0, a))
    s = bpy.context.view_layer.objects.active
    s.data.materials.append(em)

bpy.ops.mesh.primitive_cone_add(radius1=0.2, depth=0.5, location=(15, 0, 0.15), rotation=(0, math.radians(90), 0))
bpy.context.view_layer.objects.active.data.materials.append(em)

for txt, loc, color in [
    ("V2 FLED SCENE", (10, 1.5, 0.3), (1, 0.4, 0, 1)),
    ("CAM-04  2026-03-01  21:47:23  REC", (-15, 12, 0.03), (0.8, 0, 0, 1)),
]:
    bpy.ops.object.text_add(location=loc)
    t = bpy.context.view_layer.objects.active
    t.data.body = txt; t.data.size = 0.5
    m = bpy.data.materials.new(f"L_{txt[:6]}")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = color
    t.data.materials.append(m)

__result__ = "escape_done"
""")
    
    log("  Adding evidence...")
    forensic({"action": "add_impact_marker", "marker_type": "impact_point", "location": [-0.5, -3.5, 0]})
    forensic({"action": "add_impact_marker", "marker_type": "debris", "location": [-0.5, -3, 0],
              "count": 10, "radius": 1.5, "debris_type": "plastic"})
    
    forensic({"action": "add_measurement_grid", "size": 30, "spacing": 5})
    forensic({
        "action": "add_exhibit_overlay",
        "case_number": "Case No. 2026-CV-09157",
        "exhibit_id": "Exhibit D — Parking Lot Reconstruction",
        "expert_name": "OpenClaw Forensic Animation",
        "firm_name": "Certified Reconstruction Analysis",
        "disclaimer": "DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
        "show_scale_bar": True, "scale_bar_length": 5,
        "show_timestamp": True, "timestamp": "Incident: 2026-03-01 21:47 EST"
    })
    
    forensic({"action": "set_time_of_day", "time": "night"})
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    run_py("""
import bpy, math
bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, -3, 0))
tgt = bpy.context.view_layer.objects.active
tgt.name = "S4_Tgt"; tgt.hide_viewport = True; tgt.hide_render = True

for name, loc, lens in [
    ("Cam_SecurityCam", (-15, 10, 8), 18),
    ("Cam_BirdEye", (0, 0, 30), 30),
    ("Cam_ImpactCloseup", (3, -6, 1.5), 35),
    ("Cam_Wide", (20, -15, 10), 24),
    ("Cam_EscapeRoute", (15, 8, 5), 28),
]:
    bpy.ops.object.camera_add(location=loc)
    c = bpy.context.view_layer.objects.active
    c.name = name; c.data.lens = lens
    if name == "Cam_BirdEye":
        c.rotation_euler = (0, 0, 0)
    else:
        t = c.constraints.new("TRACK_TO")
        t.target = tgt; t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

__result__ = "cams_done"
""")
    
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/portfolio_scene4.blend")}"); __result__ = "saved"')
    
    for i, cam in enumerate(["Cam_SecurityCam", "Cam_BirdEye", "Cam_ImpactCloseup", "Cam_Wide", "Cam_EscapeRoute"]):
        log(f"  Rendering {cam}...")
        r = render_camera(cam, os.path.join(RENDER_DIR, f"scene4_{i+1:02d}_{cam}.png"))
        if r: log(f"    {cam}: {r.get('size_mb', '?')} MB")
    log("SCENE 4 COMPLETE")

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    with open(LOG, "w") as f:
        f.write("")  # Clear log
    
    total_start = time.time()
    
    build_scene_1()
    time.sleep(3)
    build_scene_2()
    time.sleep(3)
    build_scene_3()
    time.sleep(3)
    build_scene_4()
    
    elapsed = time.time() - total_start
    log("="*60)
    log(f"ALL 4 SCENES COMPLETE in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    
    # Summary
    renders = sorted([f for f in os.listdir(RENDER_DIR) if f.endswith(".png")])
    log(f"Total renders: {len(renders)}")
    for r in renders:
        sz = os.path.getsize(os.path.join(RENDER_DIR, r))
        log(f"  {r}: {sz/1024/1024:.1f} MB")
    log("="*60)
