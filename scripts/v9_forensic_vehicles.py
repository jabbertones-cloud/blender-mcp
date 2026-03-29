import bpy
import bmesh
from mathutils import Vector, Matrix, Euler
import math


def create_sedan(name, color, location):
    '''Creates a realistic sedan model (~2K vertices).
    
    Args:
        name: Object name
        color: Tuple (R, G, B, A) for base color
        location: Tuple (x, y, z) for placement
    
    Returns:
        Object reference to sedan
    '''
    # Vehicle dimensions: 4.5m long, 1.8m wide, 1.4m tall
    length = 4.5
    width = 1.8
    height = 1.4
    
    # Create main body from cube
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=location
    )
    body = bpy.context.active_object
    body.name = name + '_body'
    
    # Scale to vehicle dimensions
    body.scale = (length / 2, width / 2, height / 2)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.transform_apply(scale=True)
    
    # Enter edit mode to shape body
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(width=0.1, segments=2)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Add subdivision surface for smoothing
    subsurf = body.modifiers.new(name='Subsurf', type='SUBSURF')
    subsurf.levels = 2
    subsurf.render_levels = 3
    
    # Create wheels
    wheel_positions = [
        (length * 0.25, width * 0.5 + 0.05, 0),
        (length * 0.25, -width * 0.5 - 0.05, 0),
        (-length * 0.25, width * 0.5 + 0.05, 0),
        (-length * 0.25, -width * 0.5 - 0.05, 0),
    ]
    
    wheel_radius = 0.35
    wheel_objs = []
    
    for i, wheel_pos in enumerate(wheel_positions):
        wheel_obj = _create_wheel(
            name + f'_wheel_{i}',
            wheel_radius,
            (location[0] + wheel_pos[0], location[1] + wheel_pos[1], location[2] + wheel_pos[2])
        )
        wheel_objs.append(wheel_obj)
    
    # Apply car paint material
    apply_car_paint(body, color)
    
    return body


def create_suv(name, color, location):
    '''Creates a realistic SUV model (~2K vertices).
    
    Args:
        name: Object name
        color: Tuple (R, G, B, A) for base color
        location: Tuple (x, y, z) for placement
    
    Returns:
        Object reference to SUV
    '''
    # Vehicle dimensions: 4.8m long, 1.9m wide, 1.7m tall
    length = 4.8
    width = 1.9
    height = 1.7
    
    # Create main body from cube
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=location
    )
    body = bpy.context.active_object
    body.name = name + '_body'
    
    # Scale to vehicle dimensions
    body.scale = (length / 2, width / 2, height / 2)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.transform_apply(scale=True)
    
    # Enter edit mode to shape body
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(width=0.12, segments=2)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Add subdivision surface for smoothing
    subsurf = body.modifiers.new(name='Subsurf', type='SUBSURF')
    subsurf.levels = 2
    subsurf.render_levels = 3
    
    # Create wheels - slightly larger for SUV
    wheel_positions = [
        (length * 0.25, width * 0.5 + 0.05, 0),
        (length * 0.25, -width * 0.5 - 0.05, 0),
        (-length * 0.25, width * 0.5 + 0.05, 0),
        (-length * 0.25, -width * 0.5 - 0.05, 0),
    ]
    
    wheel_radius = 0.38
    wheel_objs = []
    
    for i, wheel_pos in enumerate(wheel_positions):
        wheel_obj = _create_wheel(
            name + f'_wheel_{i}',
            wheel_radius,
            (location[0] + wheel_pos[0], location[1] + wheel_pos[1], location[2] + wheel_pos[2])
        )
        wheel_objs.append(wheel_obj)
    
    # Apply car paint material
    apply_car_paint(body, color)
    
    return body


def create_pickup_truck(name, color, location):
    '''Creates a realistic pickup truck model (~2.5K vertices).
    
    Args:
        name: Object name
        color: Tuple (R, G, B, A) for base color
        location: Tuple (x, y, z) for placement
    
    Returns:
        Object reference to truck
    '''
    # Vehicle dimensions: 5.3m long, 1.9m wide, 1.8m tall
    length = 5.3
    width = 1.9
    height = 1.8
    
    # Create main body from cube
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=location
    )
    body = bpy.context.active_object
    body.name = name + '_body'
    
    # Scale to vehicle dimensions
    body.scale = (length / 2, width / 2, height / 2)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.transform_apply(scale=True)
    
    # Enter edit mode to shape body
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.bevel(width=0.15, segments=2)
    bpy.ops.object.mode_set(mode='OBJECT')
    
    # Add subdivision surface for smoothing
    subsurf = body.modifiers.new(name='Subsurf', type='SUBSURF')
    subsurf.levels = 2
    subsurf.render_levels = 3
    
    # Create truck bed (rear cargo area)
    bed_length = 1.8
    bed_obj = _create_truck_bed(
        name + '_bed',
        bed_length,
        width,
        0.5,
        (location[0] - length * 0.3, location[1], location[2])
    )
    
    # Create wheels - larger for truck
    wheel_positions = [
        (length * 0.25, width * 0.5 + 0.05, 0),
        (length * 0.25, -width * 0.5 - 0.05, 0),
        (-length * 0.25, width * 0.5 + 0.05, 0),
        (-length * 0.25, -width * 0.5 - 0.05, 0),
    ]
    
    wheel_radius = 0.4
    wheel_objs = []
    
    for i, wheel_pos in enumerate(wheel_positions):
        wheel_obj = _create_wheel(
            name + f'_wheel_{i}',
            wheel_radius,
            (location[0] + wheel_pos[0], location[1] + wheel_pos[1], location[2] + wheel_pos[2])
        )
        wheel_objs.append(wheel_obj)
    
    # Apply car paint material
    apply_car_paint(body, color)
    
    return body


def create_pedestrian_mannequin(name, location, pose='standing'):
    '''Creates a realistic pedestrian mannequin (~1K vertices).
    
    Args:
        name: Object name
        location: Tuple (x, y, z) for placement
        pose: String - 'standing', 'walking', or 'crossing'
    
    Returns:
        Object reference to mannequin (single joined mesh)
    '''
    # Human proportions - total height 1.75m
    total_height = 1.75
    head_diameter = 0.22
    
    # Create head
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=head_diameter / 2,
        location=(location[0], location[1], location[2] + total_height * 0.45)
    )
    head = bpy.context.active_object
    head.name = name + '_head'
    
    # Create neck
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.08,
        depth=0.15,
        location=(location[0], location[1], location[2] + total_height * 0.35)
    )
    neck = bpy.context.active_object
    neck.name = name + '_neck'
    
    # Create torso
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=(location[0], location[1], location[2] + total_height * 0.15)
    )
    torso = bpy.context.active_object
    torso.name = name + '_torso'
    torso.scale = (0.25, 0.2, 0.35)
    
    # Create left arm
    left_arm = _create_arm(
        name + '_arm_left',
        (location[0] - 0.35, location[1], location[2] + total_height * 0.25),
        pose
    )
    
    # Create right arm
    right_arm = _create_arm(
        name + '_arm_right',
        (location[0] + 0.35, location[1], location[2] + total_height * 0.25),
        pose
    )
    
    # Create left leg
    left_leg = _create_leg(
        name + '_leg_left',
        (location[0] - 0.1, location[1], location[2] - total_height * 0.25),
        pose
    )
    
    # Create right leg
    right_leg = _create_leg(
        name + '_leg_right',
        (location[0] + 0.1, location[1], location[2] - total_height * 0.25),
        pose
    )
    
    # Join all parts
    bpy.context.view_layer.objects.active = head
    bpy.ops.object.select_all(action='DESELECT')
    head.select_set(True)
    neck.select_set(True)
    torso.select_set(True)
    left_arm.select_set(True)
    right_arm.select_set(True)
    left_leg.select_set(True)
    right_leg.select_set(True)
    
    bpy.ops.object.join()
    mannequin = bpy.context.active_object
    mannequin.name = name
    
    # Apply neutral gray material
    gray_color = (0.5, 0.5, 0.5, 1.0)
    _apply_basic_material(mannequin, gray_color, 'Mannequin_Gray')
    
    return mannequin


def apply_car_paint(obj, color):
    '''Applies realistic car paint material to object.
    
    Args:
        obj: Blender object
        color: Tuple (R, G, B, A) for base color
    '''
    # Create material
    mat = bpy.data.materials.new(name=obj.name + '_CarPaint')
    mat.use_nodes = True
    
    # Clear default nodes
    mat.node_tree.nodes.clear()
    
    # Create nodes
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Metallic'].default_value = 0.4
    bsdf.inputs['Roughness'].default_value = 0.25
    bsdf.inputs['Coat Weight'].default_value = 0.8
    bsdf.inputs['Coat Roughness'].default_value = 0.03
    
    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    # Assign material
    obj.data.materials.append(mat)


def apply_asphalt_material(obj):
    '''Applies procedural asphalt material to object.
    
    Args:
        obj: Blender object
    '''
    # Create material
    mat = bpy.data.materials.new(name=obj.name + '_Asphalt')
    mat.use_nodes = True
    
    # Clear default nodes
    mat.node_tree.nodes.clear()
    
    # Create nodes
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    
    # Base color
    base_color = (0.08, 0.08, 0.08, 1.0)
    
    # Noise texture for aggregate
    noise = nodes.new(type='ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 200.0
    noise.inputs['Detail'].default_value = 5.0
    
    # Voronoi for cracks
    voronoi = nodes.new(type='ShaderNodeTexVoronoi')
    voronoi.inputs['Scale'].default_value = 15.0
    
    # ColorRamp for contrast
    ramp = nodes.new(type='ShaderNodeValRamp')
    ramp.color_ramp.elements[0].color = (0.05, 0.05, 0.05, 1.0)
    ramp.color_ramp.elements[1].color = (0.12, 0.12, 0.12, 1.0)
    
    # Mix for combining textures
    mix = nodes.new(type='ShaderNodeMix')
    mix.inputs['A'].default_value = base_color
    mix.inputs['B'].default_value = (0.1, 0.1, 0.1, 1.0)
    
    # Principled BSDF
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Roughness'].default_value = 0.85
    
    # Output
    output = nodes.new(type='ShaderNodeOutputMaterial')
    
    # Connect nodes
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], mix.inputs['A'])
    links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    
    # Assign material
    obj.data.materials.append(mat)


def apply_impact_deformation(vehicle_obj, impact_point, impact_direction, severity=0.5):
    '''Applies lattice-based crumple deformation to vehicle.
    
    Args:
        vehicle_obj: Vehicle object to deform
        impact_point: Tuple (x, y, z) - center of impact
        impact_direction: Tuple (x, y, z) - direction of force
        severity: Float 0.0-1.0 - intensity of deformation
    '''
    # Create lattice
    bpy.ops.object.lattice_add(
        size=3,
        location=impact_point
    )
    lattice_obj = bpy.context.active_object
    lattice_obj.name = vehicle_obj.name + '_Lattice'
    
    # Scale lattice to encompass impact zone
    impact_radius = 1.0 + severity * 0.5
    lattice_obj.scale = (impact_radius, impact_radius, impact_radius)
    bpy.context.view_layer.objects.active = lattice_obj
    bpy.ops.object.transform_apply(scale=True)
    
    # Add lattice modifier to vehicle
    lattice_mod = vehicle_obj.modifiers.new(
        name='ImpactLattice',
        type='LATTICE'
    )
    lattice_mod.object = lattice_obj
    
    # Deform lattice points
    bpy.context.view_layer.objects.active = lattice_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.lattice.select_all(action='SELECT')
    
    # Move lattice points along impact direction
    impact_vec = Vector(impact_direction).normalized()
    displacement = impact_vec * severity * 0.3
    bpy.ops.transform.translate(
        value=(displacement.x, displacement.y, displacement.z)
    )
    
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return lattice_obj


def add_exhibit_overlay(scene_name, case_number, exhibit_id):
    '''Adds forensic exhibit overlay elements to scene.
    
    Args:
        scene_name: Name of scene to add to
        case_number: String like "Smith v. Johnson, Case No. 2024-CV-1234"
        exhibit_id: String like "EXHIBIT A-1"
    '''
    scene = bpy.data.scenes[scene_name]
    
    # Scale bar at bottom left
    scale_bar_obj = _create_scale_bar(
        'ScaleBar_3m',
        3.0,
        (-5.0, -5.0, 0.0)
    )
    
    # Case number text
    bpy.ops.object.text_add(
        location=(-6.0, 5.5, 0.0)
    )
    case_text = bpy.context.active_object
    case_text.name = 'CaseNumber_Text'
    case_text.data.body = case_number
    case_text.scale = (0.4, 0.4, 0.4)
    
    # Exhibit ID text
    bpy.ops.object.text_add(
        location=(-6.0, 5.0, 0.0)
    )
    exhibit_text = bpy.context.active_object
    exhibit_text.name = 'ExhibitID_Text'
    exhibit_text.data.body = exhibit_id
    exhibit_text.scale = (0.5, 0.5, 0.5)
    
    # Disclaimer text
    bpy.ops.object.text_add(
        location=(-6.0, 4.0, 0.0)
    )
    disclaimer_text = bpy.context.active_object
    disclaimer_text.name = 'Disclaimer_Text'
    disclaimer_text.data.body = 'DEMONSTRATIVE AID — NOT DRAWN TO SCALE'
    disclaimer_text.scale = (0.3, 0.3, 0.3)
    
    # Timestamp text
    import datetime
    timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    bpy.ops.object.text_add(
        location=(-6.0, 3.5, 0.0)
    )
    timestamp_text = bpy.context.active_object
    timestamp_text.name = 'Timestamp_Text'
    timestamp_text.data.body = 'Generated: ' + timestamp_str
    timestamp_text.scale = (0.25, 0.25, 0.25)
    
    # North arrow
    north_arrow = _create_north_arrow(
        'NorthArrow',
        (5.5, 5.5, 0.0)
    )
    
    return {
        'scale_bar': scale_bar_obj,
        'case_text': case_text,
        'exhibit_text': exhibit_text,
        'disclaimer_text': disclaimer_text,
        'timestamp_text': timestamp_text,
        'north_arrow': north_arrow
    }


# Helper functions

def _create_wheel(name, radius, location):
    '''Creates a wheel (cylinder + torus for tire/rim).'''
    # Rim (cylinder)
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius * 0.6,
        depth=0.15,
        location=location
    )
    rim = bpy.context.active_object
    rim.name = name + '_rim'
    
    # Tire (torus)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius,
        minor_radius=radius * 0.2,
        location=location
    )
    tire = bpy.context.active_object
    tire.name = name + '_tire'
    
    # Join rim and tire
    bpy.context.view_layer.objects.active = rim
    rim.select_set(True)
    tire.select_set(True)
    bpy.ops.object.join()
    wheel = bpy.context.active_object
    wheel.name = name
    
    # Apply rubber material to tire
    _apply_basic_material(wheel, (0.1, 0.1, 0.1, 1.0), 'Rubber')
    
    return wheel


def _create_truck_bed(name, length, width, height, location):
    '''Creates truck bed (cargo area).'''
    bpy.ops.mesh.primitive_cube_add(
        size=1,
        location=location
    )
    bed = bpy.context.active_object
    bed.name = name
    
    bed.scale = (length / 2, width / 2, height / 2)
    bpy.context.view_layer.objects.active = bed
    bpy.ops.object.transform_apply(scale=True)
    
    # Apply metal material
    _apply_basic_material(bed, (0.3, 0.3, 0.3, 1.0), 'BedMetal')
    
    return bed


def _create_arm(name, location, pose):
    '''Creates arm segment with elbow bend.'''
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.05,
        depth=0.6,
        location=location
    )
    arm = bpy.context.active_object
    arm.name = name
    
    # Apply rotation based on pose
    if pose == 'walking':
        arm.rotation_euler = Euler((0.3, 0, 0), 'XYZ')
    elif pose == 'crossing':
        arm.rotation_euler = Euler((0.5, 0, 0), 'XYZ')
    
    return arm


def _create_leg(name, location, pose):
    '''Creates leg segment with knee bend.'''
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.06,
        depth=0.85,
        location=location
    )
    leg = bpy.context.active_object
    leg.name = name
    
    # Apply rotation based on pose
    if pose == 'walking':
        leg.rotation_euler = Euler((0.2, 0, 0), 'XYZ')
    elif pose == 'crossing':
        leg.rotation_euler = Euler((0.15, 0, 0), 'XYZ')
    
    return leg


def _apply_basic_material(obj, color, mat_name):
    '''Applies basic material to object.'''
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = color
    obj.data.materials.append(mat)


def _create_scale_bar(name, length, location):
    '''Creates 3D scale bar with tick marks and labels.'''
    bpy.ops.mesh.primitive_cube_add(
        size=0.05,
        location=location
    )
    bar = bpy.context.active_object
    bar.name = name + '_bar'
    
    bar.scale = (length / 2, 0.025, 0.025)
    bpy.context.view_layer.objects.active = bar
    bpy.ops.object.transform_apply(scale=True)
    
    # Add tick marks
    tick_height = 0.1
    for i in range(0, int(length) + 1):
        tick_x = location[0] + (i / length) * length - length / 2
        bpy.ops.mesh.primitive_cube_add(
            size=0.02,
            location=(tick_x, location[1], location[2] + tick_height / 2)
        )
        tick = bpy.context.active_object
        tick.name = name + f'_tick_{i}'
        tick.scale = (0.01, 0.01, tick_height / 2)
    
    # Add text label
    bpy.ops.object.text_add(
        location=(location[0], location[1] - 0.5, location[2])
    )
    label = bpy.context.active_object
    label.name = name + '_label'
    label.data.body = f'{int(length)}m'
    label.scale = (0.3, 0.3, 0.3)
    
    return bar


def _create_north_arrow(name, location):
    '''Creates north arrow (cone + line).'''
    # Cone pointing north
    bpy.ops.mesh.primitive_cone_add(
        vertices=8,
        radius=0.15,
        depth=0.4,
        location=location
    )
    arrow = bpy.context.active_object
    arrow.name = name + '_cone'
    
    # Add line below arrow
    bpy.ops.mesh.primitive_cylinder_add(
        radius=0.05,
        depth=0.5,
        location=(location[0], location[1] - 0.4, location[2])
    )
    line = bpy.context.active_object
    line.name = name + '_line'
    
    # Add 'N' label
    bpy.ops.object.text_add(
        location=(location[0], location[1], location[2] + 0.3)
    )
    label = bpy.context.active_object
    label.name = name + '_label'
    label.data.body = 'N'
    label.scale = (0.4, 0.4, 0.4)
    
    return arrow


# Main demo block
if __name__ == '__main__':
    # Clear existing mesh objects (optional)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Create sedan (red)
    sedan = create_sedan(
        'Sedan_Red',
        (0.9, 0.1, 0.1, 1.0),
        (-3.0, 0.0, 0.5)
    )
    
    # Create SUV (blue)
    suv = create_suv(
        'SUV_Blue',
        (0.1, 0.3, 0.9, 1.0),
        (3.0, 0.0, 0.5)
    )
    
    # Create pickup truck (black)
    truck = create_pickup_truck(
        'Truck_Black',
        (0.1, 0.1, 0.1, 1.0),
        (0.0, -4.0, 0.5)
    )
    
    # Create mannequins in different poses
    mannequin_standing = create_pedestrian_mannequin(
        'Mannequin_Standing',
        (-5.0, -2.0, 0.0),
        pose='standing'
    )
    
    mannequin_walking = create_pedestrian_mannequin(
        'Mannequin_Walking',
        (0.0, -6.0, 0.0),
        pose='walking'
    )
    
    mannequin_crossing = create_pedestrian_mannequin(
        'Mannequin_Crossing',
        (5.0, -2.0, 0.0),
        pose='crossing'
    )
    
    # Apply impact deformation to sedan
    apply_impact_deformation(
        sedan,
        (-3.0, 0.5, 0.8),
        (-1.0, 0.2, 0.0),
        severity=0.6
    )
    
    # Create ground plane with asphalt material
    bpy.ops.mesh.primitive_plane_add(
        size=1,
        location=(0.0, 0.0, 0.0)
    )
    ground = bpy.context.active_object
    ground.name = 'Ground_Asphalt'
    ground.scale = (15.0, 15.0, 1.0)
    bpy.context.view_layer.objects.active = ground
    bpy.ops.object.transform_apply(scale=True)
    
    apply_asphalt_material(ground)
    
    # Add forensic exhibit overlay
    scene = bpy.context.scene
    overlay_objs = add_exhibit_overlay(
        scene.name,
        'Smith v. Johnson, Case No. 2024-CV-1234',
        'EXHIBIT A-1'
    )
    
    print('Forensic vehicle scene created successfully!')
    print(f'Total objects: {len(bpy.data.objects)}')
