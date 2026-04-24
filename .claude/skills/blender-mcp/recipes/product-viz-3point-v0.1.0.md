---
id: product-viz-3point
version: 0.1.0
title: 3-Point Lighting for Product Visualization
description: |
  Professional 3-point lighting setup (key, fill, back lights) optimized for
  product photography. Creates natural shadows and highlights for e-commerce
  and catalog renderings.
trigger_patterns:
  - "product lighting"
  - "3-point light"
  - "key fill back light"
  - "product photo setup"
tools_used:
  - blender_create_light
  - blender_set_object_property
  - blender_modify_material
  - execute_python
created_at: 2026-04-23
author: AutoSkill
tier: atomic
category: lighting
dependencies: []
---

## When to Use
Use this recipe when setting up product photography scenes that require professional studio lighting. Optimal for:
- E-commerce product catalogs
- Product photography mockups
- Studio product visualization
- Any scene requiring balanced, shadow-controlled lighting

## Parameters
- **Product Location**: XYZ coordinates of product center (default: 0, 0, 0)
- **Key Light Intensity**: 2.0 (main illumination, adjustable 1.0-3.0)
- **Fill Light Intensity**: 0.8 (shadow softening, adjustable 0.5-1.5)
- **Back Light Intensity**: 1.2 (rim lighting, adjustable 0.8-2.0)
- **Render Engine**: CYCLES (for photorealistic output)

## Steps

1. **Initialize Scene and Camera**
Execute the following to set up the base environment:
```python
import bpy
bpy.ops.scene.new(type='NEW')
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 128
bpy.context.scene.world.use_nodes = True
world_bg = bpy.context.scene.world.node_tree.nodes['Background']
world_bg.inputs['Strength'].default_value = 1.5
```

2. **Create Key Light (Main)**
Create the primary light source positioned at 45° angle:
- Tool: blender_create_light
- Type: AREA
- Energy: 2000W
- Location: (3.5, 2.0, 2.5)
- Rotation: (45°, 30°, 0°)
- Size: 2.0m x 2.0m

3. **Create Fill Light (Shadow Softening)**
Position opposite to key light to reduce harsh shadows:
- Tool: blender_create_light
- Type: AREA
- Energy: 800W
- Location: (-2.5, -1.5, 1.5)
- Rotation: (60°, -45°, 0°)
- Size: 1.5m x 1.5m
- Color Temperature: 4500K (slightly warm)

4. **Create Back Light (Rim Light)**
Add separation between product and background:
- Tool: blender_create_light
- Type: SPOT
- Energy: 1200W
- Location: (0, -4.0, 1.8)
- Rotation: (45°, 0°, 0°)
- Beam Angle: 30°
- Color Temperature: 5500K (cool/neutral)

5. **Configure Render Settings**
Set up CYCLES engine for optimal product rendering:
```python
import bpy
scene = bpy.context.scene
scene.render.resolution_x = 1920
scene.render.resolution_y = 1440
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPTIX'
```

6. **Verify Lighting Balance**
Execute lighting verification to ensure proper ratios:
```python
import bpy
lights = [obj for obj in bpy.data.objects if obj.type == 'LIGHT']
total_energy = sum([light.data.energy for light in lights])
print(f"Total lighting energy: {total_energy}W")
for light in lights:
    ratio = (light.data.energy / total_energy) * 100
    print(f"{light.name}: {ratio:.1f}%")
```

## Verification (GCS Constraints)

```json
{
  "constraints": [
    {
      "type": "light_count",
      "operator": "==",
      "value": 3,
      "description": "Exactly 3 lights present"
    },
    {
      "type": "light_type_distribution",
      "objects": ["Key.001", "Fill.001"],
      "constraint": "type == 'AREA'",
      "description": "Key and fill lights must be area lights"
    },
    {
      "type": "light_energy_ratio",
      "key_light": "Key.001",
      "fill_light": "Fill.001",
      "min_ratio": 1.8,
      "max_ratio": 3.0,
      "description": "Key-to-fill ratio between 1.8:1 and 3.0:1"
    },
    {
      "type": "spatial_separation",
      "light_pair": ["Key.001", "Fill.001"],
      "min_distance": 4.5,
      "tolerance": 0.1,
      "description": "Key and fill lights separated by minimum 4.5m"
    },
    {
      "type": "render_settings",
      "engine": "CYCLES",
      "samples": 128,
      "denoiser": "OPTIX",
      "description": "Render engine configured for product quality"
    }
  ],
  "expected_outputs": {
    "image_format": "PNG",
    "resolution": "1920x1440",
    "color_depth": "RGBA"
  }
}
```

## Known Failure Modes
- **Overexposed Highlights**: Reduce key light energy to 1500W or enable clamp direct to 1.0
- **Lost Shadow Detail**: Increase fill light to 1000W and reduce key light by 10%
- **Blown Out Background**: Add world strength cap at 1.0 or use HDRI backdrop
- **Asymmetrical Lighting**: Verify light positions using `bpy.data.objects['Light'].location` coordinates
- **Poor Edge Separation**: Increase back light to 1500W and position 5.0m away from product
- **Flickering in Viewport**: Disable real-time viewport denoising, render will still use OptiX denoiser

