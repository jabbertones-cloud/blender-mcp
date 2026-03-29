#!/usr/bin/env node

/**
 * Render Quality Scorer — Unified, tiered quality assessment for Blender renders.
 *
 * Tier 1 (FREE, <50ms): Pixel-level metrics via pure Node.js image analysis
 *   - Blank/black render detection
 *   - Histogram spread (contrast)
 *   - Noise estimation (Laplacian variance proxy)
 *   - Edge density (detail detection)
 *   - Brightness/exposure check
 *
 * Tier 2 (≈$0.10, ~3s): Vision LLM semantic scoring via OpenAI
 *   - Overall composition quality
 *   - Lighting assessment
 *   - Material/surface realism
 *   - Artifact detection (fireflies, banding, z-fighting)
 *   - Specific remediation suggestions
 *
 * Usage:
 *   node render-quality-scorer.js --image /path/to/render.png [--tier 1|2|auto] [--json-out path] [--seed SEED]
 *   node render-quality-scorer.js --asset-dir /path/to/exports/3d-forge/<id> [--tier auto] [--seed SEED]
 *   node render-quality-scorer.js --all-exports [--tier 1] [--min-score 50] [--seed SEED]\n *
 * Exit codes:
 *   0 = scored successfully
 *   1 = image not found or unreadable
 *   2 = scoring failed
 */

'use strict';

const fs = require('fs');
const path = require('path');
const https = require('https');

// Load .env
require('./lib/env').loadEnv();

// ============================================================================
// CONFIG
// ============================================================================

const REPO_ROOT = path.join(__dirname, '..', '..');
const EXPORTS_DIR = path.join(REPO_ROOT, 'exports', '3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');

const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const VISION_MODEL = process.env.RENDER_VISION_MODEL || 'gpt-4o';

// Thresholds (tuned from production data — see SKILL.md)
const BLANK_RENDER_THRESHOLD = 0.02;     // <2% unique pixel values = blank
const LOW_CONTRAST_THRESHOLD = 0.15;     // Histogram spread <15% = washed out
const HIGH_NOISE_THRESHOLD = 0.85;       // Laplacian variance proxy (normalized)
const MIN_EDGE_DENSITY = 0.01;           // <1% edges = likely blank or featureless
const OVEREXPOSED_THRESHOLD = 0.90;      // >90% brightness avg = overexposed
const UNDEREXPOSED_THRESHOLD = 0.10;     // <10% brightness avg = underexposed

// Scoring weights
const TIER1_WEIGHTS = {
  not_blank: 25,            // Is the render not blank/black?
  contrast: 20,             // Does it have good tonal range?
  exposure: 20,             // Is it neither over- nor under-exposed?
  detail: 20,               // Does it have meaningful edge detail?
  noise: 15,                // Is noise within acceptable range?
};

// ============================================================================
// SEEDED PRNG (Mulberry32)
// ============================================================================

/**
 * Mulberry32: Simple, fast, seedable PRNG with good distribution.
 * Returns a function that generates pseudorandom numbers [0, 1).
 */
function createSeededPRNG(seed) {
  return function() {
    seed |= 0; // coerce to int32
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ============================================================================
// CLI
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    image: null,
    assetDir: null,
    allExports: false,
    tier: 'auto',
    jsonOut: null,
    minScore: null,
    verbose: false,
    dryRun: false,
    seed: null,  // New: optional seed override
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--image': opts.image = args[++i]; break;
      case '--asset-dir': opts.assetDir = args[++i]; break;
      case '--all-exports': opts.allExports = true; break;
      case '--tier': opts.tier = args[++i]; break;
      case '--json-out': opts.jsonOut = args[++i]; break;
      case '--min-score': opts.minScore = parseFloat(args[++i]); break;
      case '--seed': opts.seed = parseInt(args[++i], 10); break;
      case '--verbose': opts.verbose = true; break;
      case '--dry-run': opts.dryRun = true; break;
    }
  }

  return opts;
}

const log = (msg, level = 'INFO') => {
  console.log(`[${new Date().toISOString()}] [scorer:${level.toLowerCase()}] ${msg}`);
};

// ============================================================================
// TIER 1: PIXEL-LEVEL METRICS (pure Node.js, no external deps)
// ============================================================================

/**
 * Read a PNG file and extract raw RGBA pixel data.
 * Minimal PNG decoder — handles IHDR + IDAT with zlib inflate.
 */
function readPngPixels(filePath) {
  const buf = fs.readFileSync(filePath);

  // Verify PNG signature
  const PNG_SIG = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (buf.compare(PNG_SIG, 0, 8, 0, 8) !== 0) {
    throw new Error(`Not a valid PNG file: ${filePath}`);
  }

  let width = 0, height = 0, bitDepth = 0, colorType = 0;
  const idatChunks = [];

  let offset = 8;
  while (offset < buf.length) {
    const length = buf.readUInt32BE(offset);
    const type = buf.toString('ascii', offset + 4, offset + 8);
    const data = buf.subarray(offset + 8, offset + 8 + length);

    if (type === 'IHDR') {
      width = data.readUInt32BE(0);
      height = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === 'IDAT') {
      idatChunks.push(data);
    } else if (type === 'IEND') {
      break;
    }

    offset += 12 + length; // 4 (length) + 4 (type) + length + 4 (crc)
  }

  if (!width || !height) throw new Error('Failed to parse PNG IHDR');

  // Inflate IDAT data
  const zlib = require('zlib');
  const compressed = Buffer.concat(idatChunks);
  const inflated = zlib.inflateSync(compressed);

  // Determine bytes per pixel
  const channels = colorType === 6 ? 4 : colorType === 2 ? 3 : colorType === 4 ? 2 : 1;
  const bpp = channels * (bitDepth / 8);
  const rowBytes = Math.ceil(width * bpp);

  // Unfilter rows (simplified — handles None, Sub, Up, Average, Paeth)
  const pixels = Buffer.alloc(width * height * channels);
  let prevRow = Buffer.alloc(rowBytes);

  for (let y = 0; y < height; y++) {
    const filterType = inflated[y * (rowBytes + 1)];
    const rawRow = inflated.subarray(y * (rowBytes + 1) + 1, y * (rowBytes + 1) + 1 + rowBytes);
    const unfilteredRow = Buffer.alloc(rowBytes);

    for (let x = 0; x < rowBytes; x++) {
      const a = x >= bpp ? unfilteredRow[x - bpp] : 0;
      const b = prevRow[x];
      const c = x >= bpp ? prevRow[x - bpp] : 0;

      let val = rawRow[x];
      switch (filterType) {
        case 0: break; // None
        case 1: val = (val + a) & 0xFF; break; // Sub
        case 2: val = (val + b) & 0xFF; break; // Up
        case 3: val = (val + Math.floor((a + b) / 2)) & 0xFF; break; // Average
        case 4: { // Paeth
          const p = a + b - c;
          const pa = Math.abs(p - a);
          const pb = Math.abs(p - b);
          const pc = Math.abs(p - c);
          val = (val + (pa <= pb && pa <= pc ? a : pb <= pc ? b : c)) & 0xFF;
          break;
        }
      }
      unfilteredRow[x] = val;
    }

    unfilteredRow.copy(pixels, y * rowBytes, 0, rowBytes);
    prevRow = unfilteredRow;
  }

  return { width, height, channels, pixels };
}

/**
 * Compute luminance histogram from pixel data (256 bins).
 */
function computeLuminanceHistogram(imgData) {
  const { width, height, channels, pixels } = imgData;
  const histogram = new Uint32Array(256);
  const totalPixels = width * height;

  for (let i = 0; i < totalPixels; i++) {
    const offset = i * channels;
    const r = pixels[offset];
    const g = channels >= 3 ? pixels[offset + 1] : r;
    const b = channels >= 3 ? pixels[offset + 2] : r;
    // ITU-R BT.709 luminance
    const lum = Math.round(0.2126 * r + 0.7152 * g + 0.0722 * b);
    histogram[Math.min(255, Math.max(0, lum))]++;
  }

  return { histogram, totalPixels };
}

/**
 * Tier 1 scoring — all checks, returns normalized 0-100 score + breakdown.
 * NOW DETERMINISTIC: Uses seeded PRNG for patch sampling and consistent sampleStep.
 */
function scoreTier1(imagePath, seed = null) {
  const startTime = Date.now();

  let imgData;
  try {
    imgData = readPngPixels(imagePath);
  } catch (e) {
    // Fallback: try to get basic file info
    return {
      tier: 1,
      score: 0,
      verdict: 'ERROR',
      error: `Failed to read PNG: ${e.message}`,
      duration_ms: Date.now() - startTime,
      checks: {},
    };
  }

  const { histogram, totalPixels } = computeLuminanceHistogram(imgData);
  const { width, height, channels, pixels } = imgData;

  // ---- DETERMINISTIC SEED: Use image dimensions or override ----
  const autoSeed = width * height * 31337;
  const useSeed = seed !== null ? seed : autoSeed;
  const prng = createSeededPRNG(useSeed);

  // ---- Check 1: Blank/Black render detection ----
  const nonZeroBins = histogram.filter(v => v > 0).length;
  const uniqueRatio = nonZeroBins / 256;
  const isBlank = uniqueRatio < BLANK_RENDER_THRESHOLD;
  const blankScore = isBlank ? 0 : Math.min(1, uniqueRatio / 0.3); // Scale: 0-30% → 0-1

  // ---- Check 2: Contrast (histogram spread) ----
  let minBin = 255, maxBin = 0;
  for (let i = 0; i < 256; i++) {
    if (histogram[i] > 0) {
      minBin = Math.min(minBin, i);
      maxBin = Math.max(maxBin, i);
    }
  }
  const histogramSpread = (maxBin - minBin) / 255;
  const isLowContrast = histogramSpread < LOW_CONTRAST_THRESHOLD;
  const contrastScore = Math.min(1, histogramSpread / 0.7); // Scale: 0-70% → 0-1

  // ---- Check 3: Exposure ----
  let lumSum = 0;
  for (let i = 0; i < 256; i++) lumSum += i * histogram[i];
  const avgBrightness = lumSum / totalPixels / 255;
  const isOverexposed = avgBrightness > OVEREXPOSED_THRESHOLD;
  const isUnderexposed = avgBrightness < UNDEREXPOSED_THRESHOLD;
  // Best exposure is around 0.4-0.6 (18% gray maps to ~0.46 in linear)
  const exposureDeviation = Math.abs(avgBrightness - 0.45);
  const exposureScore = Math.max(0, 1 - exposureDeviation * 2.5);

  // ---- Check 4: Detail/Edge density (simplified Sobel-like) ----
  // FIXED: sampleStep now calculated consistently from image dimensions
  let edgePixels = 0;
  const sampleStep = Math.max(1, Math.ceil(Math.sqrt(totalPixels / 50000))); // Deterministic: uses total pixels
  for (let y = 1; y < height - 1; y += sampleStep) {
    for (let x = 1; x < width - 1; x += sampleStep) {
      const idx = (y * width + x) * channels;
      const idxLeft = (y * width + (x - 1)) * channels;
      const idxRight = (y * width + (x + 1)) * channels;
      const idxUp = ((y - 1) * width + x) * channels;
      const idxDown = ((y + 1) * width + x) * channels;

      const gx = Math.abs(pixels[idxRight] - pixels[idxLeft]);
      const gy = Math.abs(pixels[idxDown] - pixels[idxUp]);
      const gradient = Math.sqrt(gx * gx + gy * gy);

      if (gradient > 20) edgePixels++;
    }
  }
  const sampledPixels = Math.ceil((height - 2) / sampleStep) * Math.ceil((width - 2) / sampleStep);
  const edgeDensity = sampledPixels > 0 ? edgePixels / sampledPixels : 0;
  const detailScore = Math.min(1, edgeDensity / 0.15); // Scale: 0-15% edges → 0-1

  // ---- Check 5: Noise estimation (local variance) ----
  // NOW DETERMINISTIC: Uses seeded PRNG for patch position selection
  // Also increased patchSampleCount from 50 to 100 to reduce sampling variance
  let patchVariances = [];
  const patchSize = 8;
  const patchSampleCount = Math.min(100, Math.floor(width / patchSize) * Math.floor(height / patchSize));
  for (let p = 0; p < patchSampleCount; p++) {
    // Use seeded PRNG instead of Math.random()
    const px = Math.floor(prng() * (width - patchSize));
    const py = Math.floor(prng() * (height - patchSize));
    let sum = 0, sumSq = 0, count = 0;
    for (let dy = 0; dy < patchSize; dy++) {
      for (let dx = 0; dx < patchSize; dx++) {
        const idx = ((py + dy) * width + (px + dx)) * channels;
        const lum = 0.2126 * pixels[idx] + 0.7152 * (channels >= 3 ? pixels[idx + 1] : pixels[idx]) + 0.0722 * (channels >= 3 ? pixels[idx + 2] : pixels[idx]);
        sum += lum;
        sumSq += lum * lum;
        count++;
      }
    }
    const mean = sum / count;
    const variance = sumSq / count - mean * mean;
    patchVariances.push(variance);
  }
  // High median variance with low variation across patches = uniform noise
  patchVariances.sort((a, b) => a - b);
  const medianVariance = patchVariances[Math.floor(patchVariances.length / 2)] || 0;
  const normalizedNoise = Math.min(1, medianVariance / 2000);
  const noiseScore = 1 - Math.max(0, (normalizedNoise - 0.3) / 0.7); // Penalty above 30% noise

  // ---- Composite score ----
  const weightedScore =
    blankScore * TIER1_WEIGHTS.not_blank +
    contrastScore * TIER1_WEIGHTS.contrast +
    exposureScore * TIER1_WEIGHTS.exposure +
    detailScore * TIER1_WEIGHTS.detail +
    noiseScore * TIER1_WEIGHTS.noise;

  const totalWeight = Object.values(TIER1_WEIGHTS).reduce((a, b) => a + b, 0);
  const finalScore = Math.round(weightedScore / totalWeight * 100);

  // Determine verdict
  let verdict = 'PASS';
  if (finalScore < 30) verdict = 'REJECT';
  else if (finalScore < 60) verdict = 'NEEDS_IMPROVEMENT';
  else if (finalScore < 80) verdict = 'ACCEPTABLE';

  // Build issues list
  const issues = [];
  if (isBlank) issues.push({ id: 'blank_render', severity: 'critical', message: 'Render appears blank or nearly blank', fix: 'Check camera framing, lighting, and object visibility' });
  if (isLowContrast) issues.push({ id: 'low_contrast', severity: 'high', message: `Histogram spread only ${(histogramSpread * 100).toFixed(1)}%`, fix: 'Increase light energy differential (key vs fill), adjust world background' });
  if (isOverexposed) issues.push({ id: 'overexposed', severity: 'high', message: `Average brightness ${(avgBrightness * 100).toFixed(1)}% — overexposed`, fix: 'Reduce light energy, change background from white to gray (0.18)' });
  if (isUnderexposed) issues.push({ id: 'underexposed', severity: 'high', message: `Average brightness ${(avgBrightness * 100).toFixed(1)}% — underexposed`, fix: 'Increase light energy (500W key, 200W fill, 300W rim)' });
  if (edgeDensity < MIN_EDGE_DENSITY) issues.push({ id: 'no_detail', severity: 'high', message: 'No meaningful edge detail detected', fix: 'Check model is in camera view, check subdivision applied, check material assignment' });
  if (normalizedNoise > HIGH_NOISE_THRESHOLD) issues.push({ id: 'high_noise', severity: 'medium', message: 'Excessive noise detected', fix: 'Increase render samples or enable denoiser' });

  return {
    tier: 1,
    score: finalScore,
    verdict,
    duration_ms: Date.now() - startTime,
    image: path.basename(imagePath),
    dimensions: { width, height },
    seed: useSeed,  // Track which seed was used
    checks: {
      blank: { passed: !isBlank, score: Math.round(blankScore * 100), unique_ratio: Number(uniqueRatio.toFixed(4)) },
      contrast: { passed: !isLowContrast, score: Math.round(contrastScore * 100), histogram_spread: Number(histogramSpread.toFixed(4)) },
      exposure: { passed: !isOverexposed && !isUnderexposed, score: Math.round(exposureScore * 100), avg_brightness: Number(avgBrightness.toFixed(4)) },
      detail: { passed: edgeDensity >= MIN_EDGE_DENSITY, score: Math.round(detailScore * 100), edge_density: Number(edgeDensity.toFixed(4)) },
      noise: { passed: normalizedNoise <= HIGH_NOISE_THRESHOLD, score: Math.round(noiseScore * 100), normalized_noise: Number(normalizedNoise.toFixed(4)) },
    },
    issues,
  };
}

// ============================================================================
// TIER 2: VISION LLM SEMANTIC SCORING
// ============================================================================

/**
 * Score a render using OpenAI Vision API.
 * Returns structured assessment with score, issues, and fix suggestions.
 */
async function scoreTier2(imagePath) {
  const startTime = Date.now();

  if (!OPENAI_API_KEY) {
    return {
      tier: 2,
      score: null,
      verdict: 'SKIPPED',
      error: 'OPENAI_API_KEY not set',
      duration_ms: Date.now() - startTime,
    };
  }

  const imageData = fs.readFileSync(imagePath);
  const base64 = imageData.toString('base64');
  const mimeType = imagePath.endsWith('.png') ? 'image/png' : 'image/jpeg';

  const prompt = `You are a 3D render quality assessor for a forensic animation studio. Score this Blender render on a 0-100 scale.

Evaluate these dimensions (each 0-20):
1. **Composition & Framing**: Is the subject well-framed? Is there a clear focal point?
2. **Lighting Quality**: Is lighting balanced? Studio three-point? No blown highlights or crushed shadows?
3. **Material/Surface Quality**: Do materials look realistic? Any obvious placeholder or default materials?
4. **Technical Quality**: No fireflies, banding, z-fighting, noise, or rendering artifacts?
5. **Overall Impression**: Would this be acceptable for a forensic animation client presentation?

Respond in EXACTLY this JSON format (no markdown, no code fences):
{
  "score": <0-100>,
  "composition": <0-20>,
  "lighting": <0-20>,
  "materials": <0-20>,
  "technical": <0-20>,
  "impression": <0-20>,
  "verdict": "PASS|ACCEPTABLE|NEEDS_IMPROVEMENT|REJECT",
  "issues": [{"id": "<short_id>", "severity": "critical|high|medium|low", "message": "<description>"}],
  "suggested_fixes": [{"fix_id": "<short_id>", "description": "<what to change>", "parameter": "<blender_param_if_applicable>", "value": "<suggested_value>"}]
}`;

  const body = JSON.stringify({
    model: VISION_MODEL,
    max_tokens: 1000,
    messages: [{
      role: 'user',
      content: [
        { type: 'text', text: prompt },
        { type: 'image_url', image_url: { url: `data:${mimeType};base64,${base64}`, detail: 'low' } },
      ],
    }],
  });

  try {
    const response = await new Promise((resolve, reject) => {
      const req = https.request({
        hostname: 'api.openai.com',
        port: 443,
        path: '/v1/chat/completions',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${OPENAI_API_KEY}`,
          'Content-Length': Buffer.byteLength(body),
        },
        timeout: 30000,
      }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(new Error(`Failed to parse OpenAI response: ${e.message}`));
          }
        });
      });
      req.on('error', reject);
      req.on('timeout', () => { req.destroy(); reject(new Error('OpenAI request timeout')); });
      req.write(body);
      req.end();
    });

    if (response.error) {
      throw new Error(`OpenAI API error: ${response.error.message}`);
    }

    const content = response.choices?.[0]?.message?.content || '';
    // Extract JSON from response (strip markdown fences if present)
    const jsonMatch = content.replace(/```json?\n?/g, '').replace(/```/g, '').trim();
    const assessment = JSON.parse(jsonMatch);

    return {
      tier: 2,
      score: assessment.score,
      verdict: assessment.verdict,
      duration_ms: Date.now() - startTime,
      image: path.basename(imagePath),
      dimensions: {
        composition: assessment.composition,
        lighting: assessment.lighting,
        materials: assessment.materials,
        technical: assessment.technical,
        impression: assessment.impression,
      },
      issues: assessment.issues || [],
      suggested_fixes: assessment.suggested_fixes || [],
      model: VISION_MODEL,
      cost_estimate_usd: 0.10,
    };
  } catch (e) {
    return {
      tier: 2,
      score: null,
      verdict: 'ERROR',
      error: e.message,
      duration_ms: Date.now() - startTime,
    };
  }
}

// ============================================================================
// UNIFIED SCORER
// ============================================================================

/**
 * Score a render image with tiered approach.
 *   tier='1' — Tier 1 only (free, fast)
 *   tier='2' — Tier 2 only (vision LLM)
 *   tier='auto' — Tier 1 first; if score 30-80 (ambiguous), escalate to Tier 2
 */
async function scoreRender(imagePath, tier = 'auto', seed = null) {
  const result = {
    image: imagePath,
    timestamp: new Date().toISOString(),
    tier1: null,
    tier2: null,
    final_score: null,
    final_verdict: null,
    all_issues: [],
    all_fixes: [],
  };

  // Always run Tier 1 (it's free and fast)
  if (tier === '1' || tier === '2' || tier === 'auto') {
    result.tier1 = scoreTier1(imagePath, seed);
    log(`Tier 1: score=${result.tier1.score}, verdict=${result.tier1.verdict}, ${result.tier1.duration_ms}ms`);
    result.all_issues.push(...(result.tier1.issues || []));
  }

  // Run Tier 2 if requested or if Tier 1 is ambiguous
  const shouldEscalate = tier === '2' || (
    tier === 'auto' &&
    result.tier1 &&
    result.tier1.score >= 30 &&
    result.tier1.score < 80
  );

  if (shouldEscalate) {
    result.tier2 = await scoreTier2(imagePath);
    log(`Tier 2: score=${result.tier2.score}, verdict=${result.tier2.verdict}, ${result.tier2.duration_ms}ms`);
    result.all_issues.push(...(result.tier2.issues || []));
    result.all_fixes.push(...(result.tier2.suggested_fixes || []));
  }

  // Determine final score
  if (result.tier2 && result.tier2.score !== null) {
    // Blend: 30% Tier 1 (objective) + 70% Tier 2 (semantic)
    result.final_score = Math.round(result.tier1.score * 0.3 + result.tier2.score * 0.7);
    result.final_verdict = result.tier2.verdict;
  } else if (result.tier1) {
    result.final_score = result.tier1.score;
    result.final_verdict = result.tier1.verdict;
  }

  // Deduplicate issues by id
  const seenIds = new Set();
  result.all_issues = result.all_issues.filter(issue => {
    if (seenIds.has(issue.id)) return false;
    seenIds.add(issue.id);
    return true;
  });

  return result;
}

// ============================================================================
// ASSET DIRECTORY SCORER
// ============================================================================

/**
 * Score all renders in an asset export directory.
 * Looks for render.png, thumbnail.png, hero_render.png, etc.
 */
async function scoreAssetDir(assetDir, tier = 'auto', seed = null) {
  const renderFiles = fs.readdirSync(assetDir)
    .filter(f => /\.(png|jpg|jpeg)$/i.test(f))
    .filter(f => /render|thumbnail|hero|preview/i.test(f));

  if (renderFiles.length === 0) {
    return { asset_dir: assetDir, error: 'No render images found', renders: [] };
  }

  const results = [];
  for (const file of renderFiles) {
    const result = await scoreRender(path.join(assetDir, file), tier, seed);
    results.push(result);
  }

  // Aggregate: use the primary render (render.png) or best score
  const primary = results.find(r => /^render\./i.test(path.basename(r.image))) || results[0];

  return {
    asset_dir: assetDir,
    asset_id: path.basename(assetDir),
    primary_score: primary.final_score,
    primary_verdict: primary.final_verdict,
    render_count: results.length,
    renders: results,
    all_issues: results.flatMap(r => r.all_issues),
    all_fixes: results.flatMap(r => r.all_fixes),
  };
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const opts = parseArgs();

  if (opts.image) {
    // Score a single image
    if (!fs.existsSync(opts.image)) {
      log(`Image not found: ${opts.image}`, 'ERROR');
      process.exit(1);
    }
    const result = await scoreRender(opts.image, opts.tier, opts.seed);
    const output = JSON.stringify(result, null, 2);
    console.log(output);
    if (opts.jsonOut) fs.writeFileSync(opts.jsonOut, output);
    process.exit(result.final_verdict === 'REJECT' ? 2 : 0);

  } else if (opts.assetDir) {
    // Score all renders in an asset directory
    if (!fs.existsSync(opts.assetDir)) {
      log(`Asset directory not found: ${opts.assetDir}`, 'ERROR');
      process.exit(1);
    }
    const result = await scoreAssetDir(opts.assetDir, opts.tier, opts.seed);
    const output = JSON.stringify(result, null, 2);
    console.log(output);
    if (opts.jsonOut) fs.writeFileSync(opts.jsonOut, output);

  } else if (opts.allExports) {
    // Score all exported assets
    if (!fs.existsSync(EXPORTS_DIR)) {
      log(`Exports directory not found: ${EXPORTS_DIR}`, 'ERROR');
      process.exit(1);
    }

    const subdirs = fs.readdirSync(EXPORTS_DIR).filter(d => {
      try { return fs.statSync(path.join(EXPORTS_DIR, d)).isDirectory(); } catch { return false; }
    });

    const summary = {
      timestamp: new Date().toISOString(),
      total_assets: subdirs.length,
      scored: 0,
      passed: 0,
      needs_improvement: 0,
      rejected: 0,
      avg_score: 0,
      assets: [],
    };

    let scoreSum = 0;

    for (const dir of subdirs) {
      const assetPath = path.join(EXPORTS_DIR, dir);
      try {
        const result = await scoreAssetDir(assetPath, opts.tier, opts.seed);
        if (result.primary_score !== null && result.primary_score !== undefined) {
          summary.scored++;
          scoreSum += result.primary_score;
          if (result.primary_verdict === 'PASS' || result.primary_verdict === 'ACCEPTABLE') summary.passed++;
          else if (result.primary_verdict === 'NEEDS_IMPROVEMENT') summary.needs_improvement++;
          else if (result.primary_verdict === 'REJECT') summary.rejected++;

          if (opts.minScore && result.primary_score < opts.minScore) {
            log(`BELOW THRESHOLD: ${dir} scored ${result.primary_score} (min: ${opts.minScore})`);
          }
        }
        summary.assets.push({
          id: dir,
          score: result.primary_score,
          verdict: result.primary_verdict,
          issues_count: result.all_issues?.length || 0,
        });
      } catch (e) {
        log(`Failed to score ${dir}: ${e.message}`, 'WARN');
        summary.assets.push({ id: dir, score: null, verdict: 'ERROR', error: e.message });
      }
    }

    summary.avg_score = summary.scored > 0 ? Math.round(scoreSum / summary.scored) : 0;

    const output = JSON.stringify(summary, null, 2);
    console.log(output);

    // Save report
    const reportPath = path.join(REPORTS_DIR, 'render-quality-latest.json');
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
    fs.writeFileSync(reportPath, output);
    log(`Report saved: ${reportPath}`);

    if (opts.jsonOut) fs.writeFileSync(opts.jsonOut, output);

  } else {
    console.log('Usage:');
    console.log('  node render-quality-scorer.js --image /path/to/render.png [--tier 1|2|auto] [--seed SEED]');
    console.log('  node render-quality-scorer.js --asset-dir /path/to/exports/3d-forge/<id> [--tier auto] [--seed SEED]');
    console.log('  node render-quality-scorer.js --all-exports [--tier 1] [--min-score 50] [--seed SEED]');
    process.exit(1);
  }
}

// Export for use by other scripts (render-improvement-loop.js)
module.exports = { scoreRender, scoreTier1, scoreTier2, scoreAssetDir };

// Only run main() when executed directly (not when required as a module)
if (require.main === module) {
  main().catch(e => {
    log(`Fatal: ${e.message}`, 'ERROR');
    process.exit(2);
  });
}
