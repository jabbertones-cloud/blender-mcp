#!/usr/bin/env python3
"""
DEMO 05: Energy Drink Can Animation (Monster/Red Bull style)
==============================================================
Recreates the soda/energy drink can tutorial:
- Models a standard drink can from cylinder + taper
- Metallic brushed aluminum body + glossy label band
- Condensation droplets (particle system)
- Dynamic hero reveal with pull-back
- Food/beverage product lighting
- Social media vertical format (1080x1920)

Demonstrates: particle_system, social_media_reel recipe,
             food_product lighting, vertical resolution,
             blender_product_animation one-call
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from product_animation_recipes import send, run_python, apply_material, setup_lighting, \
    setup_turntable_camera, setup_hero_reveal_camera, configure_render, \
    setup_compositor_product, setup_gradient_background

def build_energy_drink():
    print("═══ DEMO 05: Energy Drink Can ═══\n")
    
    print("[1/9] Clearing scene...")
    run_python("""
import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
__result__ = {"status": "ok"}
""")
    
    # --- Can body ---
    print("[2/9] Modeling can body...")
    run_python("""
import bpy

# Main cylinder
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.33, depth=1.5,
    location=(0, 0, 0.75),
    vertices=64
)
body = bpy.context.active_object
body.name = "Can_Body"
bpy.ops.object.shade_smooth()

# Subdivision for smooth metal look
sub = body.modifiers.new("Subsurf", 'SUBSURF')
sub.levels = 2
sub.render_levels = 3

__result__ = {"status": "ok", "object": "Can_Body"}
""")
    
    # --- Can top rim ---
    print("[3/9] Modeling can top + tab...")
    run_python("""
import bpy

# Top indent: slightly smaller cylinder
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.29, depth=0.04,
    location=(0, 0, 1.52),
    vertices=64
)
top = bpy.context.active_object
top.name = "Can_Top"
bpy.ops.object.shade_smooth()

# Rim ring
bpy.ops.mesh.primitive_torus_add(
    major_radius=0.31, minor_radius=0.015,
    major_segments=64, minor_segments=12,
    location=(0, 0, 1.5)
)
rim = bpy.context.active_object
rim.name = "Can_Rim"
bpy.ops.object.shade_smooth()

# Pull tab: small stretched oval
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.04, depth=0.005,
    location=(0.08, 0, 1.545),
    vertices=16
)
tab = bpy.context.active_object
tab.name = "Pull_Tab"
tab.scale = (1.0, 2.5, 1.0)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()

__result__ = {"status": "ok"}
""")
    
    # --- Can bottom ---
    print("[4/9] Modeling can bottom...")
    run_python("""
import bpy

# Bottom dome (concave)
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=0.32, segments=32, ring_count=16,
    location=(0, 0, 0.05)
)
bottom = bpy.context.active_object
bottom.name = "Can_Bottom"
bottom.scale = (1.0, 1.0, 0.15)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()

__result__ = {"status": "ok", "object": "Can_Bottom"}
""")
    
    # --- Label band ---
    print("[5/9] Modeling label band...")
    run_python("""
import bpy

# Label: thin cylinder wrapping the middle section
bpy.ops.mesh.primitive_cylinder_add(
    radius=0.335, depth=0.8,
    location=(0, 0, 0.75),
    vertices=64
)
label = bpy.context.active_object
label.name = "Label_Band"
bpy.ops.object.shade_smooth()

# Solidify to make it a thin shell
solid = label.modifiers.new("Solidify", 'SOLIDIFY')
solid.thickness = 0.003
solid.offset = 1.0  # expand outward

__result__ = {"status": "ok", "object": "Label_Band"}
""")
    
    # --- Materials ---
    print("[6/9] Applying materials...")
    
    # Brushed aluminum body + top + bottom
    apply_material("Can_Body", "brushed_aluminum", "Can_Metal")
    for name in ["Can_Top", "Can_Rim", "Pull_Tab", "Can_Bottom"]:
        run_python(f"""
import bpy
obj = bpy.data.objects.get("{name}")
mat = bpy.data.materials.get("Can_Metal")
if obj and mat and hasattr(obj.data, 'materials'):
    obj.data.materials.append(mat)
__result__ = {{"status": "ok"}}
""")
    
    # Label: glossy colored plastic (neon green for energy drink)
    run_python("""
import bpy
obj = bpy.data.objects.get("Label_Band")
mat = bpy.data.materials.new("Label_Neon")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs['Base Color'].default_value = (0.0, 0.85, 0.15, 1.0)
bsdf.inputs['Metallic'].default_value = 0.3
bsdf.inputs['Roughness'].default_value = 0.2
bsdf.inputs['Emission Color'].default_value = (0.0, 0.3, 0.05, 1.0)
bsdf.inputs['Emission Strength'].default_value = 0.15
bsdf.inputs['Coat Weight'].default_value = 0.4
bsdf.inputs['Coat Roughness'].default_value = 0.08
obj.data.materials.append(mat)
__result__ = {"status": "ok", "material": "Label_Neon"}
""")
    
    # --- Condensation droplets (particle system) ---
    print("[7/9] Adding condensation droplets (particles)...")
    run_python("""
import bpy

can = bpy.data.objects.get("Can_Body")
if can:
    # Add particle system for water droplets
    bpy.context.view_layer.objects.active = can
    bpy.ops.object.particle_system_add()
    ps = can.particle_systems[-1]
    ps.name = "Condensation"
    settings = ps.settings
    settings.name = "Droplet_Settings"
    
    # Particle config: small spheres scattered on surface
    settings.type = 'HAIR'
    settings.count = 500
    settings.hair_length = 0.008
    settings.use_advanced_hair = True
    
    # Render as small spheres
    settings.render_type = 'OBJECT'
    
    # Create tiny sphere for droplet instance
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.006, segments=8, ring_count=6, location=(10, 10, 10))
    droplet = bpy.context.active_object
    droplet.name = "Droplet_Instance"
    bpy.ops.object.shade_smooth()
    
    # Transparent droplet material
    mat = bpy.data.materials.new("Water_Droplet")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs['Base Color'].default_value = (0.9, 0.95, 1.0, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.02
    bsdf.inputs['Transmission Weight'].default_value = 0.95
    bsdf.inputs['IOR'].default_value = 1.33
    droplet.data.materials.append(mat)
    
    settings.instance_object = droplet
    
    # Hide droplet instance from render
    droplet.hide_render = True
    droplet.hide_viewport = True

__result__ = {"status": "ok", "particles": "condensation droplets added"}
""")
    
    # --- Group ---
    print("[8/9] Grouping objects...")
    run_python("""
import bpy
bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 0, 0))
parent = bpy.context.active_object
parent.name = "Energy_Drink"

for obj in bpy.data.objects:
    if obj.name != "Energy_Drink" and obj.name != "Droplet_Instance" and obj.type in ('MESH',):
        obj.parent = parent

# Slight tilt for dynamic angle
parent.rotation_euler = (0.08, 0, 0.05)

__result__ = {"status": "ok", "parent": "Energy_Drink"}
""")
    
    # --- Scene setup ---
    print("[9/9] Setting up scene (social media reel format)...\n")
    
    # Dark gradient background (moody energy drink vibe)
    setup_gradient_background(
        top_color=[0.0, 0.02, 0.0],
        bottom_color=[0.02, 0.08, 0.02],
        strength=0.5,
    )
    
    # Food/beverage lighting
    setup_lighting("food_product", shadow_catcher=True)
    
    # Hero reveal for social media reel (vertical)
    setup_hero_reveal_camera(
        target_object="Energy_Drink",
        frames=150,
        start_distance=6.0,
        end_distance=3.0,
        start_height=0.3,
        end_height=1.2,
        start_focal=35.0,
        end_focal=65.0,
        f_stop=2.8,
        fps=30,
    )
    
    # Vertical format for social media
    configure_render(
        quality="balanced",
        resolution="vertical",  # 1080x1920
        transparent_bg=False,
        output_path="/tmp/energy_drink_reel/frame_####",
    )
    
    setup_compositor_product(bloom=True, vignette=True)
    
    print("═══ DEMO 05 COMPLETE ═══")
    print("  Product: Energy drink can")
    print("  Materials: Brushed aluminum + neon green label (emissive)")
    print("  Effects: Condensation droplets (particle system)")
    print("  Lighting: Food product rig + dark gradient bg")
    print("  Camera: 150-frame hero reveal, 35→65mm f/2.8")
    print("  Format: Vertical 1080x1920 (TikTok/Reels)")
    print("  Output: /tmp/energy_drink_reel/")

if __name__ == "__main__":
    build_energy_drink()
