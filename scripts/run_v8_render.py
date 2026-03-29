#!/usr/bin/env python3
"""V8 Render Pipeline — Execute improvements + render through Blender MCP bridge.

Connects to Blender addon on 127.0.0.1:9876, applies v8 upgrades, renders all scenes.
"""

import socket
import json
import os
import sys
import time
from datetime import datetime

BLENDER_HOST = "127.0.0.1"
BLENDER_PORT = 9876
RENDER_DIR = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v8"
THUMB_DIR = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v8_thumb"
SOCKET_TIMEOUT = 120  # 2 min for renders

os.makedirs(RENDER_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    sys.stdout.flush()

def send_blender(command, params=None, timeout=SOCKET_TIMEOUT):
    """Send command to Blender bridge and get response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((BLENDER_HOST, BLENDER_PORT))
    msg = json.dumps({"command": command, "params": params or {}})
    s.sendall(msg.encode() + b"\n")
    data = b""
    while True:
        try:
            chunk = s.recv(8192)
            if not chunk:
                break
            data += chunk
            try:
                json.loads(data.decode())
                break
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        except socket.timeout:
            break
    s.close()
    if data:
        try:
            return json.loads(data.decode())
        except:
            return {"error": data.decode()[:500]}
    return {"error": "no response"}

def run_py(code, timeout=SOCKET_TIMEOUT):
    """Execute Python code inside Blender."""
    return send_blender("execute_python", {"code": code}, timeout=timeout)

def render_camera(cam_name, output_path, timeout=120):
    """Render from a specific camera."""
    code = f"""
import bpy
cam = bpy.data.objects.get('{cam_name}')
if cam and cam.type == 'CAMERA':
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = '{output_path}'
    bpy.ops.render.render(write_still=True)
    __result__ = '{output_path}'
else:
    __result__ = 'Camera {cam_name} not found'
"""
    return run_py(code, timeout=timeout)

def create_thumbnail(src, dst, size=256):
    """Create a thumbnail using Blender's compositor."""
    code = f"""
import bpy
img = bpy.data.images.load('{src}')
img.scale({size}, int({size} * img.size[1] / img.size[0]))
img.save_render('{dst}')
bpy.data.images.remove(img)
__result__ = 'thumb saved'
"""
    return run_py(code, timeout=30)

# ============================================================
# SCENE DEFINITIONS
# ============================================================
SCENES = [
    {
        "num": 1, "title": "T-Bone Intersection Collision",
        "type": "intersection", "lighting": "day",
        "cameras": ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness"],
    },
    {
        "num": 2, "title": "Pedestrian Crosswalk Incident",
        "type": "crosswalk", "lighting": "day",
        "cameras": ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness"],
    },
    {
        "num": 3, "title": "Workplace Scaffolding Collapse",
        "type": "industrial", "lighting": "day",
        "cameras": ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness"],
    },
    {
        "num": 4, "title": "Nighttime Parking Lot Hit-and-Run",
        "type": "parking_night", "lighting": "night",
        "cameras": ["Cam_BirdEye", "Cam_DriverPOV", "Cam_Orbit", "Cam_Witness"],
    },
]


# ============================================================
# V8 UPGRADE FUNCTIONS
# ============================================================

def apply_v8_render_settings():
    """Apply v8 render settings: Cycles 256spl, OIDN, Filmic."""
    log("Applying v8 render settings...")
    code = """
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
s.cycles.volume_bounces = 0
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'
s.cycles.caustics_reflective = False
s.cycles.caustics_refractive = False
try: s.cycles.filter_glossy = 1.0
except: pass
s.cycles.sample_clamp_direct = 0
s.cycles.sample_clamp_indirect = 10
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGBA'
s.render.film_transparent = False
s.view_settings.view_transform = 'Filmic'
s.view_settings.look = 'Medium High Contrast'
s.view_settings.exposure = 0.3
__result__ = 'V8 render: Cycles 256spl, OIDN, Filmic, Metal GPU'
"""
    r = run_py(code)
    log(f"  Result: {r}")
    return r


def apply_v8_materials():
    """Apply upgraded procedural materials to all scene objects."""
    log("Applying v8 procedural materials...")

    # Pro asphalt
    code = """
import bpy
def create_pro_asphalt():
    mat = bpy.data.materials.new(name='Pro_Asphalt_v8')
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    for n in nodes: nodes.remove(n)
    out = nodes.new('ShaderNodeOutputMaterial'); out.location = (1200, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (900, 0)
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    noise = nodes.new('ShaderNodeTexNoise'); noise.location = (-400, 200)
    noise.inputs['Scale'].default_value = 120.0
    noise.inputs['Detail'].default_value = 12.0
    noise.inputs['Roughness'].default_value = 0.7
    voronoi = nodes.new('ShaderNodeTexVoronoi'); voronoi.location = (-400, -100)
    voronoi.inputs['Scale'].default_value = 60.0
    ramp = nodes.new('ShaderNodeValToRGB'); ramp.location = (-100, 200)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.03, 0.03, 0.035, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.065, 0.06, 0.058, 1)
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    bump = nodes.new('ShaderNodeBump'); bump.location = (600, -200)
    bump.inputs['Strength'].default_value = 0.25
    math_add = nodes.new('ShaderNodeMath'); math_add.operation = 'ADD'; math_add.location = (400, -200)
    links.new(voronoi.outputs['Distance'], math_add.inputs[0])
    links.new(noise.outputs['Fac'], math_add.inputs[1])
    links.new(math_add.outputs[0], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat

mat = create_pro_asphalt()
applied = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and any(k in obj.name.lower() for k in ('road', 'asphalt', 'street', 'ground', 'plane')):
        if obj.data and hasattr(obj.data, 'materials'):
            obj.data.materials.clear()
            obj.data.materials.append(mat)
            applied += 1
__result__ = f'Asphalt applied to {applied} objects'
"""
    r = run_py(code)
    log(f"  Asphalt: {r}")

    # Upgrade vehicle paints with clearcoat + orange peel
    code = """
import bpy
upgraded = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and any(k in obj.name.lower() for k in ('body', 'sedan', 'suv', 'truck', 'car', 'vehicle')):
        if not any(k in obj.name.lower() for k in ('wheel', 'tire', 'glass', 'cabin', 'window')):
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
                        # Add bump for orange peel
                        tree = mat.node_tree
                        noise = tree.nodes.new('ShaderNodeTexNoise')
                        noise.inputs['Scale'].default_value = 800.0
                        noise.inputs['Detail'].default_value = 6.0
                        bump = tree.nodes.new('ShaderNodeBump')
                        bump.inputs['Strength'].default_value = 0.008
                        tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
                        tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
                        upgraded += 1
__result__ = f'Vehicle paint upgraded: {upgraded} materials'
"""
    r = run_py(code)
    log(f"  Vehicle paint: {r}")

    # Upgrade tires/wheels with rubber material
    code = """
import bpy
upgraded = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and any(k in obj.name.lower() for k in ('wheel', 'tire')):
        for mat in (obj.data.materials if obj.data else []):
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get('Principled BSDF')
                if bsdf:
                    bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.025, 1)
                    bsdf.inputs['Roughness'].default_value = 0.75
                    bsdf.inputs['Metallic'].default_value = 0.0
                    upgraded += 1
__result__ = f'Rubber applied: {upgraded}'
"""
    r = run_py(code)
    log(f"  Rubber: {r}")

    # Glass upgrade for cabins/windows
    code = """
import bpy
upgraded = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and any(k in obj.name.lower() for k in ('cabin', 'glass', 'window', 'windshield')):
        for mat in (obj.data.materials if obj.data else []):
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get('Principled BSDF')
                if bsdf:
                    bsdf.inputs['Base Color'].default_value = (0.7, 0.75, 0.8, 1)
                    bsdf.inputs['Roughness'].default_value = 0.0
                    bsdf.inputs['Alpha'].default_value = 0.35
                    try: bsdf.inputs['Transmission Weight'].default_value = 0.92
                    except:
                        try: bsdf.inputs['Transmission'].default_value = 0.92
                        except: pass
                    try: bsdf.inputs['IOR'].default_value = 1.52
                    except: pass
                    upgraded += 1
            try: mat.surface_render_method = 'DITHERED'
            except:
                try: mat.blend_method = 'BLEND'
                except: pass
__result__ = f'Glass applied: {upgraded}'
"""
    r = run_py(code)
    log(f"  Glass: {r}")

    # Concrete for curbs/sidewalks
    code = """
import bpy
upgraded = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and any(k in obj.name.lower() for k in ('curb', 'sidewalk', 'concrete', 'median')):
        for mat in (obj.data.materials if obj.data else []):
            if mat and mat.use_nodes:
                bsdf = mat.node_tree.nodes.get('Principled BSDF')
                if bsdf:
                    bsdf.inputs['Base Color'].default_value = (0.32, 0.31, 0.29, 1)
                    bsdf.inputs['Roughness'].default_value = 0.85
                    upgraded += 1
__result__ = f'Concrete applied: {upgraded}'
"""
    r = run_py(code)
    log(f"  Concrete: {r}")
    return True


def apply_v8_lighting_day():
    """Apply v8 daytime 3-point lighting rig."""
    log("Applying v8 day lighting...")
    code = """
import bpy, math
scene = bpy.context.scene

# Remove existing lights
for obj in list(bpy.data.objects):
    if obj.type == 'LIGHT' and 'v8' not in obj.name:
        pass  # Keep existing, just add new ones

# Key Sun
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20))
sun = bpy.context.active_object
sun.name = 'Key_Sun_v8'
sun.data.energy = 4.0
sun.data.angle = math.radians(0.545)
sun.rotation_euler = (math.radians(45), 0, math.radians(160))
sun.data.color = (1.0, 0.95, 0.9)

# Fill light
bpy.ops.object.light_add(type='AREA', location=(-15, -10, 8))
fill = bpy.context.active_object
fill.name = 'Fill_Area_v8'
fill.data.energy = 200.0
fill.data.size = 12.0
fill.data.color = (0.85, 0.9, 1.0)
fill.rotation_euler = (math.radians(60), 0, math.radians(-30))

# Rim light
bpy.ops.object.light_add(type='AREA', location=(10, 15, 6))
rim = bpy.context.active_object
rim.name = 'Rim_Area_v8'
rim.data.energy = 150.0
rim.data.size = 8.0
rim.data.color = (1.0, 0.95, 0.85)
rim.rotation_euler = (math.radians(70), 0, math.radians(145))

__result__ = 'V8 day lighting: Key + Fill + Rim'
"""
    r = run_py(code)
    log(f"  Result: {r}")
    return r


def apply_v8_compositor():
    """Apply v8 compositor: glare + lens distortion + vignette."""
    log("Applying v8 compositor...")
    code = """
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
lens.inputs['Dispersion'].default_value = 0.003
lens.location = (600, 300)

# Vignette
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

__result__ = 'V8 compositor: glare + lens + vignette'
"""
    r = run_py(code)
    log(f"  Result: {r}")
    return r


def add_exhibit_overlay(scene_num, scene_title, cam_name, exhibit_ref):
    """Add exhibit text overlay for the current camera."""
    code = f"""
import bpy

# Remove old exhibit labels
for obj in list(bpy.data.objects):
    if 'ExhibitLabel' in obj.name or 'CaseLabel' in obj.name or 'ScaleBar' in obj.name or 'NorthArrow' in obj.name or 'NorthLabel' in obj.name or 'ScaleLabel' in obj.name:
        bpy.data.objects.remove(obj, do_unlink=True)

cam = bpy.context.scene.camera
if cam:
    # Bottom label
    fc = bpy.data.curves.new(name='ExhibitLabel_v8', type='FONT')
    fc.body = 'Exhibit {exhibit_ref}  |  {scene_title}  |  DEMONSTRATIVE AID'
    fc.size = 0.016
    fc.align_x = 'CENTER'
    lbl = bpy.data.objects.new('ExhibitLabel_v8', fc)
    bpy.context.collection.objects.link(lbl)
    lbl.parent = cam
    lbl.location = (0, -0.02, -0.18)
    
    tmat = bpy.data.materials.new(name='ExhTextMat')
    tmat.use_nodes = True
    b = tmat.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1)
    b.inputs['Emission Strength'].default_value = 3.0
    try: b.inputs['Emission Color'].default_value = (0.95, 0.95, 0.95, 1)
    except: pass
    fc.materials.append(tmat)
    
    # Top label
    tc = bpy.data.curves.new(name='CaseLabel_v8', type='FONT')
    tc.body = 'Case: 2026-CV-DEMO  |  OpenClaw Forensic Animation System  |  {cam_name}'
    tc.size = 0.011
    tc.align_x = 'CENTER'
    tlbl = bpy.data.objects.new('CaseLabel_v8', tc)
    bpy.context.collection.objects.link(tlbl)
    tlbl.parent = cam
    tlbl.location = (0, -0.02, -0.135)
    
    tmat2 = bpy.data.materials.new(name='CaseTextMat')
    tmat2.use_nodes = True
    b2 = tmat2.node_tree.nodes['Principled BSDF']
    b2.inputs['Base Color'].default_value = (0.7, 0.7, 0.75, 1)
    b2.inputs['Emission Strength'].default_value = 2.0
    try: b2.inputs['Emission Color'].default_value = (0.7, 0.7, 0.75, 1)
    except: pass
    tc.materials.append(tmat2)

__result__ = 'Exhibit overlay: {exhibit_ref}'
"""
    return run_py(code)


def add_scale_bar():
    """Add physical scale bar to the scene."""
    code = """
import bpy

# Remove old scale bars
for obj in list(bpy.data.objects):
    if 'ScaleBar' in obj.name or 'ScaleLabel' in obj.name or 'NorthArrow' in obj.name or 'NorthLabel' in obj.name:
        bpy.data.objects.remove(obj, do_unlink=True)

bpy.ops.mesh.primitive_cube_add(size=1, location=(8, -10, 0.02))
bar = bpy.context.active_object
bar.name = 'ScaleBar_10m'
bar.scale = (10, 0.15, 0.02)

mat = bpy.data.materials.new(name='ScaleBarMat')
mat.use_nodes = True
tree = mat.node_tree
nodes = tree.nodes; links = tree.links
bsdf = nodes['Principled BSDF']
checker = nodes.new('ShaderNodeTexChecker')
checker.inputs['Scale'].default_value = 20.0
checker.inputs['Color1'].default_value = (0.95, 0.95, 0.95, 1)
checker.inputs['Color2'].default_value = (0.05, 0.05, 0.05, 1)
links.new(checker.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.9
bsdf.inputs['Emission Strength'].default_value = 0.5
try: links.new(checker.outputs['Color'], bsdf.inputs['Emission Color'])
except: pass
bar.data.materials.append(mat)

fc = bpy.data.curves.new(name='ScaleLabel', type='FONT')
fc.body = '10m'
fc.size = 0.4
fc.align_x = 'CENTER'
lbl = bpy.data.objects.new('ScaleLabel', fc)
bpy.context.collection.objects.link(lbl)
lbl.location = (8, -10.5, 0.1)
lmat = bpy.data.materials.new(name='ScaleLblMat')
lmat.use_nodes = True
lmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1,1,1,1)
lmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
fc.materials.append(lmat)

# North arrow
bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=0.8, location=(15, -9.6, 0.02))
arrow = bpy.context.active_object
arrow.name = 'NorthArrow'
amat = bpy.data.materials.new(name='NArrowMat')
amat.use_nodes = True
amat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.1, 0.1, 1)
amat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.0
arrow.data.materials.append(amat)

nfc = bpy.data.curves.new(name='NorthLabel', type='FONT')
nfc.body = 'N'
nfc.size = 0.5
nfc.align_x = 'CENTER'
nlbl = bpy.data.objects.new('NorthLabel', nfc)
bpy.context.collection.objects.link(nlbl)
nlbl.location = (15, -9, 0.02)
nlmat = bpy.data.materials.new(name='NLblMat')
nlmat.use_nodes = True
nlmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1,1,1,1)
nlmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
nfc.materials.append(nlmat)

__result__ = 'Scale bar + compass added'
"""
    return run_py(code)


def add_vehicle_details():
    """Add headlights, taillights, mirrors to vehicles."""
    log("Adding vehicle detail geometry...")
    code = """
import bpy, math

details = 0
for obj in bpy.data.objects:
    if obj.type != 'MESH':
        continue
    n = obj.name.lower()
    if not any(k in n for k in ('body', 'sedan', 'suv', 'truck')):
        continue
    if any(k in n for k in ('wheel', 'tire', 'cabin', 'glass')):
        continue
    
    dims = obj.dimensions.copy()
    loc = obj.location.copy()
    
    # Headlights
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, segments=12, ring_count=6, location=(0,0,0))
        hl = bpy.context.active_object
        hl.name = f'{obj.name}_HL_{"L" if side<0 else "R"}'
        hl.parent = obj
        hl.location = (dims.x*0.48, side*dims.y*0.35, dims.z*0.3)
        hmat = bpy.data.materials.new(name=hl.name+'_mat')
        hmat.use_nodes = True
        b = hmat.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (1.0, 0.98, 0.9, 1)
        b.inputs['Emission Strength'].default_value = 5.0
        try: b.inputs['Emission Color'].default_value = (1.0, 0.98, 0.9, 1)
        except: pass
        hl.data.materials.append(hmat)
        details += 1
    
    # Taillights
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=0.15, location=(0,0,0))
        tl = bpy.context.active_object
        tl.name = f'{obj.name}_TL_{"L" if side<0 else "R"}'
        tl.parent = obj
        tl.location = (-dims.x*0.48, side*dims.y*0.35, dims.z*0.35)
        tl.scale = (0.3, 0.8, 0.4)
        tlmat = bpy.data.materials.new(name=tl.name+'_mat')
        tlmat.use_nodes = True
        b = tlmat.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.8, 0.02, 0.02, 1)
        b.inputs['Emission Strength'].default_value = 3.0
        try: b.inputs['Emission Color'].default_value = (0.8, 0.02, 0.02, 1)
        except: pass
        tl.data.materials.append(tlmat)
        details += 1
    
    # Side mirrors
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=0.08, location=(0,0,0))
        m = bpy.context.active_object
        m.name = f'{obj.name}_Mirror_{"L" if side<0 else "R"}'
        m.parent = obj
        m.location = (dims.x*0.15, side*(dims.y*0.52), dims.z*0.5)
        m.scale = (0.4, 0.15, 0.3)
        mmat = bpy.data.materials.new(name=m.name+'_mat')
        mmat.use_nodes = True
        b = mmat.node_tree.nodes['Principled BSDF']
        b.inputs['Metallic'].default_value = 0.9
        b.inputs['Roughness'].default_value = 0.05
        m.data.materials.append(mmat)
        details += 1

__result__ = f'Vehicle details added: {details} parts'
"""
    r = run_py(code)
    log(f"  Result: {r}")
    return r


# ============================================================
# MAIN PIPELINE
# ============================================================
def main():
    log("=" * 60)
    log("V8 FORENSIC RENDER PIPELINE")
    log("=" * 60)

    # Step 1: Apply global upgrades
    apply_v8_render_settings()
    apply_v8_materials()
    apply_v8_lighting_day()
    apply_v8_compositor()
    add_vehicle_details()
    add_scale_bar()

    log("")
    log("=" * 60)
    log("RENDERING ALL SCENES")
    log("=" * 60)

    total_renders = 0
    for scene in SCENES:
        snum = scene["num"]
        stitle = scene["title"]
        cams = scene["cameras"]

        log(f"")
        log(f"--- Scene {snum}: {stitle} ---")

        # Build scene via bridge
        log(f"  Building forensic scene {snum}...")
        r = send_blender("forensic_scene", {
            "action": "create_scene",
            "scene_type": scene["type"],
            "scene_index": snum - 1,
        })
        log(f"  Scene build: {str(r)[:200]}")

        # Re-apply materials + lighting after scene rebuild
        apply_v8_materials()
        if scene["lighting"] == "night":
            log("  Applying night lighting...")
            night_code = """
import bpy, math
# Add parking lot lights
positions = [(-8,-8,7),(8,-8,7),(-8,8,7),(8,8,7),(0,0,8)]
for i, pos in enumerate(positions):
    bpy.ops.object.light_add(type='AREA', location=pos)
    l = bpy.context.active_object
    l.name = f'ParkingLight_{i}_v8'
    l.data.energy = 800.0
    l.data.size = 2.0
    l.data.color = (1.0, 0.7, 0.3)
    l.rotation_euler = (math.radians(90), 0, 0)
# Dim world
w = bpy.context.scene.world
if w and w.use_nodes:
    for n in w.node_tree.nodes:
        if n.type == 'BACKGROUND':
            n.inputs['Color'].default_value = (0.005, 0.008, 0.02, 1)
            n.inputs['Strength'].default_value = 0.3
__result__ = 'Night lighting applied'
"""
            run_py(night_code)
        else:
            apply_v8_lighting_day()

        apply_v8_compositor()
        add_scale_bar()

        # Render each camera
        for i, cam in enumerate(cams, 1):
            exhibit_ref = f"{snum}-{chr(64+i)}"
            out_path = os.path.join(RENDER_DIR, f"scene{snum}_{i:02d}_{cam}.png")
            thumb_path = os.path.join(THUMB_DIR, f"scene{snum}_{i:02d}_{cam}_tiny.png")

            log(f"  Rendering {cam} -> Exhibit {exhibit_ref}")

            # Add exhibit overlay for this camera
            add_exhibit_overlay(snum, stitle, cam, exhibit_ref)

            # Render
            r = render_camera(cam, out_path, timeout=180)
            log(f"    Result: {str(r)[:150]}")

            if os.path.exists(out_path):
                size_kb = os.path.getsize(out_path) // 1024
                log(f"    Saved: {out_path} ({size_kb}KB)")
                total_renders += 1

                # Thumbnail
                create_thumbnail(out_path, thumb_path)
            else:
                log(f"    WARNING: Render output not found!")

        # Save blend
        blend_path = os.path.join(os.path.dirname(RENDER_DIR), f"v8_scene{snum}.blend")
        run_py(f"import bpy; bpy.ops.wm.save_as_mainfile(filepath='{blend_path}')")
        log(f"  Saved: {blend_path}")

    log("")
    log("=" * 60)
    log(f"ALL SCENES COMPLETE — {total_renders} renders")
    log("=" * 60)

    # List final renders
    for f in sorted(os.listdir(RENDER_DIR)):
        if f.endswith('.png'):
            size_kb = os.path.getsize(os.path.join(RENDER_DIR, f)) // 1024
            log(f"  {f} ({size_kb}KB)")


if __name__ == "__main__":
    main()
