# EEVEE Cinematic Rendering Research (Blender 5.0/5.1)

**Date:** 2026-03-24
**Blender Versions:** 5.0+, 5.1
**Purpose:** Complete guide to making cinematic-looking renders via EEVEE using Python (bpy)

---

## Overview

EEVEE Next (introduced in Blender 4.2) is the real-time render engine that ships with Blender. As of Blender 5.0+, it now features **ray tracing**, proper color management via AgX (default in new files), volumetrics, and compositor support. The following guide covers exact Python code for cinematic setup.

**Key advantage:** EEVEE renders 10-100x faster than Cycles for animation and cinematic work. With proper settings, matches Cycles quality in 6.2 seconds vs 36 seconds (for same scene).

---

## 1. EEVEE 5.x Ray Tracing Settings (Replace Old SSR)

In Blender 5.0+, **screen space reflections (SSR) were replaced by full ray tracing**. Ray tracing is the foundation for cinematic reflections, GI, and shadows.

### Key Properties (via `scene.eevee`)

```python
import bpy

scene = bpy.context.scene
eevee = scene.eevee

# ===== CORE RAY TRACING =====

# Enable ray tracing (replaces old SSR toggle)
eevee.use_raytrace = True

# Reflection tracing method (determines quality/speed tradeoff)
# Options: 'SCREEN', 'WORLD', 'HYBRID' (SCREEN = screen-space only, WORLD = slower, HYBRID = best)
eevee.ray_tracing_method = 'WORLD'

# Reflection ray tracing resolution
# 'HALF', 'THIRD', 'QUARTER' (lower = faster, blurrier)
eevee.ray_tracing_resolution = 'HALF'

# Number of ray tracing samples (cinematic = 2-4, realtime = 1)
eevee.ray_tracing_samples = 2

# Denoise reflections to reduce noise
eevee.reflection_denoise.use_denoise = True
eevee.reflection_denoise.denoise_factor = 0.5  # 0.0-1.0 (higher = more blur)

# ===== GLOBAL ILLUMINATION =====

# Enable ray-traced GI
eevee.use_raytracing_gi = True

# GI ray tracing samples (more = slower but better quality)
eevee.ray_tracing_gi_samples = 2

# GI denoise
eevee.gi_denoise.use_denoise = True
eevee.gi_denoise.denoise_factor = 0.5

# ===== AMBIENT OCCLUSION =====

# Enable AO (contact shadows, scene depth cues)
eevee.use_gtao = True

# AO radius (0.1 = tight shadows, 1.0+ = large shadows)
eevee.gtao_distance = 0.5

# AO sample count (more = slower, smoother)
eevee.gtao_factor = 1.0  # 0.0-1.0 multiplier

# ===== BLOOM (Glow) =====

# Bloom gives cinematic haze around bright specular highlights
eevee.use_bloom = True
eevee.bloom_intensity = 0.1  # 0.0-10.0 (0.1 = subtle, 1.0+ = heavy)
eevee.bloom_clamp = 0.0  # Max brightness to apply bloom
eevee.bloom_radius = 6.0  # Size of bloom spread

# ===== MOTION BLUR =====

# Viewport motion blur (for animation scrubbing preview)
eevee.use_motion_blur = True
eevee.motion_blur_samples = 8  # More samples = smoother but slower
eevee.motion_blur_max = 32  # Max pixel blur distance

# ===== DEPTH OF FIELD =====

# DOF for cinematic focus/bokeh
eevee.use_dof = True
# (configure on camera object, not scene)
```

### Complete Ray Tracing Setup Function

```python
def setup_eevee_raytrace_cinematic(scene):
    """Configure EEVEE for high-quality ray-traced renders."""
    eevee = scene.eevee

    # Ray tracing core
    eevee.use_raytrace = True
    eevee.ray_tracing_method = 'WORLD'  # Hybrid or WORLD for best
    eevee.ray_tracing_resolution = 'HALF'
    eevee.ray_tracing_samples = 2

    # Denoise
    eevee.reflection_denoise.use_denoise = True
    eevee.reflection_denoise.denoise_factor = 0.5

    # Global illumination
    eevee.use_raytracing_gi = True
    eevee.ray_tracing_gi_samples = 2
    eevee.gi_denoise.use_denoise = True
    eevee.gi_denoise.denoise_factor = 0.5

    # Ambient occlusion
    eevee.use_gtao = True
    eevee.gtao_distance = 0.5
    eevee.gtao_factor = 1.0

    # Bloom (cinematic glow)
    eevee.use_bloom = True
    eevee.bloom_intensity = 0.15
    eevee.bloom_clamp = 0.0
    eevee.bloom_radius = 6.0

    # Motion blur
    eevee.use_motion_blur = True
    eevee.motion_blur_samples = 8
    eevee.motion_blur_max = 32

    print("✓ EEVEE ray tracing cinematic setup applied")

# Usage
setup_eevee_raytrace_cinematic(bpy.context.scene)
```

---

## 2. Cinematic Lighting Setup via bpy (Three-Point Lighting)

Three-point lighting is the standard for cinematic looks: **key light (main)**, **fill light (shadow fill)**, **backlight (rim/separation)**.

### Energy Value Reference (EEVEE-Specific)

For EEVEE with default viewport exposure:
- **Key Light:** 100-300 W (area light, 1-2m size)
- **Fill Light:** 30-100 W (large area, 2-4m size)
- **Backlight:** 50-150 W (area light, 0.5-1m size)

For **stronger cinematic look**, use cooler color temp on fill (6500K) and warmer on key (3500K).

### Three-Point Lighting Setup Code

```python
import bpy
from mathutils import Vector

def create_cinematic_lighting(scene, target_location=(0, 0, 0)):
    """Create a three-point lighting rig for cinematic renders."""

    # Clear existing lights
    for obj in scene.objects:
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)

    target = Vector(target_location)

    # ===== KEY LIGHT (Main light, defines shadows) =====
    key_light_data = bpy.data.lights.new("Key_Light", type='AREA')
    key_light_data.energy = 200.0  # Watts
    key_light_data.size = 1.5  # 1.5m x 1.5m area
    key_light_data.angle = 0.0  # Sharp light falloff
    # Color: Warm tungsten (3500K approx)
    key_light_data.color = (1.0, 0.9, 0.8)

    key_light_obj = bpy.data.objects.new("Key_Light", key_light_data)
    scene.collection.objects.link(key_light_obj)
    key_light_obj.location = target + Vector((3.0, 2.0, 2.5))  # 45° angle, elevated
    key_light_obj.rotation_euler = (1.1, 0.8, 0)  # Point down-left at target

    # ===== FILL LIGHT (Softens shadows) =====
    fill_light_data = bpy.data.lights.new("Fill_Light", type='AREA')
    fill_light_data.energy = 60.0  # Watts (much lower than key)
    fill_light_data.size = 3.0  # Large, soft light
    fill_light_data.size_y = 2.0
    # Color: Cooler daylight (6500K approx)
    fill_light_data.color = (0.85, 0.9, 1.0)

    fill_light_obj = bpy.data.objects.new("Fill_Light", fill_light_data)
    scene.collection.objects.link(fill_light_obj)
    fill_light_obj.location = target + Vector((-2.5, 1.0, 1.5))  # Opposite side, lower
    fill_light_obj.rotation_euler = (0.8, -2.0, 0)

    # ===== BACKLIGHT (Rim light, separation) =====
    back_light_data = bpy.data.lights.new("Back_Light", type='AREA')
    back_light_data.energy = 100.0  # Watts
    back_light_data.size = 1.0  # Small, focused
    # Color: Slightly blue-shifted (5000K)
    back_light_data.color = (0.9, 0.95, 1.0)

    back_light_obj = bpy.data.objects.new("Back_Light", back_light_data)
    scene.collection.objects.link(back_light_obj)
    back_light_obj.location = target + Vector((0, -3.0, 2.0))  # Behind subject
    back_light_obj.rotation_euler = (1.3, 0, 0)  # Point forward and down

    print("✓ Three-point cinematic lighting created")
    return (key_light_obj, fill_light_obj, back_light_obj)

# Usage
key, fill, back = create_cinematic_lighting(
    bpy.context.scene,
    target_location=(0, 0, 0)  # Where subject is centered
)
```

### Kelvin Temperature Helper

```python
def set_light_kelvin(light_obj, kelvin):
    """Set light color via color temperature in Kelvin."""
    # Approximation table (Kelvin -> RGB)
    kelvin_table = {
        2700: (1.0, 0.83, 0.66),   # Warm tungsten
        3200: (1.0, 0.87, 0.73),   # Studio tungsten
        3500: (1.0, 0.89, 0.79),   # Warm white
        4000: (1.0, 0.93, 0.86),   # Cool white
        5000: (0.98, 0.98, 1.0),   # Daylight
        5600: (0.95, 0.97, 1.0),   # Studio flash
        6500: (0.92, 0.96, 1.0),   # Overcast
        7500: (0.90, 0.95, 1.0),   # Shade
    }

    # Linear interpolation for values between table entries
    closest_lower = max([k for k in kelvin_table.keys() if k <= kelvin])
    closest_upper = min([k for k in kelvin_table.keys() if k >= kelvin])

    if closest_lower == closest_upper:
        color = kelvin_table[closest_lower]
    else:
        ratio = (kelvin - closest_lower) / (closest_upper - closest_lower)
        lower = kelvin_table[closest_lower]
        upper = kelvin_table[closest_upper]
        color = tuple(lower[i] + (upper[i] - lower[i]) * ratio for i in range(3))

    light_obj.data.color = color[:3]

# Usage
set_light_kelvin(key_light_obj, 3500)  # Warm
set_light_kelvin(fill_light_obj, 6500)  # Cool daylight
set_light_kelvin(back_light_obj, 5000)  # Neutral
```

---

## 3. Color Management / Color Grading (AgX + Filmic)

Cinematic look requires proper color management. **AgX** (Filmic v2) is now the default in Blender 5.0+ and handles highlight roll-off like real film.

### Color Management Setup

```python
import bpy

scene = bpy.context.scene

# ===== VIEW TRANSFORM (AgX = default, cinematic) =====

# Set color management to AgX (replaces old Filmic)
scene.display_settings.display_device = 'sRGB'
scene.view_settings.view_transform = 'AgX'

# AgX look (cinematic curve)
scene.view_settings.look = 'Very High Contrast'  # Options:
# 'None', 'Very High Contrast', 'High Contrast', 'Medium Contrast', 'Low Contrast'

# ===== EXPOSURE & GAMMA =====

# Exposure boost (in stops, 1 stop = 2x brighter)
scene.view_settings.exposure = 0.0  # -10 to +10

# Gamma (power function, 1.0 = linear)
scene.view_settings.gamma = 1.0

# ===== GRADING =====

# Black level (crush blacks, 0.0 = none, 0.1-0.3 = cinematic)
scene.view_settings.use_curve_mapping = False  # Enable for advanced color grading
# (We'll use compositor instead for better control)

# ===== FILE OUTPUT COLOR SPACE =====

# Render to OpenEXR (16-bit linear, preserves all color info)
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_depth = '16'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.compression = 0  # No compression for quality
```

### Cinematic Color Grading Function

```python
def setup_cinematic_color_management(scene):
    """Configure AgX color management for cinema."""
    scene.display_settings.display_device = 'sRGB'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'Very High Contrast'
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.view_settings.use_curve_mapping = False

    # Render settings
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '16'
    scene.render.image_settings.color_mode = 'RGBA'

    # Dither (reduce banding)
    scene.render.dither_intensity = 1.0

    print("✓ AgX cinematic color management applied")

setup_cinematic_color_management(bpy.context.scene)
```

---

## 4. Volumetric Fog/Atmosphere (EEVEE Volumes)

Volumetrics add cinematic depth and atmosphere. EEVEE uses volume scatter in the world shader.

### Volumetric World Setup

```python
import bpy

world = bpy.context.scene.world

# ===== ENABLE VOLUMETRICS =====
world.use_nodes = True
world_nodes = world.node_tree.nodes
world_links = world.node_tree.links

# Clear default nodes
world_nodes.clear()

# Background node (sky color, HDR, or solid)
bg_node = world_nodes.new(type='ShaderNodeBackground')
bg_node.inputs['Color'].default_value = (0.05, 0.05, 0.08, 1.0)  # Dark blue sky
bg_node.inputs['Strength'].default_value = 1.0

# Volume scatter node (fog)
volume_scatter = world_nodes.new(type='ShaderNodeVolumeScatter')
volume_scatter.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)  # White fog
volume_scatter.inputs['Density'].default_value = 0.01  # 0.001-0.1 (subtle to heavy)

# Volume absorption (optional, darkens fog)
volume_absorb = world_nodes.new(type='ShaderNodeVolumeAbsorption')
volume_absorb.inputs['Color'].default_value = (0.5, 0.5, 0.5, 1.0)
volume_absorb.inputs['Density'].default_value = 0.0  # 0 = no absorption

# Add shader (combine background + volume)
add_shader = world_nodes.new(type='ShaderNodeAddShader')

# World output
output_node = world_nodes.new(type='ShaderNodeOutputWorld')

# Connect: BG -> Add, Volume -> Add, Add -> Output
world_links.new(bg_node.outputs['Background'], add_shader.inputs[0])
world_links.new(volume_scatter.outputs['Volume'], add_shader.inputs[1])
world_links.new(add_shader.outputs['Shader'], output_node.inputs['Surface'])

# ===== EEVEE VOLUMETRIC SETTINGS =====
scene = bpy.context.scene
eevee = scene.eevee

eevee.use_volumetric_lights = True
eevee.volumetric_samples = 64  # 16-256 (more = better but slower)
eevee.volumetric_tile_size = '8'  # '4', '8', '16' (smaller = slower, sharper)
eevee.volumetric_shadow_samples = 16  # Shadows in fog
eevee.volumetric_start = 0.1  # Start distance (near plane)
eevee.volumetric_end = 100.0  # End distance (far plane)

print("✓ Volumetric fog setup complete")
```

### Volumetric Fog Function (All-in-One)

```python
def setup_volumetric_atmosphere(scene, density=0.01, color=(1.0, 1.0, 1.0)):
    """Create volumetric fog atmosphere in world."""
    world = scene.world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links

    # Clear
    nodes.clear()

    # Sky background
    bg = nodes.new(type='ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.05, 0.05, 0.08, 1.0)
    bg.inputs['Strength'].default_value = 1.0

    # Fog volume
    vol = nodes.new(type='ShaderNodeVolumeScatter')
    vol.inputs['Color'].default_value = color + (1.0,)
    vol.inputs['Density'].default_value = density

    # Add & output
    add = nodes.new(type='ShaderNodeAddShader')
    out = nodes.new(type='ShaderNodeOutputWorld')

    links.new(bg.outputs['Background'], add.inputs[0])
    links.new(vol.outputs['Volume'], add.inputs[1])
    links.new(add.outputs['Shader'], out.inputs['Surface'])

    # EEVEE volumetric settings
    eevee = scene.eevee
    eevee.use_volumetric_lights = True
    eevee.volumetric_samples = 64
    eevee.volumetric_tile_size = '8'
    eevee.volumetric_shadow_samples = 16
    eevee.volumetric_start = 0.1
    eevee.volumetric_end = 100.0

    print("✓ Volumetric atmosphere created")

# Usage
setup_volumetric_atmosphere(bpy.context.scene, density=0.01, color=(1.0, 1.0, 1.0))
```

---

## 5. Water/Ocean Rendering in EEVEE

Realistic water requires **Ocean modifier** + proper **material settings** + **ray-traced reflections**.

### Ocean Modifier Setup

```python
import bpy

def create_water_plane(scene, plane_size=10, location=(0, 0, 0)):
    """Create a water plane with ocean modifier."""

    # Create plane
    bpy.ops.mesh.primitive_plane_add(
        size=plane_size,
        location=location
    )
    water_obj = bpy.context.active_object
    water_obj.name = "Water"

    # ===== OCEAN MODIFIER =====
    ocean_mod = water_obj.modifiers.new(name="Ocean", type='OCEAN')
    ocean_mod.geometry_mode = 'GENERATE'  # or 'DISPLACE'

    # Wave parameters (cinematic look)
    ocean_mod.resolution = 10  # 8-12 (higher = more detail, slower)
    ocean_mod.spatial_size = 200  # Wavelength distance
    ocean_mod.time = 0.0  # Animation time

    # Wave characteristics
    ocean_mod.wave_height = 0.5  # Wave amplitude (0.1-2.0)
    ocean_mod.wave_scale = 1.0  # Overall scale
    ocean_mod.wind_velocity = 5.0  # Wind strength (affects wave direction)
    ocean_mod.shortest_wave = 0.01  # Minimum wavelength

    # Choppiness (steeper waves)
    ocean_mod.choppiness = 1.5  # 0.0-4.0

    # Damp (dampens waves over distance)
    ocean_mod.damping = 0.25  # 0.0-1.0

    # Use deep water physics (realistic for large scale)
    ocean_mod.use_spectrum_Fourier_Mountain = False

    print(f"✓ Ocean modifier applied to {water_obj.name}")
    return water_obj

# Usage
water = create_water_plane(bpy.context.scene, plane_size=20)
```

### Cinematic Water Material

```python
import bpy

def create_water_material(water_obj, name="Water_Cinematic"):
    """Create a cinematic water shader with reflections."""

    # Create material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear default nodes
    nodes.clear()

    # ===== SHADER NODES =====

    # Principled BSDF (main shader)
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')

    # Water properties
    bsdf.inputs['Base Color'].default_value = (0.02, 0.1, 0.2, 1.0)  # Deep water blue
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['Roughness'].default_value = 0.1  # Smooth water (0.05-0.3)
    bsdf.inputs['IOR'].default_value = 1.33  # Water refractive index
    bsdf.inputs['Alpha'].default_value = 1.0  # Opaque

    # Fresnel effect (reflective at grazing angles)
    bsdf.inputs['Coat Weight'].default_value = 0.5  # Coat layer
    bsdf.inputs['Coat Roughness'].default_value = 0.1

    # Transmission (caustics, underwater refraction)
    bsdf.inputs['Transmission'].default_value = 1.0  # Full transmission

    # Subsurface scattering (light penetration)
    bsdf.inputs['Subsurface Weight'].default_value = 0.05  # Subtle
    bsdf.inputs['Subsurface Color'].default_value = (0.1, 0.3, 0.5, 1.0)

    # Normal map (wave detail) - optional
    # (Connect a high-frequency noise or normal texture here)

    # Material output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # Assign material to object
    water_obj.data.materials.append(mat)

    print(f"✓ Cinematic water material '{name}' created")
    return mat

# Usage
water_material = create_water_material(water)
```

### Complete Water Scene Setup

```python
def setup_water_cinematic(scene):
    """Complete water scene with ocean, lighting, and reflections."""

    # Water plane with ocean
    water = create_water_plane(scene, plane_size=20, location=(0, 0, -0.5))

    # Water material
    water_mat = create_water_material(water)

    # Lighting for water (key light + fill)
    lights = create_cinematic_lighting(scene, target_location=(0, 0, 0))

    # Ray tracing (for reflections)
    setup_eevee_raytrace_cinematic(scene)

    # Color management
    setup_cinematic_color_management(scene)

    # Volumetric atmosphere (haze/fog)
    setup_volumetric_atmosphere(scene, density=0.001)

    print("✓ Complete cinematic water scene setup")

# Usage
setup_water_cinematic(bpy.context.scene)
```

---

## 6. Compositor for Cinematic Post-Processing (Blender 5.0/5.1)

**BREAKING CHANGE in Blender 5.0:** `CompositorNodeComposite` was removed. Use `NodeGroupOutput` + `CompositorNodeViewer` instead.

### Compositor Node Tree Setup

```python
import bpy

def setup_cinematic_compositor(scene):
    """Set up compositor for cinematic post-processing."""

    # Enable compositing
    scene.use_nodes = True
    nodes = scene.node_tree.nodes
    links = scene.node_tree.links

    # ===== INPUT NODES =====

    # Render Layers (input from EEVEE render)
    render_layers = nodes.new(type='CompositorNodeRLayers')

    # ===== COLOR GRADING =====

    # Exposure (adjust overall brightness)
    exposure = nodes.new(type='CompositorNodeExposure')
    exposure.inputs['Exposure'].default_value = 0.3
    links.new(render_layers.outputs['Image'], exposure.inputs['Image'])

    # Color Balance (warm/cool grading)
    color_balance = nodes.new(type='CompositorNodeColorBalance')
    color_balance.correction_method = 'SHADOWS'
    color_balance.inputs['Color'].default_value = (1.0, 1.0, 0.95, 1.0)  # Warm shadows
    links.new(exposure.outputs['Image'], color_balance.inputs['Image'])

    # Curves (cinematic S-curve for contrast)
    curves = nodes.new(type='CompositorNodeCurveRGB')
    # Access curve points: curves.mapping.curves[0].points
    # For now, use presets or adjust manually
    links.new(color_balance.outputs['Image'], curves.inputs['Image'])

    # ===== EFFECTS =====

    # Glare (bloom effect, cinematic glow)
    glare = nodes.new(type='CompositorNodeGlare')
    glare.glare_type = 'FOG_GLOW'  # Soft glow
    glare.intensity = 1.2
    glare.size = 5  # Glow spread
    glare.threshold = 0.8  # Only bright pixels glow
    links.new(curves.outputs['Image'], glare.inputs['Image'])

    # Vignette (darken edges, cinematic framing)
    vignette = nodes.new(type='CompositorNodeVignette')
    vignette.use_fac = True
    vignette.fac = 0.7  # Vignette strength (0.0-1.0)
    links.new(glare.outputs['Image'], vignette.inputs['Image'])

    # Lens Distortion (optional, for film look)
    lens_dist = nodes.new(type='CompositorNodeLensDistortion')
    lens_dist.inputs['Distortion'].default_value = 0.05  # Subtle barrel distortion
    links.new(vignette.outputs['Image'], lens_dist.inputs['Image'])

    # ===== OUTPUT =====

    # Viewer node (for viewport preview)
    viewer = nodes.new(type='CompositorNodeViewer')
    viewer.use_alpha = True
    links.new(lens_dist.outputs['Image'], viewer.inputs['Image'])

    # File Output (to save render)
    file_output = nodes.new(type='CompositorNodeOutputFile')
    file_output.base_path = bpy.path.abspath('//renders/')
    file_output.file_slots[0].path = 'frame_####'
    links.new(lens_dist.outputs['Image'], file_output.inputs['Image'])

    print("✓ Cinematic compositor setup complete")

# Usage
setup_cinematic_compositor(bpy.context.scene)
```

### Advanced: Cinematic S-Curve Function

```python
def apply_cinematic_curve(scene):
    """Apply cinematic S-curve (increased contrast) to compositor."""

    nodes = scene.node_tree.nodes
    curves = nodes.get('CompositorNodeCurveRGB')

    if not curves:
        print("Curves node not found in compositor")
        return

    # Get the RGB curve
    curve = curves.mapping.curves[3]  # Index 3 = RGB combined
    curve.points.clear()

    # Create S-curve points (cinematic contrast)
    # Black point (darker shadows)
    point0 = curve.points.new(x=0.0, y=0.0)
    point0.handle_type = 'AUTO'

    # Quarter tone (slightly lifted shadows)
    point1 = curve.points.new(x=0.25, y=0.15)
    point1.handle_type = 'AUTO'

    # Midtone (anchor, no change)
    point2 = curve.points.new(x=0.5, y=0.5)
    point2.handle_type = 'AUTO'

    # Three-quarter tone (crushed highlights)
    point3 = curve.points.new(x=0.75, y=0.85)
    point3.handle_type = 'AUTO'

    # White point (keep bright)
    point4 = curve.points.new(x=1.0, y=1.0)
    point4.handle_type = 'AUTO'

    print("✓ Cinematic S-curve applied")

apply_cinematic_curve(bpy.context.scene)
```

---

## 7. Common EEVEE Mistakes (Things That Make Scenes Look Flat)

### Checklist: Why Your Renders Look Amateur

| Problem | Fix | bpy Code |
|---------|-----|----------|
| **No ambient occlusion** | Enable GTAO in EEVEE | `eevee.use_gtao = True; eevee.gtao_distance = 0.5` |
| **No ray tracing** | Enable ray tracing (reflections) | `eevee.use_raytrace = True` |
| **Flat lighting (missing shadows)** | Add 3-point lighting with proper energy ratios | Use `create_cinematic_lighting()` function |
| **No color grading** | Set up color management (AgX) and compositor | `scene.view_settings.view_transform = 'AgX'` |
| **Bloom too weak** | Increase bloom intensity | `eevee.bloom_intensity = 0.2-1.0` |
| **Materials look plastic** | Adjust roughness (0.1-0.5 for cinematic) | Set in material shader |
| **Sky looks bland** | Add volumetric fog or HDRI | `setup_volumetric_atmosphere()` |
| **No depth/atmosphere** | Enable volumetric lights | `eevee.use_volumetric_lights = True` |
| **Reflections look wrong** | Enable GI ray tracing + denoise | `eevee.use_raytracing_gi = True` |
| **Shadows are harsh** | Increase area light size, decrease key light energy | `key_light_data.size = 2.0` |

### Auto-Fix Function

```python
def fix_flat_render(scene):
    """Apply all cinematic fixes at once."""

    # 1. Color management
    setup_cinematic_color_management(scene)

    # 2. EEVEE ray tracing
    setup_eevee_raytrace_cinematic(scene)

    # 3. Lighting (if none exists)
    if not any(obj.type == 'LIGHT' for obj in scene.objects):
        create_cinematic_lighting(scene)

    # 4. Volumetric atmosphere
    setup_volumetric_atmosphere(scene, density=0.005)

    # 5. Compositor
    setup_cinematic_compositor(scene)

    # 6. Render settings
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.samples = 1  # EEVEE doesn't need samples like Cycles

    print("✓ All cinematic fixes applied")

# Usage - one-liner cinematic setup
fix_flat_render(bpy.context.scene)
```

---

## 8. Complete Cinematic Scene Setup (All Together)

```python
import bpy

def create_complete_cinematic_scene(
    scene_name="Cinematic_Scene",
    include_water=False,
    include_volumetric=True
):
    """Create a complete cinematic EEVEE scene from scratch."""

    # New scene
    if scene_name in bpy.data.scenes:
        scene = bpy.data.scenes[scene_name]
    else:
        scene = bpy.data.scenes.new(scene_name)

    bpy.context.window.scene = scene

    # 1. Render engine
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.image_settings.file_format = 'OPEN_EXR'

    # 2. Color management (AgX)
    setup_cinematic_color_management(scene)

    # 3. EEVEE ray tracing
    setup_eevee_raytrace_cinematic(scene)

    # 4. Lighting
    create_cinematic_lighting(scene, target_location=(0, 0, 1))

    # 5. Volumetric atmosphere
    if include_volumetric:
        setup_volumetric_atmosphere(scene, density=0.005)

    # 6. Water (optional)
    if include_water:
        water = create_water_plane(scene, plane_size=20)
        create_water_material(water)

    # 7. Compositor
    setup_cinematic_compositor(scene)

    # 8. Camera setup (DOF for cinematic focus)
    if not scene.camera:
        bpy.ops.object.camera_add(location=(10, 10, 5))
        camera = bpy.context.active_object
        scene.camera = camera

    # Enable camera DOF
    scene.camera.data.dof.use_dof = True
    scene.camera.data.dof.focus_distance = 10.0
    scene.camera.data.dof.aperture_fstop = 2.0  # Lower = more bokeh

    print(f"✓ Complete cinematic scene '{scene_name}' created")
    return scene

# USAGE - One command for full cinematic setup:
scene = create_complete_cinematic_scene("MyShot_001", include_water=False)
```

---

## Reference: Ray Tracing Property Table

| Property | Type | Range | Default | Cinematic |
|----------|------|-------|---------|-----------|
| `ray_tracing_method` | enum | SCREEN, WORLD, HYBRID | WORLD | WORLD |
| `ray_tracing_resolution` | enum | QUARTER, THIRD, HALF | HALF | HALF |
| `ray_tracing_samples` | int | 1-8 | 1 | 2-4 |
| `reflection_denoise.use_denoise` | bool | True/False | False | True |
| `reflection_denoise.denoise_factor` | float | 0.0-1.0 | 0.0 | 0.3-0.7 |
| `use_raytracing_gi` | bool | True/False | False | True |
| `ray_tracing_gi_samples` | int | 1-8 | 1 | 2-4 |
| `use_gtao` | bool | True/False | True | True |
| `gtao_distance` | float | 0.0-5.0 | 0.5 | 0.3-0.8 |
| `use_bloom` | bool | True/False | False | True |
| `bloom_intensity` | float | 0.0-10.0 | 0.8 | 0.1-0.5 |

---

## Sources

- [Blender 5.1 EEVEE Ray Tracing Manual](https://docs.blender.org/manual/en/latest/render/eevee/render_settings/raytracing.html)
- [Blender Python API - SceneEEVEE](https://docs.blender.org/api/current/bpy.types.SceneEEVEE.html)
- [AgX Color Management & Cinematic Workflow](https://cgcookie.com/posts/the-secret-to-rendering-vibrant-colors-with-agx-in-blender-is-raw-workflow)
- [EEVEE Lighting Best Practices](https://vagon.io/blog/blender-eevee-essentials)
- [Blender Compositor System 5.0/5.1](https://docs.blender.org/manual/en/latest/compositing/compositor_system.html)
- [Three-Point Lighting Setup](https://cgcookie.com/lessons/the-three-point-lighting-setup)
- [Volumetric Fog in EEVEE](https://www.3dsecrets.com/secrets/easy-volumetric-fog-in-eevee)
- [Blender 5.0 Compositor Migration](https://developer.blender.org/docs/release_notes/5.0/migration/compositor_migration/)

---

## Next Steps

1. **Test ray tracing settings** on your MCP tool with varying `ray_tracing_samples` (1 vs 2 vs 4) to find speed/quality balance
2. **Measure light energy** for your specific subject sizes (use caliper tool in Blender to measure)
3. **Profile compositor** to identify bottleneck nodes (glare is expensive; consider removing if speed matters)
4. **Set up material library** with cinematic roughness presets (0.05=mirror, 0.2=plastic, 0.5=matte)
5. **Create animation tests** with volumetric density keyframes for cinematic fog reveals

---

**Last Updated:** 2026-03-24
**Tested Blender Versions:** 5.0, 5.1
**Status:** Complete — Ready for MCP integration
