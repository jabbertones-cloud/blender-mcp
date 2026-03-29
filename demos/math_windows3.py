"""Math-based window grid v3 — Object X+Z grid, FLOOR-based per-cell noise.
Proven approach for vertical building faces in cityscapes.
"""
import bpy, math, random
random.seed(42)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

# Dark twilight sky
world = bpy.data.worlds["World"]
world.use_nodes = True
wnodes = world.node_tree.nodes
wlinks = world.node_tree.links
wnodes.clear()

coord_w = wnodes.new("ShaderNodeTexCoord")
sep_w = wnodes.new("ShaderNodeSeparateXYZ")
wlinks.new(coord_w.outputs["Generated"], sep_w.inputs["Vector"])

ramp_w = wnodes.new("ShaderNodeValToRGB")
cr = ramp_w.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (0.15, 0.06, 0.02, 1)  # warm horizon
e1 = cr.elements.new(0.06)
e1.color = (0.1, 0.04, 0.05, 1)
e2 = cr.elements.new(0.2)
e2.color = (0.03, 0.02, 0.08, 1)
cr.elements[1].position = 1.0
cr.elements[1].color = (0.01, 0.015, 0.04, 1)  # dark zenith
wlinks.new(sep_w.outputs["Z"], ramp_w.inputs["Fac"])

bg_w = wnodes.new("ShaderNodeBackground")
bg_w.inputs["Strength"].default_value = 0.8
wlinks.new(ramp_w.outputs["Color"], bg_w.inputs["Color"])
out_w = wnodes.new("ShaderNodeOutputWorld")
wlinks.new(bg_w.outputs["Background"], out_w.inputs["Surface"])

# Subtle sun
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 0.5
sun.data.color = (1.0, 0.55, 0.25)
sun.rotation_euler = (math.radians(80), 0, math.radians(-30))


def make_window_material(name, win_per_unit=1.5, frame_pct=0.15,
                         wall_color=(0.02, 0.025, 0.04, 1),
                         emit_color=(1.0, 0.9, 0.6, 1), emit_str=12.0,
                         lit_pct=0.5):
    """Window grid: Object coords, X+Z grid, FLOOR-based per-cell noise.

    win_per_unit: window cells per world unit
    frame_pct: fraction of cell that is frame (dark border)
    lit_pct: fraction of windows that are lit
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()

    tc = nd.new("ShaderNodeTexCoord")
    sep = nd.new("ShaderNodeSeparateXYZ")
    lk.new(tc.outputs["Object"], sep.inputs["Vector"])

    # === X axis: columns ===
    x_sc = nd.new("ShaderNodeMath"); x_sc.operation = "MULTIPLY"
    lk.new(sep.outputs["X"], x_sc.inputs[0])
    x_sc.inputs[1].default_value = win_per_unit

    x_frac = nd.new("ShaderNodeMath"); x_frac.operation = "FRACT"
    lk.new(x_sc.outputs["Value"], x_frac.inputs[0])

    x_gt = nd.new("ShaderNodeMath"); x_gt.operation = "GREATER_THAN"
    lk.new(x_frac.outputs["Value"], x_gt.inputs[0])
    x_gt.inputs[1].default_value = frame_pct

    x_lt = nd.new("ShaderNodeMath"); x_lt.operation = "LESS_THAN"
    lk.new(x_frac.outputs["Value"], x_lt.inputs[0])
    x_lt.inputs[1].default_value = 1.0 - frame_pct

    x_win = nd.new("ShaderNodeMath"); x_win.operation = "MULTIPLY"
    lk.new(x_gt.outputs["Value"], x_win.inputs[0])
    lk.new(x_lt.outputs["Value"], x_win.inputs[1])

    # === Z axis: rows (taller windows → lower Z scale) ===
    z_sc = nd.new("ShaderNodeMath"); z_sc.operation = "MULTIPLY"
    lk.new(sep.outputs["Z"], z_sc.inputs[0])
    z_sc.inputs[1].default_value = win_per_unit * 0.7

    z_frac = nd.new("ShaderNodeMath"); z_frac.operation = "FRACT"
    lk.new(z_sc.outputs["Value"], z_frac.inputs[0])

    z_gt = nd.new("ShaderNodeMath"); z_gt.operation = "GREATER_THAN"
    lk.new(z_frac.outputs["Value"], z_gt.inputs[0])
    z_gt.inputs[1].default_value = frame_pct

    z_lt = nd.new("ShaderNodeMath"); z_lt.operation = "LESS_THAN"
    lk.new(z_frac.outputs["Value"], z_lt.inputs[0])
    z_lt.inputs[1].default_value = 1.0 - frame_pct

    z_win = nd.new("ShaderNodeMath"); z_win.operation = "MULTIPLY"
    lk.new(z_gt.outputs["Value"], z_win.inputs[0])
    lk.new(z_lt.outputs["Value"], z_win.inputs[1])

    # Window mask = X grid AND Z grid
    win_mask = nd.new("ShaderNodeMath"); win_mask.operation = "MULTIPLY"
    lk.new(x_win.outputs["Value"], win_mask.inputs[0])
    lk.new(z_win.outputs["Value"], win_mask.inputs[1])

    # === PER-CELL NOISE using FLOOR of grid coords ===
    # Floor gives each cell a unique integer → feed to noise for blocky variation
    x_floor = nd.new("ShaderNodeMath"); x_floor.operation = "FLOOR"
    lk.new(x_sc.outputs["Value"], x_floor.inputs[0])

    z_floor = nd.new("ShaderNodeMath"); z_floor.operation = "FLOOR"
    lk.new(z_sc.outputs["Value"], z_floor.inputs[0])

    # Combine back to vector for noise input
    combine = nd.new("ShaderNodeCombineXYZ")
    lk.new(x_floor.outputs["Value"], combine.inputs["X"])
    lk.new(z_floor.outputs["Value"], combine.inputs["Y"])
    combine.inputs["Z"].default_value = 0.0

    # Noise on cell indices → per-cell random value
    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.0  # Scale=1 because input is already integer-stepped
    noise.inputs["Detail"].default_value = 0.0
    noise.inputs["Roughness"].default_value = 1.0
    lk.new(combine.outputs["Vector"], noise.inputs["Vector"])

    # Threshold: lit or not
    lit_thresh = nd.new("ShaderNodeMath"); lit_thresh.operation = "GREATER_THAN"
    lk.new(noise.outputs["Fac"], lit_thresh.inputs[0])
    lit_thresh.inputs[1].default_value = 1.0 - lit_pct

    # Final mask: window shape AND lit
    final_mask = nd.new("ShaderNodeMath"); final_mask.operation = "MULTIPLY"
    lk.new(win_mask.outputs["Value"], final_mask.inputs[0])
    lk.new(lit_thresh.outputs["Value"], final_mask.inputs[1])

    # === SHADERS ===
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = wall_color
    wall.inputs["Roughness"].default_value = 0.85

    win = nd.new("ShaderNodeBsdfPrincipled")
    win.inputs["Base Color"].default_value = emit_color
    win.inputs["Emission Color"].default_value = emit_color
    win.inputs["Emission Strength"].default_value = emit_str
    win.inputs["Roughness"].default_value = 0.05

    mix = nd.new("ShaderNodeMixShader")
    lk.new(final_mask.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["BSDF"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


# 3 material variants
mat_glass = make_window_material("Glass", win_per_unit=1.5, frame_pct=0.12,
    wall_color=(0.02, 0.03, 0.05, 1), emit_color=(0.95, 0.88, 0.6, 1),
    emit_str=12.0, lit_pct=0.55)
mat_concrete = make_window_material("Concrete", win_per_unit=1.2, frame_pct=0.18,
    wall_color=(0.06, 0.05, 0.04, 1), emit_color=(1.0, 0.92, 0.7, 1),
    emit_str=10.0, lit_pct=0.4)
mat_warm = make_window_material("Warm", win_per_unit=1.8, frame_pct=0.1,
    wall_color=(0.08, 0.04, 0.03, 1), emit_color=(1.0, 0.8, 0.4, 1),
    emit_str=14.0, lit_pct=0.6)
variants = [mat_glass, mat_concrete, mat_warm]

# Build several buildings
buildings = [
    (-16, 10, 22, 4, 4),
    (-8,  8,  32, 3.5, 3.5),
    (-2,  12, 18, 5, 5),
    (6,   9,  28, 3, 3),
    (14,  11, 24, 4.5, 4.5),
    (-12, 16, 35, 3, 3),
    (2,   18, 40, 4, 4),
    (10,  15, 20, 5, 5),
]

for i, (x, y, h, w, d) in enumerate(buildings):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h/2))
    b = bpy.context.active_object
    b.name = f"Bldg_{i}"
    b.scale = (w/2, d/2, h/2)
    bpy.ops.object.transform_apply(scale=True)
    b.data.materials.append(variants[i % 3])

# Water plane
bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
water = bpy.context.active_object
water.name = "Water"
wm = bpy.data.materials.new("Water")
wm.use_nodes = True
wb = wm.node_tree.nodes.get("Principled BSDF")
wb.inputs["Base Color"].default_value = (0.01, 0.03, 0.08, 1)
wb.inputs["Roughness"].default_value = 0.05
water.data.materials.append(wm)

# Camera
bpy.ops.object.camera_add(location=(0, -3, 8))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(82), 0, 0)
cam.data.lens = 30

scene.render.filepath = "/tmp/math_windows3.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/math_windows3.png")
