"""Diagnostic: Compare Checker vs Brick vs Noise on flat planes, camera overhead."""
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
bg.inputs["Color"].default_value = (0.01, 0.01, 0.01, 1)
bg.inputs["Strength"].default_value = 1.0

# Bright area light overhead
bpy.ops.object.light_add(type='AREA', location=(0, 0, 8))
light = bpy.context.active_object
light.data.energy = 500
light.data.size = 20

def make_checker_mat(name, scale):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()
    tc = nd.new("ShaderNodeTexCoord")
    checker = nd.new("ShaderNodeTexChecker")
    checker.inputs["Scale"].default_value = scale
    checker.inputs["Color1"].default_value = (1, 1, 1, 1)
    checker.inputs["Color2"].default_value = (0, 0, 0, 1)
    lk.new(tc.outputs["Object"], checker.inputs["Vector"])
    emit = nd.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 3.0
    lk.new(checker.outputs["Color"], emit.inputs["Color"])
    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat

def make_brick_emit_mat(name, scale, mortar, coord_type="Object"):
    """Brick Fac → Emission Color (white=mortar=1, black=brick=0)"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()
    tc = nd.new("ShaderNodeTexCoord")
    brick = nd.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = scale
    brick.inputs["Mortar Size"].default_value = mortar
    brick.offset = 0.5
    # Set brick colors to see them clearly
    brick.inputs["Color1"].default_value = (1, 0, 0, 1)  # Red bricks
    brick.inputs["Color2"].default_value = (0, 0, 1, 1)  # Blue alternate
    brick.inputs["Mortar"].default_value = (1, 1, 1, 1)   # White mortar
    lk.new(tc.outputs[coord_type], brick.inputs["Vector"])

    # Route 1: Color output → Emission (should show red/blue bricks, white mortar)
    emit = nd.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 3.0
    lk.new(brick.outputs["Color"], emit.inputs["Color"])
    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat

def make_brick_fac_mat(name, scale, mortar, coord_type="Object"):
    """Brick Fac → grayscale Emission (white=mortar=1, black=brick=0)"""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()
    tc = nd.new("ShaderNodeTexCoord")
    brick = nd.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = scale
    brick.inputs["Mortar Size"].default_value = mortar
    brick.offset = 0.5
    lk.new(tc.outputs[coord_type], brick.inputs["Vector"])

    # Fac → separate RGB via color ramp for visualization
    ramp = nd.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    lk.new(brick.outputs["Fac"], ramp.inputs["Fac"])

    emit = nd.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 3.0
    lk.new(ramp.outputs["Color"], emit.inputs["Color"])
    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat

def make_noise_mat(name, scale):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()
    tc = nd.new("ShaderNodeTexCoord")
    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 5.0
    lk.new(tc.outputs["Object"], noise.inputs["Vector"])
    emit = nd.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 3.0
    lk.new(noise.outputs["Color"], emit.inputs["Color"])
    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat

# Create 6 test planes in a 2x3 grid
planes = [
    # Row 1: Checker, Brick Color, Noise
    ("Checker_s5", make_checker_mat("checker_s5", 5.0), (-4, 0, 0)),
    ("BrickColor_Obj_s5", make_brick_emit_mat("brick_col_obj_s5", 5.0, 0.02, "Object"), (0, 0, 0)),
    ("Noise_s5", make_noise_mat("noise_s5", 5.0), (4, 0, 0)),
    # Row 2: Brick Fac variants
    ("BrickFac_Obj_s5", make_brick_fac_mat("brick_fac_obj_s5", 5.0, 0.02, "Object"), (-4, -4, 0)),
    ("BrickFac_Gen_s5", make_brick_fac_mat("brick_fac_gen_s5", 5.0, 0.02, "Generated"), (0, -4, 0)),
    ("BrickColor_Gen_s5", make_brick_emit_mat("brick_col_gen_s5", 5.0, 0.02, "Generated"), (4, -4, 0)),
]

for name, mat, loc in planes:
    bpy.ops.mesh.primitive_plane_add(size=3, location=loc)
    p = bpy.context.active_object
    p.name = name
    p.data.materials.append(mat)

# Add text labels as small planes with emission (just for reference in print)
for name, mat, loc in planes:
    print(f"  Plane '{name}' at {loc}")

# Camera directly overhead looking down
bpy.ops.object.camera_add(location=(0, -2, 12))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(10), 0, 0)
cam.data.lens = 25

scene.render.filepath = "/tmp/texture_diag.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/texture_diag.png")
