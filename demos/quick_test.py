"""Quick diagnostic: render with NO fog, Cycles, to see true scene colors."""
import bpy, math, random

random.seed(42)
scene = bpy.context.scene

# Clear
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)

# Cycles for reliable background rendering
scene.render.engine = "CYCLES"
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100

# AgX
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Very High Contrast'
except:
    try:
        scene.view_settings.look = 'Very High Contrast'
    except:
        pass

# Sunset sky
world = bpy.data.worlds["World"]
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
nodes.clear()

coord = nodes.new("ShaderNodeTexCoord")
sep = nodes.new("ShaderNodeSeparateXYZ")
links.new(coord.outputs["Generated"], sep.inputs["Vector"])

ramp = nodes.new("ShaderNodeValToRGB")
cr = ramp.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (0.12, 0.04, 0.2, 1.0)  # deep purple nadir
e1 = cr.elements.new(0.42)
e1.color = (1.0, 0.45, 0.12, 1.0)  # warm orange near horizon
e2 = cr.elements.new(0.5)
e2.color = (1.0, 0.8, 0.3, 1.0)  # golden at horizon
e3 = cr.elements.new(0.58)
e3.color = (0.5, 0.65, 0.85, 1.0)  # pale blue above
cr.elements[1].position = 1.0
cr.elements[1].color = (0.05, 0.08, 0.18, 1.0)  # dark blue zenith
links.new(sep.outputs["Z"], ramp.inputs["Fac"])

bg = nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 3.0
links.new(ramp.outputs["Color"], bg.inputs["Color"])
output = nodes.new("ShaderNodeOutputWorld")
links.new(bg.outputs["Background"], output.inputs["Surface"])

# Sun
bpy.ops.object.light_add(type="SUN", location=(0, 0, 10))
sun = bpy.context.active_object
sun.data.energy = 5.0
sun.data.color = (1.0, 0.7, 0.4)
sun.rotation_euler = (math.radians(75), math.radians(15), math.radians(-30))

# A few test buildings with window material
def make_window_mat(name, wall_col, win_col, emit_col, emit_str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nd = mat.node_tree.nodes
    lk = mat.node_tree.links
    nd.clear()
    tc = nd.new("ShaderNodeTexCoord")
    mp = nd.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (15, 15, 15)
    lk.new(tc.outputs["Object"], mp.inputs["Vector"])

    brick = nd.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = 20.0
    brick.inputs["Mortar Size"].default_value = 0.1
    brick.offset = 0.5
    lk.new(mp.outputs["Vector"], brick.inputs["Vector"])

    inv = nd.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    lk.new(brick.outputs["Fac"], inv.inputs[1])

    noise = nd.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 13.0
    noise.inputs["Detail"].default_value = 5.0
    lk.new(mp.outputs["Vector"], noise.inputs["Vector"])

    nr = nd.new("ShaderNodeValToRGB")
    nr.color_ramp.elements[0].position = 0.0
    nr.color_ramp.elements[1].position = 0.5
    lk.new(noise.outputs["Fac"], nr.inputs["Fac"])

    mult = nd.new("ShaderNodeMath")
    mult.operation = "MULTIPLY"
    lk.new(inv.outputs["Value"], mult.inputs[0])
    lk.new(nr.outputs["Color"], mult.inputs[1])

    wall = nd.new("ShaderNodeBsdfPrincipled")
    wall.inputs["Base Color"].default_value = wall_col
    wall.inputs["Roughness"].default_value = 0.85

    win = nd.new("ShaderNodeBsdfPrincipled")
    win.inputs["Base Color"].default_value = win_col
    win.inputs["Emission Color"].default_value = emit_col
    win.inputs["Emission Strength"].default_value = emit_str
    win.inputs["Roughness"].default_value = 0.1

    mix = nd.new("ShaderNodeMixShader")
    lk.new(mult.outputs["Value"], mix.inputs["Fac"])
    lk.new(wall.outputs["BSDF"], mix.inputs[1])
    lk.new(win.outputs["BSDF"], mix.inputs[2])

    out = nd.new("ShaderNodeOutputMaterial")
    lk.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat

m1 = make_window_mat("TestGlass", (0.12, 0.15, 0.22, 1), (0.08, 0.12, 0.2, 1), (0.9, 0.85, 0.6, 1), 5.0)
m2 = make_window_mat("TestBrick", (0.5, 0.3, 0.2, 1), (0.1, 0.12, 0.18, 1), (1, 0.85, 0.5, 1), 4.0)

# Place a few buildings close to camera
for i, (x, h) in enumerate([(-12, 25), (-4, 35), (4, 20), (12, 30), (20, 15)]):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, 15, h/2))
    b = bpy.context.active_object
    b.name = f"TestBldg_{i}"
    b.scale = (3, 3, h/2)
    bpy.ops.object.transform_apply(scale=True)
    b.data.materials.append(m1 if i % 2 == 0 else m2)

# Water plane
bpy.ops.mesh.primitive_plane_add(size=100, location=(0, 0, 0))
water = bpy.context.active_object
water.name = "Water"
wm = bpy.data.materials.new("Water")
wm.use_nodes = True
wb = wm.node_tree.nodes.get("Principled BSDF")
wb.inputs["Base Color"].default_value = (0.02, 0.1, 0.2, 1)
wb.inputs["Roughness"].default_value = 0.05
water.data.materials.append(wm)

# Camera
bpy.ops.object.camera_add(location=(-15, -5, 6))
cam = bpy.context.active_object
cam.name = "TestCam"
scene.camera = cam
cam.rotation_euler = (math.radians(80), 0, math.radians(-10))
cam.data.lens = 35

# Render
scene.frame_set(1)
scene.render.filepath = "/tmp/city_diag_cycles.png"
bpy.ops.render.render(write_still=True)

print("=== DIAGNOSTIC RENDER COMPLETE ===")
print("Saved: /tmp/city_diag_cycles.png")
