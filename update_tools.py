import re

with open("server/product_animation_tools.py", "r") as f:
    content = f.read()

# Replace _gen_material_code call with explicit parameters dict
old_mat = """        code = _gen_material_code(
            params.preset.value, params.object_name, params.material_name,
            params.color_override, params.roughness_override, params.add_imperfections
        )
        return format_result_fn(send_command_fn("execute_python", {"code": code}))"""
new_mat = """        d = MATERIAL_DEFS[params.preset.value].copy()
        d["object_name"] = params.object_name
        d["material_name"] = params.material_name or f"Product_{params.preset.value}"
        if params.color_override:
            d["color"] = params.color_override
        if params.roughness_override is not None:
            d["roughness"] = params.roughness_override
        d["add_imperfections"] = params.add_imperfections
        return format_result_fn(send_command_fn("product_material", d))"""

content = content.replace(old_mat, new_mat)

old_render = """        render_code = _gen_render_code(
            params.quality.value, params.resolution.value,
            params.transparent_bg, params.output_path, params.output_format
        )
        result1 = send_command_fn("execute_python", {"code": render_code})
        
        comp_code = _gen_compositor_code(params.bloom, params.vignette)
        result2 = send_command_fn("execute_python", {"code": comp_code})
        
        return format_result_fn({
            "status": "ok",
            "render": result1,
            "compositor": result2,
        })"""
new_render = """        args = {
            "quality": params.quality.value,
            "resolution": params.resolution.value,
            "transparent_bg": params.transparent_bg,
            "output_path": params.output_path,
            "output_format": params.output_format,
            "bloom": params.bloom,
            "vignette": params.vignette
        }
        return format_result_fn(send_command_fn("product_render_setup", args))"""

content = content.replace(old_render, new_render)

with open("server/product_animation_tools.py", "w") as f:
    f.write(content)
