import re

with open("blender_addon/openclaw_blender_bridge.py", "r") as f:
    content = f.read()

new_handlers = """
def handle_product_material(params):
    import bpy
    obj_name = params.get("object_name")
    if not obj_name:
        return {"error": "object_name is required"}
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return {"error": f"Object {obj_name} not found"}
        
    mat_name = params.get("material_name", "ProductMaterial")
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
        
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return {"error": "Material does not have Principled BSDF"}
        
    if "color" in params:
        bsdf.inputs['Base Color'].default_value = params["color"]
    if "roughness" in params:
        bsdf.inputs['Roughness'].default_value = params["roughness"]
    if "metallic" in params:
        bsdf.inputs['Metallic'].default_value = params["metallic"]
    if "transmission" in params:
        if 'Transmission Weight' in bsdf.inputs: # 4.x
            bsdf.inputs['Transmission Weight'].default_value = params["transmission"]
        elif 'Transmission' in bsdf.inputs: # 3.x
            bsdf.inputs['Transmission'].default_value = params["transmission"]
    if "ior" in params:
        bsdf.inputs['IOR'].default_value = params["ior"]
    if "coat_weight" in params:
        if 'Coat Weight' in bsdf.inputs:
            bsdf.inputs['Coat Weight'].default_value = params["coat_weight"]
    if "coat_roughness" in params:
        if 'Coat Roughness' in bsdf.inputs:
            bsdf.inputs['Coat Roughness'].default_value = params["coat_roughness"]
    if "subsurface" in params:
        if 'Subsurface Weight' in bsdf.inputs:
            bsdf.inputs['Subsurface Weight'].default_value = params["subsurface"]
        elif 'Subsurface' in bsdf.inputs:
            bsdf.inputs['Subsurface'].default_value = params["subsurface"]
            
    if params.get("add_imperfections"):
        tc = nodes.new('ShaderNodeTexCoord')
        tc.location = (-800, 0)
        fp = nodes.new('ShaderNodeTexNoise')
        fp.location = (-600, 100)
        fp.inputs['Scale'].default_value = 800
        fp.inputs['Detail'].default_value = 8
        fp_s = nodes.new('ShaderNodeMath')
        fp_s.location = (-400, 100)
        fp_s.operation = 'MULTIPLY'
        fp_s.inputs[1].default_value = 0.5
        fp_a = nodes.new('ShaderNodeMath')
        fp_a.location = (-200, 100)
        fp_a.operation = 'ADD'
        fp_a.inputs[1].default_value = params.get("roughness", 0.15)
        
        links = mat.node_tree.links
        links.new(tc.outputs['Object'], fp.inputs['Vector'])
        links.new(fp.outputs['Fac'], fp_s.inputs[0])
        links.new(fp_s.outputs['Value'], fp_a.inputs[0])
        links.new(fp_a.outputs['Value'], bsdf.inputs['Roughness'])
        
    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat
        
    return {"status": "ok", "material": mat.name, "object": obj.name}


def handle_product_render_setup(params):
    import bpy
    scene = bpy.context.scene
    
    engine = params.get("engine", "CYCLES").upper()
    if engine not in ["CYCLES", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"]:
        return {"error": f"Engine {engine} not allowed"}
    scene.render.engine = engine
    
    QUALITY_MAP = {
        "fast": {"samples": 128, "bounces": 6, "threshold": 0.1},
        "balanced": {"samples": 256, "bounces": 8, "threshold": 0.05},
        "premium": {"samples": 512, "bounces": 12, "threshold": 0.01},
    }

    RES_MAP = {
        "720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160),
        "square_1080": (1080, 1080), "vertical": (1080, 1920), "instagram": (1080, 1350),
    }
    
    q = QUALITY_MAP.get(params.get("quality", "balanced"), QUALITY_MAP["balanced"])
    w, h = RES_MAP.get(params.get("resolution", "1080p"), RES_MAP["1080p"])
    
    if engine == 'CYCLES':
        scene.cycles.device = 'GPU'
        scene.cycles.samples = q['samples']
        scene.cycles.preview_samples = 64
        scene.cycles.use_adaptive_sampling = True
        scene.cycles.adaptive_threshold = q['threshold']
        scene.cycles.use_denoising = True
        scene.cycles.denoiser = 'OPENIMAGEDENOISE'
        scene.cycles.max_bounces = q['bounces']
        scene.cycles.diffuse_bounces = 3
        scene.cycles.glossy_bounces = 4
        scene.cycles.transmission_bounces = 8
        scene.cycles.volume_bounces = 0
        scene.cycles.caustics_reflective = False
        scene.cycles.caustics_refractive = False
        scene.cycles.use_persistent_data = True
    
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = bool(params.get("transparent_bg", True))
    
    try:
        scene.view_settings.view_transform = 'AgX'
        scene.view_settings.look = 'AgX - Punchy'
    except:
        scene.view_settings.view_transform = 'Filmic'
        scene.view_settings.look = 'Medium High Contrast'
        
    scene.render.image_settings.file_format = params.get("output_format", "PNG")
    scene.render.image_settings.color_mode = 'RGBA'
    
    if "output_path" in params:
        scene.render.filepath = params["output_path"]
        
    # Compositor
    scene.use_nodes = True
    tree = scene.node_tree
    for n in list(tree.nodes):
        tree.nodes.remove(n)
        
    rl = tree.nodes.new('CompositorNodeRLayers')
    rl.location = (0, 0)
    comp = tree.nodes.new('CompositorNodeComposite')
    comp.location = (800, 0)
    last = rl.outputs['Image']
    x = 200
    
    if params.get("bloom", True):
        gl = tree.nodes.new('CompositorNodeGlare')
        gl.location = (x, 0)
        gl.glare_type = 'FOG_GLOW'
        gl.threshold = 0.8
        gl.quality = 'HIGH'
        gl.mix = -0.7
        gl.size = 6
        tree.links.new(last, gl.inputs[0])
        last = gl.outputs[0]
        x += 200
        
    if params.get("vignette", True):
        mask = tree.nodes.new('CompositorNodeEllipseMask')
        mask.location = (x, -200)
        mask.width = 0.85
        mask.height = 0.85
        blur = tree.nodes.new('CompositorNodeBlur')
        blur.location = (x+200, -200)
        blur.size_x = 200
        blur.size_y = 200
        blur.use_relative = True
        mix = tree.nodes.new('CompositorNodeMixRGB')
        mix.location = (x+400, 0)
        mix.blend_type = 'MULTIPLY'
        tree.links.new(mask.outputs[0], blur.inputs[0])
        tree.links.new(last, mix.inputs[1])
        tree.links.new(blur.outputs[0], mix.inputs[2])
        last = mix.outputs[0]
        
    tree.links.new(last, comp.inputs['Image'])
    
    return {"status": "ok"}
"""

content = content.replace("HANDLERS = {", new_handlers + "\nHANDLERS = {\n    \"product_material\": handle_product_material,\n    \"product_render_setup\": handle_product_render_setup,")

with open("blender_addon/openclaw_blender_bridge.py", "w") as f:
    f.write(content)
