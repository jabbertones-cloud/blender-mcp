"""One owned compositor graph, compatible with Blender 4.5 LTS and 5.0+."""
import bpy
try:
    from .compositor_effects import add_glare, add_vignette
except ImportError:
    from compositor_effects import add_glare, add_vignette


def configure_product_compositor(scene, bloom=True, vignette=True):
    modern = hasattr(scene, "compositing_node_group")
    previous = scene.compositing_node_group if modern else None
    if modern:
        tree = bpy.data.node_groups.new("OpenClaw_Product_Compositor", "CompositorNodeTree")
        scene.compositing_node_group = tree
        output = tree.nodes.new("NodeGroupOutput")
        tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    else:
        scene.use_nodes = True
        tree = scene.node_tree
        tree.nodes.clear()
        output = tree.nodes.new("CompositorNodeComposite")
    if hasattr(scene.render, "use_compositing"):
        scene.render.use_compositing = True
    image = tree.nodes.new("CompositorNodeRLayers").outputs["Image"]
    if bloom:
        image = add_glare(tree, image, modern)
    if vignette:
        image = add_vignette(tree, image, modern)
    tree.links.new(image, output.inputs["Image"])
    if (modern and previous and previous.name.startswith("OpenClaw_Product_Compositor")
            and not previous.users):
        bpy.data.node_groups.remove(previous)
    return {"status": "ok", "compositor": tree.name, "bloom": bloom, "vignette": vignette}
