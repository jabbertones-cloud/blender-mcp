#!/usr/bin/env node

/**
 * Render Test Suite — Cohesive smoke, regression, and performance tests
 * for the Blender MCP integration and render pipeline.
 *
 * Test categories:
 *   SMOKE:       MCP connection, scene cleanup, basic render produces output
 *   REGRESSION:  Known fixes still work, operational learnings not regressed
 *   QUALITY:     Render quality scorer produces valid results on test images
 *   PERFORMANCE: Render time benchmarks, MCP latency
 *   INTEGRATION: Full pipeline stages work end-to-end
 *
 * CLI:
 *   node render-test-suite.js                        (run all tests)
 *   node render-test-suite.js --smoke                (smoke tests only)
 *   node render-test-suite.js --regression           (regression tests only)
 *   node render-test-suite.js --quality              (quality scorer tests only)
 *   node render-test-suite.js --performance          (performance benchmarks only)
 *   node render-test-suite.js --integration          (integration tests only)
 *   node render-test-suite.js --dry-run              (list tests without running)
 *   node render-test-suite.js --json-out path        (write results to file)
 *   node render-test-suite.js --skip-blender         (skip tests requiring live Blender)
 *
 * Exit codes:
 *   0 = all tests passed
 *   1 = some tests failed
 *   2 = suite error
 */

'use strict';

const fs = require('fs');
const path = require('path');
const net = require('net');

// Load .env
require('./lib/env').loadEnv();

// ============================================================================
// CONFIG
// ============================================================================

const REPO_ROOT = path.join(__dirname, '..', '..');
const EXPORTS_DIR = path.join(REPO_ROOT, 'exports', '3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const SCRIPTS_DIR = __dirname;

const BLENDER_HOST = process.env.BLENDER_MCP_HOST || '127.0.0.1';
const BLENDER_PORT = parseInt(process.env.BLENDER_MCP_PORT || '9876', 10);

// ============================================================================
// CLI
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    smoke: false,
    regression: false,
    quality: false,
    performance: false,
    integration: false,
    dryRun: false,
    jsonOut: null,
    skipBlender: false,
    verbose: false,
    port: BLENDER_PORT,
    host: BLENDER_HOST,
  };

  let anyCategory = false;
  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--smoke': opts.smoke = true; anyCategory = true; break;
      case '--regression': opts.regression = true; anyCategory = true; break;
      case '--quality': opts.quality = true; anyCategory = true; break;
      case '--performance': opts.performance = true; anyCategory = true; break;
      case '--integration': opts.integration = true; anyCategory = true; break;
      case '--dry-run': opts.dryRun = true; break;
      case '--json-out': opts.jsonOut = args[++i]; break;
      case '--skip-blender': opts.skipBlender = true; break;
      case '--verbose': opts.verbose = true; break;
      case '--port': opts.port = parseInt(args[++i], 10); break;
      case '--host': opts.host = args[++i]; break;
    }
  }

  // If no category specified, run all
  if (!anyCategory) {
    opts.smoke = true;
    opts.regression = true;
    opts.quality = true;
    opts.performance = true;
    opts.integration = true;
  }

  return opts;
}

// ============================================================================
// TEST RUNNER
// ============================================================================

class TestRunner {
  constructor(opts) {
    this.opts = opts;
    this.results = [];
    this.startTime = Date.now();
  }

  log(msg, level = 'INFO') {
    const icon = level === 'PASS' ? '\u2705' : level === 'FAIL' ? '\u274C' : level === 'SKIP' ? '\u23ED' : '\u2139\uFE0F';
    console.log(`${icon} [${level}] ${msg}`);
  }

  async run(name, category, fn, { requiresBlender = false } = {}) {
    if (this.opts.skipBlender && requiresBlender) {
      this.results.push({ name, category, status: 'SKIP', reason: 'skip-blender', duration_ms: 0 });
      this.log(`${name} — skipped (requires Blender)`, 'SKIP');
      return;
    }

    if (this.opts.dryRun) {
      this.results.push({ name, category, status: 'DRY_RUN', duration_ms: 0 });
      this.log(`${name} — would run`, 'SKIP');
      return;
    }

    const start = Date.now();
    try {
      await fn();
      const duration = Date.now() - start;
      this.results.push({ name, category, status: 'PASS', duration_ms: duration });
      this.log(`${name} (${duration}ms)`, 'PASS');
    } catch (e) {
      const duration = Date.now() - start;
      this.results.push({ name, category, status: 'FAIL', error: e.message, duration_ms: duration });
      this.log(`${name} — ${e.message} (${duration}ms)`, 'FAIL');
    }
  }

  summary() {
    const total = this.results.length;
    const passed = this.results.filter(r => r.status === 'PASS').length;
    const failed = this.results.filter(r => r.status === 'FAIL').length;
    const skipped = this.results.filter(r => r.status === 'SKIP' || r.status === 'DRY_RUN').length;

    return {
      timestamp: new Date().toISOString(),
      total,
      passed,
      failed,
      skipped,
      pass_rate: total > 0 ? Number(((passed / (total - skipped)) * 100).toFixed(1)) : 0,
      duration_ms: Date.now() - this.startTime,
      verdict: failed === 0 ? 'PASS' : 'FAIL',
      results: this.results,
    };
  }
}

// ============================================================================
// HELPER: MCP CLIENT (lightweight, for test use)
// ============================================================================

function mcpCall(host, port, command, params = {}, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(port, host);
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
            resolve(msg);
          } catch (e) { /* continue */ }
          break;
        }}
      }
    });

    socket.on('error', err => { if (!completed) reject(err); });
    socket.on('end', () => { if (!completed) reject(new Error('Connection closed')); });
    setTimeout(() => { if (!completed) { socket.end(); reject(new Error('Timeout')); } }, timeoutMs);
  });
}

function mcpConnectable(host, port) {
  return new Promise((resolve) => {
    const socket = net.createConnection(port, host);
    socket.on('connect', () => { socket.end(); resolve(true); });
    socket.on('error', () => resolve(false));
    setTimeout(() => { socket.destroy(); resolve(false); }, 3000);
  });
}

// ============================================================================
// ASSERTION HELPERS
// ============================================================================

function assert(condition, message) {
  if (!condition) throw new Error(message || 'Assertion failed');
}

function assertType(value, type, name) {
  assert(typeof value === type, `${name} should be ${type}, got ${typeof value}`);
}

function assertRange(value, min, max, name) {
  assert(value >= min && value <= max, `${name} should be ${min}-${max}, got ${value}`);
}

// ============================================================================
// SMOKE TESTS
// ============================================================================

async function runSmokeTests(runner) {
  const { host, port } = runner.opts;

  await runner.run('MCP: TCP connection to Blender', 'smoke', async () => {
    const connectable = await mcpConnectable(host, port);
    assert(connectable, `Cannot connect to Blender MCP at ${host}:${port}`);
  }, { requiresBlender: true });

  await runner.run('MCP: execute_python returns result', 'smoke', async () => {
    const resp = await mcpCall(host, port, 'execute_python', {
      code: `__result__ = {'test': True, 'version': 'ok'}`
    });
    assert(resp.result, 'No result in response');
    const inner = resp.result.result !== undefined ? resp.result.result : resp.result;
    assert(inner.test === true, 'Python result not unwrapped correctly');
  }, { requiresBlender: true });

  await runner.run('MCP: scene cleanup works', 'smoke', async () => {
    // Step 1: new file
    await mcpCall(host, port, 'save_file', { action: 'new', use_empty: true });
    // Step 2: Python nuke
    const resp = await mcpCall(host, port, 'execute_python', {
      code: `import bpy\nfor obj in list(bpy.data.objects):\n    bpy.data.objects.remove(obj, do_unlink=True)\n__result__ = {'objects': len(bpy.data.objects)}`
    });
    const inner = resp.result?.result !== undefined ? resp.result.result : resp.result;
    assert(inner.objects === 0, `Scene not clean: ${inner.objects} objects remain`);
  }, { requiresBlender: true });

  await runner.run('MCP: basic render produces file', 'smoke', async () => {
    const testRender = path.join(REPORTS_DIR, '_test_render.png');
    fs.mkdirSync(REPORTS_DIR, { recursive: true });

    // Create a simple cube scene
    await mcpCall(host, port, 'save_file', { action: 'new', use_empty: true });
    await mcpCall(host, port, 'execute_python', {
      code: `import bpy\n` +
        `for obj in list(bpy.data.objects):\n    bpy.data.objects.remove(obj, do_unlink=True)\n` +
        `bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))\n` +
        `cdata = bpy.data.cameras.new('TestCam')\ncam = bpy.data.objects.new('TestCam', cdata)\n` +
        `bpy.context.collection.objects.link(cam)\ncam.location = (3, -3, 2)\n` +
        `bpy.context.scene.camera = cam\n` +
        `ldata = bpy.data.lights.new('TestLight', 'AREA')\nldata.energy = 500\n` +
        `lobj = bpy.data.objects.new('TestLight', ldata)\n` +
        `bpy.context.collection.objects.link(lobj)\nlobj.location = (2, -2, 4)\n` +
        `__result__ = {'objects': len(bpy.data.objects)}`
    });

    await mcpCall(host, port, 'set_render_settings', {
      engine: 'eevee', resolution_x: 256, resolution_y: 256, samples: 16,
    });
    await mcpCall(host, port, 'render', { output_path: testRender }, 30000);

    assert(fs.existsSync(testRender), 'Render file was not created');
    const stat = fs.statSync(testRender);
    assert(stat.size > 1000, `Render file too small (${stat.size} bytes) — likely blank`);

    // Cleanup test render
    try { fs.unlinkSync(testRender); } catch { /* ok */ }
  }, { requiresBlender: true });

  await runner.run('Scripts: render-quality-scorer.js loads', 'smoke', async () => {
    const mod = require('./render-quality-scorer');
    assert(typeof mod.scoreRender === 'function', 'scoreRender not exported');
    assert(typeof mod.scoreTier1 === 'function', 'scoreTier1 not exported');
    assert(typeof mod.scoreTier2 === 'function', 'scoreTier2 not exported');
  });

  await runner.run('Scripts: render-improvement-loop.js loads', 'smoke', async () => {
    const mod = require('./render-improvement-loop');
    assert(typeof mod.improveAsset === 'function', 'improveAsset not exported');
    assert(Array.isArray(mod.FIX_CATALOG), 'FIX_CATALOG not exported');
    assert(mod.FIX_CATALOG.length >= 5, `Only ${mod.FIX_CATALOG.length} fixes in catalog (expected >=5)`);
  });

  await runner.run('Scripts: lib modules load', 'smoke', async () => {
    const fixEff = require('./lib/fix-effectiveness');
    assert(typeof fixEff.appendFixEffect === 'function', 'appendFixEffect missing');
    assert(typeof fixEff.buildFixPriority === 'function', 'buildFixPriority missing');

    const rework = require('./lib/rework-budget');
    assert(typeof rework.evaluateMode === 'function', 'evaluateMode missing');

    const failClass = require('./lib/failure-classifier');
    assert(typeof failClass.classifyFailures === 'function', 'classifyFailures missing');
  });

  await runner.run('Scripts: forge-orchestrator.js exists', 'smoke', async () => {
    const filePath = path.join(SCRIPTS_DIR, 'forge-orchestrator.js');
    assert(fs.existsSync(filePath), 'forge-orchestrator.js not found');
    const stat = fs.statSync(filePath);
    assert(stat.size > 500, `forge-orchestrator.js too small (${stat.size} bytes)`);
  });
}

// ============================================================================
// REGRESSION TESTS
// ============================================================================

async function runRegressionTests(runner) {
  const { host, port } = runner.opts;

  await runner.run('Regression: no blender_ prefix in MCP calls', 'regression', async () => {
    // Scan all JS files in 3d-forge for client.call('blender_*') anti-pattern
    const files = fs.readdirSync(SCRIPTS_DIR).filter(f => f.endsWith('.js'));
    const violations = [];
    for (const file of files) {
      const content = fs.readFileSync(path.join(SCRIPTS_DIR, file), 'utf8');
      const matches = content.match(/\.call\(['"]blender_(?:execute_python|render|export|cleanup)['"]/g);
      if (matches) violations.push({ file, matches });
    }
    assert(violations.length === 0, `blender_ prefix in MCP calls: ${JSON.stringify(violations)}`);
  });

  await runner.run('Regression: Python code uses single quotes only', 'regression', async () => {
    const files = fs.readdirSync(SCRIPTS_DIR).filter(f => f.endsWith('.js'));
    const violations = [];
    for (const file of files) {
      const content = fs.readFileSync(path.join(SCRIPTS_DIR, file), 'utf8');
      // Find executePython or execute_python calls with double quotes in Python code
      const regex = /executePython\(`([^`]+)`\)|call\('execute_python',\s*\{[^}]*code:\s*`([^`]+)`/g;
      let match;
      while ((match = regex.exec(content)) !== null) {
        const pyCode = match[1] || match[2];
        // Check for double quotes that aren't in JS template parts
        if (pyCode && /[^\\]"/.test(pyCode.replace(/\\"/g, ''))) {
          violations.push({ file, snippet: pyCode.substring(0, 80) });
        }
      }
    }
    // Allow some false positives (comments, etc.) but flag if many
    assert(violations.length < 3, `Possible double quotes in Python code: ${JSON.stringify(violations.slice(0, 3))}`);
  });

  await runner.run('Regression: validator opens .blend before measuring', 'regression', async () => {
    const validatorPath = path.join(SCRIPTS_DIR, 'asset-validator.js');
    const content = fs.readFileSync(validatorPath, 'utf8');
    assert(content.includes('open_mainfile'), 'asset-validator.js missing bpy.ops.wm.open_mainfile call');
  });

  await runner.run('Regression: ground plane exclusion in validator', 'regression', async () => {
    const validatorPath = path.join(SCRIPTS_DIR, 'asset-validator.js');
    const content = fs.readFileSync(validatorPath, 'utf8');
    assert(content.includes('_ground_plane'), 'asset-validator.js missing _ground_plane exclusion');
  });

  await runner.run('Regression: EXPORTS_DIR uses REPO_ROOT not cwd (new scripts)', 'regression', async () => {
    // Only check the scorer and improvement loop — not the test suite itself
    const newFiles = ['render-quality-scorer.js', 'render-improvement-loop.js'];
    for (const file of newFiles) {
      const filePath = path.join(SCRIPTS_DIR, file);
      if (!fs.existsSync(filePath)) continue;
      const content = fs.readFileSync(filePath, 'utf8');
      if (content.includes('process.cwd()') && content.includes('EXPORTS_DIR')) {
        throw new Error(`${file} uses process.cwd() for EXPORTS_DIR`);
      }
    }
  });

  await runner.run('Regression: brace-depth parser in MCP clients', 'regression', async () => {
    // Check that MCP client code in the pipeline uses brace-depth parsing, not readline.
    // Only check files that define MCP clients (have socket connect + data handler).
    const files = ['asset-validator.js', 'render-improvement-loop.js', 'blender-producer.js'];
    for (const file of files) {
      const filePath = path.join(SCRIPTS_DIR, file);
      if (!fs.existsSync(filePath)) continue;
      const content = fs.readFileSync(filePath, 'utf8');
      if (content.includes('createConnection') && content.includes("on('data'")) {
        // Look for actual readline usage in the data handler, not just the string
        const hasReadline = /\.on\(\s*['"]line['"]\s*\)/.test(content);
        assert(!hasReadline, `${file} uses readline event instead of brace-depth parser`);
      }
    }
  });

  await runner.run('Regression: fix catalog covers known issue types', 'regression', async () => {
    const { FIX_CATALOG } = require('./render-improvement-loop');
    const coveredIssues = new Set(FIX_CATALOG.flatMap(f => f.targets));
    const requiredIssues = ['blank_render', 'overexposed', 'underexposed', 'low_contrast', 'no_detail', 'high_noise'];
    const missing = requiredIssues.filter(i => !coveredIssues.has(i));
    assert(missing.length === 0, `Fix catalog missing coverage for: ${missing.join(', ')}`);
  });
}

// ============================================================================
// QUALITY SCORER TESTS
// ============================================================================

async function runQualityTests(runner) {

  await runner.run('Quality: Tier 1 scorer handles missing file gracefully', 'quality', async () => {
    const { scoreTier1 } = require('./render-quality-scorer');
    const result = scoreTier1('/nonexistent/image.png');
    assert(result.verdict === 'ERROR', 'Should return ERROR for missing file');
    assert(result.score === 0, 'Score should be 0 for missing file');
  });

  await runner.run('Quality: Tier 1 returns valid structure', 'quality', async () => {
    // Find any existing render to test with
    let testImage = null;
    if (fs.existsSync(EXPORTS_DIR)) {
      for (const dir of fs.readdirSync(EXPORTS_DIR)) {
        const renderPath = path.join(EXPORTS_DIR, dir, 'render.png');
        if (fs.existsSync(renderPath)) { testImage = renderPath; break; }
      }
    }

    if (!testImage) {
      // Create a minimal test PNG (1x1 gray pixel)
      testImage = path.join(REPORTS_DIR, '_test_quality.png');
      fs.mkdirSync(REPORTS_DIR, { recursive: true });
      // Minimal valid PNG: 1x1 gray pixel
      const pngBuffer = createMinimalPng(128, 128, 128);
      fs.writeFileSync(testImage, pngBuffer);
    }

    const { scoreTier1 } = require('./render-quality-scorer');
    const result = scoreTier1(testImage);

    assertType(result.score, 'number', 'score');
    assertRange(result.score, 0, 100, 'score');
    assert(['PASS', 'ACCEPTABLE', 'NEEDS_IMPROVEMENT', 'REJECT', 'ERROR'].includes(result.verdict), `Invalid verdict: ${result.verdict}`);
    assert(result.checks, 'Missing checks object');
    assert(result.checks.blank, 'Missing blank check');
    assert(result.checks.contrast, 'Missing contrast check');
    assert(result.checks.exposure, 'Missing exposure check');
    assert(result.checks.detail, 'Missing detail check');
    assert(result.checks.noise, 'Missing noise check');
    assertType(result.duration_ms, 'number', 'duration_ms');

    // Cleanup
    const cleanupPath = path.join(REPORTS_DIR, '_test_quality.png');
    if (fs.existsSync(cleanupPath)) try { fs.unlinkSync(cleanupPath); } catch { /* ok */ }
  });

  await runner.run('Quality: scoreRender auto-tier works', 'quality', async () => {
    const { scoreRender } = require('./render-quality-scorer');

    // Create minimal test image
    const testImage = path.join(REPORTS_DIR, '_test_auto_tier.png');
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
    fs.writeFileSync(testImage, createMinimalPng(100, 100, 100));

    const result = await scoreRender(testImage, '1'); // Force Tier 1 only
    assert(result.tier1, 'Missing tier1 result');
    assert(result.final_score !== null, 'final_score should not be null');
    assertType(result.final_score, 'number', 'final_score');

    try { fs.unlinkSync(testImage); } catch { /* ok */ }
  });

  await runner.run('Quality: fix-effectiveness tracking works', 'quality', async () => {
    const { appendFixEffect, loadFixEvents, buildFixPriority } = require('./lib/fix-effectiveness');

    const testLog = path.join(REPORTS_DIR, `_test_fix_log_${Date.now()}.jsonl`);

    // Clean start
    try { fs.unlinkSync(testLog); } catch { /* ok */ }

    // Append some test events
    appendFixEffect(testLog, { fix_id: 'test_fix_a', success: true, delta_score: 10, duration_ms: 100 });
    appendFixEffect(testLog, { fix_id: 'test_fix_a', success: true, delta_score: 15, duration_ms: 120 });
    appendFixEffect(testLog, { fix_id: 'test_fix_b', success: false, delta_score: -5, duration_ms: 200 });

    const events = loadFixEvents(testLog);
    assert(events.length === 3, `Expected 3 events, got ${events.length}`);

    const priority = buildFixPriority(events);
    assert(priority.length === 2, `Expected 2 fix rankings, got ${priority.length}`);
    assert(priority[0].fix_id === 'test_fix_a', 'test_fix_a should be ranked first');
    assert(priority[0].success_rate === 1.0, 'test_fix_a should have 100% success');

    try { fs.unlinkSync(testLog); } catch { /* ok */ }
  });
}

// ============================================================================
// PERFORMANCE TESTS
// ============================================================================

async function runPerformanceTests(runner) {
  const { host, port } = runner.opts;

  await runner.run('Perf: MCP round-trip latency <500ms', 'performance', async () => {
    const start = Date.now();
    await mcpCall(host, port, 'execute_python', { code: `__result__ = {'ping': True}` }, 5000);
    const latency = Date.now() - start;
    assert(latency < 500, `MCP latency ${latency}ms exceeds 500ms limit`);
  }, { requiresBlender: true });

  await runner.run('Perf: Tier 1 scoring <200ms', 'performance', async () => {
    // Find a render to benchmark
    let testImage = null;
    if (fs.existsSync(EXPORTS_DIR)) {
      for (const dir of fs.readdirSync(EXPORTS_DIR)) {
        const renderPath = path.join(EXPORTS_DIR, dir, 'render.png');
        if (fs.existsSync(renderPath)) { testImage = renderPath; break; }
      }
    }

    if (!testImage) {
      testImage = path.join(REPORTS_DIR, '_test_perf.png');
      fs.writeFileSync(testImage, createMinimalPng(128, 128, 128));
    }

    const { scoreTier1 } = require('./render-quality-scorer');
    const result = scoreTier1(testImage);
    assert(result.duration_ms < 200, `Tier 1 scoring took ${result.duration_ms}ms (limit: 200ms)`);

    const cleanupPath = path.join(REPORTS_DIR, '_test_perf.png');
    if (fs.existsSync(cleanupPath)) try { fs.unlinkSync(cleanupPath); } catch { /* ok */ }
  });

  await runner.run('Perf: EEVEE render <10s (256x256)', 'performance', async () => {
    const testRender = path.join(REPORTS_DIR, '_test_perf_render.png');
    fs.mkdirSync(REPORTS_DIR, { recursive: true });

    // Quick scene
    await mcpCall(host, port, 'save_file', { action: 'new', use_empty: true });
    await mcpCall(host, port, 'execute_python', {
      code: `import bpy\nfor o in list(bpy.data.objects):\n    bpy.data.objects.remove(o, do_unlink=True)\nbpy.ops.mesh.primitive_cube_add()\ncdata = bpy.data.cameras.new('C')\ncam = bpy.data.objects.new('C', cdata)\nbpy.context.collection.objects.link(cam)\ncam.location = (3, -3, 2)\nbpy.context.scene.camera = cam\n__result__ = {'ok': True}`
    });
    await mcpCall(host, port, 'set_render_settings', { engine: 'eevee', resolution_x: 256, resolution_y: 256, samples: 16 });

    const start = Date.now();
    await mcpCall(host, port, 'render', { output_path: testRender }, 15000);
    const renderTime = Date.now() - start;

    assert(renderTime < 10000, `EEVEE render took ${renderTime}ms (limit: 10000ms)`);
    try { fs.unlinkSync(testRender); } catch { /* ok */ }
  }, { requiresBlender: true });
}

// ============================================================================
// INTEGRATION TESTS
// ============================================================================

async function runIntegrationTests(runner) {
  const { host, port } = runner.opts;

  await runner.run('Integration: full render → score → improve cycle (dry-run)', 'integration', async () => {
    // Verify the full loop loads and the dry-run path works
    const { FIX_CATALOG } = require('./render-improvement-loop');
    assert(FIX_CATALOG.length >= 5, 'Fix catalog should have >=5 entries');

    // Check each fix has required fields
    for (const fix of FIX_CATALOG) {
      assert(fix.fix_id, `Fix missing fix_id`);
      assert(Array.isArray(fix.targets), `Fix ${fix.fix_id} missing targets array`);
      assert(typeof fix.apply === 'function', `Fix ${fix.fix_id} missing apply function`);
      assert(fix.description, `Fix ${fix.fix_id} missing description`);
    }
  });

  await runner.run('Integration: autoresearch operational learnings loaded', 'integration', async () => {
    const autoresearchPath = path.join(SCRIPTS_DIR, 'autoresearch-agent.js');
    assert(fs.existsSync(autoresearchPath), 'autoresearch-agent.js not found');
    const content = fs.readFileSync(autoresearchPath, 'utf8');
    // Verify key learnings are still present
    assert(content.includes('python_single_quotes'), 'Missing python_single_quotes learning');
    assert(content.includes('mcp_no_prefix'), 'Missing mcp_no_prefix learning');
    assert(content.includes('validator_opens_blend'), 'Missing validator_opens_blend learning');
    assert(content.includes('camera_auto_framing'), 'Missing camera_auto_framing learning');
  });

  await runner.run('Integration: pipeline stages exist', 'integration', async () => {
    const requiredStages = [
      'forge-orchestrator.js',
      'trend-scanner.js',
      'image-harvester.js',
      'concept-generator.js',
      'blender-producer.js',
      'asset-validator.js',
      'autoresearch-agent.js',
      'render-quality-scorer.js',
      'render-improvement-loop.js',
    ];

    for (const stage of requiredStages) {
      const filePath = path.join(SCRIPTS_DIR, stage);
      assert(fs.existsSync(filePath), `Missing pipeline stage: ${stage}`);
      const stat = fs.statSync(filePath);
      assert(stat.size > 200, `${stage} is too small (${stat.size} bytes)`);
    }
  });

  await runner.run('Integration: new render scripts load as modules', 'integration', async () => {
    // Verify our new scripts can be required without error
    const scorer = require('./render-quality-scorer');
    assert(typeof scorer.scoreRender === 'function', 'render-quality-scorer: scoreRender missing');
    assert(typeof scorer.scoreTier1 === 'function', 'render-quality-scorer: scoreTier1 missing');

    const loop = require('./render-improvement-loop');
    assert(typeof loop.improveAsset === 'function', 'render-improvement-loop: improveAsset missing');
    assert(Array.isArray(loop.FIX_CATALOG), 'render-improvement-loop: FIX_CATALOG missing');
  });

  await runner.run('Integration: lib modules consistent', 'integration', async () => {
    const requiredLibs = [
      'lib/env.js',
      'lib/checkpoint-gate.js',
      'lib/failure-classifier.js',
      'lib/fix-effectiveness.js',
      'lib/rework-budget.js',
    ];

    for (const lib of requiredLibs) {
      const filePath = path.join(SCRIPTS_DIR, lib);
      assert(fs.existsSync(filePath), `Missing lib: ${lib}`);
    }
  });

  await runner.run('Integration: MCP → render → score (live)', 'integration', async () => {
    const testRender = path.join(REPORTS_DIR, '_test_integration.png');
    fs.mkdirSync(REPORTS_DIR, { recursive: true });

    // Clean scene
    await mcpCall(host, port, 'save_file', { action: 'new', use_empty: true });
    await mcpCall(host, port, 'execute_python', {
      code: `import bpy\nfor o in list(bpy.data.objects):\n    bpy.data.objects.remove(o, do_unlink=True)\n` +
        `bpy.ops.mesh.primitive_monkey_add(size=1)\n` +
        `cdata = bpy.data.cameras.new('C')\ncam = bpy.data.objects.new('C', cdata)\nbpy.context.collection.objects.link(cam)\n` +
        `cam.location = (3, -3, 2)\nbpy.context.scene.camera = cam\n` +
        `ldata = bpy.data.lights.new('L', 'AREA')\nldata.energy = 500\n` +
        `lobj = bpy.data.objects.new('L', ldata)\nbpy.context.collection.objects.link(lobj)\nlobj.location = (2, -2, 4)\n` +
        `world = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')\nbpy.context.scene.world = world\nworld.use_nodes = True\n` +
        `bg = world.node_tree.nodes.get('Background')\nif bg:\n    bg.inputs['Color'].default_value = (0.18, 0.18, 0.2, 1.0)\n` +
        `__result__ = {'objects': len(bpy.data.objects)}`
    });

    await mcpCall(host, port, 'set_render_settings', { engine: 'eevee', resolution_x: 512, resolution_y: 512, samples: 32 });
    await mcpCall(host, port, 'render', { output_path: testRender }, 30000);

    assert(fs.existsSync(testRender), 'Integration render not created');

    // Score it
    const { scoreTier1 } = require('./render-quality-scorer');
    const score = scoreTier1(testRender);
    assertType(score.score, 'number', 'score');
    assertRange(score.score, 0, 100, 'score');

    // A proper Suzanne render with lighting should score >30
    assert(score.score > 20, `Integration render scored too low: ${score.score} (expected >20 for lit Suzanne)`);

    try { fs.unlinkSync(testRender); } catch { /* ok */ }
  }, { requiresBlender: true });
}

// ============================================================================
// HELPER: Create a minimal valid PNG for testing
// ============================================================================

function createMinimalPng(r, g, b) {
  const zlib = require('zlib');
  const width = 8, height = 8;

  // Raw pixel data (filter byte + RGB per row)
  const rawData = Buffer.alloc(height * (1 + width * 3));
  for (let y = 0; y < height; y++) {
    rawData[y * (1 + width * 3)] = 0; // filter: None
    for (let x = 0; x < width; x++) {
      const offset = y * (1 + width * 3) + 1 + x * 3;
      rawData[offset] = r;
      rawData[offset + 1] = g;
      rawData[offset + 2] = b;
    }
  }

  const deflated = zlib.deflateSync(rawData);

  // Build PNG
  const chunks = [];

  // Signature
  chunks.push(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));

  // IHDR
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // color type (RGB)
  ihdr[10] = 0; // compression
  ihdr[11] = 0; // filter
  ihdr[12] = 0; // interlace
  chunks.push(makeChunk('IHDR', ihdr));

  // IDAT
  chunks.push(makeChunk('IDAT', deflated));

  // IEND
  chunks.push(makeChunk('IEND', Buffer.alloc(0)));

  return Buffer.concat(chunks);
}

function makeChunk(type, data) {
  const buf = Buffer.alloc(12 + data.length);
  buf.writeUInt32BE(data.length, 0);
  buf.write(type, 4, 4, 'ascii');
  data.copy(buf, 8);

  // CRC32
  const crcData = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = crc32(crcData);
  buf.writeUInt32BE(crc, 8 + data.length);

  return buf;
}

function crc32(buf) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i];
    for (let j = 0; j < 8; j++) {
      crc = (crc >>> 1) ^ (crc & 1 ? 0xEDB88320 : 0);
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const opts = parseArgs();
  const runner = new TestRunner(opts);

  console.log('\n=== Render Test Suite ===\n');
  console.log(`Blender MCP: ${opts.host}:${opts.port}`);
  console.log(`Skip Blender: ${opts.skipBlender}`);
  console.log(`Dry run: ${opts.dryRun}\n`);

  if (opts.smoke) await runSmokeTests(runner);
  if (opts.regression) await runRegressionTests(runner);
  if (opts.quality) await runQualityTests(runner);
  if (opts.performance) await runPerformanceTests(runner);
  if (opts.integration) await runIntegrationTests(runner);

  const summary = runner.summary();

  console.log(`\n=== Results: ${summary.passed} passed, ${summary.failed} failed, ${summary.skipped} skipped (${summary.duration_ms}ms) ===`);
  console.log(`Verdict: ${summary.verdict}\n`);

  // Save report
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  const reportPath = path.join(REPORTS_DIR, 'render-test-suite-latest.json');
  fs.writeFileSync(reportPath, JSON.stringify(summary, null, 2));

  if (opts.jsonOut) {
    fs.writeFileSync(opts.jsonOut, JSON.stringify(summary, null, 2));
  }

  process.exit(summary.failed > 0 ? 1 : 0);
}

main().catch(e => {
  console.error(`Suite error: ${e.message}`);
  process.exit(2);
});
