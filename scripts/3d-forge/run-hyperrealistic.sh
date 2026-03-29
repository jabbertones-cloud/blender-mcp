#!/bin/bash
# run-hyperrealistic.sh — Upgrade all 4 forensic scenes to hyperrealistic quality
#
# Usage:
#   bash scripts/3d-forge/run-hyperrealistic.sh [--render] [--samples N] [--engine CYCLES|EEVEE]
#
# Without --render: just upgrades scenes and saves .blend files (fast, no GPU)
# With --render: upgrades AND renders all camera angles (requires GPU, ~10-30 min)

BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
if [ ! -f "$BLENDER" ]; then
    BLENDER=$(which blender 2>/dev/null || echo "blender")
fi

BASE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$BASE_DIR/scripts/3d-forge/hyperrealistic-upgrade.py"
RENDER_FLAG=""
SAMPLES=128
ENGINE="CYCLES"

for arg in "$@"; do
    case $arg in
        --render) RENDER_FLAG="--render" ;;
        --samples=*) SAMPLES="${arg#*=}" ;;
        --engine=*) ENGINE="${arg#*=}" ;;
    esac
done

echo "═══════════════════════════════════════════════════════════════"
echo "  HYPERREALISTIC SCENE UPGRADE PIPELINE"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  Engine: $ENGINE | Samples: $SAMPLES | Render: ${RENDER_FLAG:-'no (save only)'}"
echo "═══════════════════════════════════════════════════════════════"

FAILED=0

for SCENE in 1 2 3 4; do
    echo ""
    echo "── Scene $SCENE ──────────────────────────────────────────────"
    "$BLENDER" --background --python "$SCRIPT" -- \
        --scene $SCENE \
        --engine $ENGINE \
        --samples $SAMPLES \
        $RENDER_FLAG \
        2>&1 | tee "$BASE_DIR/data/hyperrealistic_scene${SCENE}.log"

    if [ $? -ne 0 ]; then
        echo "  ERROR: Scene $SCENE failed"
        ((FAILED++))
    fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  PIPELINE COMPLETE — Failures: $FAILED/4"
echo "  Upgraded scenes: $BASE_DIR/renders/hyperrealistic/"
echo "═══════════════════════════════════════════════════════════════"
