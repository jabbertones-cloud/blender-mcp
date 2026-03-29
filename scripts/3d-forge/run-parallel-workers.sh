#!/bin/bash
# run-parallel-workers.sh — Launch multiple render improvement workers in parallel.
# Each worker runs the improvement loop independently, picking different cameras.
#
# Usage: bash scripts/3d-forge/run-parallel-workers.sh [NUM_WORKERS] [ITERATIONS_EACH]

NUM_WORKERS=${1:-3}
ITERATIONS=${2:-5}
BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
LOG_DIR="$BASE_DIR/data/worker_logs"
mkdir -p "$LOG_DIR"

echo "═══════════════════════════════════════════════════════════════"
echo "  PARALLEL RENDER WORKERS — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  Workers: $NUM_WORKERS | Iterations each: $ITERATIONS"
echo "═══════════════════════════════════════════════════════════════"

PIDS=()

for i in $(seq 1 $NUM_WORKERS); do
  LOG="$LOG_DIR/worker_${i}_$(date +%Y%m%d_%H%M%S).log"
  echo "Starting worker $i → $LOG"

  node "$BASE_DIR/scripts/3d-forge/render-improve-loop.js" \
    --max-iterations=$ITERATIONS \
    --workers=1 \
    > "$LOG" 2>&1 &

  PIDS+=($!)
  # Stagger worker starts by 5 seconds to avoid Ollama contention
  sleep 5
done

echo ""
echo "Workers launched: ${PIDS[*]}"
echo "Waiting for all workers to complete..."

FAILURES=0
for pid in "${PIDS[@]}"; do
  wait $pid
  EXIT=$?
  if [ $EXIT -ne 0 ]; then
    echo "Worker PID $pid exited with code $EXIT"
    ((FAILURES++))
  fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ALL WORKERS COMPLETE — Failures: $FAILURES/$NUM_WORKERS"
echo "═══════════════════════════════════════════════════════════════"

# Run supervisor audit after all workers finish
echo ""
echo "Running supervisor audit..."
node "$BASE_DIR/scripts/3d-forge/render-audit-supervisor.js"

echo ""
echo "Done. Check reports/supervisor_audit_latest.json for results."
