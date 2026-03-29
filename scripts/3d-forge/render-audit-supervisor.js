#!/usr/bin/env node
/**
 * Render Audit Supervisor — Claude-powered audit layer.
 *
 * This script analyzes the local LLM workers' experiment logs, identifies
 * patterns in what works vs. what doesn't, and generates improved strategies
 * that get written back into the workers' MEMORY.md for the next cycle.
 *
 * Designed to be run by Claude (the supervising agent) to accelerate
 * local LLM learning. Can also run autonomously via cron.
 *
 * Usage: node scripts/3d-forge/render-audit-supervisor.js [--auto|--harsh-review|--micro-eval]
 */

const fs = require("fs");
const path = require("path");

const BASE_DIR = path.resolve(__dirname, "../..");
const CLAW_DIR = path.resolve(BASE_DIR, "..");
const DATA_DIR = path.join(BASE_DIR, "data");
const REPORTS_DIR = path.join(BASE_DIR, "reports");
const EXPERIMENTS_LOG = path.join(DATA_DIR, "worker_experiments.ndjson");
const MEMORY_FILE = path.join(CLAW_DIR, "agent-state/agents/blender_render_worker/MEMORY.md");
const SOUL_FILE = path.join(CLAW_DIR, "agent-state/agents/blender_render_worker/SOUL.md");
const AUDIT_OUTPUT = path.join(REPORTS_DIR, "supervisor_audit_latest.json");
const LEARNINGS_OUTPUT = path.join(DATA_DIR, "supervisor_learnings.md");
const STATE_FILE = path.join(DATA_DIR, "supervisor_state.json");

// ─── Load Experiments ────────────────────────────────────────────────────────
function loadAllExperiments() {
  if (!fs.existsSync(EXPERIMENTS_LOG)) return [];
  return fs
    .readFileSync(EXPERIMENTS_LOG, "utf8")
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((l) => {
      try { return JSON.parse(l); } catch { return null; }
    })
    .filter(Boolean);
}

// ─── Supervisor State Management ──────────────────────────────────────────────
function loadState() {
  if (!fs.existsSync(STATE_FILE)) {
    return { scores: {}, timestamps: {}, velocities: {} };
  }
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return { scores: {}, timestamps: {}, velocities: {} };
  }
}

function saveState(state) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
}

// ─── Analyze Patterns ────────────────────────────────────────────────────────
function analyzeExperiments(experiments) {
  const analysis = {
    total: experiments.length,
    improvements: 0,
    regressions: 0,
    neutral: 0,
    by_fix_type: {},
    by_camera: {},
    by_camera_fix: {},
    best_combos: [],
    worst_combos: [],
    streaks: { current_failures: 0, max_failures: 0 },
  };

  let currentFailStreak = 0;

  for (const exp of experiments) {
    // Overall counts
    if (exp.kept === "improved") {
      analysis.improvements++;
      currentFailStreak = 0;
    } else {
      analysis.regressions++;
      currentFailStreak++;
      analysis.streaks.max_failures = Math.max(analysis.streaks.max_failures, currentFailStreak);
    }

    // By fix type
    const ft = exp.fix_type || "unknown";
    if (!analysis.by_fix_type[ft]) {
      analysis.by_fix_type[ft] = { total: 0, wins: 0, avg_delta: 0, deltas: [] };
    }
    analysis.by_fix_type[ft].total++;
    if (exp.kept === "improved") analysis.by_fix_type[ft].wins++;
    analysis.by_fix_type[ft].deltas.push(exp.delta || 0);

    // By camera
    const cam = exp.camera || "unknown";
    if (!analysis.by_camera[cam]) {
      analysis.by_camera[cam] = { total: 0, wins: 0, best_fix: null, best_delta: -Infinity };
    }
    analysis.by_camera[cam].total++;
    if (exp.kept === "improved") analysis.by_camera[cam].wins++;
    if ((exp.delta || 0) > analysis.by_camera[cam].best_delta) {
      analysis.by_camera[cam].best_delta = exp.delta;
      analysis.by_camera[cam].best_fix = ft;
    }

    // By camera+fix combo
    const comboKey = `${cam}+${ft}`;
    if (!analysis.by_camera_fix[comboKey]) {
      analysis.by_camera_fix[comboKey] = { camera: cam, fix: ft, tries: 0, wins: 0, avg_delta: 0, deltas: [] };
    }
    analysis.by_camera_fix[comboKey].tries++;
    if (exp.kept === "improved") analysis.by_camera_fix[comboKey].wins++;
    analysis.by_camera_fix[comboKey].deltas.push(exp.delta || 0);
  }

  analysis.streaks.current_failures = currentFailStreak;

  // Calculate averages
  for (const ft of Object.values(analysis.by_fix_type)) {
    ft.avg_delta = ft.deltas.length > 0 ? ft.deltas.reduce((a, b) => a + b, 0) / ft.deltas.length : 0;
    ft.win_rate = ft.total > 0 ? Math.round((ft.wins / ft.total) * 100) : 0;
  }

  for (const combo of Object.values(analysis.by_camera_fix)) {
    combo.avg_delta = combo.deltas.length > 0 ? combo.deltas.reduce((a, b) => a + b, 0) / combo.deltas.length : 0;
    combo.win_rate = combo.tries > 0 ? Math.round((combo.wins / combo.tries) * 100) : 0;
  }

  // Sort combos by effectiveness
  const combos = Object.values(analysis.by_camera_fix).filter((c) => c.tries >= 2);
  combos.sort((a, b) => b.avg_delta - a.avg_delta);
  analysis.best_combos = combos.slice(0, 5);
  analysis.worst_combos = combos.slice(-5).reverse();

  return analysis;
}

// ─── Generate Strategy Recommendations ───────────────────────────────────────
function generateStrategy(analysis) {
  const recommendations = [];

  // 1. Identify which fix types actually work
  for (const [ft, stats] of Object.entries(analysis.by_fix_type)) {
    if (stats.win_rate >= 60 && stats.total >= 3) {
      recommendations.push({
        type: "PREFER",
        fix: ft,
        reason: `${ft} has ${stats.win_rate}% win rate over ${stats.total} trials (avg delta: ${stats.avg_delta.toFixed(1)})`,
      });
    } else if (stats.win_rate < 20 && stats.total >= 3) {
      recommendations.push({
        type: "AVOID",
        fix: ft,
        reason: `${ft} has only ${stats.win_rate}% win rate over ${stats.total} trials — not effective`,
      });
    }
  }

  // 2. Camera-specific advice
  for (const [cam, stats] of Object.entries(analysis.by_camera)) {
    if (stats.wins === 0 && stats.total >= 3) {
      recommendations.push({
        type: "ESCALATE",
        camera: cam,
        reason: `${cam} has 0 improvements in ${stats.total} attempts — needs geometry changes, not post-processing`,
      });
    } else if (stats.best_fix && stats.best_delta > 0) {
      recommendations.push({
        type: "PROVEN",
        camera: cam,
        fix: stats.best_fix,
        reason: `Best fix for ${cam} is ${stats.best_fix} (best delta: +${stats.best_delta})`,
      });
    }
  }

  // 3. Combo-specific blacklist
  for (const combo of analysis.worst_combos) {
    if (combo.avg_delta < -1 && combo.tries >= 2) {
      recommendations.push({
        type: "BLACKLIST",
        camera: combo.camera,
        fix: combo.fix,
        reason: `${combo.camera}+${combo.fix} consistently regresses (avg: ${combo.avg_delta.toFixed(1)} over ${combo.tries} tries)`,
      });
    }
  }

  // 4. Plateau detection
  if (analysis.streaks.current_failures >= 5) {
    recommendations.push({
      type: "PLATEAU",
      reason: `${analysis.streaks.current_failures} consecutive failures. Post-processing ceiling reached. Switch to Blender geometry improvements.`,
    });
  }

  return recommendations;
}

// ─── Update MEMORY.md ────────────────────────────────────────────────────────
function updateMemoryWithLearnings(analysis, recommendations) {
  if (!fs.existsSync(MEMORY_FILE)) return;

  let memory = fs.readFileSync(MEMORY_FILE, "utf8");

  // Build new learnings section
  const newLearnings = [];
  let idx = 11; // Continue from L10

  for (const rec of recommendations) {
    if (rec.type === "PREFER") {
      newLearnings.push(`- L${idx}: SUPERVISOR: ${rec.fix} is highly effective (${rec.reason})`);
      idx++;
    } else if (rec.type === "AVOID") {
      newLearnings.push(`- L${idx}: SUPERVISOR: AVOID ${rec.fix} — ${rec.reason}`);
      idx++;
    } else if (rec.type === "BLACKLIST") {
      newLearnings.push(`- L${idx}: SUPERVISOR: BLACKLIST ${rec.camera}+${rec.fix} — ${rec.reason}`);
      idx++;
    } else if (rec.type === "PROVEN") {
      newLearnings.push(`- L${idx}: SUPERVISOR: ${rec.camera} responds best to ${rec.fix} (${rec.reason})`);
      idx++;
    } else if (rec.type === "ESCALATE") {
      newLearnings.push(`- L${idx}: SUPERVISOR: ESCALATE ${rec.camera} — ${rec.reason}`);
      idx++;
    }
  }

  // Remove old supervisor learnings and append new ones
  const lines = memory.split("\n");
  const filtered = lines.filter((l) => !l.includes("SUPERVISOR:"));
  const keyLearningsIdx = filtered.findIndex((l) => l.includes("KEY LEARNINGS"));
  if (keyLearningsIdx >= 0) {
    // Find next section header after KEY LEARNINGS
    let insertIdx = keyLearningsIdx + 1;
    while (insertIdx < filtered.length && !filtered[insertIdx].startsWith("##")) {
      insertIdx++;
    }
    filtered.splice(insertIdx, 0, ...newLearnings, "");
  }

  // Update experiment history
  const histIdx = filtered.findIndex((l) => l.includes("EXPERIMENT HISTORY"));
  if (histIdx >= 0) {
    const statsLine = `- Worker runs: ${analysis.total} experiments, ${analysis.improvements} improvements, ${analysis.regressions} reverted (${Math.round((analysis.improvements / Math.max(1, analysis.total)) * 100)}% win rate)`;
    // Insert after the header
    filtered.splice(histIdx + 1, 0, statsLine);
  }

  fs.writeFileSync(MEMORY_FILE, filtered.join("\n"));
}

// ─── Write Reports ───────────────────────────────────────────────────────────
function writeReports(analysis, recommendations) {
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  fs.mkdirSync(DATA_DIR, { recursive: true });

  // JSON audit
  const auditReport = {
    timestamp: new Date().toISOString(),
    type: "supervisor_audit",
    analysis,
    recommendations,
    summary: {
      total_experiments: analysis.total,
      win_rate: analysis.total > 0 ? Math.round((analysis.improvements / analysis.total) * 100) : 0,
      best_fix_type: Object.entries(analysis.by_fix_type)
        .sort(([, a], [, b]) => b.avg_delta - a.avg_delta)[0]?.[0] || "none",
      plateau_detected: analysis.streaks.current_failures >= 5,
      recommendations_count: recommendations.length,
    },
  };
  fs.writeFileSync(AUDIT_OUTPUT, JSON.stringify(auditReport, null, 2));

  // Human-readable learnings
  const lines = [
    `# Supervisor Learnings — ${new Date().toISOString().split("T")[0]}`,
    "",
    `## Summary`,
    `- Total experiments: ${analysis.total}`,
    `- Win rate: ${auditReport.summary.win_rate}%`,
    `- Best fix type: ${auditReport.summary.best_fix_type}`,
    `- Plateau: ${auditReport.summary.plateau_detected ? "YES" : "No"}`,
    "",
    `## Fix Type Effectiveness`,
  ];

  for (const [ft, stats] of Object.entries(analysis.by_fix_type).sort(([, a], [, b]) => b.avg_delta - a.avg_delta)) {
    lines.push(`- **${ft}**: ${stats.win_rate}% win rate, avg delta ${stats.avg_delta.toFixed(1)}, ${stats.total} trials`);
  }

  lines.push("", "## Recommendations");
  for (const rec of recommendations) {
    lines.push(`- [${rec.type}] ${rec.reason}`);
  }

  lines.push("", "## Best Camera+Fix Combos");
  for (const combo of analysis.best_combos) {
    lines.push(`- ${combo.camera} + ${combo.fix}: avg +${combo.avg_delta.toFixed(1)} (${combo.win_rate}% win rate, ${combo.tries} tries)`);
  }

  fs.writeFileSync(LEARNINGS_OUTPUT, lines.join("\n"));
}

// ─── Micro-Eval Harness ──────────────────────────────────────────────────────
/**
 * Fast evaluation function that scores renders and compares against previous best.
 * Returns { improved, regressed, unchanged, delta_avg, details }
 */
function runMicroEval(imagePaths) {
  const state = loadState();
  const results = {
    improved: [],
    regressed: [],
    unchanged: [],
    delta_avg: 0,
    details: {},
    timestamp: new Date().toISOString(),
  };

  if (imagePaths.length === 0) return results;

  const deltas = [];

  for (const imgPath of imagePaths) {
    if (!fs.existsSync(imgPath)) continue;

    const key = path.basename(imgPath);
    const currentScore = runDeterministicScore(imgPath);
    const previousScore = state.scores[key] || null;

    if (previousScore === null) {
      results.unchanged.push(key);
      results.details[key] = { current: currentScore, previous: null, delta: 0, status: "baseline" };
      state.scores[key] = currentScore;
      state.timestamps[key] = new Date().toISOString();
    } else {
      const delta = currentScore - previousScore;
      deltas.push(delta);

      if (delta > 0.1) {
        results.improved.push(key);
        results.details[key] = { current: currentScore, previous: previousScore, delta, status: "improved" };
        state.scores[key] = currentScore;
        state.timestamps[key] = new Date().toISOString();
      } else if (delta < -0.1) {
        results.regressed.push(key);
        results.details[key] = { current: currentScore, previous: previousScore, delta, status: "regressed" };
      } else {
        results.unchanged.push(key);
        results.details[key] = { current: currentScore, previous: previousScore, delta, status: "unchanged" };
      }
    }
  }

  if (deltas.length > 0) {
    results.delta_avg = deltas.reduce((a, b) => a + b, 0) / deltas.length;
  }

  saveState(state);
  return results;
}

// ─── Deterministic Scorer (stub) ──────────────────────────────────────────────
/**
 * Runs external scorer with --seed flag for deterministic results.
 * Placeholder: returns consistent score based on path hash.
 */
function runDeterministicScore(imagePath) {
  // In production: spawn child process with blender scorer + --seed
  // For now, stub returns consistent mock score
  const hash = imagePath.split("").reduce((h, c) => ((h << 5) - h) + c.charCodeAt(0), 0);
  return (Math.abs(hash % 100) + 50) / 2; // 25-75 range
}

// ─── Harsh Review Mode ────────────────────────────────────────────────────────
/**
 * Strict evaluation with penalty multipliers.
 * Returns red/yellow/green status per camera.
 */
function harshReview(cameraScores) {
  const traffic = {};
  let anyRed = false;

  for (const [camera, scores] of Object.entries(cameraScores)) {
    const metrics = Object.values(scores);
    const avgScore = metrics.reduce((a, b) => a + b, 0) / metrics.length;

    let penalty = 0;
    let status = "GREEN";

    // Apply harsh penalties
    const below80 = metrics.filter((m) => m < 80).length > 0;
    if (below80) {
      penalty += 1.5;
      status = "RED";
      anyRed = true;
    }

    if (avgScore < 85) {
      penalty -= 5;
      status = "RED";
      anyRed = true;
    }

    const finalScore = avgScore * (1 - penalty);
    traffic[camera] = {
      avg: avgScore,
      penalty_factor: 1 - penalty,
      final: finalScore,
      status,
      metrics,
    };
  }

  return { traffic, anyRed };
}

// ─── Improvement Velocity Tracking ────────────────────────────────────────────
/**
 * Calculate improvement rate: points_gained_per_hour, experiments_per_improvement.
 */
function trackVelocity(experiments) {
  if (experiments.length === 0) return { points_per_hour: 0, exp_per_improvement: 0, velocity_status: "no_data" };

  const state = loadState();
  const now = new Date();
  const improvements = experiments.filter((e) => e.kept === "improved");

  if (improvements.length === 0) {
    return { points_per_hour: 0, exp_per_improvement: Infinity, velocity_status: "plateau" };
  }

  const totalDelta = improvements.reduce((sum, e) => sum + (e.delta || 0), 0);
  const avgExperimentTime = 5; // minutes (stub)
  const totalMinutes = experiments.length * avgExperimentTime;
  const totalHours = totalMinutes / 60;

  const pointsPerHour = totalDelta / Math.max(1, totalHours);
  const expPerImprovement = experiments.length / improvements.length;

  state.velocities.last_update = now.toISOString();
  state.velocities.points_per_hour = pointsPerHour;
  state.velocities.exp_per_improvement = expPerImprovement;
  state.velocities.status = pointsPerHour > 0 ? "improving" : "plateau";

  saveState(state);

  return {
    points_per_hour: pointsPerHour,
    exp_per_improvement: expPerImprovement,
    velocity_status: state.velocities.status,
  };
}

// ─── Cross-Validation ─────────────────────────────────────────────────────────
/**
 * Re-score an improved image 3 times with different methods.
 * Flag as SUSPICIOUS if scores disagree by >10 points.
 */
function crossValidate(imagePath) {
  const validation = {
    path: imagePath,
    scorers: {},
    agreement: "PASS",
    details: [],
  };

  // Score 1: Deterministic scorer
  const score1 = runDeterministicScore(imagePath);
  validation.scorers.deterministic = score1;

  // Score 2: Tier 1 pixel scorer (stub)
  const score2 = runDeterministicScore(imagePath) + (Math.random() * 2 - 1); // Add small jitter
  validation.scorers.tier1_pixel = score2;

  // Score 3: Internal compute_score (stub)
  const score3 = runDeterministicScore(imagePath) + (Math.random() * 2 - 1);
  validation.scorers.compute_score = score3;

  const scores = [score1, score2, score3];
  const max = Math.max(...scores);
  const min = Math.min(...scores);
  const disagreement = max - min;

  validation.disagreement = disagreement;
  validation.details.push(`Min: ${min.toFixed(1)}, Max: ${max.toFixed(1)}, Gap: ${disagreement.toFixed(1)}`);

  if (disagreement > 10) {
    validation.agreement = "SUSPICIOUS";
    validation.details.push("Scorer disagreement > 10 points — improvement flagged for manual review.");
  }

  return validation;
}

// ─── Pattern Mining ──────────────────────────────────────────────────────────
/**
 * Enhance experiment analysis to find camera+fix+time combos, durability, diminishing returns.
 */
function minePatternsAdvanced(experiments) {
  const patterns = {
    camera_fix_time: {},
    durability: {},
    diminishing_returns: {},
    transfer_potential: {},
  };

  // Group by camera+fix+hour_of_day
  for (const exp of experiments) {
    const hour = new Date(exp.timestamp).getHours();
    const key = `${exp.camera}+${exp.fix_type}@${hour}h`;

    if (!patterns.camera_fix_time[key]) {
      patterns.camera_fix_time[key] = { count: 0, improvements: 0, avg_delta: 0, deltas: [] };
    }
    patterns.camera_fix_time[key].count++;
    if (exp.kept === "improved") patterns.camera_fix_time[key].improvements++;
    patterns.camera_fix_time[key].deltas.push(exp.delta || 0);
  }

  // Calculate averages
  for (const stats of Object.values(patterns.camera_fix_time)) {
    stats.avg_delta = stats.deltas.reduce((a, b) => a + b, 0) / stats.deltas.length;
    stats.win_rate = Math.round((stats.improvements / stats.count) * 100);
  }

  // Durability: re-scored improvements (from cross-validation)
  patterns.durability.retest_required = [];
  patterns.durability.verified_improvements = [];

  // Diminishing returns: count consecutive attempts per camera
  const cameraAttempts = {};
  for (const exp of experiments) {
    const cam = exp.camera || "unknown";
    if (!cameraAttempts[cam]) cameraAttempts[cam] = [];
    cameraAttempts[cam].push(exp.delta || 0);
  }

  for (const [cam, deltas] of Object.entries(cameraAttempts)) {
    const sorted = [...deltas].sort((a, b) => b - a);
    const top5 = sorted.slice(0, 5).reduce((a, b) => a + b, 0) / 5;
    const tail5 = sorted.slice(-5).reduce((a, b) => a + b, 0) / 5;
    patterns.diminishing_returns[cam] = {
      top_avg: top5,
      bottom_avg: tail5,
      ratio: top5 > 0 ? (top5 / tail5).toFixed(2) : "N/A",
    };
  }

  // Cross-camera transfer: if denoise works on scene1_BirdEye, test scene2_BirdEye
  const cameraTypes = {};
  for (const exp of experiments) {
    const cam = exp.camera || "unknown";
    const type = cam.split("_")[cam.split("_").length - 1]; // Extract type (e.g., "BirdEye")
    if (!cameraTypes[type]) cameraTypes[type] = {};
    if (!cameraTypes[type][exp.fix_type]) cameraTypes[type][exp.fix_type] = [];
    cameraTypes[type][exp.fix_type].push(exp.delta || 0);
  }

  for (const [type, fixes] of Object.entries(cameraTypes)) {
    patterns.transfer_potential[type] = {};
    for (const [fix, deltas] of Object.entries(fixes)) {
      const avgDelta = deltas.reduce((a, b) => a + b, 0) / deltas.length;
      patterns.transfer_potential[type][fix] = { avg_delta: avgDelta.toFixed(2), count: deltas.length };
    }
  }

  return patterns;
}

// ─── Main ────────────────────────────────────────────────────────────────────
function main() {
  const args = process.argv.slice(2);
  const flagHarshReview = args.includes("--harsh-review");
  const flagMicroEval = args.includes("--micro-eval");

  console.log(`\n${"═".repeat(70)}`);
  console.log(`  RENDER AUDIT SUPERVISOR — ${new Date().toISOString()}`);
  if (flagHarshReview) console.log(`  MODE: HARSH REVIEW`);
  if (flagMicroEval) console.log(`  MODE: MICRO-EVAL HARNESS`);
  console.log(`${"═".repeat(70)}\n`);

  // ─── Micro-Eval Mode ──────────────────────────────────────────────────────
  if (flagMicroEval) {
    console.log("Running micro-eval harness...");

    // Scan for recent renders in a standard location
    const renderDir = path.join(BASE_DIR, "renders");
    let imagePaths = [];
    if (fs.existsSync(renderDir)) {
      const files = fs.readdirSync(renderDir);
      imagePaths = files
        .filter((f) => /\.(png|jpg|exr)$/i.test(f))
        .map((f) => path.join(renderDir, f))
        .slice(0, 16); // Limit to 16 cameras
    }

    console.log(`Found ${imagePaths.length} render images for evaluation.`);
    const microEvalResult = runMicroEval(imagePaths);

    console.log(`\nMicro-Eval Results:`);
    console.log(`  Improved: ${microEvalResult.improved.length}`);
    console.log(`  Regressed: ${microEvalResult.regressed.length}`);
    console.log(`  Unchanged: ${microEvalResult.unchanged.length}`);
    console.log(`  Average delta: ${microEvalResult.delta_avg.toFixed(2)}`);

    // Cross-validate top improvements
    if (microEvalResult.improved.length > 0) {
      console.log(`\nCross-validating ${Math.min(3, microEvalResult.improved.length)} improvements...`);
      for (let i = 0; i < Math.min(3, microEvalResult.improved.length); i++) {
        const imgPath = path.join(renderDir, microEvalResult.improved[i]);
        const cv = crossValidate(imgPath);
        console.log(`  ${cv.path}: ${cv.agreement} (disagreement: ${cv.disagreement.toFixed(2)})`);
      }
    }

    console.log(`\n${JSON.stringify(microEvalResult)}`);
    return;
  }

  // ─── Harsh Review Mode ────────────────────────────────────────────────────
  if (flagHarshReview) {
    console.log("Running harsh review mode on all cameras...");

    // Stub: load mock camera scores
    const cameraScores = {
      scene1_FrontView: { contrast: 82, exposure: 78, sharpness: 85 },
      scene1_BirdEye: { contrast: 88, exposure: 91, sharpness: 92 },
      scene2_FrontView: { contrast: 76, exposure: 72, sharpness: 79 },
      scene2_LeftSide: { contrast: 84, exposure: 86, sharpness: 88 },
    };

    const { traffic, anyRed } = harshReview(cameraScores);

    console.log(`\nTraffic Light Results:`);
    for (const [camera, data] of Object.entries(traffic)) {
      const light = data.status === "RED" ? "RED" : data.status === "YELLOW" ? "YELLOW" : "GREEN";
      console.log(`  ${light} ${camera}: avg ${data.avg.toFixed(1)} → final ${data.final.toFixed(1)} [${data.status}]`);
    }

    if (anyRed) {
      console.log(`\nHARSH REVIEW FAILED: ${Object.values(traffic).filter((t) => t.status === "RED").length} cameras in RED.`);
      process.exit(1);
    } else {
      console.log(`\nAll cameras passed harsh review.`);
      console.log(`\n${JSON.stringify({ ok: true, harsh_review: "pass", traffic })}`);
    }
    return;
  }

  // ─── Standard Audit Mode ──────────────────────────────────────────────────
  const experiments = loadAllExperiments();
  if (experiments.length === 0) {
    console.log("No experiments found. Workers need to run first.");
    console.log(JSON.stringify({ ok: true, experiments: 0, message: "No data yet" }));
    return;
  }

  console.log(`Loaded ${experiments.length} experiments.`);

  const analysis = analyzeExperiments(experiments);
  console.log(`\nAnalysis:`);
  console.log(`  Improvements: ${analysis.improvements}/${analysis.total} (${Math.round((analysis.improvements / analysis.total) * 100)}%)`);
  console.log(`  Current fail streak: ${analysis.streaks.current_failures}`);
  console.log(`  Max fail streak: ${analysis.streaks.max_failures}`);

  // Velocity tracking
  const velocity = trackVelocity(experiments);
  console.log(`\nVelocity:`);
  console.log(`  Points per hour: ${velocity.points_per_hour.toFixed(2)}`);
  console.log(`  Experiments per improvement: ${velocity.exp_per_improvement.toFixed(1)}`);
  console.log(`  Status: ${velocity.velocity_status}`);

  // Pattern mining
  const patterns = minePatternsAdvanced(experiments);
  console.log(`\nPattern Mining:`);
  console.log(`  Time-of-day combos found: ${Object.keys(patterns.camera_fix_time).length}`);
  console.log(`  Diminishing returns tracked for ${Object.keys(patterns.diminishing_returns).length} cameras`);
  console.log(`  Cross-camera transfer potential identified for ${Object.keys(patterns.transfer_potential).length} types`);

  const recommendations = generateStrategy(analysis);
  console.log(`\nRecommendations (${recommendations.length}):`);
  for (const rec of recommendations) {
    console.log(`  [${rec.type}] ${rec.reason}`);
  }

  // Update worker memory with learnings
  updateMemoryWithLearnings(analysis, recommendations);
  console.log(`\nUpdated worker MEMORY.md with ${recommendations.length} supervisor learnings.`);

  // Write reports
  writeReports(analysis, recommendations);
  console.log(`Written: ${AUDIT_OUTPUT}`);
  console.log(`Written: ${LEARNINGS_OUTPUT}`);

  // Output for orchestrator
  const output = {
    ok: true,
    experiments: experiments.length,
    win_rate: Math.round((analysis.improvements / Math.max(1, analysis.total)) * 100),
    recommendations: recommendations.length,
    plateau: analysis.streaks.current_failures >= 5,
    best_fix: Object.entries(analysis.by_fix_type)
      .sort(([, a], [, b]) => b.avg_delta - a.avg_delta)[0]?.[0] || "none",
    velocity: velocity,
    patterns_mined: Object.keys(patterns.camera_fix_time).length,
  };
  console.log(`\n${JSON.stringify(output)}`);
}

main();
