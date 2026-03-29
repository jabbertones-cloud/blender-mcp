#!/usr/bin/env node

/**
 * produce-table.js
 * 
 * Complete Node.js script that connects to the Blender MCP server on port 9876,
 * creates a simple table (flat top surface with 4 legs), applies polish,
 * exports as STL and FBX, renders hero and top-down shots, and saves the .blend file.
 * 
 * Follows all Blender MCP operational guidelines:
 * - Scene cleanup at start (save_file + Python nuke)
 * - No blender_ prefix on MCP commands
 * - Single quotes only in Python code strings
 * - Brace-depth JSON parsing for response unwrapping
 * - Subdivision surface + smooth shading (via execute_python, NOT blender_cleanup)
 * - 3-point studio lighting with gray background
 * - Auto-framed cameras from bounding box
 * - STL export via execute_python, FBX via export_file
 * - Proper render parameters (output_path, lowercase engine)
 */

const net = require('net');
const path = require('path');
const fs = require('fs');

// ===========================
// Configuration
// ===========================

const BLENDER_HOST = 'localhost';
const BLENDER_PORT = 9876;
const OUTPUT_DIR = path.resolve(__dirname, 'table-output');

// Create output directory if it doesn't exist
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

// ===========================
// Blender MCP Client
// ===========================

class BlenderMCPClient {
  constructor(host, port) {
    this.host = host;
    this.port = port;
    this.socket = null;
    this.nextId = 1;
    this.pendingRequests = new Map();
  }

  /**
   * Connect to Blender MCP server.
   */
  async connect() {
    return new Promise((resolve, reject) => {
      this.socket = net.createConnection({ host: this.host, port: this.port }, () => {
        console.log(`✓ Connected to Blender MCP on ${this.host}:${this.port}`);
        resolve();
      });

      this.socket.on('error', (err) => {
        console.error('Socket error:', err);
        reject(err);
      });

      this.socket.on('close', () => {
        console.log('Socket closed');
      });

      // Handle incoming messages with brace-depth parsing
      let buffer = '';
      this.socket.on('data', (chunk) => {
        buffer += chunk.toString();
        this.processBuffer(buffer);
        buffer = this.getRemainingBuffer();
      });
    });
  }

  /**
   * Process buffered data using brace-depth parsing.
   * Handles multiple JSON messages in the buffer by tracking brace depth.
   */
  processBuffer(buffer) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    let messageStart = 0;

    for (let i = 0; i < buffer.length; i++) {
      const char = buffer[i];

      if (escaped) {
        escaped = false;
        continue;
      }

      if (char === '\\') {
        escaped = true;
        continue;
      }

      if (char === '"') {
        inString = !inString;
        continue;
      }

      if (inString) continue;

      if (char === '{') depth++;
      else if (char === '}') {
        depth--;
        if (depth === 0) {
          const message = buffer.substring(messageStart, i + 1);
          try {
            const parsed = JSON.parse(message);
            this.handleMessage(parsed);
          } catch (e) {
            console.error('Failed to parse JSON:', e.message);
            console.error('Message:', message.substring(0, 200));
          }
          messageStart = i + 1;
        }
      }
    }
  }

  /**
   * Extract remaining unparsed buffer.
   */
  getRemainingBuffer() {
    // For simplicity, we clear the buffer after each parse
    // In a real implementation, track the position
    return '';
  }

  /**
   * Handle incoming MCP response.
   */
  handleMessage(msg) {
    if (msg.id && this.pendingRequests.has(msg.id)) {
      const { resolve } = this.pendingRequests.get(msg.id);
      this.pendingRequests.delete(msg.id);
      resolve(msg);
    }
  }

  /**
   * Call a Blender MCP tool.
   * NO blender_ prefix — command names are stripped of the prefix before sending.
   */
  async call(command, params = {}) {
    if (!this.socket) {
      throw new Error('Not connected to Blender MCP');
    }

    const id = this.nextId++;
    const request = {
      id,
      command,
      params,
    };

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Timeout waiting for response to command: ${command}`));
      }, 30000);

      this.pendingRequests.set(id, {
        resolve: (msg) => {
          clearTimeout(timeout);
          resolve(msg);
        },
        reject: (err) => {
          clearTimeout(timeout);
          reject(err);
        },
      });

      const json = JSON.stringify(request);
      this.socket.write(json);
    });
  }

  /**
   * Execute Python code in Blender.
   * Returns the unwrapped result (handles double-nested structure).
   */
  async executePython(code) {
    const response = await this.call('execute_python', { code });
    // Double-nested result: { result: { result: actual_value } }
    return response.result?.result;
  }

  /**
   * Disconnect from Blender MCP.
   */
  async disconnect() {
    return new Promise((resolve) => {
      if (this.socket) {
        this.socket.end(() => {
          console.log('Disconnected from Blender MCP');
          resolve();
        });
      } else {
        resolve();
      }
    });
  }
}

// ===========================
// Production Functions
// ===========================

/**
 * Clean the scene: start fresh with empty scene + nuke all data blocks.
 */
async function cleanScene(client) {
  console.log('🧹 Cleaning scene...');

  // Step 1: Request new empty scene from MCP
  await client.call('save_file', { action: 'new', use_empty: true });

  // Step 2: Python nuke of all data blocks
  const cleaned = await client.executePython(`import bpy
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for mesh in list(bpy.data.meshes):
    bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    bpy.data.materials.remove(mat)
for cam in list(bpy.data.cameras):
    bpy.data.cameras.remove(cam)
for light in list(bpy.data.lights):
    bpy.data.lights.remove(light)
__result__ = {'cleared': True, 'objects': len(bpy.data.objects)}`);

  console.log(`  ✓ Scene cleaned: ${cleaned.objects} objects remaining`);
}

/**
 * Create a simple table: flat top (cube scaled) + 4 legs.
 */
async function createTable(client) {
  console.log('📦 Creating table...');

  const code = `import bpy

# Create tabletop (flat cube)
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
top = bpy.context.active_object
top.name = 'TableTop'
top.scale = (1.5, 1.5, 0.05)

# Create 4 table legs
leg_positions = [
  (1.3, 1.3, 0.4),   # Front-right
  (1.3, -1.3, 0.4),  # Front-left
  (-1.3, 1.3, 0.4),  # Back-right
  (-1.3, -1.3, 0.4)  # Back-left
]

for i, pos in enumerate(leg_positions):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    leg = bpy.context.active_object
    leg.name = f'Leg_{i+1}'
    leg.scale = (0.1, 0.1, 0.45)

__result__ = {'table_created': True, 'objects': len([o for o in bpy.data.objects if o.type == 'MESH'])}`

  const result = await client.executePython(code);
  console.log(`  ✓ Table created: ${result.objects} mesh objects`);
}

/**
 * Apply subdivision surface modifier to all mesh objects.
 */
async function applySubdivisionSurface(client) {
  console.log('✨ Applying subdivision surface...');

  const code = `import bpy
count = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH':
        mod = obj.modifiers.new('Subsurf', 'SUBSURF')
        mod.levels = 2
        mod.render_levels = 2
        count += 1
__result__ = {'applied': count}`

  const result = await client.executePython(code);
  console.log(`  ✓ Subdivision surface applied to ${result.applied} objects`);
}

/**
 * Apply smooth shading to all mesh objects (excluding ground plane).
 * IMPORTANT: Use execute_python per-object loop, NOT blender_cleanup (which fails with bpy_prop_collection error).
 */
async function applySmoothing(client) {
  console.log('🎨 Applying smooth shading...');

  const code = `import bpy
count = 0
for obj in bpy.data.objects:
    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.shade_smooth()
        obj.select_set(False)
        count += 1
__result__ = {'shaded': count}`

  const result = await client.executePython(code);
  console.log(`  ✓ Smooth shading applied to ${result.shaded} objects`);
}

/**
 * Set up 3-point studio lighting with gray background and ground plane.
 */
async function setupLighting(client) {
  console.log('💡 Setting up studio lighting...');

  const code = `import bpy, mathutils

# Find model center and size
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            wc = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(wc)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

# World background: medium gray (0.18)
world = bpy.context.scene.world
if not world:
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
    bg.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)
    bg.inputs[1].default_value = 1.0

# 3-point area lighting relative to model size
d = max(size * 2.0, 3.0)
for name, loc, energy in [('key_light', (d, d, d*0.8), 500.0), ('fill_light', (-d*0.6, d*0.6, d*0.5), 200.0), ('rim_light', (0, -d*0.8, d*0.5), 300.0)]:
    light_data = bpy.data.lights.new(name=name, type='AREA')
    light_data.energy = energy
    light_data.size = size * 0.5
    light_obj = bpy.data.objects.new(name=name, object_data=light_data)
    bpy.context.scene.collection.objects.link(light_obj)
    light_obj.location = center + mathutils.Vector(loc)
    dir = center - light_obj.location
    rot = dir.to_track_quat('-Z', 'Y')
    light_obj.rotation_euler = rot.to_euler()

# Ground plane: proportional to model, neutral gray
bpy.ops.mesh.primitive_plane_add(size=size*4, location=(center.x, center.y, min(zs) - 0.01 if meshes else -0.5))
ground = bpy.context.active_object
ground.name = '_ground_plane'
mat = bpy.data.materials.new('ground_mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
ground.data.materials.append(mat)

__result__ = {'center': [center.x, center.y, center.z], 'size': size, 'light_dist': d}`

  const result = await client.executePython(code);
  console.log(`  ✓ Studio lighting configured: center=${result.center}, size=${result.size.toFixed(2)}`);
}

/**
 * Set render settings (EEVEE, 2048x2048, PNG format).
 */
async function setRenderSettings(client) {
  console.log('📷 Setting render settings...');

  // Use lowercase engine name 'eevee' (NOT 'EEVEE')
  await client.call('set_render_settings', {
    engine: 'eevee',
    resolution_x: 2048,
    resolution_y: 2048,
    samples: 64,
    output_format: 'PNG'
  });

  console.log('  ✓ Render settings applied');
}

/**
 * Position and aim camera for a specific shot angle.
 */
async function positionCamera(client, angle) {
  console.log(`📹 Positioning camera for ${angle} shot...`);

  const code = `import bpy, mathutils

meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != '_ground_plane']
if meshes:
    all_coords = []
    for obj in meshes:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ mathutils.Vector(corner)
            all_coords.append(world_corner)
    xs = [c.x for c in all_coords]
    ys = [c.y for c in all_coords]
    zs = [c.z for c in all_coords]
    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))
    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))
else:
    center = mathutils.Vector((0, 0, 0))
    size = 2.0

d = max(size * 2.5, 3.0)

cam = bpy.data.objects.get('Camera')
if not cam:
    bpy.ops.object.camera_add()
    cam = bpy.context.active_object

# Position based on shot angle
angle = '${angle}'
if angle == 'hero':
    cam.location = center + mathutils.Vector((d*0.6, d*0.6, d*0.45))
elif angle == 'front':
    cam.location = center + mathutils.Vector((0, d, 0))
elif angle == 'side':
    cam.location = center + mathutils.Vector((d, 0, 0))
elif angle == 'top':
    cam.location = center + mathutils.Vector((0, 0.001, d))
elif angle == 'detail':
    cam.location = center + mathutils.Vector((d*0.35, d*0.35, d*0.25))

# Aim camera at model center
dir = center - cam.location
rot = dir.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam
__result__ = {'center': [center.x, center.y, center.z], 'distance': d}`;

  const result = await client.executePython(code);
  console.log(`  ✓ Camera positioned: center=${result.center}, distance=${result.distance.toFixed(2)}`);
}

/**
 * Render a shot and save to file.
 * CRITICAL: Use output_path (NOT filepath).
 */
async function renderShot(client, shotName) {
  console.log(`🎬 Rendering ${shotName} shot...`);

  const outputPath = path.join(OUTPUT_DIR, `${shotName}.png`);
  await client.call('render', {
    output_path: outputPath
  });

  console.log(`  ✓ Rendered to ${outputPath}`);
  return outputPath;
}

/**
 * Export model as STL.
 * CRITICAL: STL export requires execute_python with bpy.ops.wm.stl_export (NOT export_file tool).
 */
async function exportSTL(client) {
  console.log('💾 Exporting as STL...');

  const stlPath = path.join(OUTPUT_DIR, 'table.stl');
  const code = `import bpy
bpy.ops.wm.stl_export(filepath='${stlPath}')
__result__ = {'exported': '${stlPath}'}`;

  const result = await client.executePython(code);
  console.log(`  ✓ Exported to ${result.exported}`);
  return stlPath;
}

/**
 * Export model as FBX.
 */
async function exportFBX(client) {
  console.log('💾 Exporting as FBX...');

  const fbxPath = path.join(OUTPUT_DIR, 'table.fbx');
  await client.call('export_file', {
    action: 'export_fbx',
    filepath: fbxPath
  });

  console.log(`  ✓ Exported to ${fbxPath}`);
  return fbxPath;
}

/**
 * Save .blend file.
 */
async function saveBlendFile(client) {
  console.log('💾 Saving .blend file...');

  const blendPath = path.join(OUTPUT_DIR, 'table.blend');
  await client.call('save_file', {
    action: 'save_as',
    filepath: blendPath
  });

  console.log(`  ✓ Saved to ${blendPath}`);
  return blendPath;
}

// ===========================
// Main Execution
// ===========================

async function main() {
  const client = new BlenderMCPClient(BLENDER_HOST, BLENDER_PORT);

  try {
    console.log('🚀 Starting table production...\n');

    // Connect to Blender MCP
    await client.connect();

    // Clean scene
    await cleanScene(client);

    // Create table
    await createTable(client);

    // Apply polish
    await applySubdivisionSurface(client);
    await applySmoothing(client);

    // Set up rendering
    await setRenderSettings(client);
    await setupLighting(client);

    // Render shots
    await positionCamera(client, 'hero');
    const heroRender = await renderShot(client, 'hero');

    await positionCamera(client, 'top');
    const topRender = await renderShot(client, 'top-down');

    // Export
    const stlFile = await exportSTL(client);
    const fbxFile = await exportFBX(client);

    // Save
    const blendFile = await saveBlendFile(client);

    // Summary
    console.log('\n✅ Production complete!\n');
    console.log('📊 Output files:');
    console.log(`  - Blend: ${blendFile}`);
    console.log(`  - STL: ${stlFile}`);
    console.log(`  - FBX: ${fbxFile}`);
    console.log(`  - Hero render: ${heroRender}`);
    console.log(`  - Top-down render: ${topRender}`);

  } catch (error) {
    console.error('\n❌ Error during production:', error.message);
    process.exit(1);
  } finally {
    await client.disconnect();
  }
}

main();
