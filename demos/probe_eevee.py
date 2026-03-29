"""Probe Blender 5.1 EEVEE settings available."""
import bpy

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
eevee = scene.eevee

# List all eevee attributes
attrs = [a for a in dir(eevee) if not a.startswith('_')]
print("=== EEVEE attributes ===")
for a in sorted(attrs):
    try:
        val = getattr(eevee, a)
        if not callable(val):
            print(f"  {a} = {val}")
    except:
        print(f"  {a} = <error>")

# Check view_settings looks
print("\n=== View Transform Looks ===")
for item in bpy.types.ColorManagedViewSettings.bl_rna.properties['look'].enum_items:
    print(f"  '{item.identifier}' = '{item.name}'")

# Check render engines
print("\n=== Render Engines ===")
for item in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items:
    print(f"  '{item.identifier}'")
