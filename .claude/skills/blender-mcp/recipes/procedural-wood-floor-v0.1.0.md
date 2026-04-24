---
id: procedural-wood-floor
version: 0.1.0
title: Procedural Wood Floor with Geometry Nodes
description: |
  Parametric wood floor generation using Geometry Nodes for dynamic
  plank variation, grain patterns, and wear simulation. Supports
  multiple wood species and finish types with real-time adjustment.
trigger_patterns:
  - "wood floor"
  - "procedural wood"
  - "geometry nodes floor"
  - "hardwood simulation"
tools_used:
  - blender_create_object
  - blender_modify_material
  - execute_python
  - blender_add_geometry_nodes
created_at: 2026-04-23
author: AutoSkill
tier: atomic
category: materials
dependencies: []
---

## When to Use
Use for architectural visualization, interior design presentations, and any scene requiring realistic wood flooring. Ideal for:
- Interior design renderings
- Architectural walkthroughs
- Real estate visualizations
- Product placement on natural surfaces
- Cost-effective alternative to hand-modeling planks

## Parameters
- **Floor Dimensions**: 10m × 8m (adjustable)
- **Plank Width**: 0.15m (adjustable 0.10-0.25m)
- **Plank Length**: 1.2m (adjustable 0.8-2.0m)
- **Grain Scale**: 0.5 (adjustable 0.3-0.8)
- **Wood Species**: Oak (can switch to Walnut, Maple, Ash)
- **Finish Type**: Matte (options: Matte, Satin, Gloss)

## Steps

1. **Create Base Floor Plane**
Create the foundation mesh for procedural modification:
```python
import bpy
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
floor = bpy.context.active_object
floor.name = 'WoodFloor_Base'
floor.scale = (10, 8, 1)
bpy.ops.object.transform_apply(scale=True)
```

2. **Subdivide Floor Mesh**
Add geometry density for detailed plank variation:
- Tool: blender_modify_mesh
- Operation: Subdivision Surface
- Levels Viewport: 2
- Levels Render: 3
- Alternative: Use Remesh modifier with octree depth 7

3. **Add Geometry Nodes Modifier**
Apply procedural plank generation logic:
```python
import bpy
floor = bpy.context.active_object
nodes_mod = floor.modifiers.new(name='PlankGeneration', type='NODES')
nodes_tree = bpy.data.node_groups.new(name='WoodPlankNodes', type='GeometryNodeTree')
nodes_mod.node_group = nodes_tree

# Create node group structure
group_in = nodes_tree.nodes.new(type='NodeGroupInput')
group_out = nodes_tree.nodes.new(type='NodeGroupOutput')

# Add input sockets
nodes_tree.inputs.new('NodeSocketFloat', 'Plank Width')
nodes_tree.inputs.new('NodeSocketFloat', 'Plank Length')
nodes_tree.inputs.new('NodeSocketFloat', 'Grain Scale')
nodes_tree.inputs.new('NodeSocketInt', 'Random Seed')

# Set default values
nodes_tree.inputs['Plank Width'].default_value = 0.15
nodes_tree.inputs['Plank Length'].default_value = 1.2
nodes_tree.inputs['Grain Scale'].default_value = 0.5
nodes_tree.inputs['Random Seed'].default_value = 42
```

4. **Create Wood Material**
Build physically-based wood material with procedural textures:
```python
import bpy
mat = bpy.data.materials.new(name='WoodFloor_Oak')
mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Clear default nodes
nodes.clear()

# Create shader nodes
tex_noise = nodes.new(type='ShaderNodeTexNoise')
tex_noise.inputs['Scale'].default_value = 15.0
tex_noise.inputs['Detail'].default_value = 5.0

color_ramp = nodes.new(type='ShaderNodeValRamp')
# Oak wood base color
principled = nodes.new(type='ShaderNodeBsdfPrincipled')
principled.inputs['Base Color'].default_value = (0.4, 0.3, 0.15, 1.0)
principled.inputs['Roughness'].default_value = 0.3
principled.inputs['Metallic'].default_value = 0.0

output = nodes.new(type='ShaderNodeOutputMaterial')

# Connect nodes
links.new(tex_noise.outputs['Fac'], color_ramp.inputs['Fac'])
links.new(principled.outputs['BSDF'], output.inputs['Surface'])
```

5. **Add Wear and Variation Layers**
Simulate natural floor aging and usage patterns:
```python
import bpy
floor = bpy.context.active_object
# Add second material for worn areas
wear_mat = bpy.data.materials.new(name='WoodFloor_Worn')
wear_mat.use_nodes = True
pbsdf = wear_mat.node_tree.nodes['Principled BSDF']
pbsdf.inputs['Base Color'].default_value = (0.25, 0.2, 0.1, 1.0)
pbsdf.inputs['Roughness'].default_value = 0.6

# Add vertex paint layer for wear masking
bpy.ops.paint.vertex_paint_toggle()
```

6. **Configure UV Mapping**
Set up unwrapping for consistent wood grain alignment:
```python
import bpy
floor = bpy.context.active_object
bpy.context.view_layer.objects.active = floor
floor.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.unwrap(method='ANGLE_BASED', margin_copied=0.2)
bpy.ops.object.mode_set(mode='OBJECT')
```

7. **Render and Verify**
Execute final verification of material and geometry:
```python
import bpy
floor = bpy.context.active_object
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.samples = 256
bpy.context.scene.render.image_settings.file_format = 'PNG'
print(f'Floor dimensions: {floor.dimensions}')
print(f'Materials assigned: {len(floor.data.materials)}')
print(f'Modifiers: {[m.name for m in floor.modifiers]}')
```

## Verification (GCS Constraints)

```json
{
  "constraints": [
    {
      "type": "object_property",
      "object": "WoodFloor_Base",
      "property": "type",
      "expected_value": "MESH",
      "description": "Floor is a mesh object"
    },
    {
      "type": "modifier_count",
      "object": "WoodFloor_Base",
      "operator": ">=",
      "value": 1,
      "description": "At least one geometry modifier present"
    },
    {
      "type": "material_assigned",
      "object": "WoodFloor_Base",
      "material_name": "WoodFloor_Oak",
      "description": "Oak material assigned to floor"
    },
    {
      "type": "uv_unwrap_verification",
      "object": "WoodFloor_Base",
      "has_uv_map": true,
      "uv_name": "UVMap",
      "description": "UV map present for texture coordinate mapping"
    },
    {
      "type": "material_property",
      "material": "WoodFloor_Oak",
      "property": "use_nodes",
      "expected_value": true,
      "description": "Material uses node-based shading"
    },
    {
      "type": "render_compatibility",
      "engine": "CYCLES",
      "min_samples": 128,
      "description": "Render engine configured for quality output"
    }
  ],
  "wood_properties": {
    "species": "Oak",
    "grain_scale": 0.5,
    "plank_width_m": 0.15,
    "plank_length_m": 1.2,
    "finish": "Matte",
    "roughness": 0.3
  }
}
```

## Known Failure Modes
- **Grain Alignment Issues**: Ensure UV unwrap uses ANGLE_BASED method; adjust seam placement
- **Stretching on Edges**: Increase UV margin to 0.3; check for overlapping UV islands
- **Unrealistic Color Variation**: Adjust noise texture scale from 15.0 to 25.0 for finer grain
- **Poor Wear Simulation**: Use vertex paint with layer weight modifier for localized wear patterns
- **Geometry Nodes Not Evaluating**: Verify node tree has connected input/output group nodes
- **Material Preview Different from Render**: Enable viewport shading to Material Preview mode (Z key, then Material Preview)
- **Performance Degradation**: Reduce viewport subdivision levels to 1; keep render at 3

