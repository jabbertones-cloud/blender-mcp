#!/bin/bash
#
# Adaptive Multi-Pass Render Pipeline
# Implements intelligent quality-based rendering with fallback to previous best results
#
# Usage:
#   ./adaptive_render_pipeline.sh --scenes "1 2 3 4" --output-dir renders/v23_final --previous-dir renders/v21_final
#

set -euo pipefail

# Configuration
BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
SCORER_SCRIPT="scripts/3d-forge/render-quality-scorer.js"
VALIDATOR_SCRIPT="scripts/pre_render_validator.py"
SCENE_DIR="renders"

# Default arguments
SCENES="1 2 3 4"
OUTPUT_DIR="renders/v23_final"
PREVIOUS_DIR="renders/v21_final"

# Scoring thresholds
SCORE_SKIP_THRESHOLD=30
SCORE_UPRES_THRESHOLD=70

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --scenes)
            SCENES="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --previous-dir)
            PREVIOUS_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Initialize tracking
TOTAL_RENDER_TIME=0
TOTAL_SKIP_TIME=0
CAMERAS_PROCESSED=0
CAMERAS_IMPROVED=0
DECISIONS=()
ERRORS=()

# Logging function
log_message() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] $1"
}

# Parse scorer output to extract score
parse_scorer_score() {
    local json_output="$1"
    echo "$json_output" | grep -o '"score":[0-9.]*' | cut -d':' -f2 | head -1
}

# Get previous best score for camera
get_previous_score() {
    local scene_num="$1"
    local camera_name="$2"
    
    if [ ! -d "$PREVIOUS_DIR" ]; then
        echo "0"
        return
    fi
    
    local prev_score_file="$PREVIOUS_DIR/scene${scene_num}/${camera_name}_score.txt"
    if [ -f "$prev_score_file" ]; then
        cat "$prev_score_file"
    else
        echo "0"
    fi
}

# Get list of cameras for a scene
get_scene_cameras() {
    local scene_file="$1"
    
    if [ ! -f "$scene_file" ]; then
        echo ""
        return
    fi
    
    # Extract camera names from blender file using Python
    # This is a simplified approach - in practice, you'd parse the .blend file
    # For now, we'll use a convention: cameras are named Cam_<name>
    python3 << 'PYTHON_END'
import bpy
import sys

try:
    bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
    cameras = [obj.name for obj in bpy.data.objects if obj.type == 'CAMERA']
    for cam in cameras:
        print(cam)
except Exception as e:
    print(f"Error loading scene: {e}", file=sys.stderr)
PYTHON_END
}

# Main pipeline loop
process_pipeline() {
    log_message "Starting Adaptive Multi-Pass Render Pipeline"
    log_message "Output directory: $OUTPUT_DIR"
    log_message "Previous best directory: $PREVIOUS_DIR"
    log_message "Processing scenes: $SCENES"
    
    for scene_num in $SCENES; do
        local scene_file="${SCENE_DIR}/v11_scene${scene_num}.blend"
        
        log_message "===== SCENE $scene_num ====="
        
        if [ ! -f "$scene_file" ]; then
            local error_msg="Scene file not found: $scene_file"
            log_message "ERROR: $error_msg"
            ERRORS+=("Scene $scene_num: $error_msg")
            continue
        fi
        
        local scene_output_dir="${OUTPUT_DIR}/scene${scene_num}"
        mkdir -p "$scene_output_dir"
        
        # Get cameras for this scene
        log_message "Extracting cameras from $scene_file..."
        local cameras=$(get_scene_cameras "$scene_file" 2>/dev/null || echo "")
        
        if [ -z "$cameras" ]; then
            local error_msg="No cameras found in scene"
            log_message "WARNING: $error_msg"
            ERRORS+=("Scene $scene_num: $error_msg")
            continue
        fi
        
        # Process each camera
        while IFS= read -r camera_name; do
            [ -z "$camera_name" ] && continue
            
            CAMERAS_PROCESSED=$((CAMERAS_PROCESSED + 1))
            local safe_name=$(echo "$camera_name" | sed 's/[^a-zA-Z0-9_]/_/g')
            
            log_message "Processing camera: $camera_name"
            
            # Step 1: Validate scene
            log_message "  [1/4] Validating scene..."
            if command -v python3 &> /dev/null && [ -f "$VALIDATOR_SCRIPT" ]; then
                if ! python3 "$VALIDATOR_SCRIPT" "$scene_file" --camera "$camera_name" > /dev/null 2>&1; then
                    log_message "  VALIDATION FAILED - Skipping camera"
                    DECISIONS+=("Scene $scene_num, Camera $camera_name: VALIDATION_FAILED")
                    continue
                fi
            fi
            
            # Step 2: Render at 25%
            log_message "  [2/4] Rendering at 25%..."
            local render_25="${scene_output_dir}/${safe_name}_25pct.png"
            local render_start=$(date +%s%N)
            
            if ! "$BLENDER_BIN" --background "$scene_file" --python scripts/proxy_render.py \
                -- --percent 25 --camera "$camera_name" --output "$render_25" > /dev/null 2>&1; then
                log_message "  RENDER FAILED at 25% - Skipping camera"
                DECISIONS+=("Scene $scene_num, Camera $camera_name: RENDER_FAILED_25")
                continue
            fi
            
            local render_end=$(date +%s%N)
            local render_time_25=$(( (render_end - render_start) / 1000000 ))
            TOTAL_RENDER_TIME=$((TOTAL_RENDER_TIME + render_time_25))
            
            # Step 3: Score at 25%
            log_message "  [3/4] Scoring 25% render..."
            local score_25=0
            
            if command -v node &> /dev/null && [ -f "$SCORER_SCRIPT" ]; then
                local scorer_output=$(node "$SCORER_SCRIPT" --image "$render_25" --tier 1 2>/dev/null || echo "{}")
                score_25=$(parse_scorer_score "$scorer_output" || echo "0")
            else
                score_25=75  # Default good score if scorer unavailable
            fi
            
            log_message "  25% Score: $score_25"
            
            # Step 4: Determine upres strategy
            local best_score=$score_25
            local best_render=$render_25
            local best_percent=25
            
            if (( $(echo "$score_25 < $SCORE_SKIP_THRESHOLD" | bc -l) )); then
                # Score too low - skip entirely
                log_message "  Score < $SCORE_SKIP_THRESHOLD - SKIPPING (broken render)"
                DECISIONS+=("Scene $scene_num, Camera $camera_name: SKIPPED (score=$score_25)")
                continue
            elif (( $(echo "$score_25 < $SCORE_UPRES_THRESHOLD" | bc -l) )); then
                # Score mediocre - try 50%
                log_message "  Score < $SCORE_UPRES_THRESHOLD - Attempting 50%..."
                local render_50="${scene_output_dir}/${safe_name}_50pct.png"
                
                render_start=$(date +%s%N)
                if "$BLENDER_BIN" --background "$scene_file" --python scripts/proxy_render.py \
                    -- --percent 50 --camera "$camera_name" --output "$render_50" > /dev/null 2>&1; then
                    
                    render_end=$(date +%s%N)
                    render_time_50=$(( (render_end - render_start) / 1000000 ))
                    TOTAL_RENDER_TIME=$((TOTAL_RENDER_TIME + render_time_50))
                    
                    log_message "  [3/4] Scoring 50% render..."
                    local score_50=0
                    
                    if command -v node &> /dev/null && [ -f "$SCORER_SCRIPT" ]; then
                        scorer_output=$(node "$SCORER_SCRIPT" --image "$render_50" --tier 1 2>/dev/null || echo "{}")
                        score_50=$(parse_scorer_score "$scorer_output" || echo "0")
                    else
                        score_50=80
                    fi
                    
                    log_message "  50% Score: $score_50"
                    
                    if (( $(echo "$score_50 > $score_25" | bc -l) )); then
                        best_score=$score_50
                        best_render=$render_50
                        best_percent=50
                    fi
                fi
            fi
            
            # Final decision: try 100% if we don't have a great score
            if (( $(echo "$best_score < 90" | bc -l) )); then
                log_message "  Score < 90 - Rendering at 100%..."
                local render_100="${scene_output_dir}/${safe_name}_100pct.png"
                
                render_start=$(date +%s%N)
                if "$BLENDER_BIN" --background "$scene_file" --python scripts/proxy_render.py \
                    -- --percent 100 --camera "$camera_name" --output "$render_100" > /dev/null 2>&1; then
                    
                    render_end=$(date +%s%N)
                    local render_time_100=$(( (render_end - render_start) / 1000000 ))
                    TOTAL_RENDER_TIME=$((TOTAL_RENDER_TIME + render_time_100))
                    
                    log_message "  [3/4] Scoring 100% render..."
                    local score_100=0
                    
                    if command -v node &> /dev/null && [ -f "$SCORER_SCRIPT" ]; then
                        scorer_output=$(node "$SCORER_SCRIPT" --image "$render_100" --tier 1 2>/dev/null || echo "{}")
                        score_100=$(parse_scorer_score "$scorer_output" || echo "0")
                    else
                        score_100=95
                    fi
                    
                    log_message "  100% Score: $score_100"
                    
                    if (( $(echo "$score_100 > $best_score" | bc -l) )); then
                        best_score=$score_100
                        best_render=$render_100
                        best_percent=100
                    fi
                fi
            fi
            
            # Step 5: Compare with previous best
            log_message "  [4/4] Comparing with previous best..."
            local prev_score=$(get_previous_score "$scene_num" "$safe_name")
            
            local decision="KEPT_OLD"
            if (( $(echo "$best_score > $prev_score" | bc -l) )); then
                decision="IMPROVED (new=$best_score, old=$prev_score)"
                CAMERAS_IMPROVED=$((CAMERAS_IMPROVED + 1))
                
                # Copy to best-of directory
                mkdir -p "${OUTPUT_DIR}/best-of/scene${scene_num}"
                cp "$best_render" "${OUTPUT_DIR}/best-of/scene${scene_num}/${safe_name}_best.png"
                echo "$best_score" > "${OUTPUT_DIR}/best-of/scene${scene_num}/${safe_name}_score.txt"
            else
                log_message "  No improvement over previous (new=$best_score, old=$prev_score)"
            fi
            
            # Record decision
            DECISIONS+=("Scene $scene_num, Camera $safe_name: $decision (percent=$best_percent, score=$best_score)")
            log_message "  Decision: $decision"
            
            # Write per-camera result
            echo "$best_score" > "${scene_output_dir}/${safe_name}_score.txt"
            
        done <<< "$cameras"
    done
}

# Write final summary
write_summary() {
    log_message ""
    log_message "===== PIPELINE COMPLETE ====="
    log_message "Cameras processed: $CAMERAS_PROCESSED"
    log_message "Cameras improved: $CAMERAS_IMPROVED"
    log_message "Total render time: ${TOTAL_RENDER_TIME}ms"
    
    # Create summary JSON
    local summary_file="${OUTPUT_DIR}/pipeline_summary.json"
    
    cat > "$summary_file" << EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "scenes_processed": "$SCENES",
  "output_directory": "$OUTPUT_DIR",
  "previous_directory": "$PREVIOUS_DIR",
  "cameras_processed": $CAMERAS_PROCESSED,
  "cameras_improved": $CAMERAS_IMPROVED,
  "total_render_time_ms": $TOTAL_RENDER_TIME,
  "score_skip_threshold": $SCORE_SKIP_THRESHOLD,
  "score_upres_threshold": $SCORE_UPRES_THRESHOLD,
  "decisions": [
EOF
    
    for i in "${!DECISIONS[@]}"; do
        echo "    \"${DECISIONS[$i]}\"" >> "$summary_file"
        if [ $i -lt $((${#DECISIONS[@]} - 1)) ]; then
            echo "," >> "$summary_file"
        fi
    done
    
    cat >> "$summary_file" << EOF
  ],
  "errors": [
EOF
    
    for i in "${!ERRORS[@]}"; do
        echo "    \"${ERRORS[$i]}\"" >> "$summary_file"
        if [ $i -lt $((${#ERRORS[@]} - 1)) ]; then
            echo "," >> "$summary_file"
        fi
    done
    
    cat >> "$summary_file" << EOF
  ]
}
EOF
    
    log_message "Summary written to: $summary_file"
}

# Main execution
main() {
    process_pipeline
    write_summary
}

main
