"""Math-based window grid using Object XZ coordinates.
Works on ALL vertical faces of buildings regardless of orientation.
Object X = horizontal window columns, Object Z = vertical window rows.
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

world = bpy.data.worlds["World"]
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.01, 0.015, 0.04, 1)
bg.inputs["Strength"].default_value = 1.0

bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 0.3
sun.data.color = (1.0, 0.6, 0.3)
sun.rotation_euler = (math.radians(75), 0, math.radians(-30))


def make_window_material(name, window_scale=2.0, frame_pct=0.15,
                         wall_color=(0.02, 0.025, 0.04, 1),
                         emit_color=(1.0, 0.9, 0.6, 1), emit_str=12.0,
                         lit_pct=0.5):
    """Window grid using Object coords with X and Z axes.

    window_scale: windows per world unit (e.g. 2.0 = 2 windows per meter)
    frame_pct: fraction of each cell that is frame (0.15 = 15% frame border)
    lit_pct: fraction of windows that are lit (noise-driven)
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()

    # Object coordinates (after scale apply, these are world-scale)
    tc = nd.new("ShaderNodeTexCoord")
    sep = nd.new("ShaderNodeSeparateXYZ")
    lk.new(tc.outputs["Object"], sep.inputs["Vector"])

    # === HORIZONTAL GRID (Object X) ===
    # Scale X by window density
    x_scale = nd.new("ShaderNodeMath")
    x_scale.operation = "MULTIPLY"
    lk.new(sep.outputs["X"], x_scale.inputs[0])
    x_scale.inputs[1].default_value = window_scale

    x_frac = nd.new("ShaderNodeMath")
    x_frac.operation = "FRACT"
    lk.new(x_scale.outputs["Value"], x_frac.inputs[0])

    x_gt = nd.new("ShaderNodeMath")
    x_gt.operation = "GREATER_THAN"
    lk.new(x_frac.outputs["Value"], x_gt.inputs[0])
    x_gt.inputs[1].default_value = frame_pct

    x_lt = nd.new("ShaderNodeMath")
    x_lt.operation = "LESS_THAN"
    lk.new(x_frac.outputs["Value"], x_lt.inputs[0])
    x_lt.inputs[1].default_value = 1.0 - frame_pct

    x_win = nd.new("ShaderNodeMath")
    x_win.operation = "MULTIPLY"
    lk.new(x_gt.outputs["Value"], x_win.inputs[0])
    lk.new(x_lt.outputs["Value"], x_win.inputs[1])

    # === ALSO DO Y AXIS (for side faces) ===
    y_scale = nd.new("ShaderNodeMath")
    y_scale.operation = "MULTIPLY"
    lk.new(sep.outputs["Y"], y_scale.inputs[0])
    y_scale.inputs[1].default_value = window_scale

    y_frac = nd.new("ShaderNodeMath")
    y_frac.operation = "FRACT"
    lk.new(y_scale.outputs["Value"], y_frac.inputs[0])

    y_gt = nd.new("ShaderNodeMath")
    y_gt.operation = "GREATER_THAN"
    lk.new(y_frac.outputs["Value"], y_gt.inputs[0])
    y_gt.inputs[1].default_value = frame_pct

    y_lt = nd.new("ShaderNodeMath")
    y_lt.operation = "LESS_THAN"
    lk.new(y_frac.outputs["Value"], y_lt.inputs[0])
    y_lt.inputs[1].default_value = 1.0 - frame_pct

    y_win = nd.new("ShaderNodeMath")
    y_win.operation = "MULTIPLY"
    lk.new(y_gt.outputs["Value"], y_win.inputs[0])
    lk.new(y_lt.outputs["Value"], y_win.inputs[1])

    # Combine X and Y: take maximum (window on front OR side face)
    xy_win = nd.new("ShaderNodeMath")
    xy_win.operation = "MAXIMUM"
    lk.new(x_win.outputs["Value"], xy_win.inputs[0])
    lk.new(y_win.outputs["Value"], xy_win.inputs[1])

    # === VERTICAL GRID (Object Z) ===
    z_scale = nd.new("ShaderNodeMath")
    z_scale.operation = "MULTIPLY"
    lk.new(sep.outputs["Z"], z_scale.inputs[0])
    z_scale.inputs[1].default_value = window_scale * 0.7  # windows taller than wide

    z_frac = nd.new("ShaderNodeMath")
    z_frac.operation = "FRACT"
    lk.new(z_scale.outputs["Value"], z_frac.inputs[0])

    z_gt = nd.new("ShaderNodeMath")
    z_gt.operation = "GREATER_THAN"
    lk.new(z_frac.outputs["Value"], z_gt.inputs[0])
    z_gt.inputs[1].default_value = frame_pct

    z_lt = nd.new("ShaderNodeMath")
    z_lt.operation = "LESS_THAN"
    lk.new(z_frac.outputs["Value"], z_lt.inputs[0])
    z_lt.inputs[1].default_value = 1.0 - frame_pct

    z_win = nd.new("ShaderNodeMath")
    z_win.operation = "MULTIPLY"
    lk.new(z_gt.outputs["Value"], z_win.inputs[0])
    lk.new(z_lt.outputs["Value"], z_win.inputs[1])

    # Final window mask: horizontal AND vertical
    window_mask = nd.new("ShaderNodeMath")
    window_mask.operation = "MULTIPLY"
    lk.new(xy_win.outputs["Value"], window_mask.inputs[0])
    lk.new(z_win.outputs["Value"], window_mask.inputs[1])

    # === NOISE: random lit/unlit windows ===
    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = window_scale * 3.0
    noise.inputs["Detail"].default_value = 0.0
    noise.inputs["Roughness"].default_value = 1.0
    lk.new(tc.outputs["Object"], noise.inputs["Vector"])

    noise_thresh = nd.new("ShaderNodeMath")
    noise_thresh.operation = "GREATER_THAN"
    lk.new(noise.outputs["Fac"], noise_thresh.inputs[0])
    noise_thresh.inputs[1].default_value = 1.0 - lit_pct

    # Window mask * noise = only some windows lit
    lit_mask = nd.new("ShaderNodeMath")
    lit_mask.operation = "MULTIPLY"
    lk.new(window_mask.outputs["Value"], lit_mask.inputs[0])
    lk.new(noise_thresh.outputs["Value"], lit_mask.inputs[1])

    # Shaders
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = wall_color
    wall.inputs["Roughness"].default_value = 0.85

    win = nd.new("ShaderNodeBsdfPrincipled")
    win.inputs["Base Color"].default_value = emit_color
    win.inputs["Emission Color"].default_value = emit_color
    win.inputs["Emission Strength"].default_value = emit_str
    win.inputs["Roughness"].default_value = 0.05

    mix = nd.new("ShaderNodeMixShader")
    lk.new(lit_mask.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["BSDF"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


# Create 3 material variants
mat_glass = make_window_material("Glass", window_scale=1.5, frame_pct=0.12,
    wall_color=(0.02, 0.03, 0.05, 1), emit_color=(0.95, 0.88, 0.6, 1),
    emit_str=12.0, lit_pct=0.55)
mat_concrete = make_window_material("Concrete", window_scale=1.2, frame_pct=0.18,
    wall_color=(0.06, 0.05, 0.04, 1), emit_color=(1.0, 0.92, 0.7, 1),
    emit_str=10.0, lit_pct=0.4)
mat_warm = make_window_material("Warm", window_scale=1.8, frame_pct=0.1,
    wall_color=(0.08, 0.04, 0.03, 1), emit_color=(1.0, 0.8, 0.4, 1),
    emit_str=14.0, lit_pct=0.6)
variants = [mat_glass, mat_concrete, mat_warm]

# Build 5 test buildings at various positions
buildings = [
    (-12, 8, 20, 4, 4),   # x, y, height, width, depth
    (-4,  6, 30, 3, 3),
    (4,   7, 15, 5, 5),
    (12,  8, 25, 3.5, 3.5),
    (0,   12, 35, 4, 4),   # one farther back
]

for i, (x, y, h, w, d) in enumerate(buildings):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, h/2))
    b = bpy.context.active_object
    b.name = f"Bldg_{i}"
    b.scale = (w/2, d/2, h/2)
    bpy.ops.object.transform_apply(scale=True)
    b.data.materials.append(variants[i % 3])

# Camera
bpy.ops.object.camera_add(location=(0, -3, 8))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(80), 0, 0)
cam.data.lens = 28

scene.render.filepath = "/tmp/math_windows2.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/math_windows2.png")
