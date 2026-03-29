"""V8 Forensic Upgrades — Baked into Addon as Standardized Actions

These functions are designed to be imported into openclaw_blender_bridge.py
and registered as new actions within handle_forensic_scene().

New actions added:
  apply_pro_materials  — Replace all scene materials with v8 procedural PBR
  setup_exhibit_overlay — Add forensic exhibit labels/annotations to scene
  add_scale_reference  — Place scale bar + compass in scene
  setup_v8_lighting    — Professional 3-point lighting rig
  upgrade_vehicle_geo  — Enhance vehicle geometry with details
  upgrade_figure_geo   — Enhance human figure geometry

Integration:
  Add to handle_forensic_scene() dispatch:
    elif action == "apply_pro_materials":
        return v8_apply_pro_materials(params)
    elif action == "setup_exhibit_overlay":
        return v8_setup_exhibit_overlay(params)
    ... etc
"""

import bpy
import bmesh
import math


# ============================================================
# ACTION: apply_pro_materials
# ============================================================
def v8_apply_pro_materials(params):
    """Replace flat materials with v8 procedural PBR materials.
    
    Params:
        target: 'all' | 'roads' | 'vehicles' | 'figures' | 'environment'
    """
    target = params.get("target", "all")
    applied = []
    
    if target in ("all", "roads"):
        # Find road objects and apply pro asphalt
        for obj in bpy.data.objects:
            if any(k in obj.name.lower() for k in ("road", "asphalt", "street", "lane")):
                mat = _create_pro_asphalt_material()
                if obj.data and hasattr(obj.data, 'materials'):
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
                    applied.append(f"asphalt -> {obj.name}")
            elif any(k in obj.name.lower() for k in ("curb", "sidewalk", "concrete")):
                mat = _create_pro_concrete_material()
                if obj.data and hasattr(obj.data, 'materials'):
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
                    applied.append(f"concrete -> {obj.name}")
            elif any(k in obj.name.lower() for k in ("marking", "stripe", "line")):
                color = 'yellow' if 'yellow' in obj.name.lower() else 'white'
                mat = _create_pro_lane_marking(color)
                if obj.data and hasattr(obj.data, 'materials'):
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
                    applied.append(f"lane_{color} -> {obj.name}")
    
    if target in ("all", "vehicles"):
        for obj in bpy.data.objects:
            if any(k in obj.name.lower() for k in ("wheel", "tire")):
                mat = _create_pro_rubber_material()
                if obj.data and hasattr(obj.data, 'materials'):
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
                    applied.append(f"rubber -> {obj.name}")
            elif "cabin" in obj.name.lower() or "glass" in obj.name.lower():
                mat = _create_pro_glass_material()
                if obj.data and hasattr(obj.data, 'materials'):
                    obj.data.materials.clear()
                    obj.data.materials.append(mat)
                    applied.append(f"glass -> {obj.name}")
    
    return f"V8 materials applied: {len(applied)} objects updated. {'; '.join(applied[:10])}"


# ============================================================
# ACTION: setup_exhibit_overlay
# ============================================================
def v8_setup_exhibit_overlay(params):
    """Configure forensic exhibit labels and metadata.
    
    Params:
        case_number: str (default "2026-CV-DEMO")
        exhibit_ref: str (default "1-A")
        scene_title: str (default "Forensic Scene")
        preparer: str (default "OpenClaw Forensic Animation System")
    """
    case = params.get("case_number", "2026-CV-DEMO")
    exhibit = params.get("exhibit_ref", "1-A")
    title = params.get("scene_title", "Forensic Scene")
    preparer = params.get("preparer", "OpenClaw Forensic Animation System")
    disclaimer = "DEMONSTRATIVE AID \u2014 NOT DRAWN TO SCALE"
    
    scene = bpy.context.scene
    cam = scene.camera
    
    if not cam:
        return "ERROR: No active camera for exhibit overlay"
    
    # Bottom label
    font_curve = bpy.data.curves.new(name='ExhibitLabel_v8', type='FONT')
    font_curve.body = f'Exhibit {exhibit}  |  {title}  |  {disclaimer}'
    font_curve.size = 0.016
    font_curve.align_x = 'CENTER'
    label_obj = bpy.data.objects.new('ExhibitLabel_v8', font_curve)
    bpy.context.collection.objects.link(label_obj)
    label_obj.parent = cam
    label_obj.location = (0, -0.02, -0.18)
    
    # Emissive white text
    tmat = bpy.data.materials.new(name='ExhibitTextMat_v8')
    tmat.use_nodes = True
    bsdf = tmat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1)
    bsdf.inputs['Emission Strength'].default_value = 3.0
    try:
        bsdf.inputs['Emission Color'].default_value = (0.95, 0.95, 0.95, 1)
    except: pass
    font_curve.materials.append(tmat)
    
    # Top label
    top_curve = bpy.data.curves.new(name='CaseLabel_v8', type='FONT')
    top_curve.body = f'Case: {case}  |  {preparer}'
    top_curve.size = 0.011
    top_curve.align_x = 'CENTER'
    top_obj = bpy.data.objects.new('CaseLabel_v8', top_curve)
    bpy.context.collection.objects.link(top_obj)
    top_obj.parent = cam
    top_obj.location = (0, -0.02, -0.135)
    
    tmat2 = bpy.data.materials.new(name='CaseTextMat_v8')
    tmat2.use_nodes = True
    bsdf2 = tmat2.node_tree.nodes['Principled BSDF']
    bsdf2.inputs['Base Color'].default_value = (0.7, 0.7, 0.75, 1)
    bsdf2.inputs['Emission Strength'].default_value = 2.0
    try:
        bsdf2.inputs['Emission Color'].default_value = (0.7, 0.7, 0.75, 1)
    except: pass
    top_curve.materials.append(tmat2)
    
    return f"Exhibit overlay: {exhibit} | {title} | {case}"


# ============================================================
# ACTION: add_scale_reference
# ============================================================
def v8_add_scale_reference(params):
    """Add scale bar and compass arrow to scene.
    
    Params:
        length_meters: float (default 10.0)
        position: [x, y, z] (default [5, -8, 0.01])
        compass: bool (default True)
    """
    length = params.get("length_meters", 10.0)
    pos = params.get("position", [5, -8, 0.01])
    add_compass = params.get("compass", True)
    
    # Scale bar
    bpy.ops.mesh.primitive_cube_add(size=1, location=tuple(pos))
    bar = bpy.context.active_object
    bar.name = f'ScaleBar_{length}m'
    bar.scale = (length, 0.15, 0.02)
    
    mat = bpy.data.materials.new(name='ScaleBarMat_v8')
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    bsdf = nodes['Principled BSDF']
    
    checker = nodes.new('ShaderNodeTexChecker')
    checker.inputs['Scale'].default_value = length * 2
    checker.inputs['Color1'].default_value = (0.95, 0.95, 0.95, 1)
    checker.inputs['Color2'].default_value = (0.05, 0.05, 0.05, 1)
    links.new(checker.outputs['Color'], bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.9
    bsdf.inputs['Emission Strength'].default_value = 0.5
    links.new(checker.outputs['Color'], bsdf.inputs['Emission Color'])
    bar.data.materials.append(mat)
    
    # Label
    fc = bpy.data.curves.new(name='ScaleLabel_v8', type='FONT')
    fc.body = f'{int(length)}m'
    fc.size = 0.4
    fc.align_x = 'CENTER'
    lbl = bpy.data.objects.new('ScaleLabel_v8', fc)
    bpy.context.collection.objects.link(lbl)
    lbl.location = (pos[0], pos[1] - 0.5, pos[2] + 0.1)
    
    lmat = bpy.data.materials.new(name='ScaleLabelMat_v8')
    lmat.use_nodes = True
    lmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 1, 1, 1)
    lmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
    fc.materials.append(lmat)
    
    result = f"Scale bar: {length}m at {pos}"
    
    # Compass arrow
    if add_compass:
        cx, cy = pos[0] + length/2 + 2, pos[1]
        bpy.ops.mesh.primitive_cone_add(vertices=3, radius1=0.3, depth=0.8, 
                                         location=(cx, cy + 0.4, pos[2]))
        arrow = bpy.context.active_object
        arrow.name = 'NorthArrow_v8'
        
        amat = bpy.data.materials.new(name='NorthArrowMat_v8')
        amat.use_nodes = True
        amat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.9, 0.1, 0.1, 1)
        amat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 1.0
        arrow.data.materials.append(amat)
        
        nfc = bpy.data.curves.new(name='NorthLabel_v8', type='FONT')
        nfc.body = 'N'
        nfc.size = 0.5
        nfc.align_x = 'CENTER'
        nlbl = bpy.data.objects.new('NorthLabel_v8', nfc)
        bpy.context.collection.objects.link(nlbl)
        nlbl.location = (cx, cy + 1.0, pos[2])
        
        nlmat = bpy.data.materials.new(name='NorthLabelMat_v8')
        nlmat.use_nodes = True
        nlmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1, 1, 1, 1)
        nlmat.node_tree.nodes['Principled BSDF'].inputs['Emission Strength'].default_value = 2.0
        nfc.materials.append(nlmat)
        result += " + compass"
    
    return result


# ============================================================
# ACTION: upgrade_vehicle_geo
# ============================================================
def v8_upgrade_vehicle_geometry(params):
    """Add detail geometry to existing vehicles: headlights, taillights,
    door panel lines, windshield wipers, side mirrors.
    
    Params:
        vehicle_name: str (name of vehicle object to upgrade)
    """
    name = params.get("vehicle_name", "")
    vehicle = bpy.data.objects.get(name)
    if not vehicle:
        return f"Vehicle '{name}' not found"
    
    dims = vehicle.dimensions.copy()
    loc = vehicle.location.copy()
    rot_z = vehicle.rotation_euler[2]
    
    details_added = []
    
    # --- HEADLIGHTS (front, emissive) ---
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.12, segments=16, ring_count=8,
            location=(loc.x, loc.y, loc.z)
        )
        hl = bpy.context.active_object
        hl.name = f'{name}_Headlight_{"L" if side < 0 else "R"}'
        hl.parent = vehicle
        hl.location = (dims.x * 0.48, side * dims.y * 0.35, dims.z * 0.3)
        
        hmat = bpy.data.materials.new(name=f'{name}_HeadlightMat')
        hmat.use_nodes = True
        bsdf = hmat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (1.0, 0.98, 0.9, 1)
        bsdf.inputs['Emission Strength'].default_value = 5.0
        try:
            bsdf.inputs['Emission Color'].default_value = (1.0, 0.98, 0.9, 1)
        except: pass
        hl.data.materials.append(hmat)
        details_added.append('headlights')
    
    # --- TAILLIGHTS (rear, red emissive) ---
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=0.2, location=(loc.x, loc.y, loc.z))
        tl = bpy.context.active_object
        tl.name = f'{name}_Taillight_{"L" if side < 0 else "R"}'
        tl.parent = vehicle
        tl.location = (-dims.x * 0.48, side * dims.y * 0.35, dims.z * 0.35)
        tl.scale = (0.3, 0.8, 0.4)
        
        tlmat = bpy.data.materials.new(name=f'{name}_TaillightMat')
        tlmat.use_nodes = True
        bsdf = tlmat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (0.8, 0.02, 0.02, 1)
        bsdf.inputs['Emission Strength'].default_value = 3.0
        try:
            bsdf.inputs['Emission Color'].default_value = (0.8, 0.02, 0.02, 1)
        except: pass
        tl.data.materials.append(tlmat)
        details_added.append('taillights')
    
    # --- SIDE MIRRORS ---
    for side in [-1, 1]:
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(loc.x, loc.y, loc.z))
        mirror = bpy.context.active_object
        mirror.name = f'{name}_Mirror_{"L" if side < 0 else "R"}'
        mirror.parent = vehicle
        mirror.location = (dims.x * 0.15, side * (dims.y * 0.52), dims.z * 0.5)
        mirror.scale = (0.4, 0.15, 0.3)
        
        mmat = bpy.data.materials.new(name=f'{name}_MirrorMat')
        mmat.use_nodes = True
        bsdf = mmat.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (0.1, 0.1, 0.12, 1)
        bsdf.inputs['Metallic'].default_value = 0.9
        bsdf.inputs['Roughness'].default_value = 0.05
        mirror.data.materials.append(mmat)
        details_added.append('mirrors')
    
    # --- WINDSHIELD WIPERS ---
    for side_offset in [-0.3, 0.3]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.015, depth=0.8, 
                                             location=(loc.x, loc.y, loc.z))
        wiper = bpy.context.active_object
        wiper.name = f'{name}_Wiper'
        wiper.parent = vehicle
        wiper.location = (dims.x * 0.2, side_offset, dims.z * 0.6)
        wiper.rotation_euler = (0, math.radians(15), math.radians(10))
        
        wmat = bpy.data.materials.new(name=f'{name}_WiperMat')
        wmat.use_nodes = True
        wmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
        wmat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
        wiper.data.materials.append(wmat)
        details_added.append('wipers')
    
    return f"Vehicle '{name}' upgraded: {', '.join(set(details_added))}"


# ============================================================
# PRIVATE: Material creation helpers (same as v8_materials.py but as native functions)
# ============================================================
def _create_pro_asphalt_material():
    """Inline pro asphalt material creation."""
    mat = bpy.data.materials.new(name='Pro_Asphalt_v8')
    mat.use_nodes = True
    tree = mat.node_tree
    nodes = tree.nodes
    links = tree.links
    for n in nodes: nodes.remove(n)
    
    out = nodes.new('ShaderNodeOutputMaterial'); out.location = (1200, 0)
    bsdf = nodes.new('ShaderNodeBsdfPrincipled'); bsdf.location = (900, 0)
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    
    noise = nodes.new('ShaderNodeTexNoise'); noise.location = (-400, 200)
    noise.inputs['Scale'].default_value = 120.0
    noise.inputs['Detail'].default_value = 12.0
    
    voronoi = nodes.new('ShaderNodeTexVoronoi'); voronoi.location = (-400, -100)
    voronoi.inputs['Scale'].default_value = 60.0
    
    ramp = nodes.new('ShaderNodeValToRGB'); ramp.location = (-100, 200)
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = (0.03, 0.03, 0.035, 1)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = (0.065, 0.06, 0.058, 1)
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    
    bsdf.inputs['Roughness'].default_value = 0.85
    
    bump = nodes.new('ShaderNodeBump'); bump.location = (600, -200)
    bump.inputs['Strength'].default_value = 0.25
    math_add = nodes.new('ShaderNodeMath'); math_add.operation = 'ADD'
    math_add.location = (400, -200)
    links.new(voronoi.outputs['Distance'], math_add.inputs[0])
    links.new(noise.outputs['Fac'], math_add.inputs[1])
    links.new(math_add.outputs[0], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    
    return mat


def _create_pro_concrete_material():
    """Inline pro concrete material."""
    mat = bpy.data.materials.new(name='Pro_Concrete_v8')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.32, 0.31, 0.29, 1)
    bsdf.inputs['Roughness'].default_value = 0.85
    return mat


def _create_pro_lane_marking(color='white'):
    """Inline lane marking material."""
    base = (0.9, 0.9, 0.88, 1) if color == 'white' else (0.85, 0.7, 0.05, 1)
    mat = bpy.data.materials.new(name=f'Pro_LaneMarking_{color}_v8')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = base
    bsdf.inputs['Roughness'].default_value = 0.4
    return mat


def _create_pro_rubber_material():
    """Inline tire rubber material."""
    mat = bpy.data.materials.new(name='Pro_Rubber_v8')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.025, 1)
    bsdf.inputs['Roughness'].default_value = 0.75
    return mat


def _create_pro_glass_material():
    """Inline windshield glass material."""
    mat = bpy.data.materials.new(name='Pro_Glass_v8')
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.7, 0.75, 0.8, 1)
    bsdf.inputs['Roughness'].default_value = 0.0
    try: bsdf.inputs['Transmission Weight'].default_value = 0.92
    except:
        try: bsdf.inputs['Transmission'].default_value = 0.92
        except: pass
    try: bsdf.inputs['IOR'].default_value = 1.52
    except: pass
    bsdf.inputs['Alpha'].default_value = 0.35
    try: mat.surface_render_method = 'DITHERED'
    except:
        try: mat.blend_method = 'BLEND'
        except: pass
    return mat
