#!/usr/bin/env python3
"""
Multi-round iterative improvement — the real deal.
Each round takes the BEST version of each camera, tries ALL applicable fixes,
keeps the winner, and feeds it into the next round.
"""
import os, sys, json, time, shutil, glob
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V20_DIR = os.path.join(BASE_DIR, "renders", "v20_final")
WORK_DIR = os.path.join(BASE_DIR, "renders", "worker_rounds")
BEST_DIR = os.path.join(BASE_DIR, "renders", "worker_best")
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs(BEST_DIR, exist_ok=True)

NUM_ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 3

# ─── Scorer ───────────────────────────────────────────────────────────────────
def score(img):
    arr = np.array(img.convert("RGB")).astype(float)
    h, w = arr.shape[:2]
    flat = arr.reshape(-1, 3)
    n = min(10000, len(flat))
    idx = np.random.choice(len(flat), n, replace=False)
    blank = min(25, len(np.unique(flat[idx].astype(np.uint8), axis=0)) / n * 30)
    gray = np.mean(arr, axis=2)
    contrast = min(20, np.std(gray) / 4.0)
    brightness = np.mean(arr) / 255.0
    exposure = max(0, 20 - abs(brightness - 0.45) * 60)
    gx = np.abs(np.diff(gray, axis=1)); gy = np.abs(np.diff(gray, axis=0))
    detail = min(20, (np.mean(gx) + np.mean(gy)) / 2.0 * 1.5)
    ns = []
    for _ in range(200):
        y, x = np.random.randint(0, h-8), np.random.randint(0, w-8)
        ns.append(np.var(gray[y:y+8, x:x+8]))
    noise = max(0, 15 - np.median(ns) * 0.02)
    return round(blank + contrast + exposure + detail + noise, 1)

# ─── Fix Functions ────────────────────────────────────────────────────────────
def fix_denoise(img):
    rgb = img.convert("RGB")
    blurred = rgb.filter(ImageFilter.GaussianBlur(radius=0.7))
    a = np.array(rgb).astype(float); b = np.array(blurred).astype(float)
    g = np.mean(a, axis=2)
    gx = np.pad(np.abs(np.diff(g, axis=1)), ((0,0),(0,1)), mode='edge')
    gy = np.pad(np.abs(np.diff(g, axis=0)), ((0,1),(0,0)), mode='edge')
    mask = np.clip(np.sqrt(gx**2 + gy**2) / 40.0, 0, 1)[:,:,np.newaxis]
    return Image.fromarray(np.clip(a * mask + b * (1 - mask), 0, 255).astype(np.uint8))

def fix_exposure(img):
    arr = np.array(img.convert("RGB")).astype(float)
    brightness = np.mean(arr) / 255.0
    if brightness < 0.01: return img
    gamma = np.clip(np.log(0.45) / np.log(max(brightness, 0.01)), 0.5, 2.0)
    return Image.fromarray(np.clip(np.power(arr / 255.0, gamma) * 255.0, 0, 255).astype(np.uint8))

def fix_contrast(img):
    rgb = ImageOps.autocontrast(img.convert("RGB"), cutoff=0.5)
    return ImageEnhance.Contrast(rgb).enhance(1.15)

def fix_detail(img):
    rgb = img.convert("RGB")
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
    return rgb.filter(ImageFilter.EDGE_ENHANCE)

def fix_detail_grid(img):
    """Detail + measurement grid overlay."""
    rgb = fix_detail(img)
    draw = ImageDraw.Draw(rgb)
    w, h = rgb.size
    try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except: font = ImageFont.load_default()
    for x in range(0, w, 60):
        draw.line([(x, h-15), (x, h-5)], fill=(255,255,0,180), width=1)
        if x % 180 == 0:
            draw.text((x+2, h-25), f"{x//60}m", fill=(255,255,0,150), font=font)
    for y in range(0, h, 60):
        draw.line([(5,y),(15,y)], fill=(255,255,0,180), width=1)
    return rgb

def fix_combined_day(img):
    img = ImageOps.autocontrast(img.convert("RGB"), cutoff=0.5)
    img = fix_exposure(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
    return ImageEnhance.Contrast(img).enhance(1.1)

def fix_combined_night(img):
    img = ImageOps.autocontrast(img.convert("RGB"), cutoff=1.0)
    img = fix_exposure(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=2.0, percent=100, threshold=2))
    img = img.filter(ImageFilter.EDGE_ENHANCE)
    return ImageEnhance.Contrast(img).enhance(1.2)

def fix_color_dusk(img):
    arr = np.array(img.convert("RGB")).astype(float)
    arr[:,:,0] = np.clip(arr[:,:,0] * 1.05, 0, 255)
    arr[:,:,1] = np.clip(arr[:,:,1] * 1.02, 0, 255)
    arr[:,:,2] = np.clip(arr[:,:,2] * 0.92, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

FIXES = {
    "denoise": fix_denoise,
    "exposure": fix_exposure,
    "contrast": fix_contrast,
    "detail": fix_detail,
    "detail_grid": fix_detail_grid,
    "combined_day": fix_combined_day,
    "combined_night": fix_combined_night,
    "color_dusk": fix_color_dusk,
}

# Camera → applicable fix types
CAM_FIXES = {
    "BirdEye": ["denoise", "exposure", "contrast", "combined_day"],
    "DriverPOV": ["detail", "detail_grid", "exposure", "contrast", "combined_day"],
    "WideAngle": ["exposure", "contrast", "detail", "combined_day", "color_dusk"],
    "SightLine": ["contrast", "detail", "exposure", "combined_day"],
    "SecurityCam": ["contrast", "denoise", "exposure"],
}

# ─── Main Loop ────────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"  ITERATIVE IMPROVEMENT — {NUM_ROUNDS} rounds")
print(f"{'='*70}\n")

# Initialize: copy v20 to best_dir as starting point
cameras = {}
for f in sorted(os.listdir(V20_DIR)):
    if not f.endswith(".png"): continue
    # Extract camera type from filename like v20_scene1_Cam_BirdEye.png
    parts = f.replace(".png", "").split("_")
    # scene1_Cam_BirdEye
    scene = parts[1]  # scene1
    cam_type = parts[-1]  # BirdEye
    cam_key = f"{scene}_{cam_type}"

    src = os.path.join(V20_DIR, f)
    dst = os.path.join(BEST_DIR, f)
    shutil.copy2(src, dst)

    img = Image.open(src)
    s = score(img)
    cameras[cam_key] = {"file": dst, "score": s, "cam_type": cam_type, "scene": scene, "orig_name": f}
    print(f"  Baseline {cam_key}: {s}")

print(f"\n  Baseline average: {np.mean([c['score'] for c in cameras.values()]):.1f}\n")

total_improvements = 0
all_experiments = []

for round_num in range(1, NUM_ROUNDS + 1):
    print(f"\n{'─'*70}")
    print(f"  ROUND {round_num}/{NUM_ROUNDS}")
    print(f"{'─'*70}")

    round_improvements = 0

    for cam_key, cam_info in sorted(cameras.items(), key=lambda x: x[1]["score"]):
        cam_type = cam_info["cam_type"]
        fixes_to_try = CAM_FIXES.get(cam_type, ["exposure", "contrast", "denoise"])
        current_score = cam_info["score"]
        current_img = Image.open(cam_info["file"])

        best_score = current_score
        best_img = current_img
        best_fix = None

        for fix_name in fixes_to_try:
            fix_fn = FIXES[fix_name]
            try:
                candidate = fix_fn(current_img.copy())
                # Apply exposure AFTER overlay-type fixes
                if fix_name in ("detail_grid",):
                    candidate = fix_exposure(candidate)
                s = score(candidate)
                delta = round(s - current_score, 1)

                exp = {
                    "round": round_num,
                    "camera": cam_key,
                    "fix": fix_name,
                    "before": current_score,
                    "after": s,
                    "delta": delta,
                    "kept": bool(s > best_score),
                }
                all_experiments.append(exp)

                if s > best_score:
                    best_score = s
                    best_img = candidate
                    best_fix = fix_name
            except Exception as e:
                print(f"    ERROR {cam_key}+{fix_name}: {e}")

        if best_fix:
            delta = round(best_score - current_score, 1)
            print(f"  {cam_key}: {current_score} → {best_score} (+{delta}) via {best_fix}")
            best_img.save(cam_info["file"], "PNG")
            cameras[cam_key]["score"] = best_score
            round_improvements += 1
            total_improvements += 1
        else:
            print(f"  {cam_key}: {current_score} (no improvement found)")

    avg = np.mean([c["score"] for c in cameras.values()])
    print(f"\n  Round {round_num} average: {avg:.1f} | Improvements: {round_improvements}/14")

    if round_improvements == 0:
        print(f"\n  PLATEAU: No improvements in round {round_num}. Stopping.")
        break

# ─── Final Summary ────────────────────────────────────────────────────────────
print(f"\n{'='*70}")
print(f"  FINAL RESULTS after {round_num} rounds")
print(f"{'='*70}")
for cam_key, cam_info in sorted(cameras.items()):
    print(f"  {cam_key}: {cam_info['score']}")
avg = np.mean([c["score"] for c in cameras.values()])
print(f"\n  Final average: {avg:.1f}")
print(f"  Total improvements: {total_improvements}")
print(f"  Best images saved to: {BEST_DIR}")

# Save experiments log
log_path = os.path.join(BASE_DIR, "data", "improvement_rounds.json")
with open(log_path, "w") as f:
    json.dump({
        "rounds": round_num,
        "final_avg": round(avg, 1),
        "total_improvements": total_improvements,
        "cameras": {k: v["score"] for k, v in cameras.items()},
        "experiments": all_experiments,
    }, f, indent=2)
print(f"  Experiments log: {log_path}")
print(f"{'='*70}")
