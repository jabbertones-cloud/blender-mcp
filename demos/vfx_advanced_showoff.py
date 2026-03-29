#!/usr/bin/env python3
"""
OpenClaw Blender MCP — Advanced VFX Showoff Demo (Blender 5.1)
================================================================
Demonstrates 13 advanced VFX techniques most Blender users never learn,
all driven entirely via MCP commands.

Run: python3 demos/vfx_advanced_showoff.py
"""

import json
import socket
import sys
import time
import math

HOST = "127.0.0.1"
PORT = 9876
TIMEOUT = 30.0

_id = 0


def send(command, params=None):
    global _id
    _id += 1
    payload = {"id": str(_id), "command": command, "params": params or {}}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(TIMEOUT)
    sock.connect((HOST, PORT))
    sock.sendall(json.dumps(payload).encode("utf-8"))
    chunks = []
    while True:
        chunk = sock.recv(1048576)
        if not chunk:
            break
        chunks.append(chunk)
        try:
            data = json.loads(b"".join(chunks).decode("utf-8"))
            sock.close()
            return data.get("result", data)
        except json.JSONDecodeError:
            continue
    sock.close()
    return json.loads(b"".join(chunks).decode("utf-8"))


def step(msg, command, params=None):
    print(f"  \u2192 {msg}...", end=" ", flush=True)
    result = send(command, params)
    if isinstance(result, dict) and "error" in result:
        print(f"\u26a0 {result['error']}")
    else:
        print("\u2713")
    return result


def run_py(msg, code):
    """Execute Python code in Blender and print status."""
    print(f"  \u2192 {msg}...", end=" ", flush=True)
    result = send("execute_python", {"code": code})
    if isinstance(result, dict) and "error" in result:
        print(f"\u26a0 {result['error']}")
    else:
        print("\u2713")
    return result


def main():
    t0 = time.time()

    print("\n" + "=" * 72)
    print("  OpenClaw Blender MCP \u2014 Advanced VFX Showoff (Blender 5.1)")
    print("=" * 72 + "\n")

    # 1. SCENE SETUP
    print("[1/13] Scene Setup")
    step("Load cinematic template", "scene_template", {"template": "cinematic"})
    run_py("Clear default objects", """
import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
__result__ = "cleared"
""")

    # 2. SUBSURFACE SCATTERING
    print("\n[2/13] Subsurface Scattering \u2014 Skin-Like Material")
    step("Create SSS sphere", "create_object", {
        "type": "sphere", "name": "SSS_Skin", "location": [-4, 0, 1.5], "scale": [1.5, 1.5, 1.5]
    })
    step("Subdivide for smoothness", "apply_modifier", {
        "object_name": "SSS_Skin", "modifier_type": "SUBSURF", "action": "add", "level": 3
    })
    run_py("Apply SSS skin shader", """
import bpy
obj = bpy.data.objects.get("SSS_Skin")
mat = bpy.data.materials.new("SkinSSS")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.85, 0.65, 0.52, 1.0)
bsdf.inputs["Subsurface Weight"].default_value = 0.8
bsdf.inputs["Subsurface Radius"].default_value = (1.5, 1.0, 0.75)
bsdf.inputs["Subsurface Scale"].default_value = 0.1
bsdf.inputs["Roughness"].default_value = 0.35
bsdf.inputs["Specular IOR Level"].default_value = 0.5
if obj and hasattr(obj.data, "materials"):
    obj.data.materials.append(mat)
__result__ = "sss applied"
""")

    # 3. GLASS CAUSTICS
    print("\n[3/13] Glass Caustics \u2014 Diamond Refraction")
    step("Create diamond sphere", "create_object", {
        "type": "sphere", "name": "Diamond", "location": [0, 0, 1.5], "scale": [1.2, 1.2, 1.2]
    })
    step("Subdivide diamond", "apply_modifier", {
        "object_name": "Diamond", "modifier_type": "SUBSURF", "action": "add", "level": 2
    })
    run_py("Apply diamond caustics shader", """
import bpy
obj = bpy.data.objects.get("Diamond")
mat = bpy.data.materials.new("DiamondCaustics")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.95, 0.95, 1.0, 1.0)
bsdf.inputs["Transmission Weight"].default_value = 1.0
bsdf.inputs["IOR"].default_value = 2.42
bsdf.inputs["Roughness"].default_value = 0.0
bsdf.inputs["Coat Weight"].default_value = 1.0
bsdf.inputs["Coat Roughness"].default_value = 0.05
if obj and hasattr(obj.data, "materials"):
    obj.data.materials.append(mat)
__result__ = "diamond applied"
""")

    # 4. VOLUMETRIC GOD RAYS
    print("\n[4/13] Volumetric God Rays")
    step("Create god ray cone", "create_object", {
        "type": "cone", "name": "GodRayCone", "location": [4, -2, 4],
        "scale": [3, 3, 6], "rotation": [3.14159, 0, 0]
    })
    run_py("Apply volume scatter shader", """
import bpy
obj = bpy.data.objects.get("GodRayCone")
mat = bpy.data.materials.new("VolumeGodRay")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()
vol_scatter = nodes.new(type="ShaderNodeVolumeScatter")
vol_scatter.inputs["Color"].default_value = (1.0, 0.95, 0.8, 1.0)
vol_scatter.inputs["Density"].default_value = 0.08
vol_scatter.inputs["Anisotropy"].default_value = 0.6
output = nodes.new(type="ShaderNodeOutputMaterial")
links.new(vol_scatter.outputs[0], output.inputs["Volume"])
if obj and hasattr(obj.data, "materials"):
    obj.data.materials.append(mat)
__result__ = "god rays applied"
""")
    run_py("Add spotlight for god rays", """
import bpy
bpy.ops.object.light_add(type="SPOT", location=(4, -2, 10))
spot = bpy.context.active_object
spot.name = "GodRaySpot"
spot.data.energy = 500
spot.data.color = (1.0, 0.9, 0.7)
spot.data.spot_size = 0.8
spot.data.shadow_soft_size = 0.5
__result__ = "spotlight added"
""")

    # 5. PROCEDURAL DISPLACEMENT
    print("\n[5/13] Procedural Displacement \u2014 Geometry Nodes")
    step("Create displacement sphere", "create_object", {
        "type": "sphere", "name": "DisplaceSphere", "location": [4, 3, 1.5], "scale": [1.5, 1.5, 1.5]
    })
    step("Subdivide for detail", "apply_modifier", {
        "object_name": "DisplaceSphere", "modifier_type": "SUBSURF", "action": "add", "level": 4
    })
    run_py("Add noise displacement via geometry nodes", """
import bpy
obj = bpy.data.objects.get("DisplaceSphere")
if obj:
    bpy.context.view_layer.objects.active = obj
    mod = obj.modifiers.new(name="NoiseDisplace", type="NODES")
    bpy.ops.node.new_geometry_node_group_assign()
    if mod.node_group:
        tree = mod.node_group
        nodes = tree.nodes
        links = tree.links
        group_in = None
        group_out = None
        for n in nodes:
            if n.type == "GROUP_INPUT": group_in = n
            if n.type == "GROUP_OUTPUT": group_out = n
        set_pos = nodes.new(type="GeometryNodeSetPosition")
        noise = nodes.new(type="ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = 3.0
        noise.inputs["Detail"].default_value = 6.0
        math_node = nodes.new(type="ShaderNodeVectorMath")
        math_node.operation = "SCALE"
        math_node.inputs[3].default_value = 0.3
        normal = nodes.new(type="GeometryNodeInputNormal")
        links.new(normal.outputs[0], math_node.inputs[0])
        links.new(noise.outputs["Fac"], math_node.inputs[3])
        links.new(math_node.outputs[0], set_pos.inputs["Offset"])
        if group_in:
            links.new(group_in.outputs[0], set_pos.inputs["Geometry"])
        if group_out:
            links.new(set_pos.outputs[0], group_out.inputs[0])
__result__ = "displacement applied"
""")
    step("Apply metal to displaced sphere", "procedural_material", {
        "preset": "metal", "object_name": "DisplaceSphere",
        "color": [0.8, 0.5, 0.2, 1], "roughness": 0.2
    })

    # 6. PARTICLE SYSTEM SPARKS
    print("\n[6/13] Particle System \u2014 Sparks Emitter")
    step("Create spark emitter", "create_object", {
        "type": "sphere", "name": "SparkEmitter", "location": [-4, 3, 0.5], "scale": [0.3, 0.3, 0.3]
    })
    run_py("Configure spark particle system", """
import bpy
obj = bpy.data.objects.get("SparkEmitter")
if obj:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.ops.object.particle_system_add()
    ps = obj.particle_systems[-1]
    s = ps.settings
    s.count = 500
    s.lifetime = 50
    s.lifetime_random = 0.3
    s.emit_from = "FACE"
    s.normal_factor = 5.0
    s.factor_random = 1.5
    s.physics_type = "NEWTON"
    s.particle_size = 0.02
    s.size_random = 0.5
    s.effector_weights.gravity = 0.3
__result__ = "sparks configured"
""")
    step("Apply emissive to sparks emitter", "set_material", {
        "object_name": "SparkEmitter", "material_name": "SparkGlow",
        "color": [1, 0.6, 0.1, 1], "emission_color": [1, 0.5, 0, 1], "emission_strength": 20
    })

    # 7. DEPTH OF FIELD
    print("\n[7/13] Depth of Field \u2014 Shallow DoF with Bokeh")
    run_py("Configure camera DoF (f/1.4, 7-blade bokeh)", """
import bpy
cam = None
for obj in bpy.data.objects:
    if obj.type == "CAMERA":
        cam = obj
        break
if not cam:
    bpy.ops.object.camera_add(location=(0, -10, 5))
    cam = bpy.context.active_object
cam.data.dof.use_dof = True
cam.data.dof.focus_distance = 6.0
cam.data.dof.aperture_fstop = 1.4
cam.data.dof.aperture_blades = 7
cam.data.dof.aperture_ratio = 1.0
cam.data.lens = 50
__result__ = "dof configured"
""")

    # 8. COMPOSITING CHAIN (Blender 5.1: glare settings are inputs, not attributes)
    print("\n[8/13] Compositing \u2014 Glare + Chromatic Aberration")
    run_py("Build compositor node chain", """
import bpy
scene = bpy.context.scene
scene.use_nodes = True
ng = scene.compositing_node_group
if ng is None:
    ng = bpy.data.node_groups.new("Compositing Nodetree", "CompositorNodeTree")
    scene.compositing_node_group = ng
nodes = ng.nodes
links = ng.links
nodes.clear()
# Render layers input
rl = nodes.new(type="CompositorNodeRLayers")
rl.location = (0, 0)
# Glare bloom (Blender 5.1: settings are socket inputs)
glare = nodes.new(type="CompositorNodeGlare")
glare.location = (300, 0)
# Set glare params via inputs (5.1 API)
for inp in glare.inputs:
    if inp.name == "Threshold": inp.default_value = 0.8
    if inp.name == "Strength": inp.default_value = 0.3
    pass  # Quality is MENU type, skip
# Lens distortion with chromatic aberration
lens = nodes.new(type="CompositorNodeLensdist")
lens.location = (600, 0)
# Blender 5.1: Jitter/Dispersion are socket inputs
for inp in lens.inputs:
    if inp.name == "Jitter" and inp.type == "VALUE": inp.default_value = 1.0
    if inp.name == "Dispersion" and inp.type == "VALUE": inp.default_value = 0.03
# Output (5.1: CompositorNodeComposite removed, use Viewer + GroupOutput)
viewer = nodes.new(type="CompositorNodeViewer")
viewer.location = (900, 0)
group_out = nodes.new(type="NodeGroupOutput")
group_out.location = (900, -200)
# Connect chain: RL -> Glare -> Lens -> Output
links.new(rl.outputs["Image"], glare.inputs["Image"])
links.new(glare.outputs["Image"], lens.inputs["Image"])
links.new(lens.outputs["Image"], viewer.inputs["Image"])
try:
    links.new(lens.outputs["Image"], group_out.inputs[0])
except:
    pass
__result__ = "compositor built"
""")

    # 9. PROCEDURAL FOG VOLUME
    print("\n[9/13] Procedural Fog Volume")
    step("Create fog volume cube", "create_object", {
        "type": "cube", "name": "FogVolume", "location": [0, 0, 3], "scale": [15, 15, 6]
    })
    run_py("Apply noise-driven fog shader", """
import bpy
obj = bpy.data.objects.get("FogVolume")
mat = bpy.data.materials.new("ProceduralFog")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
nodes.clear()
vol = nodes.new(type="ShaderNodeVolumePrincipled")
vol.inputs["Color"].default_value = (0.8, 0.85, 1.0, 1.0)
vol.inputs["Density"].default_value = 0.015
noise = nodes.new(type="ShaderNodeTexNoise")
noise.inputs["Scale"].default_value = 2.0
noise.inputs["Detail"].default_value = 4.0
math_n = nodes.new(type="ShaderNodeMath")
math_n.operation = "MULTIPLY"
math_n.inputs[1].default_value = 0.03
links.new(noise.outputs["Fac"], math_n.inputs[0])
links.new(math_n.outputs[0], vol.inputs["Density"])
output = nodes.new(type="ShaderNodeOutputMaterial")
links.new(vol.outputs[0], output.inputs["Volume"])
if obj and hasattr(obj.data, "materials"):
    obj.data.materials.append(mat)
__result__ = "fog applied"
""")

    # 10. IRIDESCENT MATERIAL
    print("\n[10/13] Iridescent / Holographic Material")
    step("Create iridescent torus", "create_object", {
        "type": "torus", "name": "HoloTorus", "location": [0, 3, 1.5], "scale": [1.2, 1.2, 1.2]
    })
    run_py("Apply rainbow holographic shader", """
import bpy
obj = bpy.data.objects.get("HoloTorus")
mat = bpy.data.materials.new("Iridescent")
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links
bsdf = nodes.get("Principled BSDF")
lw = nodes.new(type="ShaderNodeLayerWeight")
lw.inputs["Blend"].default_value = 0.4
ramp = nodes.new(type="ShaderNodeValToRGB")
cr = ramp.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (0.0, 0.2, 1.0, 1.0)
e1 = cr.elements.new(0.25)
e1.color = (0.0, 1.0, 0.5, 1.0)
e2 = cr.elements.new(0.5)
e2.color = (1.0, 1.0, 0.0, 1.0)
e3 = cr.elements.new(0.75)
e3.color = (1.0, 0.2, 0.0, 1.0)
cr.elements[1].position = 1.0
cr.elements[1].color = (0.8, 0.0, 1.0, 1.0)
links.new(lw.outputs["Facing"], ramp.inputs["Fac"])
links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Metallic"].default_value = 0.9
bsdf.inputs["Roughness"].default_value = 0.15
bsdf.inputs["Coat Weight"].default_value = 1.0
bsdf.inputs["Coat Roughness"].default_value = 0.05
if obj and hasattr(obj.data, "materials"):
    obj.data.materials.append(mat)
__result__ = "iridescent applied"
""")

    # 11. MOTION BLUR
    print("\n[11/13] Motion Blur")
    run_py("Enable motion blur", """
import bpy
scene = bpy.context.scene
scene.render.use_motion_blur = True
scene.render.motion_blur_shutter = 0.5
__result__ = "motion blur enabled"
""")

    # 12. 3-POINT CINEMATIC LIGHTING
    print("\n[12/13] 3-Point Cinematic Lighting Rig")
    run_py("Add key light (warm area)", """
import bpy
bpy.ops.object.light_add(type="AREA", location=(5, -4, 6))
key = bpy.context.active_object
key.name = "KeyLight"
key.data.energy = 200
key.data.color = (1.0, 0.9, 0.75)
key.data.size = 3.0
key.rotation_euler = (0.8, 0.2, 0.3)
__result__ = "key light"
""")
    run_py("Add fill light (cool area)", """
import bpy
bpy.ops.object.light_add(type="AREA", location=(-5, -3, 4))
fill = bpy.context.active_object
fill.name = "FillLight"
fill.data.energy = 80
fill.data.color = (0.7, 0.8, 1.0)
fill.data.size = 4.0
fill.rotation_euler = (0.8, -0.2, -0.5)
__result__ = "fill light"
""")
    run_py("Add rim light (bright backlight)", """
import bpy
bpy.ops.object.light_add(type="SPOT", location=(0, 6, 5))
rim = bpy.context.active_object
rim.name = "RimLight"
rim.data.energy = 400
rim.data.color = (1.0, 0.95, 0.9)
rim.data.spot_size = 1.2
rim.rotation_euler = (-0.6, 3.14, 0)
__result__ = "rim light"
""")

    # 13. TURNTABLE ANIMATION
    print("\n[13/13] 360\u00b0 Turntable Camera Animation")
    step("Create turntable animation", "advanced_animation", {
        "action": "turntable", "target": "Diamond",
        "frames": 240, "radius": 12, "height": 5
    })

    # GROUND PLANE
    step("Create ground plane", "create_object", {
        "type": "plane", "name": "Ground", "location": [0, 0, 0], "scale": [20, 20, 1]
    })
    step("Apply marble to ground", "procedural_material", {
        "preset": "marble", "object_name": "Ground", "scale": 3.0
    })

    # RENDER SETTINGS
    print("\n\u250c\u2500 Render Configuration \u2500\u2510")
    step("Set high quality render", "render_presets", {"preset": "high_quality", "samples": 128})

    # FINAL ANALYSIS
    print("\n\u250c\u2500 Final Scene Analysis \u2500\u2510")
    analysis = send("scene_analyze", {})
    stats = analysis.get("statistics", {})
    elapsed = time.time() - t0
    print(f"  Objects:   {stats.get('total_objects', '?')}")
    print(f"  Vertices:  {stats.get('total_vertices', '?')}")
    print(f"  Faces:     {stats.get('total_faces', '?')}")
    print(f"  Lights:    {stats.get('total_lights', '?')}")
    print(f"  Cameras:   {stats.get('total_cameras', '?')}")
    print(f"  Materials: {stats.get('materials_count', '?')}")
    print(f"  Time:      {elapsed:.1f}s")

    print("\n" + "=" * 72)
    print("  \u2713 Advanced VFX Showoff COMPLETE!")
    print("=" * 72)
    print("  Techniques demonstrated:")
    techniques = [
        "Subsurface scattering (realistic skin SSS)",
        "Glass caustics (diamond IOR 2.42, full transmission)",
        "Volumetric god rays (volume scatter cone + spotlight)",
        "Procedural displacement (geometry nodes + noise)",
        "Particle system sparks (500 physics particles)",
        "Depth of field (f/1.4, 7-blade bokeh)",
        "Compositing chain (glare + chromatic aberration)",
        "Procedural fog volume (noise-driven density)",
        "Iridescent holographic material (LayerWeight rainbow)",
        "Motion blur (shutter 0.5)",
        "3-point cinematic lighting (key + fill + rim)",
        "360\u00b0 turntable camera animation",
        "Marble ground + production render setup",
    ]
    for i, t in enumerate(techniques, 1):
        print(f"    {i:2d}. {t}")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()
