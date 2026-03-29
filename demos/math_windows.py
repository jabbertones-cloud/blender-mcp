"""Math-based window grid on vertical building faces.
Uses SeparateXYZ + Frac + Step to create a 2D grid pattern that works on ANY surface.
No Brick Texture (which is 3D volumetric and fails on certain face orientations).
"""
import bpy, math

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
bg.inputs["Color"].default_value = (0.02, 0.02, 0.05, 1)
bg.inputs["Strength"].default_value = 1.0

bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 0.3


def make_math_window_mat(name, rows=8, cols=5, frame_thickness=0.15,
                         wall_color=(0.02, 0.02, 0.04, 1),
                         emit_color=(1.0, 0.9, 0.6, 1), emit_str=15.0):
    """Window grid using UV coords + Math nodes.

    UV coords ensure the pattern works on every face independently.
    Multiply UV by rows/cols, then frac() to get 0-1 per cell,
    then threshold to create window frame vs glass.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()

    # UV Coordinates
    tc = nd.new("ShaderNodeTexCoord")

    # Separate into U and V
    sep = nd.new("ShaderNodeSeparateXYZ")
    lk.new(tc.outputs["UV"], sep.inputs["Vector"])

    # --- U axis (horizontal windows) ---
    # Multiply U by columns
    u_scale = nd.new("ShaderNodeMath")
    u_scale.operation = "MULTIPLY"
    lk.new(sep.outputs["X"], u_scale.inputs[0])
    u_scale.inputs[1].default_value = cols

    # Frac: repeating 0-1 per column
    u_frac = nd.new("ShaderNodeMath")
    u_frac.operation = "FRACT"
    lk.new(u_scale.outputs["Value"], u_frac.inputs[0])

    # Window pane: frame_thickness < u_frac < (1-frame_thickness)
    u_gt = nd.new("ShaderNodeMath")
    u_gt.operation = "GREATER_THAN"
    lk.new(u_frac.outputs["Value"], u_gt.inputs[0])
    u_gt.inputs[1].default_value = frame_thickness

    u_lt = nd.new("ShaderNodeMath")
    u_lt.operation = "LESS_THAN"
    lk.new(u_frac.outputs["Value"], u_lt.inputs[0])
    u_lt.inputs[1].default_value = 1.0 - frame_thickness

    u_window = nd.new("ShaderNodeMath")
    u_window.operation = "MULTIPLY"
    lk.new(u_gt.outputs["Value"], u_window.inputs[0])
    lk.new(u_lt.outputs["Value"], u_window.inputs[1])

    # --- V axis (vertical windows) ---
    v_scale = nd.new("ShaderNodeMath")
    v_scale.operation = "MULTIPLY"
    lk.new(sep.outputs["Y"], v_scale.inputs[0])
    v_scale.inputs[1].default_value = rows

    v_frac = nd.new("ShaderNodeMath")
    v_frac.operation = "FRACT"
    lk.new(v_scale.outputs["Value"], v_frac.inputs[0])

    v_gt = nd.new("ShaderNodeMath")
    v_gt.operation = "GREATER_THAN"
    lk.new(v_frac.outputs["Value"], v_gt.inputs[0])
    v_gt.inputs[1].default_value = frame_thickness

    v_lt = nd.new("ShaderNodeMath")
    v_lt.operation = "LESS_THAN"
    lk.new(v_frac.outputs["Value"], v_lt.inputs[0])
    v_lt.inputs[1].default_value = 1.0 - frame_thickness

    v_window = nd.new("ShaderNodeMath")
    v_window.operation = "MULTIPLY"
    lk.new(v_gt.outputs["Value"], v_window.inputs[0])
    lk.new(v_lt.outputs["Value"], v_window.inputs[1])

    # Combine U and V: both must be in window range
    window_mask = nd.new("ShaderNodeMath")
    window_mask.operation = "MULTIPLY"
    lk.new(u_window.outputs["Value"], window_mask.inputs[0])
    lk.new(v_window.outputs["Value"], window_mask.inputs[1])

    # Dark wall
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = wall_color
    wall.inputs["Roughness"].default_value = 0.9

    # Window emission
    win = nd.new("ShaderNodeEmission")
    win.inputs["Color"].default_value = emit_color
    win.inputs["Strength"].default_value = emit_str

    # Mix
    mix = nd.new("ShaderNodeMixShader")
    lk.new(window_mask.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["Emission"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


# Test buildings
configs = [
    ("8x5_thin", 8, 5, 0.12),
    ("12x6_med", 12, 6, 0.15),
    ("6x4_thick", 6, 4, 0.2),
]

for i, (name, rows, cols, frame) in enumerate(configs):
    x = (i - 1) * 10
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 6, 8))
    b = bpy.context.active_object
    b.name = name
    b.scale = (3, 3, 8)
    bpy.ops.object.transform_apply(scale=True)
    mat = make_math_window_mat(f"mat_{name}", rows=rows, cols=cols, frame_thickness=frame)
    b.data.materials.append(mat)
    print(f"  {name}: {rows}x{cols}, frame={frame}")

# Camera
bpy.ops.object.camera_add(location=(0, -4, 8))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(85), 0, 0)
cam.data.lens = 25

scene.render.filepath = "/tmp/math_windows.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/math_windows.png")
