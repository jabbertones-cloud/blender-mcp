#!/usr/bin/env python3
"""
v16.1 Post-Processing — Adaptive pipeline that applies stronger
processing to BirdEye/overhead shots (low detail) vs eye-level shots.
Uses gamma for exposure (preserves range) + CLAHE for local contrast.
"""
import os, sys, glob, argparse
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps


def compute_avg_brightness(img):
    arr = np.array(img).astype(float)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        lum = 0.2126 * arr[:,:,0] + 0.7152 * arr[:,:,1] + 0.0722 * arr[:,:,2]
    else:
        lum = arr if arr.ndim == 2 else arr[:,:,0]
    return lum.mean() / 255.0


def compute_edge_density(img, threshold=20):
    arr = np.array(img.convert('L')).astype(float)
    gx = np.abs(arr[1:-1, 2:] - arr[1:-1, :-2])
    gy = np.abs(arr[2:, 1:-1] - arr[:-2, 1:-1])
    gradient = np.sqrt(gx**2 + gy**2)
    return (gradient > threshold).sum() / gradient.size


def gamma_exposure(img, target=0.45):
    """Use gamma correction to adjust exposure — preserves dynamic range."""
    current = compute_avg_brightness(img)
    if current < 0.01:
        return img
    # Solve: target = current^gamma => gamma = log(target)/log(current)
    if current > 0.01 and current < 0.99:
        gamma = np.log(target) / np.log(current)
        gamma = max(0.3, min(3.0, gamma))  # Clamp
    else:
        gamma = 1.0
    arr = np.array(img).astype(float) / 255.0
    arr = np.power(arr, gamma)
    arr = np.clip(arr * 255, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def clahe_enhance(img, clip_limit=3.0, grid_size=8):
    """Apply CLAHE-like local contrast enhancement using tile-based processing."""
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]
    tile_h = max(h // grid_size, 1)
    tile_w = max(w // grid_size, 1)
    
    result = arr.copy()
    for c in range(min(3, arr.shape[2] if arr.ndim == 3 else 1)):
        channel = arr[:,:,c] if arr.ndim == 3 else arr
        out = channel.copy()
        for ty in range(0, h, tile_h):
            for tx in range(0, w, tile_w):
                tile = channel[ty:ty+tile_h, tx:tx+tile_w]
                tmin, tmax = tile.min(), tile.max()
                if tmax - tmin > 5:
                    # Local stretch with clip limit
                    stretch = (tile - tmin) / (tmax - tmin) * 255
                    # Blend with original to limit effect
                    blend = 0.3  # 30% local contrast boost
                    out[ty:ty+tile_h, tx:tx+tile_w] = tile * (1 - blend) + stretch * blend
        if arr.ndim == 3:
            result[:,:,c] = out
        else:
            result = out
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))


def process_image(input_path, output_path, is_birdeye=False, verbose=False):
    """Adaptive pipeline — stronger processing for BirdEye shots."""
    img = Image.open(input_path).convert('RGB')
    
    before_bright = compute_avg_brightness(img)
    before_edge = compute_edge_density(img)
    
    if verbose:
        print(f"  Before: brightness={before_bright:.3f}, edge_density={before_edge:.4f}")

    # Step 1: Autocontrast to maximize histogram spread
    img = ImageOps.autocontrast(img, cutoff=1.0)
    
    # Step 2: Gamma-based exposure targeting 0.45
    img = gamma_exposure(img, target=0.45)
    
    # Step 3: CLAHE-like local contrast (helps BirdEye a lot)
    if is_birdeye:
        img = clahe_enhance(img, clip_limit=3.0, grid_size=8)
    
    # Step 4: Sharpening — stronger for BirdEye
    sharp_strength = 3.0 if is_birdeye else 1.8
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(sharp_strength * 100), threshold=2))
    
    # Step 5: Edge enhance for BirdEye
    if is_birdeye:
        img = img.filter(ImageFilter.EDGE_ENHANCE)
    
    # Step 6: Mild contrast boost
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.12 if not is_birdeye else 1.18)
    
    # Step 7: Final exposure correction (contrast can shift it)
    img = gamma_exposure(img, target=0.45)
    
    if verbose:
        after_bright = compute_avg_brightness(img)
        after_edge = compute_edge_density(img)
        print(f"  After:  brightness={after_bright:.3f}, edge_density={after_edge:.4f}")
    
    img.save(output_path, 'PNG', optimize=True)
    return output_path


def main():
    parser = argparse.ArgumentParser(description='v16.1 Adaptive Post-Processing')
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    input_files = sorted(glob.glob(os.path.join(args.input_dir, '*.png')))
    if not input_files:
        print(f"No PNG files in {args.input_dir}"); sys.exit(1)

    print(f"Processing {len(input_files)} images (adaptive v2)...")
    for f in input_files:
        basename = os.path.basename(f)
        is_birdeye = 'BirdEye' in basename
        out_name = basename.replace('v15_1_', 'v16_').replace('v15_', 'v16_').replace('v13_1_', 'v16_').replace('v13_', 'v16_')
        if not out_name.startswith('v16_'):
            out_name = 'v16_' + out_name
        out_path = os.path.join(args.output_dir, out_name)
        try:
            if args.verbose:
                tag = " [BIRDEYE-BOOST]" if is_birdeye else ""
                print(f"\n--- {basename}{tag} ---")
            process_image(f, out_path, is_birdeye=is_birdeye, verbose=args.verbose)
            print(f"  [OK] {basename}")
        except Exception as e:
            print(f"  [FAIL] {basename}: {e}")

    print("Done.")


if __name__ == '__main__':
    main()
