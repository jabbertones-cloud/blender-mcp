"""
Forensic Scene Lighting Setup for Blender
v9 - Scene-appropriate lighting for all 4 forensic accident scenarios

Provides realistic daylight and nighttime lighting configurations for:
1. T-Bone Intersection (daylight)
2. Pedestrian Crosswalk (daylight)
3. Rear-end Highway (daylight with long shadows)
4. Hit-and-Run Parking Lot (nighttime with sodium vapor lights)

Usage:
    import v9_forensic_lighting as lighting
    lights = lighting.setup_daylight_intersection(sun_angle=50, time='2pm')
"""

import bpy
import math
from mathutils import Vector, Euler


def clear_all_lights():
    """Remove all light objects from the current scene."""
    scene = bpy.context.scene
    for obj in bpy.data.objects:
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)


def create_sun_light(name, location, energy, color, angle=50):
    """
    Create a sun light with given properties.
    
    Args:
        name: Light object name
        location: 3D location (Vector or tuple)
        energy: Light energy in watts
        color: RGB color tuple (r, g, b)
        angle: Sun elevation angle in degrees
    
    Returns:
        Light object
    """
    light_data = bpy.data.lights.new(name=name, type='SUN')
    light_data.energy = energy
    light_data.color = color[:3]
    light_data.angle = math.radians(angle)
    
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    
    light_obj.location = location
    light_obj.rotation_euler = Euler((math.radians(90 - angle), 0, 0))
    
    light_data.use_shadow = True
    light_data.shadow_type = 'RAY_SHADOW'
    
    return light_obj


def create_area_light(name, location, energy, color, size=1.0, falloff='INVERSE_SQUARE'):
    """
    Create an area light with given properties.
    
    Args:
        name: Light object name
        location: 3D location
        energy: Light energy in watts
        color: RGB color tuple
        size: Light size in Blender units
        falloff: Falloff type ('CONSTANT', 'LINEAR', 'QUADRATIC', 'INVERSE_SQUARE')
    
    Returns:
        Light object
    """
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = energy
    light_data.color = color[:3]
    light_data.size = size
    light_data.distance = 100
    light_data.falloff_type = falloff
    
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    
    light_obj.location = location
    light_data.use_shadow = True
    light_data.shadow_type = 'RAY_SHADOW'
    
    return light_obj


def create_spot_light(name, location, rotation, energy, color, spot_size=math.pi/4, falloff='LINEAR'):
    """
    Create a spotlight with cone and falloff.
    
    Args:
        name: Light object name
        location: 3D location
        rotation: Euler rotation in radians
        energy: Light energy in watts
        color: RGB color tuple
        spot_size: Cone angle in radians
        falloff: Falloff type
    
    Returns:
        Light object
    """
    light_data = bpy.data.lights.new(name=name, type='SPOT')
    light_data.energy = energy
    light_data.color = color[:3]
    light_data.spot_size = spot_size
    light_data.spot_blend = 0.15
    light_data.falloff_type = falloff
    light_data.distance = 50
    
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.collection.objects.link(light_obj)
    
    light_obj.location = location
    light_obj.rotation_euler = rotation
    light_data.use_shadow = True
    light_data.shadow_type = 'RAY_SHADOW'
    
    return light_obj


def setup_daylight_intersection(sun_angle=50, time='2pm'):
    """
    Setup lighting for T-Bone Intersection scene.
    
    Daylight scenario with:
    - High sun position creating sharp shadows
    - Warm daylight color temperature
    - Environment HDRI sky texture
    - Ambient fill from world
    
    Args:
        sun_angle: Sun elevation angle in degrees (default 50 for afternoon)
        time: Time descriptor for reference ('2pm', 'morning', etc.)
    
    Returns:
        Dictionary of created light objects
    """
    clear_all_lights()
    lights = {}
    
    # Primary sun light at 50° elevation
    sun_location = (50, -50, 40)
    sun_color = (1.0, 0.95, 0.9)  # Warm daylight
    
    lights['sun_primary'] = create_sun_light(
        name='Sun_Intersection',
        location=sun_location,
        energy=3000,
        color=sun_color,
        angle=sun_angle
    )
    
    # Ambient fill light - subtle area light from above
    lights['fill_ambient'] = create_area_light(
        name='Fill_Ambient_Intersection',
        location=(0, 0, 30),
        energy=300,
        color=(0.95, 0.95, 1.0),  # Slightly blue for sky bounce
        size=100,
        falloff='CONSTANT'
    )
    
    # Setup world/environment
    setup_forensic_world('daylight')
    
    return lights


def setup_daylight_crosswalk(sun_angle=45, time='midday'):
    """
    Setup lighting for Pedestrian Crosswalk scene.
    
    Daylight scenario optimized for:
    - Driver POV visibility (sightline critical)
    - Slightly higher sun (midday) = cooler light
    - Emphasis on contrast for forensic clarity
    - Pedestrian visibility from vehicle perspective
    
    Args:
        sun_angle: Sun elevation angle in degrees (default 45 for midday)
        time: Time descriptor ('midday', 'noon', etc.)
    
    Returns:
        Dictionary of created light objects
    """
    clear_all_lights()
    lights = {}
    
    # Primary sun light - slightly cooler for midday
    sun_location = (60, -40, 40)
    sun_color = (0.98, 0.97, 0.95)  # Very neutral midday sun
    
    lights['sun_primary'] = create_sun_light(
        name='Sun_Crosswalk',
        location=sun_location,
        energy=3200,
        color=sun_color,
        angle=sun_angle
    )
    
    # Key fill light - emphasize sightlines
    lights['fill_sightline'] = create_area_light(
        name='Fill_Sightline_Crosswalk',
        location=(20, 30, 25),
        energy=400,
        color=(0.9, 0.9, 1.0),  # Neutral blue sky
        size=80,
        falloff='INVERSE_SQUARE'
    )
    
    # Bounce light to show pedestrian clearly
    lights['bounce_pedestrian'] = create_area_light(
        name='Bounce_Pedestrian',
        location=(-30, 0, 20),
        energy=250,
        color=(0.95, 0.95, 0.98),
        size=60,
        falloff='CONSTANT'
    )
    
    setup_forensic_world('daylight')
    
    return lights


def setup_highway_daylight(sun_angle=35, time='afternoon'):
    """
    Setup lighting for Rear-End Highway Collision scene.
    
    Daylight scenario emphasizing:
    - Lower sun angle (35°) for long shadows
    - Shadows show distance and speed context
    - Area light to simulate sky bounce on highway
    - Emphasis on depth perception
    
    Args:
        sun_angle: Sun elevation angle in degrees (default 35 for afternoon)
        time: Time descriptor ('afternoon', 'late afternoon', etc.)
    
    Returns:
        Dictionary of created light objects
    """
    clear_all_lights()
    lights = {}
    
    # Primary sun light - lower angle for long shadows
    sun_location = (80, -60, 30)
    sun_color = (1.0, 0.93, 0.85)  # Warmer afternoon sun
    
    lights['sun_primary'] = create_sun_light(
        name='Sun_Highway',
        location=sun_location,
        energy=2800,
        color=sun_color,
        angle=sun_angle
    )
    
    # Large sky dome area light - simulate atmospheric bounce
    lights['sky_dome'] = create_area_light(
        name='Sky_Dome_Highway',
        location=(0, 0, 50),
        energy=500,
        color=(0.92, 0.92, 1.0),  # Cool sky
        size=150,
        falloff='INVERSE_SQUARE'
    )
    
    # Ground bounce light - road reflects some light back
    lights['ground_bounce'] = create_area_light(
        name='Ground_Bounce_Highway',
        location=(0, 0, 2),
        energy=200,
        color=(0.85, 0.83, 0.80),  # Asphalt gray
        size=120,
        falloff='CONSTANT'
    )
    
    setup_forensic_world('daylight')
    
    return lights


def setup_parking_lot_night():
    """
    Setup lighting for Hit-and-Run Parking Lot scene (NIGHTTIME).
    
    Nighttime scenario with:
    - NO sun light (nighttime)
    - 4x sodium vapor pole lights (warm orange) at corners
    - 500W each light with harsh downward pool effect
    - Security camera visible light cone
    - Moon ambient low-level blue
    - Dark world background
    
    Returns:
        Dictionary of created light objects
    """
    clear_all_lights()
    lights = {}
    
    # Sodium vapor color - warm orange (typical parking lot sodium lights)
    sodium_color = (1.0, 0.85, 0.4)
    
    # Four corner pole lights (parking lot typical layout)
    # Positions assume lot is roughly -50 to 50 in X and Y
    pole_positions = [
        (-40, -40, 8),   # Southwest corner
        (40, -40, 8),    # Southeast corner
        (40, 40, 8),     # Northeast corner
        (-40, 40, 8)     # Northwest corner
    ]
    
    pole_names = [
        'Pole_Light_SW',
        'Pole_Light_SE',
        'Pole_Light_NE',
        'Pole_Light_NW'
    ]
    
    for i, (pos, name) in enumerate(zip(pole_positions, pole_names)):
        lights[f'pole_{i}'] = create_area_light(
            name=name,
            location=pos,
            energy=500,
            color=sodium_color,
            size=2.0,
            falloff='INVERSE_SQUARE'
        )
        # Make lights cast shadows for realistic pool effect
        lights[f'pole_{i}'].data.use_shadow = True
        lights[f'pole_{i}'].data.shadow_type = 'RAY_SHADOW'
    
    # Security camera spotlight - visible light cone pointing down
    # Assume camera at corner tower
    lights['security_camera'] = create_spot_light(
        name='Security_Camera_Light',
        location=(-45, 45, 12),
        rotation=Euler((math.radians(-70), 0, 0)),
        energy=300,
        color=(0.98, 0.98, 0.95),  # Nearly white for security cam
        spot_size=math.radians(30),
        falloff='LINEAR'
    )
    
    # Moon ambient light - very subtle blue
    lights['moon_ambient'] = create_area_light(
        name='Moon_Ambient',
        location=(0, 0, 100),
        energy=2,
        color=(0.7, 0.75, 1.0),  # Blue moonlight
        size=200,
        falloff='CONSTANT'
    )
    lights['moon_ambient'].data.use_shadow = False
    
    # Setup dark night world
    setup_forensic_world('nighttime')
    
    return lights


def setup_forensic_world(scene_type='daylight'):
    """
    Configure world/environment settings appropriate for forensic scene.
    
    Args:
        scene_type: 'daylight' for day scenes, 'nighttime' for night scenes
    
    Sets up:
    - World shader/HDRI environment
    - Color management (AgX with Punchy)
    - Background color and strength
    """
    world = bpy.context.scene.world
    
    # Setup world shader
    world.use_nodes = True
    world_nodes = world.node_tree.nodes
    world_links = world.node_tree.links
    
    # Clear default nodes
    world_nodes.clear()
    
    # Create new node setup
    output_node = world_nodes.new('ShaderNodeOutputWorld')
    bg_shader = world_nodes.new('ShaderNodeBackground')
    
    world_links.new(bg_shader.outputs['Background'], output_node.inputs['Surface'])
    
    if scene_type == 'daylight':
        # Light blue sky gradient for day scenes
        bg_shader.inputs['Color'].default_value = (0.5, 0.7, 1.0, 1.0)
        bg_shader.inputs['Strength'].default_value = 1.0
    else:
        # Dark blue/black for night scenes
        bg_shader.inputs['Color'].default_value = (0.02, 0.02, 0.04, 1.0)
        bg_shader.inputs['Strength'].default_value = 0.5
    
    # Setup color management - AgX with Punchy look
    scene = bpy.context.scene
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'Punchy'
    scene.view_settings.exposure = 0.0
    
    # Set color space
    scene.sequencer_colorspace_settings.name = 'Linear'


def get_scene_lights(scene_name):
    """
    Retrieve all lights in a named collection/scene group.
    
    Args:
        scene_name: Name of the scene or light group to query
    
    Returns:
        List of light objects in scene
    """
    lights = [obj for obj in bpy.context.scene.objects if obj.type == 'LIGHT']
    return lights


def validate_lighting_setup():
    """
    Validate that lighting setup is complete and correct.
    
    Returns:
        Dictionary with validation results
    """
    world = bpy.context.scene.world
    lights = [obj for obj in bpy.context.scene.objects if obj.type == 'LIGHT']
    
    validation = {
        'total_lights': len(lights),
        'world_configured': world.use_nodes,
        'light_names': [light.name for light in lights],
        'has_sun': any('Sun' in light.name for light in lights),
        'has_fill': any('Fill' in light.name or 'Ambient' in light.name for light in lights),
    }
    
    return validation


# Example usage functions
def demo_setup_intersection():
    """Demo: Setup intersection scene lighting."""
    lights = setup_daylight_intersection(sun_angle=50, time='2pm')
    validation = validate_lighting_setup()
    print(f'Intersection lighting setup complete: {validation}')
    return lights


def demo_setup_parking_lot():
    """Demo: Setup parking lot nighttime lighting."""
    lights = setup_parking_lot_night()
    validation = validate_lighting_setup()
    print(f'Parking lot lighting setup complete: {validation}')
    return lights


if __name__ == '__main__':
    # This allows the script to be run directly in Blender
    print('Forensic Lighting Module v9 loaded')
    print('Available functions:')
    print('  - setup_daylight_intersection()')
    print('  - setup_daylight_crosswalk()')
    print('  - setup_highway_daylight()')
    print('  - setup_parking_lot_night()')
    print('  - setup_forensic_world()')
    print('  - validate_lighting_setup()')
