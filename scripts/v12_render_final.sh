#!/bin/bash
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
BASE="/Users/tatsheen/claw-architect/openclaw-blender-mcp"
RENDERS="$BASE/renders/v12_renders"
mkdir -p "$RENDERS"

# Clear old renders (except test files)
rm -f "$RENDERS"/v12_scene*.png

for SCENE in 1 2 3 4; do
  echo "========================================"
  echo "Processing Scene $SCENE"
  echo "========================================"
  BLEND="$BASE/renders/v11_scene${SCENE}.blend"
  
  if [ ! -f "$BLEND" ]; then
    echo "ERROR: $BLEND not found"
    continue
  fi
  
  echo "Applying fixes and rendering..."
  $BLENDER --background "$BLEND" \
    --python "$BASE/scripts/v12_fix_and_render.py" \
    -- $SCENE \
    2>&1 | tail -50
  
  echo ""
done

echo "========================================"
echo "ALL SCENES RENDERED"
echo "========================================"
ls -lh "$RENDERS"/v12_scene*.png | tail -20
