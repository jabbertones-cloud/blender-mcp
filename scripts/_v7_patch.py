# Patch the v7 script to fix Blender 5.x compositor API
import re

path = "/Users/tatsheen/claw-architect/openclaw-blender-mcp/scripts/perfume_v7_fast_quality.py"
with open(path, "r") as f:
    content = f.read()

# Replace the compositor section
old_section = """# ===== COMPOSITING DENOISE NODE (v7 NEW: post-process quality boost) =====
print("[13/14] Compositing denoise node (v7: post-process cleanup)...")
s.use_nodes = True
comp_tree = s.node_tree

# Clear default compositing nodes
for node in list(comp_tree.nodes):
    comp_tree.nodes.remove(node)"""

new_section = """# ===== COMPOSITING DENOISE NODE (v7 NEW: post-process quality boost) =====
print("[13/14] Compositing denoise node (v7: post-process cleanup)...")
# Blender 5.0+ API: scene.compositing_node_group replaces scene.node_tree
if hasattr(s, 'compositing_node_group'):
    # Blender 5.0+
    if s.compositing_node_group is None:
        ng = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        s.compositing_node_group = ng
    comp_tree = s.compositing_node_group
else:
    # Blender 4.x fallback
    s.use_nodes = True
    comp_tree = s.node_tree

# Clear default compositing nodes
for node in list(comp_tree.nodes):
    comp_tree.nodes.remove(node)"""

content = content.replace(old_section, new_section)

with open(path, "w") as f:
    f.write(content)

print("Patched successfully!")
