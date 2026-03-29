"""
Product Animation Tools — MCP Server Extension
================================================
Professional-grade product animation tools that extend the Blender MCP.

To integrate: import and call register_product_tools(mcp, send_command, format_result)
from the main blender_mcp_server.py
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ProductMaterialPreset(str, Enum):
    glossy_plastic = "glossy_plastic"
    matte_plastic = "matte_plastic"
    brushed_aluminum = "brushed_aluminum"
    polished_chrome = "polished_chrome"
    gold = "gold"
    rose_gold = "rose_gold"
    copper = "copper"
    clear_glass = "clear_glass"
    frosted_glass = "frosted_glass"
    tinted_glass = "tinted_glass"
    ceramic_glazed = "ceramic_glazed"
    rubber_matte = "rubber_matte"
    fabric_cotton = "fabric_cotton"
    leather = "leather"
    silk_satin = "silk_satin"
    white_product = "white_product"

class LightingRigPreset(str, Enum):
    product_studio = "product_studio"
    jewelry = "jewelry"
    cosmetics = "cosmetics"
    electronics = "electronics"
    automotive = "automotive"
    food_product = "food_product"

class CameraStyle(str, Enum):
    turntable = "turntable"
    hero_reveal = "hero_reveal"
    detail_orbit = "detail_orbit"

class RenderQuality(str, Enum):
    fast = "fast"
    balanced = "balanced"
    premium = "premium"

class ResolutionPreset(str, Enum):
    hd_720p = "720p"
    full_hd = "1080p"
    uhd_4k = "4k"
    square = "square_1080"
    vertical = "vertical"
    instagram = "instagram"


class ProductAnimationInput(BaseModel):
    """Full product animation recipe — sets up everything in one call."""
    object_name: str = Field(..., description="Name of the product object in the scene")
    material: Optional[ProductMaterialPreset] = Field(default=None, description="Material preset to apply (skip to keep existing)")
    lighting: LightingRigPreset = Field(default=LightingRigPreset.product_studio, description="Lighting rig preset")
    camera_style: CameraStyle = Field(default=CameraStyle.turntable, description="Camera animation style")
    frames: int = Field(default=240, ge=24, le=2400, description="Total animation frames (240=10sec @24fps)")
    camera_distance: float = Field(default=4.0, gt=0.5, description="Camera distance from product")
    camera_height: float = Field(default=1.2, description="Camera height above product center")
    focal_length: float = Field(default=50.0, ge=12, le=300, description="Camera focal length in mm")
    f_stop: float = Field(default=2.8, ge=0.5, le=32, description="Aperture f-stop for DOF")
    use_dof: bool = Field(default=True, description="Enable depth of field")
    quality: RenderQuality = Field(default=RenderQuality.balanced, description="Render quality preset")
    resolution: ResolutionPreset = Field(default=ResolutionPreset.full_hd, description="Output resolution")
    transparent_bg: bool = Field(default=True, description="Transparent background")
    bloom: bool = Field(default=True, description="Add bloom/glow post-processing")
    vignette: bool = Field(default=True, description="Add vignette post-processing")
    gradient_bg: bool = Field(default=False, description="Use gradient background instead of transparent")
    shadow_catcher: bool = Field(default=True, description="Add shadow catcher plane")
    output_path: Optional[str] = Field(default=None, description="Output directory for rendered frames")
    fps: int = Field(default=24, ge=12, le=120, description="Frames per second")
    auto_render: bool = Field(default=False, description="Start rendering immediately after setup")


class ProductMaterialInput(BaseModel):
    """Apply a professional product material to an object."""
    object_name: str = Field(..., description="Object to apply material to")
    preset: ProductMaterialPreset = Field(..., description="Material preset")
    material_name: Optional[str] = Field(default=None, description="Custom material name")
    color_override: Optional[List[float]] = Field(default=None, description="Override base color [R,G,B,A] 0-1")
    roughness_override: Optional[float] = Field(default=None, ge=0, le=1, description="Override roughness")
    add_imperfections: bool = Field(default=False, description="Add fingerprints/dust for photorealism")


class ProductLightingInput(BaseModel):
    """Set up professional product lighting."""
    preset: LightingRigPreset = Field(..., description="Lighting rig preset")
    shadow_catcher: bool = Field(default=True, description="Add shadow catcher plane")
    gradient_bg: bool = Field(default=False, description="Use gradient world background")
    gradient_top: Optional[List[float]] = Field(default=None, description="Gradient top color [R,G,B]")
    gradient_bottom: Optional[List[float]] = Field(default=None, description="Gradient bottom color [R,G,B]")
    hdri_path: Optional[str] = Field(default=None, description="Optional HDRI path (overrides preset world)")
    hdri_strength: float = Field(default=1.5, ge=0, description="HDRI/world strength")
    hdri_rotation: float = Field(default=0.0, description="HDRI rotation in degrees")


class ProductCameraInput(BaseModel):
    """Set up professional product camera animation."""
    style: CameraStyle = Field(..., description="Camera animation style")
    target_object: str = Field(..., description="Object to focus on")
    frames: int = Field(default=240, ge=24, description="Total animation frames")
    camera_distance: float = Field(default=4.0, gt=0.5, description="Camera distance")
    camera_height: float = Field(default=1.2, description="Camera height")
    focal_length: float = Field(default=50.0, ge=12, le=300, description="Focal length mm")
    f_stop: float = Field(default=2.8, ge=0.5, le=32, description="Aperture f-stop")
    use_dof: bool = Field(default=True, description="Enable DOF")
    fps: int = Field(default=24, ge=12, le=120, description="FPS")
    # Hero reveal specific
    start_distance: Optional[float] = Field(default=None, description="Hero reveal: start distance")
    end_distance: Optional[float] = Field(default=None, description="Hero reveal: end distance")
    start_focal: Optional[float] = Field(default=None, description="Hero reveal: starting focal length")
    end_focal: Optional[float] = Field(default=None, description="Hero reveal: ending focal length")
    # Detail orbit specific
    orbit_angle: Optional[float] = Field(default=None, description="Detail orbit: angle to sweep in degrees")


class ProductRenderInput(BaseModel):
    """Configure professional product render settings."""
    quality: RenderQuality = Field(default=RenderQuality.balanced, description="Quality preset")
    resolution: ResolutionPreset = Field(default=ResolutionPreset.full_hd, description="Resolution preset")
    transparent_bg: bool = Field(default=True, description="Transparent background")
    bloom: bool = Field(default=True, description="Bloom/glow post-processing")
    vignette: bool = Field(default=True, description="Vignette post-processing")
    output_path: Optional[str] = Field(default=None, description="Output path with #### for frame numbers")
    output_format: str = Field(default="PNG", description="Output format: PNG, JPEG, EXR")


class MultiShotInput(BaseModel):
    """Create a multi-shot product commercial sequence."""
    object_name: str = Field(..., description="Product object name")
    shots: List[Dict[str, Any]] = Field(..., description="List of shot configs: [{style, frames, focal_length, ...}]")
    material: Optional[ProductMaterialPreset] = Field(default=None)
    lighting: LightingRigPreset = Field(default=LightingRigPreset.product_studio)
    quality: RenderQuality = Field(default=RenderQuality.balanced)
    resolution: ResolutionPreset = Field(default=ResolutionPreset.full_hd)
    output_path: Optional[str] = Field(default=None)


class FCurveInput(BaseModel):
    """Fine-tune animation F-curves for professional easing."""
    object_name: str = Field(..., description="Object with animation")
    data_path: str = Field(default="location", description="Property path (location, rotation_euler, scale)")
    index: int = Field(default=-1, description="Channel index (-1=all, 0=X, 1=Y, 2=Z)")
    interpolation: str = Field(default="BEZIER", description="Interpolation: LINEAR, BEZIER, CONSTANT")
    easing: Optional[str] = Field(default=None, description="Easing: EASE_IN, EASE_OUT, EASE_IN_OUT, AUTO")
    handle_type: Optional[str] = Field(default=None, description="Handle type: AUTO, VECTOR, ALIGNED, FREE, AUTO_CLAMPED")


# ═══════════════════════════════════════════════════════════════════════════════
# BLENDER-SIDE PYTHON CODE GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

# Material preset definitions (Principled BSDF values)
MATERIAL_DEFS = {
    "glossy_plastic": {"color": [0.1,0.1,0.1,1], "metallic": 0, "roughness": 0.15, "coat_weight": 0.2, "coat_roughness": 0.05},
    "matte_plastic": {"color": [0.2,0.2,0.2,1], "metallic": 0, "roughness": 0.65},
    "brushed_aluminum": {"color": [0.92,0.92,0.92,1], "metallic": 1, "roughness": 0.35, "coat_weight": 0.2},
    "polished_chrome": {"color": [0.77,0.78,0.78,1], "metallic": 1, "roughness": 0.08, "coat_weight": 0.5, "coat_roughness": 0.02},
    "gold": {"color": [1.0,0.84,0.0,1], "metallic": 1, "roughness": 0.15, "coat_weight": 0.3},
    "rose_gold": {"color": [0.95,0.77,0.69,1], "metallic": 1, "roughness": 0.18, "coat_weight": 0.3},
    "copper": {"color": [0.96,0.63,0.48,1], "metallic": 1, "roughness": 0.2},
    "clear_glass": {"color": [1,1,1,1], "metallic": 0, "roughness": 0.02, "transmission": 1.0, "ior": 1.52},
    "frosted_glass": {"color": [0.95,0.97,1,1], "metallic": 0, "roughness": 0.25, "transmission": 1.0, "ior": 1.52},
    "tinted_glass": {"color": [0.3,0.6,0.4,1], "metallic": 0, "roughness": 0.02, "transmission": 1.0, "ior": 1.52},
    "ceramic_glazed": {"color": [0.92,0.88,0.80,1], "metallic": 0, "roughness": 0.45, "subsurface": 0.2, "coat_weight": 0.8, "coat_roughness": 0.1},
    "rubber_matte": {"color": [0.1,0.1,0.1,1], "metallic": 0, "roughness": 0.95},
    "fabric_cotton": {"color": [0.85,0.80,0.75,1], "metallic": 0, "roughness": 0.80, "subsurface": 0.08},
    "leather": {"color": [0.35,0.2,0.1,1], "metallic": 0, "roughness": 0.55, "subsurface": 0.05, "coat_weight": 0.15},
    "silk_satin": {"color": [0.85,0.75,0.8,1], "metallic": 0, "roughness": 0.35, "subsurface": 0.1},
    "white_product": {"color": [0.95,0.95,0.95,1], "metallic": 0, "roughness": 0.3, "coat_weight": 0.1},
}

# Lighting rig definitions
LIGHTING_DEFS = {
    "product_studio": {
        "lights": [
            {"name": "Key_Light", "type": "AREA", "loc": [2.5,0.5,1.8], "energy": 100, "size": 1.5, "color": [1.0,0.97,0.92]},
            {"name": "Fill_Light", "type": "AREA", "loc": [-2.0,1.2,0.8], "energy": 40, "size": 2.0, "color": [0.95,0.93,0.90]},
            {"name": "Rim_Light", "type": "AREA", "loc": [0.0,-3.0,2.5], "energy": 150, "size": 1.2, "color": [0.92,0.95,1.0]},
        ],
        "world": [0.05,0.05,0.06], "world_str": 0.3,
    },
    "jewelry": {
        "lights": [
            {"name": "Sparkle_Key", "type": "AREA", "loc": [1.5,0.8,2.5], "energy": 200, "size": 0.8, "color": [0.92,0.95,1.0]},
            {"name": "Fill_Warm", "type": "AREA", "loc": [-1.2,-0.5,1.0], "energy": 30, "size": 1.5, "color": [1.0,0.95,0.88]},
            {"name": "Rim_Cool", "type": "AREA", "loc": [-2.0,2.0,1.8], "energy": 100, "size": 1.0, "color": [0.88,0.92,1.0]},
        ],
        "world": [0.02,0.02,0.03], "world_str": 0.1,
    },
    "cosmetics": {
        "lights": [
            {"name": "Key_Beauty", "type": "AREA", "loc": [2.2,0.3,1.0], "energy": 85, "size": 1.8, "color": [1.0,0.97,0.93]},
            {"name": "Fill_Label", "type": "AREA", "loc": [-2.5,1.5,0.9], "energy": 50, "size": 2.5, "color": [1.0,0.96,0.90]},
            {"name": "Rim_Luxury", "type": "AREA", "loc": [0.2,-2.8,1.5], "energy": 110, "size": 1.0, "color": [0.95,0.97,1.0]},
        ],
        "world": [0.08,0.08,0.09], "world_str": 0.2,
    },
    "electronics": {
        "lights": [
            {"name": "Key_Screen", "type": "AREA", "loc": [2.5,0.5,1.8], "energy": 110, "size": 2.0, "color": [1.0,0.98,0.95]},
            {"name": "Top_Edge", "type": "AREA", "loc": [-1.0,-0.2,2.3], "energy": 70, "size": 1.5, "color": [0.95,0.97,1.0]},
            {"name": "Rim_Sep", "type": "AREA", "loc": [0.0,3.0,1.5], "energy": 130, "size": 1.2, "color": [0.92,0.95,1.0]},
        ],
        "world": [0.04,0.04,0.05], "world_str": 0.15,
    },
    "automotive": {
        "lights": [
            {"name": "Key_Paint", "type": "AREA", "loc": [2.0,-1.0,1.2], "energy": 120, "size": 2.5, "color": [1.0,0.98,0.95]},
            {"name": "Accent_Flake", "type": "AREA", "loc": [-3.5,0.0,2.0], "energy": 60, "size": 1.8, "color": [0.95,0.97,1.0]},
            {"name": "Rim_Define", "type": "AREA", "loc": [0.5,3.0,2.2], "energy": 140, "size": 1.5, "color": [0.90,0.94,1.0]},
        ],
        "world": [0.03,0.03,0.04], "world_str": 0.2,
    },
    "food_product": {
        "lights": [
            {"name": "Key_Warm", "type": "AREA", "loc": [2.0,0.0,1.5], "energy": 90, "size": 2.0, "color": [1.0,0.95,0.85]},
            {"name": "Fill_Soft", "type": "AREA", "loc": [-1.5,1.0,0.8], "energy": 45, "size": 2.5, "color": [1.0,0.97,0.90]},
            {"name": "Rim_Appetite", "type": "AREA", "loc": [0.0,-2.5,2.0], "energy": 80, "size": 1.5, "color": [1.0,0.93,0.80]},
        ],
        "world": [0.06,0.05,0.04], "world_str": 0.25,
    },
}

QUALITY_MAP = {
    "fast": {"samples": 128, "bounces": 6, "threshold": 0.1},
    "balanced": {"samples": 256, "bounces": 8, "threshold": 0.05},
    "premium": {"samples": 512, "bounces": 12, "threshold": 0.01},
}

RES_MAP = {
    "720p": (1280, 720), "1080p": (1920, 1080), "4k": (3840, 2160),
    "square_1080": (1080, 1080), "vertical": (1080, 1920), "instagram": (1080, 1350),
}


def _gen_material_code(preset_name: str, object_name: str, mat_name: str = None, color_override=None, roughness_override=None, add_imperfections=False):
    """Generate Python code for applying a material preset."""
    d = MATERIAL_DEFS[preset_name]
    mn = mat_name or f"Product_{preset_name}"
    c = color_override or d["color"]
    r = roughness_override if roughness_override is not None else d["roughness"]
    
    extras = []
    if d.get("coat_weight"):
        extras.append(f"bsdf.inputs['Coat Weight'].default_value = {d['coat_weight']}")
    if d.get("coat_roughness"):
        extras.append(f"bsdf.inputs['Coat Roughness'].default_value = {d['coat_roughness']}")
    if d.get("transmission"):
        extras.append(f"bsdf.inputs['Transmission Weight'].default_value = {d['transmission']}")
    if d.get("ior"):
        extras.append(f"bsdf.inputs['IOR'].default_value = {d['ior']}")
    if d.get("subsurface"):
        extras.append(f"bsdf.inputs['Subsurface Weight'].default_value = {d['subsurface']}")
    
    extras_code = "\n        ".join(extras)
    
    imperf_code = ""
    if add_imperfections:
        imperf_code = """
    # Imperfections: fingerprints + dust on roughness
    tc = tree.nodes.new('ShaderNodeTexCoord')
    tc.location = (-800, 0)
    fp = tree.nodes.new('ShaderNodeTexNoise')
    fp.location = (-600, 100)
    fp.inputs['Scale'].default_value = 800
    fp.inputs['Detail'].default_value = 8
    fp_s = tree.nodes.new('ShaderNodeMath')
    fp_s.location = (-400, 100)
    fp_s.operation = 'MULTIPLY'
    fp_s.inputs[1].default_value = 0.06
    fp_a = tree.nodes.new('ShaderNodeMath')
    fp_a.location = (-200, 100)
    fp_a.operation = 'ADD'
    fp_a.inputs[0].default_value = bsdf.inputs['Roughness'].default_value
    tree.links.new(tc.outputs['Object'], fp.inputs['Vector'])
    tree.links.new(fp.outputs['Fac'], fp_s.inputs[0])
    tree.links.new(fp_s.outputs[0], fp_a.inputs[1])
    tree.links.new(fp_a.outputs[0], bsdf.inputs['Roughness'])
"""
    
    return f"""
import bpy
obj = bpy.data.objects.get("{object_name}")
if not obj:
    __result__ = {{"error": "Object '{object_name}' not found"}}
else:
    mat = bpy.data.materials.new("{mn}")
    mat.use_nodes = True
    tree = mat.node_tree
    bsdf = tree.nodes.get("Principled BSDF")
    bsdf.inputs['Base Color'].default_value = ({c[0]}, {c[1]}, {c[2]}, {c[3] if len(c)>3 else 1.0})
    bsdf.inputs['Metallic'].default_value = {d['metallic']}
    bsdf.inputs['Roughness'].default_value = {r}
    {extras_code}
    {imperf_code}
    if obj.data and hasattr(obj.data, 'materials'):
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    __result__ = {{"status": "ok", "material": "{mn}", "preset": "{preset_name}"}}
"""


def _gen_lighting_code(preset_name: str, shadow_catcher: bool = True, gradient_bg: bool = False, 
                        grad_top=None, grad_bottom=None, hdri_path=None, hdri_strength=1.5, hdri_rotation=0):
    """Generate Python code for a lighting rig."""
    rig = LIGHTING_DEFS[preset_name]
    
    lights_code = ""
    for lt in rig["lights"]:
        lights_code += f"""
ld = bpy.data.lights.new(name="{lt['name']}", type='{lt['type']}')
ld.energy = {lt['energy']}
ld.color = ({lt['color'][0]}, {lt['color'][1]}, {lt['color'][2]})
if hasattr(ld, 'size'): ld.size = {lt['size']}
lo = bpy.data.objects.new(name="{lt['name']}", object_data=ld)
bpy.context.collection.objects.link(lo)
lo.location = ({lt['loc'][0]}, {lt['loc'][1]}, {lt['loc'][2]})
d = mathutils.Vector((0,0,0)) - mathutils.Vector(({lt['loc'][0]}, {lt['loc'][1]}, {lt['loc'][2]}))
lo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
"""
    
    wc = rig["world"]
    
    world_code = ""
    if hdri_path:
        world_code = f"""
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree
for n in list(tree.nodes): tree.nodes.remove(n)
tc = tree.nodes.new('ShaderNodeTexCoord')
tc.location = (-400, 0)
mp = tree.nodes.new('ShaderNodeMapping')
mp.location = (-200, 0)
mp.inputs['Rotation'].default_value[2] = {hdri_rotation * 3.14159 / 180.0}
env = tree.nodes.new('ShaderNodeTexEnvironment')
env.location = (0, 0)
env.image = bpy.data.images.load("{hdri_path}")
bg = tree.nodes.new('ShaderNodeBackground')
bg.location = (200, 0)
bg.inputs['Strength'].default_value = {hdri_strength}
out = tree.nodes.new('ShaderNodeOutputWorld')
out.location = (400, 0)
tree.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
tree.links.new(mp.outputs['Vector'], env.inputs['Vector'])
tree.links.new(env.outputs['Color'], bg.inputs['Color'])
tree.links.new(bg.outputs['Background'], out.inputs['Surface'])
"""
    elif gradient_bg:
        gt = grad_top or [0.88, 0.90, 0.92]
        gb = grad_bottom or [1.0, 1.0, 1.0]
        world_code = f"""
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
tree = world.node_tree
for n in list(tree.nodes): tree.nodes.remove(n)
tc = tree.nodes.new('ShaderNodeTexCoord')
tc.location = (-600, 0)
mp = tree.nodes.new('ShaderNodeMapping')
mp.location = (-400, 0)
gr = tree.nodes.new('ShaderNodeTexGradient')
gr.location = (-200, 0)
ramp = tree.nodes.new('ShaderNodeValToRGB')
ramp.location = (0, 0)
ramp.color_ramp.elements[0].color = ({gb[0]}, {gb[1]}, {gb[2]}, 1)
ramp.color_ramp.elements[1].color = ({gt[0]}, {gt[1]}, {gt[2]}, 1)
bg = tree.nodes.new('ShaderNodeBackground')
bg.location = (200, 0)
bg.inputs['Strength'].default_value = 1.0
out = tree.nodes.new('ShaderNodeOutputWorld')
out.location = (400, 0)
tree.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
tree.links.new(mp.outputs['Vector'], gr.inputs['Vector'])
tree.links.new(gr.outputs['Color'], ramp.inputs['Fac'])
tree.links.new(ramp.outputs['Color'], bg.inputs['Color'])
tree.links.new(bg.outputs['Background'], out.inputs['Surface'])
"""
    else:
        world_code = f"""
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
if bg:
    bg.inputs['Color'].default_value = ({wc[0]}, {wc[1]}, {wc[2]}, 1)
    bg.inputs['Strength'].default_value = {rig['world_str']}
"""
    
    catcher_code = ""
    if shadow_catcher:
        catcher_code = """
for o in list(bpy.data.objects):
    if o.name.startswith("Shadow_Catcher"):
        bpy.data.objects.remove(o, do_unlink=True)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.01))
sc = bpy.context.active_object
sc.name = "Shadow_Catcher"
sc.is_shadow_catcher = True
"""
    
    return f"""
import bpy, mathutils

# Remove existing lights
for o in list(bpy.data.objects):
    if o.type == 'LIGHT':
        bpy.data.objects.remove(o, do_unlink=True)

{lights_code}
{world_code}
{catcher_code}

__result__ = {{"status": "ok", "rig": "{preset_name}", "lights": {len(rig['lights'])}}}
"""


def _gen_camera_code(style, target, frames, distance, height, focal, fstop, use_dof, fps,
                      start_dist=None, end_dist=None, start_focal=None, end_focal=None, orbit_angle=None):
    """Generate Python code for camera animation."""
    
    if style == "turntable":
        return f"""
import bpy, math
scene = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name.startswith("Turntable_") or o.name == "Product_Camera":
        bpy.data.objects.remove(o, do_unlink=True)
target = bpy.data.objects.get("{target}")
if not target:
    __result__ = {{"error": "Object '{target}' not found"}}
else:
    tc = target.location.copy()
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=tc)
    orbit = bpy.context.active_object
    orbit.name = "Turntable_Orbit"
    cd = bpy.data.cameras.new("ProductCamData")
    cd.lens = {focal}
    cd.sensor_width = 36
    cd.dof.use_dof = {use_dof}
    cd.dof.focus_object = target
    cd.dof.aperture_fstop = {fstop}
    co = bpy.data.objects.new("Product_Camera", cd)
    bpy.context.collection.objects.link(co)
    co.location = (tc.x + {distance}, tc.y, tc.z + {height})
    co.parent = orbit
    tr = co.constraints.new('TRACK_TO')
    tr.target = target
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    scene.camera = co
    scene.frame_start = 1
    scene.frame_end = {frames}
    scene.render.fps = {fps}
    orbit.rotation_euler = (0, 0, 0)
    orbit.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    orbit.rotation_euler = (0, 0, math.radians(360))
    orbit.keyframe_insert(data_path="rotation_euler", index=2, frame={frames})
    if orbit.animation_data and orbit.animation_data.action:
        for fc in orbit.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'LINEAR'
    __result__ = {{"status": "ok", "style": "turntable", "frames": {frames}, "fps": {fps}}}
"""
    
    elif style == "hero_reveal":
        sd = start_dist or 8.0
        ed = end_dist or 3.5
        sf = start_focal or 35.0
        ef = end_focal or 85.0
        return f"""
import bpy, math
scene = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name.startswith("Hero_") or o.name == "Product_Camera":
        bpy.data.objects.remove(o, do_unlink=True)
target = bpy.data.objects.get("{target}")
if not target:
    __result__ = {{"error": "Object '{target}' not found"}}
else:
    tc = target.location.copy()
    cd = bpy.data.cameras.new("HeroCamData")
    cd.lens = {sf}
    cd.dof.use_dof = {use_dof}
    cd.dof.focus_object = target
    cd.dof.aperture_fstop = {fstop}
    co = bpy.data.objects.new("Product_Camera", cd)
    bpy.context.collection.objects.link(co)
    scene.camera = co
    tr = co.constraints.new('TRACK_TO')
    tr.target = target
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    scene.frame_start = 1
    scene.frame_end = {frames}
    scene.render.fps = {fps}
    co.location = (tc.x + {sd}, tc.y, tc.z + 0.5)
    co.keyframe_insert(data_path="location", frame=1)
    cd.lens = {sf}
    cd.keyframe_insert(data_path="lens", frame=1)
    co.location = (tc.x + {ed}, tc.y + 1, tc.z + {height})
    co.keyframe_insert(data_path="location", frame={frames})
    cd.lens = {ef}
    cd.keyframe_insert(data_path="lens", frame={frames})
    for obj in [co]:
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kf in fc.keyframe_points:
                    kf.interpolation = 'BEZIER'
                    kf.easing = 'EASE_OUT'
    if cd.animation_data and cd.animation_data.action:
        for fc in cd.animation_data.action.fcurves:
            for kf in fc.keyframe_points:
                kf.interpolation = 'BEZIER'
                kf.easing = 'EASE_OUT'
    __result__ = {{"status": "ok", "style": "hero_reveal", "frames": {frames}}}
"""
    
    elif style == "detail_orbit":
        oa = orbit_angle or 120.0
        ed = end_dist or 2.0
        return f"""
import bpy, math
scene = bpy.context.scene
for o in list(bpy.data.objects):
    if o.name.startswith("Detail_") or o.name == "Product_Camera":
        bpy.data.objects.remove(o, do_unlink=True)
target = bpy.data.objects.get("{target}")
if not target:
    __result__ = {{"error": "Object '{target}' not found"}}
else:
    tc = target.location.copy()
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=tc)
    orbit = bpy.context.active_object
    orbit.name = "Detail_Orbit"
    cd = bpy.data.cameras.new("DetailCamData")
    cd.lens = {focal}
    cd.dof.use_dof = {use_dof}
    cd.dof.focus_object = target
    cd.dof.aperture_fstop = {fstop}
    co = bpy.data.objects.new("Product_Camera", cd)
    bpy.context.collection.objects.link(co)
    co.parent = orbit
    scene.camera = co
    tr = co.constraints.new('TRACK_TO')
    tr.target = target
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    scene.frame_start = 1
    scene.frame_end = {frames}
    scene.render.fps = {fps}
    co.location = (tc.x + {distance}, tc.y, tc.z + {height})
    co.keyframe_insert(data_path="location", frame=1)
    orbit.rotation_euler = (0, 0, 0)
    orbit.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    co.location = (tc.x + {ed}, tc.y, tc.z + {height})
    co.keyframe_insert(data_path="location", frame={frames})
    orbit.rotation_euler = (0, 0, math.radians({oa}))
    orbit.keyframe_insert(data_path="rotation_euler", index=2, frame={frames})
    for obj in [co, orbit]:
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kf in fc.keyframe_points:
                    kf.interpolation = 'BEZIER'
                    kf.easing = 'EASE_IN_OUT'
    __result__ = {{"status": "ok", "style": "detail_orbit", "frames": {frames}, "orbit_angle": {oa}}}
"""
    return '__result__ = {"error": "Unknown camera style"}'


def _gen_render_code(quality, resolution, transparent, output_path, output_format):
    """Generate render configuration code."""
    q = QUALITY_MAP.get(quality, QUALITY_MAP["balanced"])
    w, h = RES_MAP.get(resolution, RES_MAP["1080p"])
    op = output_path or "/tmp/product_render/frame_####"
    
    return f"""
import bpy
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = {q['samples']}
scene.cycles.preview_samples = 64
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = {q['threshold']}
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = {q['bounces']}
scene.cycles.diffuse_bounces = 3
scene.cycles.glossy_bounces = 4
scene.cycles.transmission_bounces = 8
scene.cycles.volume_bounces = 0
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.cycles.use_persistent_data = True
scene.render.resolution_x = {w}
scene.render.resolution_y = {h}
scene.render.resolution_percentage = 100
scene.render.film_transparent = {transparent}
try:
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Punchy'
except:
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'
scene.render.image_settings.file_format = '{output_format}'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = "{op}"
__result__ = {{"status": "ok", "quality": "{quality}", "resolution": "{resolution}", "samples": {q['samples']}}}
"""


def _gen_compositor_code(bloom=True, vignette=True):
    """Generate compositor setup code."""
    return f"""
import bpy
scene = bpy.context.scene
scene.use_nodes = True
tree = scene.node_tree
for n in list(tree.nodes): tree.nodes.remove(n)

rl = tree.nodes.new('CompositorNodeRLayers')
rl.location = (0, 0)
comp = tree.nodes.new('CompositorNodeComposite')
comp.location = (800, 0)
last = rl.outputs['Image']
x = 200

if {bloom}:
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

if {vignette}:
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
    mix.inputs[0].default_value = 0.3
    tree.links.new(mask.outputs[0], blur.inputs[0])
    tree.links.new(last, mix.inputs[1])
    tree.links.new(blur.outputs[0], mix.inputs[2])
    last = mix.outputs[0]
    x += 600

tree.links.new(last, comp.inputs[0])
__result__ = {{"status": "ok", "bloom": {bloom}, "vignette": {vignette}}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRATION — Call this from blender_mcp_server.py
# ═══════════════════════════════════════════════════════════════════════════════

def register_product_tools(mcp_instance, send_command_fn, format_result_fn):
    """Register all product animation tools with the MCP server."""
    
    @mcp_instance.tool(
        name="blender_product_animation",
        annotations={"title": "Product Animation Recipe", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_product_animation(params: ProductAnimationInput) -> str:
        """Create a complete professional product animation in one call.
        
        Sets up material → lighting → camera animation → render settings → compositor.
        Supports turntable, hero reveal, and detail orbit camera styles.
        Includes 16 material presets (glass, metal, plastic, ceramic, fabric, leather, etc.)
        and 6 lighting rigs (studio, jewelry, cosmetics, electronics, automotive, food).
        
        Example: turntable of a bottle with glass material and cosmetics lighting:
          object_name="Bottle", material="clear_glass", lighting="cosmetics", camera_style="turntable"
        """
        results = {}
        
        # 1. Material
        if params.material:
            code = _gen_material_code(params.material.value, params.object_name)
            results["material"] = send_command_fn("execute_python", {"code": code})
        
        # 2. Lighting
        code = _gen_lighting_code(
            params.lighting.value, params.shadow_catcher, params.gradient_bg,
            hdri_path=None, hdri_strength=1.5
        )
        results["lighting"] = send_command_fn("execute_python", {"code": code})
        
        # 3. Camera
        code = _gen_camera_code(
            params.camera_style.value, params.object_name, params.frames,
            params.camera_distance, params.camera_height, params.focal_length,
            params.f_stop, params.use_dof, params.fps
        )
        results["camera"] = send_command_fn("execute_python", {"code": code})
        
        # 4. Render settings
        op = params.output_path or "/tmp/product_render/frame_####"
        code = _gen_render_code(
            params.quality.value, params.resolution.value,
            params.transparent_bg, op, "PNG"
        )
        results["render"] = send_command_fn("execute_python", {"code": code})
        
        # 5. Compositor
        code = _gen_compositor_code(params.bloom, params.vignette)
        results["compositor"] = send_command_fn("execute_python", {"code": code})
        
        # 6. Auto-render
        if params.auto_render:
            results["render_start"] = send_command_fn("render", {"type": "animation", "output_path": op})
        
        summary = {
            "status": "ok",
            "recipe": f"{params.camera_style.value} animation",
            "object": params.object_name,
            "material": params.material.value if params.material else "existing",
            "lighting": params.lighting.value,
            "camera": params.camera_style.value,
            "frames": params.frames,
            "duration_sec": round(params.frames / params.fps, 1),
            "quality": params.quality.value,
            "resolution": params.resolution.value,
            "output": op,
            "steps_completed": len([v for v in results.values() if not (isinstance(v, dict) and v.get("error"))]),
            "errors": [k for k, v in results.items() if isinstance(v, dict) and v.get("error")],
        }
        return format_result_fn(summary)
    
    @mcp_instance.tool(
        name="blender_product_material",
        annotations={"title": "Product Material Preset", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_product_material(params: ProductMaterialInput) -> str:
        """Apply a professional product material preset to an object.
        
        16 presets: glossy_plastic, matte_plastic, brushed_aluminum, polished_chrome, gold, 
        rose_gold, copper, clear_glass, frosted_glass, tinted_glass, ceramic_glazed, 
        rubber_matte, fabric_cotton, leather, silk_satin, white_product.
        
        Optional: color/roughness overrides, photorealistic imperfections (fingerprints/dust).
        """
        code = _gen_material_code(
            params.preset.value, params.object_name, params.material_name,
            params.color_override, params.roughness_override, params.add_imperfections
        )
        return format_result_fn(send_command_fn("execute_python", {"code": code}))
    
    @mcp_instance.tool(
        name="blender_product_lighting",
        annotations={"title": "Product Lighting Rig", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_product_lighting(params: ProductLightingInput) -> str:
        """Set up professional product lighting.
        
        6 presets: product_studio, jewelry, cosmetics, electronics, automotive, food_product.
        Each creates optimized 3-point lighting with proper energy, color temperature, and positioning.
        Supports HDRI environments, gradient backgrounds, and shadow catchers.
        """
        code = _gen_lighting_code(
            params.preset.value, params.shadow_catcher, params.gradient_bg,
            params.gradient_top, params.gradient_bottom,
            params.hdri_path, params.hdri_strength, params.hdri_rotation
        )
        return format_result_fn(send_command_fn("execute_python", {"code": code}))
    
    @mcp_instance.tool(
        name="blender_product_camera",
        annotations={"title": "Product Camera Animation", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_product_camera(params: ProductCameraInput) -> str:
        """Set up professional product camera animation.
        
        Styles:
        - turntable: smooth 360° orbit with linear interpolation
        - hero_reveal: cinematic dolly-in + zoom + rise with ease-out
        - detail_orbit: slow partial orbit with dolly-in, shallow DOF
        
        All create proper camera rigs with Track-To constraints, DOF, and F-curve easing.
        """
        code = _gen_camera_code(
            params.style.value, params.target_object, params.frames,
            params.camera_distance, params.camera_height, params.focal_length,
            params.f_stop, params.use_dof, params.fps,
            params.start_distance, params.end_distance,
            params.start_focal, params.end_focal, params.orbit_angle
        )
        return format_result_fn(send_command_fn("execute_python", {"code": code}))
    
    @mcp_instance.tool(
        name="blender_product_render_setup",
        annotations={"title": "Product Render Configuration", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_product_render_setup(params: ProductRenderInput) -> str:
        """Configure professional product render settings + compositor.
        
        Quality: fast (128 samples), balanced (256), premium (512).
        Resolution: 720p, 1080p, 4k, square_1080, vertical, instagram.
        Includes Cycles GPU, adaptive sampling, denoising, AgX color management,
        bloom/glow post-processing, and optional vignette.
        """
        render_code = _gen_render_code(
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
            "quality": params.quality.value,
            "resolution": params.resolution.value,
        })
    
    @mcp_instance.tool(
        name="blender_fcurve_edit",
        annotations={"title": "F-Curve Animation Editor", "readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_fcurve_edit(params: FCurveInput) -> str:
        """Fine-tune animation F-curves for professional easing.
        
        Control interpolation (LINEAR, BEZIER, CONSTANT), easing (EASE_IN, EASE_OUT, EASE_IN_OUT),
        and handle types (AUTO, VECTOR, ALIGNED, FREE, AUTO_CLAMPED) on any animated property.
        
        Essential for getting the premium feel: ease-out on camera approaches, 
        linear on turntables, ease-in-out on detail orbits.
        """
        easing_code = f'kf.easing = "{params.easing}"' if params.easing else ""
        handle_code = f'kf.handle_left_type = "{params.handle_type}"\n                    kf.handle_right_type = "{params.handle_type}"' if params.handle_type else ""
        
        code = f"""
import bpy
obj = bpy.data.objects.get("{params.object_name}")
if not obj or not obj.animation_data or not obj.animation_data.action:
    __result__ = {{"error": "Object '{params.object_name}' has no animation"}}
else:
    modified = 0
    for fc in obj.animation_data.action.fcurves:
        if "{params.data_path}" in fc.data_path:
            if {params.index} == -1 or fc.array_index == {params.index}:
                for kf in fc.keyframe_points:
                    kf.interpolation = '{params.interpolation}'
                    {easing_code}
                    {handle_code}
                    modified += 1
    __result__ = {{"status": "ok", "keyframes_modified": modified, "interpolation": "{params.interpolation}"}}
"""
        return format_result_fn(send_command_fn("execute_python", {"code": code}))
    
    return [
        "blender_product_animation",
        "blender_product_material",
        "blender_product_lighting",
        "blender_product_camera",
        "blender_product_render_setup",
        "blender_fcurve_edit",
    ]
