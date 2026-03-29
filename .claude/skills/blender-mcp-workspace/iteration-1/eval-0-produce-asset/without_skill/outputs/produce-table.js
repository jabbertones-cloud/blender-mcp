#!/usr/bin/env node

/**
 * Blender MCP Table Production Script
 * Creates a simple table model with proper topology, applies modifiers,
 * renders hero and top-down shots, and exports to STL and FBX formats.
 *
 * Usage: node produce-table.js [--output-dir ./output] [--no-cleanup]
 */

const net = require("net");
const path = require("path");
const fs = require("fs");
const { EventEmitter } = require("events");

class BlenderMCPClient extends EventEmitter {
  constructor(host = "localhost", port = 9876) {
    super();
    this.host = host;
    this.port = port;
    this.socket = null;
    this.requestId = 0;
    this.pendingRequests = new Map();
    this.buffer = "";
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.socket = net.createConnection(this.port, this.host, () => {
        console.log(`[MCP] Connected to Blender on ${this.host}:${this.port}`);
        resolve();
      });

      this.socket.on("data", (data) => this._handleData(data));
      this.socket.on("error", (err) => {
        console.error(`[MCP] Connection error:`, err.message);
        reject(err);
      });
      this.socket.on("close", () => {
        console.log("[MCP] Connection closed");
        this.emit("closed");
      });

      setTimeout(() => {
        reject(new Error("Connection timeout"));
      }, 10000);
    });
  }

  _handleData(data) {
    this.buffer += data.toString();
    const lines = this.buffer.split("\n");
    this.buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.trim()) continue;
      try {
        const response = JSON.parse(line);
        this._handleResponse(response);
      } catch (err) {
        console.error("[MCP] Failed to parse response:", line, err.message);
      }
    }
  }

  _handleResponse(response) {
    if (response.id && this.pendingRequests.has(response.id)) {
      const { resolve, reject, timeout } = this.pendingRequests.get(response.id);
      clearTimeout(timeout);
      this.pendingRequests.delete(response.id);

      if (response.error) {
        reject(new Error(`${response.error.message || "Unknown error"}`));
      } else {
        resolve(response.result);
      }
    } else if (response.method) {
      this.emit("notification", response);
    }
  }

  async request(method, params = {}, timeoutMs = 30000) {
    if (!this.socket) throw new Error("Not connected");

    const id = ++this.requestId;
    const request = { jsonrpc: "2.0", id, method, params };

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timeout: ${method}`));
      }, timeoutMs);

      this.pendingRequests.set(id, { resolve, reject, timeout });

      try {
        this.socket.write(JSON.stringify(request) + "\n");
      } catch (err) {
        this.pendingRequests.delete(id);
        clearTimeout(timeout);
        reject(err);
      }
    });
  }

  async execute_bpy_script(script, description = "") {
    const params = { script };
    if (description) params.description = description;
    return this.request("execute_bpy_script", params, 60000);
  }

  async close() {
    if (this.socket) {
      this.socket.end();
      return new Promise((resolve) => {
        this.socket.on("close", resolve);
      });
    }
  }
}

// ============================================================================
// BLENDER SCRIPT TEMPLATES
// ============================================================================

const scripts = {
  // Clear the scene of all objects
  clearScene: () => `
import bpy

# Select all objects and delete them
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Remove all unused materials
for material in bpy.data.materials:
    if material.users == 0:
        bpy.data.materials.remove(material)
`,

  // Create a simple table: flat top with 4 legs
  createTable: () => `
import bpy
from mathutils import Matrix

# Table dimensions
top_width = 2.0
top_depth = 1.0
top_thickness = 0.1

leg_width = 0.08
leg_depth = 0.08
leg_height = 1.0

# ===== CREATE TABLE TOP =====
bpy.ops.mesh.primitive_cube_add(size=1)
top = bpy.context.active_object
top.name = "TableTop"
top.scale = (top_width / 2, top_depth / 2, top_thickness / 2)
top.location = (0, 0, leg_height + top_thickness / 2)

# Apply scale
bpy.context.view_layer.objects.active = top
bpy.ops.object.transform_apply(scale=True)

# ===== CREATE LEGS =====
leg_positions = [
  (-top_width / 2 + leg_width / 2, -top_depth / 2 + leg_depth / 2),
  (top_width / 2 - leg_width / 2, -top_depth / 2 + leg_depth / 2),
  (-top_width / 2 + leg_width / 2, top_depth / 2 - leg_depth / 2),
  (top_width / 2 - leg_width / 2, top_depth / 2 - leg_depth / 2),
]

legs = []
for i, (x, y) in enumerate(leg_positions):
    bpy.ops.mesh.primitive_cube_add(size=1)
    leg = bpy.context.active_object
    leg.name = f"TableLeg_{i+1}"
    leg.scale = (leg_width / 2, leg_depth / 2, leg_height / 2)
    leg.location = (x, y, leg_height / 2)
    
    # Apply scale
    bpy.context.view_layer.objects.active = leg
    bpy.ops.object.transform_apply(scale=True)
    legs.append(leg)

# Join all objects into one
bpy.context.view_layer.objects.active = top
for leg in legs:
    leg.select_set(True)
top.select_set(True)
bpy.ops.object.join()

# Rename final object
top.name = "Table"
print("Table created successfully")
`,

  // Apply subdivision surface and smooth shading
  applyModifiers: () => `
import bpy

table = bpy.context.scene.objects.get("Table")
if table:
    bpy.context.view_layer.objects.active = table
    table.select_set(True)
    
    # Add subdivision surface modifier
    subsurf = table.modifiers.new(name="Subdivision", type='SUBSURF')
    subsurf.levels = 2
    subsurf.render_levels = 3
    subsurf.use_smooth_shade = True
    
    # Apply smooth shading to object
    bpy.context.view_layer.objects.active = table
    bpy.ops.object.shade_smooth()
    
    print("Modifiers applied")
else:
    print("ERROR: Table object not found")
`,

  // Set up lighting
  setupLighting: () => `
import bpy
from mathutils import Vector

# Remove default lights
for obj in bpy.data.objects:
    if obj.type == 'LIGHT':
        bpy.data.objects.remove(obj, do_unlink=True)

# Add key light (strong directional)
bpy.ops.object.light_add(type='SUN', location=(3, 4, 5))
key_light = bpy.context.active_object
key_light.name = "KeyLight"
key_light.data.energy = 2.0
key_light.data.angle = 0.2

# Add fill light (soft)
bpy.ops.object.light_add(type='SUN', location=(-2, 2, 3))
fill_light = bpy.context.active_object
fill_light.name = "FillLight"
fill_light.data.energy = 0.8
fill_light.data.angle = 0.3

# Add back light for depth
bpy.ops.object.light_add(type='SUN', location=(0, -3, 2))
back_light = bpy.context.active_object
back_light.name = "BackLight"
back_light.data.energy = 0.5
back_light.data.angle = 0.4

# Enable ambient occlusion in world settings
world = bpy.data.worlds["World"]
world.use_nodes = True
bg_node = world.node_tree.nodes["Background"]
bg_node.inputs[1].default_value = 0.8  # Strength

print("Lighting setup complete")
`,

  // Set up render settings and camera for hero shot
  setupHeroCamera: () => `
import bpy
from mathutils import Vector

# Set render resolution
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
bpy.context.scene.render.image_settings.file_format = 'PNG'
bpy.context.scene.render.samples = 128

# Create camera for hero shot (3/4 view)
bpy.ops.object.camera_add(location=(3, 3, 2))
hero_camera = bpy.context.active_object
hero_camera.name = "HeroCamera"
hero_camera.data.lens = 50

# Point camera at origin
direction = Vector((0, 0, 0)) - Vector(hero_camera.location)
hero_camera.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

# Make active
bpy.context.scene.camera = hero_camera

print("Hero camera setup complete")
`,

  // Set up camera for top-down shot
  setupTopDownCamera: () => `
import bpy
from mathutils import Vector

# Create camera for top-down shot
bpy.ops.object.camera_add(location=(0, 0, 3))
topdown_camera = bpy.context.active_object
topdown_camera.name = "TopDownCamera"
topdown_camera.data.lens = 50
topdown_camera.rotation_euler = (0, 0, 0)

print("Top-down camera setup complete")
`,

  // Render and save hero shot
  renderHeroShot: (outputPath) => `
import bpy

hero_camera = bpy.data.objects.get("HeroCamera")
if hero_camera:
    bpy.context.scene.camera = hero_camera
    bpy.context.scene.render.filepath = "${outputPath}"
    bpy.ops.render.render(write_still=True)
    print(f"Hero shot rendered: ${outputPath}")
else:
    print("ERROR: HeroCamera not found")
`,

  // Render and save top-down shot
  renderTopDownShot: (outputPath) => `
import bpy

topdown_camera = bpy.data.objects.get("TopDownCamera")
if topdown_camera:
    bpy.context.scene.camera = topdown_camera
    bpy.context.scene.render.filepath = "${outputPath}"
    bpy.ops.render.render(write_still=True)
    print(f"Top-down shot rendered: ${outputPath}")
else:
    print("ERROR: TopDownCamera not found")
`,

  // Export as STL
  exportSTL: (outputPath) => `
import bpy

table = bpy.context.scene.objects.get("Table")
if table:
    # Select only the table
    bpy.ops.object.select_all(action='DESELECT')
    table.select_set(True)
    bpy.context.view_layer.objects.active = table
    
    # Export STL
    bpy.ops.export_mesh.stl(filepath="${outputPath}", use_selection=True)
    print(f"STL exported: ${outputPath}")
else:
    print("ERROR: Table object not found")
`,

  // Export as FBX
  exportFBX: (outputPath) => `
import bpy

table = bpy.context.scene.objects.get("Table")
if table:
    # Select only the table
    bpy.ops.object.select_all(action='DESELECT')
    table.select_set(True)
    bpy.context.view_layer.objects.active = table
    
    # Export FBX with smooth groups
    bpy.ops.export_scene.fbx(
        filepath="${outputPath}",
        use_selection=True,
        use_smooth_groups=True,
        use_mesh_modifiers=True
    )
    print(f"FBX exported: ${outputPath}")
else:
    print("ERROR: Table object not found")
`,

  // Save .blend file
  saveBendFile: (outputPath) => `
import bpy
bpy.ops.wm.save_as_mainfile(filepath="${outputPath}")
print(f"Blend file saved: ${outputPath}")
`,
};

// ============================================================================
// MAIN EXECUTION
// ============================================================================

async function main() {
  const args = process.argv.slice(2);
  let outputDir = "./output";
  let skipCleanup = false;

  // Parse command line arguments
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--output-dir" && args[i + 1]) {
      outputDir = args[++i];
    } else if (args[i] === "--no-cleanup") {
      skipCleanup = true;
    }
  }

  // Ensure output directory exists
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const client = new BlenderMCPClient("localhost", 9876);

  try {
    // Connect to Blender MCP server
    console.log("[MAIN] Connecting to Blender MCP server...");
    await client.connect();
    console.log("[MAIN] Connected successfully");

    // ===== STEP 1: CLEANUP =====
    if (!skipCleanup) {
      console.log("[MAIN] Step 1/8: Clearing scene...");
      await client.execute_bpy_script(scripts.clearScene(), "Clear scene");
      console.log("[MAIN] ✓ Scene cleared");
    }

    // ===== STEP 2: CREATE TABLE =====
    console.log("[MAIN] Step 2/8: Creating table geometry...");
    await client.execute_bpy_script(scripts.createTable(), "Create table with 4 legs");
    console.log("[MAIN] ✓ Table created");

    // ===== STEP 3: APPLY MODIFIERS =====
    console.log("[MAIN] Step 3/8: Applying subdivision surface and smooth shading...");
    await client.execute_bpy_script(scripts.applyModifiers(), "Apply modifiers");
    console.log("[MAIN] ✓ Modifiers applied");

    // ===== STEP 4: SETUP LIGHTING =====
    console.log("[MAIN] Step 4/8: Setting up three-point lighting...");
    await client.execute_bpy_script(scripts.setupLighting(), "Setup lighting");
    console.log("[MAIN] ✓ Lighting configured");

    // ===== STEP 5: SETUP CAMERAS =====
    console.log("[MAIN] Step 5/8: Setting up render cameras...");
    await client.execute_bpy_script(scripts.setupHeroCamera(), "Setup hero camera");
    await client.execute_bpy_script(scripts.setupTopDownCamera(), "Setup top-down camera");
    console.log("[MAIN] ✓ Cameras configured");

    // ===== STEP 6: RENDER SHOTS =====
    const heroShotPath = path.join(outputDir, "table_hero_shot.png");
    const topDownPath = path.join(outputDir, "table_topdown_shot.png");

    console.log("[MAIN] Step 6/8: Rendering hero shot...");
    await client.execute_bpy_script(
      scripts.renderHeroShot(heroShotPath),
      "Render hero shot"
    );
    console.log(`[MAIN] ✓ Hero shot saved: ${heroShotPath}`);

    console.log("[MAIN] Step 7/8: Rendering top-down shot...");
    await client.execute_bpy_script(
      scripts.renderTopDownShot(topDownPath),
      "Render top-down shot"
    );
    console.log(`[MAIN] ✓ Top-down shot saved: ${topDownPath}`);

    // ===== STEP 8: EXPORT MODELS =====
    const stlPath = path.join(outputDir, "table.stl");
    const fbxPath = path.join(outputDir, "table.fbx");
    const blendPath = path.join(outputDir, "table.blend");

    console.log("[MAIN] Step 8/8: Exporting models...");
    await client.execute_bpy_script(scripts.exportSTL(stlPath), "Export STL");
    console.log(`[MAIN] ✓ STL exported: ${stlPath}`);

    await client.execute_bpy_script(scripts.exportFBX(fbxPath), "Export FBX");
    console.log(`[MAIN] ✓ FBX exported: ${fbxPath}`);

    // ===== SAVE BLEND FILE =====
    await client.execute_bpy_script(scripts.saveBendFile(blendPath), "Save .blend file");
    console.log(`[MAIN] ✓ Blend file saved: ${blendPath}`);

    // ===== SUMMARY =====
    console.log("\n" + "=".repeat(70));
    console.log("TABLE PRODUCTION COMPLETE");
    console.log("=".repeat(70));
    console.log(`Output Directory: ${path.resolve(outputDir)}`);
    console.log(`  - Blend File:     ${blendPath}`);
    console.log(`  - STL Model:      ${stlPath}`);
    console.log(`  - FBX Model:      ${fbxPath}`);
    console.log(`  - Hero Shot:      ${heroShotPath}`);
    console.log(`  - Top-Down Shot:  ${topDownPath}`);
    console.log("=".repeat(70));
  } catch (error) {
    console.error("[ERROR]", error.message);
    process.exit(1);
  } finally {
    await client.close();
  }
}

// Run the script
main().catch((err) => {
  console.error("[FATAL]", err.message);
  process.exit(1);
});
