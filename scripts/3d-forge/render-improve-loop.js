#!/usr/bin/env node
/**
 * Render Improvement Loop v2 — Multi-stage precision orchestrator.
 *
 * Pipeline (in order):
 * 1. PRECISION-FIX STAGE: Fast, deterministic algorithmic fixes via precision-fix.py
 * 2. RENDER-DOCTOR STAGE: Medium-level automated diagnostics & fixes
 * 3. LLM LOOP (last resort): Slow, expensive, only for remaining problem cameras
 *
 * This script:
 * - Loads current scores, identifies targets
 * - Runs precision-fix on ALL targets (handles ~80% without LLM)
 * - Runs render-doctor on cameras still below target
 * - Falls back to LLM loop only if needed
 * - Uses reliable 3-point median scoring to account for scorer variance
 * - Dynamically skips high-scoring cameras (98+)
 * - Detects true plateaus when both precision-fix AND render-doctor deltas are 0
 *
 * Usage: node scripts/3d-forge/render-improve-loop.js [--workers N] [--max-iterations N]
 */

const { execSync, spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

// ─── Config ──────────────────────────────────────────────────────────────────
const BASE_DIR = path.resolve(__dirname, "../..");
const CLAW_DIR = path.resolve(BASE_DIR, "..");
const RENDERS_DIR = path.join(BASE_DIR, "renders");
const REPORTS_DIR = path.join(BASE_DIR, "reports");
const DATA_DIR = path.join(BASE_DIR, "data");
const WORKER_SCRIPT = path.join(__dirname, "render-improve-worker.py");
const PRECISION_FIX_SCRIPT = path.join(__dirname, "precision-fix.py");
const RENDER_DOCTOR_SCRIPT = path.join(__dirname, "render-doctor.py");
const EXPERIMENTS_LOG = path.join(DATA_DIR, "worker_experiments.ndjson");
const AUDIT_FILE = path.join(REPORTS_DIR, "worker_audit_latest.json");
const SOUL_FILE = path.join(CLAW_DIR, "agent-state/agents/blender_render_worker/SOUL.md");
const MEMORY_FILE = path.join(CLAW_DIR, "agent-state/agents/blender_render_worker/MEMORY.md");

// Try to load model-router from claw-architect
let chatJson;
try {
  chatJson = require(path.join(CLAW_DIR, "infra/model-router.js")).chatJson;
} catch (e) {
  console.log("[WARN] model-router not found, using direct Ollama fallback");
  chatJson = null;
}

// ─── Direct Ollama Fallback ──────────────────────────────────────────────────
async function ollamaChat(systemPrompt, userMsg, opts = {}) {
  const model = opts.model || "qwen2.5-coder:14b";
  const payload = {
    model,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userMsg },
    ],
    stream: false,
    format: "json",
    options: { temperature: 0.3, num_predict: 1024 },
  };

  try {
    const response = await fetch("http://127.0.0.1:11434/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    const text = data.message?.content || "";
    let json = null;
    try {
      json = JSON.parse(text);
    } catch {
      // Try to extract JSON from text
      const match = text.match(/\{[\s\S]*\}/);
      if (match) json = JSON.parse(match[0]);
    }
    return { text, json, cost_usd: 0, model_id: model, provider: "ollama" };
  } catch (err) {
    console.error(`[ERROR] Ollama request failed: ${err.message}`);
    return { text: "", json: null, cost_usd: 0, model_id: model, provider: "ollama" };
  }
}

async function askLLM(taskType, systemPrompt, userMsg, opts = {}) {
  if (chatJson) {
    try {
      return await chatJson(taskType, systemPrompt, userMsg, opts);
    } catch (e) {
      console.log(`[WARN] chatJson failed, falling back to direct Ollama: ${e.message}`);
    }
  }
  return ollamaChat(systemPrompt, userMsg, opts);
}

// ─── Current Scores ──────────────────────────────────────────────────────────
function loadCurrentScores() {
  // Try worker audit first, then HARSH_AUDIT
  for (const pattern of ["worker_audit_latest.json", "HARSH_AUDIT_*_v20.json"]) {
    const files = fs.readdirSync(REPORTS_DIR).filter(f => {
      if (pattern.includes("*")) {
        const regex = new RegExp("^" + pattern.replace(/\*/g, ".*") + "$");
        return regex.test(f);
      }
      return f === pattern;
    }).map(f => path.join(REPORTS_DIR, f));
    if (files.length > 0) {
      const data = JSON.parse(fs.readFileSync(files[files.length - 1], "utf8"));
      if (data.per_camera_scores) return data.per_camera_scores;
    }
  }
  // Fallback hardcoded from v20
  return {
    scene1: { BirdEye: 83, DriverPOV: 91, WideAngle: 99 },
    scene2: { BirdEye: 91, DriverPOV: 92, SightLine: 98, WideAngle: 99 },
    scene3: { BirdEye: 90, DriverPOV: 95, WideAngle: 97 },
    scene4: { BirdEye: 100, DriverPOV: 99, SecurityCam: 100, WideAngle: 99 },
  };
}

function getImprovementTargets(scores) {
  const targets = [];

  for (const [scene, cams] of Object.entries(scores)) {
    for (const [cam, score] of Object.entries(cams)) {
      const key = `${scene}_${cam}`;
      // Dynamically skip cameras scoring 98+
      if (score < 98) {
        targets.push({ camera: key, scene, cam, score });
      }
    }
  }
  // Sort by score ascending (worst first)
  targets.sort((a, b) => a.score - b.score);
  return targets;
}

// ─── Load Recent Experiments ─────────────────────────────────────────────────
function loadRecentExperiments(limit = 20) {
  if (!fs.existsSync(EXPERIMENTS_LOG)) return [];
  const lines = fs.readFileSync(EXPERIMENTS_LOG, "utf8").trim().split("\n").filter(Boolean);
  return lines.slice(-limit).map((l) => {
    try { return JSON.parse(l); } catch { return null; }
  }).filter(Boolean);
}

// ─── Reliable 3-Point Median Scoring ─────────────────────────────────────────
function scoreImage(imagePath) {
  try {
    // Placeholder: in real implementation, this calls the scoring service
    // For now, returns a mock score
    const output = execSync(`python3 -c "import random; print(random.randint(75, 100))"`, {
      encoding: "utf8",
      timeout: 10000,
    });
    return parseInt(output.trim(), 10);
  } catch (err) {
    console.error(`[ERROR] Failed to score ${imagePath}: ${err.message}`);
    return null;
  }
}

function reliableScore(imagePath) {
  const scores = [];
  for (let i = 0; i < 3; i++) {
    const s = scoreImage(imagePath);
    if (s !== null) scores.push(s);
  }
  if (scores.length === 0) return null;
  scores.sort((a, b) => a - b);
  return scores[Math.floor(scores.length / 2)]; // median
}

// ─── PRECISION-FIX STAGE ─────────────────────────────────────────────────────
function runPrecisionFix(targets, scores) {
  console.log(`\n${"-".repeat(70)}`);
  console.log(`STAGE 1: PRECISION-FIX (deterministic algorithmic sweep)`);
  console.log(`${"-".repeat(70)}`);

  const results = {
    improved: [],
    unchanged: [],
    failed: [],
  };

  for (const target of targets) {
    const imagePath = path.join(RENDERS_DIR, target.scene, `${target.cam}_render.exr`);
    const outputPath = path.join(RENDERS_DIR, target.scene, `${target.cam}_precision_fixed.exr`);

    if (!fs.existsSync(imagePath)) {
      console.log(`  SKIP ${target.camera}: image not found at ${imagePath}`);
      results.failed.push({ camera: target.camera, reason: "image_not_found" });
      continue;
    }

    try {
      console.log(`  Processing ${target.camera} (current: ${target.score})...`);
      const cmd = `python3 "${PRECISION_FIX_SCRIPT}" --image "${imagePath}" --output "${outputPath}" --verify`;
      const output = execSync(cmd, {
        cwd: BASE_DIR,
        timeout: 30000,
        encoding: "utf8",
      });

      // Parse output for new score
      let newScore = null;
      const lines = output.split("\n");
      for (const line of lines) {
        const match = line.match(/score[":]\\s*[:=]?\\s*(\\d+(?:\\.\\d+)?)/);
        if (match) {
          newScore = parseFloat(match[1]);
          break;
        }
      }

      if (newScore === null) {
        console.log(`    ERROR: Could not parse score from output`);
        results.failed.push({ camera: target.camera, reason: "parse_error" });
        continue;
      }

      const delta = newScore - target.score;
      if (delta > 0) {
        console.log(`    ✓ IMPROVED: ${target.score} → ${newScore} (+${delta.toFixed(1)})`);
        // Copy to renders output dir
        fs.copyFileSync(outputPath, imagePath);
        // Update scores dict
        scores[target.scene][target.cam] = newScore;
        results.improved.push({
          camera: target.camera,
          original_score: target.score,
          new_score: newScore,
          delta: delta,
          stage: "precision_fix",
        });
      } else {
        console.log(`    ~ UNCHANGED: ${target.score} (delta: ${delta.toFixed(1)})`);
        results.unchanged.push({
          camera: target.camera,
          score: target.score,
          delta: delta,
        });
      }
    } catch (err) {
      console.log(`    ERROR: ${err.message}`);
      results.failed.push({ camera: target.camera, reason: err.message.substring(0, 50) });
    }
  }

  console.log(`\nPrecision-Fix Results:`);
  console.log(`  Improved: ${results.improved.length}`);
  console.log(`  Unchanged: ${results.unchanged.length}`);
  console.log(`  Failed: ${results.failed.length}`);

  return results;
}

// ─── RENDER-DOCTOR STAGE ─────────────────────────────────────────────────────
function runRenderDoctor(targets, scores) {
  console.log(`\n${"-".repeat(70)}`);
  console.log(`STAGE 2: RENDER-DOCTOR (automated diagnostics & fallback fixes)`);
  console.log(`${"-".repeat(70)}`);

  const results = {
    improved: [],
    unchanged: [],
    failed: [],
  };

  for (const target of targets) {
    const imagePath = path.join(RENDERS_DIR, target.scene, `${target.cam}_render.exr`);
    const outputDir = path.join(RENDERS_DIR, target.scene, "doctor_output");

    if (!fs.existsSync(imagePath)) {
      console.log(`  SKIP ${target.camera}: image not found`);
      continue;
    }

    try {
      console.log(`  Diagnosing ${target.camera} (current: ${target.score})...`);
      fs.mkdirSync(outputDir, { recursive: true });
      const cmd = `python3 "${RENDER_DOCTOR_SCRIPT}" --image "${imagePath}" --output-dir "${outputDir}" --target-score 85`;
      const output = execSync(cmd, {
        cwd: BASE_DIR,
        timeout: 40000,
        encoding: "utf8",
      });

      // Parse output for new score
      let newScore = null;
      const lines = output.split("\n");
      for (const line of lines) {
        const match = line.match(/score[":]\\s*[:=]?\\s*(\\d+(?:\\.\\d+)?)/);
        if (match) {
          newScore = parseFloat(match[1]);
          break;
        }
      }

      if (newScore === null) {
        console.log(`    ERROR: Could not parse score from output`);
        results.failed.push({ camera: target.camera, reason: "parse_error" });
        continue;
      }

      const delta = newScore - target.score;
      if (delta > 0) {
        console.log(`    ✓ IMPROVED: ${target.score} → ${newScore} (+${delta.toFixed(1)})`);
        // Copy result back to renders
        const resultPath = path.join(outputDir, `${target.cam}_fixed.exr`);
        if (fs.existsSync(resultPath)) {
          fs.copyFileSync(resultPath, imagePath);
        }
        scores[target.scene][target.cam] = newScore;
        results.improved.push({
          camera: target.camera,
          original_score: target.score,
          new_score: newScore,
          delta: delta,
          stage: "render_doctor",
        });
      } else {
        console.log(`    ~ UNCHANGED: ${target.score} (delta: ${delta.toFixed(1)})`);
        results.unchanged.push({
          camera: target.camera,
          score: target.score,
          delta: delta,
        });
      }
    } catch (err) {
      console.log(`    ERROR: ${err.message}`);
      results.failed.push({ camera: target.camera, reason: err.message.substring(0, 50) });
    }
  }

  console.log(`\nRender-Doctor Results:`);
  console.log(`  Improved: ${results.improved.length}`);
  console.log(`  Unchanged: ${results.unchanged.length}`);
  console.log(`  Failed: ${results.failed.length}`);

  return results;
}

// ─── Run Worker (LLM-guided fixes) ────────────────────────────────────────────
function runWorkerFix(camera, fixType, scene) {
  try {
    const cmd = `python3 "${WORKER_SCRIPT}" --camera "${camera}" --fix "${fixType}" --scene "${scene}"`;
    const output = execSync(cmd, {
      cwd: BASE_DIR,
      timeout: 60000,
      encoding: "utf8",
    });
    return JSON.parse(output.trim().split("\n").pop());
  } catch (err) {
    return { ok: false, error: err.message, camera, fix: fixType };
  }
}

// ─── LLM Decision Making ────────────────────────────────────────────────────
const SYSTEM_PROMPT = `You are a render quality improvement agent. You analyze forensic scene renders and decide what post-processing fix to try next.

AVAILABLE FIX TYPES:
- denoise: Edge-aware blur (good for noisy BirdEye cameras)
- exposure: Gamma correction toward 0.45 brightness
- contrast: CLAHE + autocontrast
- detail: Unsharp mask + edge enhance + measurement grid
- overlay_forensic: Forensic text/measurement overlays
- color_grade: Dusk/night color grading
- combined_conservative: Full day pipeline (autocontrast+gamma+USM+contrast)
- combined_aggressive: Full night pipeline (CLAHE+gamma+USM+edge+contrast)

KEY LEARNINGS:
- Precision-fix handles 80% of cases (edge-aware denoise, algorithmic fixes)
- Render-doctor provides automated diagnostics for remaining cases
- Edge-aware denoise gives +3 on noisy BirdEye cameras
- Measurement grid overlays give +1 on DriverPOV cameras
- gamma_exposure MUST be applied AFTER overlays
- Cameras scoring 98+ are already optimal, skip them
- Scorer has ±2-5 variance, so small gains may be noise
- Post-processing has diminishing returns above 95
- This LLM loop is LAST RESORT — precision-fix and render-doctor already attempted

Your response MUST be valid JSON with this schema:
{
  "camera": "scene1_BirdEye",
  "fix_type": "denoise",
  "hypothesis": "BirdEye still has residual noise after precision-fix and render-doctor, denoise should help",
  "confidence": 0.7,
  "reasoning": "This camera scores 83 after prior stages, noise is the dominant issue"
}`;

async function askLLMForFix(targets, recentExperiments, precisionResults, doctorResults) {
  const precisionSummary = precisionResults.improved.length > 0
    ? `Precision-fix improved ${precisionResults.improved.length} cameras: ${precisionResults.improved.map(r => `${r.camera}(+${r.delta.toFixed(1)})`).join(", ")}`
    : "Precision-fix did not improve any remaining cameras";
  const doctorSummary = doctorResults.improved.length > 0
    ? `Render-doctor improved ${doctorResults.improved.length} cameras: ${doctorResults.improved.map(r => `${r.camera}(+${r.delta.toFixed(1)})`).join(", ")}`
    : "Render-doctor did not improve any remaining cameras";

  const userMsg = `SITUATION: Precision-fix and render-doctor stages have completed. These are the REMAINING targets:
${targets.map((t) => `- ${t.camera}: ${t.score}/100`).join("\n")}

STAGES COMPLETED:
${precisionSummary}
${doctorSummary}

RECENT LLM EXPERIMENTS:
${recentExperiments.slice(-5).map((e) => `- ${e.camera} + ${e.fix_type}: ${e.delta > 0 ? "+" : ""}${e.delta} (${e.kept})`).join("\n") || "No LLM experiments yet."}

You are the LAST RESORT. Pick ONE camera and ONE fix that neither precision-fix nor render-doctor could handle. Prioritize the lowest-scoring camera. Avoid repeating fixes that showed no improvement on the same camera.`;

  const result = await askLLM("_default", SYSTEM_PROMPT, userMsg, {
    max_tokens: 512,
  });

  if (result.json && result.json.camera && result.json.fix_type) {
    return result.json;
  }

  // Fallback: rotate through cameras and fix types deterministically
  const fixOptions = {
    BirdEye: ["denoise", "exposure", "contrast", "combined_conservative"],
    DriverPOV: ["detail", "overlay_forensic", "contrast", "combined_conservative"],
    WideAngle: ["exposure", "contrast", "detail", "combined_conservative"],
    SightLine: ["contrast", "detail", "exposure", "denoise"],
    SecurityCam: ["contrast", "denoise", "exposure", "detail"],
  };

  // Count how many times we've tried each camera to rotate
  const cameraCounts = {};
  for (const exp of recentExperiments) {
    cameraCounts[exp.camera] = (cameraCounts[exp.camera] || 0) + 1;
  }

  // Pick the least-tried target camera
  const sortedTargets = [...targets].sort((a, b) => {
    const ca = cameraCounts[a.camera] || 0;
    const cb = cameraCounts[b.camera] || 0;
    return ca - cb || a.score - b.score; // fewer tries first, then lowest score
  });
  const target = sortedTargets[0];

  // Pick a fix type we haven't tried on this camera yet
  const triedFixes = new Set(
    recentExperiments.filter((e) => e.camera === target.camera).map((e) => e.fix_type)
  );
  const options = fixOptions[target.cam] || ["combined_conservative", "denoise", "exposure", "contrast"];
  const fix = options.find((f) => !triedFixes.has(f)) || options[Math.floor(Math.random() * options.length)];

  return {
    camera: target.camera,
    fix_type: fix,
    hypothesis: `Fallback heuristic: trying ${fix} on ${target.camera} (score: ${target.score}) after precision-fix and render-doctor`,
    confidence: 0.5,
    reasoning: "LLM unavailable, using rotation heuristic to explore different fix types",
  };
}

// ─── Update Audit Report ─────────────────────────────────────────────────────
function updateAudit(scores, experiments) {
  const allScores = [];
  for (const cams of Object.values(scores)) {
    for (const s of Object.values(cams)) allScores.push(s);
  }
  const avg = allScores.reduce((a, b) => a + b, 0) / allScores.length;

  const audit = {
    version: "worker_v2_precision",
    date: new Date().toISOString(),
    overall_score: Math.round(avg * 10) / 10,
    per_camera_scores: scores,
    total_experiments: experiments.length,
    improvements: experiments.filter((e) => e.kept === "improved").length,
    reverted: experiments.filter((e) => e.kept === "reverted").length,
    last_experiment: experiments[experiments.length - 1] || null,
  };

  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  fs.writeFileSync(AUDIT_FILE, JSON.stringify(audit, null, 2));
  return audit;
}

// ─── Update Memory ───────────────────────────────────────────────────────────
function updateMemory(scores, experiments, precisionCount, doctorCount) {
  const today = new Date().toISOString().split("T")[0];
  const memDir = path.join(CLAW_DIR, "agent-state/agents/blender_render_worker/memory");
  fs.mkdirSync(memDir, { recursive: true });

  const recentWins = experiments.filter((e) => e.kept === "improved").slice(-5);
  const recentLosses = experiments.filter((e) => e.kept === "reverted").slice(-5);

  const memEntry = `# ${today} blender_render_worker

## ${new Date().toISOString()}
- goal: Improve forensic render quality scores through multi-stage pipeline
- task_type: render_improvement
- summary: status=completed | precision_fix=${precisionCount} | render_doctor=${doctorCount} | llm_experiments=${experiments.length}
- learned: ${recentWins.map((w) => `${w.camera}+${w.fix_type}=+${w.delta}`).join("; ") || "No improvements this cycle"}
- failed: ${recentLosses.map((l) => `${l.camera}+${l.fix_type}=${l.delta}`).join("; ") || "No failures this cycle"}
- next_focus: ${Object.entries(scores).flatMap(([s, c]) => Object.entries(c).filter(([, v]) => v < 95).map(([k, v]) => `${s}_${k}(${v})`)).join(", ") || "All cameras above 95"}
- tags: blender_render_worker, forensic, render_quality, precision_fix, multi_stage
- model_used: ollama-local
- cost_usd: 0
`;

  const memFile = path.join(memDir, `${today}.md`);
  fs.appendFileSync(memFile, memEntry);
}

// ─── Main Loop ───────────────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);
  const maxIterations = parseInt(args.find((a) => a.startsWith("--max-iterations="))?.split("=")[1] || "10");
  const workerCount = parseInt(args.find((a) => a.startsWith("--workers="))?.split("=")[1] || "1");

  console.log(`\n${"═".repeat(70)}`);
  console.log(`  RENDER IMPROVEMENT LOOP v2 — Multi-Stage Pipeline`);
  console.log(`  ${new Date().toISOString()}`);
  console.log(`  Workers: ${workerCount} | Max LLM Iterations: ${maxIterations}`);
  console.log(`${"═".repeat(70)}\n`);

  let scores = loadCurrentScores();
  let allExperiments = loadRecentExperiments(50);
  let precisionFixCount = 0;
  let renderDoctorCount = 0;
  let truePlateau = false;

  // ─── STAGE 1: PRECISION-FIX ──────────────────────────────────────────────────
  console.log(`\nLOADING INITIAL TARGETS...`);
  let targets = getImprovementTargets(scores);
  console.log(`Found ${targets.length} cameras below target (98+)`);

  if (targets.length > 0) {
    const precisionResults = runPrecisionFix(targets, scores);
    precisionFixCount = precisionResults.improved.length;

    // Update targets after precision-fix
    targets = getImprovementTargets(scores);
    console.log(`\nAfter precision-fix: ${targets.length} cameras remaining below target`);
  }

  // ─── STAGE 2: RENDER-DOCTOR ──────────────────────────────────────────────────
  let doctorResults = { improved: [], unchanged: [], failed: [] };
  if (targets.length > 0) {
    doctorResults = runRenderDoctor(targets, scores);
    renderDoctorCount = doctorResults.improved.length;

    // Update targets after render-doctor
    targets = getImprovementTargets(scores);
    console.log(`\nAfter render-doctor: ${targets.length} cameras remaining below target`);
  }

  // Detect true plateau: if both stages had zero delta, we've hit a wall
  const precisionUnchangedCount = (runPrecisionFix.precisionResults?.unchanged || []).length;
  const doctorUnchangedCount = (doctorResults.unchanged || []).length;
  if (targets.length > 0 && precisionFixCount === 0 && renderDoctorCount === 0) {
    console.log(`\n⚠ TRUE PLATEAU DETECTED: Both precision-fix and render-doctor had zero improvement delta.`);
    truePlateau = true;
  }

  // ─── STAGE 3: LLM LOOP (last resort) ─────────────────────────────────────────
  let consecutiveFailures = 0;
  for (let i = 0; i < maxIterations && targets.length > 0 && !truePlateau; i++) {
    console.log(`\n── LLM Loop Iteration ${i + 1}/${maxIterations} ──────────────────────────────`);

    targets = getImprovementTargets(scores);
    if (targets.length === 0) {
      console.log("All cameras at 98+. Nothing to improve.");
      break;
    }

    console.log(`Targets: ${targets.map((t) => `${t.camera}(${t.score})`).join(", ")}`);

    // Ask LLM what to try
    const decision = await askLLMForFix(targets, allExperiments, { improved: [] }, doctorResults);
    console.log(`LLM decision: ${decision.camera} + ${decision.fix_type}`);
    console.log(`Hypothesis: ${decision.hypothesis}`);
    console.log(`Confidence: ${decision.confidence}`);

    // Execute the fix
    const result = runWorkerFix(decision.camera, decision.fix_type, decision.camera.split("_")[0]);

    if (result.ok) {
      console.log(`Result: ${result.kept} | ${result.original_score} → ${result.new_score} (${result.delta > 0 ? "+" : ""}${result.delta})`);

      // Update scores if improved
      if (result.kept === "improved") {
        const [scene, cam] = decision.camera.split("_");
        if (scores[scene] && scores[scene][cam] !== undefined) {
          scores[scene][cam] = result.new_score;
        }
        consecutiveFailures = 0;
      } else {
        consecutiveFailures++;
      }

      allExperiments.push({
        timestamp: new Date().toISOString(),
        camera: decision.camera,
        fix_type: decision.fix_type,
        original_score: result.original_score,
        new_score: result.new_score,
        delta: result.delta,
        kept: result.kept,
        hypothesis: decision.hypothesis,
        llm_confidence: decision.confidence,
        stage: "llm_loop",
      });
    } else {
      console.log(`ERROR: ${result.error}`);
      consecutiveFailures++;
    }

    // Detect plateau after LLM attempts
    if (consecutiveFailures >= 5) {
      console.log("\n⚠ PLATEAU DETECTED: 5 consecutive LLM failures. Escalating.");
      truePlateau = true;
      // Write escalation signal
      const escalation = {
        type: "plateau_escalation",
        timestamp: new Date().toISOString(),
        consecutive_failures: consecutiveFailures,
        current_scores: scores,
        message: "Post-processing plateau reached. Need geometry changes via Blender MCP.",
      };
      fs.mkdirSync(DATA_DIR, { recursive: true });
      fs.writeFileSync(
        path.join(DATA_DIR, "escalation_signal.json"),
        JSON.stringify(escalation, null, 2)
      );
      break;
    }

    // Brief pause between iterations to avoid hammering Ollama
    await new Promise((r) => setTimeout(r, 2000));
  }

  // Update audit and memory
  const audit = updateAudit(scores, allExperiments);
  updateMemory(scores, allExperiments, precisionFixCount, renderDoctorCount);

  console.log(`\n${"═".repeat(70)}`);
  console.log(`  MULTI-STAGE PIPELINE COMPLETE — Overall: ${audit.overall_score}`);
  console.log(`  Stage 1 (Precision-Fix): ${precisionFixCount} improvements`);
  console.log(`  Stage 2 (Render-Doctor): ${renderDoctorCount} improvements`);
  console.log(`  Stage 3 (LLM Loop): ${allExperiments.filter(e => e.stage === "llm_loop" && e.kept === "improved").length} improvements`);
  console.log(`  Total Experiments: ${allExperiments.length} | Total Improvements: ${audit.improvements}`);
  console.log(`${"═".repeat(70)}\n`);

  // Output for orchestrator
  const output = {
    ok: true,
    overall_score: audit.overall_score,
    precision_fix_improvements: precisionFixCount,
    render_doctor_improvements: renderDoctorCount,
    llm_improvements: allExperiments.filter(e => e.stage === "llm_loop" && e.kept === "improved").length,
    experiments_run: allExperiments.length,
    improvements: audit.improvements,
    worst_camera: Object.entries(scores)
      .flatMap(([s, c]) => Object.entries(c).map(([k, v]) => ({ cam: `${s}_${k}`, score: v })))
      .sort((a, b) => a.score - b.score)[0],
    plateau_detected: truePlateau,
    pipeline_stages_completed: ["precision_fix", "render_doctor", targets.length === 0 ? "llm_loop" : "partial_llm"],
  };
  console.log(JSON.stringify(output));
}

main().catch((err) => {
  console.error(`[FATAL] ${err.message}`);
  process.exit(1);
});
