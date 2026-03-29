#!/usr/bin/env node
/**
 * 3D Asset Validator
 * Two-layer validation: mechanical checks (Blender) + visual quality (LLM)
 *
 * Usage:
 *   node asset-validator.js --concept-id ID [--skip-visual] [--auto-fix] [--dry-run]\n *   node asset-validator.js --all-pending [--skip-visual] [--auto-fix] [--dry-run]
 *
 * Environment:
 *   OPENAI_API_KEY (required for visual checks)
 *   BLENDER_MCP_HOST (default: localhost)
 *   BLENDER_MCP_PORT (default: 9876)
 */

const fs = require('fs');
const path = require('path');
const net = require('net');
const https = require('https');
const http = require('http'); // FIX-v26: Ollama runs on HTTP, not HTTPS
const { spawn } = require('child_process');
const { loadJson, classifyFailures } = require('./lib/failure-classifier');
const { appendFixEffect } = require('./lib/fix-effectiveness');

// Load .env
require('./lib/env').loadEnv();

// ============================================================================
// CONFIG
// ============================================================================

const BLENDER_MCP_HOST = process.env.BLENDER_MCP_HOST || 'localhost';
const BLENDER_MCP_PORT = parseInt(process.env.BLENDER_MCP_PORT || '9876', 10);
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const REPO_ROOT = path.join(__dirname, '..', '..');
const EXPORTS_DIR = path.join(REPO_ROOT, 'exports', '3d-forge');
const REFS_DIR = path.join(REPO_ROOT, 'data', '3d-forge', 'refs');
const SCORING_CONFIG_PATH = path.join(REPO_ROOT, 'config', '3d-forge', 'validation-scoring.json');
const FAILURE_TAXONOMY_PATH = path.join(REPO_ROOT, 'config', '3d-forge', 'failure-taxonomy.json');
const FIX_MAPPING_PATH = path.join(REPO_ROOT, 'config', '3d-forge', 'fix-mapping.json');
const FIX_EFFECTS_LOG_PATH = path.join(REPO_ROOT, 'data', '3d-forge', 'fix-effects.jsonl');

// Tri budget by platform
const TRI_BUDGETS = {
  roblox: 4000,
  game: 50000,
  stl: Infinity,
};

// Wall thickness minimum (mm)
const MIN_WALL_THICKNESS_MM = 1.5;

// Visual quality thresholds
const VISUAL_PASS_THRESHOLD = 7.0;
const VISUAL_REVISION_THRESHOLD = 5.0;

// ============================================================================
// UTILITIES
// ============================================================================

class Logger {
  log(...args) {
    console.log('[validator]', ...args);
  }

  info(...args) {
    console.log('[validator:info]', ...args);
  }

  warn(...args) {
    console.warn('[validator:warn]', ...args);
  }

  error(...args) {
    console.error('[validator:error]', ...args);
  }

  debug(...args) {
    if (process.env.DEBUG) {
      console.log('[validator:debug]', ...args);
    }
  }
}

const logger = new Logger();

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    conceptId: null,
    allPending: false,
    skipVisual: false,
    autoFix: false,
    dryRun: false,
    port: parseInt(process.env.BLENDER_MCP_PORT || '9876'),
    host: process.env.BLENDER_MCP_HOST || '127.0.0.1',
    shotGates: false,
    strictShotGates: false,
    ciSamples: 1,
    ciAlpha: 0.05,
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--concept-id' && args[i + 1]) {
      opts.conceptId = args[++i];
    } else if (args[i] === '--all-pending') {
      opts.allPending = true;
    } else if (args[i] === '--skip-visual') {
      opts.skipVisual = true;
    } else if (args[i] === '--auto-fix') {
      opts.autoFix = true;
    } else if (args[i] === '--dry-run') {
      opts.dryRun = true;
    } else if (args[i] === '--port') {
      opts.port = parseInt(args[++i]);
    } else if (args[i] === '--host') {
      opts.host = args[++i];
    } else if (args[i] === '--shot-gates') {
      opts.shotGates = true;
    } else if (args[i] === '--strict-shot-gates') {
      opts.strictShotGates = true;
    } else if (args[i] === '--ci-samples' && args[i + 1]) {
      opts.ciSamples = Math.max(1, parseInt(args[++i], 10) || 1);
    } else if (args[i] === '--ci-alpha' && args[i + 1]) {
      opts.ciAlpha = Math.max(0.001, Math.min(0.5, parseFloat(args[++i]) || 0.05));
    }
  }

  if (!opts.conceptId && !opts.allPending) {
    logger.error('Usage: --concept-id ID or --all-pending');
    process.exit(1);
  }

  return opts;
}

function computeCI95(values, alpha = 0.05) {
  if (!values.length) return { low: 0, high: 0, margin: 0, samples: 0, alpha };
  const n = values.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  if (n === 1) return { low: mean, high: mean, margin: 0, samples: 1, alpha };
  const variance = values.reduce((s, x) => s + Math.pow(x - mean, 2), 0) / (n - 1);
  const sd = Math.sqrt(variance);
  const z = 1.96;
  const margin = z * (sd / Math.sqrt(n));
  return {
    low: Number((mean - margin).toFixed(3)),
    high: Number((mean + margin).toFixed(3)),
    margin: Number(margin.toFixed(3)),
    samples: n,
    alpha,
  };
}

function evaluateShotLevelGates(conceptDir, visualAverage, config) {
  const gateCfg = config?.shot_gates || {};
  const required = gateCfg.required_shots || ['hero', 'front', 'side'];
  const minScore = Number(gateCfg.min_per_shot_score ?? 6.5);
  const perShot = {};
  let failed = 0;
  for (const shot of required) {
    const file = path.join(conceptDir, `${shot}.png`);
    const exists = fs.existsSync(file);
    const size = exists ? fs.statSync(file).size : 0;
    const pass = exists && size > 100 * 1024 && visualAverage >= minScore;
    if (!pass) failed += 1;
    perShot[shot] = {
      pass,
      fail_reasons: pass ? [] : [
        !exists ? 'missing_frame' : null,
        exists && size <= 100 * 1024 ? 'small_filesize' : null,
        visualAverage < minScore ? 'low_visual_score' : null,
      ].filter(Boolean),
    };
  }
  const overallPass = failed <= Number(gateCfg.max_failed_shots ?? 0);
  return {
    enabled: true,
    shots_required: required,
    per_shot: perShot,
    overall_pass: overallPass,
    failed_shots: failed,
  };
}

function computeThreeTrackScore(validation, config, confidenceInterval) {
  const weights = config?.weights || { forensic_clarity: 0.4, physical_plausibility: 0.35, cinematic_presentation: 0.25 };
  const checks = validation?.mechanical?.checks || {};
  const totalChecks = Object.keys(checks).length || 1;
  const passedChecks = Object.values(checks).filter((c) => c.passed).length;
  const mechRatio = passedChecks / totalChecks;
  const visual = Number(validation?.visual?.average || 0);
  const shotPass = validation?.scoring?.shot_gates?.overall_pass !== false;

  const forensic = Math.max(0, Math.min(10, visual * 0.7 + (shotPass ? 3 : 0)));
  const physical = Math.max(0, Math.min(10, mechRatio * 10));
  const cinematic = Math.max(0, Math.min(10, visual));

  const weighted10 = (
    forensic * weights.forensic_clarity +
    physical * weights.physical_plausibility +
    cinematic * weights.cinematic_presentation
  );
  return {
    version: config?.version || 'v1-three-track',
    tracks: {
      forensic_clarity: { score: Number(forensic.toFixed(3)), weight: weights.forensic_clarity, components: { visual, shotPass } },
      physical_plausibility: { score: Number(physical.toFixed(3)), weight: weights.physical_plausibility, components: { mechRatio: Number(mechRatio.toFixed(3)) } },
      cinematic_presentation: { score: Number(cinematic.toFixed(3)), weight: weights.cinematic_presentation, components: { visual } },
    },
    weighted_score_10: Number(weighted10.toFixed(3)),
    weighted_score_100: Number((weighted10 * 10).toFixed(1)),
    confidence_interval_95: confidenceInterval,
  };
}

// ============================================================================
// BLENDER MCP CLIENT
// ============================================================================

class BlenderMCPClient {
  constructor(host, port) {
    this.host = host;
    this.port = port;
  }

  async executePython(code) {
    return new Promise((resolve, reject) => {
      const socket = net.createConnection(this.port, this.host);
      let buffer = '';
      let completed = false;

      socket.on('connect', () => {
        const reqId = Date.now();
        socket.write(JSON.stringify({ id: reqId, command: 'execute_python', params: { code } }));
      });

      socket.on('data', (chunk) => {
        buffer += chunk.toString();
        // Use brace-depth parsing (Blender MCP sends raw JSON without newline terminators)
        let depth = 0, inString = false, escaped = false, startIdx = -1, endIdx = -1;
        for (let i = 0; i < buffer.length; i++) {
          const ch = buffer[i];
          if (escaped) { escaped = false; continue; }
          if (ch === '\\' && inString) { escaped = true; continue; }
          if (ch === '"') { inString = !inString; continue; }
          if (inString) continue;
          if (ch === '{') { if (depth === 0) startIdx = i; depth++; }
          if (ch === '}') { depth--; if (depth === 0 && startIdx >= 0) { endIdx = i; break; } }
        }
        if (endIdx >= 0 && startIdx >= 0) {
          try {
            const msg = JSON.parse(buffer.substring(startIdx, endIdx + 1));
            completed = true;
            socket.end();
            if (msg.error) {
              reject(new Error(`Blender error: ${typeof msg.error === 'string' ? msg.error : JSON.stringify(msg.error)}`));
            } else {
              // Unwrap nested result: MCP returns {id, result: {result: {actual_data}}} for execute_python
              const outer = msg.result || msg;
              const inner = outer.result !== undefined ? outer.result : outer;
              resolve(inner);
            }
          } catch (e) {
            // continue buffering
          }
        }
      });

      socket.on('error', (err) => {
        if (!completed) {
          reject(err);
        }
      });

      socket.on('end', () => {
        if (!completed) {
          reject(new Error('Blender MCP connection closed without response'));
        }
      });

      setTimeout(() => {
        if (!completed) {
          socket.end();
          reject(new Error('Blender MCP request timeout'));
        }
      }, 30000);
    });
  }
}

// ============================================================================
// MECHANICAL VALIDATION (Layer 1)
// ============================================================================

class MechanicalValidator {
  constructor(blenderClient) {
    this.blenderClient = blenderClient;
  }

  /**
   * Run mechanical checks - tries trimesh first (fast), falls back to Blender
   */
  async validate(filePath, platform = 'game', autoFix = false, tier = null) {
    const startTime = Date.now();
    const absPath = path.resolve(filePath);
    const conceptDir = path.dirname(absPath);
    
    logger.info(`Running mechanical checks on ${path.basename(filePath)}`);

    try {
      // FIRST: Try trimesh validation (fast path, no Blender needed)
      logger.info('Attempting trimesh validation (PRIMARY backend)...');
      let result = await this.runTrimeshValidation(conceptDir, platform, tier);
      
      if (result) {
        logger.info(`Trimesh validation successful, backend: ${result.backend}`);
        return result;
      }

      // FALLBACK: Use Blender MCP backend if trimesh unavailable or failed
      logger.info('Trimesh unavailable/failed, falling back to Blender MCP backend...');
      
      // CRITICAL: Open the .blend file in Blender before measuring.
      // Without this, the validator measures whatever scene is currently
      // loaded in Blender (which may be a completely different project).
      logger.info(`Opening ${absPath} in Blender for validation...`);
      await this.blenderClient.executePython(
        `import bpy\\nbpy.ops.wm.open_mainfile(filepath='${absPath.replace(/'/g, "\\'")}')\n__result__ = {'opened': '${path.basename(filePath)}', 'objects': len(bpy.data.objects)}`
      );

      // First, get the mesh data
      const meshData = await this.getMeshData();

      // Build checks
      const checks = this.buildChecks(meshData, platform);

      // Determine if all passed
      let allPassed = Object.values(checks).every((c) => c.passed);

      // Apply auto-fixes if needed
      let autoFixesApplied = [];
      if (!allPassed && autoFix) {
        autoFixesApplied = await this.applyAutoFixes(checks, meshData);
        // Re-validate after fixes
        const newMeshData = await this.getMeshData();
        const newChecks = this.buildChecks(newMeshData, platform);
        allPassed = Object.values(newChecks).every((c) => c.passed);
        return {
          passed: allPassed,
          checks: newChecks,
          autoFixesApplied,
          duration: Date.now() - startTime,
          backend: 'blender',
        };
      }

      return {
        passed: allPassed,
        checks,
        autoFixesApplied,
        duration: Date.now() - startTime,
        backend: 'blender',
      };
    } catch (err) {
      logger.error(`Mechanical validation failed: ${err.message}`);
      throw err;
    }
  }

  async getMeshData() {
    // CRITICAL: Python code must use single quotes only — double quotes inside
    // a JS template literal get escaped to \" by JSON.stringify, which crashes
    // the Blender addon's exec() or its JSON parser (ECONNRESET).
    const pythonCode = `
import bpy
import bmesh
import math

meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('_ground_plane')]
if not meshes:
    __result__ = {'error': 'No mesh objects in scene'}
else:
    tv = 0
    te = 0
    tf = 0
    tt = 0
    tnm = 0
    tl = 0
    td = 0
    ta = 0.0
    tvol = 0.0
    for obj in meshes:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        tv += len(bm.verts)
        te += len(bm.edges)
        tf += len(bm.faces)
        tt += sum(len(f.verts) - 2 for f in bm.faces)
        tnm += sum(1 for e in bm.edges if not e.is_manifold)
        tl += sum(1 for v in bm.verts if not v.link_edges)
        td += sum(1 for f in bm.faces if f.calc_area() < 1e-8)
        ta += sum(f.calc_area() for f in bm.faces)
        try:
            tvol += bm.calc_volume()
        except:
            pass
        bm.free()
    ac = []
    for obj in meshes:
        for v in obj.data.vertices:
            ac.append(obj.matrix_world @ v.co)
    if ac:
        xs = [c.x for c in ac]
        ys = [c.y for c in ac]
        zs = [c.z for c in ac]
        dims = [max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs)]
    else:
        dims = [0, 0, 0]
    dmm = [round(d * 1000, 1) for d in dims]
    __result__ = {
        'vertex_count': tv,
        'edge_count': te,
        'face_count': tf,
        'tri_count': tt,
        'non_manifold_edges': tnm,
        'loose_vertices': tl,
        'degenerate_faces': td,
        'surface_area_sq_mm': round(ta * 1e6, 2),
        'volume_cu_mm': round(tvol * 1e9, 2),
        'dimensions_mm': dmm,
        'is_manifold': tnm == 0,
        'mesh_count': len(meshes),
        'mesh_names': [o.name for o in meshes[:20]]
    }
`;

    try {
      const result = await this.blenderClient.executePython(pythonCode);
      if (result.error) {
        throw new Error(result.error);
      }
      return result;
    } catch (err) {
      logger.error(`Failed to get mesh data: ${err.message}`);
      throw err;
    }
  }

  /**
   * Run mechanical checks via trimesh (Python library) - PRIMARY backend
   * Faster and doesn't require Blender to be open
   */
  async runTrimeshValidation(conceptDir, platform, tier) {
    const startTime = Date.now();
    const stlPath = path.join(conceptDir, 'model.stl');
    
    // Check if STL exists
    if (!fs.existsSync(stlPath)) {
      logger.info(`No STL file at ${stlPath}, will use Blender backend`);
      return null;
    }

    logger.info(`Running trimesh validation on ${stlPath}`);
    
    // Determine triangle budget
    const triBudget = TRI_BUDGETS[platform] || TRI_BUDGETS.game;
    
    // Determine tier for trimesh validator
    let tierArg = tier || 'standard';
    if (!tierArg || tierArg === 'unknown') {
      try {
        const scoringConfig = loadJson(SCORING_CONFIG_PATH);
        tierArg = scoringConfig.default_tier || 'standard';
      } catch (e) {
        tierArg = 'standard';
      }
    }

    return new Promise((resolve, reject) => {
      try {
        const trimeshScriptPath = path.join(REPO_ROOT, 'scripts', '3d-forge', 'trimesh-validator.py');
        const args = [trimeshScriptPath, stlPath, '--tier', tierArg, '--max-tris', String(triBudget)];
        
        logger.debug(`Spawning: python3 ${args.join(' ')}`);
        const proc = spawn('python3', args, {
          cwd: conceptDir,
          timeout: 30000, // 30 sec timeout
        });

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
          stdout += data.toString();
        });

        proc.stderr.on('data', (data) => {
          stderr += data.toString();
          logger.debug(`trimesh stderr: ${data.toString()}`);
        });

        proc.on('close', (code) => {
          if (code !== 0) {
            logger.warn(`trimesh-validator.py exited with code ${code}: ${stderr}`);
            resolve(null); // Fall back to Blender
            return;
          }

          try {
            const trimeshOutput = JSON.parse(stdout);
            logger.debug(`trimesh output: ${JSON.stringify(trimeshOutput)}`);

            // FIX-v25: Convert trimesh output format to buildChecks() format
            // Trimesh output nests everything under .checks.{check_name}
            const tc = trimeshOutput.checks || {};
            const geom = tc.geometry || {};
            const wt = tc.watertight || {};
            const vol = tc.volume || {};
            const wallT = tc.wall_thickness || {};
            const loose = tc.loose_vertices || {};
            const degen = tc.degenerate_faces || {};
            // Trimesh dimensions are in Blender units (meters) — convert to mm
            const rawDims = geom.bounding_box?.dimensions || [0, 0, 0];
            const dimsMm = rawDims.map(d => Math.round(d * 1000 * 10) / 10);
            // Volume: trimesh returns cubic meters, convert to cubic mm (×1e9)
            const volCuMm = (vol.volume || 0) * 1e9;
            // Surface area: compute from trimesh volume/bounds (approximate)
            // Use bounding box surface area as proxy if not available
            const [dx, dy, dz] = dimsMm;
            const approxSurfArea = 2 * (dx*dy + dy*dz + dx*dz);
            const meshData = {
              is_manifold: wt.is_watertight || false,
              non_manifold_edges: wt.is_watertight ? 0 : 1,
              tri_count: geom.triangle_count || 0,
              loose_vertices: loose.loose_count || 0,
              degenerate_faces: degen.degenerate_count || 0,
              surface_area_sq_mm: approxSurfArea,
              volume_cu_mm: volCuMm,
              dimensions_mm: dimsMm,
              vertex_count: geom.vertex_count || 0,
              face_count: geom.triangle_count || 0,
              edge_count: 0,
              wall_thickness: wallT.min_thickness || null,
            };

            // Build checks using the same logic as buildChecks()
            const checks = this.buildChecks(meshData, platform);

            resolve({
              passed: Object.values(checks).every((c) => c.passed),
              checks,
              autoFixesApplied: [],
              duration: Date.now() - startTime,
              backend: 'trimesh',
            });
          } catch (parseErr) {
            logger.warn(`Failed to parse trimesh output: ${parseErr.message}`);
            resolve(null); // Fall back to Blender
          }
        });

        proc.on('error', (err) => {
          logger.warn(`Failed to spawn trimesh-validator: ${err.message}`);
          resolve(null); // Fall back to Blender
        });
      } catch (err) {
        logger.warn(`trimesh validation error: ${err.message}`);
        resolve(null); // Fall back to Blender
      }
    });
  }

  buildChecks(meshData, platform) {
    const checks = {};
    const triBudget = TRI_BUDGETS[platform] || TRI_BUDGETS.game;

    // Manifold check - verify mesh is closed/watertight
    checks.manifold = {
      passed: meshData.non_manifold_edges === 0,
      value: meshData.non_manifold_edges,
      description: 'No non-manifold edges (mesh is watertight)',
    };

    // Tri count check
    checks.tri_count = {
      passed: meshData.tri_count <= triBudget,
      value: meshData.tri_count,
      description: `Triangle count ≤ ${triBudget}`,
    };

    // Loose vertices check
    checks.loose_verts = {
      passed: meshData.loose_vertices === 0,
      value: meshData.loose_vertices,
      description: 'No loose/unconnected vertices',
    };

    // Degenerate faces check
    checks.degenerate_faces = {
      passed: meshData.degenerate_faces === 0,
      value: meshData.degenerate_faces,
      description: 'No degenerate (zero-area) faces',
    };

    // FIX-BUG2: wall_thickness check - use formula-based check instead of proportion check
    // For game assets: wall_thickness > 0.1mm passes
    // For STL/print: wall_thickness >= 1.5mm passes
    // Calculate wall thickness as (2 * volume) / surface_area
    const vol = meshData.volume_cu_mm || 0;
    const area = meshData.surface_area_sq_mm || 1;
    let wallThicknessValue = 0;
    let wallThicknessPassed = false;
    
    if (vol > 0 && area > 0) {
      wallThicknessValue = (2 * vol) / area; // approximate wall thickness in mm
      const minThreshold = platform === 'stl' ? MIN_WALL_THICKNESS_MM : 0.1;
      wallThicknessPassed = wallThicknessValue >= minThreshold;
    } else {
      // Fallback: check if dimensions are reasonable
      const [x, y, z] = meshData.dimensions_mm;
      const minDim = Math.min(x, y, z);
      const minThreshold = platform === 'stl' ? MIN_WALL_THICKNESS_MM : 0.1;
      wallThicknessValue = minDim;
      wallThicknessPassed = minDim >= minThreshold;
    }

    checks.wall_thickness = {
      passed: wallThicknessPassed,
      value: `min=${wallThicknessValue.toFixed(1)}mm, avg=${((2 * vol) / area).toFixed(1)}mm`,
      description: platform === 'stl' ? `Wall thickness ≥ ${MIN_WALL_THICKNESS_MM}mm` : 'Wall thickness > 0.1mm',
    };

    // Bounding box checks - platform-dependent
    // Blender uses meters: size=1.0 = 1000mm. Most 3D print beds max ~300mm.
    // Game/Roblox assets don't have physical size limits but should be non-zero.
    const [x, y, z] = meshData.dimensions_mm;
    const maxDim = platform === 'stl' ? 300 : 5000; // STL = 3D print bed, game = virtual
    checks.bounding_box = {
      passed: x > 0 && y > 0 && z > 0 && x <= maxDim && y <= maxDim && z <= maxDim,
      value: `${x}×${y}×${z}mm`,
      description: `Within bounds (≤${maxDim}×${maxDim}×${maxDim}mm)`,
    };

    return checks;
  }

  async applyAutoFixes(checks, meshData) {
    const fixes = [];

    // Fix non-manifold edges
    if (!checks.manifold.passed) {
      logger.info('Auto-fixing: filling holes...');
      const fillCode = `
import bpy
import bmesh
obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=0.0001)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if not e.is_manifold])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
`;
      await this.blenderClient.executePython(fillCode);
      fixes.push('fill_holes');
    }

    // Fix loose vertices
    if (!checks.loose_verts.passed) {
      logger.info('Auto-fixing: deleting loose vertices...');
      const delCode = `
import bpy
import bmesh
obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    isolated = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=isolated, context='VERTS')
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
`;
      await this.blenderClient.executePython(delCode);
      fixes.push('delete_loose_verts');
    }

    // Recalculate normals using bmesh (more reliable than shade_smooth operator)
    logger.info('Auto-fixing: recalculating normals via bmesh...');
    const normCode = `
import bpy
import bmesh
obj = bpy.context.active_object
if obj and obj.type == 'MESH':
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
`;
    await this.blenderClient.executePython(normCode);
    fixes.push('recalc_normals');

    // Decimate if tri count is too high (Roblox platform)
    if (!checks.tri_count.passed && checks.tri_count.value > 4000) {
      const targetRatio = 4000 / checks.tri_count.value;
      logger.info(`Auto-fixing: decimating to ${(targetRatio * 100).toFixed(1)}%...`);
      const decimateCode = `
import bpy
obj = bpy.context.active_object
if obj:
    dec = obj.modifiers.new('Decimate', 'DECIMATE')
    dec.ratio = ${targetRatio.toFixed(3)}
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=dec.name)
`;
      await this.blenderClient.executePython(decimateCode);
      fixes.push(`decimate_${(targetRatio * 100).toFixed(0)}pct`);
    }

    return fixes;
  }
}

// ============================================================================
// VISUAL VALIDATION (Layer 2)
// ============================================================================

class VisualValidator {
  constructor(apiKey) {
    this.apiKey = apiKey;
    this.geminiKey = process.env.GEMINI_API_KEY;
    this.anthropicKey = process.env.ANTHROPIC_API_KEY;
  }

  async validate(conceptDir, trendId) {
    if (!this.apiKey && !this.geminiKey && !this.anthropicKey) {
      logger.warn('No vision API keys set, skipping visual validation');
      return null;
    }

    const startTime = Date.now();
    logger.info(`Running visual checks for concept`);

    try {
      // Pre-check: Run pixel-metrics analysis to auto-reject washed-out renders
      const pixelMetricsModule = path.join(path.dirname(__dirname), 'scripts', '3d-forge', 'pixel-metrics.js');
      if (fs.existsSync(pixelMetricsModule)) {
        try {
          const pixelMetrics = require(pixelMetricsModule);
          // Analyze hero.png first as a quick gating mechanism
          const heroPath = path.join(conceptDir, 'hero.png');
          if (fs.existsSync(heroPath)) {
            logger.info('Running pixel-metrics pre-check on hero.png...');
            const metricsResult = await new Promise((resolve, reject) => {
              try {
                const { analyzeImage } = require(pixelMetricsModule);
                resolve(analyzeImage(heroPath));
              } catch (e) {
                // If pixel-metrics fails, continue with LLM validation
                logger.warn(`Pixel-metrics pre-check failed: ${e.message}`);
                resolve(null);
              }
            });
            
            if (metricsResult && metricsResult.auto_reject) {
              logger.warn(`Auto-rejected render (pixel-metrics): ${metricsResult.rejection_reasons.join('; ')}`);
              return {
                average: 2,
                verdict: 'REJECT',
                issues: metricsResult.rejection_reasons,
                suggested_fixes: ['Re-render with corrected lighting (check render fixes)', 'Verify material colors are in 0.03-0.35 range'],
                auto_rejected_by_metrics: true,
                composite_score: metricsResult.composite_score || 0,
              };
            }
          }
        } catch (err) {
          logger.warn(`Could not load pixel-metrics module: ${err.message}`);
        }
      }

      // Load renders
      const heroPath = path.join(conceptDir, 'hero.png');
      const frontPath = path.join(conceptDir, 'front.png');
      const sidePath = path.join(conceptDir, 'side.png');

      const renders = [];
      for (const p of [heroPath, frontPath, sidePath]) {
        if (fs.existsSync(p)) {
          const b64 = fs.readFileSync(p, 'base64');
          renders.push({
            type: 'image_url',
            image_url: {
              url: `data:image/png;base64,${b64}`,
            },
          });
        }
      }

      if (renders.length === 0) {
        logger.warn('No render images found');
        return null;
      }

      // FIX-BUG3: Load reference images from data/3d-forge/refs/{trend_id}/images/
      // Reference images are critical for vision API to compare against
      // The harvester saves images in an 'images/' subdirectory, with a manifest.json at root
      const references = [];
      if (trendId) {
        const refDir = path.join(REFS_DIR, trendId);
        const refImagesDir = path.join(refDir, 'images');
        // Look in images/ subdirectory first (where harvester puts them), fall back to root
        const searchDir = fs.existsSync(refImagesDir) ? refImagesDir : refDir;
        if (fs.existsSync(searchDir)) {
          try {
            // Use manifest.json to pick best images if available
            const manifestPath = path.join(refDir, 'manifest.json');
            let sortedFiles = [];
            if (fs.existsSync(manifestPath)) {
              try {
                const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
                // Sort by quality_score descending, only use downloaded images
                sortedFiles = (manifest.images || [])
                  .filter((img) => img.downloaded)
                  .sort((a, b) => (b.quality_score || 0) - (a.quality_score || 0))
                  .map((img) => img.filename);
                logger.info(`Loaded manifest with ${sortedFiles.length} downloaded images (sorted by quality)`);
              } catch (mErr) {
                logger.warn(`Failed to parse manifest: ${mErr.message}, falling back to directory scan`);
              }
            }
            // Fall back to directory scan if manifest didn't yield results
            if (sortedFiles.length === 0) {
              sortedFiles = fs.readdirSync(searchDir).filter((f) => /\.(png|jpg|jpeg)$/i.test(f));
            }
            const refFiles = sortedFiles;
            logger.info(`Found ${refFiles.length} reference images in ${searchDir}`);
            for (const rf of refFiles.slice(0, 5)) {
              const refPath = path.join(searchDir, rf);
              const b64 = fs.readFileSync(refPath, 'base64');
              const ext = path.extname(rf).toLowerCase();
              const mime = ext === '.png' ? 'image/png' : 'image/jpeg';
              references.push({
                type: 'image_url',
                image_url: {
                  url: `data:${mime};base64,${b64}`,
                },
              });
            }
          } catch (err) {
            logger.warn(`Failed to load reference images from ${refDir}: ${err.message}`);
          }
        } else {
          logger.warn(`No reference directory found at ${refDir} for trend ${trendId}`);
        }
      } else {
        logger.warn('No trend_id provided, cannot load reference images');
      }

      if (references.length === 0) {
        logger.warn('No reference product photos provided for comparison');
      }

      const allImages = [...renders, ...references];

      // Build prompt — local models (llava) score unfairly low if we ask for "match references" when refs=0
      const prompt =
        references.length === 0
          ? `You are grading ${renders.length} product render image(s) for a 3D-print / game-asset listing. There are NO reference photos — judge the renders on their own merits.

Score 1-10 on each dimension (use the full range; 6+ means "acceptable for a first-pass marketplace shot"):
- shape_accuracy: Is the object silhouette clear, intentional, and readable (not broken/empty)?
- proportion_accuracy: Do parts look proportionate and believable for this type of product?
- detail_level: Is there enough geometric and surface detail for the category (not a flat placeholder)?
- material_quality: Do materials/lighting read as intentional (not flat grey mush or blown highlights)?
- marketplace_readiness: Would this pass as a draft hero shot on Etsy/Cults3D/Sketchfab (composition, contrast)?

Also provide:
- issues: list of specific problems (array of strings)
- suggested_fixes: list of actionable improvements for regeneration (array of strings)

Output ONLY valid JSON (no markdown, no extra text) with these exact keys:
{
  "shape_accuracy": number,
  "proportion_accuracy": number,
  "detail_level": number,
  "material_quality": number,
  "marketplace_readiness": number,
  "issues": [],
  "suggested_fixes": []
}`
          : `Compare these 3D renders (first ${renders.length} images) to the reference product photos (remaining ${references.length} images).

Score 1-10 on each dimension:
- shape_accuracy: Does the 3D model silhouette match the references?
- proportion_accuracy: Are the dimensional ratios correct?
- detail_level: Are key distinguishing features present?
- material_quality: Do surfaces look convincing?
- marketplace_readiness: Would a buyer purchase this on Etsy/Cults3D?

Also provide:
- issues: list of specific problems (array of strings)
- suggested_fixes: list of actionable improvements for regeneration (array of strings)

Output ONLY valid JSON (no markdown, no extra text) with these exact keys:
{
  "shape_accuracy": number,
  "proportion_accuracy": number,
  "detail_level": number,
  "material_quality": number,
  "marketplace_readiness": number,
  "issues": [],
  "suggested_fixes": []
}`;

      const response = await this.callVisionAPI(allImages, prompt, conceptDir);
      const lmCost = this.estimateLLMCost(allImages.length);

      const scores = this.extractJSON(response);
      const average = (
        (scores.shape_accuracy +
          scores.proportion_accuracy +
          scores.detail_level +
          scores.material_quality +
          scores.marketplace_readiness) /
        5
      ).toFixed(2);

      let verdict = 'PASS';
      if (average < VISUAL_REVISION_THRESHOLD) {
        verdict = 'REJECT';
      } else if (average < VISUAL_PASS_THRESHOLD) {
        verdict = 'NEEDS_REVISION';
      }

      return {
        ...scores,
        average: parseFloat(average),
        verdict,
        duration: Date.now() - startTime,
        lmCost,
        references_provided: references.length,
      };
    } catch (err) {
      logger.error(`Visual validation failed: ${err.message}`);
      throw err;
    }
  }

  extractJSON(text) {
    let jsonStr = text;
    const jsonMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
    if (jsonMatch) jsonStr = jsonMatch[1];
    jsonStr = jsonStr.trim();
    try { return JSON.parse(jsonStr); } catch (e) { /* try repair */ }
    // Repair truncated JSON
    let open = 0;
    for (const ch of jsonStr) {
      if (ch === '{' || ch === '[') open++;
      if (ch === '}' || ch === ']') open--;
    }
    let repaired = jsonStr;
    while (open > 0) {
      repaired += repaired.includes('[') && !repaired.endsWith(']') ? ']' : '}';
      open--;
    }
    return JSON.parse(repaired);
  }

  async callVisionAPI(imageData, prompt, conceptDir) {
    const errors = [];

    // 1. Try Gemini (cheapest)
    if (this.geminiKey) {
      try {
        logger.info('Trying Gemini vision for validation...');
        return await this.callGeminiVision(imageData, prompt, conceptDir);
      } catch (err) {
        logger.warn(`Gemini failed: ${err.message}`);
        errors.push(`Gemini: ${err.message}`);
      }
    }

    // 2. Try Anthropic
    if (this.anthropicKey) {
      try {
        logger.info('Trying Anthropic vision for validation...');
        return await this.callAnthropicVision(imageData, prompt, conceptDir);
      } catch (err) {
        logger.warn(`Anthropic failed: ${err.message}`);
        errors.push(`Anthropic: ${err.message}`);
      }
    }

    // 3. Try OpenAI
    if (this.apiKey) {
      try {
        logger.info('Trying OpenAI vision for validation...');
        return await this.callOpenAIVision(imageData, prompt);
      } catch (err) {
        logger.warn(`OpenAI failed: ${err.message}`);
        errors.push(`OpenAI: ${err.message}`);
      }
    }

    // 4. Try Ollama llava:7b local fallback
    try {
      logger.info('Trying Ollama llava:7b local vision fallback...');
      return await this.callOllamaVision(imageData, prompt);
    } catch (err) {
      logger.warn(`Ollama fallback failed: ${err.message}`);
      errors.push(`Ollama: ${err.message}`);
    }

    throw new Error(`All vision providers failed: ${errors.join('; ')}`);
  }

  async callGeminiVision(imageData, prompt, conceptDir) {
    // Prepare image parts for Gemini inline_data format
    const parts = [{ text: prompt }];
    for (const img of imageData) {
      // imageData items are in OpenAI format: { type: 'image_url', image_url: { url: 'data:mime;base64,...' } }
      const dataUri = img.image_url.url;
      const match = dataUri.match(/^data:(image\/(\w+));base64,(.+)$/);
      if (match) {
        parts.push({ inline_data: { mime_type: match[1], data: match[3] } });
      }
    }

    const requestBody = JSON.stringify({
      contents: [{ parts }],
      generationConfig: {
        responseMimeType: 'application/json',
        temperature: 0.3,
        maxOutputTokens: 2048,
      },
    });

    return new Promise((resolve, reject) => {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${this.geminiKey}`;
      const parsed = new URL(url);

      const req = https.request(
        {
          hostname: parsed.hostname,
          path: parsed.pathname + parsed.search,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(requestBody),
          },
        },
        (res) => {
          let data = '';
          res.on('data', (chunk) => (data += chunk));
          res.on('end', () => {
            try {
              if (res.statusCode !== 200) {
                reject(new Error(`Gemini ${res.statusCode}: ${data.slice(0, 300)}`));
                return;
              }
              const parsed = JSON.parse(data);
              const text = parsed.candidates?.[0]?.content?.parts?.[0]?.text || '';
              resolve(text);
            } catch (e) {
              reject(e);
            }
          });
        }
      );
      req.on('error', reject);
      req.write(requestBody);
      req.end();
    });
  }

  async callAnthropicVision(imageData, prompt, conceptDir) {
    // FIX-BUG1: Convert OpenAI image format to Anthropic format with proper base64 handling
    // Strip data URI prefix, remove whitespace, and use raw base64
    const content = [{ type: 'text', text: prompt }];
    for (const img of imageData) {
      const dataUri = img.image_url.url;
      const match = dataUri.match(/^data:(image\/(\w+));base64,(.+)$/);
      if (match) {
        // Extract the base64 data and strip any whitespace/newlines
        const base64Data = match[3].replace(/\s/g, '');
        const mediaType = match[1];
        content.push({
          type: 'image',
          source: {
            type: 'base64',
            media_type: mediaType,
            data: base64Data,
          },
        });
      }
    }

    const requestBody = JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 4096,
      system: 'You are a 3D asset quality inspector. Output ONLY raw JSON. Do NOT wrap in markdown code blocks.',
      messages: [{ role: 'user', content }],
    });

    return new Promise((resolve, reject) => {
      const req = https.request(
        {
          hostname: 'api.anthropic.com',
          path: '/v1/messages',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(requestBody),
            'x-api-key': this.anthropicKey,
            'anthropic-version': '2023-06-01',
          },
        },
        (res) => {
          let data = '';
          res.on('data', (chunk) => (data += chunk));
          res.on('end', () => {
            try {
              if (res.statusCode !== 200) {
                reject(new Error(`Anthropic ${res.statusCode}: ${data.slice(0, 300)}`));
                return;
              }
              const parsed = JSON.parse(data);
              const text = parsed.content?.[0]?.text || '';
              resolve(text);
            } catch (e) {
              reject(e);
            }
          });
        }
      );
      req.on('error', reject);
      req.write(requestBody);
      req.end();
    });
  }

  async callOpenAIVision(imageData, prompt) {
    return new Promise((resolve, reject) => {
      const requestBody = JSON.stringify({
        model: 'gpt-4o',
        messages: [
          {
            role: 'system',
            content: 'You are a 3D asset quality inspector. Output ONLY raw JSON.',
          },
          {
            role: 'user',
            content: [{ type: 'text', text: prompt }, ...imageData],
          },
        ],
        max_tokens: 1024,
        temperature: 0.7,
      });

      const req = https.request(
        {
          hostname: 'api.openai.com',
          path: '/v1/chat/completions',
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(requestBody),
            Authorization: `Bearer ${this.apiKey}`,
          },
        },
        (res) => {
          let data = '';
          res.on('data', (chunk) => (data += chunk));
          res.on('end', () => {
            try {
              if (res.statusCode !== 200) {
                reject(new Error(`OpenAI ${res.statusCode}: ${data.slice(0, 300)}`));
                return;
              }
              const parsed = JSON.parse(data);
              resolve(parsed.choices[0]?.message?.content || '');
            } catch (e) {
              reject(e);
            }
          });
        }
      );
      req.on('error', reject);
      req.write(requestBody);
      req.end();
    });
  }

  async callOllamaVision(imageData, prompt) {
    return new Promise((resolve, reject) => {
      try {
        // Extract base64 data from image_url format
        const base64Images = [];
        for (const img of imageData) {
          const dataUri = img.image_url?.url || '';
          // FIX-v26: was \\w+ (literal backslash+w) — must be \w+ (word char class)
          const match = dataUri.match(/^data:image\/(\w+);base64,(.+)$/);
          if (match) {
            base64Images.push(match[2]);
          }
        }

        if (base64Images.length === 0) {
          throw new Error('No valid base64 images found for Ollama');
        }

        // Build Ollama API request
        const requestBody = JSON.stringify({
          model: 'llava:7b',
          prompt,
          images: base64Images,
          stream: false,
        });

        // FIX-v26: Ollama serves HTTP on localhost, not HTTPS
        const req = http.request(
          {
            hostname: 'localhost',
            port: 11434,
            path: '/api/generate',
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Content-Length': Buffer.byteLength(requestBody),
            },
          },
          (res) => {
            let data = '';
            res.on('data', (chunk) => (data += chunk));
            res.on('end', () => {
              try {
                if (res.statusCode !== 200) {
                  reject(new Error(`Ollama ${res.statusCode}: ${data.slice(0, 300)}`));
                  return;
                }
                const parsed = JSON.parse(data);
                const response = parsed.response || '';
                resolve(response);
              } catch (e) {
                reject(e);
              }
            });
          }
        );

        req.on('error', reject);
        req.setTimeout(300000);
        req.write(requestBody);
        req.end();
      } catch (err) {
        reject(err);
      }
    });
  }

  estimateLLMCost(imageCount) {
    // Approximate cost across providers
    const estimatedInputTokens = 200 + imageCount * 500;
    const estimatedOutputTokens = 400;
    const costCents = (estimatedInputTokens * 0.003 + estimatedOutputTokens * 0.006) / 10;
    return parseFloat(costCents.toFixed(4));
  }
}

// ============================================================================
// ORCHESTRATOR
// ============================================================================

class AssetValidator {
  constructor(opts) {
    this.opts = opts;
    const host = opts.host || BLENDER_MCP_HOST;
    const port = opts.port || BLENDER_MCP_PORT;
    this.blenderClient = new BlenderMCPClient(host, port);
    this.mechanicalValidator = new MechanicalValidator(this.blenderClient);
    this.visualValidator = !opts.skipVisual ? new VisualValidator(OPENAI_API_KEY) : null;
    this.scoringConfig = loadJson(SCORING_CONFIG_PATH, {});
    this.failureTaxonomy = loadJson(FAILURE_TAXONOMY_PATH, { classes: [] });
    this.fixMapping = loadJson(FIX_MAPPING_PATH, { mappings: [] });
  }

  async validateConcept(conceptId) {
    const startTime = Date.now();
    logger.info(`===== Validating concept: ${conceptId} =====`);

    const conceptDir = path.join(EXPORTS_DIR, conceptId);
    const metadataPath = path.join(conceptDir, 'metadata.json');
    const validationPath = path.join(conceptDir, 'validation.json');

    // Load metadata
    if (!fs.existsSync(metadataPath)) {
      logger.error(`No metadata found at ${metadataPath}`);
      return null;
    }

    const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf-8'));
    const platform = metadata.platform || 'game';
    const trendId = metadata.trend_id;

    logger.info(`Platform: ${platform}, Trend: ${trendId}`);

    // Prepare validation result
    const validation = {
      concept_id: conceptId,
      validated_at: new Date().toISOString(),
      metadata: {
        platform,
        trend_id: trendId,
      },
    };

    // Layer 1: Mechanical validation
    try {
      // Extract tier from metadata or scoring config
      const tier = metadata.tier || this.scoringConfig.default_tier || 'standard';
      
      const mechanicalResult = await this.mechanicalValidator.validate(
        path.join(conceptDir, 'model.blend'),
        platform,
        this.opts.autoFix,
        tier
      );

      validation.mechanical = {
        passed: mechanicalResult.passed,
        checks: mechanicalResult.checks,
        auto_fixes_applied: mechanicalResult.autoFixesApplied,
        duration_ms: mechanicalResult.duration,
        backend: mechanicalResult.backend || 'unknown',
      };

      logger.info(`Mechanical checks: ${mechanicalResult.passed ? 'PASS' : 'FAIL'} (backend: ${mechanicalResult.backend || 'unknown'})`);
    } catch (err) {
      logger.error(`Mechanical validation error: ${err.message}`);
      validation.mechanical = { passed: false, error: err.message };
    }

    // Layer 2: Visual validation
    let visualSamples = [];
    if (!this.opts.skipVisual && this.visualValidator) {
      try {
        const sampleCount = Math.max(1, this.opts.ciSamples || 1);
        for (let i = 0; i < sampleCount; i++) {
          const visualResult = await this.visualValidator.validate(conceptDir, trendId);
          if (visualResult) visualSamples.push(visualResult);
        }
        const visualResult = visualSamples.length
          ? {
              ...visualSamples[visualSamples.length - 1],
              average: Number((visualSamples.reduce((s, r) => s + r.average, 0) / visualSamples.length).toFixed(3)),
            }
          : null;

        if (visualResult) {
          validation.visual = {
            shape_accuracy: visualResult.shape_accuracy,
            proportion_accuracy: visualResult.proportion_accuracy,
            detail_level: visualResult.detail_level,
            material_quality: visualResult.material_quality,
            marketplace_readiness: visualResult.marketplace_readiness,
            average: visualResult.average,
            verdict: visualResult.verdict,
            issues: visualResult.issues,
            suggested_fixes: visualResult.suggested_fixes,
            duration_ms: visualResult.duration,
            lm_cost_cents: visualResult.lmCost,
            references_provided: visualResult.references_provided,
          };

          logger.info(`Visual checks: ${visualResult.verdict} (${visualResult.average}/10)`);
        } else {
          logger.warn('Visual validation skipped (no images or API key)');
        }
      } catch (err) {
        logger.error(`Visual validation error: ${err.message}`);
        validation.visual = { error: err.message };
      }
    }

    // Shot-level acceptance gates + confidence interval + three-track scoring
    const sampleAverages = visualSamples.map((s) => Number(s.average)).filter((n) => Number.isFinite(n));
    const ci95 = computeCI95(sampleAverages, this.opts.ciAlpha || 0.05);
    const shotGates = this.opts.shotGates
      ? evaluateShotLevelGates(conceptDir, Number(validation?.visual?.average || 0), this.scoringConfig)
      : null;
    validation.scoring = validation.scoring || {};
    if (shotGates) validation.scoring.shot_gates = shotGates;
    const tracks = computeThreeTrackScore(validation, this.scoringConfig, ci95);
    validation.scoring = { ...validation.scoring, ...tracks };

    // Overall verdict — based on individual check weights
    const mechanicalPass = validation.mechanical?.passed ?? false;
    const checks = validation.mechanical?.checks || {};
    const totalChecks = Object.keys(checks).length;
    const passedChecks = Object.values(checks).filter(c => c.passed).length;
    const checkPassRate = totalChecks > 0 ? passedChecks / totalChecks : 0;

    const visualPass = validation.visual?.verdict === 'PASS' ?? true;
    const visualRevision = validation.visual?.verdict === 'NEEDS_REVISION' ?? false;

    // Critical checks that must pass for PASS verdict
    const criticalFails = ['manifold', 'degenerate_faces'].filter(
      k => checks[k] && !checks[k].passed
    );

    if (criticalFails.length > 0) {
      validation.overall_verdict = 'REJECT';
    } else if (this.opts.strictShotGates && validation.scoring.shot_gates && !validation.scoring.shot_gates.overall_pass) {
      validation.overall_verdict = 'REJECT';
    } else if (!mechanicalPass && checkPassRate < 0.7) {
      validation.overall_verdict = 'REJECT';
    } else if (!mechanicalPass || visualRevision) {
      validation.overall_verdict = 'NEEDS_REVISION';
    } else if (!visualPass && validation.visual) {
      validation.overall_verdict = 'NEEDS_REVISION';
    } else {
      validation.overall_verdict = 'PASS';
    }

    // Production quality score (0-100) — granular per check
    let score = 0;
    // Mechanical: 50 points total, weighted per check
    const checkWeight = totalChecks > 0 ? 50 / totalChecks : 0;
    score += passedChecks * checkWeight;
    // Visual: 50 points (or add 25 bonus if visual is skipped and mechanical is good)
    if (validation.visual && validation.visual.average) {
      score += (validation.visual.average / 10) * 50;
    } else if (mechanicalPass) {
      score += 25; // bonus for clean mechanical when visual is skipped
    }
    const trackScore = Number(validation?.scoring?.weighted_score_100 || 0);
    validation.production_quality_score = Math.round(trackScore > 0 ? trackScore : score);

    // Failure taxonomy + fix-effectiveness logging (append-only)
    const classifiedFailures = classifyFailures(validation, this.failureTaxonomy);
    validation.failure_taxonomy = classifiedFailures;
    const beforeScore = metadata?.previous_validation_score || null;
    const afterScore = validation.production_quality_score;
    for (const f of classifiedFailures) {
      const map = (this.fixMapping.mappings || []).find((m) => m.failure_code === f.failure_code);
      appendFixEffect(FIX_EFFECTS_LOG_PATH, {
        timestamp: new Date().toISOString(),
        concept_id: conceptId,
        failure_code: f.failure_code,
        fix_id: map?.fix_id || 'UNMAPPED_FIX',
        phase: f.phase,
        before: { production_quality_score: beforeScore },
        after: { production_quality_score: afterScore, overall_verdict: validation.overall_verdict },
        success: validation.overall_verdict !== 'REJECT',
        delta_score: Number.isFinite(beforeScore) ? afterScore - beforeScore : 0,
        duration_ms: validation.total_duration_ms || 0,
      });
    }

    validation.total_duration_ms = Date.now() - startTime;

    // Write result
    if (!this.opts.dryRun) {
      fs.writeFileSync(validationPath, JSON.stringify(validation, null, 2));
      logger.info(`Validation saved to ${validationPath}`);
    } else {
      logger.info('[DRY-RUN] Would save to ' + validationPath);
    }

    logger.info(
      `Overall verdict: ${validation.overall_verdict} (score: ${validation.production_quality_score}/100)`
    );

    return validation;
  }

  async findPendingConcepts() {
    if (!fs.existsSync(EXPORTS_DIR)) {
      logger.warn(`No exports directory found at ${EXPORTS_DIR}`);
      return [];
    }

    const concepts = [];
    const folders = fs.readdirSync(EXPORTS_DIR);

    for (const folder of folders) {
      const metadataPath = path.join(EXPORTS_DIR, folder, 'metadata.json');
      const validationPath = path.join(EXPORTS_DIR, folder, 'validation.json');

      if (fs.existsSync(metadataPath) && !fs.existsSync(validationPath)) {
        concepts.push(folder);
      }
    }

    logger.info(`Found ${concepts.length} pending concepts`);
    return concepts;
  }

  async run() {
    try {
      let conceptIds = [];

      if (this.opts.allPending) {
        conceptIds = await this.findPendingConcepts();
      } else {
        conceptIds = [this.opts.conceptId];
      }

      if (conceptIds.length === 0) {
        logger.warn('No concepts to validate');
        return;
      }

      const results = [];
      for (const cid of conceptIds) {
        try {
          const result = await this.validateConcept(cid);
          if (result) {
            results.push(result);
          }
        } catch (err) {
          logger.error(`Failed to validate ${cid}: ${err.message}`);
        }
      }

      // Summary
      logger.info(`\n===== VALIDATION SUMMARY =====`);
      logger.info(`Total concepts: ${results.length}`);
      const passCount = results.filter((r) => r.overall_verdict === 'PASS').length;
      const revisionCount = results.filter((r) => r.overall_verdict === 'NEEDS_REVISION').length;
      const rejectCount = results.filter((r) => r.overall_verdict === 'REJECT').length;
      logger.info(`PASS: ${passCount}, NEEDS_REVISION: ${revisionCount}, REJECT: ${rejectCount}`);
      const avgScore =
        results.length > 0
          ? (results.reduce((sum, r) => sum + r.production_quality_score, 0) / results.length).toFixed(1)
          : 0;
      logger.info(`Average quality score: ${avgScore}/100`);
    } catch (err) {
      logger.error(`Fatal error: ${err.message}`);
      process.exit(1);
    }
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const opts = parseArgs();
  const validator = new AssetValidator(opts);
  await validator.run();
}

if (require.main === module) {
  main().catch((err) => {
    logger.error(`Unhandled error: ${err.message}`);
    process.exit(1);
  });
}

module.exports = { AssetValidator, MechanicalValidator, VisualValidator };
