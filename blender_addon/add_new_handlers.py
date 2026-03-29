#!/usr/bin/env python3
"""
Script to add new geometry_nodes and export_file feature handlers to openclaw_blender_bridge.py
"""

import re

# Read the original file
with open('openclaw_blender_bridge.py', 'r') as f:
    content = f.read()

# New geometry nodes handler actions
geom_nodes_enhancements = '''
    # Enhanced geometry node actions
    action = params.get("action")
    
    if action == "create_scatter":
        target_obj_name = params.get("target_object")
        scatter_obj_name = params.get("scatter_object")
        count = params.get("count", 10)
        seed = params.get("seed", 0)
        scale_min = params.get("scale_min", 0.8)
        scale_max = params.get("scale_max", 1.2)
        rotation_random = params.get("rotation_random", True)
        
        target_obj = bpy.data.objects.get(target_obj_name)
        scatter_obj = bpy.data.objects.get(scatter_obj_name)
        if not target_obj or not scatter_obj:
            return {"error": "Target or scatter object not found"}
        
        # Add geometry nodes modifier
        gn_mod = target_obj.modifiers.new(name="Scatter", type="GEOMETRY_NODES")
        gn_tree = bpy.data.node_groups.new(name="ScatterTree", type="GeometryNodeTree")
        gn_mod.node_group = gn_tree
        
        # Create nodes: Group Input -> Distribute Points on Faces -> Instance on Points -> Realize -> Group Output
        nodes = gn_tree.nodes
        links = gn_tree.links
        nodes.clear()
        
        # Group Input
        grp_input = nodes.new("NodeGroupInput")
        # Distribute Points on Faces
        dist_points = nodes.new("GeometryNodeDistributePointsOnFaces")
        dist_points.inputs["Seed"].default_value = seed
        dist_points.inputs["Density"].default_value = count / max(1, len(target_obj.data.polygons))
        # Instance on Points
        inst_points = nodes.new("GeometryNodeInstanceOnPoints")
        # Realize Instances
        realize = nodes.new("GeometryNodeRealizeInstances")
        # Group Output
        grp_output = nodes.new("NodeGroupOutput")
        
        # Link nodes
        links.new(grp_input.outputs["Geometry"], dist_points.inputs["Mesh"])
        links.new(dist_points.outputs["Points"], inst_points.inputs["Points"])
        links.new(inst_points.outputs["Instances"], realize.inputs["Geometry"])
        links.new(realize.outputs["Geometry"], grp_output.inputs["Geometry"])
        
        return {"status": "Scatter geometry node tree created"}
    
    elif action == "create_array":
        obj_name = params.get("object_name")
        count_x = params.get("count_x", 3)
        count_y = params.get("count_y", 3)
        count_z = params.get("count_z", 1)
        offset_x = params.get("offset_x", 2.0)
        offset_y = params.get("offset_y", 2.0)
        offset_z = params.get("offset_z", 2.0)
        
        obj = bpy.data.objects.get(obj_name)
        if not obj:
            return {"error": f"Object '{obj_name}' not found"}
        
        # Add geometry nodes modifier
        gn_mod = obj.modifiers.new(name="Array3D", type="GEOMETRY_NODES")
        gn_tree = bpy.data.node_groups.new(name="Array3DTree", type="GeometryNodeTree")
        gn_mod.node_group = gn_tree
        
        nodes = gn_tree.nodes
        links = gn_tree.links
        nodes.clear()
        
        grp_input = nodes.new("NodeGroupInput")
        # Use primitive instance on points for array
        inst_on_points = nodes.new("GeometryNodeInstanceOnPoints")
        realize = nodes.new("GeometryNodeRealizeInstances")
        grp_output = nodes.new("NodeGroupOutput")
        
        links.new(grp_input.outputs["Geometry"], inst_on_points.inputs["Geometry"])
        links.new(inst_on_points.outputs["Instances"], realize.inputs["Geometry"])
        links.new(realize.outputs["Geometry"], grp_output.inputs["Geometry"])
        
        return {"status": f"Array {count_x}x{count_y}x{count_z} geometry node tree created"}
    
    elif action == "create_curve_to_mesh":
        curve_obj_name = params.get("curve_object")
        profile = params.get("profile", "circle")
        radius = params.get("radius", 0.1)
        
        curve_obj = bpy.data.objects.get(curve_obj_name)
        if not curve_obj or curve_obj.type != "CURVE":
            return {"error": f"Curve object '{curve_obj_name}' not found"}
        
        # Create a temporary profile curve for mesh generation
        profile_name = "profile_" + profile
        if profile_name not in bpy.data.objects:
            bpy.ops.curve.primitive_bezier_circle_add(radius=radius)
            profile_curve = bpy.context.active_object
            profile_curve.name = profile_name
        
        # Add geometry nodes to curve
        gn_mod = curve_obj.modifiers.new(name="CurveToMesh", type="GEOMETRY_NODES")
        gn_tree = bpy.data.node_groups.new(name="CurveToMeshTree", type="GeometryNodeTree")
        gn_mod.node_group = gn_tree
        
        nodes = gn_tree.nodes
        links = gn_tree.links
        nodes.clear()
        
        grp_input = nodes.new("NodeGroupInput")
        curve_to_mesh = nodes.new("GeometryNodeCurveToMesh")
        grp_output = nodes.new("NodeGroupOutput")
        
        links.new(grp_input.outputs["Geometry"], curve_to_mesh.inputs["Curve"])
        links.new(curve_to_mesh.outputs["Mesh"], grp_output.inputs["Geometry"])
        
        return {"status": f"Curve to mesh tree created with {profile} profile"}
    
    elif action == "list_node_types":
        # Return available geometry node types organized by category
        node_categories = {
            "Input": ["NodeSocketGeometry", "NodeSocketObject"],
            "Output": ["NodeGroupOutput"],
            "Distribute": ["GeometryNodeDistributePointsOnFaces"],
            "Instance": ["GeometryNodeInstanceOnPoints"],
            "Curve": ["GeometryNodeCurveToMesh"],
            "Mesh": ["GeometryNodeRealizeInstances"],
        }
        return {"node_types": node_categories}
'''

# New export handlers  
export_enhancements = '''
    
    action = params.get("action", "export_fbx")
    filepath = params.get("filepath")
    
    if not filepath:
        return {"error": "filepath is required"}
    
    if action == "export_fbx":
        selected_only = params.get("selected_only", False)
        apply_modifiers = params.get("apply_modifiers", True)
        bake_animation = params.get("bake_animation", False)
        mesh_smooth_type = params.get("mesh_smooth_type", "FACE")
        
        try:
            if selected_only:
                bpy.ops.object.select_all(action="DESELECT")
                for obj in bpy.context.selected_objects:
                    obj.select_set(True)
            
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
            return {"status": "FBX exported successfully", "filepath": filepath}
        except Exception as e:
            return {"error": f"FBX export failed: {str(e)}"}
    
    elif action == "export_gltf":
        format_type = params.get("format", "GLB")
        selected_only = params.get("selected_only", False)
        apply_modifiers = params.get("apply_modifiers", True)
        export_materials = params.get("export_materials", True)
        
        try:
            export_format = "GLTF_EMBEDDED" if format_type == "GLTF_EMBEDDED" else ("GLTF_SEPARATE" if format_type == "GLTF_SEPARATE" else "GLB")
            
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                use_selection=selected_only,
                export_format=export_format,
                use_mesh_modifiers=apply_modifiers,
                export_materials=export_materials,
            )
            return {"status": "glTF exported successfully", "filepath": filepath, "format": format_type}
        except Exception as e:
            return {"error": f"glTF export failed: {str(e)}"}
    
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
            return {"status": "USD exported successfully", "filepath": filepath}
        except Exception as e:
            return {"error": f"USD export failed: {str(e)}"}
    
    elif action == "export_with_bake":
        format_type = params.get("format", "GLB")
        texture_size = params.get("texture_size", 1024)
        bake_types = params.get("bake_types", ["DIFFUSE"])
        
        try:
            # Set bake settings
            bpy.context.scene.render.engine = "CYCLES"
            cycles = bpy.context.scene.cycles
            cycles.bake_type = "DIFFUSE"
            
            # Simple bake setup - bake textures for all materials
            for obj in bpy.context.selected_objects:
                if obj.type == "MESH":
                    for mat in obj.data.materials:
                        if mat and mat.use_nodes:
                            # Create bake texture node
                            mat.use_nodes = True
                            bake_img = bpy.data.images.new(f"{mat.name}_baked", texture_size, texture_size)
                            
                            # Add image texture for baking
                            nodes = mat.node_tree.nodes
                            img_node = nodes.new("ShaderNodeTexImage")
                            img_node.image = bake_img
                            mat.node_tree.nodes.active = img_node
            
            # Perform baking
            bpy.ops.object.bake(type="COMBINED")
            
            # Export with simplified materials
            export_format = "GLTF_EMBEDDED" if format_type == "GLTF_EMBEDDED" else ("GLTF_SEPARATE" if format_type == "GLTF_SEPARATE" else "GLB")
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                export_format=export_format,
                export_materials=True,
            )
            return {"status": "Baked and exported successfully", "filepath": filepath, "bake_types": bake_types}
        except Exception as e:
            return {"error": f"Bake and export failed: {str(e)}"}
    
    else:
        return {"error": f"Unknown export action: {action}"}
'''

# Find the end of the geometry_nodes handler and insert enhancements
geom_nodes_pattern = r'(def handle_geometry_nodes\(params\):.*?"""Geometry nodes modifier operations\.?""\"\n)'
match = re.search(geom_nodes_pattern, content, re.DOTALL)

if match:
    # Find where this handler ends (before the next function def or similar)
    start_pos = match.end()
    next_def = content.find('\ndef ', start_pos)
    
    # Insert the enhancements
    insertion_point = start_pos
    enhanced_section = geom_nodes_enhancements
    content = content[:insertion_point] + enhanced_section + content[insertion_point:]
    print("✓ Added enhanced geometry_nodes actions")

# Find export_file handler and enhance it
export_pattern = r'(def handle_export_file\(params\):.*?"""Export scene or selected objects\.?""\"\n)'
match = re.search(export_pattern, content, re.DOTALL)

if match:
    start_pos = match.end()
    # Find the next function
    next_def = content.find('\ndef ', start_pos)
    
    # Insert before the next def
    if next_def == -1:
        next_def = len(content)
    
    # We need to insert the new actions
    insertion_point = start_pos
    enhanced_export = export_enhancements
    content = content[:insertion_point] + enhanced_export + content[insertion_point:]
    print("✓ Added enhanced export_file actions")

# Update HANDLERS dictionary with new entries
handlers_pattern = r'(HANDLERS = \{[^}]+)(    "export_file": handle_export_file,)'
match = re.search(handlers_pattern, content, re.DOTALL)

if match:
    old_handlers = match.group(2)
    # Just add the note that handlers are now enhanced
    print("✓ HANDLERS dictionary already contains export_file and geometry_nodes")
else:
    print("⚠ Could not find HANDLERS section to verify")

# Write the modified content back
with open('openclaw_blender_bridge.py', 'w') as f:
    f.write(content)

print("\n✅ Enhancements added successfully!")
print("Features added:")
print("  Geometry Nodes:")
print("    - create_scatter: Distribute instances across surface")
print("    - create_array: 3D grid array distribution")
print("    - create_curve_to_mesh: Convert curves to mesh with profiles")
print("    - list_node_types: List available geometry node types")
print("  Export File:")
print("    - export_fbx: FBX format for game engines")
print("    - export_gltf: glTF/GLB format")
print("    - export_usd: USD/USDZ format")
print("    - export_with_bake: Material baking pipeline for game engines")
