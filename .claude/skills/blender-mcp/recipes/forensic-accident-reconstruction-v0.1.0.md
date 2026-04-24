---
id: forensic-accident-reconstruction
version: 0.1.0
title: Accident Scene Reconstruction for Forensic Analysis
description: |
  Complete accident scene setup with vehicles, road infrastructure, and
  witness camera positions. Includes impact markers, damage simulation,
  and coordinate system alignment for forensic report generation.
trigger_patterns:
  - "accident reconstruction"
  - "forensic scene"
  - "vehicle collision"
  - "impact analysis"
tools_used:
  - blender_create_object
  - blender_import_model
  - blender_set_object_property
  - execute_python
  - blender_render
created_at: 2026-04-23
author: AutoSkill
tier: atomic
category: forensics
dependencies: []
---

## When to Use
Essential for forensic investigation presentations, insurance claim documentation, and legal proceedings requiring spatial reconstruction of accident scenes. Use when:
- Documenting vehicle collision angles and positions
- Establishing sightlines for witness positions
- Calculating impact velocities from deformation
- Creating court-admissible visualizations
- Measuring distances and trajectories

## Parameters
- **Road Width**: 7.5m (adjustable 6.0-9.0m)
- **Road Material**: Asphalt with lane markings
- **Accident Location**: Intersection (X: 0, Y: 0, Z: 0)
- **Coordinate System**: NAD83 UTM Zone 11
- **Impact Time**: 2026-04-23 14:32:45 UTC

## Steps

1. **Create Road Infrastructure**
Build the street environment with proper scale:
```python
import bpy
bpy.ops.mesh.primitive_plane_add(size=50, location=(0, 0, 0))
road = bpy.context.active_object
road.name = 'Road_Base'
road.scale = (25, 12.5, 1)
mat = bpy.data.materials.new(name='Asphalt')
mat.use_nodes = True
bsdf = mat.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (0.15, 0.15, 0.15, 1.0)
bsdf.inputs['Roughness'].default_value = 0.6
road.data.materials.append(mat)
```

2. **Add Road Markings**
Create yellow center line and white edge markings:
- Tool: blender_create_object
- Type: Plane (lane markings)
- Dimensions: 50m length × 0.15m width
- Color: Yellow (1.0, 0.95, 0.0) for center
- Offset: Y = -3.75m (center line position)
- Repeat at Y = 3.75m with white paint (1.0, 1.0, 1.0)

3. **Position Vehicle 1 (Sedan)**
Primary vehicle in collision:
- Tool: blender_import_model
- Model: Generic sedan (4.5m length, 1.8m width)
- Location: (2.1, -1.5, 0.5)
- Rotation: (0°, 0°, 15°) - heading north-northeast
- Scale: 1.0 (real-world scale)
- Damage State: Pre-impact (used for impact calculation)

4. **Position Vehicle 2 (SUV)**
Secondary vehicle in collision:
- Tool: blender_import_model
- Model: Generic SUV (4.8m length, 2.0m width)
- Location: (-1.8, 1.2, 0.5)
- Rotation: (0°, 0°, -160°) - heading southeast
- Scale: 1.0 (real-world scale)
- Damage State: Pre-impact

5. **Add Impact Markers and Measurements**
Create measurement reference objects:
```python
import bpy
# Impact point marker
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.15, location=(0.15, -0.25, 0.35))
impact_marker = bpy.context.active_object
impact_marker.name = 'Impact_Center'
impact_marker.display_type = 'SOLID'
# Add measurement annotation
bpy.ops.object.add(type='EMPTY', name='Distance_Marker_A', location=(2.1, -1.5, 1.5))
bpy.ops.object.add(type='EMPTY', name='Distance_Marker_B', location=(-1.8, 1.2, 1.5))
```

6. **Configure Witness Camera Positions**
Set up sightline verification cameras:
- Camera 1 (Street corner): Location (8.5, 5.0, 1.7), FOV 75°, direction to impact center
- Camera 2 (Traffic light): Location (-6.0, -3.0, 4.0), FOV 60°, looking down intersection
- Camera 3 (Store window): Location (0.5, -8.0, 2.5), FOV 90°, wide field of view

7. **Verify Scene Geometry**
Execute coordinate validation:
```python
import bpy
vehicles = [obj for obj in bpy.data.objects if 'Vehicle' in obj.name]
print(f"Scene coordinate origin: 0, 0, 0")
print(f"Vehicles in scene: {len(vehicles)}")
for v in vehicles:
    print(f"{v.name}: Location {v.location}, Rotation {v.rotation_euler}")
impact = bpy.data.objects['Impact_Center']
print(f"Impact point: {impact.location}")
```

## Verification (GCS Constraints)

```json
{
  "constraints": [
    {
      "type": "object_count",
      "objects": ["Road_Base", "Vehicle_Sedan", "Vehicle_SUV"],
      "operator": ">=",
      "value": 3,
      "description": "Minimum road and 2 vehicles present"
    },
    {
      "type": "spatial_separation",
      "object_a": "Vehicle_Sedan",
      "object_b": "Vehicle_SUV",
      "min_distance": 3.0,
      "max_distance": 5.0,
      "tolerance": 0.2,
      "description": "Vehicles positioned 3-5m apart"
    },
    {
      "type": "coordinate_alignment",
      "reference_point": "Impact_Center",
      "tolerance": 0.5,
      "description": "Impact center within 0.5m of calculated collision point"
    },
    {
      "type": "rotation_validation",
      "object": "Vehicle_Sedan",
      "expected_heading": 15,
      "tolerance": 5,
      "description": "Vehicle heading within 5 degrees of northeasterly direction"
    },
    {
      "type": "camera_count",
      "operator": ">=",
      "value": 3,
      "description": "Minimum 3 witness camera viewpoints"
    }
  ],
  "forensic_metadata": {
    "scene_scale": "1:1",
    "coordinate_system": "NAD83_UTM_11",
    "incident_time": "2026-04-23T14:32:45Z",
    "documentation_standard": "ASIS_SCI"
  }
}
```

## Known Failure Modes
- **Incorrect Vehicle Spacing**: Use distance constraint validator; adjust X/Y coordinates
- **Camera Sightline Obstruction**: Rotate witness cameras to maintain 2.0m height (eye level)
- **Scale Inconsistency**: Lock object scale to 1.0; use measuring tools to verify real-world dimensions
- **Missing Impact Documentation**: Ensure Impact_Center marker exists and is rendered in output
- **Coordinate System Mismatch**: Verify origin at (0, 0, 0) and all objects relative to intersection center
- **Lighting Reveals Accident Details Poorly**: Add 3-point lighting setup (see product-viz-3point recipe) for clear visibility

