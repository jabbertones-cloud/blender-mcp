#!/usr/bin/env node

/**
 * Forensic Scene Builder v9
 * Connects to Blender MCP on localhost:9876
 * Builds complete forensic scenes with geometry, materials, lighting, evidence markers
 * Usage: node v9_scene_builder.js <scene_number>
 * Scene numbers: 1, 2, 3, 4
 */

const net = require('net');
const fs = require('fs');
const path = require('path');

const BLENDER_MCP_HOST = '127.0.0.1';
const BLENDER_MCP_PORT = 9876;
const RENDERS_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v9';

let messageId = 0;
let client = null;
let buffer = '';
let pendingMessages = new Map();
let connected = false;

// Scene configurations
const SCENES = {
  1: {
    name: 'Crosswalk Accident - Day',
    filename: 'v9_scene1.blend',
    render_filename: 'scene1',
    lighting_type: 'day',
    cameras: ['BirdEye', 'DriverPOV', 'Wide'],
    geometry: 'crosswalk',
    description: 'Urban crosswalk intersection with vehicles'
  },
  2: {
    name: 'Road Accident - Day',
    filename: 'v9_scene2.blend',
    render_filename: 'scene2',
    lighting_type: 'day',
    cameras: ['BirdEye', 'DriverPOV', 'Wide'],
    geometry: 'road',
    description: 'Multi-lane road collision scene'
  },
  3: {
    name: 'Parking Lot - Day',
    filename: 'v9_scene3.blend',
    render_filename: 'scene3',
    lighting_type: 'day',
    cameras: ['BirdEye', 'TruckPOV', 'Wide'],
    geometry: 'parking_lot',
    description: 'Parking lot side-swipe incident'
  },
  4: {
    name: 'Parking Lot - Night',
    filename: 'v9_scene4.blend',
    render_filename: 'scene4',
    lighting_type: 'night',
    cameras: ['SecurityCam', 'BirdEye', 'Wide'],
    geometry: 'parking_lot',
    description: 'Nighttime parking lot evidence scene'
  }
};

function sendMessage(command, params = {}) {
  return new Promise((resolve, reject) => {
    if (!client || !connected) {
      reject(new Error('Not connected to Blender MCP'));
      return;
    }

    messageId++;
    const msg = {
      id: messageId,
      command: command,
      params: params
    };

    const timeout = setTimeout(() => {
      pendingMessages.delete(messageId);
      reject(new Error(`Timeout waiting for message ${messageId}`));
    }, 30000);

    pendingMessages.set(messageId, {
      resolve: (result) => {
        clearTimeout(timeout);
        resolve(result);
      },
      reject: (error) => {
        clearTimeout(timeout);
        reject(error);
      }
    });

    const json = JSON.stringify(msg);
    client.write(json + '\n');
  });
}

function parseNestedJSON(str) {
  let braceCount = 0;
  let bracketCount = 0;
  let inString = false;
  let escapeNext = false;
  let jsonStart = -1;
  let results = [];

  for (let i = 0; i < str.length; i++) {
    const char = str[i];

    if (escapeNext) {
      escapeNext = false;
      continue;
    }

    if (char === '\\') {
      escapeNext = true;
      continue;
    }

    if (char === '"' && !escapeNext) {
      inString = !inString;
      continue;
    }

    if (inString) continue;

    if (char === '{') {
      if (braceCount === 0 && bracketCount === 0) {
        jsonStart = i;
      }
      braceCount++;
    } else if (char === '}') {
      braceCount--;
      if (braceCount === 0 && bracketCount === 0 && jsonStart !== -1) {
        try {
          const json = JSON.parse(str.substring(jsonStart, i + 1));
          results.push(json);
          jsonStart = -1;
        } catch (e) {
          // Parse error, continue
        }
      }
    } else if (char === '[') {
      bracketCount++;
    } else if (char === ']') {
      bracketCount--;
    }
  }

  return results;
}

function onData(data) {
  buffer += data.toString();

  const messages = parseNestedJSON(buffer);
  for (const msg of messages) {
    if (msg.id && pendingMessages.has(msg.id)) {
      const handler = pendingMessages.get(msg.id);
      pendingMessages.delete(msg.id);

      if (msg.error) {
        handler.reject(new Error(msg.error));
      } else {
        // msg.result contains the nested response
        handler.resolve(msg);
      }
    }
  }

  // Keep only unparsed data
  const lastMessage = messages.length > 0 ? messages[messages.length - 1] : null;
  if (lastMessage) {
    const lastStr = JSON.stringify(lastMessage);
    const idx = buffer.lastIndexOf(lastStr);
    if (idx !== -1) {
      buffer = buffer.substring(idx + lastStr.length);
    }
  }
}

function connectToBlender() {
  return new Promise((resolve, reject) => {
    client = new net.Socket();

    client.on('connect', () => {
      console.log('✓ Connected to Blender MCP on localhost:9876');
      connected = true;
      resolve();
    });

    client.on('data', onData);

    client.on('error', (err) => {
      console.error('✗ Connection error:', err.message);
      connected = false;
      reject(err);
    });

    client.on('close', () => {
      console.log('Connection closed');
      connected = false;
    });

    client.connect(BLENDER_MCP_PORT, BLENDER_MCP_HOST, () => {});

    setTimeout(() => {
      if (!connected) {
        reject(new Error('Connection timeout'));
      }
    }, 5000);
  });
}

async function cleanScene() {
  console.log('\n[Step 1] Cleaning scene...');
  try {
    // Save with empty scene
    await sendMessage('save_file', { use_empty: true });
    console.log('  ✓ Scene cleaned');

    // Nuke all objects via Python
    const result = await sendMessage('execute_python', {
      code: 'import bpy\nfor obj in bpy.context.scene.objects:\n    bpy.data.objects.remove(obj, do_unlink=True)\n__result__ = {"cleaned": True}'
    });

    if (result.result && result.result.result && result.result.result.cleaned) {
      console.log('  ✓ All objects removed');
    }
  } catch (err) {
    console.error('  ✗ Error cleaning scene:', err.message);
  }
}

async function buildCrosswalkGeometry() {
  console.log('\n[Step 2] Building crosswalk geometry...');
  const code = `
import bpy
import bmesh
from mathutils import Vector
import math

# Create ground plane (street)
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
ground = bpy.context.active_object
ground.name = 'Street_Ground'
ground.scale = (10, 15, 1)

# Apply asphalt material
mat_asphalt = bpy.data.materials.get('Asphalt_Forensic')
if mat_asphalt:
    ground.data.materials.append(mat_asphalt)

# Create crosswalk stripes
for i in range(8):
    x_offset = -3.5 + (i * 1.0)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x_offset, -2, 0.01))
    stripe = bpy.context.active_object
    stripe.name = f'Crosswalk_Stripe_{i}'
    stripe.scale = (0.4, 2, 0.01)
    
    # White stripe material
    mat_stripe = bpy.data.materials.new(name='Crosswalk_White_' + str(i))
    mat_stripe.use_nodes = True
    bsdf = mat_stripe.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.7
    stripe.data.materials.append(mat_stripe)

# Create two vehicles
# Vehicle 1 (red car)
bpy.ops.mesh.primitive_cube_add(size=2, location=(-3, -5, 1))
car1 = bpy.context.active_object
car1.name = 'Vehicle_1_RedCar'
car1.scale = (0.8, 2.0, 1.0)

mat_car_paint = bpy.data.materials.get('CarPaint_RedMetallic')
if mat_car_paint:
    car1.data.materials.append(mat_car_paint)

# Add wheels to car1
for wheel_y in [-0.8, 0.8]:
    for wheel_x in [-0.6, 0.6]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(wheel_x - 3, wheel_y - 5, 0.3))
        wheel = bpy.context.active_object
        wheel.name = f'Vehicle_1_Wheel_{wheel_x}_{wheel_y}'

# Vehicle 2 (blue car)
bpy.ops.mesh.primitive_cube_add(size=2, location=(3, -4, 1))
car2 = bpy.context.active_object
car2.name = 'Vehicle_2_BlueCar'
car2.scale = (0.8, 2.0, 1.0)

mat_car_blue = bpy.data.materials.new(name='CarPaint_BlueMetallic')
mat_car_blue.use_nodes = True
bsdf_blue = mat_car_blue.node_tree.nodes['Principled BSDF']
bsdf_blue.inputs['Base Color'].default_value = (0.1, 0.3, 0.8, 1.0)
bsdf_blue.inputs['Metallic'].default_value = 0.95
bsdf_blue.inputs['Roughness'].default_value = 0.25
car2.data.materials.append(mat_car_blue)

# Add wheels to car2
for wheel_y in [-0.8, 0.8]:
    for wheel_x in [-0.6, 0.6]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(wheel_x + 3, wheel_y - 4, 0.3))
        wheel = bpy.context.active_object
        wheel.name = f'Vehicle_2_Wheel_{wheel_x}_{wheel_y}'

# Create traffic signs
bpy.ops.mesh.primitive_cube_add(size=1, location=(-6, -8, 2))
sign1 = bpy.context.active_object
sign1.name = 'TrafficSign_1'
sign1.scale = (0.3, 0.3, 3.0)

bpy.ops.mesh.primitive_cube_add(size=1, location=(6, -8, 2))
sign2 = bpy.context.active_object
sign2.name = 'TrafficSign_2'
sign2.scale = (0.3, 0.3, 3.0)

__result__ = {
    'status': 'success',
    'objects_created': ['Street_Ground', 'Vehicle_1_RedCar', 'Vehicle_2_BlueCar', 'TrafficSign_1', 'TrafficSign_2'],
    'crosswalk_stripes': 8,
    'wheels_created': 8
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Crosswalk geometry created');
    return result;
  } catch (err) {
    console.error('  ✗ Error building crosswalk:', err.message);
  }
}

async function buildRoadGeometry() {
  console.log('\n[Step 2] Building road geometry...');
  const code = `
import bpy

# Create main road
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
road = bpy.context.active_object
road.name = 'Road_Main'
road.scale = (15, 20, 1)

mat_asphalt = bpy.data.materials.get('Asphalt_Forensic')
if mat_asphalt:
    road.data.materials.append(mat_asphalt)

# Lane markings (center dashed line)
for i in range(10):
    y_offset = -8 + (i * 2)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, y_offset, 0.01))
    lane = bpy.context.active_object
    lane.name = f'LaneMarking_{i}'
    lane.scale = (0.2, 0.8, 0.01)
    
    mat_lane = bpy.data.materials.new(name='LaneMarking_Yellow_' + str(i))
    mat_lane.use_nodes = True
    bsdf = mat_lane.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 0.0, 1.0)
    lane.data.materials.append(mat_lane)

# Edge line (white)
bpy.ops.mesh.primitive_plane_add(size=1, location=(-7, 0, 0.01))
edge_left = bpy.context.active_object
edge_left.name = 'EdgeLine_Left'
edge_left.scale = (0.1, 20, 0.01)

mat_edge = bpy.data.materials.new(name='EdgeLine_White')
mat_edge.use_nodes = True
bsdf_edge = mat_edge.node_tree.nodes['Principled BSDF']
bsdf_edge.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
edge_left.data.materials.append(mat_edge)

bpy.ops.mesh.primitive_plane_add(size=1, location=(7, 0, 0.01))
edge_right = bpy.context.active_object
edge_right.name = 'EdgeLine_Right'
edge_right.scale = (0.1, 20, 0.01)
edge_right.data.materials.append(mat_edge)

# Vehicle 1 (sedan)
bpy.ops.mesh.primitive_cube_add(size=2, location=(-3, -4, 1))
sedan = bpy.context.active_object
sedan.name = 'Vehicle_Sedan'
sedan.scale = (0.7, 2.2, 0.9)

mat_sedan = bpy.data.materials.get('CarPaint_RedMetallic')
if mat_sedan:
    sedan.data.materials.append(mat_sedan)

# Sedan wheels
for wheel_y in [-0.9, 0.9]:
    for wheel_x in [-0.45, 0.45]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(wheel_x - 3, wheel_y - 4, 0.35))
        wheel = bpy.context.active_object
        wheel.name = f'Sedan_Wheel_{wheel_x}_{wheel_y}'

# Vehicle 2 (truck)
bpy.ops.mesh.primitive_cube_add(size=2, location=(4, -2, 1.2))
truck = bpy.context.active_object
truck.name = 'Vehicle_Truck'
truck.scale = (0.9, 2.5, 1.2)

mat_truck = bpy.data.materials.new(name='CarPaint_SilverTruck')
mat_truck.use_nodes = True
bsdf_truck = mat_truck.node_tree.nodes['Principled BSDF']
bsdf_truck.inputs['Base Color'].default_value = (0.7, 0.7, 0.75, 1.0)
bsdf_truck.inputs['Metallic'].default_value = 0.8
truck.data.materials.append(mat_truck)

# Truck wheels (larger)
for wheel_y in [-1.0, 1.0]:
    for wheel_x in [-0.5, 0.5]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(wheel_x + 4, wheel_y - 2, 0.4))
        wheel = bpy.context.active_object
        wheel.name = f'Truck_Wheel_{wheel_x}_{wheel_y}'

__result__ = {
    'status': 'success',
    'objects_created': ['Road_Main', 'Vehicle_Sedan', 'Vehicle_Truck'],
    'lane_markings': 10,
    'wheels_created': 8
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Road geometry created');
    return result;
  } catch (err) {
    console.error('  ✗ Error building road:', err.message);
  }
}

async function buildParkingLotGeometry() {
  console.log('\n[Step 2] Building parking lot geometry...');
  const code = `
import bpy

# Create parking lot surface
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
lot = bpy.context.active_object
lot.name = 'ParkingLot_Surface'
lot.scale = (12, 16, 1)

mat_asphalt = bpy.data.materials.get('Asphalt_Forensic')
if mat_asphalt:
    lot.data.materials.append(mat_asphalt)

# Parking space lines (white stripes)
for i in range(6):
    for j in range(8):
        x_offset = -5 + (i * 2)
        y_offset = -6 + (j * 2)
        
        # Horizontal stripe
        bpy.ops.mesh.primitive_plane_add(size=1, location=(x_offset, y_offset, 0.01))
        stripe = bpy.context.active_object
        stripe.name = f'ParkingSpace_{i}_{j}'
        stripe.scale = (1.8, 0.05, 0.01)
        
        mat_space = bpy.data.materials.new(name='ParkingSpace_White_' + str(i*8+j))
        mat_space.use_nodes = True
        bsdf = mat_space.node_tree.nodes['Principled BSDF']
        bsdf.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        stripe.data.materials.append(mat_space)

# Vehicle 1 (parked SUV)
bpy.ops.mesh.primitive_cube_add(size=2, location=(-4, -3, 1.1))
suv = bpy.context.active_object
suv.name = 'Vehicle_ParkedSUV'
suv.scale = (0.85, 2.0, 1.1)

mat_suv = bpy.data.materials.get('CarPaint_RedMetallic')
if mat_suv:
    suv.data.materials.append(mat_suv)

# SUV wheels
for wheel_y in [-0.8, 0.8]:
    for wheel_x in [-0.5, 0.5]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.35, location=(wheel_x - 4, wheel_y - 3, 0.35))
        wheel = bpy.context.active_object
        wheel.name = f'SUV_Wheel_{wheel_x}_{wheel_y}'

# Vehicle 2 (moving truck - sideswipe position)
bpy.ops.mesh.primitive_cube_add(size=2, location=(3, -2, 1.25))
box_truck = bpy.context.active_object
box_truck.name = 'Vehicle_BoxTruck'
box_truck.scale = (1.0, 2.3, 1.25)

mat_box_truck = bpy.data.materials.new(name='CarPaint_WhiteBoxTruck')
mat_box_truck.use_nodes = True
bsdf_box = mat_box_truck.node_tree.nodes['Principled BSDF']
bsdf_box.inputs['Base Color'].default_value = (0.95, 0.95, 0.95, 1.0)
bsdf_box.inputs['Metallic'].default_value = 0.5
box_truck.data.materials.append(mat_box_truck)

# Box truck wheels
for wheel_y in [-0.9, 0.9]:
    for wheel_x in [-0.6, 0.6]:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.4, location=(wheel_x + 3, wheel_y - 2, 0.4))
        wheel = bpy.context.active_object
        wheel.name = f'BoxTruck_Wheel_{wheel_x}_{wheel_y}'

# Pole lights for nighttime
for i, pos in enumerate([(-5, -7, 4), (5, -7, 4), (-5, 7, 4), (5, 7, 4)]):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.1, depth=7, location=pos)
    pole = bpy.context.active_object
    pole.name = f'LightPole_{i}'

__result__ = {
    'status': 'success',
    'objects_created': ['ParkingLot_Surface', 'Vehicle_ParkedSUV', 'Vehicle_BoxTruck'],
    'parking_spaces': 48,
    'wheels_created': 8,
    'light_poles': 4
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Parking lot geometry created');
    return result;
  } catch (err) {
    console.error('  ✗ Error building parking lot:', err.message);
  }
}

async function applyAsphaltMaterial() {
  console.log('\n[Step 3a] Applying asphalt material...');
  const code = `
import bpy
import numpy as np

# Create asphalt material
mat_asphalt = bpy.data.materials.new(name='Asphalt_Forensic')
mat_asphalt.use_nodes = True
bsdf = mat_asphalt.node_tree.nodes['Principled BSDF']

# Base color: dark gray asphalt
bsdf.inputs['Base Color'].default_value = (0.15, 0.15, 0.15, 1.0)
bsdf.inputs['Roughness'].default_value = 0.85
bsdf.inputs['Metallic'].default_value = 0.0

# Add texture nodes for cracking and aggregate
nodes = mat_asphalt.node_tree.nodes
links = mat_asphalt.node_tree.links

# Voronoi texture for cracks (scale 15)
voronoi_crack = nodes.new(type='ShaderNodeTexVoronoi')
voronoi_crack.inputs['Scale'].default_value = 15
voronoi_crack.inputs['Detail'].default_value = 2
voronoi_crack.feature = 'DISTANCE_TO_EDGE'

# ColorRamp to control crack appearance
colorramp_crack = nodes.new(type='ShaderNodeValRamp')
colorramp_crack.color_ramp.elements[0].color = (0.2, 0.2, 0.2, 1.0)
colorramp_crack.color_ramp.elements[1].color = (0.1, 0.1, 0.1, 1.0)

# Noise texture for stone aggregate (scale 200)
noise_agg = nodes.new(type='ShaderNodeTexNoise')
noise_agg.inputs['Scale'].default_value = 200
noise_agg.inputs['Detail'].default_value = 5

# ColorRamp for aggregate
colorramp_agg = nodes.new(type='ShaderNodeValRamp')
colorramp_agg.color_ramp.elements[0].color = (0.15, 0.15, 0.15, 1.0)
colorramp_agg.color_ramp.elements[1].color = (0.25, 0.25, 0.25, 1.0)

# Mix the crack and aggregate roughness
mix_roughness = nodes.new(type='ShaderNodeMix')
mix_roughness.data_type = 'RGBA'
mix_roughness.inputs['Factor'].default_value = 0.5

# Connect nodes
links.new(voronoi_crack.outputs['Distance'], colorramp_crack.inputs['Fac'])
links.new(colorramp_crack.outputs['Color'], mix_roughness.inputs[6])
links.new(noise_agg.outputs['Fac'], colorramp_agg.inputs['Fac'])
links.new(colorramp_agg.outputs['Color'], mix_roughness.inputs[7])
links.new(mix_roughness.outputs['Result'], bsdf.inputs['Roughness'])

__result__ = {
    'status': 'success',
    'material': 'Asphalt_Forensic',
    'nodes_created': 5
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Asphalt material applied');
    return result;
  } catch (err) {
    console.error('  ✗ Error applying asphalt material:', err.message);
  }
}

async function applyCarPaintMaterial() {
  console.log('\n[Step 3b] Applying car paint material...');
  const code = `
import bpy

# Create two-layer car paint material
mat_paint = bpy.data.materials.new(name='CarPaint_RedMetallic')
mat_paint.use_nodes = True
bsdf = mat_paint.node_tree.nodes['Principled BSDF']

# Layer 1: Metallic flake base (red metallic)
bsdf.inputs['Base Color'].default_value = (0.8, 0.1, 0.1, 1.0)
bsdf.inputs['Metallic'].default_value = 0.95
bsdf.inputs['Roughness'].default_value = 0.25

# Layer 2: Clear coat
bsdf.inputs['Coat Weight'].default_value = 0.8
bsdf.inputs['Coat Roughness'].default_value = 0.08

# Add noise texture for flake variation
nodes = mat_paint.node_tree.nodes
links = mat_paint.node_tree.links

# Noise for flake randomness (scale 300)
noise_flake = nodes.new(type='ShaderNodeTexNoise')
noise_flake.inputs['Scale'].default_value = 300
noise_flake.inputs['Detail'].default_value = 6

# ColorRamp to control flake visibility
colorramp_flake = nodes.new(type='ShaderNodeValRamp')
colorramp_flake.color_ramp.elements[0].position = 0.4
colorramp_flake.color_ramp.elements[0].color = (0.75, 0.08, 0.08, 1.0)
colorramp_flake.color_ramp.elements[1].color = (0.95, 0.15, 0.15, 1.0)

# Mix flake variation into roughness
mix_roughness = nodes.new(type='ShaderNodeMix')
mix_roughness.data_type = 'FLOAT'
mix_roughness.inputs['Factor'].default_value = 0.15

# Connect flake noise to roughness
links.new(noise_flake.outputs['Fac'], mix_roughness.inputs[6])
mix_roughness.inputs[7].default_value = 0.25
links.new(mix_roughness.outputs['Result'], bsdf.inputs['Roughness'])

__result__ = {
    'status': 'success',
    'material': 'CarPaint_RedMetallic',
    'metallic': 0.95,
    'coat_weight': 0.8
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Car paint material applied');
    return result;
  } catch (err) {
    console.error('  ✗ Error applying car paint:', err.message);
  }
}

async function applyDayLighting() {
  console.log('\n[Step 4a] Applying day lighting...');
  const code = `
import bpy
import math

# Configure world environment with Nishita sky
world = bpy.data.worlds['World']
world.use_nodes = True
world_nodes = world.node_tree.nodes
world_links = world.node_tree.links

# Clear existing nodes
world_nodes.clear()

# Add Nishita Sky texture
nishita = world_nodes.new(type='ShaderNodeTexSky')
nishita.sky_type = 'NISHITA'
nishita.sun_elevation = math.radians(45)
nishita.sun_rotation = math.radians(0)
nishita.altitude = 0
nishita.turbidity = 2.0
nishita.ground_albedo = 0.3

# Background shader
bg_shader = world_nodes.new(type='ShaderNodeBackground')
bg_shader.inputs['Strength'].default_value = 1.2

# Output node
world_output = world_nodes.new(type='ShaderNodeOutputWorld')

# Connect nodes
world_links.new(nishita.outputs['Color'], bg_shader.inputs['Background'])
world_links.new(bg_shader.outputs['Background'], world_output.inputs['Surface'])

# Create sun lamp
sun_lamp_data = bpy.data.lights.new(name='Sun_Key', type='SUN')
sun_lamp_data.energy = 4.0
sun_lamp_data.angle = math.radians(0.545)

sun_obj = bpy.data.objects.new('Sun_Key', sun_lamp_data)
bpy.context.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(45), 0, 0)

# Create fill area light (cool blue)
fill_light_data = bpy.data.lights.new(name='Fill_Light', type='AREA')
fill_light_data.energy = 200
fill_light_data.size = 12.0
fill_light_data.color = (0.85, 0.9, 1.0)

fill_obj = bpy.data.objects.new('Fill_Light', fill_light_data)
bpy.context.collection.objects.link(fill_obj)
fill_obj.location = (-8.0, 6.0, 5.0)

# Create rim area light (warm)
rim_light_data = bpy.data.lights.new(name='Rim_Light', type='AREA')
rim_light_data.energy = 150
rim_light_data.size = 8.0
rim_light_data.color = (1.0, 0.95, 0.85)

rim_obj = bpy.data.objects.new('Rim_Light', rim_light_data)
bpy.context.collection.objects.link(rim_obj)
rim_obj.location = (8.0, -6.0, 4.0)

__result__ = {
    'status': 'success',
    'world_sky': 'Nishita',
    'sun_lamp': sun_obj.name,
    'fill_lamp': fill_obj.name,
    'rim_lamp': rim_obj.name,
    'total_lights': 3
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Day lighting applied');
    return result;
  } catch (err) {
    console.error('  ✗ Error applying day lighting:', err.message);
  }
}

async function applyNightLighting() {
  console.log('\n[Step 4b] Applying night lighting...');
  const code = `
import bpy
import math

# Set world to dark ambient
world = bpy.data.worlds['World']
world.use_nodes = True
world_nodes = world.node_tree.nodes
world_links = world.node_tree.links

# Clear nodes
world_nodes.clear()

# Dark background (night sky)
bg_shader = world_nodes.new(type='ShaderNodeBackground')
bg_shader.inputs['Background'].default_value = (0.01, 0.01, 0.02, 1.0)
bg_shader.inputs['Strength'].default_value = 0.05

world_output = world_nodes.new(type='ShaderNodeOutputWorld')
world_links.new(bg_shader.outputs['Background'], world_output.inputs['Surface'])

# Sodium vapor lamp color: [1.0, 0.82, 0.45]
sodium_color = (1.0, 0.82, 0.45)

# Create multiple sodium vapor lamps (parking lot pole lights)
lamp_positions = [
    (-6.0, -6.0, 6.0),
    (6.0, -6.0, 6.0),
    (-6.0, 6.0, 6.0),
    (6.0, 6.0, 6.0)
]

lamp_names = []
for i, pos in enumerate(lamp_positions):
    lamp_data = bpy.data.lights.new(name='SodiumVapor_' + str(i), type='AREA')
    lamp_data.energy = 500
    lamp_data.size = 2.0
    lamp_data.color = sodium_color
    
    lamp_obj = bpy.data.objects.new('SodiumVapor_' + str(i), lamp_data)
    bpy.context.collection.objects.link(lamp_obj)
    lamp_obj.location = pos
    lamp_names.append(lamp_obj.name)

# Create security spotlight (slight blue tint)
security_light_data = bpy.data.lights.new(name='SecuritySpotlight', type='SPOT')
security_light_data.energy = 300
security_light_data.spot_size = math.radians(60)
security_light_data.spot_blend = 0.5
security_light_data.color = (0.95, 0.98, 1.0)

security_obj = bpy.data.objects.new('SecuritySpotlight', security_light_data)
bpy.context.collection.objects.link(security_obj)
security_obj.location = (0.0, -8.0, 5.0)
security_obj.rotation_euler = (math.radians(60), 0, 0)

__result__ = {
    'status': 'success',
    'world_ambient': 'Dark',
    'sodium_lamps': lamp_names,
    'security_spotlight': security_obj.name,
    'total_lights': len(lamp_names) + 1
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Night lighting applied');
    return result;
  } catch (err) {
    console.error('  ✗ Error applying night lighting:', err.message);
  }
}

async function addEvidenceMarkers() {
  console.log('\n[Step 5] Adding evidence markers...');
  const code = `
import bpy

# Create evidence marker materials
mat_label = bpy.data.materials.new(name='Evidence_Label_Yellow')
mat_label.use_nodes = True
bsdf = mat_label.node_tree.nodes['Principled BSDF']
bsdf.inputs['Base Color'].default_value = (1.0, 0.95, 0.0, 1.0)
bsdf.inputs['Metallic'].default_value = 0.3
bsdf.inputs['Roughness'].default_value = 0.4

# Create evidence text objects
evidence_markers = []

# Marker positions and labels
marker_data = [
    {'label': 'A1', 'location': (0.0, 0.0, 0.1), 'size': 0.3},
    {'label': 'A2', 'location': (2.0, 0.0, 0.1), 'size': 0.3},
    {'label': 'A3', 'location': (4.0, 0.0, 0.1), 'size': 0.3},
]

for marker in marker_data:
    # Create text object
    text_data = bpy.data.curves.new(name='Text_' + marker['label'], type='FONT')
    text_data.body = marker['label']
    text_data.size = marker['size']
    text_data.align_x = 'CENTER'
    text_data.align_y = 'CENTER'
    
    text_obj = bpy.data.objects.new('Marker_' + marker['label'], text_data)
    bpy.context.collection.objects.link(text_obj)
    text_obj.location = marker['location']
    
    # Assign material
    if len(text_obj.data.materials) == 0:
        text_obj.data.materials.append(mat_label)
    else:
        text_obj.data.materials[0] = mat_label
    
    # Convert to curve with thickness
    text_data.bevel_depth = 0.02
    text_data.bevel_resolution = 4
    
    evidence_markers.append(text_obj.name)

# Create measurement line (simple cylinder)
bpy.ops.mesh.primitive_cylinder_add(radius=0.02, depth=1.0, location=(0.0, -1.0, 0.05))
measure_line = bpy.context.active_object
measure_line.name = 'MeasureLine_Ref'

# Material for measurement line
mat_line = bpy.data.materials.new(name='MeasureLine_White')
mat_line.use_nodes = True
bsdf_line = mat_line.node_tree.nodes['Principled BSDF']
bsdf_line.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
bsdf_line.inputs['Emission'].default_value = (1.0, 1.0, 1.0, 1.0)
bsdf_line.inputs['Emission Strength'].default_value = 0.2
measure_line.data.materials.append(mat_line)

__result__ = {
    'status': 'success',
    'evidence_markers': evidence_markers,
    'marker_count': len(evidence_markers),
    'measurement_line': measure_line.name,
    'total_evidence_objects': len(evidence_markers) + 1
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Evidence markers added');
    return result;
  } catch (err) {
    console.error('  ✗ Error adding evidence markers:', err.message);
  }
}

async function setupCameras(cameraNames) {
  console.log('\n[Step 6] Setting up cameras...');
  const code = `
import bpy
import math

cameras = {}

# BirdEye camera - overhead view
bpy.ops.object.camera_add(location=(0, 0, 15))
bird_cam = bpy.context.active_object
bird_cam.name = 'BirdEye'
bird_cam.rotation_euler = (0, 0, 0)
cameras['BirdEye'] = bird_cam.name

# DriverPOV camera - eye level from vehicle
bpy.ops.object.camera_add(location=(-3, -5, 1.5))
driver_cam = bpy.context.active_object
driver_cam.name = 'DriverPOV'
driver_cam.rotation_euler = (0, 0, 0)
cameras['DriverPOV'] = driver_cam.name

# TruckPOV camera - higher from truck
bpy.ops.object.camera_add(location=(4, -2, 2.5))
truck_cam = bpy.context.active_object
truck_cam.name = 'TruckPOV'
truck_cam.rotation_euler = (0, 0, 0)
cameras['TruckPOV'] = truck_cam.name

# Wide camera - far angle
bpy.ops.object.camera_add(location=(8, 8, 8))
wide_cam = bpy.context.active_object
wide_cam.name = 'Wide'
wide_cam.rotation_euler = (math.radians(30), 0, math.radians(45))
cameras['Wide'] = wide_cam.name

# SecurityCam - mounted high on pole
bpy.ops.object.camera_add(location=(0, -8, 6))
security_cam = bpy.context.active_object
security_cam.name = 'SecurityCam'
security_cam.rotation_euler = (math.radians(50), 0, 0)
cameras['SecurityCam'] = security_cam.name

__result__ = {
    'status': 'success',
    'cameras': cameras,
    'total_cameras': len(cameras)
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Cameras setup');
    return result;
  } catch (err) {
    console.error('  ✗ Error setting up cameras:', err.message);
  }
}

async function setRenderSettings() {
  console.log('\n[Step 7] Setting render settings (EEVEE)...');
  const code = `
import bpy

# Set EEVEE render engine
bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'

# Resolution: 1920x1080
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080

# EEVEE settings
eevee = bpy.context.scene.eevee
eevee.use_bloom = True
eevee.use_ambient_occlusion = True
eevee.use_gtao = True
eevee.gtao_distance = 0.25
eevee.use_ssr = True
eevee.ssr_thickness = 0.2

# Samples (for EEVEE)
bpy.context.scene.render.samples = 128

# Output format
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.image_settings.color_depth = '8'

__result__ = {
    'status': 'success',
    'engine': 'BLENDER_EEVEE_NEXT',
    'resolution': [1920, 1080],
    'samples': 128,
    'format': 'PNG'
}
`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Render settings configured');
    return result;
  } catch (err) {
    console.error('  ✗ Error setting render settings:', err.message);
  }
}

async function renderScene(sceneNumber, cameraNames) {
  console.log(`\n[Step 8] Rendering scene ${sceneNumber} from cameras: ${cameraNames.join(', ')}`);

  for (const cameraName of cameraNames) {
    try {
      console.log(`  Rendering from ${cameraName}...`);

      const code = `
import bpy

# Set active camera
cam = bpy.data.objects.get('${cameraName}')
if cam:
    bpy.context.scene.camera = cam
    
    # Output path
    output_path = '${RENDERS_DIR}/scene${sceneNumber}_${cameraName}.png'
    bpy.context.scene.render.filepath = output_path
    
    # Render
    bpy.ops.render.render(write_still=True)
    
    __result__ = {
        'status': 'success',
        'camera': '${cameraName}',
        'output': output_path
    }
else:
    __result__ = {'status': 'error', 'message': 'Camera not found: ${cameraName}'}
`;

      const result = await sendMessage('execute_python', { code });

      if (result.result && result.result.result && result.result.result.status === 'success') {
        console.log(`    ✓ Rendered to ${RENDERS_DIR}/scene${sceneNumber}_${cameraName}.png`);
      } else {
        console.error(`    ✗ Render failed for ${cameraName}`);
      }
    } catch (err) {
      console.error(`    ✗ Error rendering ${cameraName}:`, err.message);
    }
  }
}

async function saveBlendFile(sceneNumber) {
  console.log(`\n[Step 9] Saving .blend file...`);

  const blendPath = `/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v9_scene${sceneNumber}.blend`;

  try {
    await sendMessage('save_file', { filepath: blendPath });
    console.log(`  ✓ Saved to ${blendPath}`);
  } catch (err) {
    console.error(`  ✗ Error saving blend file:`, err.message);
  }
}

async function buildScene(sceneNumber) {
  const scene = SCENES[sceneNumber];

  console.log(`\n${'='.repeat(70)}`);
  console.log(`BUILDING SCENE ${sceneNumber}: ${scene.name}`);
  console.log(`Description: ${scene.description}`);
  console.log(`${'='.repeat(70)}`);

  try {
    // Step 1: Clean scene
    await cleanScene();

    // Step 2: Build geometry
    if (scene.geometry === 'crosswalk') {
      await buildCrosswalkGeometry();
    } else if (scene.geometry === 'road') {
      await buildRoadGeometry();
    } else if (scene.geometry === 'parking_lot') {
      await buildParkingLotGeometry();
    }

    // Step 3: Apply materials
    await applyAsphaltMaterial();
    await applyCarPaintMaterial();

    // Step 4: Apply lighting
    if (scene.lighting_type === 'day') {
      await applyDayLighting();
    } else if (scene.lighting_type === 'night') {
      await applyNightLighting();
    }

    // Step 5: Add evidence markers
    await addEvidenceMarkers();

    // Step 6: Setup cameras
    await setupCameras(scene.cameras);

    // Step 7: Set render settings
    await setRenderSettings();

    // Step 8: Render from each camera
    await renderScene(sceneNumber, scene.cameras);

    // Step 9: Save blend file
    await saveBlendFile(sceneNumber);

    console.log(`\n✓ Scene ${sceneNumber} completed successfully!\n`);
  } catch (err) {
    console.error(`\n✗ Error building scene ${sceneNumber}:`, err.message);
  }
}

async function main() {
  const args = process.argv.slice(2);
  const sceneNumber = parseInt(args[0]);

  if (!sceneNumber || sceneNumber < 1 || sceneNumber > 4) {
    console.error('Usage: node v9_scene_builder.js <scene_number>');
    console.error('Scene numbers: 1, 2, 3, 4');
    process.exit(1);
  }

  try {
    console.log('\n' + '='.repeat(70));
    console.log('FORENSIC SCENE BUILDER v9 - Blender MCP Integration');
    console.log('='.repeat(70));

    await connectToBlender();
    await buildScene(sceneNumber);

    console.log('\n' + '='.repeat(70));
    console.log('All tasks completed. Closing connection...');
    console.log('='.repeat(70));

    client.end();
    process.exit(0);
  } catch (err) {
    console.error('\nFatal error:', err.message);
    if (client) client.end();
    process.exit(1);
  }
}

main();
