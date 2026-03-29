"""V8 Exhibit Overlay System — Professional Forensic Annotation

Adds courtroom-standard exhibit labels, scale bars, disclaimers, and
metadata to every render via Blender's compositor system.

This runs AFTER scene setup but BEFORE rendering, injecting compositor
nodes that stamp professional forensic exhibit information onto each frame.
"""


def exhibit_compositor_code(
    case_number="2026-CV-DEMO",
    exhibit_ref="1-A",
    scene_title="T-Bone Intersection Collision",
    disclaimer="DEMONSTRATIVE AID — NOT DRAWN TO SCALE",
    preparer="OpenClaw Forensic Animation System",
    date="2026-03-25",
):
    """Generate Blender Python code to set up forensic exhibit compositor overlay."""
    return f"""
import bpy

scene = bpy.context.scene

# === CREATE OVERLAY TEXT AS RENDER-TIME STAMP ===
# We use the compositor + text strip approach: render text to an image,
# then composite it over the render output.

# First, ensure compositor is active
scene.use_nodes = True
tree = scene.node_tree

# Don't wipe existing nodes — preserve the render pipeline
# Just add our overlay nodes at the end of the chain

# Find the existing Composite node
comp_node = None
last_image_node = None
for node in tree.nodes:
    if node.type == 'COMPOSITE':
        comp_node = node
    if node.type == 'R_LAYERS':
        last_image_node = node

# Find whatever is currently feeding into Composite
existing_link = None
if comp_node:
    for link in tree.links:
        if link.to_node == comp_node and link.to_socket.name == 'Image':
            existing_link = link
            last_image_node = link.from_node
            last_socket = link.from_socket
            break

if not comp_node:
    comp_node = tree.nodes.new('CompositorNodeComposite')
    comp_node.location = (1400, 300)

# === EXHIBIT LABEL BAR (bottom of frame) ===
# Create a colored bar at the bottom with exhibit info
# We'll use a Mix node with a generated gradient mask

# Generate the exhibit text as metadata stamps on the image
# Using Text node approach via compositor

# -- Bottom bar mask --
box_mask = tree.nodes.new('CompositorNodeBoxMask')
box_mask.location = (600, -200)
box_mask.x = 0.5
box_mask.y = 0.04  # Bottom 8% of frame
box_mask.width = 1.0
box_mask.height = 0.08
box_mask.mask_type = 'BOX'

# Darken bar
bar_color = tree.nodes.new('CompositorNodeRGB')
bar_color.location = (600, -400)
bar_color.outputs[0].default_value = (0.05, 0.05, 0.08, 0.85)

# -- Top bar mask (thinner, for case number) --
top_mask = tree.nodes.new('CompositorNodeBoxMask')
top_mask.location = (600, 200)
top_mask.x = 0.5
top_mask.y = 0.975  # Top 5% of frame
top_mask.width = 1.0
top_mask.height = 0.05

top_color = tree.nodes.new('CompositorNodeRGB')
top_color.location = (600, 50)
top_color.outputs[0].default_value = (0.05, 0.05, 0.08, 0.75)

# Mix bottom bar over render
mix_bottom = tree.nodes.new('CompositorNodeMixRGB')
mix_bottom.location = (900, 0)
mix_bottom.blend_type = 'MIX'
if existing_link:
    tree.links.new(last_socket, mix_bottom.inputs[1])
elif last_image_node:
    tree.links.new(last_image_node.outputs['Image'], mix_bottom.inputs[1])
tree.links.new(box_mask.outputs[0], mix_bottom.inputs[0])
tree.links.new(bar_color.outputs[0], mix_bottom.inputs[2])

# Mix top bar over that
mix_top = tree.nodes.new('CompositorNodeMixRGB')
mix_top.location = (1100, 0)
mix_top.blend_type = 'MIX'
tree.links.new(mix_bottom.outputs[0], mix_top.inputs[1])
tree.links.new(top_mask.outputs[0], mix_top.inputs[0])
tree.links.new(top_color.outputs[0], mix_top.inputs[2])

# Remove old link to composite, add new one
if existing_link:
    tree.links.remove(existing_link)
tree.links.new(mix_top.outputs[0], comp_node.inputs['Image'])

# === ADD TEXT OBJECTS TO SCENE (rendered by camera) ===
# These are 3D text objects positioned in camera space

cam = scene.camera
if cam:
    # --- Bottom bar text: Exhibit ref + Scene title + Disclaimer ---
    font_curve = bpy.data.curves.new(name='ExhibitLabel', type='FONT')
    font_curve.body = 'Exhibit {exhibit_ref}  |  {scene_title}  |  {disclaimer}'
    font_curve.size = 0.018
    font_curve.align_x = 'CENTER'
    label_obj = bpy.data.objects.new('ExhibitLabel', font_curve)
    bpy.context.collection.objects.link(label_obj)

    # Position relative to camera
    label_obj.parent = cam
    label_obj.location = (0, 0, -0.18)  # In front of camera, at bottom
    label_obj.rotation_euler = (0, 0, 0)

    # White text material
    tmat = bpy.data.materials.new(name='ExhibitTextMat')
    tmat.use_nodes = True
    tmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1)
    tmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 3.0
    tmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.95, 0.95, 0.95, 1)
    font_curve.materials.append(tmat)

    # --- Top bar text: Case number + Date + Preparer ---
    top_curve = bpy.data.curves.new(name='CaseLabel', type='FONT')
    top_curve.body = 'Case: {case_number}  |  Prepared: {date}  |  {preparer}'
    top_curve.size = 0.012
    top_curve.align_x = 'CENTER'
    top_obj = bpy.data.objects.new('CaseLabel', top_curve)
    bpy.context.collection.objects.link(top_obj)
    top_obj.parent = cam
    top_obj.location = (0, 0, -0.135)

    tmat2 = bpy.data.materials.new(name='CaseTextMat')
    tmat2.use_nodes = True
    tmat2.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.7, 0.7, 0.75, 1)
    tmat2.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
    tmat2.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.7, 0.7, 0.75, 1)
    top_curve.materials.append(tmat2)

__result__ = 'Exhibit overlay configured: {exhibit_ref} | {scene_title}'
"""


def scale_bar_code(length_meters=10.0, position=(5, -8, 0.01)):
    """Generate code for a physical scale bar in the scene."""
    x, y, z = position
    return f"""
import bpy

# Scale bar: {length_meters}m physical length
# Create a thin box
bpy.ops.mesh.primitive_cube_add(size=1, location=({x}, {y}, {z}))
bar = bpy.context.active_object
bar.name = 'ScaleBar_{length_meters}m'
bar.scale = ({length_meters}, 0.15, 0.02)

# Alternating black/white segments via material
mat = bpy.data.materials.new(name='ScaleBarMat')
mat.use_nodes = True
tree = mat.node_tree
nodes = tree.nodes
links = tree.links
bsdf = nodes['Principled BSDF']

# Checker pattern for scale reference
checker = nodes.new('ShaderNodeTexChecker')
checker.location = (-300, 0)
checker.inputs['Scale'].default_value = {length_meters * 2}  # 1m segments
checker.inputs['Color1'].default_value = (0.95, 0.95, 0.95, 1)
checker.inputs['Color2'].default_value = (0.05, 0.05, 0.05, 1)
links.new(checker.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.9
bsdf.inputs['Emission Strength'].default_value = 0.5
links.new(checker.outputs['Color'], bsdf.inputs['Emission Color'])
bar.data.materials.append(mat)

# Label text
font_curve = bpy.data.curves.new(name='ScaleLabel', type='FONT')
font_curve.body = '{int(length_meters)}m'
font_curve.size = 0.4
font_curve.align_x = 'CENTER'
label = bpy.data.objects.new('ScaleLabel', font_curve)
bpy.context.collection.objects.link(label)
label.location = ({x}, {y - 0.5}, {z + 0.1})

lmat = bpy.data.materials.new(name='ScaleLabelMat')
lmat.use_nodes = True
lmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 1, 1, 1)
lmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
lmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 1, 1, 1)
font_curve.materials.append(lmat)

__result__ = 'Scale bar added: {length_meters}m'
"""


def compass_arrow_code(position=(12, -8, 0.01)):
    """Generate code for a north arrow indicator."""
    x, y, z = position
    return f"""
import bpy

# North arrow
bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=0.8, location=({x}, {y + 0.4}, {z}))
arrow = bpy.context.active_object
arrow.name = 'NorthArrow'
arrow.rotation_euler = (0, 0, 0)  # Points +Y = North

mat = bpy.data.materials.new(name='NorthArrowMat')
mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.1, 0.1, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.0
mat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (0.9, 0.1, 0.1, 1)
arrow.data.materials.append(mat)

# N label
font_curve = bpy.data.curves.new(name='NorthLabel', type='FONT')
font_curve.body = 'N'
font_curve.size = 0.5
font_curve.align_x = 'CENTER'
label = bpy.data.objects.new('NorthLabel', font_curve)
bpy.context.collection.objects.link(label)
label.location = ({x}, {y + 1.0}, {z})

lmat = bpy.data.materials.new(name='NorthLabelMat')
lmat.use_nodes = True
lmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 1, 1, 1)
lmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
lmat.node_tree.nodes['Principled BSDF'].inputs['Emission Color'].default_value = (1, 1, 1, 1)
font_curve.materials.append(lmat)

__result__ = 'North arrow added'
"""
