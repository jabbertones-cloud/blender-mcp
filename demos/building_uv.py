"""Test UV coords vs Generated vs Object for Brick Texture on cube faces."""
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

def make_window_mat(name, brick_scale, mortar_size, coord_output):
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
    lk.new(tc.outputs[coord_output], brick.inputs["Vector"])

    # Invert Fac
    inv = nd.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    lk.new(brick.outputs["Fac"], inv.inputs[1])

    # Dark wall
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = (0.02, 0.02, 0.04, 1)
    wall.inputs["Roughness"].default_value = 0.9

    # Window emission
    win = nd.new("ShaderNodeEmission")
    win.inputs["Color"].default_value = (1.0, 0.9, 0.6, 1)
    win.inputs["Strength"].default_value = 15.0

    mix = nd.new("ShaderNodeMixShader")
    lk.new(inv.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["Emission"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat

# 3 buildings: UV vs Generated vs Object
configs = [
    ("UV_s6", 6.0, 0.04, "UV"),
    ("Generated_s10", 10.0, 0.03, "Generated"),
    ("Object_s6", 6.0, 0.04, "Object"),
]

for i, (name, bscale, mortar, coord) in enumerate(configs):
    x = (i - 1) * 10
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 6, 8))
    b = bpy.context.active_object
    b.name = name
    b.scale = (3, 3, 8)
    bpy.ops.object.transform_apply(scale=True)
    # Ensure UV map exists (cube primitive should have one by default)
    if not b.data.uv_layers:
        bpy.ops.uv.smart_project()
    mat = make_window_mat(f"mat_{name}", bscale, mortar, coord)
    b.data.materials.append(mat)
    print(f"  {name}: scale={bscale}, mortar={mortar}, coord={coord}, UVs={len(b.data.uv_layers)}")

# Camera looking at front faces
bpy.ops.object.camera_add(location=(0, -4, 8))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(85), 0, 0)
cam.data.lens = 25

scene.render.filepath = "/tmp/building_uv.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/building_uv.png")
