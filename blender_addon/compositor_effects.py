"""Blender-native compositing effect helpers for 4.5 LTS and 5.x."""


def add_glare(tree, image, modern):
    glare = tree.nodes.new("CompositorNodeGlare")
    if modern:
        glare.inputs["Type"].default_value = "Fog Glow"
        glare.inputs["Threshold"].default_value = 0.8
    else:
        glare.glare_type = "FOG_GLOW"
        glare.threshold = 0.8
        glare.quality = "HIGH"
    tree.links.new(image, glare.inputs["Image"])
    return glare.outputs["Image"]


def add_vignette(tree, image, modern):
    mask = tree.nodes.new("CompositorNodeEllipseMask")
    blur = tree.nodes.new("CompositorNodeBlur")
    if modern:
        mask.inputs["Size"].default_value = (0.85, 0.85)
        blur.inputs["Size"].default_value = (100, 100)
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 0.3
        a, b, result = mix.inputs[6], mix.inputs[7], mix.outputs[2]
    else:
        mask.width = mask.height = 0.85
        blur.size_x = blur.size_y = 100
        mix = tree.nodes.new("CompositorNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 0.3
        a, b, result = mix.inputs[1], mix.inputs[2], mix.outputs[0]
    tree.links.new(mask.outputs[0], blur.inputs["Image"])
    tree.links.new(image, a)
    tree.links.new(blur.outputs["Image"], b)
    return result
