#!/bin/bash
BLENDER="/Applications/Blender.app/Contents/MacOS/Blender"
BASE="/Users/tatsheen/claw-architect/openclaw-blender-mcp"
RENDERS="$BASE/renders/v12_renders"
mkdir -p "$RENDERS"

for SCENE in 1 2 3 4; do
  echo "=== Processing Scene $SCENE ==="
  BLEND="$BASE/renders/v11_scene${SCENE}.blend"
  
  if [ ! -f "$BLEND" ]; then
    echo "ERROR: $BLEND not found"
    continue
  fi
  
  echo "Step 1: Apply v12 fixes to scene $SCENE..."
  $BLENDER --background "$BLEND" \
    --python "$BASE/scripts/v12_apply_all_fixes.py" \
    -- $SCENE \
    2>&1 | tail -30
  
  echo "Step 2: Render all cameras..."
  $BLENDER --background "$BLEND" \
    --python-expr "
import bpy
import os

scene = bpy.context.scene
cameras = [obj for obj in bpy.data.objects if obj.type == 'CAMERA']
print(f'Found {len(cameras)} cameras: {[c.name for c in cameras]}')

outdir = '$RENDERS'
scene_num = $SCENE

for cam in cameras:
    scene.camera = cam
    cam_name = cam.name.replace('Camera_', '').replace(' ', '_').replace('POV', 'POV')
    filepath = f'{outdir}/v12_scene{scene_num}_{cam_name}.png'
    scene.render.filepath = filepath
    print(f'Rendering {cam.name} -> {filepath}')
    bpy.ops.render.render(write_still=True)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f'  SUCCESS: {filepath} ({size} bytes)')
    else:
        print(f'  FAILED: {filepath} not created')
" \
    2>&1 | tail -30
  
  echo "=== Scene $SCENE Complete ==="
done
echo "ALL SCENES RENDERED"
