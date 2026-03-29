#!/usr/bin/env python3
"""v17 Post-Processing — Forensic render quality pipeline with adaptive BirdEye CLAHE"""
import os, sys, glob, argparse
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

def compute_avg_brightness(img):
    """Compute luminance-weighted average brightness [0, 1]"""
    arr = np.array(img).astype(float)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        lum = 0.2126 * arr[:,:,0] + 0.7152 * arr[:,:,1] + 0.0722 * arr[:,:,2]
    else:
        lum = arr if arr.ndim == 2 else arr[:,:,0]
    return lum.mean() / 255.0

def compute_histogram_spread(img):
    """Compute histogram spread [0, 1] — measures contrast"""
    arr = np.array(img.convert('L')).astype(float)
    hist, _ = np.histogram(arr, bins=256, range=(0, 256))
    # Find min/max non-zero bins
    nonzero = np.where(hist > 0)[0]
    if len(nonzero) == 0:
        return 0.0
    spread = (nonzero[-1] - nonzero[0]) / 255.0
    return spread

def compute_edge_density(img, threshold=20):
    """Compute edge pixel density [0, 1] — measures detail"""
    arr = np.array(img.convert('L')).astype(float)
    gx = np.abs(arr[1:-1, 2:] - arr[1:-1, :-2])
    gy = np.abs(arr[2:, 1:-1] - arr[:-2, 1:-1])
    gradient = np.sqrt(gx**2 + gy**2)
    return (gradient > threshold).sum() / gradient.size

def compute_noise_variance(img):
    """Compute local variance [0, 1] — penalizes noise above 30%"""
    arr = np.array(img.convert('L')).astype(float)
    local_var = np.zeros_like(arr)
    for i in range(1, arr.shape[0]-1):
        for j in range(1, arr.shape[1]-1):
            patch = arr[i-1:i+2, j-1:j+2]
            local_var[i, j] = np.var(patch)
    variance = local_var.mean() / 255.0
    return variance

def compute_unique_ratio(img):
    """Compute unique color ratio [0, 1] — penalizes blank/uniform images"""
    arr = np.array(img).astype(float)
    if arr.ndim == 3:
        arr_flat = arr.reshape(-1, arr.shape[2])
    else:
        arr_flat = arr.flatten()
    unique_count = len(np.unique(arr_flat, axis=0)) if arr.ndim == 3 else len(np.unique(arr_flat))
    total_count = arr_flat.shape[0]
    return unique_count / total_count

def compute_forensic_score(img):
    """Compute forensic render quality score [0, 100]"""
    # Key scorer weights
    not_blank = (compute_unique_ratio(img) / 0.3) * 25
    contrast = (compute_histogram_spread(img) / 0.7) * 20
    exposure = (1 - abs(compute_avg_brightness(img) - 0.45) * 2.5) * 20
    detail = (compute_edge_density(img) / 0.15) * 20
    
    variance = compute_noise_variance(img)
    noise_penalty = 0
    if variance > 0.30:
        noise_penalty = (variance - 0.30) * 15
    noise = (1 - min(1.0, noise_penalty / 15)) * 15
    
    # Clamp individual scores to [0, max_weight]
    not_blank = min(25, max(0, not_blank))
    contrast = min(20, max(0, contrast))
    exposure = min(20, max(0, exposure))
    detail = min(20, max(0, detail))
    noise = min(15, max(0, noise))
    
    score = not_blank + contrast + exposure + detail + noise
    return min(100, max(0, score))

def gamma_exposure(img, target=0.45):
    """Apply gamma correction to reach target brightness"""
    current = compute_avg_brightness(img)
    if current < 0.01:
        return img
    if 0.01 <= current <= 0.99:
        gamma = np.log(target) / np.log(current)
        gamma = max(0.3, min(3.0, gamma))
    else:
        gamma = 1.0
    arr = np.array(img).astype(float) / 255.0
    arr = np.power(arr, gamma)
    arr = np.clip(arr * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def clahe_enhance(img, clip_limit=3.0, grid_size=8, blend=0.3):
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]
    tile_h = max(h // grid_size, 1)
    tile_w = max(w // grid_size, 1)
    result = arr.copy()
    
    num_channels = arr.shape[2] if arr.ndim == 3 else 1
    for c in range(min(3, num_channels)):
        channel = arr[:,:,c] if arr.ndim == 3 else arr
        out = channel.copy()
        for ty in range(0, h, tile_h):
            for tx in range(0, w, tile_w):
                tile = channel[ty:ty+tile_h, tx:tx+tile_w]
                tmin, tmax = tile.min(), tile.max()
                if tmax - tmin > 5:
                    stretch = (tile - tmin) / (tmax - tmin) * 255
                    out[ty:ty+tile_h, tx:tx+tile_w] = tile * (1 - blend) + stretch * blend
        if arr.ndim == 3:
            result[:,:,c] = out
        else:
            result = out
    
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

def unsharp_mask(img, percent=180):
    """Apply unsharp mask sharpening"""
    arr = np.array(img).astype(float)
    blurred = np.array(img.filter(ImageFilter.GaussianBlur(radius=1))).astype(float)
    sharpened = arr + (arr - blurred) * (percent / 100.0)
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    return Image.fromarray(sharpened)

def process_birdeye_day(img):
    """v17 adaptive BirdEye day pipeline: moderate CLAHE + balanced sharpening"""
    # Step 1: CLAHE with moderate blend (0.15) for local contrast boost
    img = clahe_enhance(img, clip_limit=3.0, grid_size=8, blend=0.15)
    
    # Step 2: USM sharpening (220% — between v1's 180% and v2's 300%)
    img = unsharp_mask(img, percent=220)
    
    # Step 3: Autocontrast
    img = ImageOps.autocontrast(img, cutoff=2)
    
    return img

def process_eye_level(img):
    """v1 eye-level pipeline: autocontrast + gamma + USM + contrast boost"""
    # Step 1: Autocontrast
    img = ImageOps.autocontrast(img, cutoff=2)
    
    # Step 2: Gamma exposure to 0.45
    img = gamma_exposure(img, target=0.45)
    
    # Step 3: USM sharpening (180%)
    img = unsharp_mask(img, percent=180)
    
    # Step 4: Contrast boost (1.15x)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.15)
    
    return img

def process_night_scene(img):
    """v2 aggressive night pipeline: CLAHE 0.3 + gamma + USM + contrast"""
    # Step 1: CLAHE with stronger blend (0.3)
    img = clahe_enhance(img, clip_limit=3.0, grid_size=8, blend=0.3)
    
    # Step 2: Gamma exposure to 0.45
    img = gamma_exposure(img, target=0.45)
    
    # Step 3: USM sharpening (300%)
    img = unsharp_mask(img, percent=300)
    
    # Step 4: Contrast boost (1.15x)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.15)
    
    return img

def detect_birdeye(filename):
    """Detect BirdEye from filename"""
    return 'BirdEye' in filename or 'birdeye' in filename.lower()

def process_image(input_path, output_path, scene_type='day', verbose=False):
    """Process single image through v17 pipeline"""
    img = Image.open(input_path)
    
    # Compute pre-processing metrics
    brightness_before = compute_avg_brightness(img)
    contrast_before = compute_histogram_spread(img)
    edge_density_before = compute_edge_density(img)
    score_before = compute_forensic_score(img)
    
    # Select pipeline based on scene type and filename
    is_birdeye = detect_birdeye(input_path)
    
    if scene_type == 'night':
        # Night Scene 4: use v2 aggressive pipeline
        img = process_night_scene(img)
    elif is_birdeye and scene_type == 'day':
        # Day BirdEye: use v17 adaptive pipeline
        img = process_birdeye_day(img)
    else:
        # Eye-level shots (DriverPOV, WideAngle, SightLine, SecurityCam): use v1 pipeline
        img = process_eye_level(img)
    
    # Compute post-processing metrics
    brightness_after = compute_avg_brightness(img)
    contrast_after = compute_histogram_spread(img)
    edge_density_after = compute_edge_density(img)
    score_after = compute_forensic_score(img)
    
    # Save output
    img.save(output_path)
    
    if verbose:
        score_delta = score_after - score_before
        print(f"Processed: {os.path.basename(input_path)}")
        print(f"  Scene: {scene_type} | BirdEye: {is_birdeye}")
        print(f"  Brightness: {brightness_before:.3f} → {brightness_after:.3f}")
        print(f"  Contrast: {contrast_before:.3f} → {contrast_after:.3f}")
        print(f"  Edge Density: {edge_density_before:.4f} → {edge_density_after:.4f}")
        print(f"  Score: {score_before:.1f} → {score_after:.1f} ({score_delta:+.1f})")
        print()
    
    return score_before, score_after

def main():
    parser = argparse.ArgumentParser(description='v17 Forensic Render Quality Post-Processing')
    parser.add_argument('--input-dir', required=True, help='Input directory')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--scene-type', choices=['day', 'night'], default='day', help='Pipeline selection')
    parser.add_argument('--verbose', action='store_true', help='Print metrics')
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Process all images in input directory
    input_files = glob.glob(os.path.join(args.input_dir, '*.png')) + \
                  glob.glob(os.path.join(args.input_dir, '*.jpg')) + \
                  glob.glob(os.path.join(args.input_dir, '*.jpeg'))
    
    if not input_files:
        print(f"No images found in {args.input_dir}")
        return
    
    scores_before = []
    scores_after = []
    
    for input_path in sorted(input_files):
        filename = os.path.basename(input_path)
        output_filename = f"v17_{filename}"
        output_path = os.path.join(args.output_dir, output_filename)
        
        score_before, score_after = process_image(input_path, output_path, args.scene_type, args.verbose)
        scores_before.append(score_before)
        scores_after.append(score_after)
    
    # Summary statistics
    if args.verbose or len(input_files) > 1:
        avg_before = np.mean(scores_before) if scores_before else 0
        avg_after = np.mean(scores_after) if scores_after else 0
        print(f"Summary: Processed {len(input_files)} images")
        print(f"  Average score before: {avg_before:.1f}")
        print(f"  Average score after: {avg_after:.1f}")
        print(f"  Average improvement: {avg_after - avg_before:+.1f}")

if __name__ == '__main__':
    main()
