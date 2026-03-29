#!/usr/bin/env python3
"""
DEMO 02: Cinematic Sneaker Animation (Nike-style)
===================================================
Recreates the sneaker product ad tutorial:
- Models a stylized sneaker from primitives (sole + upper + laces)
- Rubber matte sole, fabric upper, glossy plastic accents
- Hero reveal camera: dolly-in + zoom + rise
- Electronics/product studio lighting
- Motion blur for dynamic feel

Demonstrates: hero_reveal camera, multiple materials per product,
             blender_fcurve_edit for easing, motion blur config
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from product_animation_recipes import send, run_python, apply_material, setup_lighting, \
    setup_hero_reveal_camera, configure_render, setup_compositor_product

def build_sneaker():
    print("═══ DEMO 02: Cinematic Sneaker ═══\n")
    
    # --- Clear scene ---
    print("[1/7] Clearing scene...")
    run_python("""
import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
__result__ = {"status": "ok"}
""")
    
    # --- Model sole ---
    print("[2/7] Modeling shoe sole...")
    run_python("""
import bpy

# Sole: stretched cube with bevel
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0.12))
sole = bpy.context.active_object
sole.name = "Shoe_Sole"
sole.scale = (0.45, 1.2, 0.12)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()

# Bevel for rounded edges
bev = sole.modifiers.new("Bevel", 'BEVEL')
bev.width = 0.03
bev.segments = 4

# Subdivision
sub = sole.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 2

__result__ = {"status": "ok", "object": "Shoe_Sole"}
""")
    
    # --- Model upper ---
    print("[3/7] Modeling shoe upper...")
    run_python("""
import bpy

# Upper: rounded box shape
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.05, 0.42))
upper = bpy.context.active_object
upper.name = "Shoe_Upper"
upper.scale = (0.38, 1.1, 0.3)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()

# Bevel for soft shoe shape
bev = upper.modifiers.new("Bevel", 'BEVEL')
bev.width = 0.08
bev.segments = 5

sub = upper.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 3

__result__ = {"status": "ok", "object": "Shoe_Upper"}
""")
    
    # --- Model tongue ---
    print("[4/7] Modeling tongue + swoosh accent...")
    run_python("""
import bpy

# Tongue: thin stretched cube poking up from upper
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0.35, 0.65))
tongue = bpy.context.active_object
tongue.name = "Shoe_Tongue"
tongue.scale = (0.25, 0.3, 0.15)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
tongue.modifiers.new("Bevel", 'BEVEL').width = 0.04
tongue.modifiers["Bevel"].segments = 3
tongue.modifiers.new("Subsurf", 'SUBSURF').levels = 2

# Swoosh accent: thin curved plane
bpy.ops.mesh.primitive_plane_add(size=0.6, location=(0.39, -0.1, 0.38))
swoosh = bpy.context.active_object
swoosh.name = "Swoosh_Accent"
swoosh.scale = (0.05, 0.8, 0.3)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()

__result__ = {"status": "ok"}
""")
    
    # --- Apply materials ---
    print("[5/7] Applying materials...")
    
    # Rubber sole
    apply_material("Shoe_Sole", "rubber_matte", "Sole_Rubber")
    
    # Fabric upper (custom color: dark navy)
    run_python("""
import bpy
obj = bpy.data.objects.get("Shoe_Upper")
mat = bpy.data.materials.new("Upper_Fabric")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.05, 0.08, 0.18, 1.0)
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.75
bsdf.inputs['Subsurface Weight'].default_value = 0.05
obj.data.materials.append(mat)
__result__ = {"status": "ok"}
""")
    
    # Tongue: lighter fabric
    run_python("""
import bpy
obj = bpy.data.objects.get("Shoe_Tongue")
mat = bpy.data.materials.new("Tongue_Fabric")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.15, 0.18, 0.28, 1.0)
bsdf.inputs['Roughness'].default_value = 0.7
obj.data.materials.append(mat)
__result__ = {"status": "ok"}
""")
    
    # Swoosh: glossy white plastic
    run_python("""
import bpy
obj = bpy.data.objects.get("Swoosh_Accent")
mat = bpy.data.materials.new("Swoosh_Gloss")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
bsdf.inputs['Roughness'].default_value = 0.12
bsdf.inputs['Coat Weight'].default_value = 0.3
obj.data.materials.append(mat)
__result__ = {"status": "ok"}
""")
    
    # --- Group & scene setup ---
    print("[6/7] Grouping and setting up scene...")
    run_python("""
import bpy
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
parent = bpy.context.active_object
parent.name = "Sneaker"

for name in ["Shoe_Sole", "Shoe_Upper", "Shoe_Tongue", "Swoosh_Accent"]:
    obj = bpy.data.objects.get(name)
    if obj:
        obj.parent = parent

# Tilt the shoe for dynamic angle
parent.rotation_euler = (0.15, 0, 0.1)

__result__ = {"status": "ok", "parent": "Sneaker"}
""")
    
    # --- Lighting + Camera + Render ---
    print("[7/7] Setting up lighting, camera, render...\n")
    
    setup_lighting("electronics", shadow_catcher=True)
    
    # Hero reveal: dramatic dolly-in
    setup_hero_reveal_camera(
        target_object="Sneaker",
        frames=180,
        start_distance=7.0,
        end_distance=3.0,
        start_height=0.3,
        end_height=1.0,
        start_focal=35.0,
        end_focal=65.0,
        f_stop=2.8,
        fps=30,
    )
    
    configure_render(
        quality="balanced",
        resolution="1080p",
        transparent_bg=True,
        output_path="/tmp/sneaker_hero/frame_####",
    )
    
    # Enable motion blur for dynamic feel
    run_python("""
import bpy
bpy.context.scene.render.use_motion_blur = True
bpy.context.scene.render.motion_blur_shutter = 0.5
__result__ = {"status": "ok", "motion_blur": True}
""")
    
    setup_compositor_product(bloom=False, vignette=True)
    
    print("═══ DEMO 02 COMPLETE ═══")
    print("  Product: Athletic sneaker")
    print("  Materials: Rubber sole + navy fabric + white gloss swoosh")
    print("  Lighting: Electronics product rig")
    print("  Camera: 180-frame hero reveal (35→65mm), f/2.8")
    print("  Render: Cycles balanced @ 1080p + motion blur")
    print("  Output: /tmp/sneaker_hero/")

if __name__ == "__main__":
    build_sneaker()
