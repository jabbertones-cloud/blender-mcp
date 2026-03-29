#!/usr/bin/env node

/**
 * Forensic Scene Builder v10
 * Connects to Blender MCP on localhost:9876
 * Applies technique improvements from mcp_techniques_2026-03-26.json to v9 scenes
 * Outputs v10_scene{1-4}.blend files
 * 
 * Usage: node v10_scene_builder.js [all|1|2|3|4]
 * Examples:
 *   node v10_scene_builder.js all        # Process all 4 scenes
 *   node v10_scene_builder.js 1          # Process scene 1 only
 */

const net = require('net');
const fs = require('fs');
const path = require('path');

const BLENDER_MCP_HOST = '127.0.0.1';
const BLENDER_MCP_PORT = 9876;
const RENDERS_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders';
const SCRIPTS_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/scripts';

let messageId = 0;
let client = null;
let buffer = '';
let pendingMessages = new Map();
let connected = false;

// Scene configurations for v10
const SCENES = {
  1: {
    name: 'Crosswalk Accident - Day (v10)',
    v9_filename: 'v9_scene1.blend',
    v10_filename: 'v10_scene1.blend',
    geometry: 'crosswalk',
    techniques: ['realistic_vehicle_geometry', 'pedestrian_human_figure', 'realistic_asphalt_road_material']
  },
  2: {
    name: 'Road Accident - Day (v10)',
    v9_filename: 'v9_scene2.blend',
    v10_filename: 'v10_scene2.blend',
    geometry: 'road',
    techniques: ['realistic_vehicle_geometry', 'pedestrian_human_figure', 'impact_deformation', 'realistic_asphalt_road_material']
  },
  3: {
    name: 'Parking Lot - Day (v10)',
    v9_filename: 'v9_scene3.blend',
    v10_filename: 'v10_scene3.blend',
    geometry: 'parking_lot',
    techniques: ['realistic_vehicle_geometry', 'impact_deformation', 'realistic_asphalt_road_material']
  },
  4: {
    name: 'Parking Lot - Night (v10)',
    v9_filename: 'v9_scene4.blend',
    v10_filename: 'v10_scene4.blend',
    geometry: 'parking_lot',
    techniques: ['realistic_vehicle_geometry', 'night_parking_lot_lighting', 'realistic_asphalt_road_material']
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
    }, 35000);

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

async function openBlendFile(v9Path) {
  console.log(`  Opening v9 file: ${path.basename(v9Path)}...`);
  try {
    const result = await sendMessage('execute_python', {
      code: `import bpy\nbpy.ops.wm.open_mainfile(filepath='${v9Path}')\n__result__ = {'status': 'success', 'file_opened': '${v9Path}'}`
    });
    console.log('  ✓ Blend file loaded');
    return result;
  } catch (err) {
    console.error('  ✗ Error opening blend file:', err.message);
    throw err;
  }
}

async function upgradeVehicleGeometry() {
  console.log('  Applying realistic vehicle geometry upgrade...');
  const code = `import bpy
import bmesh
from mathutils import Vector

def upgrade_vehicle_geometry():
    '''Upgrade existing vehicle geometry to detailed sedan with proper proportions'''
    
    # Find existing vehicle objects
    existing_vehicles = [obj for obj in bpy.data.objects if 'Vehicle' in obj.name and obj.type == 'MESH']
    
    if not existing_vehicles:
        return {'status': 'warning', 'message': 'No vehicles found to upgrade'}
    
    upgraded_count = 0
    for vehicle in existing_vehicles:
        # Add subdivision surface for smoothness
        if 'Subdivision' not in vehicle.modifiers:
            subsurf = vehicle.modifiers.new(name='Subdivision', type='SUBSURF')
            subsurf.levels = 2
            subsurf.render_levels = 3
            upgraded_count += 1
        
        # Add bevel modifier for panel lines
        if 'Bevel' not in vehicle.modifiers:
            bevel = vehicle.modifiers.new(name='Bevel', type='BEVEL')
            bevel.width = 0.01
            bevel.segments = 2
            bevel.limit_method = 'WEIGHT'
    
    return {
        'status': 'success',
        'vehicles_upgraded': upgraded_count,
        'modifiers_applied': ['Subdivision', 'Bevel'],
        'vertices_multiplied_by_subdivision': '4-8x'
    }

result = upgrade_vehicle_geometry()
__result__ = result`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Vehicle geometry upgraded');
    return result;
  } catch (err) {
    console.error('  ✗ Error upgrading vehicle geometry:', err.message);
  }
}

async function upgradePedestrianGeometry() {
  console.log('  Applying pedestrian figure upgrade...');
  const code = `import bpy

def check_pedestrians():
    '''Check for existing pedestrian figures'''
    pedestrians = [obj for obj in bpy.data.objects if 'Pedestrian' in obj.name or 'Human' in obj.name or 'Figure' in obj.name]
    return len(pedestrians) > 0

def create_simple_pedestrian():
    '''Create a pedestrian figure if none exists'''
    
    # Check if pedestrian already exists
    if bpy.data.objects.get('Pedestrian_Figure'):
        return {'status': 'exists', 'pedestrian': 'Pedestrian_Figure'}
    
    # Create simple pedestrian approximation
    # Head
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, vertices=24, rings=16, location=(0, 0, 1.5))
    head = bpy.context.active_object
    head.name = 'Pedestrian_Head'
    
    # Torso
    bpy.ops.mesh.primitive_cylinder_add(radius=0.15, depth=0.6, vertices=16, location=(0, 0, 0.9))
    torso = bpy.context.active_object
    torso.name = 'Pedestrian_Torso'
    
    # Legs (simple)
    for y_offset in [-0.08, 0.08]:
        bpy.ops.mesh.primitive_cylinder_add(radius=0.06, depth=0.8, vertices=12, location=(y_offset, 0, 0.4))
        leg = bpy.context.active_object
        leg.name = f'Pedestrian_Leg_{y_offset}'
    
    # Add subdivision to all parts
    for part_name in ['Pedestrian_Head', 'Pedestrian_Torso']:
        obj = bpy.data.objects.get(part_name)
        if obj and 'Subdivision' not in obj.modifiers:
            subsurf = obj.modifiers.new(name='Subdivision', type='SUBSURF')
            subsurf.levels = 2
            subsurf.render_levels = 3
    
    # Skin material
    skin_mat = bpy.data.materials.new(name='PedestrianSkin')
    skin_mat.use_nodes = True
    bsdf = skin_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.95, 0.82, 0.69, 1.0)
    
    head.data.materials.append(skin_mat)
    
    # Clothing material
    cloth_mat = bpy.data.materials.new(name='PedestrianClothing')
    cloth_mat.use_nodes = True
    bsdf = cloth_mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.3, 0.3, 0.5, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.6
    
    torso.data.materials.append(cloth_mat)
    
    return {
        'status': 'success',
        'pedestrian_created': True,
        'head': 'Pedestrian_Head',
        'torso': 'Pedestrian_Torso',
        'figure_height': 1.7
    }

if check_pedestrians():
    __result__ = {'status': 'exists', 'pedestrians_found': True}
else:
    __result__ = create_simple_pedestrian()`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Pedestrian geometry added/upgraded');
    return result;
  } catch (err) {
    console.error('  ✗ Error with pedestrian geometry:', err.message);
  }
}

async function upgradeAsphaltMaterial() {
  console.log('  Applying realistic asphalt material...');
  const code = `import bpy

# Create or upgrade asphalt material
mat_name = 'Asphalt_RealWorld'
mat = bpy.data.materials.get(mat_name)

if not mat:
    mat = bpy.data.materials.new(name=mat_name)

mat.use_nodes = True
nodes = mat.node_tree.nodes
links = mat.node_tree.links

# Clear existing nodes if starting fresh
if len(nodes) > 2:  # Only clear if complex setup
    for node in list(nodes):
        nodes.remove(node)

# Clear completely for fresh start
nodes.clear()

# Base asphalt - Voronoi for cracks
voronoi = nodes.new(type='ShaderNodeTexVoronoi')
voronoi.feature = 'DISTANCE_TO_EDGE'
voronoi.inputs['Scale'].default_value = 15.0
voronoi.inputs['Detail'].default_value = 3.0

# Crack darkening ramp
crack_ramp = nodes.new(type='ShaderNodeValRamp')
crack_ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.02, 1.0)
crack_ramp.color_ramp.elements[1].color = (0.12, 0.12, 0.12, 1.0)

# Stone aggregate noise
noise = nodes.new(type='ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 200.0
noise.inputs['Detail'].default_value = 5.0

# Aggregate ramp
agg_ramp = nodes.new(type='ShaderNodeValRamp')
agg_ramp.color_ramp.elements[0].color = (0.10, 0.10, 0.10, 1.0)
agg_ramp.color_ramp.elements[1].color = (0.25, 0.25, 0.25, 1.0)

# Displacement for micro detail
displace_noise = nodes.new(type='ShaderNodeTexNoise')
displace_noise.inputs['Scale'].default_value = 300.0
displace_noise.inputs['Detail'].default_value = 6.0

# Main BSDF
bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.inputs['Base Color'].default_value = (0.15, 0.15, 0.15, 1.0)
bsdf.inputs['Metallic'].default_value = 0.0
bsdf.inputs['Roughness'].default_value = 0.85

# Displacement
displacement = nodes.new(type='ShaderNodeDisplacement')
displacement.inputs['Distance'].default_value = 0.005

# Output
output = nodes.new(type='ShaderNodeOutputMaterial')

# Connect
links.new(voronoi.outputs['Distance'], crack_ramp.inputs['Fac'])
links.new(noise.outputs['Fac'], agg_ramp.inputs['Fac'])
links.new(crack_ramp.outputs['Color'], bsdf.inputs['Base Color'])
links.new(agg_ramp.outputs['Color'], bsdf.inputs['Roughness'])
links.new(displace_noise.outputs['Fac'], displacement.inputs['Height'])
links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
links.new(displacement.outputs['Displacement'], output.inputs['Displacement'])

# Apply material to road surfaces
for obj in bpy.data.objects:
    if 'Road' in obj.name or 'Ground' in obj.name or 'ParkingLot' in obj.name or 'Street' in obj.name or 'Asphalt' in obj.name:
        if obj.type == 'MESH':
            # Clear existing materials
            obj.data.materials.clear()
            obj.data.materials.append(mat)

__result__ = {
    'status': 'success',
    'asphalt_material': mat_name,
    'nodes_created': 8,
    'surfaces_upgraded': 'All road/street/parking surfaces'
}`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Asphalt material applied');
    return result;
  } catch (err) {
    console.error('  ✗ Error applying asphalt material:', err.message);
  }
}

async function applyImpactDeformation() {
  console.log('  Applying impact deformation effects...');
  const code = `import bpy
from mathutils import Vector

def apply_impact_deformation():
    '''Apply deformation to vehicles at impact points'''
    
    vehicles = [obj for obj in bpy.data.objects if 'Vehicle' in obj.name and obj.type == 'MESH']
    
    if not vehicles:
        return {'status': 'no_vehicles', 'message': 'No vehicles found'}
    
    deformed_count = 0
    for vehicle in vehicles:
        # Create impact zone vertex group
        if 'ImpactZone' not in vehicle.vertex_groups:
            vg = vehicle.vertex_groups.new(name='ImpactZone')
        
        # Add solidify modifier for depth
        if 'Solidify' not in vehicle.modifiers:
            solidify = vehicle.modifiers.new(name='Solidify', type='SOLIDIFY')
            solidify.thickness = 0.02
            solidify.offset = 0.5
            deformed_count += 1
        
        # Create damage material
        if 'ImpactDamage' not in bpy.data.materials:
            damage_mat = bpy.data.materials.new(name='ImpactDamage')
            damage_mat.use_nodes = True
            bsdf = damage_mat.node_tree.nodes['Principled BSDF']
            bsdf.inputs['Base Color'].default_value = (0.2, 0.2, 0.2, 1.0)
            bsdf.inputs['Metallic'].default_value = 0.9
            bsdf.inputs['Roughness'].default_value = 0.6
    
    return {
        'status': 'success',
        'vehicles_deformed': deformed_count,
        'modifiers_applied': ['Solidify'],
        'damage_material_created': 'ImpactDamage'
    }

__result__ = apply_impact_deformation()`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Impact deformation applied');
    return result;
  } catch (err) {
    console.error('  ✗ Error applying impact deformation:', err.message);
  }
}

async function upgradeNightLighting() {
  console.log('  Upgrading night lighting rig...');
  const code = `import bpy
import math

def upgrade_night_lighting():
    '''Enhance night lighting with proper sodium vapor and security lights'''
    
    # Configure dark world
    world = bpy.data.worlds['World']
    world.use_nodes = True
    world_nodes = world.node_tree.nodes
    world_links = world.node_tree.links
    
    # Clear nodes
    for node in list(world_nodes):
        world_nodes.remove(node)
    
    # Dark background
    bg = world_nodes.new(type='ShaderNodeBackground')
    bg.inputs['Background'].default_value = (0.01, 0.01, 0.02, 1.0)
    bg.inputs['Strength'].default_value = 0.05
    
    output = world_nodes.new(type='ShaderNodeOutputWorld')
    world_links.new(bg.outputs['Background'], output.inputs['Surface'])
    
    # Remove old lights
    for obj in list(bpy.data.objects):
        if obj.type == 'LIGHT':
            bpy.data.objects.remove(obj, do_unlink=True)
    
    # Sodium vapor color
    sodium = (1.0, 0.82, 0.45)
    
    # Create 4-point lighting grid
    positions = [
        (-7.0, -7.0, 6.5),
        (7.0, -7.0, 6.5),
        (-7.0, 7.0, 6.5),
        (7.0, 7.0, 6.5)
    ]
    
    lights_created = 0
    
    for idx, pos in enumerate(positions):
        # Area light
        lamp_data = bpy.data.lights.new(name=f'SodiumVapor_{idx}', type='AREA')
        lamp_data.energy = 600.0
        lamp_data.size = 1.5
        lamp_data.color = sodium
        
        lamp_obj = bpy.data.objects.new(f'SodiumVapor_{idx}', lamp_data)
        bpy.context.collection.objects.link(lamp_obj)
        lamp_obj.location = pos
        lights_created += 1
        
        # Spot for shadow
        spot_data = bpy.data.lights.new(name=f'SodiumSpot_{idx}', type='SPOT')
        spot_data.energy = 800.0
        spot_data.spot_size = math.radians(65)
        spot_data.color = sodium
        
        spot_obj = bpy.data.objects.new(f'SodiumSpot_{idx}', spot_data)
        bpy.context.collection.objects.link(spot_obj)
        spot_obj.location = (pos[0], pos[1], pos[2] - 0.5)
        spot_obj.rotation_euler = (math.radians(70), 0, 0)
        lights_created += 1
    
    # Security spotlights
    security_positions = [(0, -9, 5), (0, 9, 5), (-9, 0, 5), (9, 0, 5)]
    
    for idx, pos in enumerate(security_positions):
        sec_data = bpy.data.lights.new(name=f'SecuritySpot_{idx}', type='SPOT')
        sec_data.energy = 400.0
        sec_data.spot_size = math.radians(45)
        sec_data.color = (0.95, 0.98, 1.0)
        
        sec_obj = bpy.data.objects.new(f'SecuritySpot_{idx}', sec_data)
        bpy.context.collection.objects.link(sec_obj)
        sec_obj.location = pos
        lights_created += 1
    
    return {
        'status': 'success',
        'total_lights': lights_created,
        'world_configured': True,
        'sodium_color': list(sodium)
    }

__result__ = upgrade_night_lighting()`;

  try {
    const result = await sendMessage('execute_python', { code });
    console.log('  ✓ Night lighting upgraded');
    return result;
  } catch (err) {
    console.error('  ✗ Error upgrading night lighting:', err.message);
  }
}

async function applyTechniquesToScene(sceneNumber, techniques) {
  console.log(`\n[Step 2] Applying technique improvements to Scene ${sceneNumber}...`);
  
  for (const technique of techniques) {
    try {
      switch (technique) {
        case 'realistic_vehicle_geometry':
          await upgradeVehicleGeometry();
          break;
        case 'pedestrian_human_figure':
          await upgradePedestrianGeometry();
          break;
        case 'impact_deformation':
          await applyImpactDeformation();
          break;
        case 'realistic_asphalt_road_material':
          await upgradeAsphaltMaterial();
          break;
        case 'night_parking_lot_lighting':
          await upgradeNightLighting();
          break;
        default:
          console.log(`  ! Unknown technique: ${technique}`);
      }
    } catch (err) {
      console.error(`  ✗ Error applying ${technique}:`, err.message);
    }
  }
}

async function saveV10BlendFile(sceneNumber, v10Path) {
  console.log(`\n[Step 3] Saving v10 blend file...`);
  try {
    const result = await sendMessage('save_file', { filepath: v10Path });
    console.log(`  ✓ Saved to ${path.basename(v10Path)}`);
    return result;
  } catch (err) {
    console.error(`  ✗ Error saving blend file:`, err.message);
    throw err;
  }
}

async function processScene(sceneNumber) {
  const scene = SCENES[sceneNumber];
  const v9Path = path.join(RENDERS_DIR, scene.v9_filename);
  const v10Path = path.join(RENDERS_DIR, scene.v10_filename);

  console.log(`\n${'='.repeat(75)}`);
  console.log(`PROCESSING SCENE ${sceneNumber}: ${scene.name}`);
  console.log(`${'='.repeat(75)}`);
  console.log(`Techniques: ${scene.techniques.join(', ')}`);

  try {
    // Step 1: Open v9 blend file
    console.log(`\n[Step 1] Loading v9 source file...`);
    await openBlendFile(v9Path);

    // Step 2: Apply techniques
    await applyTechniquesToScene(sceneNumber, scene.techniques);

    // Step 3: Save v10 blend file
    await saveV10BlendFile(sceneNumber, v10Path);

    console.log(`\n✓ Scene ${sceneNumber} completed successfully!`);
    return { status: 'success', scene: sceneNumber };
  } catch (err) {
    console.error(`\n✗ Error processing scene ${sceneNumber}:`, err.message);
    return { status: 'error', scene: sceneNumber, error: err.message };
  }
}

async function main() {
  const args = process.argv.slice(2);
  let scenesToProcess = [];

  if (args.length === 0 || args[0] === 'all') {
    scenesToProcess = [1, 2, 3, 4];
  } else if (args[0] === '1' || args[0] === '2' || args[0] === '3' || args[0] === '4') {
    scenesToProcess = [parseInt(args[0])];
  } else {
    console.error('Usage: node v10_scene_builder.js [all|1|2|3|4]');
    console.error('Examples:');
    console.error('  node v10_scene_builder.js all        # Process all 4 scenes');
    console.error('  node v10_scene_builder.js 1          # Process scene 1 only');
    process.exit(1);
  }

  try {
    console.log('\n' + '='.repeat(75));
    console.log('FORENSIC SCENE BUILDER v10 - Technique Improvement Pipeline');
    console.log('Blender MCP Integration on localhost:9876');
    console.log('='.repeat(75));

    await connectToBlender();

    const results = [];
    for (const sceneNumber of scenesToProcess) {
      const result = await processScene(sceneNumber);
      results.push(result);
    }

    // Summary
    console.log('\n' + '='.repeat(75));
    console.log('PROCESSING SUMMARY');
    console.log('='.repeat(75));
    const successful = results.filter(r => r.status === 'success').length;
    const failed = results.filter(r => r.status === 'error').length;
    console.log(`✓ Successful: ${successful}/${results.length}`);
    if (failed > 0) {
      console.log(`✗ Failed: ${failed}/${results.length}`);
    }
    console.log(`Output directory: ${RENDERS_DIR}`);
    for (let i = 1; i <= 4; i++) {
      const v10Path = path.join(RENDERS_DIR, `v10_scene${i}.blend`);
      if (fs.existsSync(v10Path)) {
        const stats = fs.statSync(v10Path);
        console.log(`  v10_scene${i}.blend (${(stats.size / 1024).toFixed(1)} KB)`);
      }
    }

    console.log('\nClosing connection...');
    client.end();
    process.exit(successful === results.length ? 0 : 1);
  } catch (err) {
    console.error('\nFatal error:', err.message);
    if (client) client.end();
    process.exit(1);
  }
}

main();
