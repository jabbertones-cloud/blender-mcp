#!/usr/bin/env python3
"""
DEMO 04: Luxury Watch Animation (Rolex-style)
===============================================
Recreates luxury watch product visualization:
- Models watch from primitives (case + bezel + dial + crown + band links)
- Gold metallic case + polished chrome bezel + glass crystal
- Jewelry sparkle lighting rig
- Full commercial sequence: establishing → turntable → detail → final hero
- Demonstrates multi-shot commercial builder

Demonstrates: product_commercial_sequence, jewelry lighting,
             gold/chrome/glass materials, multi-shot timeline
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from product_animation_recipes import send, run_python, apply_material, setup_lighting, \
    configure_render, setup_compositor_product

def build_watch():
    print("═══ DEMO 04: Luxury Watch ═══\n")
    
    print("[1/9] Clearing scene...")
    run_python("""
import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
__result__ = {"status": "ok"}
""")
    
    # --- Watch case ---
    print("[2/9] Modeling watch case...")
    run_python("""
import bpy

# Case body: short cylinder
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.5, depth=0.12,
    location=(0, 0, 0.06),
    vertices=64
)
case = bpy.context.active_object
case.name = "Watch_Case"
bpy.ops.object.shade_smooth()

bev = case.modifiers.new("Bevel", 'BEVEL')
bev.width = 0.015
bev.segments = 4

sub = case.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 3

__result__ = {"status": "ok", "object": "Watch_Case"}
""")
    
    # --- Bezel ---
    print("[3/9] Modeling bezel...")
    run_python("""
import bpy

# Bezel: torus sitting on top edge of case
bpy.ops.mesh.primitive_torus_add(
    major_radius=0.48, minor_radius=0.025,
    major_segments=64, minor_segments=16,
    location=(0, 0, 0.12)
)
bezel = bpy.context.active_object
bezel.name = "Watch_Bezel"
bpy.ops.object.shade_smooth()

__result__ = {"status": "ok", "object": "Watch_Bezel"}
""")
    
    # --- Dial / face ---
    print("[4/9] Modeling watch dial...")
    run_python("""
import bpy

# Dial: thin disc inside case
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.44, depth=0.005,
    location=(0, 0, 0.115),
    vertices=64
)
dial = bpy.context.active_object
dial.name = "Watch_Dial"
bpy.ops.object.shade_smooth()

# Hour markers: 12 small cylinders around the dial
import math
for i in range(12):
    angle = math.radians(i * 30)
    x = 0.38 * math.cos(angle)
    y = 0.38 * math.sin(angle)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.012, depth=0.003,
        location=(x, y, 0.118),
        vertices=8
    )
    marker = bpy.context.active_object
    marker.name = f"Hour_Marker_{i+1}"
    bpy.ops.object.shade_smooth()

# Hour hand
bpy.ops.mesh.primitive_cube_add(size=0.01, location=(0, 0.18, 0.12))
hand_h = bpy.context.active_object
hand_h.name = "Hand_Hour"
hand_h.scale = (0.3, 12.0, 0.5)
bpy.ops.object.transform_apply(scale=True)
hand_h.rotation_euler = (0, 0, 0.5)

# Minute hand
bpy.ops.mesh.primitive_cube_add(size=0.01, location=(0, 0.22, 0.122))
hand_m = bpy.context.active_object
hand_m.name = "Hand_Minute"
hand_m.scale = (0.2, 16.0, 0.4)
bpy.ops.object.transform_apply(scale=True)
hand_m.rotation_euler = (0, 0, -0.8)

__result__ = {"status": "ok"}
""")
    
    # --- Crystal (glass dome) ---
    print("[5/9] Modeling glass crystal...")
    run_python("""
import bpy

# Crystal: flattened sphere (convex glass cover)
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.46, segments=64, ring_count=32,
    location=(0, 0, 0.12)
)
crystal = bpy.context.active_object
crystal.name = "Watch_Crystal"
crystal.scale = (1.0, 1.0, 0.12)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()

__result__ = {"status": "ok", "object": "Watch_Crystal"}
""")
    
    # --- Crown (winding knob) ---
    print("[6/9] Modeling crown...")
    run_python("""
import bpy

bpy.ops.mesh.primitive_cylinder_add(
    radius=0.04, depth=0.06,
    location=(0.54, 0, 0.06),
    vertices=24
)
crown = bpy.context.active_object
crown.name = "Watch_Crown"
crown.rotation_euler = (0, 1.5708, 0)  # point outward
bpy.ops.object.shade_smooth()

crown.modifiers.new("Bevel", 'BEVEL').width = 0.005
crown.modifiers["Bevel"].segments = 3

__result__ = {"status": "ok", "object": "Watch_Crown"}
""")
    
    # --- Band links ---
    print("[7/9] Modeling band links...")
    run_python("""
import bpy

# Create band links extending from case
for i in range(5):
    offset = (i + 1) * 0.13
    for side in [1, -1]:
        bpy.ops.mesh.primitive_cube_add(
            size=0.1,
            location=(0, side * (0.52 + offset), 0.04)
        )
        link = bpy.context.active_object
        link.name = f"Band_Link_{i}_{('T' if side > 0 else 'B')}"
        link.scale = (3.8, 0.9, 0.6)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        link.modifiers.new("Bevel", 'BEVEL').width = 0.008
        link.modifiers["Bevel"].segments = 2

__result__ = {"status": "ok", "links": 10}
""")
    
    # --- Materials ---
    print("[8/9] Applying materials...")
    
    # Gold case + crown + band links
    apply_material("Watch_Case", "gold", "Case_Gold")
    run_python("""
import bpy
mat = bpy.data.materials.get("Case_Gold")
for obj in bpy.data.objects:
    if obj.name.startswith("Band_Link_") or obj.name == "Watch_Crown":
        if obj.data and hasattr(obj.data, 'materials'):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
    if obj.name.startswith("Hand_") or obj.name.startswith("Hour_Marker"):
        if obj.data and hasattr(obj.data, 'materials'):
            obj.data.materials.append(mat)
__result__ = {"status": "ok"}
""")
    
    # Chrome bezel
    apply_material("Watch_Bezel", "polished_chrome", "Bezel_Chrome")
    
    # Glass crystal
    run_python("""
import bpy
obj = bpy.data.objects.get("Watch_Crystal")
mat = bpy.data.materials.new("Crystal_Glass")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.97, 0.98, 1.0, 1.0)
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.01
bsdf.inputs['Transmission Weight'].default_value = 0.98
bsdf.inputs['IOR'].default_value = 1.77  # sapphire crystal
bsdf.inputs['Coat Weight'].default_value = 0.5
bsdf.inputs['Coat Roughness'].default_value = 0.005
obj.data.materials.append(mat)
__result__ = {"status": "ok", "material": "Crystal_Glass"}
""")
    
    # Dark dial
    run_python("""
import bpy
obj = bpy.data.objects.get("Watch_Dial")
mat = bpy.data.materials.new("Dial_Dark")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.02, 0.03, 0.05, 1.0)
bsdf.inputs['Metallic'].default_value = 0.2
bsdf.inputs['Roughness'].default_value = 0.15
obj.data.materials.append(mat)
__result__ = {"status": "ok"}
""")
    
    # --- Group and set up scene ---
    print("[9/9] Setting up full commercial sequence...\n")
    run_python("""
import bpy
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
parent = bpy.context.active_object
parent.name = "Luxury_Watch"

for obj in bpy.data.objects:
    if obj.name != "Luxury_Watch" and obj.type == 'MESH':
        obj.parent = parent

__result__ = {"status": "ok", "parent": "Luxury_Watch"}
""")
    
    # Use jewelry lighting
    setup_lighting("jewelry", shadow_catcher=True)
    
    # Build the multi-shot commercial using the sequence builder
    # We import and use it here directly
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
    from product_commercial_sequence import build_commercial
    
    result = build_commercial(
        object_name="Luxury_Watch",
        preset_name="luxury_jewelry",
        lighting_rig="jewelry",
        quality="premium",
        resolution="4k",
        output_dir="/tmp/luxury_watch_commercial",
    )
    
    print("\n═══ DEMO 04 COMPLETE ═══")
    print("  Product: Luxury watch")
    print("  Materials: Gold case + chrome bezel + sapphire crystal + dark dial")
    print("  Lighting: Jewelry sparkle rig")
    print(f"  Commercial: {len(result.get('shots', []))} shots, {result.get('total_duration_sec', 0)}s")
    print("  Render: Cycles premium @ 4K")
    print("  Output: /tmp/luxury_watch_commercial/")

if __name__ == "__main__":
    build_watch()
