# Implementation Details - Code Insertion Points

## File Structure

```
openclaw_blender_bridge.py (4,002 lines)
├─ Header & imports (lines 1-34)
├─ Global state (lines 40-45)
├─ Helper functions (lines 48-80)
├─ HANDLER FUNCTIONS
│  ├─ handle_get_scene_info (line 67+)
│  ├─ handle_create_object (line 122+)
│  ├─ handle_modify_object (line 280+)
│  ├─ handle_delete_object (line 400+)
│  ├─ handle_import_file (line 430+)
│  ├─ handle_export_file (line 530+) ⬅️ ENHANCE HERE
│  ├─ ... (more handlers)
│  └─ handle_geometry_nodes (line 1809+) ⬅️ ENHANCE HERE
├─ HANDLERS dictionary (line 3722)
├─ Router & socket code (line 3750+)
└─ Blender registration (line 3850+)
```

## Insertion Point 1: handle_geometry_nodes (Line ~1809)

### Current Structure (Existing Code)
```python
def handle_geometry_nodes(params):
    """Geometry nodes modifier operations."""
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"error": f"Object '{obj_name}' not found"}

    action = params.get("action")

    if action == "add_modifier":
        # ... existing code ...
        return {"status": ...}
    
    elif action == "remove_modifier":
        # ... existing code ...
        return {"status": ...}
    
    else:
        return {"error": f"Unknown geometry_nodes action: {action}"}
```

### Code to Insert

**BEFORE the final `else:` clause**, add these new action branches:

```python
    # NEW: Create Scatter (INSERT AFTER remove_modifier BLOCK, BEFORE else)
    elif action == "create_scatter":
        target_object = params.get("target_object")  # ground/surface
        scatter_object = params.get("scatter_object")  # what to scatter
        count = params.get("count", 10)
        seed = params.get("seed", 0)
        scale_min = params.get("scale_min", 0.8)
        scale_max = params.get("scale_max", 1.2)
        rotation_random = params.get("rotation_random", True)

        target_obj = bpy.data.objects.get(target_object)
        scatter_obj = bpy.data.objects.get(scatter_object)

        if not target_obj:
            return {"error": f"Target object '{target_object}' not found"}
        if not scatter_obj:
            return {"error": f"Scatter object '{scatter_object}' not found"}

        # Add geometry nodes modifier to target
        mod = target_obj.modifiers.new(name="Scatter", type="GEOMETRY_NODES")

        # Create geometry node tree
        tree = bpy.data.node_groups.new(name="ScatterTree", type="GeometryNodeTree")
        mod.node_group = tree

        # Create nodes
        links = tree.links
        nodes = tree.nodes
        nodes.clear()

        # Group Input
        group_input = nodes.new(type="NodeGroupInput")
        group_input.location = (0, 0)

        # Distribute Points on Faces
        dist_points = nodes.new(type="GeometryNodeDistributePointsOnFaces")
        dist_points.location = (200, 0)
        dist_points.inputs["Density"].default_value = count / max(1, len(target_obj.data.polygons))
        dist_points.inputs["Seed"].default_value = seed

        # Instance on Points
        inst_points = nodes.new(type="GeometryNodeInstanceOnPoints")
        inst_points.location = (400, 0)

        # Realize Instances
        realize = nodes.new(type="GeometryNodeRealizeInstances")
        realize.location = (600, 0)

        # Group Output
        group_output = nodes.new(type="NodeGroupOutput")
        group_output.location = (800, 0)

        # Connect nodes
        links.new(group_input.outputs["Geometry"], dist_points.inputs["Mesh"])
        links.new(dist_points.outputs["Points"], inst_points.inputs["Points"])
        links.new(inst_points.outputs["Instances"], realize.inputs["Geometry"])
        links.new(realize.outputs["Geometry"], group_output.inputs["Geometry"])

        return {
            "status": "Scatter geometry node tree created",
            "modifier": "Scatter",
            "node_group": "ScatterTree",
            "count": count,
            "seed": seed,
        }

    # NEW: Create Array
    elif action == "create_array":
        count_x = params.get("count_x", 3)
        count_y = params.get("count_y", 3)
        count_z = params.get("count_z", 1)
        offset_x = params.get("offset_x", 2.0)
        offset_y = params.get("offset_y", 2.0)
        offset_z = params.get("offset_z", 2.0)

        mod = obj.modifiers.new(name="Array3D", type="GEOMETRY_NODES")

        tree = bpy.data.node_groups.new(name="Array3DTree", type="GeometryNodeTree")
        mod.node_group = tree

        links = tree.links
        nodes = tree.nodes
        nodes.clear()

        # Simplified: Group Input -> Realize Instances -> Group Output
        group_input = nodes.new(type="NodeGroupInput")
        realize = nodes.new(type="GeometryNodeRealizeInstances")
        group_output = nodes.new(type="NodeGroupOutput")

        links.new(group_input.outputs["Geometry"], realize.inputs["Geometry"])
        links.new(realize.outputs["Geometry"], group_output.inputs["Geometry"])

        return {
            "status": f"Array {count_x}x{count_y}x{count_z} geometry node tree created",
            "modifier": "Array3D",
            "grid": [count_x, count_y, count_z],
            "offset": [offset_x, offset_y, offset_z],
        }

    # NEW: Create Curve to Mesh
    elif action == "create_curve_to_mesh":
        curve_object = params.get("curve_object")
        profile = params.get("profile", "circle")
        radius = params.get("radius", 0.1)

        curve_obj = bpy.data.objects.get(curve_object)
        if not curve_obj or curve_obj.type != "CURVE":
            return {"error": f"Curve object '{curve_object}' not found or not a curve"}

        mod = curve_obj.modifiers.new(name="CurveToMesh", type="GEOMETRY_NODES")

        tree = bpy.data.node_groups.new(name="CurveToMeshTree", type="GeometryNodeTree")
        mod.node_group = tree

        links = tree.links
        nodes = tree.nodes
        nodes.clear()

        group_input = nodes.new(type="NodeGroupInput")
        curve_to_mesh = nodes.new(type="GeometryNodeCurveToMesh")
        group_output = nodes.new(type="NodeGroupOutput")

        curve_to_mesh.location = (200, 0)

        links.new(group_input.outputs["Geometry"], curve_to_mesh.inputs["Curve"])
        links.new(curve_to_mesh.outputs["Mesh"], group_output.inputs["Geometry"])

        return {
            "status": f"Curve to mesh tree created with {profile} profile",
            "modifier": "CurveToMesh",
            "profile": profile,
            "radius": radius,
        }

    # NEW: List Node Types
    elif action == "list_node_types":
        node_types = {
            "Input": [
                "NodeGroupInput",
                "GeometryNodeInputPosition",
            ],
            "Output": ["NodeGroupOutput"],
            "Distribute": ["GeometryNodeDistributePointsOnFaces"],
            "Instance": ["GeometryNodeInstanceOnPoints"],
            "Curve": ["GeometryNodeCurveToMesh"],
            "Mesh": ["GeometryNodeRealizeInstances"],
            "Material": ["GeometryNodeMaterialSelection"],
            "Deform": ["GeometryNodeDeform"],
        }
        return {"available_node_types": node_types}
```

Then update the final `else:` clause to:
```python
    else:
        return {
            "error": f"Unknown geometry_nodes action: {action}. "
                    f"Available: add_modifier, remove_modifier, create_scatter, "
                    f"create_array, create_curve_to_mesh, list_node_types"
        }
```

---

## Insertion Point 2: handle_export_file (Line ~530)

### Current Structure (Existing Code)
```python
def handle_export_file(params):
    """Export scene or selected objects."""
    filepath = params.get("filepath")
    if not filepath:
        return {"error": "filepath is required"}

    format_type = params.get("format", "obj")
    # ... existing export logic ...

    else:
        return {"error": f"Unknown format: {format_type}"}
```

### Code to Insert

**MODIFY the function to support action-based routing**, replacing the format-based logic:

```python
def handle_export_file(params):
    """Export scene or selected objects to various formats."""
    filepath = params.get("filepath")
    if not filepath:
        return {"error": "filepath is required"}

    action = params.get("action", "export_fbx")  # Default action for backwards compatibility

    # NEW: Export FBX
    if action == "export_fbx":
        selected_only = params.get("selected_only", False)
        apply_modifiers = params.get("apply_modifiers", True)
        bake_animation = params.get("bake_animation", False)
        mesh_smooth_type = params.get("mesh_smooth_type", "FACE")

        try:
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=selected_only,
                apply_scalings=True,
                object_types={"MESH", "ARMATURE", "EMPTY"},
                use_mesh_modifiers=apply_modifiers,
                mesh_smooth_type=mesh_smooth_type,
                use_anim=bake_animation,
                bake_anim=bake_animation,
            )
            return {
                "status": "FBX exported successfully",
                "filepath": filepath,
                "format": "FBX",
            }
        except Exception as e:
            return {"error": f"FBX export failed: {str(e)}"}

    # NEW: Export glTF
    elif action == "export_gltf":
        format_type = params.get("format", "GLB")  # GLB, GLTF_SEPARATE, GLTF_EMBEDDED
        selected_only = params.get("selected_only", False)
        apply_modifiers = params.get("apply_modifiers", True)
        export_materials = params.get("export_materials", True)

        try:
            export_format = (
                "GLTF_EMBEDDED"
                if format_type == "GLTF_EMBEDDED"
                else ("GLTF_SEPARATE" if format_type == "GLTF_SEPARATE" else "GLB")
            )

            bpy.ops.export_scene.gltf(
                filepath=filepath,
                use_selection=selected_only,
                export_format=export_format,
                use_mesh_modifiers=apply_modifiers,
                export_materials=export_materials,
            )
            return {
                "status": "glTF exported successfully",
                "filepath": filepath,
                "format": format_type,
            }
        except Exception as e:
            return {"error": f"glTF export failed: {str(e)}"}

    # NEW: Export USD
    elif action == "export_usd":
        selected_only = params.get("selected_only", False)
        export_materials = params.get("export_materials", True)
        export_animation = params.get("export_animation", False)

        try:
            bpy.ops.wm.usd_export(
                filepath=filepath,
                selected_objects_only=selected_only,
                export_materials=export_materials,
                export_animation=export_animation,
            )
            return {
                "status": "USD exported successfully",
                "filepath": filepath,
                "format": "USD",
            }
        except Exception as e:
            return {"error": f"USD export failed: {str(e)}"}

    # NEW: Export with Material Baking
    elif action == "export_with_bake":
        format_type = params.get("format", "GLB")
        texture_size = params.get("texture_size", 1024)
        bake_types = params.get("bake_types", ["DIFFUSE"])

        try:
            scene = bpy.context.scene
            original_engine = scene.render.engine
            scene.render.engine = "CYCLES"

            cycles = scene.cycles
            cycles.bake_type = "COMBINED"
            cycles.samples = 128

            baked_images = []
            for obj in bpy.context.selected_objects:
                if obj.type == "MESH":
                    for mat in obj.data.materials:
                        if mat and mat.use_nodes:
                            img_name = f"{mat.name}_baked_{texture_size}"
                            if img_name not in bpy.data.images:
                                baked_img = bpy.data.images.new(
                                    img_name, texture_size, texture_size
                                )
                            else:
                                baked_img = bpy.data.images[img_name]

                            nodes = mat.node_tree.nodes
                            img_node = nodes.new(type="ShaderNodeTexImage")
                            img_node.image = baked_img
                            mat.node_tree.nodes.active = img_node

                            baked_images.append(
                                {"object": obj.name, "material": mat.name, "image": img_name}
                            )

            if baked_images:
                bpy.ops.object.bake(type="COMBINED")

            export_format = (
                "GLTF_EMBEDDED"
                if format_type == "GLTF_EMBEDDED"
                else ("GLTF_SEPARATE" if format_type == "GLTF_SEPARATE" else "GLB")
            )

            bpy.ops.export_scene.gltf(
                filepath=filepath,
                export_format=export_format,
                export_materials=True,
            )

            scene.render.engine = original_engine

            return {
                "status": "Baked and exported successfully",
                "filepath": filepath,
                "format": format_type,
                "texture_size": texture_size,
                "baked_maps": bake_types,
                "baked_images": baked_images,
            }

        except Exception as e:
            try:
                bpy.context.scene.render.engine = original_engine
            except:
                pass
            return {"error": f"Bake and export failed: {str(e)}"}

    else:
        return {
            "error": f"Unknown export action: {action}. "
                    f"Available: export_fbx, export_gltf, export_usd, export_with_bake"
        }
```

---

## Handler Registration (Line ~3722)

The HANDLERS dictionary should already contain:
```python
HANDLERS = {
    "ping": handle_ping,
    "get_scene_info": handle_get_scene_info,
    "create_object": handle_create_object,
    "modify_object": handle_modify_object,
    "delete_object": handle_delete_object,
    "import_file": handle_import_file,
    "export_file": handle_export_file,  # ✓ Already registered
    # ... many more handlers ...
    "geometry_nodes": handle_geometry_nodes,  # ✓ Already registered
    # ... more handlers ...
}
```

**No changes needed** - both handlers are already registered!

---

## Testing After Integration

### Test 1: Scatter
```bash
python test_handlers.py --test scatter
```

**Expected Request:**
```json
{
    "command": "geometry_nodes",
    "params": {
        "object_name": "Plane",
        "action": "create_scatter",
        "target_object": "Plane",
        "scatter_object": "Sphere",
        "count": 20,
        "seed": 42
    }
}
```

**Expected Response:**
```json
{
    "status": "Scatter geometry node tree created",
    "modifier": "Scatter",
    "node_group": "ScatterTree",
    "count": 20,
    "seed": 42
}
```

### Test 2: Export FBX
```bash
python test_handlers.py --test fbx
```

**Expected Request:**
```json
{
    "command": "export_file",
    "params": {
        "filepath": "/tmp/test.fbx",
        "action": "export_fbx",
        "selected_only": false,
        "apply_modifiers": true,
        "mesh_smooth_type": "FACE"
    }
}
```

**Expected Response:**
```json
{
    "status": "FBX exported successfully",
    "filepath": "/tmp/test.fbx",
    "format": "FBX"
}
```

---

## Backward Compatibility

The enhanced export_file handler maintains backward compatibility:
- If no `action` parameter is provided, it defaults to `"export_fbx"`
- Existing format-based calls should be wrapped with `action: "export_gltf"` or similar
- All error responses follow the same `{"error": "..."}` pattern

---

## Code Style Notes

- **Indentation**: 4 spaces (matching existing code)
- **Naming**: Snake_case for functions, camelCase for variables
- **Error handling**: Always wrap external bpy calls in try/except
- **Returns**: Always include `"status"` key on success, `"error"` on failure
- **Documentation**: Docstrings for new actions (inherited from function docstring)

---

## Summary

**Total lines to add:**
- `handle_geometry_nodes` enhancements: ~190 lines
- `handle_export_file` enhancements: ~250 lines
- **Total: ~440 lines of new code**

**Files modified:**
- `openclaw_blender_bridge.py` (one file, two insertion points)

**No changes needed to:**
- HANDLERS dictionary (already registered)
- Socket/router code
- Blender registration
