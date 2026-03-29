#!/usr/bin/env node

/**
 * 3D Forge Production Pipeline Orchestrator
 * 
 * Chains all production stages together in sequence:
 * SCAN → HARVEST → GENERATE → PRODUCE → VALIDATE → RENDER_SWARM → TEMPORAL_AUDIT → LEARN → METRICS → SKILL_LEARN
 * 
 * CLI: node forge-orchestrator.js [--full] [--scan-only] [--produce-only] [--validate-only] [--limit N] [--dry-run]
 */

const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { promisify } = require('util');
const { loadJson, saveJson, evaluateMode } = require('./lib/rework-budget');
const { ensureCheckpointState, isCheckpointApprovedForStage } = require('./lib/checkpoint-gate');

const execFileAsync = promisify(execFile);

// Load .env
require('./lib/env').loadEnv();

// Configuration
const REPO_ROOT = path.join(__dirname, '../../');
const SCRIPTS_DIR = path.join(REPO_ROOT, 'scripts/3d-forge');
const EXPORTS_DIR = path.join(REPO_ROOT, 'exports', '3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const CACHE_DIR = path.join(REPO_ROOT, 'cache');
const REFS_DIR = path.join(REPO_ROOT, 'data', '3d-forge', 'refs');
const REWORK_POLICY_PATH = path.join(REPO_ROOT, 'config', '3d-forge', 'rework-budget-policy.json');
const REWORK_STATE_PATH = path.join(REPO_ROOT, 'config', '3d-forge', 'rework-budget-state.json');
const CHECKPOINT_POLICY_PATH = path.join(REPO_ROOT, 'config', '3d-forge', 'checkpoint-policy.json');

// Parse CLI args
const args = process.argv.slice(2);
const runFull = args.includes('--full');
const scanOnly = args.includes('--scan-only');
const produceOnly = args.includes('--produce-only');
const validateOnly = args.includes('--validate-only');
const temporalOnly = args.includes('--temporal-only');
const skipTemporal = args.includes('--skip-temporal');
const isDryRun = args.includes('--dry-run');
const isVerbose = args.includes('--verbose');
const requireCheckpoints = args.includes('--require-checkpoints');
const runIdIdx = args.findIndex(a => a === '--run-id');
const runId = runIdIdx !== -1 ? args[runIdIdx + 1] : (new Date().toISOString().replace(/[:.]/g, '-'));
const shotGates = args.includes('--shot-gates');
const strictShotGates = args.includes('--strict-shot-gates');
const ciSamplesIdx = args.findIndex(a => a === '--ci-samples');
const ciSamples = ciSamplesIdx !== -1 ? parseInt(args[ciSamplesIdx + 1], 10) : null;
const CHECKPOINTS_STATE_PATH = path.join(REPO_ROOT, 'data', '3d-forge', 'checkpoints', `${runId}.json`);

const limitIdx = args.findIndex(a => a === '--limit');
const limit = limitIdx !== -1 ? parseInt(args[limitIdx + 1], 10) : null;

// Multi-Blender instance support: --port 9877 connects to a different Blender
const portIdx = args.findIndex(a => a === '--port');
const blenderPort = portIdx !== -1 ? args[portIdx + 1] : (process.env.BLENDER_MCP_PORT || '9876');
const hostIdx = args.findIndex(a => a === '--host');
const blenderHost = hostIdx !== -1 ? args[hostIdx + 1] : (process.env.BLENDER_MCP_HOST || '127.0.0.1');

// Ensure dirs exist
[EXPORTS_DIR, REPORTS_DIR, CACHE_DIR].forEach(dir => {
  fs.mkdirSync(dir, { recursive: true });
});

const log = (msg, level = 'INFO') => {
  const ts = new Date().toISOString();
  console.log(`[${ts}] [${level}] ${msg}`);
};

const vlog = (msg) => {
  if (isVerbose) log(msg, 'DEBUG');
};

/**
 * Live counts from stage outputs (trend-scanner / harvester / concept-generator do NOT write cache/trends.json).
 */
function countTrendsFromScanReport() {
  const p = path.join(REPORTS_DIR, 'trend-scan-latest.json');
  if (!fs.existsSync(p)) return null;
  try {
    const d = JSON.parse(fs.readFileSync(p, 'utf8'));
    return Array.isArray(d.trends) ? d.trends.length : 0;
  } catch (e) {
    return null;
  }
}

/** Sum image_count from manifests for trends in the scan report (respects --limit like image-harvester). */
function countHarvestedImagesFromManifests() {
  const scanPath = path.join(REPORTS_DIR, 'trend-scan-latest.json');
  if (!fs.existsSync(scanPath) || !fs.existsSync(REFS_DIR)) return null;
  try {
    const data = JSON.parse(fs.readFileSync(scanPath, 'utf8'));
    let trends = data.trends || [];
    if (limit && limit > 0) trends = trends.slice(0, limit);
    let total = 0;
    for (const t of trends) {
      const tid = t.trend_id;
      if (!tid) continue;
      const mp = path.join(REFS_DIR, tid, 'manifest.json');
      if (fs.existsSync(mp)) {
        const m = JSON.parse(fs.readFileSync(mp, 'utf8'));
        total += m.image_count || 0;
      }
    }
    return total;
  } catch (e) {
    return null;
  }
}

function countConceptsFromGenerationReport() {
  const p = path.join(REPORTS_DIR, 'concept-generation-latest.json');
  if (!fs.existsSync(p)) return null;
  try {
    const d = JSON.parse(fs.readFileSync(p, 'utf8'));
    if (typeof d.total_concepts === 'number') return d.total_concepts;
    if (Array.isArray(d.concepts)) return d.concepts.length;
    return 0;
  } catch (e) {
    return null;
  }
}

/**
 * Load or initialize pipeline state
 */
function loadPipelineState() {
  const statePath = path.join(REPORTS_DIR, '3d-forge-pipeline-state.json');
  if (fs.existsSync(statePath)) {
    try {
      return JSON.parse(fs.readFileSync(statePath, 'utf8'));
    } catch (e) {
      log(`Failed to parse pipeline state: ${e.message}`, 'WARN');
    }
  }
  return initPipelineState();
}

/**
 * Initialize fresh pipeline state
 */
function initPipelineState() {
  return {
    last_run: null,
    stage: 'none',
    trends_scanned: 0,
    images_harvested: 0,
    concepts_generated: 0,
    assets_produced: 0,
    assets_validated: 0,
    assets_passed: 0,
    assets_rejected: 0,
    total_time_seconds: 0,
    total_cost_usd: 0,
    stage_timings: {},
    errors: [],
  };
}

/**
 * Save pipeline state
 */
function savePipelineState(state) {
  if (!isDryRun) {
    const statePath = path.join(REPORTS_DIR, '3d-forge-pipeline-state.json');
    fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
    vlog(`Pipeline state saved`);
  }
}

/**
 * Run a stage script
 */
async function runStage(stageName, scriptName, scriptArgs = []) {
  const stageStart = Date.now();
  log(`>>> Starting stage: ${stageName}`);

  const scriptPath = path.join(SCRIPTS_DIR, scriptName);

  if (!fs.existsSync(scriptPath)) {
    log(`Script not found: ${scriptPath}`, 'ERROR');
    throw new Error(`Missing script: ${scriptName}`);
  }

  try {
    const args = [scriptPath, ...scriptArgs];
    if (isDryRun) args.push('--dry-run');
    // Pass Blender connection to sub-scripts (multi-instance support)
    args.push('--port', blenderPort, '--host', blenderHost);
    if (isVerbose) args.push('--verbose');

    vlog(`Executing: node ${args.join(' ')}`);

    const { stdout, stderr } = await execFileAsync('node', args, {
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      timeout: 45 * 60 * 1000, // 45 minutes (large harvest / produce batches)
    });

    if (stdout) vlog(`Output: ${stdout}`);
    if (stderr) log(`Stage warnings: ${stderr}`, 'WARN');

    const duration = (Date.now() - stageStart) / 1000;
    log(`<<< Stage complete: ${stageName} (${duration.toFixed(1)}s)`);

    return { success: true, duration };
  } catch (error) {
    log(`Stage failed: ${stageName}`, 'ERROR');
    log(`Error: ${error.message}`, 'ERROR');
    throw error;
  }
}

/**
 * Stage 1: SCAN for trends
 */
async function stageScan(state) {
  try {
    await runStage('SCAN', 'trend-scanner.js');
    state.stage = 'scan';

    const fromReport = countTrendsFromScanReport();
    if (fromReport !== null) {
      state.trends_scanned = fromReport;
    } else {
      const trendCache = path.join(CACHE_DIR, 'trends.json');
      if (fs.existsSync(trendCache)) {
        try {
          const trends = JSON.parse(fs.readFileSync(trendCache, 'utf8'));
          state.trends_scanned = Array.isArray(trends) ? trends.length : 0;
        } catch (e) {
          state.trends_scanned = 0;
        }
      }
    }
    state.trends_scanned = state.trends_scanned ?? 0;
    log(`Trends scanned: ${state.trends_scanned}`);

    return true;
  } catch (error) {
    log(`SCAN stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'scan',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 2: HARVEST reference images
 */
async function stageHarvest(state) {
  try {
    const limitArg = limit ? ['--limit', String(limit)] : [];
    await runStage('HARVEST', 'image-harvester.js', limitArg);
    state.stage = 'harvest';

    const imgTotal = countHarvestedImagesFromManifests();
    if (imgTotal !== null) {
      state.images_harvested = imgTotal;
    } else {
      const harvestCache = path.join(CACHE_DIR, 'images.json');
      if (fs.existsSync(harvestCache)) {
        try {
          const images = JSON.parse(fs.readFileSync(harvestCache, 'utf8'));
          state.images_harvested = Array.isArray(images) ? images.length : 0;
        } catch (e) {
          state.images_harvested = 0;
        }
      }
    }
    state.images_harvested = state.images_harvested ?? 0;
    log(`Images harvested (downloaded, this scan scope): ${state.images_harvested}`);

    return true;
  } catch (error) {
    log(`HARVEST stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'harvest',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 3: GENERATE concepts
 */
async function stageGenerate(state) {
  try {
    const limitArg = limit ? ['--limit', String(limit)] : [];
    await runStage('GENERATE', 'concept-generator.js', limitArg);
    state.stage = 'generate';

    const genCount = countConceptsFromGenerationReport();
    if (genCount !== null) {
      state.concepts_generated = genCount;
    } else {
      const conceptCache = path.join(CACHE_DIR, 'concepts.json');
      if (fs.existsSync(conceptCache)) {
        try {
          const concepts = JSON.parse(fs.readFileSync(conceptCache, 'utf8'));
          state.concepts_generated = Array.isArray(concepts) ? concepts.length : 0;
        } catch (e) {
          state.concepts_generated = 0;
        }
      }
    }
    state.concepts_generated = state.concepts_generated ?? 0;
    log(`Concepts generated: ${state.concepts_generated}`);

    return true;
  } catch (error) {
    log(`GENERATE stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'generate',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 4: PRODUCE 3D assets
 */
async function stageProduce(state) {
  try {
    const limitArg = limit ? ['--limit', String(limit)] : [];
    await runStage('PRODUCE', 'blender-producer.js', ['--all-pending', ...limitArg]);
    state.stage = 'produce';

    // Count produced assets
    if (fs.existsSync(EXPORTS_DIR)) {
      const produced = fs.readdirSync(EXPORTS_DIR).filter(f => {
        const subpath = path.join(EXPORTS_DIR, f);
        return fs.statSync(subpath).isDirectory();
      });
      state.assets_produced = produced.length;
      log(`Assets produced: ${state.assets_produced}`);
    }

    return true;
  } catch (error) {
    log(`PRODUCE stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'produce',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 5: VALIDATE assets
 */
async function stageValidate(state) {
  try {
    const policy = loadJson(REWORK_POLICY_PATH, { modes: { balanced: { max_visual_retries: 1 } } });
    const budgetState = loadJson(REWORK_STATE_PATH, { current_mode: 'balanced' });
    const modeCfg = (policy.modes && policy.modes[budgetState.current_mode || 'balanced']) || { max_visual_retries: 1 };
    const validatorArgs = ['--all-pending', '--auto-fix'];
    if (shotGates) validatorArgs.push('--shot-gates');
    if (strictShotGates) validatorArgs.push('--strict-shot-gates');
    if (ciSamples && Number.isFinite(ciSamples)) validatorArgs.push('--ci-samples', String(ciSamples));
    else if (modeCfg.max_visual_retries > 1) validatorArgs.push('--ci-samples', String(modeCfg.max_visual_retries));
    await runStage('VALIDATE', 'asset-validator.js', validatorArgs);
    state.stage = 'validate';

    // Count validation results
    let passed = 0;
    let rejected = 0;
    let total = 0;

    if (fs.existsSync(EXPORTS_DIR)) {
      const subdirs = fs.readdirSync(EXPORTS_DIR);
      subdirs.forEach(subdir => {
        const subpath = path.join(EXPORTS_DIR, subdir);
        const stat = fs.statSync(subpath);

        if (!stat.isDirectory()) return;

        const validationPath = path.join(subpath, 'validation.json');
        if (fs.existsSync(validationPath)) {
          try {
            const validation = JSON.parse(fs.readFileSync(validationPath, 'utf8'));
            total++;
            // Use correct field: overall_verdict (NOT passed/status)
            if (validation.overall_verdict === 'PASS') {
              passed++;
            } else if (validation.overall_verdict === 'REJECT') {
              rejected++;
            }
          } catch (e) {
            vlog(`Failed to parse validation in ${subdir}`);
          }
        }
      });
    }

    state.assets_validated = total;
    state.assets_passed = passed;
    state.assets_rejected = rejected;
    log(`Assets validated: ${total} (passed: ${passed}, rejected: ${rejected})`);

    return true;
  } catch (error) {
    log(`VALIDATE stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'validate',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 5.5: RENDER SWARM — Parallel post-processing quality improvement
 * Runs render-swarm.js between VALIDATE and TEMPORAL_AUDIT for 4x throughput.
 * Only runs if validation found assets with visual scores between floor (60) and excellence (85).
 */
async function stageRenderSwarm(state) {
  try {
    // Check if any assets need visual improvement (score 60-84)
    const needsSwarm = [];
    if (fs.existsSync(EXPORTS_DIR)) {
      const subdirs = fs.readdirSync(EXPORTS_DIR);
      for (const subdir of subdirs) {
        const valPath = path.join(EXPORTS_DIR, subdir, 'validation.json');
        if (!fs.existsSync(valPath)) continue;
        try {
          const val = JSON.parse(fs.readFileSync(valPath, 'utf8'));
          const score = val.production_quality_score || 0;
          const mechPass = val.mechanical?.passed === true;
          // Only swarm assets that mechanically pass but visually need work
          if (mechPass && score >= 60 && score < 85) {
            needsSwarm.push({ id: subdir, score });
          }
        } catch (e) { /* skip */ }
      }
    }

    if (needsSwarm.length === 0) {
      log('RENDER_SWARM: No assets in improvement range (60-84) — skipping');
      state.render_swarm_skipped = true;
      return true;
    }

    log(`RENDER_SWARM: ${needsSwarm.length} assets eligible for parallel improvement`);
    log(`  Candidates: ${needsSwarm.map(a => `${a.id}(${a.score})`).join(', ')}`);

    // Run render-swarm with target 85 and max 3 retries
    const swarmArgs = ['--target-score=85', '--max-retries=3'];
    await runStage('RENDER_SWARM', 'render-swarm.js', swarmArgs);
    state.stage = 'render_swarm';

    // Read swarm report if available
    const swarmReports = fs.readdirSync(REPORTS_DIR)
      .filter(f => f.startsWith('swarm_results_'))
      .sort()
      .reverse();

    if (swarmReports.length > 0) {
      try {
        const report = JSON.parse(fs.readFileSync(path.join(REPORTS_DIR, swarmReports[0]), 'utf8'));
        state.render_swarm_cameras = report.stats?.totalCameras || 0;
        state.render_swarm_improved = report.stats?.improved || 0;
        state.render_swarm_escalated = report.stats?.escalated || 0;
        state.render_swarm_avg_improvement = report.stats?.avgFinal
          ? (parseFloat(report.stats.avgFinal) - parseFloat(report.stats.avgOriginal)).toFixed(1)
          : '0.0';
        log(`RENDER_SWARM: ${state.render_swarm_improved}/${state.render_swarm_cameras} cameras improved, ${state.render_swarm_escalated} escalated`);
      } catch (e) {
        vlog(`Failed to parse swarm report: ${e.message}`);
      }
    }

    return true;
  } catch (error) {
    log(`RENDER_SWARM stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'render_swarm',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    // Non-fatal: swarm failure shouldn't halt pipeline
    return true;
  }
}

async function stageTemporalAudit(state) {
  try {
    await runStage('TEMPORAL_AUDIT', 'temporal-audit.js');
    state.stage = 'temporal_audit';
    const reportPath = path.join(REPORTS_DIR, '3d-forge-temporal-latest.json');
    if (fs.existsSync(reportPath)) {
      const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
      state.assets_temporal_audited = report.assets_analyzed || 0;
      state.temporal_pass_rate = report.temporal_stability_pass_rate || 0;
    }
    return true;
  } catch (error) {
    log(`TEMPORAL_AUDIT stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'temporal_audit',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 6: LEARN from batch
 */
async function stageLearn(state) {
  try {
    await runStage('LEARN', 'autoresearch-agent.js');
    state.stage = 'learn';

    // Load autoresearch report if it exists
    const reportPath = path.join(REPORTS_DIR, '3d-forge-autoresearch-latest.json');
    if (fs.existsSync(reportPath)) {
      try {
        const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
        if (report.kpis) {
          state.total_cost_usd = report.kpis.cost_per_asset_usd * state.assets_produced || 0;
        }
      } catch (e) {
        vlog(`Failed to read autoresearch report`);
      }
    }

    return true;
  } catch (error) {
    log(`LEARN stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'learn',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 7: METRICS — aggregate validation exports for learning
 */
async function stageMetrics(state) {
  try {
    await runStage('METRICS', 'metrics-tracker.js');
    state.stage = 'metrics';
    return true;
  } catch (error) {
    log(`METRICS stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'metrics',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Stage 8: SKILL_LEARN — write skill-plan-adjustments.json from metrics + failures
 */
async function stageSkillLearn(state) {
  try {
    await runStage('SKILL_LEARN', 'skill-learning-loop.js');
    state.stage = 'skill_learn';
    return true;
  } catch (error) {
    log(`SKILL_LEARN stage failed: ${error.message}`, 'ERROR');
    state.errors.push({
      stage: 'skill_learn',
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    return false;
  }
}

/**
 * Determine which stages to run
 */
function getStages() {
  const tail = ['metrics', 'skill_learn'];
  if (runFull) {
    return ['scan', 'harvest', 'generate', 'produce', 'validate', 'render_swarm', ...(skipTemporal ? [] : ['temporal_audit']), 'learn', ...tail];
  }

  const stages = [];

  if (scanOnly) return ['scan'];
  if (produceOnly) return ['produce'];
  if (validateOnly) return ['validate'];
  if (temporalOnly) return ['temporal_audit'];

  // Default: full pipeline (render_swarm runs between validate and temporal_audit)
  return ['scan', 'harvest', 'generate', 'produce', 'validate', 'render_swarm', ...(skipTemporal ? [] : ['temporal_audit']), 'learn', ...tail];
}

/**
 * Print summary report
 */
function printSummary(state, duration) {
  log('=== PIPELINE SUMMARY ===');
  log(`Run completed in ${duration.toFixed(1)}s`);
  log(`Stage: ${state.stage}`);
  log(`Trends scanned: ${state.trends_scanned}`);
  log(`Images harvested: ${state.images_harvested}`);
  log(`Concepts generated: ${state.concepts_generated}`);
  log(`Assets produced: ${state.assets_produced}`);
  log(`Assets validated: ${state.assets_validated}`);
  log(`  - Passed: ${state.assets_passed}`);
  log(`  - Rejected: ${state.assets_rejected}`);
  if (state.render_swarm_cameras) {
    log(`Render swarm: ${state.render_swarm_improved}/${state.render_swarm_cameras} improved (avg +${state.render_swarm_avg_improvement})`);
  }
  if (state.total_cost_usd > 0) {
    log(`Total cost: $${state.total_cost_usd.toFixed(2)}`);
  }

  if (state.errors.length > 0) {
    log(`=== ERRORS (${state.errors.length}) ===`);
    state.errors.forEach(err => {
      log(`  [${err.stage}] ${err.error}`, 'ERROR');
    });
  }
}

/**
 * Main execution
 */
async function main() {
  try {
    log('=== 3D Forge Production Pipeline Starting ===');
    const pipelineStart = Date.now();

    // Load state
    const state = loadPipelineState();
    state.last_run = new Date().toISOString();
    state.errors = [];

    // Get stages to run
    const stagesToRun = getStages();
    log(`Running ${stagesToRun.length} stages: ${stagesToRun.join(' → ')}`);

    // Run stages in sequence
    for (const stage of stagesToRun) {
      const stageStart = Date.now();
      if (requireCheckpoints) {
        const cpPolicy = loadJson(CHECKPOINT_POLICY_PATH, { required_checkpoints: [] });
        const cpState = ensureCheckpointState(CHECKPOINTS_STATE_PATH, runId, cpPolicy);
        const gate = isCheckpointApprovedForStage(cpState, stage);
        if (!gate.ok) {
          log(`Checkpoint gate blocked stage '${stage}'. Missing approvals: ${gate.missing.join(', ')}`, 'WARN');
          log(`Approve using checkpoint-cli with run-id ${runId}`, 'WARN');
          break;
        }
      }

      let success = false;
      try {
        switch (stage) {
          case 'scan':
            success = await stageScan(state);
            break;
          case 'harvest':
            success = await stageHarvest(state);
            break;
          case 'generate':
            success = await stageGenerate(state);
            break;
          case 'produce':
            success = await stageProduce(state);
            break;
          case 'validate':
            success = await stageValidate(state);
            break;
          case 'render_swarm':
            success = await stageRenderSwarm(state);
            break;
          case 'temporal_audit':
            success = await stageTemporalAudit(state);
            break;
          case 'learn':
            success = await stageLearn(state);
            break;
          case 'metrics':
            success = await stageMetrics(state);
            break;
          case 'skill_learn':
            success = await stageSkillLearn(state);
            break;
        }
      } catch (error) {
        log(`Stage ${stage} threw exception: ${error.message}`, 'ERROR');
        success = false;
      }

      const stageDuration = (Date.now() - stageStart) / 1000;
      if (!state.stage_timings) state.stage_timings = {};
      state.stage_timings[stage] = stageDuration;

      if (!success) {
        log(`Pipeline halted at stage: ${stage}`, 'WARN');
        break;
      }
    }

    // Final state
    state.stage = state.stage || 'complete';
    const totalDuration = (Date.now() - pipelineStart) / 1000;
    state.total_time_seconds = totalDuration;
    const reportPath = path.join(REPORTS_DIR, '3d-forge-autoresearch-latest.json');
    if (fs.existsSync(reportPath)) {
      try {
        const report = JSON.parse(fs.readFileSync(reportPath, 'utf8'));
        const nextMode = evaluateMode(report.kpis || {});
        const budgetState = loadJson(REWORK_STATE_PATH, {
          current_mode: 'balanced',
          last_switched_at: null,
          switch_reason: 'initial',
          run_counters: { conservative_signals: 0, balanced_signals: 0, aggressive_signals: 0 },
        });
        if (budgetState.current_mode !== nextMode) {
          budgetState.current_mode = nextMode;
          budgetState.last_switched_at = new Date().toISOString();
          budgetState.switch_reason = 'kpi_policy';
          saveJson(REWORK_STATE_PATH, budgetState);
          log(`Rework budget mode switched to: ${nextMode}`);
        }
      } catch (e) {
        vlog(`Failed to update rework mode: ${e.message}`);
      }
    }

    // Save state
    savePipelineState(state);

    // Print summary
    printSummary(state, totalDuration);

    if (isDryRun) {
      log('DRY RUN: No actual execution occurred', 'INFO');
    }

    log('=== Pipeline Complete ===');
  } catch (error) {
    log(`Fatal error: ${error.message}`, 'ERROR');
    if (isVerbose) console.error(error);
    process.exit(1);
  }
}

main();
