# Quick test: which compositor API does this Blender version use?
import bpy
s = bpy.context.scene
print(f"Blender version: {bpy.app.version}")
print(f"Has node_tree: {hasattr(s, 'node_tree')}")
print(f"Has compositing_node_group: {hasattr(s, 'compositing_node_group')}")
print(f"Has use_nodes: {hasattr(s, 'use_nodes')}")
print(f"Has use_compositing: {hasattr(s, 'use_compositing')}")

# Try the new API
if hasattr(s, 'compositing_node_group'):
    # Blender 5.0+
    # Need to create a compositor node group first
    if s.compositing_node_group is None:
        ng = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        s.compositing_node_group = ng
    comp_tree = s.compositing_node_group
    print(f"Using compositing_node_group: {comp_tree}")
    print(f"Nodes: {list(comp_tree.nodes)}")
elif hasattr(s, 'node_tree'):
    s.use_nodes = True
    comp_tree = s.node_tree
    print(f"Using node_tree: {comp_tree}")
