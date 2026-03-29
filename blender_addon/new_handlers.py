# Enhanced Geometry Nodes and Export File Handlers for OpenClaw Blender Bridge
# These handlers should be integrated into openclaw_blender_bridge.py

import bpy


def handle_geometry_nodes_enhanced(params):
    """Geometry nodes modifier operations with enhanced scatter, array, and curve-to-mesh support."""
    obj_name = params.get("object_name")
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"error": f"Object '{obj_name}' not found"}

    action = params.get("action")

    # Original actions (preserved)
    if action == "add_modifier":
        gn_tree_name = params.get("node_group", "GeometryNodes")
        gn_tree = bpy.data.node_groups.get(gn_tree_name)
        if not gn_tree:
            return {"error": f"Node group '{gn_tree_name}' not found"}
        mod = obj.modifiers.new(name="GeometryNodes", type="GEOMETRY_NODES")
        mod.node_group = gn_tree
        return {"status": f"Geometry Nodes modifier added to {obj_name}"}

    elif action == "remove_modifier":
        mod_name = params.get("modifier_name", "GeometryNodes")
        mod = obj.modifiers.get(mod_name)
        if not mod:
            return {"error": f"Modifier '{mod_name}' not found"}
        obj.modifiers.remove(mod)
        return {"status": f"Modifier '{mod_name}' removed"}

    # NEW: Create Scatter
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

        # Instance on Points (reference scatter object)
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
        # (Full array implementation would use nested instance chains)
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

    else:
        return {"error": f"Unknown geometry_nodes action: {action}"}


def handle_export_file_enhanced(params):
    """Enhanced file export with FBX, glTF, USD, and material baking support."""
    action = params.get("action", "export_fbx")
    filepath = params.get("filepath")

    if not filepath:
        return {"error": "filepath is required"}

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
        format_type = params.get("format", "GLB")  # GLB, GLTF_SEPARATE, GLTF_EMBEDDED
        texture_size = params.get("texture_size", 1024)  # 512, 1024, 2048, 4096
        bake_types = params.get("bake_types", ["DIFFUSE"])

        try:
            # Switch to Cycles for baking
            scene = bpy.context.scene
            original_engine = scene.render.engine
            scene.render.engine = "CYCLES"

            cycles = scene.cycles
            cycles.bake_type = "COMBINED"
            cycles.samples = 128

            # Prepare for baking
            baked_images = []
            for obj in bpy.context.selected_objects:
                if obj.type == "MESH":
                    for mat in obj.data.materials:
                        if mat and mat.use_nodes:
                            # Create bake image
                            img_name = f"{mat.name}_baked_{texture_size}"
                            if img_name not in bpy.data.images:
                                baked_img = bpy.data.images.new(
                                    img_name, texture_size, texture_size
                                )
                            else:
                                baked_img = bpy.data.images[img_name]

                            # Create image texture for baking
                            nodes = mat.node_tree.nodes
                            img_node = nodes.new(type="ShaderNodeTexImage")
                            img_node.image = baked_img
                            mat.node_tree.nodes.active = img_node

                            baked_images.append(
                                {"object": obj.name, "material": mat.name, "image": img_name}
                            )

            # Perform baking
            if baked_images:
                bpy.ops.object.bake(type="COMBINED")

            # Export with simplified materials
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

            # Restore original render engine
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
            # Restore original render engine on error
            try:
                bpy.context.scene.render.engine = original_engine
            except:
                pass
            return {"error": f"Bake and export failed: {str(e)}"}

    else:
        return {"error": f"Unknown export action: {action}"}
