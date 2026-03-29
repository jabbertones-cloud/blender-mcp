#!/usr/bin/env python3
"""V8 Step 1: Apply render settings + materials + lighting, then render Scene 1."""
import socket, json, os, sys, time
from datetime import datetime

HOST, PORT = "127.0.0.1", 9876
RENDER_DIR = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v8"
os.makedirs(RENDER_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

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
    return bridge("execute_python", {"code": code}, timeout=timeout)

# ============================================================
# STEP 1: Render settings
# ============================================================
log("=== STEP 1: V8 Render Settings ===")
r = run_py("""
import bpy
s = bpy.context.scene
s.render.engine = 'CYCLES'
s.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    prefs.preferences.compute_device_type = 'METAL'
    prefs.preferences.get_devices()
    for d in prefs.preferences.devices:
        d.use = True
s.cycles.samples = 256
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.015
s.cycles.max_bounces = 8
s.cycles.diffuse_bounces = 4
s.cycles.glossy_bounces = 4
s.cycles.transmission_bounces = 4
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'
s.cycles.caustics_reflective = False
s.cycles.caustics_refractive = False
s.cycles.sample_clamp_indirect = 10
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
s.render.image_settings.file_format = 'PNG'
s.render.film_transparent = False
s.view_settings.view_transform = 'Filmic'
s.view_settings.look = 'Medium High Contrast'
s.view_settings.exposure = 0.3
__result__ = f'Cycles 256spl OIDN Filmic - {len(bpy.data.objects)} objects'
""")
log(f"  Settings: {r}")

# ============================================================
# STEP 2: Upgrade materials on existing objects
# ============================================================
log("=== STEP 2: V8 Materials ===")

# Asphalt
r = run_py("""
import bpy
mat = bpy.data.materials.new(name='Pro_Asphalt_v8')
mat.use_nodes = True
tree = mat.node_tree; nodes = tree.nodes; links = tree.links
for n in nodes: nodes.remove(n)
out = nodes.new('ShaderNodeOutputMaterial'); out.location = (1200, 0)
bsdf = nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (900, 0)
links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
noise = nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 120.0
noise.inputs['Detail'].default_value = 12.0
noise.inputs['Roughness'].default_value = 0.7
voronoi = nodes.new('ShaderNodeTexVoronoi')
voronoi.inputs['Scale'].default_value = 60.0
ramp = nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = 0.3
ramp.color_ramp.elements[0].color = (0.03, 0.03, 0.035, 1)
ramp.color_ramp.elements[1].position = 0.7
ramp.color_ramp.elements[1].color = (0.065, 0.06, 0.058, 1)
links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.85
bump = nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.25
add = nodes.new('ShaderNodeMath'); add.operation = 'ADD'
links.new(voronoi.outputs['Distance'], add.inputs[0])
links.new(noise.outputs['Fac'], add.inputs[1])
links.new(add.outputs[0], bump.inputs['Height'])
links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
applied = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and any(k in obj.name.lower() for k in ('road','asphalt','street','ground','plane')):
        if obj.data and hasattr(obj.data, 'materials'):
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            applied += 1
__result__ = f'Asphalt: {applied} objects'
""")
log(f"  {r}")

# Vehicle paint upgrade
r = run_py("""
import bpy
upgraded = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if not any(k in n for k in ('body','sedan','suv','truck','car','vehicle')): continue
    if any(k in n for k in ('wheel','tire','glass','cabin','window')): continue
    for mat in (obj.data.materials if obj.data else []):
        if mat and mat.use_nodes:
            bsdf = mat.node_tree.nodes.get('Principled BSDF')
            if bsdf:
                bsdf.inputs['Metallic'].default_value = 0.85
                bsdf.inputs['Roughness'].default_value = 0.12
                try:
                    bsdf.inputs['Coat Weight'].default_value = 1.0
                    bsdf.inputs['Coat Roughness'].default_value = 0.02
                except: pass
                tree = mat.node_tree
                noise = tree.nodes.new('ShaderNodeTexNoise')
                noise.inputs['Scale'].default_value = 800.0
                noise.inputs['Detail'].default_value = 6.0
                bump = tree.nodes.new('ShaderNodeBump')
                bump.inputs['Strength'].default_value = 0.008
                tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
                tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
                upgraded += 1
__result__ = f'Vehicle paint: {upgraded}'
""")
log(f"  {r}")

# Glass + rubber
r = run_py("""
import bpy
glass = rubber = concrete = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    for mat in (obj.data.materials if obj.data else []):
        if not mat or not mat.use_nodes: continue
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        if not bsdf: continue
        if any(k in n for k in ('cabin','glass','window','windshield')):
            bsdf.inputs['Base Color'].default_value = (0.7, 0.75, 0.8, 1)
            bsdf.inputs['Roughness'].default_value = 0.0
            bsdf.inputs['Alpha'].default_value = 0.35
            try: bsdf.inputs['Transmission Weight'].default_value = 0.92
            except:
                try: bsdf.inputs['Transmission'].default_value = 0.92
                except: pass
            try: bsdf.inputs['IOR'].default_value = 1.52
            except: pass
            glass += 1
        elif any(k in n for k in ('wheel','tire')):
            bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.025, 1)
            bsdf.inputs['Roughness'].default_value = 0.75
            rubber += 1
        elif any(k in n for k in ('curb','sidewalk','concrete','median')):
            bsdf.inputs['Base Color'].default_value = (0.32, 0.31, 0.29, 1)
            bsdf.inputs['Roughness'].default_value = 0.85
            concrete += 1
__result__ = f'Glass:{glass} Rubber:{rubber} Concrete:{concrete}'
""")
log(f"  {r}")

# ============================================================
# STEP 3: V8 Lighting (3-point)
# ============================================================
log("=== STEP 3: V8 Lighting ===")
r = run_py("""
import bpy, math
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20))
sun = bpy.context.active_object
sun.name = 'Key_Sun_v8'
sun.data.energy = 4.0
sun.data.angle = math.radians(0.545)
sun.rotation_euler = (math.radians(45), 0, math.radians(160))
sun.data.color = (1.0, 0.95, 0.9)

bpy.ops.object.light_add(type='AREA', location=(-15, -10, 8))
fill = bpy.context.active_object
fill.name = 'Fill_Area_v8'
fill.data.energy = 200.0
fill.data.size = 12.0
fill.data.color = (0.85, 0.9, 1.0)
fill.rotation_euler = (math.radians(60), 0, math.radians(-30))

bpy.ops.object.light_add(type='AREA', location=(10, 15, 6))
rim = bpy.context.active_object
rim.name = 'Rim_Area_v8'
rim.data.energy = 150.0
rim.data.size = 8.0
rim.data.color = (1.0, 0.95, 0.85)
rim.rotation_euler = (math.radians(70), 0, math.radians(145))

__result__ = 'Key Sun + Fill Area + Rim Area added'
""")
log(f"  {r}")

# ============================================================
# STEP 4: V8 Compositor
# ============================================================
log("=== STEP 4: V8 Compositor ===")
r = run_py("""
import bpy
s = bpy.context.scene
s.use_nodes = True
tree = s.node_tree
for n in tree.nodes: tree.nodes.remove(n)
rl = tree.nodes.new('CompositorNodeRLayers'); rl.location = (0, 300)
comp = tree.nodes.new('CompositorNodeComposite'); comp.location = (1200, 300)
glare = tree.nodes.new('CompositorNodeGlare')
glare.glare_type = 'FOG_GLOW'; glare.quality = 'HIGH'
glare.mix = 0.03; glare.threshold = 2.5; glare.location = (300, 300)
lens = tree.nodes.new('CompositorNodeLensdist')
lens.inputs['Distort'].default_value = -0.008
lens.inputs['Dispersion'].default_value = 0.003; lens.location = (600, 300)
ellipse = tree.nodes.new('CompositorNodeEllipseMask')
ellipse.location = (300, 0); ellipse.width = 0.85; ellipse.height = 0.85
blur = tree.nodes.new('CompositorNodeBlur')
blur.location = (500, 0); blur.size_x = 200; blur.size_y = 200
mix = tree.nodes.new('CompositorNodeMixRGB')
mix.location = (900, 300); mix.blend_type = 'MULTIPLY'; mix.inputs[0].default_value = 0.15
tree.links.new(rl.outputs['Image'], glare.inputs['Image'])
tree.links.new(glare.outputs['Image'], lens.inputs['Image'])
tree.links.new(ellipse.outputs['Mask'], blur.inputs['Image'])
tree.links.new(lens.outputs['Image'], mix.inputs[1])
tree.links.new(blur.outputs['Image'], mix.inputs[2])
tree.links.new(mix.outputs['Image'], comp.inputs['Image'])
__result__ = 'Compositor: glare + lens + vignette'
""")
log(f"  {r}")

# ============================================================
# STEP 5: Add vehicle details (headlights, taillights, mirrors)
# ============================================================
log("=== STEP 5: Vehicle Details ===")
r = run_py("""
import bpy, math
details = 0
for obj in list(bpy.data.objects):
    if obj.type != 'MESH': continue
    n = obj.name.lower()
    if not any(k in n for k in ('body','sedan','suv','truck')): continue
    if any(k in n for k in ('wheel','tire','cabin','glass','hl','tl','mirror')): continue
    dims = obj.dimensions.copy()
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, segments=12, ring_count=6)
        hl = bpy.context.active_object
        hl.name = f'{obj.name}_HL'
        hl.parent = obj
        hl.location = (dims.x*0.48, side*dims.y*0.35, dims.z*0.3)
        hm = bpy.data.materials.new(name=hl.name+'_m')
        hm.use_nodes = True
        b = hm.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (1,0.98,0.9,1)
        b.inputs['Emission Strength'].default_value = 5.0
        hl.data.materials.append(hm)
        details += 1
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=0.15)
        tl = bpy.context.active_object
        tl.name = f'{obj.name}_TL'
        tl.parent = obj
        tl.location = (-dims.x*0.48, side*dims.y*0.35, dims.z*0.35)
        tl.scale = (0.3, 0.8, 0.4)
        tm = bpy.data.materials.new(name=tl.name+'_m')
        tm.use_nodes = True
        b = tm.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.8,0.02,0.02,1)
        b.inputs['Emission Strength'].default_value = 3.0
        tl.data.materials.append(tm)
        details += 1
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=0.08)
        m = bpy.context.active_object
        m.name = f'{obj.name}_Mirror'
        m.parent = obj
        m.location = (dims.x*0.15, side*(dims.y*0.52), dims.z*0.5)
        m.scale = (0.4, 0.15, 0.3)
        mm = bpy.data.materials.new(name=m.name+'_m')
        mm.use_nodes = True
        b = mm.node_tree.nodes['Principled BSDF']
        b.inputs['Metallic'].default_value = 0.9
        b.inputs['Roughness'].default_value = 0.05
        m.data.materials.append(mm)
        details += 1
__result__ = f'Details: {details}'
""")
log(f"  {r}")

# ============================================================
# STEP 6: Scale bar + compass
# ============================================================
log("=== STEP 6: Scale Bar + Compass ===")
r = run_py("""
import bpy
bpy.ops.mesh.primitive_cube_add(size=1, location=(8, -10, 0.02))
bar = bpy.context.active_object; bar.name = 'ScaleBar_10m'; bar.scale = (10, 0.15, 0.02)
mat = bpy.data.materials.new(name='ScaleBarMat')
mat.use_nodes = True; tree = mat.node_tree; links = tree.links
bsdf = tree.nodes['Principled BSDF']
ch = tree.nodes.new('ShaderNodeTexChecker')
ch.inputs['Scale'].default_value = 20.0
ch.inputs['Color1'].default_value = (0.95,0.95,0.95,1)
ch.inputs['Color2'].default_value = (0.05,0.05,0.05,1)
links.new(ch.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.9
bsdf.inputs['Emission Strength'].default_value = 0.5
bar.data.materials.append(mat)
fc = bpy.data.curves.new(name='ScaleLabel', type='FONT')
fc.body = '10m'; fc.size = 0.4; fc.align_x = 'CENTER'
lbl = bpy.data.objects.new('ScaleLabel', fc)
bpy.context.collection.objects.link(lbl); lbl.location = (8, -10.5, 0.1)
bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=0.8, location=(15, -9.6, 0.02))
arrow = bpy.context.active_object; arrow.name = 'NorthArrow'
am = bpy.data.materials.new(name='NArrow')
am.use_nodes = True; am.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9,0.1,0.1,1)
am.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.0
arrow.data.materials.append(am)
nc = bpy.data.curves.new(name='NLabel', type='FONT')
nc.body = 'N'; nc.size = 0.5; nc.align_x = 'CENTER'
nl = bpy.data.objects.new('NLabel', nc)
bpy.context.collection.objects.link(nl); nl.location = (15, -9, 0.02)
__result__ = f'Scale bar + compass. Total objects: {len(bpy.data.objects)}'
""")
log(f"  {r}")

# ============================================================
# STEP 7: RENDER Scene 1 — 4 cameras
# ============================================================
log("=== STEP 7: RENDERING SCENE 1 ===")
cameras = ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness"]
for i, cam in enumerate(cameras, 1):
    exhibit = f"1-{chr(64+i)}"
    out = os.path.join(RENDER_DIR, f"scene1_{i:02d}_{cam}.png")
    log(f"  Rendering {cam} (Exhibit {exhibit})...")
    
    # Add exhibit overlay
    run_py(f"""
import bpy
for obj in list(bpy.data.objects):
    if 'ExhibitLabel' in obj.name or 'CaseLabel' in obj.name:
        bpy.data.objects.remove(obj, do_unlink=True)
cam = bpy.data.objects.get('{cam}')
if cam:
    bpy.context.scene.camera = cam
    fc = bpy.data.curves.new(name='ExhibitLabel', type='FONT')
    fc.body = 'Exhibit {exhibit}  |  T-Bone Intersection Collision  |  DEMONSTRATIVE AID'
    fc.size = 0.016; fc.align_x = 'CENTER'
    lbl = bpy.data.objects.new('ExhibitLabel', fc)
    bpy.context.collection.objects.link(lbl)
    lbl.parent = cam; lbl.location = (0, -0.02, -0.18)
    tm = bpy.data.materials.new(name='ExhTxt')
    tm.use_nodes = True
    b = tm.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.95,0.95,0.95,1)
    b.inputs['Emission Strength'].default_value = 3.0
    fc.materials.append(tm)
    tc = bpy.data.curves.new(name='CaseLabel', type='FONT')
    tc.body = 'Case: 2026-CV-DEMO  |  OpenClaw Forensic Animation  |  {cam}'
    tc.size = 0.011; tc.align_x = 'CENTER'
    tl = bpy.data.objects.new('CaseLabel', tc)
    bpy.context.collection.objects.link(tl)
    tl.parent = cam; tl.location = (0, -0.02, -0.135)
    tm2 = bpy.data.materials.new(name='CaseTxt')
    tm2.use_nodes = True; tm2.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.7,0.7,0.75,1)
    tm2.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
    tc.materials.append(tm2)
__result__ = 'overlay for {cam}'
""")
    
    # Render
    t0 = time.time()
    r = run_py(f"""
import bpy
bpy.context.scene.render.filepath = '{out}'
bpy.ops.render.render(write_still=True)
__result__ = '{out}'
""", timeout=300)
    elapsed = time.time() - t0
    
    if os.path.exists(out):
        size_kb = os.path.getsize(out) // 1024
        log(f"    DONE: {size_kb}KB in {elapsed:.0f}s")
    else:
        log(f"    FAIL: {r} ({elapsed:.0f}s)")

# Summary
log("")
log("=== V8 SCENE 1 COMPLETE ===")
renders = [f for f in os.listdir(RENDER_DIR) if f.endswith('.png')]
for f in sorted(renders):
    size = os.path.getsize(os.path.join(RENDER_DIR, f)) // 1024
    log(f"  {f} ({size}KB)")
log(f"Total: {len(renders)} renders")
