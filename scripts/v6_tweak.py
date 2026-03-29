"""
v6 tweaks based on micro-render comparison:
1. Liquid absorption density 0.6 -> 0.3 (still too opaque)
2. Backlight energy 600 -> 900W (more glow-through)
3. Backlight size 3.0 -> 4.0 (broader coverage)
4. Glass absorption density 0.008 -> 0.003 (even clearer)
5. Key light 800 -> 700 (slight reduce to avoid washing out)
6. HDRI strength 1.8 -> 1.5 (less environmental wash)
7. Floor color slightly warmer
"""
import bpy

print("Applying v6 tweaks...")

# 1. Liquid absorption - reduce density further
liq_mat = bpy.data.materials.get("AmberLiquid")
if liq_mat:
    for node in liq_mat.node_tree.nodes:
        if node.type == "VOLUME_ABSORPTION":
            node.inputs["Density"].default_value = 0.3
            node.inputs["Color"].default_value = (1.0, 0.78, 0.42, 1.0)  # Even lighter
            print(f"  Liquid absorption: density=0.3, color lighter")

# 2. Glass absorption - reduce further  
glass_mat = bpy.data.materials.get("PerfumeGlass")
if glass_mat:
    for node in glass_mat.node_tree.nodes:
        if node.type == "VOLUME_ABSORPTION":
            node.inputs["Density"].default_value = 0.003
            print(f"  Glass absorption: density=0.003")

# 3. Backlight - boost for liquid glow
back = bpy.data.objects.get("BackLight")
if back:
    back.data.energy = 900
    back.data.size = 4.0
    print(f"  BackLight: energy=900, size=4.0")

# 4. Key light - slight reduce
key = bpy.data.objects.get("Key")
if key:
    key.data.energy = 700
    print(f"  Key: energy=700")

# 5. HDRI strength reduce
world = bpy.context.scene.world
if world and world.use_nodes:
    for node in world.node_tree.nodes:
        if node.type == "BACKGROUND":
            node.inputs["Strength"].default_value = 1.5
            print(f"  HDRI strength=1.5")

# 6. Floor - slightly warmer
floor_mat = bpy.data.materials.get("StudioFloor")
if floor_mat:
    for node in floor_mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            node.inputs["Base Color"].default_value = (0.93, 0.92, 0.90, 1.0)
            print(f"  Floor: slightly warmer")

# Save as v6b
bpy.ops.wm.save_as_mainfile(filepath="/tmp/perfume_v6b.blend")
print("Saved /tmp/perfume_v6b.blend")
