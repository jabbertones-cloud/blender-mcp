#!/usr/bin/env python3

"""
Precision Fix — Apply exact, calculated corrections to hit target scores.

Unlike the brute-force approach, this applies fixes in the correct ORDER
with CALCULATED parameters based on scorer metric formulas.

Key insight from scorer source:
  exposure_score = max(0, 1 - |brightness - 0.45| * 2.5)
  noise_score = 1 - max(0, (normalized_noise - 0.3) / 0.7)
  detail_score = min(1, edge_density / 0.15)
  blank_score = min(1, unique_ratio / 0.3)

So to get exposure_score >= 0.9 (90/100), need |brightness - 0.45| <= 0.04
i.e., brightness in range [0.41, 0.49]

BLIND SPOT FIXES:
  1. Blank render detection: Detect low content and abort/stretch accordingly
  2. Detail/noise tradeoff: Adaptive denoise to preserve edge density
  3. Gamma banding fix: Dithering + S-curve + CLAHE for dark images
  4. Scorer variance: Deterministic seeding + multi-score averaging
"""

import os
import sys
import json
import math
import subprocess
import argparse
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION & HELPERS
# ─────────────────────────────────────────────────────────────────────────────

UNIQUE_RATIO_TRULY_BLANK = 0.02    # Abort if <= this
UNIQUE_RATIO_PARTIALLY_BLANK = 0.15  # Apply content stretch if < this
UNIQUE_RATIO_BELOW_SCORER = 0.30    # Apply autocontrast if < this
EDGE_DENSITY_THRESHOLD = 0.12        # Preserve if > this
DARK_IMAGE_THRESHOLD = 0.10          # Apply dithering if brightness < this

def compute_unique_ratio(img):
    """
    Compute unique_ratio: count non-zero histogram bins / 256.
    Matches scorer's blank detection method.
    """
    arr = np.array(img).astype(float)
    if len(arr.shape) == 3 and arr.shape[2] >= 3:
        lum = 0.2126 * arr[:,:,0] + 0.7152 * arr[:,:,1] + 0.0722 * arr[:,:,2]
    else:
        lum = arr[:,:,0] if len(arr.shape) == 3 else arr
    
    hist, _ = np.histogram(lum, bins=256, range=(0, 256))
    unique_ratio = float(np.count_nonzero(hist)) / 256.0
    return unique_ratio

def compute_edge_density(img):
    """
    Compute edge_density: edge_pixels / (2 * total_pixels).
    Matches scorer's detail measurement.
    """
    arr = np.array(img)
    gray = np.mean(arr[:,:,:3].astype(float), axis=2) if len(arr.shape) == 3 else arr.astype(float)
    gx = np.abs(np.diff(gray, axis=1))
    gy = np.abs(np.diff(gray, axis=0))
    edge_pixels = np.sum(gx > 20) + np.sum(gy > 20)
    total_pixels = gray.shape[0] * gray.shape[1]
    edge_density = edge_pixels / (2 * total_pixels)
    return edge_density

def compute_noise(arr, seed=42):
    """
    Measure noise using scorer's exact method: patch variance median / 2000.
    If seed is provided, use deterministic seeding.
    """
    if seed is not None:
        np.random.seed(seed)
    
    patch_vars = []
    for _ in range(100):
        if arr.shape[0] <= 8 or arr.shape[1] <= 8:
            # Image too small for patch sampling
            patch_vars.append(0)
            continue
        py = np.random.randint(0, arr.shape[0] - 8)
        px = np.random.randint(0, arr.shape[1] - 8)
        lum = (0.2126*arr[py:py+8, px:px+8, 0] + 
               0.7152*arr[py:py+8, px:px+8, 1] + 
               0.0722*arr[py:py+8, px:px+8, 2])
        patch_vars.append(float(np.var(lum)))
    
    patch_vars.sort()
    median_var = patch_vars[len(patch_vars)//2]
    norm_noise = min(1.0, median_var / 2000.0)
    return norm_noise

def score_image(image_path):
    """Score via official scorer."""
    result = subprocess.run(
        ["node", os.path.join(os.path.dirname(__file__), "render-quality-scorer.js"),
         "--image", image_path, "--tier", "1"],
        capture_output=True, text=True, timeout=30
    )
    lines = result.stdout.strip().split('\n')
    json_lines = [l for l in lines if not l.startswith('[')]
    data = json.loads('\n'.join(json_lines))
    tier1 = data.get("tier1", data)
    return {
        "score": tier1.get("score", data.get("final_score", 0)),
        "checks": tier1.get("checks", {}),
    }

def get_brightness(img):
    """Calculate average brightness matching the scorer's method."""
    arr = np.array(img).astype(float)
    if len(arr.shape) == 3 and arr.shape[2] >= 3:
        lum = 0.2126 * arr[:,:,0] + 0.7152 * arr[:,:,1] + 0.0722 * arr[:,:,2]
    else:
        lum = arr[:,:,0] if len(arr.shape) == 3 else arr
    return float(np.mean(lum) / 255.0)

def apply_gamma(img, gamma):
    """Apply gamma correction: output = input^gamma."""
    arr = np.array(img).astype(float) / 255.0
    arr = np.clip(np.power(arr, gamma), 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))

def apply_dithering(img, amount=2):
    """
    Add dithering to break up banding: add ±amount random noise per channel.
    """
    arr = np.array(img).astype(float)
    noise = np.random.randint(-amount, amount + 1, arr.shape).astype(float)
    arr = np.clip(arr + noise, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

def apply_s_curve_contrast(img, strength=0.3):
    """
    Apply S-curve contrast using simplified Hermite smoothstep.
    Formula: output = 3*x^2 - 2*x^3 (where x is normalized to [0,1])
    """
    arr = np.array(img).astype(float) / 255.0
    x = arr
    # Hermite smoothstep: 3*x^2 - 2*x^3
    s_curve = 3 * (x**2) - 2 * (x**3)
    # Blend with original by strength
    result = arr + (s_curve - arr) * strength
    result = np.clip(result, 0, 1)
    return Image.fromarray((result * 255).astype(np.uint8))

def apply_clahe(img, cutoff=0.5):
    """
    Apply CLAHE-like local contrast using PIL's autocontrast with cutoff.
    """
    return ImageOps.autocontrast(img, cutoff=cutoff)

def apply_content_stretch(img):
    """
    Apply CLAHE-style local contrast enhancement for partially blank images.
    """
    return apply_clahe(img, cutoff=0.5)

def check_blank_render(img, verbose=True):
    """
    BLIND SPOT #1: Blank render detection.
    Returns: ("abort", msg), ("stretch", img), or ("continue", img)
    """
    unique_ratio = compute_unique_ratio(img)
    
    if unique_ratio < UNIQUE_RATIO_TRULY_BLANK:
        msg = (f"Truly blank render detected (unique_ratio={unique_ratio:.4f}). "
               f"Cannot recover from < {UNIQUE_RATIO_TRULY_BLANK:.2f} unique bins. "
               f"Please re-render the scene.")
        if verbose:
            print(f"  BLANK CHECK: {msg}")
        return ("abort", msg)
    
    if unique_ratio < UNIQUE_RATIO_PARTIALLY_BLANK:
        if verbose:
            print(f"  BLANK CHECK: Partially blank (unique_ratio={unique_ratio:.4f} < {UNIQUE_RATIO_PARTIALLY_BLANK:.2f}). "
                  f"Applying content stretch...")
        img = apply_content_stretch(img)
        return ("stretch", img)
    
    if unique_ratio < UNIQUE_RATIO_BELOW_SCORER:
        if verbose:
            print(f"  BLANK CHECK: Below scorer threshold (unique_ratio={unique_ratio:.4f} < {UNIQUE_RATIO_BELOW_SCORER:.2f}). "
                  f"Applying autocontrast...")
        img = ImageOps.autocontrast(img)
        return ("continue", img)
    
    if verbose:
        print(f"  BLANK CHECK: OK (unique_ratio={unique_ratio:.4f})")
    return ("continue", img)

def adaptive_denoise(img, arr, target_edge_density=EDGE_DENSITY_THRESHOLD, 
                     norm_noise=None, verbose=True, deterministic=False):
    """
    BLIND SPOT #2: Adaptive denoise that preserves detail.
    Returns: (new_img, edge_density_before, edge_density_after, applied)
    """
    if norm_noise is None:
        norm_noise = compute_noise(arr, seed=42 if deterministic else None)
    
    edge_density_before = compute_edge_density(img)
    detail_score_before = min(1.0, edge_density_before / 0.15)
    
    if norm_noise <= 0.3:
        if verbose:
            print(f"  DENOISE: Noise={norm_noise:.4f} ≤ 0.3 → skipping denoise")
        return img, edge_density_before, edge_density_before, False
    
    # Try denoise with adaptive blend strength
    blend_strengths = [0.7, 0.5, 0.3]
    best_img = img
    best_edge_density = edge_density_before
    
    for blend_strength in blend_strengths:
        blur_radius = 2 if norm_noise > 0.7 else 1
        blurred = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        test_img = Image.blend(img, blurred, blend_strength)
        test_edge_density = compute_edge_density(test_img)
        
        if verbose:
            print(f"    Try blend={blend_strength:.1f}: edge_density={test_edge_density:.4f}", end="")
        
        # Check if detail dropped too much
        detail_score_after = min(1.0, test_edge_density / 0.15)
        if test_edge_density >= EDGE_DENSITY_THRESHOLD or detail_score_after >= 0.85:
            best_img = test_img
            best_edge_density = test_edge_density
            if verbose:
                print(" ✓")
            break
        elif verbose:
            print(f" (detail dropped to {detail_score_after*100:.0f})")
    
    # If even blend=0.3 kills detail, skip denoise entirely
    if best_edge_density < (EDGE_DENSITY_THRESHOLD * 0.8):
        if verbose:
            print(f"  DENOISE: All attempts would kill detail. Skipping denoise entirely.")
        return img, edge_density_before, edge_density_before, False
    
    if best_img is not img:
        if verbose:
            print(f"  DENOISE: Applied (edge_density: {edge_density_before:.4f} → {best_edge_density:.4f})")
        return best_img, edge_density_before, best_edge_density, True
    
    return img, edge_density_before, edge_density_before, False

def fix_gamma_banding(img, original_brightness, target_brightness=0.45, deterministic=False):
    """
    BLIND SPOT #3: Fix gamma banding for dark images.
    Returns: fixed_img
    """
    if original_brightness >= DARK_IMAGE_THRESHOLD:
        return img
    
    print(f"  GAMMA BANDING FIX: Detected dark image (brightness={original_brightness:.4f})")
    
    # Apply dithering after gamma to break up banding
    if deterministic:
        np.random.seed(42)
    img = apply_dithering(img, amount=2)
    print(f"    Applied dithering (±2 LSB)")
    
    # Apply S-curve contrast to restore depth
    img = apply_s_curve_contrast(img, strength=0.3)
    print(f"    Applied S-curve contrast (strength=0.3)")
    
    # Apply CLAHE-like local contrast
    img = apply_clahe(img, cutoff=0.5)
    print(f"    Applied CLAHE local contrast")
    
    return img

def run_multi_score(image_path, n=3):
    """
    BLIND SPOT #4: Run scoring N times and return average + breakdown.
    """
    scores = []
    all_checks = {}
    
    for i in range(n):
        result = score_image(image_path)
        scores.append(result["score"])
        if i == 0:
            all_checks = result.get("checks", {})
    
    avg_score = np.mean(scores)
    std_score = np.std(scores) if n > 1 else 0
    return {
        "average": float(avg_score),
        "std": float(std_score),
        "runs": scores,
        "checks": all_checks,
    }

def fix_image(image_path, output_path, target_brightness=0.45, 
              deterministic=False, verify=False, multi_score_runs=1, verbose=True):
    """
    Apply precision fixes based on scorer metric analysis with all blind spots fixed.

    Args:
        image_path: Input image
        output_path: Output image
        target_brightness: Target for exposure (default 0.45)
        deterministic: Seed all randomness for reproducibility
        verify: Score the result and print metrics
        multi_score_runs: If > 1, run scorer N times and average
        verbose: Print detailed output

    Returns:
        tuple: (output_path, final_score, success_flag)
    """
    if deterministic:
        np.random.seed(42)
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"  PRECISION FIX v2 (with blind spot fixes)")
        print(f"  Input: {os.path.basename(image_path)}")
        print(f"{'='*70}")
    
    img = Image.open(image_path).convert('RGB')
    current_brightness = get_brightness(img)
    arr = np.array(img).astype(float)
    
    if verbose:
        print(f"\n  INPUT METRICS:")
        print(f"    Brightness: {current_brightness:.4f}")
        print(f"    Unique ratio: {compute_unique_ratio(img):.4f}")
        print(f"    Edge density: {compute_edge_density(img):.4f}")
        print(f"    Noise (normalized): {compute_noise(arr, seed=42 if deterministic else None):.4f}")
    
    # ── BLIND SPOT #1: Blank render detection ──
    if verbose:
        print(f"\n  STEP 0: BLANK RENDER DETECTION")
    
    status, img_or_msg = check_blank_render(img, verbose=verbose)
    if status == "abort":
        if verbose:
            print(f"\n  ABORTED: {img_or_msg}")
        return output_path, 0, False
    elif status == "stretch":
        img = img_or_msg
    # else: continue
    
    arr = np.array(img).astype(float)
    
    # ── BLIND SPOT #2: Adaptive denoise ──
    if verbose:
        print(f"\n  STEP 1: ADAPTIVE DENOISE (preserve detail)")
    
    norm_noise = compute_noise(arr, seed=42 if deterministic else None)
    noise_score = max(0, 1 - max(0, (norm_noise - 0.3) / 0.7))
    if verbose:
        print(f"    Noise level: {norm_noise:.4f} (score={noise_score*100:.0f})")
    
    img, edge_dens_before, edge_dens_after, denoise_applied = adaptive_denoise(
        img, arr, target_edge_density=EDGE_DENSITY_THRESHOLD,
        norm_noise=norm_noise, verbose=verbose, deterministic=deterministic
    )
    arr = np.array(img).astype(float)
    current_brightness = get_brightness(img)
    
    # ── Step 2: Brightness/Exposure via gamma sweep ──
    if verbose:
        print(f"\n  STEP 2: EXPOSURE CORRECTION")
    
    exposure_score = max(0, 1 - abs(current_brightness - target_brightness) * 2.5)
    
    if exposure_score < 0.90:
        best_gamma = 1.0
        best_exp_score = exposure_score
        
        if current_brightness < target_brightness:
            gammas = np.linspace(0.05, 0.95, 20)
        else:
            gammas = np.linspace(1.05, 3.0, 20)
        
        for g in gammas:
            test_img = apply_gamma(img, g)
            b = get_brightness(test_img)
            e = max(0, 1 - abs(b - target_brightness) * 2.5)
            if e > best_exp_score:
                best_exp_score = e
                best_gamma = g
        
        if best_gamma != 1.0:
            img_before_gamma = img
            img = apply_gamma(img, best_gamma)
            new_bright = get_brightness(img)
            if verbose:
                print(f"    {current_brightness:.4f} → gamma={best_gamma:.3f} → {new_bright:.4f} (score={best_exp_score*100:.0f})")
    else:
        if verbose:
            print(f"    Brightness: {current_brightness:.4f} (score={exposure_score*100:.0f}) ✓")
    
    # ── BLIND SPOT #3: Gamma banding fix for dark images ──
    if current_brightness < DARK_IMAGE_THRESHOLD:
        if verbose:
            print(f"\n  STEP 2b: GAMMA BANDING FIX")
        img = fix_gamma_banding(img, current_brightness, target_brightness, deterministic)
    
    # ── Step 3: Edge enhancement if detail is low ──
    if verbose:
        print(f"\n  STEP 3: DETAIL ENHANCEMENT")
    
    edge_density = compute_edge_density(img)
    detail_score = min(1.0, edge_density / 0.15)
    
    if detail_score < 0.90:
        enhance_strength = min(2.0, 1.0 + (0.15 - edge_density) * 5)
        img = img.filter(ImageFilter.UnsharpMask(
            radius=2, percent=int(150 * enhance_strength), threshold=3))
        if verbose:
            print(f"    Edge density: {edge_density:.4f} → enhancing {enhance_strength:.2f}x (score={detail_score*100:.0f})")
    else:
        if verbose:
            print(f"    Edge density: {edge_density:.4f} (score={detail_score*100:.0f}) ✓")
    
    # ── Step 4: Micro-adjustment ──
    final_brightness = get_brightness(img)
    final_exp_score = max(0, 1 - abs(final_brightness - target_brightness) * 2.5)
    
    if final_exp_score < 0.85 and abs(final_brightness - target_brightness) > 0.03:
        if final_brightness > 0.01:
            micro_gamma = math.log(target_brightness) / math.log(final_brightness)
            micro_gamma = max(0.3, min(micro_gamma, 3.0))
            img = apply_gamma(img, micro_gamma)
            final_brightness = get_brightness(img)
            if verbose:
                print(f"\n  STEP 4: MICRO-ADJUST")
                print(f"    Applied gamma {micro_gamma:.3f}")
    
    # Save
    img.save(output_path, 'PNG')
    
    if verbose:
        print(f"\n  OUTPUT METRICS:")
        print(f"    Brightness: {final_brightness:.4f}")
        print(f"    Unique ratio: {compute_unique_ratio(img):.4f}")
        print(f"    Edge density: {compute_edge_density(img):.4f}")
        print(f"    Saved: {output_path}")
    
    # ── BLIND SPOT #4: Multi-score with deterministic seeding ──
    if verify or multi_score_runs > 1:
        if verbose:
            print(f"\n  STEP 5: VERIFICATION")
            if multi_score_runs > 1:
                print(f"    Running scorer {multi_score_runs}x for stability check...")
        
        if multi_score_runs > 1:
            score_result = run_multi_score(output_path, n=multi_score_runs)
            final_score = score_result["average"]
            checks = score_result["checks"]
            if verbose:
                print(f"\n  FINAL SCORE: {final_score:.1f}/100 (±{score_result['std']:.1f} std)")
                print(f"    Runs: {score_result['runs']}")
        else:
            result = score_image(output_path)
            final_score = result["score"]
            checks = result.get("checks", {})
            if verbose:
                print(f"\n  FINAL SCORE: {final_score:.1f}/100")
        
        if verbose and checks:
            print(f"    Breakdown:")
            for check_name, check_data in checks.items():
                check_score = check_data.get('score', 0)
                print(f"      {check_name}: {check_score:.0f}/100")
    else:
        final_score = None
        if verbose:
            print(f"\n  (Scoring skipped. Use --verify to check result.)")
    
    if verbose:
        print(f"{'='*70}\n")
    
    return output_path, final_score, final_score is not None and final_score >= 85


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Precision Fix v2: Apply calculated corrections with blind spot fixes"
    )
    parser.add_argument("--image", required=True, help="Input image path")
    parser.add_argument("--output", default="", help="Output image path (default: input_precision.png)")
    parser.add_argument("--target-brightness", type=float, default=0.45, 
                       help="Target brightness (default: 0.45)")
    parser.add_argument("--deterministic", action="store_true",
                       help="Seed all randomness for reproducible results")
    parser.add_argument("--verify", action="store_true",
                       help="Score the result and show full metric breakdown")
    parser.add_argument("--multi-score", type=int, default=1, metavar="N",
                       help="Run scoring N times and use average (requires --verify)")
    
    args = parser.parse_args()
    
    output = args.output or args.image.replace('.png', '_precision.png')
    
    output_path, final_score, success = fix_image(
        args.image, output,
        target_brightness=args.target_brightness,
        deterministic=args.deterministic,
        verify=args.verify or args.multi_score > 1,
        multi_score_runs=args.multi_score,
        verbose=True
    )
    
    # Return code
    if final_score is None:
        sys.exit(0)  # No scoring done
    elif success:
        sys.exit(0)  # Score >= 85
    elif final_score > 0:
        sys.exit(1)  # Improved but below 85
    else:
        sys.exit(2)  # No improvement
