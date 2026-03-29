#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# 3D Forge Render Quality Self-Improvement Runner
# Run 4x daily: 8am, 1pm, 6pm, 11pm
# Cron: 0 8,13,18,23 * * * /path/to/self-improve-runner.sh
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPTS_DIR="$BASE_DIR/scripts/3d-forge"
REPORTS_DIR="$BASE_DIR/reports"
TIMESTAMP=$(date +%Y-%m-%d-%H%M)
LOG_FILE="$REPORTS_DIR/self-improve-$TIMESTAMP.log"

mkdir -p "$REPORTS_DIR"

echo "═══════════════════════════════════════════════════════" | tee "$LOG_FILE"
echo "  SELF-IMPROVEMENT RUN: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" | tee -a "$LOG_FILE"

cd "$BASE_DIR"

# ── Step 1: Harsh Review ──
echo "" | tee -a "$LOG_FILE"
echo "▶ STEP 1: Harsh Review (current state)" | tee -a "$LOG_FILE"
node "$SCRIPTS_DIR/render-audit-supervisor.js" --harsh-review 2>&1 | tee -a "$LOG_FILE" || true

# ── Step 2: Self-Improvement Cycle ──
echo "" | tee -a "$LOG_FILE"
echo "▶ STEP 2: Self-Improvement Cycle" | tee -a "$LOG_FILE"
node "$SCRIPTS_DIR/autoresearch-agent.js" --self-improve --verbose 2>&1 | tee -a "$LOG_FILE" || true

# ── Step 3: Rapid Iteration ──
echo "" | tee -a "$LOG_FILE"
echo "▶ STEP 3: Rapid Iteration (cameras below 85)" | tee -a "$LOG_FILE"
node "$SCRIPTS_DIR/autoresearch-agent.js" --rapid --verbose 2>&1 | tee -a "$LOG_FILE" || true

# ── Step 4: Swarm (if needed) ──
echo "" | tee -a "$LOG_FILE"
echo "▶ STEP 4: Render Swarm (parallel fix)" | tee -a "$LOG_FILE"
node "$SCRIPTS_DIR/render-swarm.js" --scenes 1,2,3,4 --target-score 85 --max-retries 3 2>&1 | tee -a "$LOG_FILE" || true

# ── Step 5: Final Verification ──
echo "" | tee -a "$LOG_FILE"
echo "▶ STEP 5: Final Micro-Eval Verification" | tee -a "$LOG_FILE"
node "$SCRIPTS_DIR/render-audit-supervisor.js" --micro-eval 2>&1 | tee -a "$LOG_FILE" || true

# ── Step 6: Summary ──
echo "" | tee -a "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
echo "  RUN COMPLETE: $TIMESTAMP" | tee -a "$LOG_FILE"
echo "  Log: $LOG_FILE" | tee -a "$LOG_FILE"
echo "═══════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
