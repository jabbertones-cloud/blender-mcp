#!/usr/bin/env node

/**
 * Render Improvement Loop — Automated score → diagnose → adjust → re-render → learn cycle.
 *
 * This is the missing piece that ties together:
 *   - render-quality-scorer.js (Tier 1 pixel + Tier 2 vision scoring)
 *   - asset-validator.js (mechanical + visual validation)
 *   - lib/fix-effectiveness.js (tracks which fixes actually improve scores)
 *   - lib/rework-budget.js (aggressive/balanced/conservative mode)
 *   - lib/failure-classifier.js (categorizes failures)
 *   - blender-producer.js (renders via MCP)
 *
 * The loop:
 *   1. SCORE: Run render-quality-scorer on existing render
 *   2. DIAGNOSE: Classify issues, match to known fix patterns
 *   3. ADJUST: Apply parameter changes via Blender MCP (lighting, camera, materials, samples)
 *   4. RE-RENDER: Trigger a new render with adjusted settings
 *   5. RE-SCORE: Score the new render
 *   6. LEARN: Log fix effectiveness (delta score), update priority rankings
 *   7. REPEAT: Up to max iterations or until score passes threshold
 *
 * CLI:
 *   node render-improvement-loop.js --asset-id <id> [--max-iterations 3] [--target-score 75] [--dry-run]
 *   node render-improvement-loop.js --all-below <score> [--max-iterations 2] [--dry-run]
 *   node render-improvement-loop.js --report  (show improvement history)
 *
 * Integrations:
 *   - Called by forge-orchestrator.js after VALIDATE stage
 *   - Called by autoresearch-agent.js when quality KPIs drop
 *   - Can run standalone for manual improvement passes
 */

'use strict';

const fs = require('fs');
const path = require('path');
const net = require('net');
const { execFile } = require('child_process');
const { promisify } = require('util');

const execFileAsync = promisify(execFile);

// Load .env
require('./lib/env').loadEnv();

// Import sibling modules
const { scoreRender, scoreTier1 } = require('./render-quality-scorer');
const { appendFixEffect, loadFixEvents, buildFixPriority } = require('./lib/fix-effectiveness');
const { evaluateMode } = require('./lib/rework-budget');
const { classifyFailures } = require('./lib/failure-classifier');

// ============================================================================
// CONFIG
// ============================================================================

const REPO_ROOT = path.join(__dirname, '..', '..');
const EXPORTS_DIR = path.join(REPO_ROOT, 'exports', '3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const CONFIG_DIR = path.join(REPO_ROOT, 'config', '3d-forge');
const DATA_DIR = path.join(REPO_ROOT, 'data', '3d-forge');

const BLENDER_MCP_HOST = process.env.BLENDER_MCP_HOST || '127.0.0.1';
const BLENDER_MCP_PORT = parseInt(process.env.BLENDER_MCP_PORT || '9876', 10);

const DEFAULT_TARGET_SCORE = 75;
const DEFAULT_MAX_ITERATIONS = 3;

const FIX_LOG_PATH = path.join(DATA_DIR, 'render-fix-effectiveness.jsonl');
const LOOP_HISTORY_PATH = path.join(REPORTS_DIR, 'render-improvement-history.json');

// Ensure dirs
[REPORTS_DIR, DATA_DIR, CONFIG_DIR].forEach(d => fs.mkdirSync(d, { recursive: true }));

// ============================================================================
// CLI
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    assetId: null,
    allBelow: null,
    maxIterations: DEFAULT_MAX_ITERATIONS,
    targetScore: DEFAULT_TARGET_SCORE,
    dryRun: false,
    verbose: false,
    report: false,
    tier: 'auto',
    port: BLENDER_MCP_PORT,
    host: BLENDER_MCP_HOST,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--asset-id': opts.assetId = args[++i]; break;
      case '--all-below': opts.allBelow = parseFloat(args[++i]); break;
      case '--max-iterations': opts.maxIterations = parseInt(args[++i], 10); break;
      case '--target-score': opts.targetScore = parseFloat(args[++i]); break;
      case '--dry-run': opts.dryRun = true; break;
      case '--verbose': opts.verbose = true; break;
      case '--report': opts.report = true; break;
      case '--tier': opts.tier = args[++i]; break;
      case '--port': opts.port = parseInt(args[++i], 10); break;
      case '--host': opts.host = args[++i]; break;
    }
  }

  return opts;
}

const log = (msg, level = 'INFO') => {
  console.log(`[${new Date().toISOString()}] [improve:${level.toLowerCase()}] ${msg}`);
};

// ============================================================================
// BLENDER MCP CLIENT (reuse pattern from asset-validator.js)
// ============================================================================

class BlenderMCPClient {
  constructor(host, port) {
    this.host = host;
    this.port = port;
  }

  async call(command, params = {}) {
    return new Promise((resolve, reject) => {
      const socket = net.createConnection(this.port, this.host);
      let buffer = '';
      let completed = false;

      socket.on('connect', () => {
        socket.write(JSON.stringify({ id: Date.now(), command, params }));
      });

      socket.on('data', (chunk) => {
        buffer += chunk.toString();
        let depth = 0, inStr = false, escaped = false, start = -1;
        for (let i = 0; i < buffer.length; i++) {
          const ch = buffer[i];
          if (escaped) { escaped = false; continue; }
          if (ch === '\\' && inStr) { escaped = true; continue; }
          if (ch === '"') { inStr = !inStr; continue; }
          if (inStr) continue;
          if (ch === '{') { if (depth === 0) start = i; depth++; }
          if (ch === '}') { depth--; if (depth === 0 && start >= 0) {
            try {
              const msg = JSON.parse(buffer.substring(start, i + 1));
              completed = true;
              socket.end();
              if (msg.error) reject(new Error(typeof msg.error === 'string' ? msg.error : JSON.stringify(msg.error)));
              else {
                const outer = msg.result || msg;
                const inner = outer.result !== undefined ? outer.result : outer;
                resolve(inner);
              }
            } catch (e) { /* continue buffering */ }
            break;
          }}
        }
      });

      socket.on('error', err => { if (!completed) reject(err); });
      socket.on('end', () => { if (!completed) reject(new Error('Connection closed without response')); });
      setTimeout(() => { if (!completed) { socket.end(); reject(new Error('Timeout')); } }, 60000);
    });
  }

  async executePython(code) {
    return this.call('execute_python', { code });
  }

  async render(outputPath, settings = {}) {
    return this.call('set_render_settings', {
      engine: settings.engine || 'eevee',
      resolution_x: settings.width || 1024,
      resolution_y: settings.height || 1024,
      samples: settings.samples || 64,
      ...settings,
    }).then(() => this.call('render', { output_path: outputPath }));
  }
}

// ============================================================================
// FIX CATALOG — Maps issues to Blender parameter adjustments
// ============================================================================

const FIX_CATALOG = [
  {
    fix_id: 'fix_overexposed_bg',
    targets: ['overexposed', 'low_contrast'],
    description: 'Set world background to medium gray (0.18) instead of white',
    apply: async (client) => {
      await client.executePython(
        `import bpy\n` +
        `world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')\n` +
        `bpy.context.scene.world = world\n` +
        `world.use_nodes = True\n` +
        `bg = world.node_tree.nodes.get('Background')\n` +
        `if bg:\n` +
        `    bg.inputs['Color'].default_value = (0.18, 0.18, 0.2, 1.0)\n` +
        `    bg.inputs['Strength'].default_value = 1.0\n` +
        `__result__ = {'applied': 'gray_background'}`
      );
    },
  },
  {
    fix_id: 'fix_underexposed_lights',
    targets: ['underexposed', 'blank_render'],
    description: 'Boost light energy: 500W key, 200W fill, 300W rim',
    apply: async (client) => {
      await client.executePython(
        `import bpy\n` +
        `lights = [o for o in bpy.data.objects if o.type == 'LIGHT']\n` +
        `if not lights:\n` +
        `    key = bpy.data.lights.new('Key', 'AREA')\n` +
        `    key.energy = 500\n` +
        `    key.size = 2.0\n` +
        `    kobj = bpy.data.objects.new('Key', key)\n` +
        `    bpy.context.collection.objects.link(kobj)\n` +
        `    kobj.location = (3, -3, 4)\n` +
        `else:\n` +
        `    energies = [500, 200, 300]\n` +
        `    for i, l in enumerate(lights):\n` +
        `        l.data.energy = energies[min(i, len(energies)-1)]\n` +
        `__result__ = {'applied': 'boost_lights', 'light_count': len(bpy.data.objects) - len([o for o in bpy.data.objects if o.type != 'LIGHT'])}`
      );
    },
  },
  {
    fix_id: 'fix_camera_framing',
    targets: ['blank_render', 'no_detail'],
    description: 'Auto-frame camera to model bounding box center',
    apply: async (client) => {
      await client.executePython(
        `import bpy\nimport mathutils\n` +
        `meshes = [o for o in bpy.data.objects if o.type == 'MESH' and o.visible_get() and not o.name.startswith('_ground_plane')]\n` +
        `if meshes:\n` +
        `    all_coords = []\n` +
        `    for obj in meshes:\n` +
        `        for v in obj.data.vertices:\n` +
        `            all_coords.append(obj.matrix_world @ v.co)\n` +
        `    if all_coords:\n` +
        `        center = sum(all_coords, mathutils.Vector()) / len(all_coords)\n` +
        `        xs = [c.x for c in all_coords]\n` +
        `        ys = [c.y for c in all_coords]\n` +
        `        zs = [c.z for c in all_coords]\n` +
        `        size = max(max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))\n` +
        `        dist = size * 2.5\n` +
        `        cam = bpy.data.objects.get('Camera')\n` +
        `        if not cam:\n` +
        `            cdata = bpy.data.cameras.new('Camera')\n` +
        `            cam = bpy.data.objects.new('Camera', cdata)\n` +
        `            bpy.context.collection.objects.link(cam)\n` +
        `            bpy.context.scene.camera = cam\n` +
        `        cam.location = (center.x + dist * 0.7, center.y - dist * 0.7, center.z + dist * 0.5)\n` +
        `        direction = center - cam.location\n` +
        `        cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()\n` +
        `        __result__ = {'applied': 'auto_frame', 'center': [center.x, center.y, center.z], 'dist': dist}\n` +
        `    else:\n` +
        `        __result__ = {'applied': False, 'reason': 'no_vertices'}\n` +
        `else:\n` +
        `    __result__ = {'applied': False, 'reason': 'no_meshes'}`
      );
    },
  },
  {
    fix_id: 'fix_low_contrast_lights',
    targets: ['low_contrast'],
    description: 'Increase light differential: stronger key, weaker fill',
    apply: async (client) => {
      await client.executePython(
        `import bpy\n` +
        `lights = sorted([o for o in bpy.data.objects if o.type == 'LIGHT'], key=lambda o: -o.data.energy)\n` +
        `if len(lights) >= 2:\n` +
        `    lights[0].data.energy = max(lights[0].data.energy, 500)\n` +
        `    for l in lights[1:]:\n` +
        `        l.data.energy = min(l.data.energy, lights[0].data.energy * 0.3)\n` +
        `__result__ = {'applied': 'contrast_lights', 'count': len(lights)}`
      );
    },
  },
  {
    fix_id: 'fix_noise_denoiser',
    targets: ['high_noise'],
    description: 'Enable render denoiser and increase samples',
    apply: async (client) => {
      await client.executePython(
        `import bpy\n` +
        `scene = bpy.context.scene\n` +
        `scene.render.use_compositing = True\n` +
        `if scene.render.engine == 'CYCLES':\n` +
        `    scene.cycles.use_denoising = True\n` +
        `    scene.cycles.samples = max(scene.cycles.samples, 128)\n` +
        `elif scene.render.engine == 'BLENDER_EEVEE':\n` +
        `    scene.eevee.taa_render_samples = max(scene.eevee.taa_render_samples, 128)\n` +
        `__result__ = {'applied': 'denoiser', 'engine': scene.render.engine}`
      );
    },
  },
  {
    fix_id: 'fix_materials_default',
    targets: ['no_detail'],
    description: 'Apply visible materials to meshes with no material',
    apply: async (client) => {
      await client.executePython(
        `import bpy\n` +
        `fixed = 0\n` +
        `for obj in bpy.data.objects:\n` +
        `    if obj.type == 'MESH' and not obj.name.startswith('_ground_plane'):\n` +
        `        if not obj.data.materials:\n` +
        `            mat = bpy.data.materials.new(name='AutoMat')\n` +
        `            mat.use_nodes = True\n` +
        `            bsdf = mat.node_tree.nodes.get('Principled BSDF')\n` +
        `            if bsdf:\n` +
        `                bsdf.inputs['Base Color'].default_value = (0.6, 0.6, 0.65, 1.0)\n` +
        `                bsdf.inputs['Roughness'].default_value = 0.4\n` +
        `                bsdf.inputs['Metallic'].default_value = 0.1\n` +
        `            obj.data.materials.append(mat)\n` +
        `            fixed += 1\n` +
        `__result__ = {'applied': 'auto_materials', 'fixed_count': fixed}`
      );
    },
  },
];

// ============================================================================
// IMPROVEMENT LOOP CORE
// ============================================================================

/**
 * Run the improvement loop for a single asset.
 *
 * Returns: { asset_id, initial_score, final_score, iterations, fixes_applied, improved }
 */
async function improveAsset(assetId, opts) {
  const assetDir = path.join(EXPORTS_DIR, assetId);

  if (!fs.existsSync(assetDir)) {
    log(`Asset not found: ${assetDir}`, 'ERROR');
    return { asset_id: assetId, error: 'Asset directory not found' };
  }

  // Find the render image
  const renderFile = fs.readdirSync(assetDir).find(f => /^render\.(png|jpg)$/i.test(f));
  if (!renderFile) {
    log(`No render image in ${assetId}`, 'WARN');
    return { asset_id: assetId, error: 'No render image found' };
  }

  const renderPath = path.join(assetDir, renderFile);
  const blendFile = path.join(assetDir, 'model.blend');

  const loopResult = {
    asset_id: assetId,
    started_at: new Date().toISOString(),
    initial_score: null,
    final_score: null,
    iterations: [],
    fixes_applied: [],
    improved: false,
    delta: 0,
  };

  // Step 1: Score the current render
  log(`Scoring ${assetId}...`);
  const initialResult = await scoreRender(renderPath, opts.tier);
  loopResult.initial_score = initialResult.final_score;
  log(`Initial score: ${initialResult.final_score} (${initialResult.final_verdict})`);

  // Check if already above target
  if (initialResult.final_score >= opts.targetScore) {
    log(`Already at target (${opts.targetScore}). Skipping.`);
    loopResult.final_score = initialResult.final_score;
    return loopResult;
  }

  // Load fix priority rankings (learn from past)
  const fixEvents = loadFixEvents(FIX_LOG_PATH);
  const fixPriority = buildFixPriority(fixEvents);

  // Determine rework mode
  const mode = evaluateMode(null); // Could pass current KPIs here

  let currentScore = initialResult.final_score;
  let currentIssues = initialResult.all_issues || [];

  // Create MCP client
  const client = opts.dryRun ? null : new BlenderMCPClient(opts.host, opts.port);

  // Open the .blend file in Blender (CRITICAL — see SKILL.md validator_opens_blend)
  if (!opts.dryRun && fs.existsSync(blendFile)) {
    try {
      log(`Opening ${blendFile} in Blender...`);
      await client.executePython(
        `import bpy\nbpy.ops.wm.open_mainfile(filepath='${blendFile.replace(/'/g, "\\'")}')\n__result__ = {'opened': True}`
      );
    } catch (e) {
      log(`Failed to open blend file: ${e.message}`, 'WARN');
    }
  }

  // Iteration loop
  for (let iter = 0; iter < opts.maxIterations; iter++) {
    log(`\n--- Iteration ${iter + 1}/${opts.maxIterations} (current: ${currentScore}, target: ${opts.targetScore}) ---`);

    if (currentScore >= opts.targetScore) {
      log(`Target reached. Stopping.`);
      break;
    }

    // Step 2: DIAGNOSE — Match current issues to available fixes
    const issueIds = new Set(currentIssues.map(i => i.id));
    const applicableFixes = FIX_CATALOG.filter(fix =>
      fix.targets.some(t => issueIds.has(t))
    );

    // Sort by historical effectiveness (if data exists)
    applicableFixes.sort((a, b) => {
      const aPriority = fixPriority.find(p => p.fix_id === a.fix_id)?.priority_score || 0.5;
      const bPriority = fixPriority.find(p => p.fix_id === b.fix_id)?.priority_score || 0.5;
      return bPriority - aPriority;
    });

    if (applicableFixes.length === 0) {
      log(`No applicable fixes for issues: ${[...issueIds].join(', ')}. Stopping.`);
      loopResult.iterations.push({
        iteration: iter + 1,
        score_before: currentScore,
        score_after: currentScore,
        fixes_attempted: [],
        reason_stopped: 'no_applicable_fixes',
      });
      break;
    }

    // Step 3: ADJUST — Apply fixes via Blender MCP
    const iterResult = {
      iteration: iter + 1,
      score_before: currentScore,
      score_after: null,
      fixes_attempted: [],
    };

    // Apply up to 2 fixes per iteration (avoid over-correcting)
    const fixesToApply = applicableFixes.slice(0, mode === 'aggressive' ? 3 : 2);

    for (const fix of fixesToApply) {
      log(`Applying fix: ${fix.fix_id} — ${fix.description}`);

      if (opts.dryRun) {
        log(`  [DRY-RUN] Would apply ${fix.fix_id}`);
        iterResult.fixes_attempted.push({ fix_id: fix.fix_id, applied: false, dry_run: true });
        continue;
      }

      const fixStart = Date.now();
      try {
        await fix.apply(client);
        iterResult.fixes_attempted.push({
          fix_id: fix.fix_id,
          applied: true,
          duration_ms: Date.now() - fixStart,
        });
        loopResult.fixes_applied.push(fix.fix_id);
        log(`  Applied successfully (${Date.now() - fixStart}ms)`);
      } catch (e) {
        log(`  Failed: ${e.message}`, 'WARN');
        iterResult.fixes_attempted.push({
          fix_id: fix.fix_id,
          applied: false,
          error: e.message,
          duration_ms: Date.now() - fixStart,
        });
      }
    }

    // Step 4: RE-RENDER
    if (!opts.dryRun) {
      log(`Re-rendering...`);
      try {
        // Save the iteration's render with a unique name
        const iterRenderPath = path.join(assetDir, `render_iter${iter + 1}.png`);
        await client.render(iterRenderPath, { engine: 'eevee', width: 1024, height: 1024, samples: 64 });

        // Also overwrite the main render
        await client.render(renderPath, { engine: 'eevee', width: 1024, height: 1024, samples: 64 });

        log(`Render complete: ${iterRenderPath}`);
      } catch (e) {
        log(`Re-render failed: ${e.message}`, 'ERROR');
        iterResult.render_error = e.message;
        loopResult.iterations.push(iterResult);
        continue;
      }

      // Step 5: RE-SCORE
      log(`Re-scoring...`);
      const newResult = await scoreRender(renderPath, opts.tier);
      iterResult.score_after = newResult.final_score;
      currentIssues = newResult.all_issues || [];
      const delta = newResult.final_score - currentScore;

      log(`Score: ${currentScore} → ${newResult.final_score} (delta: ${delta >= 0 ? '+' : ''}${delta})`);

      // Step 6: LEARN — Log fix effectiveness
      for (const fixAttempt of iterResult.fixes_attempted) {
        if (fixAttempt.applied) {
          appendFixEffect(FIX_LOG_PATH, {
            fix_id: fixAttempt.fix_id,
            asset_id: assetId,
            iteration: iter + 1,
            score_before: currentScore,
            score_after: newResult.final_score,
            delta_score: delta,
            success: delta > 0,
            duration_ms: fixAttempt.duration_ms,
            timestamp: new Date().toISOString(),
          });
        }
      }

      currentScore = newResult.final_score;
    } else {
      iterResult.score_after = currentScore; // unchanged in dry-run
    }

    loopResult.iterations.push(iterResult);
  }

  loopResult.final_score = currentScore;
  loopResult.delta = currentScore - loopResult.initial_score;
  loopResult.improved = loopResult.delta > 0;
  loopResult.finished_at = new Date().toISOString();

  log(`\nResult: ${loopResult.initial_score} → ${loopResult.final_score} (${loopResult.improved ? 'IMPROVED' : 'NO CHANGE'}, delta: ${loopResult.delta >= 0 ? '+' : ''}${loopResult.delta})`);

  return loopResult;
}

// ============================================================================
// HISTORY & REPORTING
// ============================================================================

function loadHistory() {
  if (fs.existsSync(LOOP_HISTORY_PATH)) {
    try {
      return JSON.parse(fs.readFileSync(LOOP_HISTORY_PATH, 'utf8'));
    } catch { return { runs: [] }; }
  }
  return { runs: [] };
}

function saveHistory(history) {
  fs.writeFileSync(LOOP_HISTORY_PATH, JSON.stringify(history, null, 2));
}

function printReport() {
  const history = loadHistory();
  const fixPriority = buildFixPriority(loadFixEvents(FIX_LOG_PATH));

  console.log('\n=== Render Improvement Loop Report ===\n');
  console.log(`Total runs: ${history.runs.length}`);

  if (history.runs.length > 0) {
    const improved = history.runs.filter(r => r.improved).length;
    const avgDelta = history.runs.reduce((sum, r) => sum + (r.delta || 0), 0) / history.runs.length;
    console.log(`Improved: ${improved}/${history.runs.length} (${(improved / history.runs.length * 100).toFixed(1)}%)`);
    console.log(`Avg delta: ${avgDelta >= 0 ? '+' : ''}${avgDelta.toFixed(1)} points`);

    // Last 5 runs
    console.log('\nRecent runs:');
    for (const run of history.runs.slice(-5)) {
      console.log(`  ${run.asset_id}: ${run.initial_score} → ${run.final_score} (${run.improved ? 'improved' : 'no change'}, ${run.iterations?.length || 0} iterations)`);
    }
  }

  if (fixPriority.length > 0) {
    console.log('\nFix effectiveness rankings:');
    for (const fix of fixPriority.slice(0, 10)) {
      console.log(`  ${fix.fix_id}: ${(fix.success_rate * 100).toFixed(0)}% success, avg delta ${fix.avg_delta_score >= 0 ? '+' : ''}${fix.avg_delta_score.toFixed(1)}, ${fix.attempts} attempts (priority: ${fix.priority_score.toFixed(3)})`);
    }
  }

  console.log('');
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const opts = parseArgs();

  if (opts.report) {
    printReport();
    return;
  }

  if (!opts.assetId && opts.allBelow === null) {
    console.log('Usage:');
    console.log('  node render-improvement-loop.js --asset-id <id> [--max-iterations 3] [--target-score 75]');
    console.log('  node render-improvement-loop.js --all-below 60 [--max-iterations 2]');
    console.log('  node render-improvement-loop.js --report');
    process.exit(1);
  }

  const history = loadHistory();
  const runResults = [];

  if (opts.assetId) {
    // Single asset
    const result = await improveAsset(opts.assetId, opts);
    runResults.push(result);

  } else if (opts.allBelow !== null) {
    // Find all assets with score below threshold
    log(`Scanning exports for assets below score ${opts.allBelow}...`);

    if (!fs.existsSync(EXPORTS_DIR)) {
      log(`Exports dir not found: ${EXPORTS_DIR}`, 'ERROR');
      process.exit(1);
    }

    const subdirs = fs.readdirSync(EXPORTS_DIR).filter(d => {
      try { return fs.statSync(path.join(EXPORTS_DIR, d)).isDirectory(); } catch { return false; }
    });

    for (const dir of subdirs) {
      const renderPath = path.join(EXPORTS_DIR, dir, 'render.png');
      if (!fs.existsSync(renderPath)) continue;

      // Quick Tier 1 score to decide if improvement is needed
      const quickScore = scoreTier1(renderPath);
      if (quickScore.score < opts.allBelow) {
        log(`${dir}: score ${quickScore.score} < ${opts.allBelow} — queuing for improvement`);
        const result = await improveAsset(dir, opts);
        runResults.push(result);
      }
    }
  }

  // Save to history
  for (const result of runResults) {
    history.runs.push(result);
  }
  // Keep last 200 runs
  if (history.runs.length > 200) history.runs = history.runs.slice(-200);
  saveHistory(history);

  // Save latest report
  const report = {
    timestamp: new Date().toISOString(),
    assets_processed: runResults.length,
    improved: runResults.filter(r => r.improved).length,
    avg_initial: runResults.length > 0 ? Math.round(runResults.reduce((s, r) => s + (r.initial_score || 0), 0) / runResults.length) : 0,
    avg_final: runResults.length > 0 ? Math.round(runResults.reduce((s, r) => s + (r.final_score || 0), 0) / runResults.length) : 0,
    results: runResults,
  };
  fs.writeFileSync(path.join(REPORTS_DIR, 'render-improvement-latest.json'), JSON.stringify(report, null, 2));
  log(`Report saved: ${path.join(REPORTS_DIR, 'render-improvement-latest.json')}`);

  // Summary
  log(`\n=== Summary ===`);
  log(`Processed: ${runResults.length} assets`);
  log(`Improved: ${report.improved}/${runResults.length}`);
  log(`Avg score: ${report.avg_initial} → ${report.avg_final}`);
}

module.exports = { improveAsset, FIX_CATALOG };

if (require.main === module) {
  main().catch(e => {
    log(`Fatal: ${e.message}`, 'ERROR');
    process.exit(2);
  });
}
