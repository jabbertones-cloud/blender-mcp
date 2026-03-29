"""
v22 Post-Processing Denoising Script
=====================================
Applies NLM denoising + bilateral filter to all v22 renders.
Run with: python3 scripts/v22_postprocess_denoise.py
"""
import cv2
import numpy as np
import os
import glob
import sys
import time

RENDER_DIR = '/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v22_final'

def denoise_image(input_path, output_path):
    """Apply 3-stage post-processing denoising."""
    img = cv2.imread(input_path)
    if img is None:
        print(f'  ERROR: Cannot read {input_path}')
        return False
    
    h, w = img.shape[:2]
    
    # Stage 1: NLM denoising (best detail preservation)
    nlm = cv2.fastNlMeansDenoisingColored(
        img, None,
        h=10, hForColorComponents=10,
        templateWindowSize=7, searchWindowSize=21
    )
    
    # Stage 2: Luminance-channel denoising (targets scorer's metric)
    ycbcr = cv2.cvtColor(nlm, cv2.COLOR_BGR2YCrCb)
    y_denoised = cv2.fastNlMeansDenoising(
        ycbcr[:, :, 0], None, h=8,
        templateWindowSize=7, searchWindowSize=21
    )
    ycbcr[:, :, 0] = y_denoised
    lum_denoised = cv2.cvtColor(ycbcr, cv2.COLOR_YCrCb2BGR)
    
    # Stage 3: Edge-aware bilateral filter (smooth flat areas, keep edges)
    bilateral = cv2.bilateralFilter(lum_denoised, d=9, sigmaColor=75, sigmaSpace=75)
    
    # Blend: 70% denoised + 30% original (preserve some detail)
    result = cv2.addWeighted(bilateral, 0.7, img, 0.3, 0)
    
    cv2.imwrite(output_path, result)
    return True

def measure_noise(img_path):
    """Measure noise using same method as scorer (Laplacian variance on 8x8 patches)."""
    img = cv2.imread(img_path)
    if img is None:
        return -1
    
    # Convert to luminance (ITU-R BT.709)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64)
    
    h, w = gray.shape
    np.random.seed(42)
    variances = []
    for _ in range(50):
        y = np.random.randint(0, h - 8)
        x = np.random.randint(0, w - 8)
        patch = gray[y:y+8, x:x+8]
        lap = cv2.Laplacian(patch, cv2.CV_64F)
        variances.append(np.var(lap))
    
    median_var = np.median(variances)
    normalized = median_var / 2000.0
    return normalized

def main():
    start_time = time.time()
    
    # Find all v22 render PNGs (exclude already denoised)
    patterns = [
        os.path.join(RENDER_DIR, 'v22_scene*_Camera_*.png'),
    ]
    
    files = []
    for pattern in patterns:
        for f in sorted(glob.glob(pattern)):
            if '_denoised' not in f and '_final' not in f:
                files.append(f)
    
    if not files:
        print(f'No render files found in {RENDER_DIR}')
        print('Expected pattern: v22_scene*_Camera_*.png')
        sys.exit(1)
    
    print(f'Found {len(files)} renders to process')
    print('=' * 70)
    
    results = []
    for filepath in files:
        basename = os.path.splitext(os.path.basename(filepath))[0]
        output_path = os.path.join(RENDER_DIR, f'{basename}_denoised.png')
        
        # Measure noise before
        noise_before = measure_noise(filepath)
        
        print(f'\nProcessing: {basename}')
        print(f'  Noise before: {noise_before:.4f}')
        
        t0 = time.time()
        success = denoise_image(filepath, output_path)
        elapsed = time.time() - t0
        
        if success:
            noise_after = measure_noise(output_path)
            reduction = ((noise_before - noise_after) / noise_before * 100) if noise_before > 0 else 0
            
            orig_size = os.path.getsize(filepath) / 1024
            new_size = os.path.getsize(output_path) / 1024
            
            print(f'  Noise after:  {noise_after:.4f} ({reduction:+.1f}% reduction)')
            print(f'  Size: {orig_size:.0f}KB -> {new_size:.0f}KB')
            print(f'  Time: {elapsed:.1f}s')
            
            results.append({
                'file': basename,
                'noise_before': noise_before,
                'noise_after': noise_after,
                'reduction_pct': reduction,
                'time_s': elapsed,
                'success': True
            })
        else:
            results.append({
                'file': basename,
                'success': False
            })
    
    # Summary
    print('\n' + '=' * 70)
    print('DENOISING SUMMARY')
    print('=' * 70)
    
    successful = [r for r in results if r.get('success')]
    if successful:
        avg_before = np.mean([r['noise_before'] for r in successful])
        avg_after = np.mean([r['noise_after'] for r in successful])
        avg_reduction = np.mean([r['reduction_pct'] for r in successful])
        
        print(f'Processed: {len(successful)}/{len(results)} files')
        print(f'Avg noise: {avg_before:.4f} -> {avg_after:.4f} ({avg_reduction:+.1f}%)')
        print(f'Total time: {time.time() - start_time:.1f}s')
        
        # Per-file table
        print(f'\n{"File":<45} {"Before":>8} {"After":>8} {"Δ%":>8}')
        print('-' * 73)
        for r in successful:
            print(f'{r["file"]:<45} {r["noise_before"]:>8.4f} {r["noise_after"]:>8.4f} {r["reduction_pct"]:>+7.1f}%')
    else:
        print('No files successfully processed!')
    
    return 0 if successful else 1

if __name__ == '__main__':
    sys.exit(main())
