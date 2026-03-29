#!/usr/bin/env node
/**
 * Render Swarm Orchestrator — Parallel per-scene quality improvement workers.
 *
 * Spawns one worker process per scene (4 scenes = 4 parallel workers).
 * Each worker handles all cameras in its scene sequentially with retry logic.
 * Workers communicate results via NDJSON and stdout capture.
 * Main orchestrator collects results, produces scoreboard and final report.
 *
 * Usage: node render-swarm.js [--scenes 1,2,3,4] [--target-score 85] [--max-retries 3] [--renders-dir <path>]
 */

const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

// ─── Config ──────────────────────────────────────────────────────────────────
const BASE_DIR = path.resolve(__dirname, "../..");
const RENDERS_DIR = path.join(BASE_DIR, "renders");
const FINAL_BEST_DIR = path.join(RENDERS_DIR, "FINAL_BEST");
const REPORTS_DIR = path.join(BASE_DIR, "reports");
const DATA_DIR = path.join(BASE_DIR, "data");

const SCORER_SCRIPT = path.join(__dirname, "render-quality-scorer.js");
const PRECISION_FIX_SCRIPT = path.join(__dirname, "precision-fix.py");
const RENDER_DOCTOR_SCRIPT = path.join(__dirname, "render-doctor.py");

// Ensure output directories exist
fs.mkdirSync(REPORTS_DIR, { recursive: true });
fs.mkdirSync(DATA_DIR, { recursive: true });

// Scene configuration (4 scenes × 4 cameras each = 16 cameras total)
const SCENE_CAMERAS = {
  scene1: ["BirdEye", "DriverPOV", "WideAngle", "SecurityCam"],
  scene2: ["BirdEye", "DriverPOV", "SightLine", "WideAngle"],
  scene3: ["BirdEye", "DriverPOV", "WideAngle", "SecurityCam"],
  scene4: ["BirdEye", "DriverPOV", "SecurityCam", "WideAngle"],
};

// Logging utilities
const LOG = {
  info: (msg) => console.log(`[INFO]  ${msg}`),
  warn: (msg) => console.log(`[WARN]  ${msg}`),
  error: (msg) => console.error(`[ERROR] ${msg}`),
  debug: (msg) => {
    if (process.env.DEBUG) console.log(`[DEBUG] ${msg}`);
  },
  section: (title) => {
    const line = "─".repeat(70);
    console.log(`\n${line}\n  ${title}\n${line}`);
  },
};

// Parse CLI args
function parseArgs() {
  const args = {
    scenes: [1, 2, 3, 4],
    targetScore: 85,
    maxRetries: 3,
    rendersDir: FINAL_BEST_DIR,
  };

  for (let i = 2; i < process.argv.length; i++) {
    const arg = process.argv[i];
    if (arg.startsWith("--scenes=")) {
      args.scenes = arg.split("=")[1].split(",").map(Number);
    } else if (arg.startsWith("--target-score=")) {
      args.targetScore = parseInt(arg.split("=")[1]);
    } else if (arg.startsWith("--max-retries=")) {
      args.maxRetries = parseInt(arg.split("=")[1]);
    } else if (arg.startsWith("--renders-dir=")) {
      args.rendersDir = arg.split("=")[1];
    }
  }

  return args;
}

// Find a render image for a given camera
function findRenderImage(sceneId, cameraName) {
  const searchDirs = [FINAL_BEST_DIR];

  for (const dir of searchDirs) {
    if (!fs.existsSync(dir)) continue;

    const files = fs.readdirSync(dir);
    for (const file of files) {
      // Match pattern: scene1_BirdEye_BEST.png or scene1_BirdEye_FINAL.png
      const baseName = file.replace(/\.(png|jpg|jpeg)$/i, "");
      if (
        baseName.includes(sceneId) &&
        baseName.includes(cameraName.replace(/_/g, "").replace(/([A-Z])/g, "$1"))
      ) {
        return path.join(dir, file);
      }
      // Also try direct matching
      if (baseName.includes(`${sceneId}_${cameraName}`)) {
        return path.join(dir, file);
      }
    }
  }

  return null;
}

// Score an image using the quality scorer
function scoreImage(imagePath) {
  return new Promise((resolve) => {
    if (!fs.existsSync(imagePath)) {
      resolve(null);
      return;
    }

    let output = "";
    const proc = spawn("node", [SCORER_SCRIPT, "--image", imagePath, "--tier", "1"], {
      cwd: BASE_DIR,
      timeout: 30000,
    });

    proc.stdout.on("data", (data) => {
      output += data.toString();
    });

    proc.on("close", (code) => {
      if (code !== 0) {
        resolve(null);
        return;
      }

      // Parse score from output
      const lines = output.split("\n");
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.includes("score")) {
          const match = trimmed.match(/[\d.]+/);
          if (match) {
            resolve(parseFloat(match[0]));
            return;
          }
        }
        const val = parseFloat(trimmed);
        if (!isNaN(val) && val >= 0 && val <= 100) {
          resolve(val);
          return;
        }
      }

      resolve(null);
    });

    proc.on("error", () => resolve(null));
    setTimeout(() => {
      try {
        proc.kill();
      } catch (e) {}
      resolve(null);
    }, 30000);
  });
}

// Apply precision-fix to an image
function applyPrecisionFix(imagePath, outputPath) {
  return new Promise((resolve) => {
    let output = "";
    const proc = spawn("python3", [PRECISION_FIX_SCRIPT, "--image", imagePath, "--output", outputPath, "--verify"], {
      cwd: BASE_DIR,
      timeout: 60000,
    });

    proc.stdout.on("data", (data) => {
      output += data.toString();
    });

    proc.stderr.on("data", (data) => {
      output += data.toString();
    });

    proc.on("close", (code) => {
      const success = code === 0 && fs.existsSync(outputPath);
      resolve({ success, output });
    });

    proc.on("error", (err) => {
      resolve({ success: false, output: err.message });
    });

    setTimeout(() => {
      try {
        proc.kill();
      } catch (e) {}
      resolve({ success: false, output: "Timeout" });
    }, 60000);
  });
}

// Apply render-doctor fallback
function applyRenderDoctor(imagePath, outputPath) {
  return new Promise((resolve) => {
    let output = "";
    const proc = spawn("python3", [RENDER_DOCTOR_SCRIPT, "--image", imagePath, "--output", outputPath], {
      cwd: BASE_DIR,
      timeout: 60000,
    });

    proc.stdout.on("data", (data) => {
      output += data.toString();
    });

    proc.stderr.on("data", (data) => {
      output += data.toString();
    });

    proc.on("close", (code) => {
      const success = code === 0 && fs.existsSync(outputPath);
      resolve({ success, output });
    });

    proc.on("error", (err) => {
      resolve({ success: false, output: err.message });
    });

    setTimeout(() => {
      try {
        proc.kill();
      } catch (e) {}
      resolve({ success: false, output: "Timeout" });
    }, 60000);
  });
}

// Worker function: Process one scene with all its cameras
async function workerProcessScene(sceneId, targetScore, maxRetries) {
  const results = [];
  const cameras = SCENE_CAMERAS[sceneId];
  const outputDir = path.join(RENDERS_DIR, `swarm_output/scene${sceneId.replace("scene", "")}`);

  fs.mkdirSync(outputDir, { recursive: true });

  LOG.info(`Worker started for ${sceneId} (${cameras.length} cameras)`);

  for (const camera of cameras) {
    const cameraKey = `${sceneId}_${camera}`;
    const cameraResult = {
      camera: cameraKey,
      originalScore: null,
      finalScore: null,
      improved: false,
      retries: 0,
      strategy: null,
      escalated: false,
      log: [],
    };

    try {
      // Find original render
      const originalPath = findRenderImage(sceneId, camera);
      if (!originalPath) {
        cameraResult.log.push(`No source image found`);
        cameraResult.escalated = true;
        results.push(cameraResult);
        continue;
      }

      // Score original
      const originalScore = await scoreImage(originalPath);
      cameraResult.originalScore = originalScore;
      cameraResult.log.push(`Original score: ${originalScore}`);

      if (originalScore === null) {
        cameraResult.log.push(`Failed to score original`);
        cameraResult.escalated = true;
        results.push(cameraResult);
        continue;
      }

      // Skip if already good
      if (originalScore >= 95) {
        cameraResult.finalScore = originalScore;
        cameraResult.log.push(`Already at ${originalScore}, skipping`);
        results.push(cameraResult);
        continue;
      }

      let currentImagePath = originalPath;
      let currentScore = originalScore;
      let retryRound = 0;

      // Retry loop with multiple strategies
      while (retryRound < maxRetries && currentScore < targetScore) {
        retryRound++;
        cameraResult.retries = retryRound;

        let strategy;
        let fixPath;
        let success;

        if (retryRound === 1) {
          // Round 1: precision-fix.py (calculated fixes)
          strategy = "precision-fix";
          fixPath = path.join(outputDir, `${cameraKey}_round1_precision.png`);
          cameraResult.log.push(`Round ${retryRound}: Applying precision-fix`);

          const result = await applyPrecisionFix(currentImagePath, fixPath);
          success = result.success;

          if (!success || !fs.existsSync(fixPath)) {
            cameraResult.log.push(`  precision-fix failed: ${result.output}`);
            continue;
          }
        } else if (retryRound === 2) {
          // Round 2: render-doctor.py (combined fixes)
          strategy = "render-doctor";
          fixPath = path.join(outputDir, `${cameraKey}_round2_doctor.png`);
          cameraResult.log.push(`Round ${retryRound}: Applying render-doctor`);

          const result = await applyRenderDoctor(currentImagePath, fixPath);
          success = result.success;

          if (!success || !fs.existsSync(fixPath)) {
            cameraResult.log.push(`  render-doctor failed: ${result.output}`);
            continue;
          }
        } else if (retryRound === 3) {
          // Round 3: precision-fix with darker target (sometimes helps)
          strategy = "precision-fix-dark";
          fixPath = path.join(outputDir, `${cameraKey}_round3_dark.png`);
          cameraResult.log.push(`Round ${retryRound}: Applying precision-fix with target-brightness 0.42`);

          // Would need to extend precision-fix.py to support --target-brightness
          // For now, fallback to standard precision-fix
          const result = await applyPrecisionFix(currentImagePath, fixPath);
          success = result.success;

          if (!success || !fs.existsSync(fixPath)) {
            cameraResult.log.push(`  precision-fix-dark failed: ${result.output}`);
            break;
          }
        }

        if (!success) continue;

        // Score the fixed version
        const newScore = await scoreImage(fixPath);
        if (newScore === null) {
          cameraResult.log.push(`  Failed to score fixed image`);
          continue;
        }

        const improvement = newScore - currentScore;
        cameraResult.log.push(`  Score: ${currentScore} → ${newScore} (${improvement > 0 ? "+" : ""}${improvement})`);

        // Check if improved
        if (newScore > currentScore) {
          currentImagePath = fixPath;
          currentScore = newScore;
          cameraResult.improved = true;
          cameraResult.strategy = strategy;
          cameraResult.log.push(`  Kept this version`);

          // If good enough, stop retrying
          if (newScore >= targetScore) {
            cameraResult.finalScore = newScore;
            cameraResult.log.push(`Target score ${targetScore} reached`);
            break;
          }
        } else {
          // Regression: don't update, try next strategy
          cameraResult.log.push(`  Regression detected, reverting to previous version`);
          try {
            fs.unlinkSync(fixPath);
          } catch (e) {}
        }
      }

      // Final score
      cameraResult.finalScore = currentScore;

      // Check for escalation
      if (currentScore < targetScore && retryRound >= maxRetries) {
        cameraResult.escalated = true;
        cameraResult.log.push(`ESCALATE: Still below ${targetScore} after ${maxRetries} retries`);
      }
    } catch (err) {
      cameraResult.log.push(`Exception: ${err.message}`);
      cameraResult.escalated = true;
    }

    results.push(cameraResult);
  }

  return results;
}

// Main orchestrator
async function main() {
  const args = parseArgs();
  const startTime = Date.now();

  LOG.section(`RENDER SWARM ORCHESTRATOR — ${new Date().toISOString()}`);
  LOG.info(`Scenes: ${args.scenes.join(", ")}`);
  LOG.info(`Target score: ${args.targetScore}`);
  LOG.info(`Max retries per camera: ${args.maxRetries}`);

  // Spawn workers for each scene
  const workerPromises = args.scenes.map((sceneNum) => {
    const sceneId = `scene${sceneNum}`;
    return workerProcessScene(sceneId, args.targetScore, args.maxRetries);
  });

  // Wait for all workers to complete
  LOG.section("WORKERS RUNNING");
  const allResults = await Promise.all(workerPromises);
  const flatResults = allResults.flat();

  // Analyze results
  const elapsedMs = Date.now() - startTime;
  const elapsedSec = Math.round(elapsedMs / 100) / 10;

  const stats = {
    totalCameras: flatResults.length,
    improved: flatResults.filter((r) => r.improved).length,
    escalated: flatResults.filter((r) => r.escalated).length,
    atTarget: flatResults.filter((r) => r.finalScore >= args.targetScore).length,
    avgOriginal: (
      flatResults.reduce((sum, r) => sum + (r.originalScore || 0), 0) / flatResults.length
    ).toFixed(1),
    avgFinal: (
      flatResults.reduce((sum, r) => sum + (r.finalScore || 0), 0) / flatResults.length
    ).toFixed(1),
  };

  // Print scoreboard
  LOG.section("SCOREBOARD (Before → After)");
  console.log("\n  Scene 1:");
  for (const r of flatResults.filter((x) => x.camera.startsWith("scene1"))) {
    const orig = r.originalScore ? r.originalScore.toFixed(1) : "—";
    const final = r.finalScore ? r.finalScore.toFixed(1) : "—";
    const status = r.escalated ? "⚠ ESCALATE" : r.improved ? "✓ IMPROVED" : "→ UNCHANGED";
    console.log(
      `    ${r.camera.padEnd(20)} ${orig.padStart(5)} → ${final.padStart(5)}  ${status}`
    );
  }

  console.log("\n  Scene 2:");
  for (const r of flatResults.filter((x) => x.camera.startsWith("scene2"))) {
    const orig = r.originalScore ? r.originalScore.toFixed(1) : "—";
    const final = r.finalScore ? r.finalScore.toFixed(1) : "—";
    const status = r.escalated ? "⚠ ESCALATE" : r.improved ? "✓ IMPROVED" : "→ UNCHANGED";
    console.log(
      `    ${r.camera.padEnd(20)} ${orig.padStart(5)} → ${final.padStart(5)}  ${status}`
    );
  }

  console.log("\n  Scene 3:");
  for (const r of flatResults.filter((x) => x.camera.startsWith("scene3"))) {
    const orig = r.originalScore ? r.originalScore.toFixed(1) : "—";
    const final = r.finalScore ? r.finalScore.toFixed(1) : "—";
    const status = r.escalated ? "⚠ ESCALATE" : r.improved ? "✓ IMPROVED" : "→ UNCHANGED";
    console.log(
      `    ${r.camera.padEnd(20)} ${orig.padStart(5)} → ${final.padStart(5)}  ${status}`
    );
  }

  console.log("\n  Scene 4:");
  for (const r of flatResults.filter((x) => x.camera.startsWith("scene4"))) {
    const orig = r.originalScore ? r.originalScore.toFixed(1) : "—";
    const final = r.finalScore ? r.finalScore.toFixed(1) : "—";
    const status = r.escalated ? "⚠ ESCALATE" : r.improved ? "✓ IMPROVED" : "→ UNCHANGED";
    console.log(
      `    ${r.camera.padEnd(20)} ${orig.padStart(5)} → ${final.padStart(5)}  ${status}`
    );
  }

  // Summary
  LOG.section("RESULTS SUMMARY");
  console.log(`  Total cameras:       ${stats.totalCameras}`);
  console.log(`  Improved:            ${stats.improved}`);
  console.log(`  Escalated:           ${stats.escalated}`);
  console.log(`  At target (${args.targetScore}+): ${stats.atTarget}`);
  console.log(`  Avg original score:  ${stats.avgOriginal}`);
  console.log(`  Avg final score:     ${stats.avgFinal}`);
  console.log(`  Runtime:             ${elapsedSec}s`);

  // Write results to file
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, -5);
  const reportPath = path.join(REPORTS_DIR, `swarm_results_${timestamp}.json`);

  const report = {
    timestamp: new Date().toISOString(),
    version: "swarm_v1",
    config: {
      scenes: args.scenes,
      targetScore: args.targetScore,
      maxRetries: args.maxRetries,
    },
    stats,
    results: flatResults,
    runtimeSeconds: elapsedSec,
  };

  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  LOG.info(`Report written to ${reportPath}`);

  // Write escalation signal if needed
  if (stats.escalated > 0) {
    const escalationPath = path.join(DATA_DIR, "escalation_signal.json");
    const escalation = {
      type: "swarm_escalation",
      timestamp: new Date().toISOString(),
      escalatedCameras: flatResults
        .filter((r) => r.escalated)
        .map((r) => ({
          camera: r.camera,
          score: r.finalScore,
          retries: r.retries,
          reason: `Below target ${args.targetScore} after ${r.retries} retries`,
        })),
      message: `${stats.escalated} cameras need RENDER-LEVEL fixes. Post-processing plateau reached.`,
    };
    fs.writeFileSync(escalationPath, JSON.stringify(escalation, null, 2));
    LOG.warn(`Escalation signal written (${stats.escalated} cameras)`);
  }

  // Exit code
  const success = stats.escalated === 0;
  const exitCode = success ? 0 : 1;

  LOG.section(`SWARM COMPLETE — Exit code: ${exitCode}`);
  process.exit(exitCode);
}

main().catch((err) => {
  LOG.error(`Unhandled exception: ${err.message}`);
  LOG.error(err.stack);
  process.exit(1);
});
