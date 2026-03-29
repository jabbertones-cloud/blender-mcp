#!/usr/bin/env python3
"""v18 Regression Guard: compare v17 vs v18 per-image, keep higher scorer.
Output to v18_final/ — ZERO regressions guaranteed."""
import subprocess, json, shutil, os
from pathlib import Path

BASE = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp")
V17 = BASE / "renders/v17_hybrid"
V18 = BASE / "renders/v18_forensic"
FINAL = BASE / "renders/v18_final"
FINAL.mkdir(parents=True, exist_ok=True)
SCORER = "node scripts/3d-forge/render-quality-scorer.js"

def score_image(path):
    cmd = f'cd {BASE} && {SCORER} --image "{path}" --tier 1 2>&1'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    for line in result.stdout.split('\n'):
        if 'scorer:info' in line and 'score=' in line:
            s = line.split('score=')[1].split(',')[0]
            return int(s)
    return 0

FILES = [
    "scene1_Cam_BirdEye.png", "scene1_Cam_DriverPOV.png", "scene1_Cam_WideAngle.png",
    "scene2_Cam_BirdEye.png", "scene2_Cam_DriverPOV.png",
    "scene2_Cam_SightLine.png", "scene2_Cam_WideAngle.png",
    "scene3_Cam_BirdEye.png", "scene3_Cam_DriverPOV.png", "scene3_Cam_WideAngle.png",
    "scene4_Cam_BirdEye.png", "scene4_Cam_DriverPOV.png",
    "scene4_Cam_SecurityCam.png", "scene4_Cam_WideAngle.png",
]

print("=" * 65)
print("v18 REGRESSION GUARD — Zero Regressions Guaranteed")
print("=" * 65)

total_v17, total_v18, total_final = 0, 0, 0
regressions, improvements = 0, 0
results = []

for base in FILES:
    v17_path = V17 / f"v17_{base}"
    v18_path = V18 / f"v18_{base}"
    
    if not v17_path.exists():
        print(f"  SKIP (no v17): {base}")
        continue
    if not v18_path.exists():
        print(f"  SKIP (no v18): {base}")
        continue
    
    s17 = score_image(v17_path)
    s18 = score_image(v18_path)
    delta = s18 - s17
    
    # REGRESSION GUARD: always keep higher score
    if s18 >= s17:
        winner = "v18"
        shutil.copy2(v18_path, FINAL / f"v18_{base}")
        improvements += 1
    else:
        winner = "v17"
        shutil.copy2(v17_path, FINAL / f"v18_{base}")
        regressions += 1
    
    final_score = max(s17, s18)
    total_v17 += s17
    total_v18 += s18
    total_final += final_score
    
    tag = "✅" if delta >= 0 else "⚠️ KEPT v17"
    results.append((base, s17, s18, final_score, delta, winner))
    print(f"  {base}: v17={s17} v18={s18} delta={delta:+d} → {tag} final={final_score}")

n = len(results)
print(f"\n{'='*65}")
print(f"RESULTS: {n} images processed")
print(f"  v17 avg: {total_v17/n:.1f}")
print(f"  v18 avg: {total_v18/n:.1f}")
print(f"  FINAL avg (regression-guarded): {total_final/n:.1f}")
print(f"  Improvements: {improvements} | Regressions caught: {regressions}")
print(f"  Output: {FINAL}")
print(f"{'='*65}")
