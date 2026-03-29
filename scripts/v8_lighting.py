"""V8 Professional Lighting Rigs — Forensic Animation Quality

3-point forensic lighting + HDRI environments + volumetric atmosphere.
Each function returns Blender Python code as a string for run_py().
"""


def forensic_day_lighting():
    """Daytime 3-point forensic lighting rig with Nishita sky."""
    return """
import bpy, math

scene = bpy.context.scene

# === WORLD: Nishita Physical Sky ===
world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
tree = world.node_tree
nodes = tree.nodes
links = tree.links
for n in nodes:
    nodes.remove(n)

bg = nodes.new('ShaderNodeBackground')
bg.location = (200, 0)
out = nodes.new('ShaderNodeOutputWorld')
out.location = (400, 0)

sky = nodes.new('ShaderNodeTexSky')
sky.location = (0, 0)
sky.sky_type = 'NISHITA'
sky.sun_elevation = math.radians(45)  # Mid-morning/afternoon
sky.sun_rotation = math.radians(160)
sky.altitude = 0
sky.air_density = 1.0
sky.dust_density = 0.5
sky.ozone_density = 1.0
sky.sun_intensity = 1.0
sky.sun_disc = True
sky.sun_size = math.radians(0.545)

links.new(sky.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.2
links.new(bg.outputs['Background'], out.inputs['Surface'])

# === KEY LIGHT: Sun lamp matching sky angle ===
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20))
sun = bpy.context.active_object
sun.name = 'Key_Sun_v8'
sun.data.energy = 4.0
sun.data.angle = math.radians(0.545)
sun.rotation_euler = (math.radians(45), 0, math.radians(160))
sun.data.color = (1.0, 0.95, 0.9)

# === FILL LIGHT: Soft area light for shadow recovery ===
bpy.ops.object.light_add(type='AREA', location=(-15, -10, 8))
fill = bpy.context.active_object
fill.name = 'Fill_Area_v8'
fill.data.energy = 200.0
fill.data.size = 12.0
fill.data.color = (0.85, 0.9, 1.0)  # Slightly cool
fill.rotation_euler = (math.radians(60), 0, math.radians(-30))

# === RIM LIGHT: Separation from background ===
bpy.ops.object.light_add(type='AREA', location=(10, 15, 6))
rim = bpy.context.active_object
rim.name = 'Rim_Area_v8'
rim.data.energy = 150.0
rim.data.size = 8.0
rim.data.color = (1.0, 0.95, 0.85)  # Warm backlight
rim.rotation_euler = (math.radians(70), 0, math.radians(145))

__result__ = 'Day lighting rig: Key Sun + Fill Area + Rim Area + Nishita Sky'
"""


def forensic_night_lighting():
    """Nighttime parking lot lighting with sodium vapor lamps."""
    return """
import bpy, math

scene = bpy.context.scene

# === WORLD: Dark night sky ===
world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
tree = world.node_tree
nodes = tree.nodes
links = tree.links
for n in nodes:
    nodes.remove(n)

bg = nodes.new('ShaderNodeBackground')
bg.location = (200, 0)
out = nodes.new('ShaderNodeOutputWorld')
out.location = (400, 0)
bg.inputs['Color'].default_value = (0.005, 0.008, 0.02, 1)  # Dark blue-black
bg.inputs['Strength'].default_value = 0.3
links.new(bg.outputs['Background'], out.inputs['Surface'])

# === PARKING LOT LIGHTS: Sodium vapor (warm orange) ===
light_positions = [
    (-8, -8, 7),
    (8, -8, 7),
    (-8, 8, 7),
    (8, 8, 7),
    (0, 0, 8),
]
for i, pos in enumerate(light_positions):
    bpy.ops.object.light_add(type='AREA', location=pos)
    lamp = bpy.context.active_object
    lamp.name = f'ParkingLight_{i}_v8'
    lamp.data.energy = 800.0
    lamp.data.size = 2.0
    lamp.data.color = (1.0, 0.7, 0.3)  # Sodium vapor warm
    lamp.rotation_euler = (math.radians(90), 0, 0)  # Point down

    # Light pole geometry
    bpy.ops.mesh.primitive_cylinder_add(radius=0.08, depth=7, location=(pos[0], pos[1], pos[2]/2))
    pole = bpy.context.active_object
    pole.name = f'LightPole_{i}'
    pmat = bpy.data.materials.new(name=f'PoleMat_{i}')
    pmat.use_nodes = True
    pmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.15, 0.15, 0.15, 1)
    pmat.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value = 0.8
    pmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
    pole.data.materials.append(pmat)

# === MOONLIGHT: Very dim blue fill ===
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20))
moon = bpy.context.active_object
moon.name = 'Moonlight_v8'
moon.data.energy = 0.05
moon.data.color = (0.6, 0.7, 1.0)
moon.rotation_euler = (math.radians(60), 0, math.radians(30))

__result__ = 'Night lighting rig: 5 parking lights + moonlight'
"""


def forensic_dusk_lighting():
    """Dusk/golden hour lighting for dramatic forensic scenes."""
    return """
import bpy, math

scene = bpy.context.scene

world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
scene.world = world
world.use_nodes = True
tree = world.node_tree
nodes = tree.nodes
links = tree.links
for n in nodes:
    nodes.remove(n)

bg = nodes.new('ShaderNodeBackground')
bg.location = (200, 0)
out = nodes.new('ShaderNodeOutputWorld')
out.location = (400, 0)

sky = nodes.new('ShaderNodeTexSky')
sky.location = (0, 0)
sky.sky_type = 'NISHITA'
sky.sun_elevation = math.radians(8)  # Low sun = golden hour
sky.sun_rotation = math.radians(220)
sky.air_density = 3.0  # More atmosphere scatter
sky.dust_density = 2.0
sky.ozone_density = 1.5

links.new(sky.outputs['Color'], bg.inputs['Color'])
bg.inputs['Strength'].default_value = 1.5
links.new(bg.outputs['Background'], out.inputs['Surface'])

# Low warm sun
bpy.ops.object.light_add(type='SUN', location=(0, 0, 20))
sun = bpy.context.active_object
sun.name = 'Dusk_Sun_v8'
sun.data.energy = 3.0
sun.data.color = (1.0, 0.6, 0.3)  # Warm golden
sun.rotation_euler = (math.radians(8), 0, math.radians(220))

# Cool fill from opposite side
bpy.ops.object.light_add(type='AREA', location=(-10, -8, 5))
fill = bpy.context.active_object
fill.name = 'Dusk_Fill_v8'
fill.data.energy = 100.0
fill.data.size = 15.0
fill.data.color = (0.5, 0.6, 1.0)  # Cool shadow fill

__result__ = 'Dusk lighting rig: Low sun + cool fill'
"""


def enhanced_render_settings():
    """V8 render settings: Cycles optimized for forensic quality."""
    return """
import bpy

s = bpy.context.scene

# Engine
s.render.engine = 'CYCLES'
s.cycles.device = 'GPU'
prefs = bpy.context.preferences.addons.get('cycles')
if prefs:
    prefs.preferences.compute_device_type = 'METAL'
    prefs.preferences.get_devices()
    for d in prefs.preferences.devices:
        d.use = True

# Sampling — v8: higher quality than v6
s.cycles.samples = 256  # Up from 128
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.015  # Tighter than v6's 0.02

# Bounces — optimized for forensic scenes
s.cycles.max_bounces = 8
s.cycles.diffuse_bounces = 4
s.cycles.glossy_bounces = 4
s.cycles.transmission_bounces = 4  # Up from 1 — needed for glass
s.cycles.volume_bounces = 0

# Denoising
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPENIMAGEDENOISE'

# Noise reduction tricks
s.cycles.caustics_reflective = False
s.cycles.caustics_refractive = False
try:
    s.cycles.filter_glossy = 1.0
except: pass

# Clamping
s.cycles.sample_clamp_direct = 0
s.cycles.sample_clamp_indirect = 10

# Resolution
s.render.resolution_x = 1920
s.render.resolution_y = 1080
s.render.resolution_percentage = 100
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGBA'
s.render.film_transparent = False

# Color management — Filmic
s.view_settings.view_transform = 'Filmic'
s.view_settings.look = 'Medium High Contrast'
s.view_settings.exposure = 0.3

__result__ = 'V8 render settings: Cycles 256spl, OIDN, Filmic, optimized bounces'
"""


def v8_compositor():
    """V8 compositor: fog glow + lens distortion + subtle vignette."""
    return """
import bpy

s = bpy.context.scene
s.use_nodes = True
tree = s.node_tree
for n in tree.nodes:
    tree.nodes.remove(n)

rl = tree.nodes.new('CompositorNodeRLayers')
rl.location = (0, 300)

comp = tree.nodes.new('CompositorNodeComposite')
comp.location = (1200, 300)

# Glare for bloom on lights/reflections
glare = tree.nodes.new('CompositorNodeGlare')
glare.glare_type = 'FOG_GLOW'
glare.quality = 'HIGH'
glare.mix = 0.03  # Subtler than v6
glare.threshold = 2.5
glare.location = (300, 300)

# Lens distortion
lens = tree.nodes.new('CompositorNodeLensdist')
lens.inputs['Distort'].default_value = -0.008
lens.inputs['Dispersion'].default_value = 0.003
lens.location = (600, 300)

# Vignette (darken edges)
ellipse = tree.nodes.new('CompositorNodeEllipseMask')
ellipse.location = (300, 0)
ellipse.width = 0.85
ellipse.height = 0.85

blur_vig = tree.nodes.new('CompositorNodeBlur')
blur_vig.location = (500, 0)
blur_vig.size_x = 200
blur_vig.size_y = 200

mix_vig = tree.nodes.new('CompositorNodeMixRGB')
mix_vig.location = (900, 300)
mix_vig.blend_type = 'MULTIPLY'
mix_vig.inputs[0].default_value = 0.15  # Subtle vignette

tree.links.new(rl.outputs['Image'], glare.inputs['Image'])
tree.links.new(glare.outputs['Image'], lens.inputs['Image'])
tree.links.new(ellipse.outputs['Mask'], blur_vig.inputs['Image'])
tree.links.new(lens.outputs['Image'], mix_vig.inputs[1])
tree.links.new(blur_vig.outputs['Image'], mix_vig.inputs[2])
tree.links.new(mix_vig.outputs['Image'], comp.inputs['Image'])

__result__ = 'V8 compositor: glare + lens distortion + vignette'
"""
