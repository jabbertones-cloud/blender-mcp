"""Bare minimum test: map Brick Fac directly to emission to SEE the pattern."""
import bpy, math

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720

# Dark background
world = bpy.data.worlds["World"]
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.01, 0.01, 0.03, 1)
bg.inputs["Strength"].default_value = 1.0

# Light
bpy.ops.object.light_add(type="SUN", location=(0,0,10))
sun = bpy.context.active_object
sun.data.energy = 3.0

# Test: Brick Fac → Emission directly (no inversion, no noise)
# If Fac=1 = white (mortar lines), Fac=0 = black (brick faces)
def make_fac_vis_mat(name, coord_type, brick_scale, mortar):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()

    tc = nd.new("ShaderNodeTexCoord")

    brick = nd.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = brick_scale
    brick.inputs["Mortar Size"].default_value = mortar
    brick.offset = 0.5

    # Try different coordinate types
    if coord_type == "Object":
        lk.new(tc.outputs["Object"], brick.inputs["Vector"])
    elif coord_type == "Generated":
        lk.new(tc.outputs["Generated"], brick.inputs["Vector"])
    elif coord_type == "UV":
        lk.new(tc.outputs["UV"], brick.inputs["Vector"])

    # Emission shader: Fac → Color directly (white=mortar, black=brick)
    emit = nd.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 5.0
    lk.new(brick.outputs["Fac"], emit.inputs["Strength"])
    emit.inputs["Color"].default_value = (1, 1, 1, 1)

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat

# 4 test buildings: different coord types and scales
tests = [
    ("Generated_s5", "Generated", 5.0, 0.2),
    ("Object_s5", "Object", 5.0, 0.2),
    ("Generated_s3", "Generated", 3.0, 0.25),
    ("Object_s3", "Object", 3.0, 0.25),
]

for i, (name, ctype, bscale, mortar) in enumerate(tests):
    x = (i - 1.5) * 5
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 5, 3))
    b = bpy.context.active_object
    b.name = name
    b.scale = (2, 2, 3)
    bpy.ops.object.transform_apply(scale=True)
    mat = make_fac_vis_mat(f"mat_{name}", ctype, bscale, mortar)
    b.data.materials.append(mat)
    print(f"  {name}: coord={ctype}, scale={bscale}, mortar={mortar}")

# Camera very close
bpy.ops.object.camera_add(location=(0, -2, 3))
cam = bpy.context.active_object
scene.camera = cam
cam.rotation_euler = (math.radians(88), 0, 0)
cam.data.lens = 28

scene.render.filepath = "/tmp/fac_test.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/fac_test.png")
