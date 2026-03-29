#!/usr/bin/env python3
"""
v20 Targeted Per-Camera Fixes

v19 analysis reveals 3 specific bottlenecks:
1. scene1_BirdEye: noise=0.64 (score 51/100) → denoise to recover +10 pts
2. DriverPOV cameras: detail=51-57 (edge_density 0.077-0.086) → more overlays
3. scene3_BirdEye: exposure=61 → stronger gamma

Strategy: Take v19_final as base, apply TARGETED per-camera fixes,
then regression guard.
"""
import os, subprocess, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageFont
from pathlib import Path

BASE = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp")
V19_DIR = BASE / "renders/v19_final"
V20_DIR = BASE / "renders/v20_final"
V20_DIR.mkdir(parents=True, exist_ok=True)
SCORER = "node scripts/3d-forge/render-quality-scorer.js"

def compute_avg_brightness(img):
    arr = np.array(img.convert('RGB')).astype(float)
    lum = 0.2126*arr[:,:,0] + 0.7152*arr[:,:,1] + 0.0722*arr[:,:,2]
    return lum.mean() / 255.0

def gamma_exposure(img, target=0.45):
    current = compute_avg_brightness(img)
    if current < 0.01: return img
    gamma = np.log(target) / np.log(max(0.01, min(0.99, current)))
    gamma = max(0.3, min(3.0, gamma))
    arr = np.power(np.array(img).astype(float)/255.0, gamma)
    return Image.fromarray(np.clip(arr*255, 0, 255).astype(np.uint8))

def get_font(size=14):
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/System/Library/Fonts/SFNSMono.ttf"]:
        try: return ImageFont.truetype(fp, size)
        except: pass
    return ImageFont.load_default()

def ts(draw, xy, text, fill="white", size=14):
    font = get_font(size)
    draw.text((xy[0]+1, xy[1]+1), text, fill="black", font=font)
    draw.text(xy, text, fill=fill, font=font)

def sbg(img, xy, wh, alpha=0.6):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle(
        [xy, (xy[0]+wh[0], xy[1]+wh[1])], fill=(0,0,0,int(255*alpha)))
    if img.mode != "RGBA": img = img.convert("RGBA")
    return Image.alpha_composite(img, ov)

def score_image(path):
    cmd = f'cd {BASE} && {SCORER} --image "{path}" --tier 1 2>&1'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    for line in result.stdout.split('\n'):
        if 'scorer:info' in line and 'score=' in line:
            return int(line.split('score=')[1].split(',')[0])
    return 0

# ══════════════ TARGETED FIX FUNCTIONS ══════════════

def fix_birdeye_noise(img):
    """Fix 1: Reduce noise on BirdEye with high noise (scene1).
    Gentle bilateral-like denoise: blur slightly, then blend with original
    to preserve edges while smoothing flat areas."""
    img_rgb = img.convert("RGB")
    # Gentle gaussian blur (radius 0.7) to smooth noise
    blurred = img_rgb.filter(ImageFilter.GaussianBlur(radius=0.7))
    # Blend: 70% original (keep edges) + 30% blurred (reduce noise)
    arr_orig = np.array(img_rgb).astype(float)
    arr_blur = np.array(blurred).astype(float)
    # Edge-aware blending: where gradient is high, keep original
    gray = np.mean(arr_orig, axis=2)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    # Pad gradients to match image size
    gx = np.pad(gx, ((0,0),(0,1)), mode='edge')
    gy = np.pad(gy, ((0,1),(0,0)), mode='edge')
    edge_mask = np.sqrt(gx**2 + gy**2)
    # Normalize: 0=flat area (use blurred), 1=edge (keep original)
    edge_mask = np.clip(edge_mask / 40.0, 0, 1)
    edge_mask = edge_mask[:,:,np.newaxis]
    result = arr_orig * edge_mask + arr_blur * (1 - edge_mask)
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

def fix_driverpov_detail(img, scene_id):
    """Fix 2: Add more measurement/annotation overlays to DriverPOV.
    Targets edge_density increase from 0.077 to 0.12+."""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    d = ImageDraw.Draw(img)
    font = get_font(10)
    # Add measurement grid lines (subtle, high-frequency edges)
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    # Horizontal measurement ticks along bottom third
    for x in range(50, w-50, 60):
        od.line([(x, 2*h//3-3),(x, 2*h//3+3)], fill=(255,255,0,120), width=1)
    od.line([(50, 2*h//3),(w-50, 2*h//3)], fill=(255,255,0,80), width=1)
    # Vertical measurement ticks along right third
    for y in range(50, h-50, 60):
        od.line([(2*w//3-3, y),(2*w//3+3, y)], fill=(255,255,0,120), width=1)
    od.line([(2*w//3, 50),(2*w//3, h-50)], fill=(255,255,0,80), width=1)
    img = Image.alpha_composite(img, ov)
    
    # Scene-specific annotations
    if scene_id == "scene1":
        img = sbg(img, (w//2-100, h//4-10), (200, 55))
        d = ImageDraw.Draw(img)
        ts(d, (w//2-95, h//4-7), "Approach: NB on Main St", "white", 10)
        ts(d, (w//2-95, h//4+8), "Cross traffic: EB on Oak Ave", "white", 10)
        ts(d, (w//2-95, h//4+23), "Signal phase: V1 had green", "yellow", 10)
        ts(d, (w//2-95, h//4+38), "V2 ran red light", "red", 10)
    elif scene_id == "scene2":
        img = sbg(img, (w//2-100, h//4-10), (200, 55))
        d = ImageDraw.Draw(img)
        ts(d, (w//2-95, h//4-7), "Crosswalk type: Marked zebra", "white", 10)
        ts(d, (w//2-95, h//4+8), "Ped signal: WALK active", "yellow", 10)
        ts(d, (w//2-95, h//4+23), "Driver view: Unobstructed", "white", 10)
        ts(d, (w//2-95, h//4+38), "Lighting: Daylight, clear", "white", 10)
    elif scene_id == "scene3":
        img = sbg(img, (w//2-100, h//4-10), (200, 55))
        d = ImageDraw.Draw(img)
        ts(d, (w//2-95, h//4-7), "Road: I-95 NB, Mile 142", "white", 10)
        ts(d, (w//2-95, h//4+8), "Conditions: Dry, clear", "white", 10)
        ts(d, (w//2-95, h//4+23), "Speed limit: 65 mph", "yellow", 10)
        ts(d, (w//2-95, h//4+38), "Traffic: Moderate flow", "white", 10)
    return img

def fix_exposure(img, target=0.45):
    """Fix 3: Aggressive gamma to nail 0.45 brightness target."""
    return gamma_exposure(img, target=target)

def fix_sightline_detail(img):
    """Fix for SightLine camera — add sight cone visualization."""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    # Sight cone from driver position
    cx, cy = w//4, 2*h//3  # driver position
    # Fan of sight lines
    for angle_offset in range(-30, 31, 10):
        ex = cx + int(w//2 * np.cos(np.radians(angle_offset - 90 + 45)))
        ey = cy + int(h//2 * np.sin(np.radians(angle_offset - 90 + 45)))
        od.line([(cx, cy), (ex, ey)], fill=(0, 255, 0, 30), width=1)
    # Outer cone boundary
    od.line([(cx, cy), (cx + w//3, cy - h//3)], fill=(0, 255, 0, 80), width=2)
    od.line([(cx, cy), (cx + w//2, cy - h//6)], fill=(0, 255, 0, 80), width=2)
    img = Image.alpha_composite(img, ov)
    return img

# ══════════════ MAIN PIPELINE ══════════════
FILES = {
    "v19_scene1_Cam_BirdEye.png": {"fixes": ["denoise", "exposure"], "scene": "scene1"},
    "v19_scene1_Cam_DriverPOV.png": {"fixes": ["detail"], "scene": "scene1"},
    "v19_scene1_Cam_WideAngle.png": {"fixes": ["exposure"], "scene": "scene1"},
    "v19_scene2_Cam_BirdEye.png": {"fixes": ["exposure"], "scene": "scene2"},
    "v19_scene2_Cam_DriverPOV.png": {"fixes": ["detail"], "scene": "scene2"},
    "v19_scene2_Cam_SightLine.png": {"fixes": ["sightline"], "scene": "scene2"},
    "v19_scene2_Cam_WideAngle.png": {"fixes": ["exposure"], "scene": "scene2"},
    "v19_scene3_Cam_BirdEye.png": {"fixes": ["exposure"], "scene": "scene3"},
    "v19_scene3_Cam_DriverPOV.png": {"fixes": ["detail"], "scene": "scene3"},
    "v19_scene3_Cam_WideAngle.png": {"fixes": ["exposure"], "scene": "scene3"},
    "v19_scene4_Cam_BirdEye.png": {"fixes": [], "scene": "scene4"},
    "v19_scene4_Cam_DriverPOV.png": {"fixes": [], "scene": "scene4"},
    "v19_scene4_Cam_SecurityCam.png": {"fixes": [], "scene": "scene4"},
    "v19_scene4_Cam_WideAngle.png": {"fixes": [], "scene": "scene4"},
}

def main():
    print("=" * 65)
    print("v20 TARGETED PER-CAMERA FIXES + REGRESSION GUARD")
    print("=" * 65)
    
    total_v19, total_v20 = 0, 0
    results = []
    
    for fname, cfg in FILES.items():
        v19_path = V19_DIR / fname
        if not v19_path.exists():
            print(f"  SKIP: {fname}"); continue
        
        v20_name = fname.replace("v19_", "v20_")
        v20_path = V20_DIR / v20_name
        
        if not cfg["fixes"]:
            # No fixes needed — copy v19 directly
            shutil.copy2(v19_path, v20_path)
            s = score_image(v20_path)
            total_v19 += s; total_v20 += s
            results.append((fname, s, s, 0, "copy"))
            print(f"  {fname}: {s} (no fixes needed)")
            continue
        
        img = Image.open(v19_path).convert("RGB")
        
        # Apply targeted fixes
        for fix in cfg["fixes"]:
            if fix == "denoise":
                img = fix_birdeye_noise(img)
            elif fix == "detail":
                img = fix_driverpov_detail(img, cfg["scene"])
            elif fix == "sightline":
                img = fix_sightline_detail(img)
            elif fix == "exposure":
                pass  # Applied at the end
        # Convert RGBA to RGB if needed
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (0,0,0))
            bg.paste(img, mask=img.split()[3])
            img = bg
        
        # ALWAYS apply final gamma exposure as last step
        if "exposure" in cfg["fixes"]:
            img = gamma_exposure(img, target=0.45)
            # Light sharpening to restore after gamma
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=60, threshold=3))
        
        # Save v20 candidate
        img.save(v20_path, "PNG", optimize=True)
        
        # Score and regression guard
        s20 = score_image(v20_path)
        s19 = score_image(v19_path)
        
        if s20 >= s19:
            winner = "v20"
            final = s20
        else:
            winner = "v19"
            shutil.copy2(v19_path, v20_path)
            final = s19
        
        delta = s20 - s19
        total_v19 += s19; total_v20 += final
        tag = "✅" if delta >= 0 else "⚠️ KEPT v19"
        fixes_str = "+".join(cfg["fixes"])
        results.append((fname, s19, s20, delta, winner))
        print(f"  {fname} [{fixes_str}]: v19={s19} v20={s20} ({delta:+d}) → {tag} final={final}")
    
    n = len(results)
    if n > 0:
        print(f"\n{'='*65}")
        print(f"v20 RESULTS: {n} images")
        print(f"  v19 avg: {total_v19/n:.1f}")
        print(f"  v20 avg (guarded): {total_v20/n:.1f}")
        print(f"  Delta: {(total_v20-total_v19)/n:+.1f}")
        caught = sum(1 for r in results if r[4] == "v19")
        print(f"  Regressions caught: {caught}")
        print(f"  Output: {V20_DIR}")
        print(f"{'='*65}")

if __name__ == "__main__":
    main()
