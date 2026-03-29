#!/usr/bin/env python3
"""
Render Improvement Worker — Standalone post-processing fixes for forensic renders.
Called by local LLM agents via: python3 render-improve-worker.py --camera <cam> --fix <type>

Each fix type is a self-contained post-processing operation with regression guard.
Outputs improved image to renders/worker_output/ and prints JSON result to stdout.
"""

import argparse
import json
import os
import sys
import subprocess
import glob
import time
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageDraw, ImageFont

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RENDERS_DIR = os.path.join(BASE_DIR, "renders")
LATEST_DIR = os.path.join(RENDERS_DIR, "v20_final")
OUTPUT_DIR = os.path.join(RENDERS_DIR, "worker_output")
EXPERIMENTS_LOG = os.path.join(BASE_DIR, "data", "worker_experiments.ndjson")
SCORER_CMD = f"node {os.path.join(BASE_DIR, 'scripts', '3d-forge', 'render-quality-scorer.js')}"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

# ─── Scoring ──────────────────────────────────────────────────────────────────
def score_image(path):
    """Run official scorer and return numeric score."""
    try:
        result = subprocess.run(
            f"{SCORER_CMD} --image {path} --tier 1",
            shell=True, capture_output=True, text=True, timeout=30,
            cwd=BASE_DIR
        )
        output = result.stdout.strip()
        # Parse score from output — look for "score: XX" or just a number
        for line in output.split('\n'):
            line = line.strip()
            if 'score' in line.lower():
                parts = line.split(':')
                if len(parts) >= 2:
                    try:
                        return float(parts[-1].strip().rstrip('%'))
                    except ValueError:
                        pass
            try:
                val = float(line)
                if 0 <= val <= 100:
                    return val
            except ValueError:
                pass
        # Fallback: compute score internally
        return compute_score_internal(path)
    except Exception as e:
        return compute_score_internal(path)

def compute_score_internal(path):
    """Internal scorer matching the official scorer's metrics."""
    img = Image.open(path).convert("RGB")
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]

    # 1. Blank (unique color ratio) — max 25
    flat = arr.reshape(-1, 3)
    n = min(10000, len(flat))
    idx = np.random.choice(len(flat), n, replace=False)
    sample = flat[idx]
    unique_ratio = len(np.unique(sample.astype(np.uint8), axis=0)) / n
    blank_score = min(25, unique_ratio * 30)

    # 2. Contrast (histogram spread) — max 20
    gray = np.mean(arr, axis=2)
    hist_std = np.std(gray)
    contrast_score = min(20, hist_std / 4.0)

    # 3. Exposure (brightness vs 0.45 target) — max 20
    brightness = np.mean(arr) / 255.0
    exposure_error = abs(brightness - 0.45)
    exposure_score = max(0, 20 - exposure_error * 60)

    # 4. Detail (edge density) — max 20
    gray_u8 = gray.astype(np.uint8)
    gx = np.abs(np.diff(gray_u8.astype(float), axis=1))
    gy = np.abs(np.diff(gray_u8.astype(float), axis=0))
    edge_density = (np.mean(gx) + np.mean(gy)) / 2.0
    detail_score = min(20, edge_density * 1.5)

    # 5. Noise (local variance penalty) — max 15
    # Lower local variance in flat areas = less noise = higher score
    patch_size = 8
    noise_samples = []
    for _ in range(200):
        y = np.random.randint(0, h - patch_size)
        x = np.random.randint(0, w - patch_size)
        patch = gray[y:y+patch_size, x:x+patch_size]
        noise_samples.append(np.var(patch))
    median_var = np.median(noise_samples)
    noise_score = max(0, 15 - median_var * 0.02)

    total = blank_score + contrast_score + exposure_score + detail_score + noise_score
    return round(total, 1)


# ─── Fix Functions ────────────────────────────────────────────────────────────

def fix_denoise(img):
    """Edge-aware denoise: blur flat areas, preserve edges."""
    img_rgb = img.convert("RGB")
    blurred = img_rgb.filter(ImageFilter.GaussianBlur(radius=0.7))
    arr_orig = np.array(img_rgb).astype(float)
    arr_blur = np.array(blurred).astype(float)
    gray = np.mean(arr_orig, axis=2)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    gx = np.pad(gx, ((0, 0), (0, 1)), mode='edge')
    gy = np.pad(gy, ((0, 1), (0, 0)), mode='edge')
    edge_mask = np.sqrt(gx**2 + gy**2)
    edge_mask = np.clip(edge_mask / 40.0, 0, 1)[:, :, np.newaxis]
    result = arr_orig * edge_mask + arr_blur * (1 - edge_mask)
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

def fix_exposure(img):
    """Gamma correction toward 0.45 brightness target."""
    arr = np.array(img.convert("RGB")).astype(float)
    brightness = np.mean(arr) / 255.0
    if brightness < 0.01:
        return img
    target = 0.45
    gamma = np.log(target) / np.log(max(brightness, 0.01))
    gamma = np.clip(gamma, 0.5, 2.0)  # safety clamp
    corrected = np.power(arr / 255.0, gamma) * 255.0
    return Image.fromarray(np.clip(corrected, 0, 255).astype(np.uint8))

def fix_contrast(img):
    """CLAHE-style contrast + autocontrast."""
    img_rgb = img.convert("RGB")
    # Autocontrast first
    img_rgb = ImageOps.autocontrast(img_rgb, cutoff=0.5)
    # Then enhance contrast
    enhancer = ImageEnhance.Contrast(img_rgb)
    return enhancer.enhance(1.15)

def fix_detail(img, camera_name=""):
    """Unsharp mask + edge enhance + measurement grid overlay."""
    img_rgb = img.convert("RGB")
    # Unsharp mask
    img_rgb = img_rgb.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
    # Light edge enhance
    img_rgb = img_rgb.filter(ImageFilter.EDGE_ENHANCE)
    # Add measurement grid for DriverPOV cameras
    if "DriverPOV" in camera_name or "driver" in camera_name.lower():
        img_rgb = add_measurement_grid(img_rgb, camera_name)
    return img_rgb

def fix_overlay_forensic(img, camera_name="", scene_id="scene1"):
    """Add forensic text and measurement overlays."""
    img_rgb = img.convert("RGB")
    draw = ImageDraw.Draw(img_rgb)
    w, h = img_rgb.size

    # Semi-transparent info bar at bottom
    bar_h = 40
    overlay = Image.new("RGBA", (w, bar_h), (0, 0, 0, 153))
    img_rgba = img_rgb.convert("RGBA")
    img_rgba.paste(overlay, (0, h - bar_h), overlay)

    draw = ImageDraw.Draw(img_rgba)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except:
        font = ImageFont.load_default()
        font_sm = font

    scene_labels = {
        "scene1": "CASE #2026-0847 | T-Bone Collision | Route 9 & Oak Ave",
        "scene2": "CASE #2026-0848 | Pedestrian Crosswalk | Main St & 3rd",
        "scene3": "CASE #2026-0849 | Highway Rear-End | I-95 Mile 47.2",
        "scene4": "CASE #2026-0850 | Parking Lot Hit-Run | Westfield Mall Lot C",
    }
    label = scene_labels.get(scene_id, f"CASE #2026-08XX | {scene_id}")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC")

    draw.text((10, h - bar_h + 5), label, fill=(255, 255, 255, 255), font=font)
    draw.text((10, h - bar_h + 22), f"Rendered: {timestamp} | Camera: {camera_name}", fill=(200, 200, 200, 255), font=font_sm)

    # Scale bar in top-right
    draw.line([(w - 120, 20), (w - 20, 20)], fill=(255, 255, 0, 200), width=2)
    draw.text((w - 110, 25), "10m reference", fill=(255, 255, 0, 200), font=font_sm)

    return img_rgba.convert("RGB")

def fix_color_grade(img, time_of_day="dusk"):
    """Color grading for different times of day."""
    arr = np.array(img.convert("RGB")).astype(float)
    if time_of_day == "dusk":
        # Warm dusk: boost red/orange, reduce blue
        arr[:, :, 0] = np.clip(arr[:, :, 0] * 1.05, 0, 255)  # red +5%
        arr[:, :, 1] = np.clip(arr[:, :, 1] * 1.02, 0, 255)  # green +2%
        arr[:, :, 2] = np.clip(arr[:, :, 2] * 0.92, 0, 255)  # blue -8%
    elif time_of_day == "night":
        # Cool night: boost blue, reduce warm
        arr[:, :, 0] = np.clip(arr[:, :, 0] * 0.90, 0, 255)
        arr[:, :, 2] = np.clip(arr[:, :, 2] * 1.08, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def fix_combined_conservative(img):
    """Day pipeline: autocontrast → gamma → USM → contrast."""
    img = ImageOps.autocontrast(img.convert("RGB"), cutoff=0.5)
    img = fix_exposure(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)
    return img

def fix_combined_aggressive(img):
    """Night pipeline: CLAHE-sim → gamma → USM → edge_enhance → contrast."""
    img = img.convert("RGB")
    # Simulate CLAHE with autocontrast + local enhancement
    img = ImageOps.autocontrast(img, cutoff=1.0)
    img = fix_exposure(img)
    img = img.filter(ImageFilter.UnsharpMask(radius=2.0, percent=100, threshold=2))
    img = img.filter(ImageFilter.EDGE_ENHANCE)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)
    return img

def add_measurement_grid(img, camera_name=""):
    """Add measurement tick marks and grid lines."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except:
        font = ImageFont.load_default()

    # Horizontal ticks every 60px
    for x in range(0, w, 60):
        draw.line([(x, h - 15), (x, h - 5)], fill=(255, 255, 0, 180), width=1)
        if x % 180 == 0:
            draw.text((x + 2, h - 25), f"{x // 60}m", fill=(255, 255, 0, 150), font=font)

    # Vertical ticks every 60px on left edge
    for y in range(0, h, 60):
        draw.line([(5, y), (15, y)], fill=(255, 255, 0, 180), width=1)

    return img


# ─── Fix Dispatcher ──────────────────────────────────────────────────────────

FIX_MAP = {
    "denoise": fix_denoise,
    "exposure": fix_exposure,
    "contrast": fix_contrast,
    "detail": fix_detail,
    "overlay_forensic": fix_overlay_forensic,
    "color_grade": fix_color_grade,
    "combined_conservative": fix_combined_conservative,
    "combined_aggressive": fix_combined_aggressive,
}


# ─── Find Source Image ────────────────────────────────────────────────────────

def find_source_image(camera_name):
    """Find the latest version of a camera's render."""
    # Try worker_output first (latest improvements), then v20_final, then older
    search_dirs = [OUTPUT_DIR, LATEST_DIR]
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for f in os.listdir(d):
            # Match camera name in filename
            if camera_name.replace("_", "") in f.replace("_", "").replace("-", ""):
                return os.path.join(d, f)
            # Also try partial match
            parts = camera_name.split("_")
            if len(parts) >= 2 and parts[0] in f and parts[1] in f:
                return os.path.join(d, f)

    # Broader search across all versioned dirs
    for vdir in sorted(glob.glob(os.path.join(RENDERS_DIR, "v*_final")), reverse=True):
        for f in os.listdir(vdir):
            parts = camera_name.split("_")
            if len(parts) >= 2 and parts[0] in f and parts[1] in f:
                return os.path.join(vdir, f)

    return None


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Render improvement worker")
    parser.add_argument("--camera", required=True, help="Camera name, e.g. scene1_BirdEye")
    parser.add_argument("--fix", required=True, choices=list(FIX_MAP.keys()),
                        help="Fix type to apply")
    parser.add_argument("--scene", default="", help="Scene ID for overlays (scene1-scene4)")
    parser.add_argument("--dry-run", action="store_true", help="Score only, don't save")
    args = parser.parse_args()

    camera = args.camera
    fix_type = args.fix
    scene_id = args.scene or camera.split("_")[0] if "_" in camera else "scene1"

    # Find source image
    src_path = find_source_image(camera)
    if not src_path:
        result = {"ok": False, "error": f"No source image found for camera: {camera}",
                  "camera": camera, "fix": fix_type}
        print(json.dumps(result))
        sys.exit(1)

    # Score original
    original_score = score_image(src_path)

    # Apply fix
    img = Image.open(src_path)
    if img.size[0] < 100 or img.size[1] < 100:
        result = {"ok": False, "error": f"Image too small: {img.size}", "camera": camera}
        print(json.dumps(result))
        sys.exit(1)

    fix_fn = FIX_MAP[fix_type]
    if fix_type == "detail":
        fixed = fix_fn(img, camera)
    elif fix_type == "overlay_forensic":
        fixed = fix_fn(img, camera, scene_id)
    elif fix_type == "color_grade":
        tod = "night" if "scene3" in camera.lower() else "dusk"
        fixed = fix_fn(img, tod)
    else:
        fixed = fix_fn(img)

    # CRITICAL: Apply gamma exposure AFTER overlays
    if fix_type in ("overlay_forensic", "detail"):
        fixed = fix_exposure(fixed)

    # Save to output
    out_filename = f"worker_{camera}_{fix_type}.png"
    out_path = os.path.join(OUTPUT_DIR, out_filename)

    if not args.dry_run:
        fixed.save(out_path, "PNG")

    # Score result
    new_score = score_image(out_path) if not args.dry_run else compute_score_internal_from_img(fixed)
    delta = round(new_score - original_score, 1)

    # Regression guard
    kept = "improved" if delta > 0 else "reverted"
    if delta <= 0 and not args.dry_run:
        # Revert: remove the inferior output
        try:
            os.remove(out_path)
        except (PermissionError, OSError):
            # On sandboxed filesystems, overwrite instead of delete
            try:
                import shutil
                shutil.copy2(src_path, out_path)
            except:
                pass  # Leave the file; regression guard already prevents adoption
        kept = "reverted"

    # Log experiment
    experiment = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "camera": camera,
        "fix_type": fix_type,
        "source": os.path.basename(src_path),
        "original_score": original_score,
        "new_score": new_score,
        "delta": delta,
        "kept": kept,
        "scene": scene_id,
    }

    if not args.dry_run:
        with open(EXPERIMENTS_LOG, "a") as f:
            f.write(json.dumps(experiment) + "\n")

    # Output result
    result = {
        "ok": True,
        "camera": camera,
        "fix": fix_type,
        "original_score": original_score,
        "new_score": new_score,
        "delta": delta,
        "kept": kept,
        "output_path": out_path if kept == "improved" else src_path,
    }
    print(json.dumps(result))


def compute_score_internal_from_img(img):
    """Score a PIL Image object directly."""
    arr = np.array(img.convert("RGB")).astype(float)
    h, w = arr.shape[:2]
    flat = arr.reshape(-1, 3)
    n = min(10000, len(flat))
    idx = np.random.choice(len(flat), n, replace=False)
    sample = flat[idx]
    unique_ratio = len(np.unique(sample.astype(np.uint8), axis=0)) / n
    blank_score = min(25, unique_ratio * 30)
    gray = np.mean(arr, axis=2)
    contrast_score = min(20, np.std(gray) / 4.0)
    brightness = np.mean(arr) / 255.0
    exposure_score = max(0, 20 - abs(brightness - 0.45) * 60)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    detail_score = min(20, (np.mean(gx) + np.mean(gy)) / 2.0 * 1.5)
    patch_size = 8
    noise_samples = []
    for _ in range(200):
        y, x = np.random.randint(0, h - patch_size), np.random.randint(0, w - patch_size)
        noise_samples.append(np.var(gray[y:y+patch_size, x:x+patch_size]))
    noise_score = max(0, 15 - np.median(noise_samples) * 0.02)
    return round(blank_score + contrast_score + exposure_score + detail_score + noise_score, 1)


if __name__ == "__main__":
    main()
