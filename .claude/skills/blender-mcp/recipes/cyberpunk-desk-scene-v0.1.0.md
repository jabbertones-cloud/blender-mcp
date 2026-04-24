---
id: cyberpunk-desk-scene
version: 0.1.0
title: Cyberpunk Desk Scene with Neon Lighting and HDRI
description: |
  High-impact cyberpunk workspace with neon accent lighting, reflective
  surfaces, volumetric effects, and HDRI backdrop. Includes dynamic
  glow effects, material presets, and real-time material adjustments.
trigger_patterns:
  - "cyberpunk desk"
  - "neon lighting setup"
  - "tech workspace"
  - "futuristic interior"
tools_used:
  - blender_create_object
  - blender_modify_material
  - blender_add_hdri
  - execute_python
created_at: 2026-04-23
author: AutoSkill
tier: atomic
category: scenes
dependencies: []
---

## When to Use
Ideal for sci-fi visualizations, product placement in futuristic settings, tech company marketing materials, and cyberpunk-themed projects. Use when:
- Creating futuristic workspace renders
- Showcasing tech products in compelling environments
- Building cyberpunk aesthetic for games or film
- Designing corporate/startup brand visualizations
- Testing materials in high-contrast lighting

## Parameters
- **Neon Color Palette**: Cyan, Magenta, Yellow (RGB options)
- **Volumetric Fog Density**: 0.1 (adjustable 0.05-0.3)
- **Glow Intensity**: 2.5 (adjustable 1.0-5.0)
- **HDRI Rotation**: 0° (adjustable 0-360°)
- **Ambient Strength**: 1.2 (adjustable 0.5-2.0)

## Steps

1. **Initialize Base Desk Environment**
Create the workspace foundation:
```python
import bpy
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
desk = bpy.context.active_object
desk.name = 'Desk_Base'
desk.scale = (2.5, 1.2, 0.1)
bpy.ops.object.transform_apply(scale=True)

# Create desk surface material
mat_desk = bpy.data.materials.new(name='DeskSurface_Dark')
mat_desk.use_nodes = True
bsdf = mat_desk.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.05, 0.05, 0.08, 1.0)
bsdf.inputs['Roughness'].default_value = 0.2
bsdf.inputs['Metallic'].default_value = 0.7
desk.data.materials.append(mat_desk)
```

2. **Create Neon Accent Strips**
Add cyan, magenta, and yellow neon tubes with emission:
- Tool: blender_create_object
- Type: Cylinder (for neon tubing)
- Dimensions: 0.05m diameter, 1.8m length
- Locations: 
  - Cyan strip: (-1.2, 0, 2.5), emissive cyan (0, 1.0, 1.0)
  - Magenta strip: (0, -0.8, 2.5), emissive magenta (1.0, 0, 1.0)
  - Yellow strip: (1.2, 0, 2.5), emissive yellow (1.0, 1.0, 0)
- Emission Strength: 3.0 watts per square meter

3. **Create Neon Materials**
Build emissive materials for glowing tubes:
```python
import bpy
colors = {
    'Cyan': (0, 1.0, 1.0),
    'Magenta': (1.0, 0, 1.0),
    'Yellow': (1.0, 1.0, 0)
}

for color_name, rgb_value in colors.items():
    mat = bpy.data.materials.new(name=f'Neon_{color_name}')
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    nodes.clear()
    principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    principled.inputs['Base Color'].default_value = (*rgb_value, 1.0)
    principled.inputs['Emission'].default_value = (*rgb_value, 1.0)
    principled.inputs['Emission Strength'].default_value = 3.0
    principled.inputs['Roughness'].default_value = 0.0
    
    output = nodes.new(type='ShaderNodeOutputMaterial')
    links.new(principled.outputs['BSDF'], output.inputs['Surface'])
```

4. **Add Monitor/Screen Element**
Create glowing screen surface:
- Tool: blender_create_object
- Type: Plane
- Dimensions: 0.8m × 0.6m
- Location: (0, 0.5, 1.5)
- Material: Self-emissive dark cyan (0.1, 0.3, 0.4) with emission strength 1.5

5. **Add Volumetric Fog Effect**
Create atmospheric haze for light scattering:
```python
import bpy
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.world.use_nodes = True

# Enable volumetric rendering
scene.cycles.volume_step_size = 0.5

# Add world volume
world_output = scene.world.node_tree.nodes['World Output']
volume_scatter = scene.world.node_tree.nodes.new(type='ShaderNodeVolumeScatter')
volume_scatter.inputs['Density'].default_value = 0.1
volume_scatter.inputs['Anisotropy'].default_value = 0.5
scene.world.node_tree.links.new(volume_scatter.outputs['Volume'], world_output.inputs['Volume'])
```

6. **Configure HDRI Background**
Import environment texture for realistic backdrop:
- Tool: blender_add_hdri
- HDRI Type: Urban night scene (cyberpunk-themed)
- Rotation: 45° (adjustable)
- Strength: 1.2
- Resolution: 2048×1024 or higher
- Alternative: Use Polyhaven free HDRIs (parking_garage, industrial_room)

7. **Set Up Realistic Lighting**
Add key light for accent visibility:
```python
import bpy
bpy.ops.object.light_add(type='AREA', location=(1.5, -1.5, 3.0))
key_light = bpy.context.active_object
key_light.name = 'KeyLight_Cyan'
key_light.data.energy = 1500
key_light.data.size = 2.0
key_light.data.angle = 0.5

# Soft fill light from opposite direction
bpy.ops.object.light_add(type='AREA', location=(-2.0, 1.0, 2.0))
fill_light = bpy.context.active_object
fill_light.name = 'FillLight'
fill_light.data.energy = 400
fill_light.data.size = 1.5
```

8. **Enable Advanced Render Features**
Configure CYCLES for cinematic quality:
```python
import bpy
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 256
scene.cycles.max_bounces = 8
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.cycles.transmission_bounces = 4
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPTIX'
scene.eevee.use_bloom = True
scene.eevee.bloom_intensity = 0.8
scene.eevee.bloom_threshold = 0.8
scene.render.image_settings.file_format = 'OPEN_EXR_MULTILAYER'
```

9. **Verify Scene Composition**
Execute validation of light sources and materials:
```python
import bpy
neon_lights = [obj for obj in bpy.data.objects if 'Neon' in obj.name]
all_lights = [obj for obj in bpy.data.objects if obj.type == 'LIGHT']
print(f'Neon elements: {len(neon_lights)}')
print(f'Total lights: {len(all_lights)}')
for light in all_lights:
    print(f'{light.name}: {light.data.energy}W')
scene = bpy.context.scene
print(f'Render samples: {scene.cycles.samples}')
print(f'World volumetrics enabled: {scene.cycles.volume_step_size > 0}')
```

## Verification (GCS Constraints)

```json
{
  "constraints": [
    {
      "type": "object_count",
      "object_type": "LIGHT",
      "operator": ">=",
      "value": 2,
      "description": "Minimum 2 lights in scene"
    },
    {
      "type": "material_property",
      "materials": ["Neon_Cyan", "Neon_Magenta", "Neon_Yellow"],
      "property": "Emission Strength",
      "min_value": 2.5,
      "max_value": 5.0,
      "description": "Neon materials have appropriate emission strength"
    },
    {
      "type": "render_setting",
      "engine": "CYCLES",
      "denoiser": "OPTIX",
      "volume_rendering": true,
      "description": "Advanced rendering features enabled"
    },
    {
      "type": "object_property",
      "object": "Desk_Base",
      "property": "metallic",
      "expected_range": [0.6, 0.9],
      "description": "Desk has reflective metallic surface"
    },
    {
      "type": "world_setting",
      "hdri_enabled": true,
      "volumetric_scatter": true,
      "description": "HDRI and volumetric effects configured"
    },
    {
      "type": "light_color_validation",
      "light_names": ["KeyLight_Cyan"],
      "expected_color_temp": "daylight",
      "description": "Key light positioned for dramatic cyan accent"
    }
  ],
  "scene_characteristics": {
    "aesthetic": "cyberpunk",
    "lighting_style": "neon-accent",
    "render_quality": "cinematic",
    "atmosphere": "volumetric-fog"
  }
}
```

## Known Failure Modes
- **Neon Glow Too Subtle**: Increase emission strength from 3.0 to 4.5; enable bloom in viewport
- **Volumetric Rendering Slow**: Reduce volume_step_size to 0.25; use OPTIX denoiser for speed
- **HDRI Overexposed**: Lower world strength from 1.2 to 0.8; adjust background mix strength
- **Neon Color Bleeding**: Enable high caustics bounces (8 min); use path tracing with 512+ samples
- **Materials Look Flat**: Ensure roughness < 0.5 for metallic surfaces; add normal maps to desk
- **Performance Issues in Viewport**: Switch to EEVEE preview mode (Z key); render final in CYCLES
- **Black Spots in Render**: Increase light bounces from 8 to 12; reduce volume density to 0.05

