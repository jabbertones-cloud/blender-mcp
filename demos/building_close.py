"""ONE building, close up, Brick Fac to emission. No noise. No fog."""
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

# Minimal light
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 0.5

# Material: Brick Fac (inverted) → Emission Color via ColorRamp
# Generated coords, various scales — 3 buildings side by side
def make_simple_window_mat(name, brick_scale, mortar_size, coord_type="Generated"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()

    tc = nd.new("ShaderNodeTexCoord")
    brick = nd.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = brick_scale
    brick.inputs["Mortar Size"].default_value = mortar_size
    brick.offset = 0.5
    lk.new(tc.outputs[coord_type], brick.inputs["Vector"])

    # Invert Fac (1-Fac): 0=mortar→dark, 1=brick face→lit
    inv = nd.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    lk.new(brick.outputs["Fac"], inv.inputs[1])

    # Dark wall shader
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = (0.02, 0.02, 0.04, 1)
    wall.inputs["Roughness"].default_value = 0.9

    # Bright window emission
    win = nd.new("ShaderNodeEmission")
    win.inputs["Color"].default_value = (1.0, 0.9, 0.6, 1)
    win.inputs["Strength"].default_value = 15.0

    # Mix: Fac=0 → wall, Fac=1 → window
    mix = nd.new("ShaderNodeMixShader")
    lk.new(inv.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["Emission"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat

# Test 3 buildings with different scales/coords
configs = [
    ("Gen_s8_m03", 8.0, 0.03, "Generated"),
    ("Gen_s12_m03", 12.0, 0.03, "Generated"),
    ("Obj_s8_m03", 8.0, 0.03, "Object"),
]

for i, (name, bscale, mortar, coord) in enumerate(configs):
    x = (i - 1) * 8
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 8, 10))
    b = bpy.context.active_object
    b.name = name
    b.scale = (3, 3, 10)
    bpy.ops.object.transform_apply(scale=True)
    mat = make_simple_window_mat(f"mat_{name}", bscale, mortar, coord)
    b.data.materials.append(mat)
    print(f"  {name}: scale={bscale}, mortar={mortar}, coord={coord}")

# Camera looking at front face, close
bpy.ops.object.camera_add(location=(0, -2, 10))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(88), 0, 0)
cam.data.lens = 30

scene.render.filepath = "/tmp/building_close.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/building_close.png")
