"""Diagnostic: test Brick Texture visibility at various scales."""
import bpy, math

# Clear
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'

# World: dark blue
world = bpy.data.worlds["World"]
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.02, 0.03, 0.08, 1)
    bg.inputs["Strength"].default_value = 1.0

# Sun
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 2.0
sun.data.color = (1, 0.8, 0.5)
sun.rotation_euler = (math.radians(60), 0, 0)

def make_brick_mat(name, brick_scale, mortar_size, use_noise=False):
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
    lk.new(tc.outputs["Object"], brick.inputs["Vector"])

    # Invert Fac
    inv = nd.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    lk.new(brick.outputs["Fac"], inv.inputs[1])

    # Wall (dark)
    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = (0.03, 0.03, 0.05, 1)
    wall.inputs["Roughness"].default_value = 0.9

    # Window (bright, emissive)
    win = nd.new("ShaderNodeBsdfPrincipled")
    win.inputs["Base Color"].default_value = (0.9, 0.85, 0.6, 1)
    win.inputs["Emission Color"].default_value = (1.0, 0.9, 0.6, 1)
    win.inputs["Emission Strength"].default_value = 8.0
    win.inputs["Roughness"].default_value = 0.1

    mix = nd.new("ShaderNodeMixShader")

    if use_noise:
        noise = nd.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = brick_scale * 2.0
        noise.inputs["Detail"].default_value = 0.0
        lk.new(tc.outputs["Object"], noise.inputs["Vector"])
        nr = nd.new("ShaderNodeValToRGB")
        nr.color_ramp.elements[0].position = 0.0
        nr.color_ramp.elements[1].position = 0.5
        lk.new(noise.outputs["Fac"], nr.inputs["Fac"])
        mult = nd.new("ShaderNodeMath")
        mult.operation = "MULTIPLY"
        lk.new(inv.outputs["Value"], mult.inputs[0])
        lk.new(nr.outputs["Color"], mult.inputs[1])
        lk.new(mult.outputs["Value"], mix.inputs["Fac"])
    else:
        lk.new(inv.outputs["Value"], mix.inputs["Fac"])

    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["BSDF"], mix.inputs[2])
    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat

# Test buildings at different scales — close to camera
configs = [
    ("Scale3", 3.0, 0.2, False),
    ("Scale5", 5.0, 0.2, False),
    ("Scale8", 8.0, 0.15, False),
    ("Scale5_Noise", 5.0, 0.2, True),
]

for i, (name, bscale, mortar, noise) in enumerate(configs):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(i*5 - 7.5, 8, 5))
    b = bpy.context.active_object
    b.name = name
    b.scale = (2, 2, 5)
    bpy.ops.object.transform_apply(scale=True)
    mat = make_brick_mat(f"mat_{name}", bscale, mortar, noise)
    b.data.materials.append(mat)
    print(f"  Building '{name}': brick_scale={bscale}, mortar={mortar}, noise={noise}")

# Camera close up
bpy.ops.object.camera_add(location=(0, -2, 5))
cam = bpy.context.active_object
cam.name = "DiagCam"
scene.camera = cam
cam.rotation_euler = (math.radians(85), 0, 0)
cam.data.lens = 30

# Render
scene.render.filepath = "/tmp/brick_test.png"
bpy.ops.render.render(write_still=True)
print("Saved: /tmp/brick_test.png")
