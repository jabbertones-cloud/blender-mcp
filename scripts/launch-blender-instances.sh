#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# OpenClaw Multi-Blender Instance Launcher
# ═══════════════════════════════════════════════════════════════════════════════
#
# Launches multiple Blender instances, each on a different TCP port, so
# concurrent agents can work on separate .blend files without conflicts.
#
# Usage:
#   ./launch-blender-instances.sh                    # Launch 1 instance on default port 9876
#   ./launch-blender-instances.sh 3                  # Launch 3 instances (ports 9876, 9877, 9878)
#   ./launch-blender-instances.sh 2 /path/to/scene   # Launch 2, each opens a new file based on template
#
# Each instance gets:
#   - Unique port (OPENCLAW_PORT env var)
#   - Unique instance ID (OPENCLAW_INSTANCE env var)
#   - Separate .blend file (no file conflicts)
#
# Prerequisites:
#   - Blender installed at /Applications/Blender.app (macOS) or 'blender' in PATH
#   - OpenClaw Bridge addon installed in Blender
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

NUM_INSTANCES="${1:-1}"
TEMPLATE_FILE="${2:-}"
BASE_PORT=9876
BLENDER_APP="/Applications/Blender.app/Contents/MacOS/Blender"

# Fallback to PATH if macOS app not found
if [ ! -x "$BLENDER_APP" ]; then
    BLENDER_APP=$(which blender 2>/dev/null || echo "")
    if [ -z "$BLENDER_APP" ]; then
        echo "ERROR: Blender not found. Install it or set BLENDER_APP."
        exit 1
    fi
fi

echo "═══════════════════════════════════════════════════════"
echo " OpenClaw Multi-Blender Launcher"
echo " Instances: $NUM_INSTANCES"
echo " Port range: $BASE_PORT - $((BASE_PORT + NUM_INSTANCES - 1))"
echo "═══════════════════════════════════════════════════════"

PIDS=()

cleanup() {
    echo ""
    echo "Shutting down all Blender instances..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            echo "  Stopping PID $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done
    echo "All instances stopped."
}

trap cleanup EXIT INT TERM

for i in $(seq 0 $((NUM_INSTANCES - 1))); do
    PORT=$((BASE_PORT + i))
    INSTANCE_ID="blender-${PORT}"

    echo ""
    echo "Launching instance $((i + 1))/$NUM_INSTANCES:"
    echo "  Instance ID: $INSTANCE_ID"
    echo "  Port:        $PORT"

    # Build Blender args
    BLENDER_ARGS=("--background" "--python-expr"
        "import os; os.environ['OPENCLAW_PORT']='${PORT}'; os.environ['OPENCLAW_INSTANCE']='${INSTANCE_ID}'"
    )

    if [ -n "$TEMPLATE_FILE" ] && [ -f "$TEMPLATE_FILE" ]; then
        echo "  Template:    $TEMPLATE_FILE"
        BLENDER_ARGS=("$TEMPLATE_FILE" "${BLENDER_ARGS[@]}")
    fi

    # Launch Blender with environment variables set
    OPENCLAW_PORT="$PORT" \
    OPENCLAW_INSTANCE="$INSTANCE_ID" \
    "$BLENDER_APP" "${BLENDER_ARGS[@]}" &

    PID=$!
    PIDS+=("$PID")
    echo "  PID:         $PID"

    # Brief pause to stagger launches
    sleep 1
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo " All $NUM_INSTANCES instances launched!"
echo ""
echo " To discover instances from MCP:"
echo "   blender_instances(action='list')"
echo ""
echo " To connect an agent to a specific instance:"
echo "   blender_instances(action='connect', port=9877)"
echo ""
echo " Press Ctrl+C to stop all instances"
echo "═══════════════════════════════════════════════════════"

# Wait for all instances
wait
