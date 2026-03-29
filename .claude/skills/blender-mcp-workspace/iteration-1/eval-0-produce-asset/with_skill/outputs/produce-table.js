#!/usr/bin/env node

/**
 * Blender MCP Producer Script: Table Generation
 *
 * Creates a simple table (flat top surface with 4 legs), applies finishing touches,
 * renders hero and top-down shots, exports as STL and FBX, and saves the .blend file.
 *
 * Requirements:
 * - Blender MCP server running on port 9876
 * - Node.js with net module
 *
 * Usage:
 *   node produce-table.js [--output-dir OUTPUT_DIR] [--port PORT]
 *
 * Defaults:
 *   output-dir: ./outputs
 *   port: 9876
 */

const net = require('net');
const path = require('path');
const fs = require('fs');
const { promisify } = require('util');

// ============================================================================
// Configuration
// ============================================================================

const DEFAULT_PORT = 9876;
const DEFAULT_OUTPUT_DIR = path.join(process.cwd(), 'outputs');
const TIMEOUT_MS = 30000; // 30 second default timeout for operations

// Table dimensions (in Blender units, typically mm)
const TABLE_CONFIG = {
  top_width: 1000,
  top_depth: 800,
  top_thickness: 50,
  leg_height: 700,
  leg_size: 40,
  leg_offset: 100, // Distance from edge to leg center
};

// ============================================================================
// MCP Client Implementation
// ============================================================================

class BlenderMCPClient {
  constructor(port = DEFAULT_PORT) {
    this.port = port;
    this.socket = null;
    this.nextId = 1;
    this.pendingRequests = new Map();
    this.connected = false;
    this.receiveBuffer = '';
  }

  /**
   * Connect to the Blender MCP server via TCP
   */
  async connect() {
    return new Promise((resolve, reject) => {
      this.socket = net.createConnection(this.port, 'localhost', () => {
        this.connected = true;
        this.socket.on('data', (data) => this._handleData(data));
        this.socket.on('error', (err) => this._handleError(err));
        this.socket.on('close', () => {
          this.connected = false;
        });
        resolve();
      });

      this.socket.on('error', (err) => {
        this.connected = false;
        reject(new Error(`Failed to connect to Blender MCP on port ${this.port}: ${err.message}`));
      });
    });
  }

  /**
   * Disconnect from the server
   */
  disconnect() {
    if (this.socket) {
      this.socket.destroy();
      this.socket = null;
      this.connected = false;
    }
  }

  /**
   * Send a command to the server and wait for response
   * Handles brace-depth JSON parsing (no newline delimiters)
   */
  async call(command, params = {}, timeoutMs = TIMEOUT_MS) {
    if (!this.connected) {
      throw new Error('Not connected to Blender MCP server');
    }

    const id = this.nextId++;
    const request = { id, command, params };

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Command "${command}" timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this.pendingRequests.set(id, { resolve, reject, timeout });

      try {
        const jsonStr = JSON.stringify(request);
        this.socket.write(jsonStr);
      } catch (err) {
        this.pendingRequests.delete(id);
        clearTimeout(timeout);
        reject(new Error(`Failed to send command: ${err.message}`));
      }
    });
  }

  /**
   * Handle incoming data using brace-depth parsing
   * The server sends raw JSON without newline delimiters, so we must
   * count braces to determine message boundaries
   */
  _handleData(data) {
    this.receiveBuffer += data.toString();
    this._processBuffer();
  }

  /**
   * Process the receive buffer, extracting complete JSON messages
   */
  _processBuffer() {
    let braceDepth = 0;
    let inString = false;
    let escape = false;
    let messageStart = 0;

    for (let i = 0; i < this.receiveBuffer.length; i++) {
      const char = this.receiveBuffer[i];

      // Handle escape sequences
      if (escape) {
        escape = false;
        continue;
      }

      if (char === '\\') {
        escape = true;
        continue;
      }

      // Track string boundaries
      if (char === '"' && !escape) {
        inString = !inString;
        continue;
      }

      // Count braces only outside strings
      if (!inString) {
        if (char === '{') {
          braceDepth++;
        } else if (char === '}') {
          braceDepth--;

          // When depth returns to 0, we have a complete message
          if (braceDepth === 0) {
            const message = this.receiveBuffer.slice(messageStart, i + 1);
            try {
              this._handleMessage(JSON.parse(message));
            } catch (err) {
              console.error('Failed to parse message:', err);
            }
            messageStart = i + 1;
          }
        }
      }
    }

    // Remove processed messages from buffer
    this.receiveBuffer = this.receiveBuffer.slice(messageStart);
  }

  /**
   * Handle a complete message from the server
   */
  _handleMessage(msg) {
    if (!msg.id || !this.pendingRequests.has(msg.id)) {
      return; // Not a response to a pending request
    }

    const { resolve, reject, timeout } = this.pendingRequests.get(msg.id);
    this.pendingRequests.delete(msg.id);
    clearTimeout(timeout);

    if (msg.error) {
      reject(new Error(msg.error));
    } else {
      // Double-nested unwrapping for execute_python results
      let result = msg.result;
      if (result && typeof result === 'object' && 'result' in result) {
        result = result.result;
      }
      resolve(result);
    }
  }

  /**
   * Handle socket errors
   */
  _handleError(err) {
    console.error('Socket error:', err);
    // Clear all pending requests
    for (const [id, { reject, timeout }] of this.pendingRequests.entries()) {
      clearTimeout(timeout);
      reject(new Error(`Socket error: ${err.message}`));
      this.pendingRequests.delete(id);
    }
  }
}

// ============================================================================
// Producer Logic
// ============================================================================

class TableProducer {
  constructor(outputDir = DEFAULT_OUTPUT_DIR, port = DEFAULT_PORT) {
    this.outputDir = outputDir;
    this.client = new BlenderMCPClient(port);
    this.stepLog = [];
  }

  /**
   * Initialize output directory
   */
  async setupOutputDir() {
    if (!fs.existsSync(this.outputDir)) {
      fs.mkdirSync(this.outputDir, { recursive: true });
    }
  }

  /**
   * Log a step for tracking
   */
  logStep(stepName, success = true, details = '') {
    const entry = {
      timestamp: new Date().toISOString(),
      step: stepName,
      success,
      details,
    };
    this.stepLog.push(entry);
    const status = success ? '✓' : '✗';
    console.log(`${status} ${stepName}${details ? ': ' + details : ''}`);
  }

  /**
   * Step 1: Clean the scene
   * Start with empty scene and nuke all existing data blocks
   */
  async cleanScene() {
    try {
      // Create new empty scene
      await this.client.call('save_file', { action: 'new', use_empty: true });
      this.logStep('create_new_scene', true);

      // Belt-and-suspenders: Python nuke of all data blocks
      const result = await this.client.call('execute_python', {
        code: `import bpy
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
__result__ = {'cleared': True, 'objects_remaining': len(bpy.data.objects)}`,
      });
      this.logStep('nuke_data_blocks', true, `${result.objects_remaining} objects remaining`);
    } catch (err) {
      this.logStep('clean_scene', false, err.message);
      throw err;
    }
  }

  /**
   * Step 2: Create table geometry
   * Creates a flat tabletop and 4 legs
   */
  async createTableGeometry() {
    try {
      const code = `import bpy

# Create tabletop (cube scaled to make a flat plane)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
top = bpy.context.active_object
top.name = 'table_top'
top.scale = (${TABLE_CONFIG.top_width / 2}, ${TABLE_CONFIG.top_depth / 2}, ${TABLE_CONFIG.top_thickness / 2})

# Create 4 legs (cubes positioned at corners)
leg_positions = [
  (${TABLE_CONFIG.leg_offset}, ${TABLE_CONFIG.leg_offset}, -${TABLE_CONFIG.leg_height / 2}),
  (${TABLE_CONFIG.leg_offset}, -${TABLE_CONFIG.leg_offset}, -${TABLE_CONFIG.leg_height / 2}),
  (-${TABLE_CONFIG.leg_offset}, ${TABLE_CONFIG.leg_offset}, -${TABLE_CONFIG.leg_height / 2}),
  (-${TABLE_CONFIG.leg_offset}, -${TABLE_CONFIG.leg_offset}, -${TABLE_CONFIG.leg_height / 2}),
]

legs = []
for i, pos in enumerate(leg_positions):
  bpy.ops.mesh.primitive_cube_add(size=1.0, location=pos)
  leg = bpy.context.active_object
  leg.name = f'table_leg_{i+1}'
  leg.scale = (${TABLE_CONFIG.leg_size / 2}, ${TABLE_CONFIG.leg_size / 2}, ${TABLE_CONFIG.leg_height / 2})
  legs.append(leg)

__result__ = {'objects_created': len(legs) + 1}`;

      const result = await this.client.call('execute_python', { code });
      this.logStep('create_table_geometry', true, `Created ${result.objects_created} objects`);
    } catch (err) {
      this.logStep('create_table_geometry', false, err.message);
      throw err;
    }
  }

  /**
   * Step 3: Apply subdivision surface modifier
   */
  async applySubdivisionSurface() {
    try {
      const code = `import bpy

for obj in bpy.data.objects:
  if obj.type == 'MESH':
    mod = obj.modifiers.new('Subsurf', 'SUBSURF')
    mod.levels = 2
    mod.render_levels = 2

__result__ = {'applied': True}`;

      await this.client.call('execute_python', { code });
      this.logStep('apply_subdivision_surface', true);
    } catch (err) {
      this.logStep('apply_subdivision_surface', false, err.message);
      throw err;
    }
  }

  /**
   * Step 4: Apply smooth shading
   * Must loop through objects individually and set as active before shading
   */
  async applySmoothShading() {
    try {
      const code = `import bpy

for obj in bpy.data.objects:
  if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)

__result__ = {'shaded': True}`;

      await this.client.call('execute_python', { code });
      this.logStep('apply_smooth_shading', true);
    } catch (err) {
      this.logStep('apply_smooth_shading', false, err.message);
      throw err;
    }
  }

  /**
   * Step 5: Set up studio lighting
   * 3-point area lighting with gray background and ground plane
   */
  async setupLighting() {
    try {
      const code = `import bpy, mathutils

# Calculate model center and size
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
  center = mathutils.Vector((0,0,0))
  size = 2.0

# World background: medium gray (NOT white)
world = bpy.context.scene.world
if not world:
  world = bpy.data.worlds.new('World')
  bpy.context.scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
if bg:
  bg.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)
  bg.inputs[1].default_value = 1.0

# 3-point area lighting
d = max(size * 2.0, 3.0)
light_configs = [
  ('key_light', (d, d, d*0.8), 500.0),
  ('fill_light', (-d*0.6, d*0.6, d*0.5), 200.0),
  ('rim_light', (0, -d*0.8, d*0.5), 300.0),
]

for name, loc_offset, energy in light_configs:
  light_data = bpy.data.lights.new(name=name, type='AREA')
  light_data.energy = energy
  light_data.size = size * 0.5
  light_obj = bpy.data.objects.new(name=name, object_data=light_data)
  bpy.context.scene.collection.objects.link(light_obj)
  light_obj.location = center + mathutils.Vector(loc_offset)
  dir_vec = center - light_obj.location
  rot = dir_vec.to_track_quat('-Z', 'Y')
  light_obj.rotation_euler = rot.to_euler()

# Ground plane: proportional to model, neutral gray
min_z = min(zs) if meshes else 0
bpy.ops.mesh.primitive_plane_add(size=size*4, location=(center.x, center.y, min_z - 0.01))
ground = bpy.context.active_object
ground.name = '_ground_plane'
mat = bpy.data.materials.new('ground_mat')
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
if bsdf:
  bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)
ground.data.materials.append(mat)

__result__ = {'center': [center.x, center.y, center.z], 'size': size, 'light_distance': d}`;

      const result = await this.client.call('execute_python', { code });
      this.logStep('setup_lighting', true, `Model size: ${result.size.toFixed(2)}u`);
    } catch (err) {
      this.logStep('setup_lighting', false, err.message);
      throw err;
    }
  }

  /**
   * Step 6: Configure render settings for EEVEE (fast)
   */
  async configureRenderSettings() {
    try {
      await this.client.call('set_render_settings', {
        engine: 'eevee',
        resolution_x: 2048,
        resolution_y: 2048,
        samples: 64,
        output_format: 'PNG',
      });
      this.logStep('configure_render_settings', true);
    } catch (err) {
      this.logStep('configure_render_settings', false, err.message);
      throw err;
    }
  }

  /**
   * Step 7: Render hero shot (45-degree isometric view)
   */
  async renderHeroShot() {
    try {
      // Position camera for hero shot
      const cameraCode = `import bpy, mathutils

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

# Hero shot: 45-degree isometric view
cam.location = center + mathutils.Vector((d*0.6, d*0.6, d*0.45))
dir_vec = center - cam.location
rot = dir_vec.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam

__result__ = {'camera_positioned': True}`;

      await this.client.call('execute_python', { code });
      this.logStep('position_camera_hero', true);

      // Render
      const outputPath = path.join(this.outputDir, 'hero.png');
      await this.client.call('render', { output_path: outputPath });
      this.logStep('render_hero_shot', true, `Saved to ${path.basename(outputPath)}`);
    } catch (err) {
      this.logStep('render_hero_shot', false, err.message);
      throw err;
    }
  }

  /**
   * Step 8: Render top-down shot
   */
  async renderTopDownShot() {
    try {
      // Position camera for top-down view
      const cameraCode = `import bpy, mathutils

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

cam = bpy.context.scene.camera
if not cam:
  bpy.ops.object.camera_add()
  cam = bpy.context.active_object

# Top-down view: directly overhead (avoid gimbal lock with small Y offset)
cam.location = center + mathutils.Vector((0, 0.001, d))
dir_vec = center - cam.location
rot = dir_vec.to_track_quat('-Z', 'Y')
cam.rotation_euler = rot.to_euler()
bpy.context.scene.camera = cam

__result__ = {'camera_positioned': True}`;

      await this.client.call('execute_python', { code });
      this.logStep('position_camera_top_down', true);

      // Render
      const outputPath = path.join(this.outputDir, 'top_down.png');
      await this.client.call('render', { output_path: outputPath });
      this.logStep('render_top_down_shot', true, `Saved to ${path.basename(outputPath)}`);
    } catch (err) {
      this.logStep('render_top_down_shot', false, err.message);
      throw err;
    }
  }

  /**
   * Step 9: Export as STL
   */
  async exportSTL() {
    try {
      const stlPath = path.join(this.outputDir, 'model.stl');
      const code = `import bpy
bpy.ops.wm.stl_export(filepath='${stlPath}')
__result__ = {'exported': '${stlPath}'}`;

      await this.client.call('execute_python', { code });
      this.logStep('export_stl', true, `Saved to ${path.basename(stlPath)}`);
    } catch (err) {
      this.logStep('export_stl', false, err.message);
      throw err;
    }
  }

  /**
   * Step 10: Export as FBX
   */
  async exportFBX() {
    try {
      const fbxPath = path.join(this.outputDir, 'model.fbx');
      await this.client.call('export_file', {
        action: 'export_fbx',
        filepath: fbxPath,
      });
      this.logStep('export_fbx', true, `Saved to ${path.basename(fbxPath)}`);
    } catch (err) {
      this.logStep('export_fbx', false, err.message);
      throw err;
    }
  }

  /**
   * Step 11: Save .blend file
   */
  async saveBlendFile() {
    try {
      const blendPath = path.join(this.outputDir, 'table.blend');
      await this.client.call('save_file', {
        action: 'save_as',
        filepath: blendPath,
      });
      this.logStep('save_blend_file', true, `Saved to ${path.basename(blendPath)}`);
    } catch (err) {
      this.logStep('save_blend_file', false, err.message);
      throw err;
    }
  }

  /**
   * Write metadata log of production run
   */
  writeMetadata() {
    const stepsSucceeded = this.stepLog.filter((s) => s.success).length;
    const stepsFailed = this.stepLog.filter((s) => !s.success).length;

    const metadata = {
      production_timestamp: new Date().toISOString(),
      output_directory: this.outputDir,
      model_type: 'table',
      steps_executed: this.stepLog.length,
      steps_succeeded: stepsSucceeded,
      steps_failed: stepsFailed,
      step_log: this.stepLog,
      table_config: TABLE_CONFIG,
      files_created: fs.readdirSync(this.outputDir).map((f) => ({
        name: f,
        size_bytes: fs.statSync(path.join(this.outputDir, f)).size,
      })),
    };

    const metadataPath = path.join(this.outputDir, 'metadata.json');
    fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));
    this.logStep('write_metadata', true, `Saved to ${path.basename(metadataPath)}`);
  }

  /**
   * Main production pipeline
   */
  async produce() {
    console.log('Starting table production pipeline...\n');

    try {
      // Setup
      await this.setupOutputDir();
      await this.client.connect();
      console.log(`Connected to Blender MCP on port ${this.client.port}\n`);

      // Execution pipeline
      await this.cleanScene();
      await this.createTableGeometry();
      await this.applySubdivisionSurface();
      await this.applySmoothShading();
      await this.setupLighting();
      await this.configureRenderSettings();
      await this.renderHeroShot();
      await this.renderTopDownShot();
      await this.exportSTL();
      await this.exportFBX();
      await this.saveBlendFile();

      // Finalize
      this.writeMetadata();
      this.client.disconnect();

      // Summary
      console.log('\n' + '='.repeat(60));
      console.log('Production Complete!');
      console.log('='.repeat(60));
      console.log(`Output directory: ${this.outputDir}`);
      console.log(`Steps succeeded: ${this.stepLog.filter((s) => s.success).length}/${this.stepLog.length}`);
      console.log(`Steps failed: ${this.stepLog.filter((s) => !s.success).length}/${this.stepLog.length}`);
      console.log('='.repeat(60) + '\n');

      return { success: true, outputDir: this.outputDir, stepLog: this.stepLog };
    } catch (err) {
      console.error('\nProduction failed:', err.message);
      this.client.disconnect();
      return { success: false, error: err.message, stepLog: this.stepLog };
    }
  }
}

// ============================================================================
// CLI Entry Point
// ============================================================================

async function main() {
  // Parse command-line arguments
  let outputDir = DEFAULT_OUTPUT_DIR;
  let port = DEFAULT_PORT;

  for (let i = 2; i < process.argv.length; i++) {
    if (process.argv[i] === '--output-dir' && i + 1 < process.argv.length) {
      outputDir = process.argv[++i];
    } else if (process.argv[i] === '--port' && i + 1 < process.argv.length) {
      port = parseInt(process.argv[++i], 10);
    } else if (process.argv[i] === '--help') {
      console.log(`
Blender MCP Producer: Table Generation

Usage:
  node produce-table.js [OPTIONS]

Options:
  --output-dir PATH   Output directory (default: ./outputs)
  --port PORT         Blender MCP port (default: 9876)
  --help              Show this message

Example:
  node produce-table.js --output-dir /tmp/models --port 9876
      `);
      process.exit(0);
    }
  }

  const producer = new TableProducer(outputDir, port);
  const result = await producer.produce();

  process.exit(result.success ? 0 : 1);
}

main().catch((err) => {
  console.error('Fatal error:', err);
  process.exit(1);
});
