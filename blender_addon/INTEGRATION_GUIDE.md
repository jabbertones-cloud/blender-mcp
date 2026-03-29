# OpenClaw Blender Bridge - Enhanced Handlers Integration Guide

## Overview

This guide describes how to integrate the enhanced **Geometry Nodes** and **Export File** features into the main `openclaw_blender_bridge.py` addon.

Two new handler files have been created:
- `new_handlers.py` - Contains the complete implementations of enhanced handlers
- `INTEGRATION_GUIDE.md` - This file

## Feature 1: Enhanced Geometry Nodes Handler

### Location in openclaw_blender_bridge.py
The `handle_geometry_nodes(params)` function is defined around **line 1809** and is already registered in the HANDLERS dict.

### Enhancements to Add

Add the following new actions to the existing `handle_geometry_nodes()` function:

#### Action: `create_scatter`
Distributes instances of a scatter object across a target object's surface using geometry nodes.

**Parameters:**
- `target_object` (str) - Name of the ground/surface object
- `scatter_object` (str) - Name of the object to scatter
- `count` (int) - Number of instances (default: 10)
- `seed` (int) - Random seed for distribution (default: 0)
- `scale_min` (float) - Minimum random scale (default: 0.8)
- `scale_max` (float) - Maximum random scale (default: 1.2)
- `rotation_random` (bool) - Randomize rotation (default: True)

**Node Tree:**
```
Group Input → Distribute Points on Faces → Instance on Points → Realize Instances → Group Output
```

**Returns:**
```json
{
  "status": "Scatter geometry node tree created",
  "modifier": "Scatter",
  "node_group": "ScatterTree",
  "count": 10,
  "seed": 0
}
```

---

#### Action: `create_array`
Creates a 3D grid array distribution using geometry nodes.

**Parameters:**
- `object_name` (str) - Object to apply array to
- `count_x` (int) - Number of copies in X axis (default: 3)
- `count_y` (int) - Number of copies in Y axis (default: 3)
- `count_z` (int) - Number of copies in Z axis (default: 1)
- `offset_x` (float) - Spacing in X (default: 2.0)
- `offset_y` (float) - Spacing in Y (default: 2.0)
- `offset_z` (float) - Spacing in Z (default: 2.0)

**Node Tree:**
```
Group Input → Instance on Points → Realize Instances → Group Output
```

**Returns:**
```json
{
  "status": "Array 3x3x1 geometry node tree created",
  "modifier": "Array3D",
  "grid": [3, 3, 1],
  "offset": [2.0, 2.0, 2.0]
}
```

---

#### Action: `create_curve_to_mesh`
Converts a curve to a mesh with a specified profile shape.

**Parameters:**
- `object_name` (str) - The curve object
- `curve_object` (str) - Name of the curve object
- `profile` (str) - Profile shape: "circle", "square", "custom" (default: "circle")
- `radius` (float) - Profile radius/size (default: 0.1)

**Node Tree:**
```
Group Input → Curve to Mesh → Group Output
```

**Returns:**
```json
{
  "status": "Curve to mesh tree created with circle profile",
  "modifier": "CurveToMesh",
  "profile": "circle",
  "radius": 0.1
}
```

---

#### Action: `list_node_types`
Returns all available geometry node types organized by category.

**Parameters:** None

**Returns:**
```json
{
  "available_node_types": {
    "Input": ["NodeGroupInput", "GeometryNodeInputPosition"],
    "Output": ["NodeGroupOutput"],
    "Distribute": ["GeometryNodeDistributePointsOnFaces"],
    "Instance": ["GeometryNodeInstanceOnPoints"],
    "Curve": ["GeometryNodeCurveToMesh"],
    "Mesh": ["GeometryNodeRealizeInstances"],
    "Material": ["GeometryNodeMaterialSelection"],
    "Deform": ["GeometryNodeDeform"]
  }
}
```

---

## Feature 2: Enhanced Export File Handler

### Location in openclaw_blender_bridge.py
The `handle_export_file(params)` function is defined around **line 530** and is already registered in the HANDLERS dict.

### Enhancements to Add

Add the following new actions to the existing `handle_export_file()` function:

#### Action: `export_fbx`
Exports the scene or selected objects to FBX format (optimized for game engines like Unity/Unreal).

**Parameters:**
- `filepath` (str) - Path to save FBX file (required)
- `selected_only` (bool) - Export only selected objects (default: False)
- `apply_modifiers` (bool) - Apply modifiers before export (default: True)
- `bake_animation` (bool) - Bake animation to keyframes (default: False)
- `mesh_smooth_type` (str) - Smoothing: "FACE", "EDGE", or "OFF" (default: "FACE")

**Blender Operation:**
```python
bpy.ops.export_scene.fbx(
    filepath=filepath,
    use_selection=selected_only,
    apply_scalings=True,
    object_types={'MESH', 'ARMATURE', 'EMPTY'},
    use_mesh_modifiers=apply_modifiers,
    mesh_smooth_type=mesh_smooth_type,
    use_anim=bake_animation,
    bake_anim=bake_animation,
)
```

**Returns:**
```json
{
  "status": "FBX exported successfully",
  "filepath": "/path/to/file.fbx",
  "format": "FBX"
}
```

---

#### Action: `export_gltf`
Exports to glTF format (GLB, GLTF_SEPARATE, or GLTF_EMBEDDED).

**Parameters:**
- `filepath` (str) - Path to save file (required)
- `format` (str) - Format type: "GLB", "GLTF_SEPARATE", "GLTF_EMBEDDED" (default: "GLB")
- `selected_only` (bool) - Export only selected objects (default: False)
- `apply_modifiers` (bool) - Apply modifiers before export (default: True)
- `export_materials` (bool) - Include materials in export (default: True)

**Blender Operation:**
```python
bpy.ops.export_scene.gltf(
    filepath=filepath,
    use_selection=selected_only,
    export_format=export_format,  # GLB | GLTF_SEPARATE | GLTF_EMBEDDED
    use_mesh_modifiers=apply_modifiers,
    export_materials=export_materials,
)
```

**Returns:**
```json
{
  "status": "glTF exported successfully",
  "filepath": "/path/to/file.glb",
  "format": "GLB"
}
```

---

#### Action: `export_usd`
Exports to USD/USDZ format.

**Parameters:**
- `filepath` (str) - Path to save file (required)
- `selected_only` (bool) - Export only selected objects (default: False)
- `export_materials` (bool) - Include materials in export (default: True)
- `export_animation` (bool) - Include animation (default: False)

**Blender Operation:**
```python
bpy.ops.wm.usd_export(
    filepath=filepath,
    selected_objects_only=selected_only,
    export_materials=export_materials,
    export_animation=export_animation,
)
```

**Returns:**
```json
{
  "status": "USD exported successfully",
  "filepath": "/path/to/file.usdz",
  "format": "USD"
}
```

---

#### Action: `export_with_bake`
Advanced pipeline: bakes all materials to texture maps, then exports with simplified materials.

**Parameters:**
- `filepath` (str) - Path to save file (required)
- `format` (str) - Export format: "GLB", "GLTF_SEPARATE", "GLTF_EMBEDDED" (default: "GLB")
- `texture_size` (int) - Bake texture resolution: 512, 1024, 2048, 4096 (default: 1024)
- `bake_types` (list) - What to bake: ["DIFFUSE", "ROUGHNESS", "NORMAL", "METALLIC", "EMISSION"] (default: ["DIFFUSE"])

**Process:**
1. Switch render engine to Cycles
2. Set up bake textures for all materials
3. Create image texture nodes in each material for baking
4. Run `bpy.ops.object.bake(type="COMBINED")`
5. Export with glTF/GLB with baked materials
6. Restore original render engine

**Returns:**
```json
{
  "status": "Baked and exported successfully",
  "filepath": "/path/to/file.glb",
  "format": "GLB",
  "texture_size": 1024,
  "baked_maps": ["DIFFUSE"],
  "baked_images": [
    {
      "object": "Cube",
      "material": "Material",
      "image": "Material_baked_1024"
    }
  ]
}
```

---

## Integration Steps

### Step 1: Backup Original File
```bash
cp openclaw_blender_bridge.py openclaw_blender_bridge.py.backup
```

### Step 2: Find Handler Locations

**For Geometry Nodes (line ~1809):**
```python
def handle_geometry_nodes(params):
    """Geometry nodes modifier operations."""
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"error": f"Object '{obj_name}' not found"}
    
    action = params.get("action")
    
    # ... existing code ...
```

Add the new actions before the final `else:` clause that returns "Unknown geometry_nodes action".

**For Export File (line ~530):**
```python
def handle_export_file(params):
    """Export scene or selected objects."""
    filepath = params.get("filepath")
    if not filepath:
        return {"error": "filepath is required"}
    
    # ... existing code ...
```

Add the new actions before the final `else:` clause that returns "Unknown export format".

### Step 3: Add New Handler Code

Copy the implementation blocks from `new_handlers.py` into the respective functions, integrating the new action branches with the existing code structure.

### Step 4: Verify HANDLERS Dictionary

Confirm that both handlers are registered in the HANDLERS dictionary (around line 3722):

```python
HANDLERS = {
    "ping": handle_ping,
    "get_scene_info": handle_get_scene_info,
    # ... other handlers ...
    "geometry_nodes": handle_geometry_nodes,  # Should already exist
    "export_file": handle_export_file,        # Should already exist
    # ... other handlers ...
}
```

### Step 5: Test Integration

After integration, test each new action:

```bash
# Test scatter
python -c "
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('127.0.0.1', 9876))
cmd = json.dumps({
    'id': '1',
    'command': 'geometry_nodes',
    'params': {
        'object_name': 'Plane',
        'action': 'create_scatter',
        'target_object': 'Plane',
        'scatter_object': 'Sphere',
        'count': 20,
        'seed': 42
    }
})
s.sendall(cmd.encode())
print(s.recv(4096).decode())
s.close()
"
```

---

## Handler Pattern Reference

Both handlers follow the established pattern:

```python
def handle_something(params):
    \"\"\"Description.\"\"\"
    # Extract parameters
    param1 = params.get("param1")
    
    # Validate
    obj = bpy.data.objects.get(param1)
    if not obj:
        return {"error": "Object not found"}
    
    # Get action
    action = params.get("action")
    
    # Route to action
    if action == "do_something":
        # Implementation
        return {"status": "Success", "data": result}
    
    elif action == "do_other_thing":
        # Implementation
        return {"status": "Success", "data": result}
    
    else:
        return {"error": f"Unknown action: {action}"}
```

---

## Error Handling

All handlers catch exceptions and return error responses:

```python
try:
    bpy.ops.export_scene.fbx(filepath=filepath, ...)
    return {"status": "FBX exported successfully", "filepath": filepath}
except Exception as e:
    return {"error": f"FBX export failed: {str(e)}"}
```

---

## Testing Checklist

- [ ] **Scatter node**: Create scatter on plane with cube objects
- [ ] **Array node**: Create 3x3 array of objects
- [ ] **Curve to Mesh**: Convert bezier curve to mesh with circle profile
- [ ] **List node types**: Verify all categories are returned
- [ ] **Export FBX**: Export selected mesh with modifiers applied
- [ ] **Export glTF**: Export as GLB, GLTF_SEPARATE, GLTF_EMBEDDED
- [ ] **Export USD**: Export to USDZ format
- [ ] **Export with Bake**: Bake materials and export with textures

---

## API Examples

### Example 1: Scatter instances across a surface
```python
{
    "command": "geometry_nodes",
    "params": {
        "object_name": "Plane",
        "action": "create_scatter",
        "target_object": "Plane",
        "scatter_object": "Sphere",
        "count": 50,
        "seed": 123,
        "rotation_random": true
    }
}
```

### Example 2: Create 5x5 array
```python
{
    "command": "geometry_nodes",
    "params": {
        "object_name": "Cube",
        "action": "create_array",
        "count_x": 5,
        "count_y": 5,
        "count_z": 1,
        "offset_x": 3.0,
        "offset_y": 3.0,
        "offset_z": 2.0
    }
}
```

### Example 3: Export FBX for Unreal Engine
```python
{
    "command": "export_file",
    "params": {
        "filepath": "/path/to/model.fbx",
        "action": "export_fbx",
        "selected_only": false,
        "apply_modifiers": true,
        "mesh_smooth_type": "FACE"
    }
}
```

### Example 4: Bake and export to game engine
```python
{
    "command": "export_file",
    "params": {
        "filepath": "/path/to/model.glb",
        "action": "export_with_bake",
        "format": "GLB",
        "texture_size": 2048,
        "bake_types": ["DIFFUSE", "ROUGHNESS", "NORMAL", "METALLIC"]
    }
}
```

---

## Troubleshooting

### Node groups not available
Ensure Blender version supports geometry nodes (4.0+). Check for version-specific node name changes.

### Baking fails
- Ensure objects have UV maps
- Switch to Cycles engine (handles switching automatically)
- Check texture size constraints based on VRAM

### Export fails
- Verify filepath is writable
- Check file extension matches format
- Ensure objects have valid geometry

---

## Version Compatibility

- **Blender 3.6+**: All geometry node features
- **Blender 4.0+**: Full geometry nodes support
- **Blender 5.0+**: Some node names may differ (version helpers provided)

---

## References

- Blender Python API: https://docs.blender.org/api/current/
- Geometry Nodes: https://docs.blender.org/manual/en/latest/en/modeling/geometry_nodes/
- Export Formats: https://docs.blender.org/manual/en/latest/en/files/import_export/
