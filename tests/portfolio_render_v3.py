#!/usr/bin/env python3
"""
Portfolio Scene Renderer v3 — Professional Quality Upgrade
Improvements: procedural materials, Nishita sky, ground plane, decluttered grid,
professional exhibit frame (PIL post-render), better cameras.
"""
import socket, json, time, os, subprocess, sys

HOST = "127.0.0.1"
PORT = 9876
LOG = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v3_render_log.txt")
RENDER_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/v3/")
BLEND_DIR = os.path.expanduser("~/claw-architect/openclaw-blender-mcp/renders/")
os.makedirs(RENDER_DIR, exist_ok=True)
with open(LOG, "w") as f: f.write("")

def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f: f.write(line + "\n")

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
        try: return json.loads(data.decode())
        except: return {"error": data[:300].decode()}
    return {"error": "no response"}

def run_py(code, timeout=600):
    r = bridge("execute_python", {"code": code}, timeout=timeout)
    res = r.get("result", {})
    if "error" in res and res["error"]:
        log(f"  PY ERROR: {res['error'][:200]}")
        if "traceback" in res:
            log(f"  TRACEBACK: {res['traceback'][:300]}")
        return None
    return res.get("result")

def forensic(params, timeout=120):
    r = bridge("forensic_scene", params, timeout=timeout)
    res = r.get("result", {})
    if "error" in res:
        log(f"  FORENSIC ERR: {res['error'][:200]}")
        return None
    return res

def render_camera(cam_name, output_path, timeout=600):
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

def clean_scene():
    run_py("""
import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for bt in [bpy.data.meshes, bpy.data.materials, bpy.data.textures,
           bpy.data.cameras, bpy.data.lights, bpy.data.curves]:
    for b in list(bt):
        if b.users == 0: bt.remove(b)
for col in list(bpy.data.collections):
    bpy.data.collections.remove(col)
__result__ = "clean"
""")

# ═══════════════════════════════════════════════════════════════
# MATERIAL + SKY + GROUND (inline Blender Python)
# ═══════════════════════════════════════════════════════════════
def apply_pro_environment(time_of_day='day', ground_size=200, ground_mat='grass', road_mat='asphalt'):
    """Apply procedural materials, sky, and ground plane."""
    code = f"""
import bpy, math

# ---- Procedural Asphalt ----
def mk_asphalt():
    mat = bpy.data.materials.new("Pro_Asphalt")
    mat.use_nodes = True
    nd = mat.node_tree.nodes; lk = mat.node_tree.links; nd.clear()
    tc = nd.new('ShaderNodeTexCoord')
    n1 = nd.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value=8.5; n1.inputs['Detail'].default_value=5
    n2 = nd.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value=35; n2.inputs['Detail'].default_value=3
    cr = nd.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color=(0.17,0.17,0.17,1)
    cr.color_ramp.elements[1].color=(0.29,0.29,0.29,1)
    bp = nd.new('ShaderNodeBump'); bp.inputs['Strength'].default_value=0.5
    bs = nd.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value=0.75
    out = nd.new('ShaderNodeOutputMaterial')
    ad = nd.new('ShaderNodeMath'); ad.operation='ADD'; ad.inputs[1].default_value=0
    lk.new(tc.outputs['Generated'], n1.inputs['Vector'])
    lk.new(tc.outputs['Generated'], n2.inputs['Vector'])
    lk.new(n1.outputs['Fac'], ad.inputs[0]); lk.new(n2.outputs['Fac'], ad.inputs[1])
    lk.new(ad.outputs['Value'], cr.inputs['Fac'])
    lk.new(cr.outputs['Color'], bs.inputs['Base Color'])
    lk.new(n2.outputs['Fac'], bp.inputs['Height'])
    lk.new(bp.outputs['Normal'], bs.inputs['Normal'])
    lk.new(bs.outputs['BSDF'], out.inputs['Surface'])
    return mat

# ---- Procedural Grass ----
def mk_grass():
    mat = bpy.data.materials.new("Pro_Grass")
    mat.use_nodes = True
    nd = mat.node_tree.nodes; lk = mat.node_tree.links; nd.clear()
    tc = nd.new('ShaderNodeTexCoord')
    n1 = nd.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value=6; n1.inputs['Detail'].default_value=4
    gr = nd.new('ShaderNodeValToRGB')
    gr.color_ramp.elements[0].color=(0.12,0.20,0.08,1)
    gr.color_ramp.elements[1].color=(0.28,0.38,0.15,1)
    n2 = nd.new('ShaderNodeTexNoise'); n2.inputs['Scale'].default_value=18
    sr = nd.new('ShaderNodeValToRGB')
    sr.color_ramp.elements[0].color=(0.22,0.18,0.12,1)
    sr.color_ramp.elements[1].color=(0.35,0.28,0.18,1)
    bp = nd.new('ShaderNodeBump'); bp.inputs['Strength'].default_value=0.4
    bs = nd.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value=0.85
    out = nd.new('ShaderNodeOutputMaterial')
    lk.new(tc.outputs['Generated'], n1.inputs['Vector'])
    lk.new(tc.outputs['Generated'], n2.inputs['Vector'])
    lk.new(n1.outputs['Fac'], gr.inputs['Fac'])
    # Use green ramp directly (mix brown via color ramp midpoints)
    gr.color_ramp.elements.new(0.7)
    gr.color_ramp.elements[2].color = (0.30, 0.25, 0.15, 1)
    lk.new(gr.outputs['Color'], bs.inputs['Base Color'])
    lk.new(n2.outputs['Fac'], bp.inputs['Height'])
    lk.new(bp.outputs['Normal'], bs.inputs['Normal'])
    lk.new(bs.outputs['BSDF'], out.inputs['Surface'])
    return mat

# ---- Procedural Parking Lot ----
def mk_parking():
    mat = bpy.data.materials.new("Pro_ParkingLot")
    mat.use_nodes = True
    nd = mat.node_tree.nodes; lk = mat.node_tree.links; nd.clear()
    tc = nd.new('ShaderNodeTexCoord')
    n1 = nd.new('ShaderNodeTexNoise'); n1.inputs['Scale'].default_value=10; n1.inputs['Detail'].default_value=4
    cr = nd.new('ShaderNodeValToRGB')
    cr.color_ramp.elements[0].color=(0.10,0.10,0.10,1)
    cr.color_ramp.elements[1].color=(0.20,0.20,0.20,1)
    bp = nd.new('ShaderNodeBump'); bp.inputs['Strength'].default_value=0.4
    bs = nd.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value=0.80
    out = nd.new('ShaderNodeOutputMaterial')
    lk.new(tc.outputs['Generated'], n1.inputs['Vector'])
    lk.new(n1.outputs['Fac'], cr.inputs['Fac'])
    lk.new(cr.outputs['Color'], bs.inputs['Base Color'])
    lk.new(n1.outputs['Fac'], bp.inputs['Height'])
    lk.new(bp.outputs['Normal'], bs.inputs['Normal'])
    lk.new(bs.outputs['BSDF'], out.inputs['Surface'])
    return mat

# ---- Sky Setup ----
try:
    world = bpy.data.worlds["World"]
    world.use_nodes = True
    wn = world.node_tree.nodes; wl = world.node_tree.links
    for n in list(wn): wn.remove(n)
    sky = wn.new('ShaderNodeTexSky')
    sky.sky_type = 'HOSEK_WILKIE'
    bg = wn.new('ShaderNodeBackground')
    wo = wn.new('ShaderNodeOutputWorld')
    tod = '{time_of_day}'
    if tod == 'day':
        sky.sun_elevation = math.radians(55); sky.turbidity = 2.2
        bg.inputs['Strength'].default_value = 1.0
    elif tod == 'night':
        sky.sun_elevation = math.radians(-10); sky.turbidity = 2.0
        bg.inputs['Strength'].default_value = 0.02
    elif tod == 'overcast':
        sky.sun_elevation = math.radians(40); sky.turbidity = 5.0
        bg.inputs['Strength'].default_value = 0.7
    wl.new(sky.outputs['Color'], bg.inputs['Color'])
    wl.new(bg.outputs['Background'], wo.inputs['Surface'])
except Exception as e:
    print(f"Sky setup error: {{e}}")

# ---- Ground Plane ----
bpy.ops.mesh.primitive_plane_add(size={ground_size}, location=(0, 0, -0.02))
gp = bpy.context.view_layer.objects.active; gp.name = "GroundPlane"
gmat = mk_grass() if '{ground_mat}' == 'grass' else mk_parking()
gp.data.materials.append(gmat)

# ---- Apply materials to road objects ----
asph = mk_asphalt() if '{road_mat}' == 'asphalt' else mk_parking()
for obj in bpy.data.objects:
    nm = obj.name.lower()
    if obj.type != 'MESH': continue
    if 'road' in nm or 'lane' in nm or 'highway' in nm:
        obj.data.materials.clear(); obj.data.materials.append(asph)

__result__ = "environment_ready"
"""
    return run_py(code)


# ═══════════════════════════════════════════════════════════════
# POST-RENDER EXHIBIT FRAME (PIL overlay on rendered PNGs)
# ═══════════════════════════════════════════════════════════════
def add_exhibit_frame(image_path, case_number, exhibit_id, case_title,
                      expert_name="OpenClaw Forensic Animation",
                      disclaimer="DEMONSTRATIVE EXHIBIT — FOR ILLUSTRATIVE PURPOSES ONLY",
                      timestamp=""):
    """Add professional exhibit frame overlay to rendered image using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
        from PIL import Image, ImageDraw, ImageFont
    
    img = Image.open(image_path)
    w, h = img.size
    draw = ImageDraw.Draw(img)
    
    # Try to load a clean font
    font_large = font_med = font_small = None
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/System/Library/Fonts/SFNSMono.ttf",
               "/Library/Fonts/Arial.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if os.path.exists(fp):
            try:
                font_large = ImageFont.truetype(fp, 28)
                font_med = ImageFont.truetype(fp, 22)
                font_small = ImageFont.truetype(fp, 16)
                break
            except: continue
    if not font_large:
        font_large = ImageFont.load_default()
        font_med = font_large
        font_small = font_large
    
    margin = 40
    bar_h = 70
    
    # Draw thin border (2px black, inside margin)
    for i in range(2):
        draw.rectangle([margin-i, margin-i, w-margin+i, h-margin+i], outline=(40,40,40))
    
    # Bottom info bar (semi-transparent dark)
    bar_y = h - margin - bar_h
    overlay = Image.new('RGBA', (w, h), (0,0,0,0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rectangle([margin, bar_y, w-margin, h-margin], fill=(20,20,30,200))
    img = Image.alpha_composite(img.convert('RGBA'), overlay)
    draw = ImageDraw.Draw(img)
    
    # Top-left: case number
    draw.text((margin+12, margin+8), case_number, fill=(220,220,220), font=font_small)
    
    # Top-right: timestamp
    if timestamp:
        tw = draw.textlength(timestamp, font=font_small)
        draw.text((w-margin-12-tw, margin+8), timestamp, fill=(200,200,200), font=font_small)
    
    # Bottom bar: exhibit ID (center), expert (left), disclaimer (right)
    draw.text((margin+14, bar_y+10), exhibit_id, fill=(255,255,255), font=font_med)
    draw.text((margin+14, bar_y+38), expert_name, fill=(180,180,180), font=font_small)
    
    # Disclaimer right-aligned
    dw = draw.textlength(disclaimer, font=font_small)
    draw.text((w-margin-14-dw, bar_y+38), disclaimer, fill=(160,160,160), font=font_small)
    
    # Case title centered
    ttw = draw.textlength(case_title, font=font_med)
    draw.text(((w-ttw)//2, bar_y+10), case_title, fill=(255,255,255), font=font_med)
    
    # Save
    img.convert('RGB').save(image_path)
    return True


# ═══════════════════════════════════════════════════════════════
# SCENE 1: T-Bone Intersection Collision
# ═══════════════════════════════════════════════════════════════
def build_scene_1():
    log("="*60)
    log("SCENE 1: T-Bone Intersection Collision")
    log("="*60)
    clean_scene()
    
    # Build intersection
    log("  Building intersection...")
    forensic({"action": "build_road", "road_type": "intersection", "lanes": 2, "width": 7, "length": 60})
    
    # Place vehicles
    log("  Placing vehicles...")
    forensic({"action": "place_vehicle", "name": "V1_Plaintiff_Sedan",
        "vehicle_type": "sedan", "location": [8.5, 4.2, 0], "rotation": 35,
        "color": [0.7, 0.08, 0.05, 1], "damaged": True,
        "impact_side": "front_right", "severity": "severe"})
    forensic({"action": "place_vehicle", "name": "V2_Defendant_SUV",
        "vehicle_type": "suv", "location": [5.0, 2.5, 0], "rotation": 340,
        "color": [0.05, 0.12, 0.55, 1], "damaged": True,
        "impact_side": "left", "severity": "severe"})
    
    # Evidence markers (fewer, cleaner)
    log("  Adding evidence...")
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [-15, -1.8, 0.005], "end": [-2, -1.8, 0.005], "name": "V1_Skid"})
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [1.8, -18, 0.005], "end": [1.8, -3, 0.005], "name": "V2_Skid"})
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [2.0, 0.5, 0], "name": "POI"})
    forensic({"action": "add_impact_marker", "marker_type": "debris",
              "location": [4, 2, 0], "count": 15, "radius": 3, "debris_type": "mixed"})
    forensic({"action": "add_impact_marker", "marker_type": "fluid_spill",
              "location": [6, 3, 0], "spill_type": "coolant", "radius": 1.5})
    
    # Measurement grid — MUCH sparser (10m spacing, not 5m)
    log("  Adding subtle grid...")
    forensic({"action": "add_measurement_grid", "size": 30, "spacing": 10})
    
    # Apply pro materials + sky + ground
    log("  Applying pro materials & sky...")
    apply_pro_environment(time_of_day='day', ground_size=200, ground_mat='grass', road_mat='asphalt')
    
    # Trajectory arrows + labels (cleaner, fewer)
    log("  Adding annotations...")
    run_py("""
import bpy, math

# V1 trajectory (red, thicker)
bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=20, location=(-8, -1.8, 0.15),
    rotation=(math.radians(90), 0, math.radians(90)))
arr = bpy.context.view_layer.objects.active; arr.name = "V1_Traj"
mat = bpy.data.materials.new("V1_Path"); mat.use_nodes = True
b = mat.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.85, 0.15, 0.1, 1)
b.inputs["Emission Color"].default_value = (0.85, 0.15, 0.1, 1)
b.inputs["Emission Strength"].default_value = 0.3
arr.data.materials.append(mat)

# V1 arrowhead
bpy.ops.mesh.primitive_cone_add(radius1=0.35, depth=0.8, location=(-0.5, -1.8, 0.15),
    rotation=(0, math.radians(90), 0))
ah = bpy.context.view_layer.objects.active; ah.name = "V1_AH"; ah.data.materials.append(mat)

# V2 trajectory (blue, thicker)
bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=18, location=(1.8, -12, 0.15))
a2 = bpy.context.view_layer.objects.active; a2.name = "V2_Traj"
m2 = bpy.data.materials.new("V2_Path"); m2.use_nodes = True
b2 = m2.node_tree.nodes["Principled BSDF"]
b2.inputs["Base Color"].default_value = (0.1, 0.25, 0.85, 1)
b2.inputs["Emission Color"].default_value = (0.1, 0.25, 0.85, 1)
b2.inputs["Emission Strength"].default_value = 0.3
a2.data.materials.append(m2)

bpy.ops.mesh.primitive_cone_add(radius1=0.35, depth=0.8, location=(1.8, -1.5, 0.15),
    rotation=(math.radians(-90), 0, 0))
ah2 = bpy.context.view_layer.objects.active; ah2.name = "V2_AH"; ah2.data.materials.append(m2)

# Speed labels (larger, emissive for visibility)
for txt_data in [
    ("V1: 38 mph", (-12, -3.5, 0.5), (0.9, 0.2, 0.1, 1)),
    ("V2: 25 mph", (3.5, -15, 0.5), (0.1, 0.25, 0.9, 1)),
]:
    bpy.ops.object.text_add(location=txt_data[1])
    t = bpy.context.view_layer.objects.active
    t.data.body = txt_data[0]
    t.data.size = 0.8
    m = bpy.data.materials.new(f"Lbl_{txt_data[0][:6]}")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = txt_data[2]
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = txt_data[2]
    m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
    t.data.materials.append(m)

# Hide signals
for obj in bpy.data.objects:
    if "Signal" in obj.name or "signal" in obj.name:
        obj.hide_render = True; obj.hide_viewport = True

__result__ = "annotations_done"
""")
    
    # Lighting
    log("  Setting up lighting...")
    forensic({"action": "set_time_of_day", "time": "day",
              "sun_energy": 2.0, "sky_strength": 0.0, "fill_energy": 0.4})
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    # Cameras (improved positions)
    log("  Setting up cameras...")
    run_py("""
import bpy, math
tgt_loc = (2, 0.5, 0.5)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=tgt_loc)
tgt = bpy.context.view_layer.objects.active; tgt.name = "S1_Target"
tgt.hide_viewport = True; tgt.hide_render = True

# Bird's Eye (higher, wider lens for full overview)
bpy.ops.object.camera_add(location=(2, 0, 55))
c = bpy.context.view_layer.objects.active; c.name = "Cam_BirdEye"
c.data.lens = 40; c.rotation_euler = (0, 0, 0)

# V1 Driver POV (eye level)
bpy.ops.object.camera_add(location=(-25, -1.8, 1.4))
c = bpy.context.view_layer.objects.active; c.name = "Cam_DriverPOV"
c.data.lens = 35
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Witness perspective
bpy.ops.object.camera_add(location=(-15, 15, 2.0))
c = bpy.context.view_layer.objects.active; c.name = "Cam_Witness"
c.data.lens = 50
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Wide establishing shot (3/4 aerial)
bpy.ops.object.camera_add(location=(30, -25, 22))
c = bpy.context.view_layer.objects.active; c.name = "Cam_Wide"
c.data.lens = 28
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

__result__ = "cameras_done"
""")
    
    # Save blend
    blend_path = os.path.join(BLEND_DIR, "v3_scene1.blend")
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); __result__="saved"')
    
    # Render cameras
    cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Witness", "Cam_Wide"]
    exhibit_info = {
        "case_number": "Case No. 2026-CV-04521",
        "exhibit_id": "Exhibit A",
        "case_title": "Smith v. Johnson — T-Bone Intersection Collision",
        "timestamp": "Incident: 2026-01-15  17:42 EST"
    }
    for i, cam in enumerate(cameras):
        log(f"  Rendering {cam}...")
        path = os.path.join(RENDER_DIR, f"scene1_{i+1:02d}_{cam}.png")
        result = render_camera(cam, path, timeout=600)
        if result:
            log(f"    {cam}: {result.get('size_mb', '?')} MB")
            # Add exhibit frame
            add_exhibit_frame(path, **exhibit_info)
            log(f"    Exhibit frame applied")
        else:
            log(f"    {cam}: FAILED")
    log("SCENE 1 COMPLETE")


# ═══════════════════════════════════════════════════════════════
# SCENE 2: Pedestrian Crosswalk Incident
# ═══════════════════════════════════════════════════════════════
def build_scene_2():
    log("="*60)
    log("SCENE 2: Pedestrian Crosswalk Incident")
    log("="*60)
    clean_scene()
    
    log("  Building road...")
    forensic({"action": "build_road", "road_type": "straight", "lanes": 2, "width": 7,
              "start": [-40, 0, 0], "end": [40, 0, 0]})
    
    # Crosswalk + curbs + sidewalk areas
    run_py("""
import bpy
# Crosswalk stripes
mat = bpy.data.materials.new("Crosswalk")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.92, 0.92, 0.92, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.5
for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -3 + i*1.2, 0.008))
    s = bpy.context.view_layer.objects.active
    s.name = f"Crosswalk_{i}"; s.scale = (0.4, 0.5, 0.005)
    s.data.materials.append(mat)
# Curbs
cm = bpy.data.materials.new("Curb"); cm.use_nodes = True
cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.5, 1)
for side in [-1, 1]:
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, side*4.5, 0.08))
    c = bpy.context.view_layer.objects.active; c.scale = (80, 0.15, 0.16)
    c.name = f"Curb_{side}"; c.data.materials.append(cm)
__result__ = "crosswalk_done"
""")
    
    # Place vehicles
    log("  Placing vehicles...")
    forensic({"action": "place_vehicle", "name": "V1_DeliveryVan",
        "vehicle_type": "van", "location": [6, -0.5, 0], "rotation": 15,
        "color": [0.9, 0.9, 0.88, 1], "damaged": True,
        "impact_side": "front", "severity": "moderate"})
    # Parked SUV obstructing view
    forensic({"action": "place_vehicle", "name": "ParkedSUV",
        "vehicle_type": "suv", "location": [-5, -4.2, 0], "rotation": 0,
        "color": [0.25, 0.25, 0.28, 1]})
    
    # Pedestrian figure
    log("  Adding pedestrian...")
    forensic({"action": "place_figure", "name": "Pedestrian",
              "location": [1.5, -1.0, 0], "pose": "walking"})
    
    # Dress the pedestrian in neutral gray
    run_py("""
import bpy
for obj in bpy.data.objects:
    if 'pedestrian' in obj.name.lower() or 'figure' in obj.name.lower() or 'person' in obj.name.lower():
        # Create neutral gray clothing material
        gm = bpy.data.materials.new("Figure_Gray")
        gm.use_nodes = True
        gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.55, 0.58, 1)
        gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
        obj.data.materials.clear()
        obj.data.materials.append(gm)
__result__ = "dressed"
""")
    
    # Sight line analysis
    log("  Adding sight lines...")
    run_py("""
import bpy, math
# Blocked sight line (red) - from driver through parked SUV
for nm, pts, col in [
    ("SightBlocked", [(-5, -0.5, 1.2), (1.5, -1.0, 0.9)], (0.9, 0.15, 0.1, 1)),
    ("SightClear", [(-15, -0.5, 1.2), (1.5, -1.0, 0.9)], (0.1, 0.7, 0.2, 1)),
]:
    curve = bpy.data.curves.new(nm, 'CURVE'); curve.dimensions = '3D'
    spline = curve.splines.new('POLY')
    spline.points.add(1)
    spline.points[0].co = (*pts[0], 1); spline.points[1].co = (*pts[1], 1)
    curve.bevel_depth = 0.04
    obj = bpy.data.objects.new(nm, curve)
    bpy.context.collection.objects.link(obj)
    mat = bpy.data.materials.new(nm+"_mat"); mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = col
    mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = col
    mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.5
    obj.data.materials.append(mat)

# Speed limit sign text
bpy.ops.object.text_add(location=(-8, 5.5, 1.5))
t = bpy.context.view_layer.objects.active; t.data.body = "SPEED\\nLIMIT\\n25"
t.data.size = 0.3; t.data.align_x = 'CENTER'
sm = bpy.data.materials.new("Sign"); sm.use_nodes = True
sm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.1, 0.1, 1)
t.data.materials.append(sm)
__result__ = "sight_lines_done"
""")
    
    # Impact + evidence
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [1.5, -1.0, 0], "name": "POI"})
    
    # Sparse grid
    forensic({"action": "add_measurement_grid", "size": 25, "spacing": 10})
    
    # Pro materials + sky + ground
    log("  Applying pro materials & sky...")
    apply_pro_environment(time_of_day='overcast', ground_size=200, ground_mat='grass', road_mat='asphalt')
    
    # Lighting
    forensic({"action": "set_time_of_day", "time": "day",
              "sun_energy": 1.8, "sky_strength": 0.0, "fill_energy": 0.4})
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    # Cameras
    log("  Setting up cameras...")
    run_py("""
import bpy, math
tgt_loc = (1.5, -1.0, 0.5)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=tgt_loc)
tgt = bpy.context.view_layer.objects.active; tgt.name = "S2_Target"
tgt.hide_viewport = True; tgt.hide_render = True

# Bird's Eye
bpy.ops.object.camera_add(location=(0, 0, 40))
c = bpy.context.view_layer.objects.active; c.name = "Cam_BirdEye"
c.data.lens = 35; c.rotation_euler = (0, 0, 0)

# Driver POV
bpy.ops.object.camera_add(location=(-20, -0.5, 1.4))
c = bpy.context.view_layer.objects.active; c.name = "Cam_DriverPOV"
c.data.lens = 35
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Sight Line Analysis angle (key forensic shot)
bpy.ops.object.camera_add(location=(-8, 8, 4))
c = bpy.context.view_layer.objects.active; c.name = "Cam_SightLine"
c.data.lens = 40
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Wide
bpy.ops.object.camera_add(location=(20, -18, 14))
c = bpy.context.view_layer.objects.active; c.name = "Cam_Wide"
c.data.lens = 28
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

__result__ = "cameras_done"
""")
    
    blend_path = os.path.join(BLEND_DIR, "v3_scene2.blend")
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); __result__="saved"')
    
    cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_SightLine", "Cam_Wide"]
    exhibit_info = {
        "case_number": "Case No. 2026-CV-07833",
        "exhibit_id": "Exhibit B",
        "case_title": "Martinez v. City Transit — Pedestrian Crosswalk",
        "timestamp": "Incident: 2026-03-08  08:15 EST"
    }
    for i, cam in enumerate(cameras):
        log(f"  Rendering {cam}...")
        path = os.path.join(RENDER_DIR, f"scene2_{i+1:02d}_{cam}.png")
        result = render_camera(cam, path, timeout=600)
        if result:
            log(f"    {cam}: {result.get('size_mb', '?')} MB")
            add_exhibit_frame(path, **exhibit_info)
            log(f"    Exhibit frame applied")
        else:
            log(f"    {cam}: FAILED")
    log("SCENE 2 COMPLETE")


# ═══════════════════════════════════════════════════════════════
# SCENE 3: Highway Rear-End Chain Reaction
# ═══════════════════════════════════════════════════════════════
def build_scene_3():
    log("="*60)
    log("SCENE 3: Highway Rear-End Chain Reaction")
    log("="*60)
    clean_scene()
    
    log("  Building highway...")
    forensic({"action": "add_scene_template", "template": "highway_straight"})
    
    # 3 vehicles in chain
    log("  Placing 3 vehicles...")
    forensic({"action": "place_vehicle", "name": "V1_Stopped_Sedan",
        "vehicle_type": "sedan", "location": [0, -1.8, 0], "rotation": 90,
        "color": [0.7, 0.1, 0.08, 1], "damaged": True,
        "impact_side": "rear", "severity": "moderate"})
    forensic({"action": "place_vehicle", "name": "V2_Stopped_SUV",
        "vehicle_type": "suv", "location": [-6, -1.8, 0], "rotation": 90,
        "color": [0.6, 0.6, 0.62, 1], "damaged": True,
        "impact_side": "rear", "severity": "severe"})
    forensic({"action": "place_vehicle", "name": "V3_Truck",
        "vehicle_type": "truck", "location": [-45, -1.8, 0], "rotation": 90,
        "color": [0.1, 0.15, 0.5, 1], "damaged": True,
        "impact_side": "front", "severity": "severe"})
    
    # Evidence
    log("  Adding evidence...")
    forensic({"action": "add_impact_marker", "marker_type": "skid_mark",
              "start": [-40, -1.8, 0.005], "end": [-8, -1.8, 0.005], "name": "V3_BrakeSkid"})
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [-6, -1.8, 0], "name": "POI_Primary"})
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [0, -1.8, 0], "name": "POI_Secondary"})
    forensic({"action": "add_impact_marker", "marker_type": "debris",
              "location": [-3, -0.5, 0], "count": 20, "radius": 4})
    
    # Braking distance annotation
    run_py("""
import bpy, math
# Braking distance label
bpy.ops.object.text_add(location=(-24, -4.5, 0.5))
t = bpy.context.view_layer.objects.active; t.data.body = "Braking Distance: 32m"
t.data.size = 0.7; t.rotation_euler = (0, 0, math.radians(90))
m = bpy.data.materials.new("BrakeLbl"); m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.7, 0.1, 1)
m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.9, 0.7, 0.1, 1)
m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
t.data.materials.append(m)

# V3 speed label
bpy.ops.object.text_add(location=(-42, -4, 0.5))
t = bpy.context.view_layer.objects.active; t.data.body = "V3: 55 mph"
t.data.size = 0.7; t.rotation_euler = (0, 0, math.radians(90))
m2 = bpy.data.materials.new("V3Lbl"); m2.use_nodes = True
m2.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.1, 0.15, 0.9, 1)
m2.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.1, 0.15, 0.9, 1)
m2.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.0
t.data.materials.append(m2)
__result__ = "labels_done"
""")
    
    # Sparse measurement grid
    forensic({"action": "add_measurement_grid", "size": 40, "spacing": 10})
    
    # Pro environment
    log("  Applying pro materials & sky...")
    apply_pro_environment(time_of_day='day', ground_size=300, ground_mat='grass', road_mat='asphalt')
    
    # Lighting + render
    forensic({"action": "set_time_of_day", "time": "day",
              "sun_energy": 2.0, "sky_strength": 0.0, "fill_energy": 0.4})
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    # Cameras
    log("  Setting up cameras...")
    run_py("""
import bpy, math
tgt_loc = (-3, -1.8, 0.5)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=tgt_loc)
tgt = bpy.context.view_layer.objects.active; tgt.name = "S3_Target"
tgt.hide_viewport = True; tgt.hide_render = True

# Bird's Eye (long highway view)
bpy.ops.object.camera_add(location=(-15, 0, 50))
c = bpy.context.view_layer.objects.active; c.name = "Cam_BirdEye"
c.data.lens = 30; c.rotation_euler = (0, 0, math.radians(90))

# Truck driver POV
bpy.ops.object.camera_add(location=(-50, -1.8, 2.5))
c = bpy.context.view_layer.objects.active; c.name = "Cam_TruckPOV"
c.data.lens = 35
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Witness from shoulder
bpy.ops.object.camera_add(location=(-10, 12, 2.0))
c = bpy.context.view_layer.objects.active; c.name = "Cam_Witness"
c.data.lens = 50
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Wide aerial
bpy.ops.object.camera_add(location=(20, -30, 25))
c = bpy.context.view_layer.objects.active; c.name = "Cam_Wide"
c.data.lens = 24
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

__result__ = "cameras_done"
""")
    
    blend_path = os.path.join(BLEND_DIR, "v3_scene3.blend")
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); __result__="saved"')
    
    cameras = ["Cam_BirdEye", "Cam_TruckPOV", "Cam_Witness", "Cam_Wide"]
    exhibit_info = {
        "case_number": "Case No. 2026-CV-11290",
        "exhibit_id": "Exhibit C",
        "case_title": "Thompson v. ABC Trucking — Highway Chain Reaction",
        "timestamp": "Incident: 2026-02-22  06:48 EST"
    }
    for i, cam in enumerate(cameras):
        log(f"  Rendering {cam}...")
        path = os.path.join(RENDER_DIR, f"scene3_{i+1:02d}_{cam}.png")
        result = render_camera(cam, path, timeout=600)
        if result:
            log(f"    {cam}: {result.get('size_mb', '?')} MB")
            add_exhibit_frame(path, **exhibit_info)
            log(f"    Exhibit frame applied")
        else:
            log(f"    {cam}: FAILED")
    log("SCENE 3 COMPLETE")


# ═══════════════════════════════════════════════════════════════
# SCENE 4: Parking Lot Hit-and-Run (Night)
# ═══════════════════════════════════════════════════════════════
def build_scene_4():
    log("="*60)
    log("SCENE 4: Parking Lot Hit-and-Run (Night)")
    log("="*60)
    clean_scene()
    
    log("  Building parking lot...")
    forensic({"action": "add_scene_template", "template": "parking_lot"})
    
    log("  Placing vehicles...")
    # Victim's parked sedan
    forensic({"action": "place_vehicle", "name": "V1_Parked_Sedan",
        "vehicle_type": "sedan", "location": [3, 2, 0], "rotation": 0,
        "color": [0.6, 0.6, 0.62, 1], "damaged": True,
        "impact_side": "rear_left", "severity": "moderate"})
    # Hit-and-run pickup
    forensic({"action": "place_vehicle", "name": "V2_Pickup_Fled",
        "vehicle_type": "pickup", "location": [0, 4, 0], "rotation": 200,
        "color": [0.12, 0.12, 0.15, 1]})
    # Context vehicles
    for i, (vt, loc, rot, col) in enumerate([
        ("sedan", [-6, 2, 0], 0, [0.3, 0.15, 0.15, 1]),
        ("suv", [-3, 2, 0], 0, [0.15, 0.2, 0.3, 1]),
        ("van", [6, 2, 0], 0, [0.25, 0.25, 0.22, 1]),
    ]):
        forensic({"action": "place_vehicle", "name": f"Parked_{i}",
            "vehicle_type": vt, "location": loc, "rotation": rot,
            "color": col})
    
    # Evidence
    log("  Adding evidence...")
    forensic({"action": "add_impact_marker", "marker_type": "impact_point",
              "location": [1.5, 2.8, 0], "name": "POI"})
    forensic({"action": "add_impact_marker", "marker_type": "debris",
              "location": [2, 3, 0], "count": 8, "radius": 2})
    
    # Escape trajectory arrow
    run_py("""
import bpy, math
# Orange escape arrow path
pts = [(0, 4, 0.15), (-2, 6, 0.15), (-5, 9, 0.15), (-10, 12, 0.15), (-18, 14, 0.15)]
curve = bpy.data.curves.new("EscapePath", 'CURVE'); curve.dimensions = '3D'
spline = curve.splines.new('BEZIER')
spline.bezier_points.add(len(pts)-1)
for j, p in enumerate(pts):
    spline.bezier_points[j].co = p
    spline.bezier_points[j].handle_left_type = 'AUTO'
    spline.bezier_points[j].handle_right_type = 'AUTO'
curve.bevel_depth = 0.08
obj = bpy.data.objects.new("EscapePath", curve)
bpy.context.collection.objects.link(obj)
mat = bpy.data.materials.new("EscapeOrange"); mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.5, 0.1, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.9, 0.5, 0.1, 1)
mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.8
obj.data.materials.append(mat)

# Arrowhead at end of path
bpy.ops.mesh.primitive_cone_add(radius1=0.4, depth=0.8, location=(-18, 14, 0.15),
    rotation=(0, 0, math.radians(145)))
ah = bpy.context.view_layer.objects.active; ah.name = "EscapeAH"
ah.data.materials.append(mat)

# V2 FLED label
bpy.ops.object.text_add(location=(-12, 11, 0.5))
t = bpy.context.view_layer.objects.active; t.data.body = "V2 FLED SCENE"
t.data.size = 0.6
m = bpy.data.materials.new("FledLbl"); m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.9, 0.5, 0.1, 1)
m.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value = (0.9, 0.5, 0.1, 1)
m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.5
t.data.materials.append(m)
__result__ = "escape_done"
""")
    
    # Night lighting with point lights on poles
    log("  Setting up night lighting...")
    run_py("""
import bpy
# Parking lot pole lights (warm sodium vapor)
for pos in [(-8, 0, 6), (0, 0, 6), (8, 0, 6), (-8, 8, 6), (8, 8, 6)]:
    bpy.ops.object.light_add(type='POINT', location=pos)
    lt = bpy.context.view_layer.objects.active
    lt.data.energy = 500; lt.data.color = (1.0, 0.85, 0.6)
    lt.data.shadow_soft_size = 1.0
    lt.name = f"ParkingLight_{pos[0]}_{pos[1]}"
    # Light pole
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=6, location=(pos[0], pos[1], 3))
    pole = bpy.context.view_layer.objects.active; pole.name = f"Pole_{pos[0]}"
    pm = bpy.data.materials.new("Pole"); pm.use_nodes = True
    pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.3, 0.32, 1)
    pole.data.materials.append(pm)
__result__ = "lights_done"
""")
    
    # Sparse grid
    forensic({"action": "add_measurement_grid", "size": 25, "spacing": 10})
    
    # Pro environment (night sky, parking lot ground)
    log("  Applying night environment...")
    apply_pro_environment(time_of_day='night', ground_size=200, ground_mat='parking', road_mat='parking')
    
    forensic({"action": "setup_courtroom_render", "preset": "presentation"})
    
    # Cameras
    log("  Setting up cameras...")
    run_py("""
import bpy, math
tgt_loc = (1.5, 3, 0.5)
bpy.ops.object.empty_add(type="PLAIN_AXES", location=tgt_loc)
tgt = bpy.context.view_layer.objects.active; tgt.name = "S4_Target"
tgt.hide_viewport = True; tgt.hide_render = True

# Security camera (wide angle, high corner)
bpy.ops.object.camera_add(location=(15, -5, 8))
c = bpy.context.view_layer.objects.active; c.name = "Cam_SecurityCam"
c.data.lens = 18
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

# Bird's Eye
bpy.ops.object.camera_add(location=(0, 5, 35))
c = bpy.context.view_layer.objects.active; c.name = "Cam_BirdEye"
c.data.lens = 35; c.rotation_euler = (0, 0, 0)

# Wide showing escape route
bpy.ops.object.camera_add(location=(-20, -15, 18))
c = bpy.context.view_layer.objects.active; c.name = "Cam_Wide"
c.data.lens = 24
t = c.constraints.new("TRACK_TO"); t.target = tgt
t.track_axis = "TRACK_NEGATIVE_Z"; t.up_axis = "UP_Y"

__result__ = "cameras_done"
""")
    
    blend_path = os.path.join(BLEND_DIR, "v3_scene4.blend")
    run_py(f'import bpy; bpy.ops.wm.save_as_mainfile(filepath="{blend_path}"); __result__="saved"')
    
    cameras = ["Cam_SecurityCam", "Cam_BirdEye", "Cam_Wide"]
    exhibit_info = {
        "case_number": "Case No. 2026-CV-09157",
        "exhibit_id": "Exhibit D",
        "case_title": "Davis v. Unknown — Parking Lot Hit-and-Run",
        "timestamp": "Incident: 2026-04-03  22:17 EST"
    }
    for i, cam in enumerate(cameras):
        log(f"  Rendering {cam}...")
        path = os.path.join(RENDER_DIR, f"scene4_{i+1:02d}_{cam}.png")
        result = render_camera(cam, path, timeout=600)
        if result:
            log(f"    {cam}: {result.get('size_mb', '?')} MB")
            add_exhibit_frame(path, **exhibit_info)
            log(f"    Exhibit frame applied")
        else:
            log(f"    {cam}: FAILED")
    log("SCENE 4 COMPLETE")


# ═══════════════════════════════════════════════════════════════
# MAIN — Run all scenes
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    log("Portfolio v3 Render — Professional Quality Upgrade")
    log(f"Output: {RENDER_DIR}")
    start = time.time()
    
    build_scene_1()
    build_scene_2()
    build_scene_3()
    build_scene_4()
    
    elapsed = time.time() - start
    log(f"\nALL SCENES COMPLETE in {elapsed/60:.1f} minutes")
    log(f"Renders saved to: {RENDER_DIR}")
