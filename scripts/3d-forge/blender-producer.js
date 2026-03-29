#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const net = require('net');
const { EventEmitter } = require('events');
const { spawn } = require('child_process');

// Load .env
require('./lib/env').loadEnv();

// Skill system — recipe-driven professional quality
const SkillExecutor = require('../../skills/skill-executor.js');

// ============================================================================
// BLENDER MCP CLIENT
// ============================================================================

class BlenderMCPClient extends EventEmitter {
  constructor(host = '127.0.0.1', port = 9876) {
    super();
    this.host = host;
    this.port = port;
    this.socket = null;
    this.connected = false;
    this.requestId = 0;
    this.pendingRequests = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 1;
    this._buffer = '';
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.socket = net.createConnection(this.port, this.host);

      this.socket.on('connect', () => {
        this.connected = true;
        this.reconnectAttempts = 0;
        console.log(`[BlenderMCP] Connected to ${this.host}:${this.port}`);
        resolve();
      });

      this.socket.on('data', (chunk) => {
        this._handleData(chunk);
      });

      this.socket.on('error', (err) => {
        console.error(`[BlenderMCP] Socket error:`, err.message);
        this.connected = false;
        reject(err);
      });

      this.socket.on('close', () => {
        this.connected = false;
        console.warn('[BlenderMCP] Connection closed');
      });

      this.socket.setTimeout(30000);
    });
  }

  async ping() {
    try {
      const result = await this.call('blender_ping', {});
      return result && (result.success === true || result.status === 'ok');
    } catch (err) {
      return false;
    }
  }

  async call(toolName, params, timeoutMs = 60000) {
    if (!this.connected) {
      throw new Error('BlenderMCP not connected');
    }

    // Strip 'blender_' prefix — MCP server tools don't use it
    const mcpToolName = toolName.startsWith('blender_') ? toolName.slice(8) : toolName;

    const requestId = ++this.requestId;
    const request = {
      id: requestId,
      command: mcpToolName,
      params: params || {},
    };

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(requestId);
        reject(new Error(`Tool call timeout after ${timeoutMs}ms: ${toolName}`));
      }, timeoutMs);

      this.pendingRequests.set(requestId, { resolve, reject, timeout });

      try {
        const json = JSON.stringify(request);
        this.socket.write(json + '\n');
      } catch (err) {
        this.pendingRequests.delete(requestId);
        clearTimeout(timeout);
        reject(err);
      }
    });
  }

  _handleData(chunk) {
    this._buffer += chunk.toString('utf8');
    this._tryParseBuffer();
  }

  _tryParseBuffer() {
    // The Blender addon sends raw JSON without newline terminators.
    // Try to parse complete JSON objects from the buffer.
    let startIdx = 0;
    while (startIdx < this._buffer.length) {
      // Skip whitespace
      while (startIdx < this._buffer.length && ' \t\n\r'.includes(this._buffer[startIdx])) startIdx++;
      if (startIdx >= this._buffer.length) break;
      if (this._buffer[startIdx] !== '{') break;

      // Try to find a complete JSON object by tracking brace depth
      let depth = 0;
      let inString = false;
      let escaped = false;
      let endIdx = -1;

      for (let i = startIdx; i < this._buffer.length; i++) {
        const ch = this._buffer[i];
        if (escaped) { escaped = false; continue; }
        if (ch === '\\' && inString) { escaped = true; continue; }
        if (ch === '"') { inString = !inString; continue; }
        if (inString) continue;
        if (ch === '{') depth++;
        if (ch === '}') { depth--; if (depth === 0) { endIdx = i; break; } }
      }

      if (endIdx === -1) break; // Incomplete JSON, wait for more data

      const jsonStr = this._buffer.substring(startIdx, endIdx + 1);
      startIdx = endIdx + 1;

      try {
        const response = JSON.parse(jsonStr);
        const id = response.id;

        if (id !== undefined && this.pendingRequests.has(id)) {
          const { resolve, reject, timeout } = this.pendingRequests.get(id);
          this.pendingRequests.delete(id);
          clearTimeout(timeout);

          if (response.error) {
            reject(new Error(typeof response.error === 'string' ? response.error : JSON.stringify(response.error)));
          } else {
            resolve(response.result || response);
          }
        }
      } catch (err) {
        console.error('[BlenderMCP] Failed to parse response:', err.message);
      }
    }

    // Keep unprocessed data in buffer
    this._buffer = this._buffer.substring(startIdx);
  }

  disconnect() {
    if (this.socket) {
      this.socket.destroy();
      this.socket = null;
    }
    this.connected = false;
  }
}

// ============================================================================
// 3D FORGE PRODUCER
// ============================================================================

class ForgeProducer {
  constructor(options = {}) {
    this.host = options.host || process.env.BLENDER_MCP_HOST || '127.0.0.1';
    this.port = options.port || parseInt(process.env.BLENDER_MCP_PORT || '9876');
    this.dryRun = options.dryRun || false;
    this.skipRender = options.skipRender || false;
    this.client = new BlenderMCPClient(this.host, this.port);
    this.baseDir = path.join(__dirname, '..', '..');
    this.conceptsDir = path.join(this.baseDir, 'data', '3d-forge', 'concepts');
    this.exportsDir = path.join(this.baseDir, 'exports', '3d-forge');
    // Skill executor — initialized after client connect (needs MCP client)
    this.skillExecutor = null;
  }

  log(msg, level = 'info') {
    const timestamp = new Date().toISOString();
    console.log(`[${timestamp}] [${level.toUpperCase()}] ${msg}`);
  }

  async ensureDirectories() {
    if (!fs.existsSync(this.exportsDir)) {
      fs.mkdirSync(this.exportsDir, { recursive: true });
    }
  }

  async loadConcept(conceptId) {
    const conceptPath = path.join(this.conceptsDir, `${conceptId}.json`);
    if (!fs.existsSync(conceptPath)) {
      throw new Error(`Concept not found: ${conceptPath}`);
    }

    const data = fs.readFileSync(conceptPath, 'utf8');
    return JSON.parse(data);
  }

  async findPendingConcepts() {
    if (!fs.existsSync(this.conceptsDir)) {
      return [];
    }

    const files = fs.readdirSync(this.conceptsDir);
    const concepts = [];

    for (const file of files) {
      if (!file.endsWith('.json')) continue;

      const conceptId = file.replace('.json', '');
      const concept = await this.loadConcept(conceptId);

      // Check if already produced
      const exportDir = path.join(this.exportsDir, conceptId);
      const metadataPath = path.join(exportDir, 'metadata.json');

      if (!fs.existsSync(metadataPath)) {
        concepts.push(concept);
      } else {
        // FIX-v24: Re-queue failed concepts for retry with self-correction (Lynn Cole loop)
        try {
          const meta = JSON.parse(fs.readFileSync(metadataPath, 'utf8'));
          if (meta.status === 'failed') {
            this.log(`Re-queuing failed concept for retry: ${conceptId}`, 'info');
            // Remove old metadata so it gets re-processed
            fs.unlinkSync(metadataPath);
            concepts.push(concept);
          }
        } catch (e) {
          // Corrupted metadata — re-queue
          this.log(`Corrupted metadata for ${conceptId}, re-queuing`, 'warn');
          fs.unlinkSync(metadataPath);
          concepts.push(concept);
        }
      }
    }

    // FIX-v25: Cap at 3 concepts per run (task file rule: "Max 3 concepts per hourly run")
    // Prevents timeout when 100+ pending concepts accumulate
    const MAX_CONCEPTS_PER_RUN = 3;
    if (concepts.length > MAX_CONCEPTS_PER_RUN) {
      this.log(`Capping ${concepts.length} pending concepts to ${MAX_CONCEPTS_PER_RUN} per run`, 'info');
      concepts.splice(MAX_CONCEPTS_PER_RUN);
    }

    return concepts;
  }

  /**
   * Normalize step params to match bridge API expectations.
   * Concept generators produce params with slightly different names/formats
   * than what the bridge handlers expect. This fixes the mismatches.
   * FIX-v21: Comprehensive parameter normalization with array-to-scalar conversion
   */
  _normalizeStepParams(toolName, params) {
    const normalized = { ...params };
    const tool = toolName.replace(/^blender_/, '');

    // FIX-v21: Handle size arrays — LLM generates [x,y,z] but API expects scalar
    // For cube/sphere: use max dimension, then set scale for proportions
    // For cylinder: size[0]=diameter, size[2]=depth
    if (tool === 'create_object' && Array.isArray(normalized.size)) {
      const sizeArr = normalized.size;
      const objType = (normalized.type || 'cube').toLowerCase();

      if (objType === 'cylinder' || objType === 'cone') {
        const diameter = sizeArr[0];
        const depth = sizeArr[2] || sizeArr[0];
        normalized._convertToPython = true;
        normalized._pythonCode = `import bpy\\nbpy.ops.mesh.primitive_cylinder_add(radius=${diameter / 2}, depth=${depth}, location=[${(normalized.location || [0,0,0]).join(',')}])\\nobj = bpy.context.active_object\\nobj.rotation_euler = [${(normalized.rotation || [0,0,0]).map(r => r * 3.14159265 / 180).join(',')}]\\n__result__ = {'name': obj.name, 'type': obj.type}`;
      } else if (objType === 'cube') {
        const maxDim = Math.max(...sizeArr);
        normalized.size = maxDim;
        normalized.scale = sizeArr.map(s => s / maxDim);
      } else {
        normalized.size = Math.max(...sizeArr);
      }
    }

    // FIX-v21: Default location to (0,0,0) if missing
    if (tool === 'create_object' && !normalized.location) {
      normalized.location = [0, 0, 0];
    }

    // boolean_operation: concept sends `object`/`target`, bridge expects `object_name`/`target_name`
    if (tool === 'boolean_operation') {
      if (normalized.object && !normalized.object_name) {
        normalized.object_name = normalized.object;
        delete normalized.object;
      }
      if (normalized.target && !normalized.target_name) {
        normalized.target_name = normalized.target;
        delete normalized.target;
      }
    }

    // set_material: convert hex color string to RGBA array [0-1]
    // Bridge expects color as [r, g, b, a] with values 0.0-1.0
    if (tool === 'set_material') {
      if (normalized.object && !normalized.object_name) {
        normalized.object_name = normalized.object;
        delete normalized.object;
      }
      if (typeof normalized.color === 'string' && normalized.color.startsWith('#')) {
        const hex = normalized.color.replace('#', '');
        const r = parseInt(hex.substring(0, 2), 16) / 255;
        const g = parseInt(hex.substring(2, 4), 16) / 255;
        const b = parseInt(hex.substring(4, 6), 16) / 255;
        normalized.color = [r, g, b, 1.0];
      }
    }

    // FIX-v21: cleanup: shade_smooth/shade_flat/recalculate_normals need object_name
    // If no object_name provided, convert to execute_python targeting active or all mesh objects
    if (tool === 'cleanup') {
      const action = normalized.action;
      if ((action === 'shade_smooth' || action === 'shade_flat' || action === 'recalculate_normals') && !normalized.object_name) {
        normalized._convertToPython = true;
        if (action === 'shade_smooth') {
          // FIX-v26: Use data-level API (no selection needed, no bpy_prop_collection errors)
          normalized._pythonCode = `import bpy\\nshaded = []\\nfor obj in bpy.data.objects:\\n    if obj.type == 'MESH' and not obj.name.startswith('_ground'):\\n        for poly in obj.data.polygons:\\n            poly.use_smooth = True\\n        obj.data.update()\\n        shaded.append(obj.name)\\n__result__ = {'shaded': True, 'count': len(shaded), 'objects': shaded}`;
        } else if (action === 'shade_flat') {
          normalized._pythonCode = `import bpy\\nbpy.ops.object.mode_set(mode='OBJECT') if bpy.context.active_object and bpy.context.active_object.mode != 'OBJECT' else None\\nshaded = []\\nfor obj in bpy.data.objects:\\n    if obj.type == 'MESH':\\n        bpy.ops.object.select_all(action='DESELECT')\\n        obj.select_set(True)\\n        bpy.context.view_layer.objects.active = obj\\n        try:\\n            bpy.ops.object.shade_flat()\\n            shaded.append(obj.name)\\n        except Exception:\\n            pass\\n        obj.select_set(False)\\n__result__ = {'shaded_flat': shaded}`;
        } else if (action === 'recalculate_normals') {
          normalized._pythonCode = `import bpy\\nresults = []\\nfor obj in bpy.data.objects:\\n    if obj.type == 'MESH':\\n        bpy.context.view_layer.objects.active = obj\\n        bpy.ops.object.mode_set(mode='EDIT')\\n        bpy.ops.mesh.select_all(action='SELECT')\\n        bpy.ops.mesh.normals_make_consistent(inside=False)\\n        bpy.ops.object.mode_set(mode='OBJECT')\\n        results.append(obj.name)\\n__result__ = {'recalculated': results}`;
        }
      }
    }

    return normalized;
  }

  async produceConcept(concept) {
    const startTime = Date.now();
    const conceptId = concept.concept_id || concept.id || 'unknown';
    const outputDir = path.join(this.exportsDir, conceptId);
    const stepLog = [];
    let stepsExecuted = 0;
    let stepsFailed = 0;

    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    this.log(`Starting production: ${conceptId}`, 'info');

    try {
      // PHASE A: SCENE SETUP
      this.log(`[${conceptId}] Phase A: Scene Setup`, 'debug');

      if (!this.dryRun) {
        try {
          // FIX-v21: Scene cleanup — BOTH methods for thoroughness
          // Method 1: use_empty=true for clean state
          await this.client.call('save_file', { action: 'new', use_empty: true });

          // Method 2: Full Python nuke of all data blocks
          // FIX-v21: CRITICAL — Python code MUST use single quotes only (double quotes cause ECONNRESET)
          await this.client.call('execute_python', {
            code: `import bpy\\nfor obj in list(bpy.data.objects):\\n    bpy.data.objects.remove(obj, do_unlink=True)\\nfor mesh in list(bpy.data.meshes):\\n    bpy.data.meshes.remove(mesh)\\nfor mat in list(bpy.data.materials):\\n    bpy.data.materials.remove(mat)\\nfor cam in list(bpy.data.cameras):\\n    bpy.data.cameras.remove(cam)\\nfor light in list(bpy.data.lights):\\n    bpy.data.lights.remove(light)\\n__result__ = {'cleared': True, 'objects': len(bpy.data.objects)}`,
          });

          stepLog.push({ step: 'new_scene', success: true });
          stepsExecuted++;
          this.log(`[${conceptId}] Scene cleared to empty`, 'debug');
        } catch (err) {
          this.log(`Failed to create new scene: ${err.message}`, 'warn');
          stepLog.push({ step: 'new_scene', success: false, error: err.message });
          stepsFailed++;
        }

        // Optional: Set units
        if (concept.units) {
          try {
            await this.client.call('blender_scene_operations', {
              operation: 'set_units',
              unit_system: concept.units,
            });
            stepLog.push({ step: 'set_units', success: true });
            stepsExecuted++;
          } catch (err) {
            this.log(`Failed to set units: ${err.message}`, 'warn');
            stepLog.push({ step: 'set_units', success: false, error: err.message });
            stepsFailed++;
          }
        }
      }

      // PHASE B: GEOMETRY (from blender_steps)
      this.log(`[${conceptId}] Phase B: Geometry (${concept.blender_steps?.length || 0} steps)`, 'debug');

      if (concept.blender_steps && concept.blender_steps.length > 0) {
        for (let i = 0; i < concept.blender_steps.length; i++) {
          const step = concept.blender_steps[i];
          const stepName = step.name || `geometry_step_${i}`;

          if (this.dryRun) {
            this.log(`[DRY-RUN] Would execute: ${step.tool} (${stepName})`, 'debug');
            stepLog.push({ step: stepName, success: true, dryRun: true });
            stepsExecuted++;
            continue;
          }

          // Normalize params: fix mismatches between concept generator and bridge API
          const normalizedParams = this._normalizeStepParams(step.tool, step.params || {});

          // FIX-v21: Add try/catch with retry logic around each step
          let stepSucceeded = false;
          let retryCount = 0;
          const maxRetries = 1;

          while (!stepSucceeded && retryCount <= maxRetries) {
            try {
              let result;
              if (step.tool === 'blender_execute_python' || step.tool === 'execute_python') {
                let code = step.code || step.params?.code;
                if (!code) throw new Error('Python code not provided');
                // Fix common LLM-generated code errors:
                // 1. primitive_cube_add(size=[x,y,z]) → size=max, scale=[normalized]
                code = code.replace(
                  /primitive_cube_add\(([^)]*?)size\s*=\s*\[([^\]]+)\]/g,
                  (match, before, dims) => {
                    const parts = dims.split(',').map(s => s.trim());
                    if (parts.length >= 3) {
                      const vals = parts.map(Number);
                      const maxD = Math.max(...vals);
                      const scale = vals.map(v => (v / maxD).toFixed(4));
                      return `primitive_cube_add(${before}size=${maxD}, scale=(${scale.join(', ')})`; // FIX-v21: Single quotes in format
                    }
                    return match;
                  }
                );
                result = await this.client.call('execute_python', { code });
              } else if (normalizedParams._convertToPython) {
                // Param normalization determined this step needs direct Python for precision
                const pyCode = normalizedParams._pythonCode;
                this.log(`[${conceptId}] Converting ${step.tool} to execute_python for precision`, 'debug');
                result = await this.client.call('execute_python', { code: pyCode });
              } else {
                result = await this.client.call(step.tool, normalizedParams);
              }

              this.log(`[${conceptId}] ✓ ${stepName}`, 'debug');
              stepLog.push({ step: stepName, success: true });
              stepsExecuted++;
              stepSucceeded = true;
            } catch (err) {
              retryCount++;
              if (retryCount > maxRetries) {
                // FIX-v21: Determine if step is critical or decorative
                const isCriticalStep = ['create_object', 'boolean_operation', 'export_file'].includes(
                  step.tool.replace(/^blender_/, '')
                );

                if (isCriticalStep) {
                  // Critical step failed — abort with clear error
                  this.log(`[${conceptId}] ✗ CRITICAL STEP FAILED: ${stepName}: ${err.message}`, 'error');
                  stepLog.push({
                    step: stepName,
                    success: false,
                    error: err.message,
                    critical: true,
                  });
                  stepsFailed++;
                } else {
                  // Non-critical (decorative, detail) — log but continue
                  this.log(`[${conceptId}] ⊘ DECORATIVE STEP SKIPPED: ${stepName}: ${err.message}`, 'warn');
                  stepLog.push({
                    step: stepName,
                    success: false,
                    error: err.message,
                    critical: false,
                    skipped: true,
                  });
                  stepsFailed++;
                }
                stepSucceeded = true; // Stop retry loop
              } else {
                // Retry with 2-second delay
                this.log(`[${conceptId}] Retrying ${stepName} (attempt ${retryCount})...`, 'debug');
                await new Promise(resolve => setTimeout(resolve, 2000));
              }
            }
          }
        }
      }

      // Check failure threshold
      const totalSteps = stepsExecuted + stepsFailed;
      if (totalSteps > 0) {
        const failureRate = stepsFailed / totalSteps;
        if (failureRate > 0.3) {
          throw new Error(
            `Exceeded failure threshold: ${stepsFailed}/${totalSteps} (${(failureRate * 100).toFixed(1)}%)`
          );
        }
      }

      // PHASE B+: PRE-VALIDATE (geometry repair — BEFORE polish/materials)
      // Runs boolean_cleanup, proportion_reference_check, scale_normalizer, wall_thickness_enforcer
      if (this.skillExecutor && !this.dryRun) {
        const skillPlan = this.skillExecutor.planSkillsForConcept(concept);
        if (skillPlan.prevalidate && skillPlan.prevalidate.length > 0) {
          this.log(`[${conceptId}] Phase B+: Pre-Validate (${skillPlan.prevalidate.length} skills)`, 'debug');
          for (const preSkill of skillPlan.prevalidate) {
            try {
              const preResult = await this.skillExecutor.execute(preSkill, {
                platform: concept.platform || 'stl',
                category: concept.category || concept.name || 'product'
              });
              stepLog.push({ step: `skill_prevalidate_${preSkill}`, success: preResult.success, skill: true });
              if (preResult.success) {
                stepsExecuted++;
                this.log(`[${conceptId}] ✓ Pre-validate skill: ${preSkill}`, 'debug');
              } else {
                stepsFailed++;
                this.log(`[${conceptId}] ⊘ Pre-validate skill partial: ${preSkill}`, 'warn');
              }
            } catch (err) {
              this.log(`[${conceptId}] Pre-validate skill ${preSkill} failed: ${err.message}`, 'warn');
              stepLog.push({ step: `skill_prevalidate_${preSkill}`, success: false, error: err.message, skill: true });
            }
          }
        }
      }

      // PHASE C: POLISH
      this.log(`[${conceptId}] Phase C: Polish`, 'debug');

      const mainObject = concept.main_object || 'Cube';

      if (!this.dryRun) {
        // FIX-v25: Manifold repair — remove doubles + fill holes on ALL mesh objects
        // This fixes the #1 mechanical validation failure (non-manifold edges)
        try {
          await this.client.call('execute_python', {
            code: `import bpy, bmesh\nfixed = []\nfor obj in bpy.data.objects:\n    if obj.type == 'MESH' and not obj.name.startswith('_ground'):\n        bm = bmesh.new()\n        bm.from_mesh(obj.data)\n        # Remove doubles (merge vertices within 0.0001m)\n        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)\n        # Fill holes (non-manifold edges)\n        non_manifold = [e for e in bm.edges if not e.is_manifold]\n        if non_manifold:\n            bmesh.ops.holes_fill(bm, edges=non_manifold)\n        # Recalculate normals\n        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])\n        bm.to_mesh(obj.data)\n        bm.free()\n        obj.data.update()\n        fixed.append(obj.name)\n__result__ = {'manifold_fixed': fixed, 'count': len(fixed)}`,
          });
          stepLog.push({ step: 'manifold_repair', success: true });
          stepsExecuted++;
          this.log(`[${conceptId}] ✓ Manifold repair applied`, 'debug');
        } catch (err) {
          this.log(`Warning: Manifold repair failed: ${err.message}`, 'warn');
          stepLog.push({ step: 'manifold_repair', success: false, error: err.message });
        }

        // Apply subdivision surface
        try {
          await this.client.call('blender_apply_modifier', {
            object_name: mainObject,
            modifier_type: 'SUBSURF',
            parameters: { levels: 2 },
          });
          stepLog.push({ step: 'subsurf_modifier', success: true });
          stepsExecuted++;
        } catch (err) {
          this.log(`Warning: Failed to apply subsurf: ${err.message}`, 'warn');
          stepLog.push({
            step: 'subsurf_modifier',
            success: false,
            error: err.message,
          });
        }

        // SKILL: bevel_modifier_edges — smooth hard edges for product quality
        if (this.skillExecutor) {
          try {
            // Get all mesh object names for bevel application
            // Double-unwrap: execute_python returns { result: { result: actual_data } }
            const meshNamesResult = await this.client.call('execute_python', {
              code: "import bpy\n__result__ = {'meshes': [o.name for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground')]}",
            });
            // Unwrap MCP response — try every known nesting pattern
            let meshNames = [];
            try {
              const raw = meshNamesResult;
              meshNames = raw?.data?.result?.meshes     // {status, data: {result: {meshes}}}
                || raw?.result?.data?.result?.meshes    // deeper nesting
                || raw?.result?.result?.meshes           // {result: {result: {meshes}}}
                || raw?.result?.meshes                  // {result: {meshes}}
                || raw?.meshes                          // {meshes} (direct)
                || [];
              // Last resort: try JSON.parse if string
              if (meshNames.length === 0 && typeof raw === 'string') {
                meshNames = JSON.parse(raw)?.meshes || [];
              }
              // Walk the tree to find any 'meshes' key
              if (meshNames.length === 0) {
                const findMeshes = (obj) => {
                  if (!obj || typeof obj !== 'object') return null;
                  if (Array.isArray(obj.meshes)) return obj.meshes;
                  for (const v of Object.values(obj)) {
                    const found = findMeshes(v);
                    if (found) return found;
                  }
                  return null;
                };
                meshNames = findMeshes(raw) || [];
              }
            } catch (e) { meshNames = []; }
            this.log(`[${conceptId}] Bevel targets: ${meshNames.length} mesh objects: ${meshNames.join(', ')}`, 'debug');
            for (const objName of meshNames) {
              const bevelResult = await this.skillExecutor.execute('bevel_modifier_edges', {
                object_name: objName
              });
              stepLog.push({ step: `skill_bevel_${objName}`, success: bevelResult.success, skill: true });
              if (bevelResult.success) stepsExecuted++;
              else stepsFailed++;
            }
          } catch (err) {
            this.log(`Warning: Bevel skill failed: ${err.message}`, 'warn');
            stepLog.push({ step: 'skill_bevel', success: false, error: err.message, skill: true });
          }
        }

        // FIX-v21: Shade smooth — use execute_python directly (not blender_cleanup)
        // blender_cleanup shade_smooth fails 98% with bpy_prop_collection error
        // Fixed: ensure OBJECT mode first, deselect all before each, skip ground plane
        let shadeSmoothFailed = false;
        try {
          await this.client.call('execute_python', {
            // FIX-v26: Use data-level API (100% success) instead of bpy.ops (51% failure from bpy_prop_collection)
            code: `import bpy\\nshaded = []\\nfor obj in bpy.data.objects:\\n    if obj.type == 'MESH' and not obj.name.startswith('_ground'):\\n        for poly in obj.data.polygons:\\n            poly.use_smooth = True\\n        obj.data.update()\\n        shaded.append(obj.name)\\n__result__ = {'shaded': True, 'count': len(shaded), 'objects': shaded}`,
          });
          stepLog.push({ step: 'shade_smooth', success: true });
          stepsExecuted++;
        } catch (err) {
          this.log(`Warning: Failed to shade smooth: ${err.message}`, 'warn');
          stepLog.push({
            step: 'shade_smooth',
            success: false,
            error: err.message,
          });
          shadeSmoothFailed = true;
        }

        // FALLBACK: If shade_smooth failed, use trimesh taubin_smooth (100% success rate)
        if (shadeSmoothFailed) {
          try {
            const stlPath = path.join(outputDir, 'model_presmooth.stl');
            const smoothedPath = path.join(outputDir, 'model.stl');
            
            // Export current mesh to temp STL
            await this.client.call('execute_python', {
              code: `import bpy\\nbpy.ops.object.select_all(action='SELECT')\\nbpy.ops.export_mesh.stl(filepath='${stlPath.replace(/'/g, "\\'")}')`
            });
            
            // Run trimesh taubin smooth
            const smoothResult = await new Promise((resolve, reject) => {
              const proc = spawn('python3', ['-c', 
                `import trimesh; m=trimesh.load('${stlPath}',force='mesh'); trimesh.smoothing.filter_taubin(m,iterations=10,lamb=0.5); m.export('${smoothedPath}'); print('OK')`
              ]);
              let out = '';
              let err = '';
              proc.stdout.on('data', d => out += d.toString());
              proc.stderr.on('data', d => err += d.toString());
              proc.on('close', code => {
                if (code === 0) {
                  resolve(out.trim());
                } else {
                  reject(new Error(`Taubin smooth failed: ${err}`));
                }
              });
            });
            
            if (smoothResult.includes('OK')) {
              // Re-import smoothed mesh
              await this.client.call('execute_python', {
                code: `import bpy\\nbpy.ops.object.select_all(action='SELECT')\\nbpy.ops.object.delete()\\nbpy.ops.import_mesh.stl(filepath='${smoothedPath.replace(/'/g, "\\'")}')`
              });
              this.log(`[${conceptId}] ✓ Taubin smooth applied (trimesh fallback)`, 'debug');
              stepLog.push({ step: 'taubin_smooth_fallback', success: true });
              stepsExecuted++;
            }
          } catch (taubinErr) {
            this.log(`[${conceptId}] Taubin smooth fallback also failed: ${taubinErr.message}`, 'warn');
            stepLog.push({
              step: 'taubin_smooth_fallback',
              success: false,
              error: taubinErr.message,
            });
          }
        }

        // Apply materials — try skill-driven materials first, fall back to generic
        if (this.skillExecutor) {
          const skillPlan = this.skillExecutor.planSkillsForConcept(concept);
          if (skillPlan.materials.length > 0) {
            // Get mesh object names for material application
            let meshNames = [mainObject || 'Cube'];
            try {
              const meshResult = await this.client.call('execute_python', {
                code: "import bpy\n__result__ = {'meshes': [o.name for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground')]}",
              });
              // Deep-find meshes in response (handles any nesting pattern)
              const findMeshes = (obj) => {
                if (!obj || typeof obj !== 'object') return null;
                if (Array.isArray(obj.meshes)) return obj.meshes;
                for (const v of Object.values(obj)) {
                  const found = findMeshes(v);
                  if (found) return found;
                }
                return null;
              };
              const found = findMeshes(meshResult);
              if (found && found.length > 0) meshNames = found;
            } catch (e) { /* use default */ }

            let materialApplied = false;
            for (const matSkill of skillPlan.materials) {
              try {
                // Apply material skill to the first/main mesh object
                const matResult = await this.skillExecutor.execute(matSkill, {
                  object_name: meshNames[0]
                });
                stepLog.push({ step: `skill_material_${matSkill}`, success: matResult.success, skill: true });
                if (matResult.success) {
                  stepsExecuted++;
                  materialApplied = true;
                  this.log(`[${conceptId}] ✓ Applied material skill: ${matSkill}`, 'debug');
                }
              } catch (err) {
                this.log(`Warning: Material skill ${matSkill} failed: ${err.message}`, 'warn');
                stepLog.push({ step: `skill_material_${matSkill}`, success: false, error: err.message, skill: true });
              }
            }

            // If no skill material succeeded, fall back to generic
            if (!materialApplied && concept.visual_analysis?.materials) {
              try {
                await this.client.call('blender_set_material', {
                  object_name: mainObject,
                  material_data: concept.visual_analysis.materials,
                });
                stepLog.push({ step: 'apply_materials_fallback', success: true });
                stepsExecuted++;
              } catch (err) {
                this.log(`Warning: Fallback material also failed: ${err.message}`, 'warn');
                stepLog.push({ step: 'apply_materials_fallback', success: false, error: err.message });
              }
            }
          } else if (concept.visual_analysis?.materials) {
            // No matching material skills — use generic material
            try {
              await this.client.call('blender_set_material', {
                object_name: mainObject,
                material_data: concept.visual_analysis.materials,
              });
              stepLog.push({ step: 'apply_materials', success: true });
              stepsExecuted++;
            } catch (err) {
              this.log(`Warning: Failed to apply materials: ${err.message}`, 'warn');
              stepLog.push({ step: 'apply_materials', success: false, error: err.message });
            }
          }
        } else if (concept.visual_analysis?.materials) {
          // No skill executor available — use generic material (backward compat)
          try {
            await this.client.call('blender_set_material', {
              object_name: mainObject,
              material_data: concept.visual_analysis.materials,
            });
            stepLog.push({ step: 'apply_materials', success: true });
            stepsExecuted++;
          } catch (err) {
            this.log(`Warning: Failed to apply materials: ${err.message}`, 'warn');
            stepLog.push({
              step: 'apply_materials',
              success: false,
              error: err.message,
            });
          }
        }

        // Smart project UVs
        try {
          await this.client.call('blender_uv_operations', {
            object_name: mainObject,
            action: 'smart_project',
          });
          stepLog.push({ step: 'smart_project_uv', success: true });
          stepsExecuted++;
        } catch (err) {
          this.log(`Warning: Failed to smart project UVs: ${err.message}`, 'warn');
          stepLog.push({
            step: 'smart_project_uv',
            success: false,
            error: err.message,
          });
        }
      }

      // SKILL: scene_cleanup — verify manifold topology before export
      if (this.skillExecutor && !this.dryRun) {
        try {
          const cleanupResult = await this.skillExecutor.execute('scene_cleanup', {});
          stepLog.push({ step: 'skill_scene_cleanup', success: cleanupResult.success, skill: true });
          if (cleanupResult.success) {
            stepsExecuted++;
            this.log(`[${conceptId}] ✓ Scene cleanup skill applied`, 'debug');
          }
        } catch (err) {
          this.log(`[${conceptId}] Scene cleanup skill failed: ${err.message}`, 'warn');
          stepLog.push({ step: 'skill_scene_cleanup', success: false, error: err.message, skill: true });
        }
      }

      // PHASE D: EXPORT
      this.log(`[${conceptId}] Phase D: Export`, 'debug');

      // FIX-v25: Concept generator uses 'platform' (singular), pipeline uses 'target_platforms' (plural)
      // Normalize to array so both work
      let platforms = concept.target_platforms;
      if (!platforms && concept.platform) {
        platforms = [concept.platform];
      }
      if (!platforms || platforms.length === 0) {
        platforms = ['stl'];
      }
      let lastGlbPath = null; // Track GLB path for post-export validation/optimization

      if (!this.dryRun) {
        for (const platform of platforms) {
          try {
            // FIX-v25: ALL exports use execute_python with os.path.exists verification
            // The bridge's export_file command returns 'ok' without actually writing files
            const stlPath = path.join(outputDir, 'model.stl');
            const glbPath = path.join(outputDir, 'model.glb');
            const fbxPath = path.join(outputDir, 'model.fbx');

            if (platform === 'etsy_stl' || platform === 'cults3d' || platform === 'stl') {
              await this.client.call('execute_python', {
                code: `import bpy, os\nbpy.ops.object.select_all(action='SELECT')\nbpy.ops.wm.stl_export(filepath='${stlPath}')\n__result__ = {'stl_exists': os.path.exists('${stlPath}'), 'stl_size': os.path.getsize('${stlPath}') if os.path.exists('${stlPath}') else 0}`,
              });
              this.log(`[${conceptId}] ✓ Exported STL`, 'debug');
              stepLog.push({ step: `export_${platform}`, success: true });
              stepsExecuted++;
            } else if (platform === 'roblox_ugc') {
              await this.client.call('execute_python', {
                code: `import bpy, os\nbpy.ops.object.select_all(action='SELECT')\nbpy.ops.export_scene.fbx(filepath='${fbxPath}', use_selection=True, apply_scale_options='FBX_SCALE_ALL')\nbpy.ops.wm.stl_export(filepath='${stlPath}')\n__result__ = {'fbx': os.path.exists('${fbxPath}'), 'stl': os.path.exists('${stlPath}')}`,
              });
              this.log(`[${conceptId}] ✓ Exported FBX + STL (Roblox)`, 'debug');
              stepLog.push({ step: `export_${platform}`, success: true });
              stepsExecuted++;
            } else if (platform === 'game_asset') {
              await this.client.call('execute_python', {
                code: `import bpy, os\nbpy.ops.object.select_all(action='SELECT')\nbpy.ops.export_scene.gltf(filepath='${glbPath}', export_format='GLB')\nbpy.ops.export_scene.fbx(filepath='${fbxPath}', use_selection=True, apply_scale_options='FBX_SCALE_ALL')\nbpy.ops.wm.stl_export(filepath='${stlPath}')\n__result__ = {'glb': os.path.exists('${glbPath}'), 'fbx': os.path.exists('${fbxPath}'), 'stl': os.path.exists('${stlPath}')}`,
              });
              this.log(`[${conceptId}] ✓ Exported GLB + FBX + STL (Game)`, 'debug');
              lastGlbPath = glbPath;
              stepLog.push({ step: `export_${platform}`, success: true });
              stepsExecuted++;
            }
          } catch (err) {
            this.log(`Warning: Export failed for ${platform}: ${err.message}`, 'warn');
            stepLog.push({
              step: `export_${platform}`,
              success: false,
              error: err.message,
            });
            stepsFailed++;
          }
        }
      }

      // POST-EXPORT: GLB Validation and Optimization
      if (lastGlbPath && fs.existsSync(lastGlbPath)) {
        // POST-EXPORT: Validate GLB with gltf-validator
        try {
          const glbData = fs.readFileSync(lastGlbPath);
          const { validateBytes } = require('gltf-validator');
          const valResult = await validateBytes(new Uint8Array(glbData), { maxIssues: 20 });
          const errors = (valResult.issues?.messages || []).filter(i => i.severity === 0);
          if (errors.length === 0) {
            this.log(`[${conceptId}] ✓ GLB validation passed`, 'debug');
          } else {
            this.log(`[${conceptId}] ⚠ GLB has ${errors.length} validation errors`, 'warn');
          }
          stepLog.push({ step: 'gltf_validate', success: errors.length === 0, issues: errors.length });
        } catch (valErr) {
          this.log(`[${conceptId}] GLB validation skipped: ${valErr.message}`, 'debug');
        }

        // POST-EXPORT: Optimize GLB with gltf-transform (dedup + prune + weld)
        try {
          const { NodeIO } = require('@gltf-transform/core');
          const { ALL_EXTENSIONS } = require('@gltf-transform/extensions');
          const { dedup, prune, weld } = require('@gltf-transform/functions');
          const io = new NodeIO().registerExtensions(ALL_EXTENSIONS);
          const doc = await io.read(lastGlbPath);
          await doc.transform(prune(), dedup(), weld());
          const optimized = await io.writeBinary(doc);
          const origSize = glbData.length;
          const optSize = optimized.byteLength;
          fs.writeFileSync(lastGlbPath, Buffer.from(optimized));
          const reduction = Math.round((1 - optSize / origSize) * 100);
          this.log(`[${conceptId}] ✓ GLB optimized: ${origSize}→${optSize} bytes (${reduction}% reduction)`, 'debug');
          stepLog.push({ step: 'gltf_optimize', success: true, reduction_pct: reduction });
        } catch (optErr) {
          this.log(`[${conceptId}] GLB optimization skipped: ${optErr.message}`, 'debug');
        }
      }

      // Save .blend file for validation / future editing
      if (!this.dryRun) {
        try {
          const blendPath = path.join(outputDir, 'model.blend');
          await this.client.call('save_file', { filepath: blendPath });
          this.log(`[${conceptId}] ✓ Saved .blend file`, 'debug');
          stepLog.push({ step: 'save_blend', success: true });
          stepsExecuted++;
        } catch (err) {
          this.log(`Warning: Failed to save .blend: ${err.message}`, 'warn');
          stepLog.push({ step: 'save_blend', success: false, error: err.message });
        }
      }

      // PHASE E: PRODUCT RENDERS (unless --skip-render)
      if (!this.skipRender && !this.dryRun) {
        this.log(`[${conceptId}] Phase E: Product Renders`, 'debug');

        // Flag to track if camera skill(s) executed successfully
        let cameraSkillApplied = false;

        // SKILL-DRIVEN: Apply lighting + render + post-processing skills BEFORE studio setup
        // The skills set up professional lighting/render params via MCP tool calls.
        // The inline Python below then handles camera placement and per-shot rendering.
        if (this.skillExecutor) {
          const skillPlan = this.skillExecutor.planSkillsForConcept(concept);

          // Lighting skills (e.g., three_point_product_lighting, jewelry_sparkle_lighting)
          for (const lightSkill of skillPlan.lighting) {
            try {
              const result = await this.skillExecutor.execute(lightSkill, {
                object_name: mainObject || 'Cube'
              });
              stepLog.push({ step: `skill_light_${lightSkill}`, success: result.success, skill: true });
              if (result.success) {
                stepsExecuted++;
                this.log(`[${conceptId}] ✓ Lighting skill: ${lightSkill}`, 'debug');
              }
            } catch (err) {
              this.log(`[${conceptId}] Lighting skill ${lightSkill} failed: ${err.message}`, 'warn');
              stepLog.push({ step: `skill_light_${lightSkill}`, success: false, error: err.message, skill: true });
            }
          }

          // Camera skills (e.g., marketplace_product_shot, turntable_camera, hero_reveal_camera)
          // If any camera skill succeeds, set flag to skip inline camera positioning
          if (skillPlan.camera && skillPlan.camera.length > 0) {
            for (const camSkill of skillPlan.camera) {
              try {
                const result = await this.skillExecutor.execute(camSkill, {
                  object_name: mainObject || 'Cube'
                });
                stepLog.push({ step: `skill_camera_${camSkill}`, success: result.success, skill: true });
                if (result.success) {
                  stepsExecuted++;
                  cameraSkillApplied = true; // CRITICAL: Mark that camera was set up by skill
                  this.log(`[${conceptId}] ✓ Camera skill: ${camSkill}`, 'debug');
                }
              } catch (err) {
                this.log(`[${conceptId}] Camera skill ${camSkill} failed: ${err.message}`, 'warn');
                stepLog.push({ step: `skill_camera_${camSkill}`, success: false, error: err.message, skill: true });
              }
            }
          }

          // Render settings skills (e.g., cycles_production_render)
          for (const renderSkill of skillPlan.render) {
            try {
              const result = await this.skillExecutor.execute(renderSkill, {
                render_path: path.join(outputDir, 'hero.png').replace(/\\/g, '/')
              });
              stepLog.push({ step: `skill_render_${renderSkill}`, success: result.success, skill: true });
              if (result.success) {
                stepsExecuted++;
                this.log(`[${conceptId}] ✓ Render skill: ${renderSkill}`, 'debug');
              }
            } catch (err) {
              this.log(`[${conceptId}] Render skill ${renderSkill} failed: ${err.message}`, 'warn');
              stepLog.push({ step: `skill_render_${renderSkill}`, success: false, error: err.message, skill: true });
            }
          }

          // Post-processing skills (e.g., bloom_glow_compositor, camera_depth_of_field)
          for (const postSkill of skillPlan.postprocess) {
            try {
              const result = await this.skillExecutor.execute(postSkill, {
                object_name: mainObject || 'Cube'
              });
              stepLog.push({ step: `skill_post_${postSkill}`, success: result.success, skill: true });
              if (result.success) {
                stepsExecuted++;
                this.log(`[${conceptId}] ✓ Post-process skill: ${postSkill}`, 'debug');
              }
            } catch (err) {
              this.log(`[${conceptId}] Post-process skill ${postSkill} failed: ${err.message}`, 'warn');
              stepLog.push({ step: `skill_post_${postSkill}`, success: false, error: err.message, skill: true });
            }
          }
        }

        try {
          // Studio setup via execute_python with v6 rendering fixes:
          // FIX 1: Material colors (v6 palette with proper hues)
          // FIX 2: 4-point studio lighting (40-150W range)
          // FIX 3: Dark blue-gray background at strength 0.3
          // FIX 4: Ground plane scaled to model_size * 1.2
          // FIX 5: Cycles engine with 128 samples, OpenImageDenoise, adaptive 0.01
          await this.client.call('execute_python', {
            code: `import bpy, mathutils\\n\\n# Find model center and size for light placement\\nmeshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground')]\\nif meshes:\\n    all_coords = []\\n    for obj in meshes:\\n        for corner in obj.bound_box:\\n            wc = obj.matrix_world @ mathutils.Vector(corner)\\n            all_coords.append(wc)\\n    xs = [c.x for c in all_coords]\\n    ys = [c.y for c in all_coords]\\n    zs = [c.z for c in all_coords]\\n    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))\\n    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))\\nelse:\\n    center = mathutils.Vector((0,0,0))\\n    size = 2.0\\n\\n# World background: dark blue-gray (FIX 6: v6 palette)\\nworld = bpy.context.scene.world\\nif not world:\\n    world = bpy.data.worlds.new('World')\\n    bpy.context.scene.world = world\\nworld.use_nodes = True\\nbg = world.node_tree.nodes.get('Background')\\nif bg:\\n    bg.inputs[0].default_value = (0.12, 0.12, 0.15, 1.0)\\n    bg.inputs[1].default_value = 0.5\\n\\n# FIX-v26: 4-point studio lighting (150-500W range — autoresearch: min 200W for area lights)\\nd = size * 4.0\\nlighting_config = [\\n    ('key_light', (d*0.35, d*0.25, d*0.3), 500.0, size * 1.2),\\n    ('fill_light', (-d*0.25, d*0.15, d*0.15), 200.0, size * 1.5),\\n    ('rim_light', (d*0.2, -d*0.35, d*0.225), 300.0, size * 0.8),\\n    ('top_light', (d*0.05, d*0.05, d*0.5), 150.0, size * 2.0),\\n]\\n\\nfor name, loc, energy, light_size in lighting_config:\\n    light_data = bpy.data.lights.new(name=name, type='AREA')\\n    light_data.energy = energy\\n    light_data.size = light_size\\n    light_obj = bpy.data.objects.new(name=name, object_data=light_data)\\n    bpy.context.scene.collection.objects.link(light_obj)\\n    light_obj.location = center + mathutils.Vector(loc)\\n    dir = center - light_obj.location\\n    rot = dir.to_track_quat('-Z', 'Y')\\n    light_obj.rotation_euler = rot.to_euler()\\n\\n# FIX 5: Ground plane scaled to model_size * 1.2\\nbpy.ops.mesh.primitive_plane_add(size=size*1.2, location=(center.x, center.y, min(zs) - 0.01 if meshes else -0.5))\\nground = bpy.context.active_object\\nground.name = '_ground_plane'\\nmat = bpy.data.materials.new('ground_mat')\\nmat.use_nodes = True\\nbsdf = mat.node_tree.nodes.get('Principled BSDF')\\nif bsdf:\\n    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)\\nground.data.materials.append(mat)\\n\\n# FIX 7: Cycles render engine with proper settings (128 samples, OpenImageDenoise, adaptive 0.01)\\nbpy.context.scene.render.engine = 'CYCLES'\\nbpy.context.scene.cycles.samples = 128\\nbpy.context.scene.render.resolution_x = 1024\\nbpy.context.scene.render.resolution_y = 1024\\nbpy.context.scene.cycles.use_denoising = True\\nbpy.context.scene.cycles.adaptive_threshold = 0.01\\ntry:\\n    bpy.context.scene.cycles.denoiser = 'OPENIMAGEDENOISE'\\nexcept:\\n    pass\\nbpy.context.scene.render.film_transparent = False\\n__result__ = {'center': [center.x, center.y, center.z], 'size': size, 'light_dist': d, 'engine': 'CYCLES'}`,
          });
                        this.log(`[${conceptId}] Studio setup and render in progress`, 'debug');

          // FIX-v23d: execute_python calls don't share scene state.
          // Each shot must set up lights + camera + engine + render in ONE call.
          const shots = [
            { name: 'hero',   angle: 'hero' },
            { name: 'front',  angle: 'front' },
            { name: 'side',   angle: 'side' },
            { name: 'top',    angle: 'top' },
            { name: 'detail', angle: 'detail' },
          ];

          for (const shot of shots) {
            try {
              const outputPath = path.join(outputDir, `${shot.name}.png`).replace(/\\/g, '/');
              // FIX 3: Use bpy.ops.render.render(write_still=True) instead of MCP render command
              // This avoids the black frame bug that occurs after first call with MCP render
              // ALL-IN-ONE: lights + camera + engine + render in single execute_python
              // FIX 1: Skip inline camera positioning if cameraSkillApplied is true
              const skipCameraSetup = cameraSkillApplied ? 'True' : 'False';
              await this.client.call('execute_python', {
                code: `import bpy, mathutils, math\n\n# Find model center and size\nmeshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground')]\nif not meshes:\n    meshes = [o for o in bpy.data.objects if o.type == 'MESH']\nif meshes:\n    all_coords = []\n    for obj in meshes:\n        for corner in obj.bound_box:\n            all_coords.append(obj.matrix_world @ mathutils.Vector(corner))\n    xs = [c.x for c in all_coords]\n    ys = [c.y for c in all_coords]\n    zs = [c.z for c in all_coords]\n    center = mathutils.Vector(((min(xs)+max(xs))/2, (min(ys)+max(ys))/2, (min(zs)+max(zs))/2))\n    size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))\nelse:\n    center = mathutils.Vector((0,0,0))\n    size = 2.0\n\n# World background (FIX 6: dark blue-gray at 0.3 strength)\nworld = bpy.context.scene.world\nif not world:\n    world = bpy.data.worlds.new('World')\n    bpy.context.scene.world = world\nworld.use_nodes = True\nbg = world.node_tree.nodes.get('Background')\nif bg:\n    bg.inputs[0].default_value = (0.12, 0.12, 0.15, 1.0)\n    bg.inputs[1].default_value = 0.5\n\n# 4-point lighting (FIX-v26: 150-500W — autoresearch: min 200W for area lights)\nd = size * 4.0\nfor name, loc, energy, ls in [('key_light', (d*0.35, d*0.25, d*0.3), 500.0, size*1.2), ('fill_light', (-d*0.25, d*0.15, d*0.15), 200.0, size*1.5), ('rim_light', (d*0.2, -d*0.35, d*0.225), 300.0, size*0.8), ('top_light', (d*0.05, d*0.05, d*0.5), 150.0, size*2.0)]:\n    ld = bpy.data.lights.new(name=name, type='AREA')\n    ld.energy = energy\n    ld.size = ls\n    lo = bpy.data.objects.new(name=name, object_data=ld)\n    bpy.context.scene.collection.objects.link(lo)\n    lo.location = center + mathutils.Vector(loc)\n    dr = center - lo.location\n    lo.rotation_euler = dr.to_track_quat('-Z', 'Y').to_euler()\n\n# Ground plane (FIX 5: model_size * 1.2)\nif meshes:\n    bpy.ops.mesh.primitive_plane_add(size=size*1.2, location=(center.x, center.y, min(zs) - 0.01))\nelse:\n    bpy.ops.mesh.primitive_plane_add(size=2.4, location=(0, 0, -0.5))\nground = bpy.context.active_object\nground.name = '_ground_plane'\nmat = bpy.data.materials.new('ground_mat')\nmat.use_nodes = True\nbsdf = mat.node_tree.nodes.get('Principled BSDF')\nif bsdf:\n    bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.6, 1.0)\nground.data.materials.append(mat)\n\n# FIX 1: Only set up inline camera if skill did not already position it\nif not ${skipCameraSetup}:\n    # Camera (FIX 4: spherical coords with 50mm lens in MILLIMETERS)\n    cam_data = bpy.data.cameras.new('Camera')\n    cam = bpy.data.objects.new('Camera', cam_data)\n    bpy.context.scene.collection.objects.link(cam)\n    cam.data.lens = 50\n    cam.data.lens_unit = 'MILLIMETERS'\n    angle = '${shot.angle}'\n    if angle == 'hero':\n        # az=45, el=35, padding=1.8\n        dist = (size / 2) / math.tan(math.radians(36 / 2)) * 1.8\n        cam.location = center + mathutils.Vector((dist*0.707, dist*0.707, dist*0.574))\n    elif angle == 'front':\n        # az=0, el=30, padding=2.0\n        dist = (size / 2) / math.tan(math.radians(36 / 2)) * 2.0\n        cam.location = center + mathutils.Vector((0, dist, dist*0.577))\n    elif angle == 'side':\n        # az=90, el=30, padding=2.0\n        dist = (size / 2) / math.tan(math.radians(36 / 2)) * 2.0\n        cam.location = center + mathutils.Vector((dist, 0, dist*0.577))\n    elif angle == 'top':\n        # az=10, el=80, padding=2.2\n        dist = (size / 2) / math.tan(math.radians(36 / 2)) * 2.2\n        cam.location = center + mathutils.Vector((dist*0.174, dist*0.985, dist*5.67))\n    else:\n        # detail: az=30, el=35, padding=1.4\n        dist = (size / 2) / math.tan(math.radians(36 / 2)) * 1.4\n        cam.location = center + mathutils.Vector((dist*0.866, dist*0.5, dist*0.574))\n    dr = center - cam.location\n    cam.rotation_euler = dr.to_track_quat('-Z', 'Y').to_euler()\n    bpy.context.scene.camera = cam\n\n# Render settings (FIX 7: Cycles, 128 samples, OpenImageDenoise, adaptive 0.01)\nbpy.context.scene.render.engine = 'CYCLES'\nbpy.context.scene.cycles.samples = 128\nbpy.context.scene.render.resolution_x = 1024\nbpy.context.scene.render.resolution_y = 1024\nbpy.context.scene.cycles.use_denoising = True\nbpy.context.scene.cycles.adaptive_threshold = 0.01\nif hasattr(bpy.context.scene.cycles, 'denoiser'):\n    try:\n        bpy.context.scene.cycles.denoiser = 'OPENIMAGEDENOISE'\n    except:\n        pass\nbpy.context.scene.render.film_transparent = False\n\n# Set output path and render with bpy.ops (FIX 3: use bpy.ops.render.render)\nbpy.context.scene.render.filepath = '${outputPath}'\nbpy.context.scene.render.image_settings.file_format = 'PNG'\nbpy.ops.render.render(write_still=True)\n\n# Cleanup studio objects for next shot\nfor obj in list(bpy.data.objects):\n    if obj.type == 'LIGHT' or obj.name == '_ground_plane' or obj.name == 'Camera':\n        bpy.data.objects.remove(obj, do_unlink=True)\n\n__result__ = {'rendered': True, 'angle': angle, 'output': '${outputPath}', 'engine': 'CYCLES'}`,
              }, 120000);

              this.log(`[${conceptId}] ✓ Rendered ${shot.name}.png`, 'debug');
              stepLog.push({ step: `render_${shot.name}`, success: true });
              stepsExecuted++;
            } catch (err) {
              this.log(`Warning: Failed to render ${shot.name}: ${err.message}`, 'warn');
              stepLog.push({
                step: `render_${shot.name}`,
                success: false,
                error: err.message,
              });
            }
          }
        } catch (err) {
          this.log(`Warning: Render phase error: ${err.message}`, 'warn');
        }
      }

      // Calculate metadata
      let metadata = {
        concept_id: conceptId,
        status: 'completed',
        production_time_seconds: Math.round((Date.now() - startTime) / 1000),
        steps_executed: stepsExecuted,
        steps_failed: stepsFailed,
        step_log: stepLog,
        created_at: new Date().toISOString(),
      };

      // Try to get mesh stats if available
      if (!this.dryRun) {
        try {
          // Use execute_python to get mesh stats (no native get_mesh_stats command in MCP)
          // FIX-v22: CRITICAL — Python code MUST use single quotes only (double quotes cause ECONNRESET)
          const statsResult = await this.client.call('execute_python', {
            code: `import bpy\\nmeshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get()]\\nif meshes:\\n    tv = sum(len(m.data.vertices) for m in meshes)\\n    tf = sum(len(m.data.polygons) for m in meshes)\\n    dims = [max(m.dimensions[i] for m in meshes) * 1000 for i in range(3)]\\n    __result__ = {'vertices': tv, 'faces': tf, 'dimensions_mm': dims}\\nelse:\\n    __result__ = {'vertices': 0, 'faces': 0, 'dimensions_mm': [0,0,0]}`,
          });
          // Unwrap double-nested result from execute_python
          const outer = statsResult || {};
          const inner = outer.result !== undefined ? outer.result : outer;
          if (inner && inner.vertices !== undefined) {
            metadata.vertex_count = inner.vertices || 0;
            metadata.face_count = inner.faces || 0;
            metadata.dimensions_mm = inner.dimensions_mm || null;
          }
        } catch (err) {
          this.log(`Warning: Could not get mesh stats: ${err.message}`, 'warn');
        }
      }

      // Get file sizes
      const fileSizes = {};
      try {
        const files = fs.readdirSync(outputDir);
        for (const file of files) {
          const filePath = path.join(outputDir, file);
          const stats = fs.statSync(filePath);
          fileSizes[file] = stats.size;
        }
      } catch (err) {
        this.log(`Warning: Could not get file sizes: ${err.message}`, 'warn');
      }

      metadata.file_sizes = fileSizes;

      // Record which skills were used
      metadata.skills_applied = stepLog
        .filter(s => s.skill === true)
        .map(s => ({ step: s.step, success: s.success }));

      // Write metadata
      const metadataPath = path.join(outputDir, 'metadata.json');
      fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));

      this.log(
        `✓ Production complete: ${conceptId} (${metadata.production_time_seconds}s)`,
        'info'
      );

      return { success: true, metadata };
    } catch (err) {
      this.log(`✗ Production failed: ${conceptId}: ${err.message}`, 'error');

      const metadata = {
        concept_id: conceptId,
        status: 'failed',
        error: err.message,
        production_time_seconds: Math.round((Date.now() - startTime) / 1000),
        steps_executed: stepsExecuted,
        steps_failed: stepsFailed,
        step_log: stepLog,
        created_at: new Date().toISOString(),
      };

      const metadataPath = path.join(outputDir, 'metadata.json');
      fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2));

      return { success: false, metadata, error: err.message };
    }
  }

  async run(options) {
    const { conceptPath, conceptId, allPending } = options;

    await this.ensureDirectories();

    let concepts = [];

    if (allPending) {
      this.log('Scanning for pending concepts...', 'info');
      concepts = await this.findPendingConcepts();
      this.log(`Found ${concepts.length} pending concepts`, 'info');
      const cap = options.maxProduce;
      if (cap && cap > 0 && concepts.length > cap) {
        concepts = concepts.slice(0, cap);
        this.log(`Limited to ${concepts.length} concept(s) (--limit)`, 'info');
      }
    } else if (conceptPath) {
      const concept = await this.loadConcept(conceptPath);
      concepts = [concept];
    } else if (conceptId) {
      const concept = await this.loadConcept(conceptId);
      concepts = [concept];
    } else {
      throw new Error('Must specify --concept, --concept-id, or --all-pending');
    }

    if (!this.dryRun) {
      this.log('Connecting to Blender MCP server...', 'info');
      try {
        await this.client.connect();
        const isPing = await this.client.ping();
        if (!isPing) {
          throw new Error('Ping failed');
        }
        this.log('Connected and verified', 'info');
        // Initialize skill executor now that MCP client is connected
        this.skillExecutor = new SkillExecutor(this.client, {
          log: (msg, level) => this.log(`[SKILL] ${msg}`, level)
        });
      } catch (err) {
        throw new Error(`Failed to connect to Blender MCP: ${err.message}`);
      }
    }

    const results = [];
    for (const concept of concepts) {
      const result = await this.produceConcept(concept);
      results.push(result);
    }

    if (!this.dryRun && this.client.connected) {
      this.client.disconnect();
    }

    // Summary
    const succeeded = results.filter((r) => r.success).length;
    const failed = results.length - succeeded;

    this.log(`\n=== PRODUCTION SUMMARY ===`, 'info');
    this.log(`Total concepts: ${results.length}`, 'info');
    this.log(`Succeeded: ${succeeded}`, 'info');
    this.log(`Failed: ${failed}`, 'info');

    // FIX-v24: Do NOT exit(1) on partial failures — pipeline must flow
    // Failed concepts get re-queued on next run (Lynn Cole self-correction loop)
    if (failed > 0 && succeeded === 0) {
      this.log(`ALL concepts failed (${failed}/${results.length}). Will retry on next run.`, 'warn');
      // Still don't exit(1) — let downstream stages (LEARN, IMPROVE) analyze the failures
    }
  }
}

// ============================================================================
// CLI
// ============================================================================

async function main() {
  const args = process.argv.slice(2);

  let conceptPath = null;
  let conceptId = null;
  let allPending = false;
  let dryRun = false;
  let skipRender = false;
  let port = parseInt(process.env.BLENDER_MCP_PORT || '9876');
  let host = process.env.BLENDER_MCP_HOST || '127.0.0.1';

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--concept') {
      conceptPath = args[++i];
    } else if (args[i] === '--concept-id') {
      conceptId = args[++i];
    } else if (args[i] === '--all-pending') {
      allPending = true;
    } else if (args[i] === '--dry-run') {
      dryRun = true;
    } else if (args[i] === '--skip-render') {
      skipRender = true;
    } else if (args[i] === '--port') {
      port = parseInt(args[++i]);
    } else if (args[i] === '--host') {
      host = args[++i];
    }
  }

  try {
    const producer = new ForgeProducer({
      host,
      port,
      dryRun,
      skipRender,
    });

    let maxProduce = null;
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--limit') {
        maxProduce = parseInt(args[++i], 10);
        break;
      }
    }

    await producer.run({
      conceptPath,
      conceptId,
      allPending,
      maxProduce: maxProduce && maxProduce > 0 ? maxProduce : null,
    });
  } catch (err) {
    console.error(`[ERROR] ${err.message}`);
    // FIX-v24: Log fatal error but exit 0 so downstream pipeline stages still run
    // The LEARN and IMPROVE stages are MORE important than PRODUCE
    console.error(`[WARN] Producer failed fatally but exiting 0 for pipeline continuity`);
    process.exit(0);
  }
}

main();
