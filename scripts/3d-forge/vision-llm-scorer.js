#!/usr/bin/env node

/**
 * Vision LLM Scorer - Claude-powered forensic render quality assessment
 * 
 * Uses Claude's vision capabilities to score renders against the 3-track
 * audit rubric (FC/PP/CP) without relying on pixel-level metrics.
 * 
 * Usage:
 *   node vision-llm-scorer.js --image renders/scene1_BirdEye.png --scene-type t-bone
 *   node vision-llm-scorer.js --image renders/scene4_SecurityCam.png --scene-type parking-lot-night
 *   node vision-llm-scorer.js --batch renders/v22_final/ --tier auto
 *
 * Exit codes:
 *   0 = scored successfully
 *   1 = image not found or unreadable
 *   2 = scoring failed
 *   3 = API error
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// ============================================================================
// CONFIG & CONSTANTS
// ============================================================================

const REPO_ROOT = path.join(__dirname, '..', '..');
const CONFIG_DIR = path.join(REPO_ROOT, 'config');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const AUDIT_TRACKS_FILE = path.join(CONFIG_DIR, 'audit-tracks.json');

// Load .env file from project root (no dotenv dependency needed)
(function loadEnv() {
  const envPath = path.join(REPO_ROOT, '.env');
  try {
    const envContent = fs.readFileSync(envPath, 'utf-8');
    for (const line of envContent.split('\n')) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) continue;
      const eqIdx = trimmed.indexOf('=');
      if (eqIdx === -1) continue;
      const key = trimmed.slice(0, eqIdx).trim();
      const val = trimmed.slice(eqIdx + 1).trim();
      // Only set if not already in environment (env vars take precedence)
      if (!process.env[key] && val) {
        process.env[key] = val;
      }
    }
  } catch (e) {
    // .env file is optional
  }
})();

// Scene type descriptions for prompt context
const SCENE_DESCRIPTIONS = {
  't-bone': 'T-Bone collision at intersection (Smith v. Johnson). Two vehicles, impact point, daylight.',
  'pedestrian': 'Pedestrian struck in crosswalk. Vehicle, pedestrian figure, sight lines, daylight.',
  'highway': 'Highway rear-end collision. Truck rear-ending car, speed context, daylight.',
  'parking-lot-night': 'Parking lot hit-and-run. Night scene, security camera angle, artificial lighting.'
};

// Scene type auto-detection from filename
const SCENE_AUTO_DETECT = {
  'scene1': 't-bone',
  'scene2': 'pedestrian',
  'scene3': 'highway',
  'scene4': 'parking-lot-night'
};

// Mock scores for fallback (no API key)
const MOCK_SCORE = {
  forensic_clarity: { score: 7.5, issues: ['Example issue 1', 'Example issue 2'], strengths: ['Good marker visibility'] },
  physical_plausibility: { score: 8.0, issues: [], strengths: ['Realistic lighting', 'Accurate materials'] },
  cinematic_presentation: { score: 7.0, issues: ['Could improve composition'], strengths: ['Good color grading'] },
  weighted_score: 7.55,
  top_3_improvements: ['Improve marker contrast', 'Refine lighting consistency', 'Enhance depth composition'],
  courtroom_ready: false,
  confidence: 0.75
};

// ============================================================================
// UTILITIES
// ============================================================================

function log(msg, level = 'info') {
  const ts = new Date().toISOString();
  const prefix = level.toUpperCase();
  console.error(`[${ts}] [${prefix}] ${msg}`);
}

function logOutput(obj) {
  console.log(JSON.stringify(obj, null, 2));
}

const MAX_BASE64_BYTES = 4800000; // ~3.6MB raw, staying under 5MB API limit

async function readImageAsBase64(imagePath) {
  const data = fs.readFileSync(imagePath);
  let base64 = data.toString('base64');
  
  // If image exceeds API limit, resize it down using macOS sips
  if (base64.length > MAX_BASE64_BYTES) {
    log(`Image too large (${base64.length} base64 chars). Resizing...`, 'info');
    base64 = await resizeAndEncode(imagePath);
  }
  
  return base64;
}

async function resizeAndEncode(imagePath) {
  const { execSync } = require('child_process');
  const os = require('os');
  const tmpDir = os.tmpdir();
  const ext = path.extname(imagePath);
  const tmpPath = path.join(tmpDir, `vision-scorer-tmp-${Date.now()}${ext}`);
  
  try {
    // Copy to temp location
    fs.copyFileSync(imagePath, tmpPath);
    
    // Try progressively smaller sizes until under limit
    const widths = [1920, 1440, 1280, 1024, 800];
    for (const w of widths) {
      try {
        execSync(`sips --resampleWidth ${w} "${tmpPath}" 2>/dev/null`, { stdio: 'pipe' });
      } catch (e) {
        // sips not available (non-macOS), try ImageMagick convert
        try {
          execSync(`convert "${imagePath}" -resize ${w}x "${tmpPath}"`, { stdio: 'pipe' });
        } catch (e2) {
          log(`No image resize tool available. Sending original.`, 'warn');
          return fs.readFileSync(imagePath).toString('base64');
        }
      }
      const resized = fs.readFileSync(tmpPath);
      const b64 = resized.toString('base64');
      if (b64.length <= MAX_BASE64_BYTES) {
        log(`Resized to ${w}px width (${b64.length} base64 chars)`, 'info');
        return b64;
      }
      // Re-copy original for next attempt
      fs.copyFileSync(imagePath, tmpPath);
    }
    
    // Last resort: return whatever we got at smallest size
    const finalData = fs.readFileSync(tmpPath);
    return finalData.toString('base64');
  } finally {
    try { fs.unlinkSync(tmpPath); } catch (e) { /* cleanup */ }
  }
}

function getMediaType(imagePath) {
  const ext = path.extname(imagePath).toLowerCase();
  const mimeTypes = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.webp': 'image/webp'
  };
  return mimeTypes[ext] || 'image/png';
}

function autoDetectSceneType(imagePath) {
  const basename = path.basename(imagePath, path.extname(imagePath)).toLowerCase();
  for (const [prefix, sceneType] of Object.entries(SCENE_AUTO_DETECT)) {
    if (basename.includes(prefix)) {
      return sceneType;
    }
  }
  return 't-bone'; // default
}

function ensureReportsDir() {
  if (!fs.existsSync(REPORTS_DIR)) {
    fs.mkdirSync(REPORTS_DIR, { recursive: true });
  }
}

// ============================================================================
// CLAUDE API INTEGRATION
// ============================================================================

async function callClaudeVision(imageBase64, mediaType, sceneType, apiKey) {
  const startTime = Date.now();
  
  if (!apiKey) {
    log('No ANTHROPIC_API_KEY found. Using mock scores for testing.', 'warn');
    return {
      scores: MOCK_SCORE,
      modelUsed: 'mock-score',
      costEstimate: 0,
      rawResponse: null,
      isMock: true
    };
  }

  const sceneDescription = SCENE_DESCRIPTIONS[sceneType] || SCENE_DESCRIPTIONS['t-bone'];
  
  const systemPrompt = `You are a forensic animation quality auditor evaluating a 3D render for courtroom use. You must score renders on three tracks with specific weights and minimum gates. Your assessments must be rigorous, defensible, and focused on admissibility and expert credibility.`;

  const userPrompt = `You are a forensic animation quality auditor evaluating a 3D render for courtroom use.

Scene type: ${sceneType}
Scene description: ${sceneDescription}

Score this render on three tracks (0-10 each):

TRACK 1: FORENSIC CLARITY (FC) - Weight 40%
- Evidence markers visible and legible?
- Spatial relationships clear (distances, angles)?
- Damage documentation visible?
- Sight lines demonstrated?
- Timeline/sequence understandable?

TRACK 2: PHYSICAL PLAUSIBILITY (PP) - Weight 35%
- Lighting realistic for time of day?
- Materials look physically real (metal, glass, asphalt, rubber)?
- Shadows consistent with light sources?
- Vehicle proportions correct?
- Environment accurate?

TRACK 3: CINEMATIC PRESENTATION (CP) - Weight 25%
- Camera composition effective?
- Color grading appropriate?
- Depth of field used well?
- Motion appears smooth (if applicable)?
- Overall professional polish?

Respond in valid JSON format (no markdown, no code fences):
{
  "forensic_clarity": {"score": N, "issues": [...], "strengths": [...]},
  "physical_plausibility": {"score": N, "issues": [...], "strengths": [...]},
  "cinematic_presentation": {"score": N, "issues": [...], "strengths": [...]},
  "weighted_score": N,
  "top_3_improvements": [...],
  "courtroom_ready": true/false,
  "confidence": 0-1
}`;

  return new Promise((resolve, reject) => {
    const requestBody = {
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      system: systemPrompt,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mediaType,
                data: imageBase64
              }
            },
            {
              type: 'text',
              text: userPrompt
            }
          ]
        }
      ]
    };

    const options = {
      hostname: 'api.anthropic.com',
      path: '/v1/messages',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01'
      }
    };

    const req = require('https').request(options, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode !== 200) {
          log(`Claude API error: ${res.statusCode} - ${data}`, 'error');
          reject(new Error(`Claude API returned ${res.statusCode}`));
          return;
        }

        try {
          const parsed = JSON.parse(data);
          const responseText = parsed.content[0].text;
          
          // Extract JSON from response (handle markdown code fences if present)
          let jsonText = responseText;
          const jsonMatch = responseText.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
          if (jsonMatch) {
            jsonText = jsonMatch[1];
          }
          
          const scores = JSON.parse(jsonText);
          const duration = Date.now() - startTime;
          
          // Estimate cost: ~0.003 USD per 1M input tokens, ~0.015 per 1M output tokens
          const estimatedInputTokens = Math.ceil((imageBase64.length / 4) * 1.3 + 500); // base64 + prompt
          const estimatedOutputTokens = responseText.length / 4;
          const costEstimate = (estimatedInputTokens * 0.000003) + (estimatedOutputTokens * 0.000015);

          resolve({
            scores,
            modelUsed: 'claude-sonnet-4-20250514',
            costEstimate: parseFloat(costEstimate.toFixed(6)),
            rawResponse: responseText,
            isMock: false
          });
        } catch (e) {
          log(`Failed to parse Claude response: ${e.message}`, 'error');
          reject(e);
        }
      });
    });

    req.on('error', (e) => {
      log(`API request failed: ${e.message}`, 'error');
      reject(e);
    });

    req.write(JSON.stringify(requestBody));
    req.end();
  });
}

// ============================================================================
// MAIN SCORING PIPELINE
// ============================================================================

async function scoreImage(imagePath, sceneType = null, apiKey = null) {
  const startTime = Date.now();

  // Resolve to absolute path relative to REPO_ROOT if not already absolute
  if (!path.isAbsolute(imagePath)) {
    imagePath = path.resolve(REPO_ROOT, imagePath);
  }

  // Validate image exists
  if (!fs.existsSync(imagePath)) {
    log(`Image not found: ${imagePath}`, 'error');
    return {
      success: false,
      error: 'Image not found',
      exitCode: 1
    };
  }

  // Auto-detect scene type if not provided
  if (!sceneType) {
    sceneType = autoDetectSceneType(imagePath);
    log(`Auto-detected scene type: ${sceneType}`, 'info');
  }

  if (!SCENE_DESCRIPTIONS[sceneType]) {
    log(`Unknown scene type: ${sceneType}. Using t-bone.`, 'warn');
    sceneType = 't-bone';
  }

  // Read image as base64
  let imageBase64;
  try {
    imageBase64 = await readImageAsBase64(imagePath);
  } catch (e) {
    log(`Failed to read image: ${e.message}`, 'error');
    return {
      success: false,
      error: 'Failed to read image',
      exitCode: 1
    };
  }

  const mediaType = getMediaType(imagePath);
  log(`Image loaded: ${imagePath} (${imageBase64.length} base64 chars, ~${Math.round(imageBase64.length * 3/4)} bytes)`, 'debug');

  // Call Claude API
  let apiResult;
  try {
    apiResult = await callClaudeVision(imageBase64, mediaType, sceneType, apiKey);
  } catch (e) {
    log(`Claude API call failed: ${e.message}`, 'error');
    return {
      success: false,
      error: `API error: ${e.message}`,
      exitCode: 3
    };
  }

  const duration = Date.now() - startTime;

  // Build output structure
  const output = {
    image: imagePath,
    timestamp: new Date().toISOString(),
    scene_type: sceneType,
    vision_scores: {
      forensic_clarity: apiResult.scores.forensic_clarity.score,
      physical_plausibility: apiResult.scores.physical_plausibility.score,
      cinematic_presentation: apiResult.scores.cinematic_presentation.score,
      weighted: apiResult.scores.weighted_score,
      gate_check: {
        FC_pass: apiResult.scores.forensic_clarity.score >= 7.0,
        PP_pass: apiResult.scores.physical_plausibility.score >= 7.0,
        CP_pass: apiResult.scores.cinematic_presentation.score >= 6.5
      }
    },
    issues: [
      ...(apiResult.scores.forensic_clarity.issues || []),
      ...(apiResult.scores.physical_plausibility.issues || []),
      ...(apiResult.scores.cinematic_presentation.issues || [])
    ],
    improvements: apiResult.scores.top_3_improvements || [],
    courtroom_ready: apiResult.scores.courtroom_ready,
    model_used: apiResult.modelUsed,
    cost_estimate_usd: apiResult.costEstimate,
    duration_ms: duration,
    is_mock: apiResult.isMock || false
  };

  return {
    success: true,
    data: output,
    exitCode: 0
  };
}

async function scoreBatch(batchDir, apiKey = null) {
  if (!fs.existsSync(batchDir)) {
    log(`Batch directory not found: ${batchDir}`, 'error');
    return {
      success: false,
      error: 'Batch directory not found',
      exitCode: 1
    };
  }

  const files = fs.readdirSync(batchDir).filter(f => {
    const ext = path.extname(f).toLowerCase();
    return ['.png', '.jpg', '.jpeg', '.gif', '.webp'].includes(ext);
  });

  if (files.length === 0) {
    log(`No images found in: ${batchDir}`, 'warn');
    return {
      success: true,
      data: { images: [], summary: { total: 0, passed: 0, failed: 0 } },
      exitCode: 0
    };
  }

  log(`Found ${files.length} images in batch directory`, 'info');

  const results = [];
  for (const file of files) {
    const fullPath = path.join(batchDir, file);
    log(`Processing: ${file}`, 'info');
    
    const result = await scoreImage(fullPath, null, apiKey);
    
    if (result.success) {
      results.push(result.data);
    } else {
      log(`Skipped ${file}: ${result.error}`, 'warn');
    }
  }

  // Compute summary
  const passedCount = results.filter(r => {
    const allGatesPass = r.vision_scores.gate_check.FC_pass && 
                         r.vision_scores.gate_check.PP_pass && 
                         r.vision_scores.gate_check.CP_pass;
    return allGatesPass && r.vision_scores.weighted >= 8.5;
  }).length;

  const summary = {
    total: results.length,
    passed: passedCount,
    failed: results.length - passedCount,
    avg_weighted: results.length > 0 
      ? (results.reduce((sum, r) => sum + r.vision_scores.weighted, 0) / results.length).toFixed(2)
      : 0,
    timestamp: new Date().toISOString()
  };

  // Write batch report
  ensureReportsDir();
  const reportFilename = `vision-audit-${new Date().toISOString().split('T')[0]}-${Date.now()}.json`;
  const reportPath = path.join(REPORTS_DIR, reportFilename);
  
  fs.writeFileSync(reportPath, JSON.stringify({
    batch_dir: batchDir,
    summary,
    images: results
  }, null, 2));

  log(`Batch report written to: ${reportPath}`, 'info');

  return {
    success: true,
    data: {
      images: results,
      summary,
      report_path: reportPath
    },
    exitCode: 0
  };
}

// ============================================================================
// CLI ARGUMENT PARSING
// ============================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    image: null,
    batch: null,
    sceneType: null,
    tier: 'auto',
    jsonOut: null
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case '--image':
        opts.image = args[++i];
        break;
      case '--batch':
        opts.batch = args[++i];
        break;
      case '--scene-type':
        opts.sceneType = args[++i];
        break;
      case '--tier':
        opts.tier = args[++i];
        break;
      case '--json-out':
        opts.jsonOut = args[++i];
        break;
      case '--help':
      case '-h':
        printHelp();
        process.exit(0);
    }
  }

  return opts;
}

function printHelp() {
  console.log(`
Vision LLM Scorer - Claude-powered forensic render quality assessment

USAGE:
  node vision-llm-scorer.js --image <path> [--scene-type <type>]
  node vision-llm-scorer.js --batch <dir> [--tier auto]

OPTIONS:
  --image <path>        Path to a single render image to score
  --batch <dir>         Directory of images to score as batch
  --scene-type <type>   Scene type: t-bone, pedestrian, highway, parking-lot-night
                        (auto-detected from filename if not provided)
  --json-out <path>     Write JSON output to file instead of stdout
  --help                Show this help message

SCENE TYPES:
  t-bone               T-Bone collision at intersection
  pedestrian           Pedestrian struck in crosswalk
  highway              Highway rear-end collision
  parking-lot-night    Parking lot hit-and-run (night scene)

ENVIRONMENT:
  ANTHROPIC_API_KEY    Claude API key (required for real scores)
  
EXAMPLES:
  node vision-llm-scorer.js --image renders/scene1.png --scene-type t-bone
  node vision-llm-scorer.js --batch renders/v22_final/
  ANTHROPIC_API_KEY=sk-ant-... node vision-llm-scorer.js --image renders/test.png
`);
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  const opts = parseArgs();
  const apiKey = process.env.ANTHROPIC_API_KEY || null;

  if (!opts.image && !opts.batch) {
    log('Error: --image or --batch required', 'error');
    printHelp();
    process.exit(2);
  }

  let result;

  try {
    if (opts.image) {
      result = await scoreImage(opts.image, opts.sceneType, apiKey);
      
      if (result.success) {
        log(`Scoring complete (${result.data.duration_ms}ms)`, 'info');
        if (opts.jsonOut) {
          fs.writeFileSync(opts.jsonOut, JSON.stringify(result.data, null, 2));
          log(`Output written to: ${opts.jsonOut}`, 'info');
        } else {
          logOutput(result.data);
        }
      } else {
        log(`Scoring failed: ${result.error}`, 'error');
      }
    } else if (opts.batch) {
      result = await scoreBatch(opts.batch, apiKey);
      
      if (result.success) {
        log(`Batch complete. Processed ${result.data.summary.total} images`, 'info');
        if (opts.jsonOut) {
          fs.writeFileSync(opts.jsonOut, JSON.stringify(result.data, null, 2));
          log(`Batch output written to: ${opts.jsonOut}`, 'info');
        } else {
          logOutput(result.data);
        }
      } else {
        log(`Batch failed: ${result.error}`, 'error');
      }
    }

    process.exit(result.exitCode);
  } catch (e) {
    log(`Unexpected error: ${e.message}`, 'error');
    process.exit(2);
  }
}

main();
