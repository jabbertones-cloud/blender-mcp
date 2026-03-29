#!/usr/bin/env python3
"""
DEMO 01: Luxury Perfume Bottle Animation
==========================================
Recreates the classic Blender product animation tutorial:
- Models a perfume bottle from primitives (body + cap + neck)
- Applies glass shader with colored liquid inside
- Gold metallic cap
- HDRI-style gradient environment
- Professional cosmetics lighting rig
- Slow turntable animation with shallow DOF
- Cycles render with bloom compositor

Demonstrates: blender_product_material, blender_product_lighting,
             blender_product_camera, blender_product_render_setup,
             blender_product_animation (one-call recipe)

Run: python3 demos/demo_01_perfume_bottle.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from product_animation_recipes import send, run_python, apply_material, setup_lighting, \
    setup_turntable_camera, configure_render, setup_compositor_product, setup_gradient_background

def build_perfume_bottle():
    """Model a perfume bottle from Blender primitives."""
    print("═══ DEMO 01: Luxury Perfume Bottle ═══\n")
    
    # --- Step 1: Clear scene ---
    print("[1/8] Clearing scene...")
    run_python("""
import bpy
# Delete default objects
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
__result__ = {"status": "ok", "cleared": True}
""")
    
    # --- Step 2: Model bottle body ---
    print("[2/8] Modeling bottle body...")
    run_python("""
import bpy

# Bottle body: cylinder with subdivision
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.4, depth=1.8, 
    location=(0, 0, 0.9),
    vertices=64
)
body = bpy.context.active_object
body.name = "Bottle_Body"

# Smooth shading
bpy.ops.object.shade_smooth()

# Subdivision surface for smooth glass look
sub = body.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 3

# Slight scale on X for elegant rectangular profile
body.scale = (0.7, 0.5, 1.0)
bpy.ops.object.transform_apply(scale=True)

__result__ = {"status": "ok", "object": "Bottle_Body"}
""")
    
    # --- Step 3: Model bottle neck ---
    print("[3/8] Modeling bottle neck...")
    run_python("""
import bpy

# Neck: tapered cylinder
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.15, depth=0.4,
    location=(0, 0, 2.0),
    vertices=32
)
neck = bpy.context.active_object
neck.name = "Bottle_Neck"
bpy.ops.object.shade_smooth()

sub = neck.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 3

__result__ = {"status": "ok", "object": "Bottle_Neck"}
""")
    
    # --- Step 4: Model cap ---
    print("[4/8] Modeling cap...")
    run_python("""
import bpy

# Cap: wider cylinder on top
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.22, depth=0.35,
    location=(0, 0, 2.38),
    vertices=32
)
cap = bpy.context.active_object
cap.name = "Bottle_Cap"
bpy.ops.object.shade_smooth()

sub = cap.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 3

# Bevel for luxury edge
bev = cap.modifiers.new("Bevel", 'BEVEL')
bev.width = 0.02
bev.segments = 3

__result__ = {"status": "ok", "object": "Bottle_Cap"}
""")
    
    # --- Step 5: Model liquid inside ---
    print("[5/8] Modeling liquid interior...")
    run_python("""
import bpy

# Liquid: slightly smaller cylinder inside body
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.35, depth=1.4,
    location=(0, 0, 0.75),
    vertices=64
)
liquid = bpy.context.active_object
liquid.name = "Liquid"
bpy.ops.object.shade_smooth()
liquid.scale = (0.65, 0.45, 1.0)
bpy.ops.object.transform_apply(scale=True)

__result__ = {"status": "ok", "object": "Liquid"}
""")
    
    # --- Step 6: Apply materials ---
    print("[6/8] Applying materials...")
    
    # Glass body
    run_python("""
import bpy
obj = bpy.data.objects.get("Bottle_Body")
mat = bpy.data.materials.new("Perfume_Glass")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.95, 0.97, 1.0, 1.0)
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.02
bsdf.inputs['Transmission Weight'].default_value = 1.0
bsdf.inputs['IOR'].default_value = 1.52
bsdf.inputs['Coat Weight'].default_value = 0.3
bsdf.inputs['Coat Roughness'].default_value = 0.01
obj.data.materials.append(mat)
__result__ = {"status": "ok", "material": "Perfume_Glass"}
""")
    
    # Glass neck (same material)
    run_python("""
import bpy
obj = bpy.data.objects.get("Bottle_Neck")
mat = bpy.data.materials.get("Perfume_Glass")
obj.data.materials.append(mat)
__result__ = {"status": "ok"}
""")
    
    # Gold cap
    apply_material("Bottle_Cap", "cosmetics_gold_cap", "Gold_Cap")
    
    # Colored liquid (amber/pink tint)
    run_python("""
import bpy
obj = bpy.data.objects.get("Liquid")
mat = bpy.data.materials.new("Perfume_Liquid")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.95, 0.75, 0.6, 1.0)
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.0
bsdf.inputs['Transmission Weight'].default_value = 0.95
bsdf.inputs['IOR'].default_value = 1.36
bsdf.inputs['Subsurface Weight'].default_value = 0.3
bsdf.inputs['Subsurface Radius'].default_value = (1.0, 0.5, 0.3)
obj.data.materials.append(mat)
__result__ = {"status": "ok", "material": "Perfume_Liquid"}
""")
    
    # --- Step 7: Parent all to empty for turntable ---
    print("[7/8] Grouping objects...")
    run_python("""
import bpy

# Create parent empty
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
parent = bpy.context.active_object
parent.name = "Perfume_Bottle"

# Parent all parts
for name in ["Bottle_Body", "Bottle_Neck", "Bottle_Cap", "Liquid"]:
    obj = bpy.data.objects.get(name)
    if obj:
        obj.parent = parent

__result__ = {"status": "ok", "parent": "Perfume_Bottle", "children": 4}
""")
    
    # --- Step 8: Set up scene ---
    print("[8/8] Setting up scene (lighting + camera + render)...\n")
    
    # Gradient background (white-to-soft-pink cyclorama)
    setup_gradient_background(
        top_color=[0.85, 0.82, 0.88],
        bottom_color=[1.0, 0.98, 0.96],
        strength=1.2
    )
    
    # Cosmetics lighting rig
    setup_lighting("cosmetics", shadow_catcher=True)
    
    # Turntable camera: 240 frames, 65mm lens, shallow DOF
    setup_turntable_camera(
        target_object="Perfume_Bottle",
        frames=240,
        camera_distance=3.5,
        camera_height=1.4,
        focal_length=65.0,
        f_stop=2.0,
        use_dof=True,
        fps=24,
    )
    
    # Premium render settings
    configure_render(
        quality="balanced",
        resolution="1080p",
        transparent_bg=False,  # using gradient bg
        output_path="/tmp/perfume_bottle/frame_####",
    )
    
    # Compositor with bloom (glass highlights glow)
    setup_compositor_product(bloom=True, vignette=True)
    
    print("═══ DEMO 01 COMPLETE ═══")
    print("  Product: Luxury perfume bottle")
    print("  Materials: Glass body + gold cap + amber liquid")
    print("  Lighting: Cosmetics beauty rig")
    print("  Camera: 240-frame turntable, 65mm f/2.0")
    print("  Render: Cycles balanced @ 1080p")
    print("  Output: /tmp/perfume_bottle/")
    print("\n  To render: blender_render(type='animation')")

if __name__ == "__main__":
    build_perfume_bottle()
