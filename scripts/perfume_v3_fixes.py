"""
Perfume Bottle v3 - Fixes applied to v2.blend
Run: blender -b /tmp/perfume_v2.blend -P perfume_v3_fixes.py
Then render: blender -b /tmp/perfume_v3.blend -o /tmp/perfume_v3_ -f 1 -- --cycles-device CPU
"""
import bpy
import math
import mathutils

print("=" * 50)
print("PERFUME v3 - Fix pass")
print("=" * 50)

# ===== FIX 1: Brighter lighting =====
print("[1] Brightening lighting...")
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        if obj.name == "Key":
            obj.data.energy = 400      # was 200
            obj.data.size = 2.0        # bigger, softer
        elif obj.name == "Fill":
            obj.data.energy = 120      # was 40
            obj.data.size = 5.0        # much bigger
        elif obj.name == "Rim":
            obj.data.energy = 500      # was 350
        elif obj.name == "BottomFill":
            obj.data.energy = 80       # was 30

# ===== FIX 2: Better DOF =====
print("[2] Fixing DOF (f/5.6 for sharper product)...")
cam = bpy.context.scene.camera
cam.data.dof.aperture_fstop = 5.6    # was 1.8

# ===== FIX 3: White cyclorama =====
print("[3] White cyclorama...")
cyc_mat = bpy.data.materials.get("CycMat")
if cyc_mat:
    bsdf = cyc_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5

# ===== FIX 4: Brighter world =====
print("[4] Brighter world background...")
world = bpy.context.scene.world
if world and world.use_nodes:
    for node in world.node_tree.nodes:
        if node.type == 'BACKGROUND':
            node.inputs["Strength"].default_value = 1.5  # was 0.8
        if node.type == 'VALTORGB':
            node.color_ramp.elements[0].color = (0.98, 0.97, 1.0, 1.0)  # near white
            node.color_ramp.elements[1].color = (0.92, 0.90, 0.95, 1.0)

# ===== FIX 5: More visible liquid =====
print("[5] Making liquid more visible (stronger color)...")
liq_mat = bpy.data.materials.get("AmberLiquid")
if liq_mat:
    bsdf = liq_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 0.55, 0.15, 1.0)  # deeper amber
    bsdf.inputs["Transmission Weight"].default_value = 0.7   # less transparent
    bsdf.inputs["Subsurface Weight"].default_value = 0.6     # more scatter
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.3, 0.05)
    bsdf.inputs["Subsurface Scale"].default_value = 0.8
    bsdf.inputs["Roughness"].default_value = 0.05

# ===== FIX 6: Glass — less coat so we see inside better =====
print("[6] Adjusting glass for better interior visibility...")
glass_mat = bpy.data.materials.get("PerfumeGlass")
if glass_mat:
    bsdf = glass_mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Coat Weight"].default_value = 0.3    # was 1.0

# ===== FIX 7: Increase render quality =====
print("[7] Render quality boost...")
s = bpy.context.scene
s.cycles.samples = 256            # was 128
s.render.resolution_percentage = 75  # was 50 (now 1440x810)

# ===== SAVE =====
print("[8] Saving v3...")
bpy.ops.wm.save_as_mainfile(filepath="/tmp/perfume_v3.blend")

print("\n" + "=" * 50)
print("V3 FIXES APPLIED")
print("  - Brighter lighting (2x key, 3x fill)")
print("  - DOF f/5.6 (was f/1.8)")
print("  - White cyclorama")
print("  - Brighter world")
print("  - Deeper amber liquid (more visible)")
print("  - Glass coat reduced for interior visibility")
print("  - 256 samples @ 75% resolution")
print("=" * 50)
