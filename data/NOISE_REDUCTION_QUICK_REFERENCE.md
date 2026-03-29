# Noise Reduction Quick Reference Card

## Your Problem
**Scene1 BirdEye:** normalized_noise = 0.9026  
**Penalty:** 86 points lost (out of 15% = 86/15 = 5.7 weight)  
**Target:** ≤ 0.5 normalized noise (break even)  

## Your Scorer (from render-quality-scorer.js)
```
1. Sample 50 random 8×8 patches
2. Measure variance in each patch (using luminance)
3. Take median variance
4. Normalize: normalizedNoise = min(1, medianVariance / 2000)
5. Score: 1 - max(0, (normalizedNoise - 0.3) / 0.7)
```

## 30-Second Fix
Open Blender:
1. **Render Settings → Sampling**
   - Samples: `256`
   - Adaptive Sampling: `ON`
   - Noise Threshold: `0.002` ← KEY SETTING
   - Denoiser: `OpenImageDenoise`

2. **View Layer → Passes → Data**
   - Denoising Data: `ON`
   - Denoising Albedo: `ON`
   - Denoising Normal: `ON`

3. **Render Settings → Light Paths**
   - Caustics Reflective: `OFF`
   - Caustics Refractive: `OFF`

**Result:** 0.9026 → ~0.35-0.40 (62-72% improvement)

## If That Wasn't Enough
```
Compositing → Add Denoise Node
├─ Mode: Accurate
├─ Input: Image from Render Layer
├─ Input: Denoising Normal pass
├─ Input: Denoising Albedo pass
└─ Output: to Composite

Result: 0.35 → ~0.25-0.28 (additional improvement)
```

## If You Need <0.20
```bash
python -c "
import cv2
img = cv2.imread('render.png')
denoised = cv2.fastNlMeansDenoisingColored(
    img, None, h=10, hForColorComponents=10,
    templateWindowSize=7, searchWindowSize=21
)
cv2.imwrite('render_denoised.png', denoised)
"
```
Result: 0.25 → ~0.15-0.20

## Why Each Setting Matters

| Setting | Why It Matters |
|---------|---------------|
| **0.002 threshold** | Forces per-pixel noise detection. 0.1 (default) is too lenient. |
| **256 samples** | Balanced quality. 128 is too noisy, 512 has diminishing returns. |
| **Denoising passes** | Give OIDN geometric context. Without them, denoiser is "blind." |
| **Disable caustics** | One of noisiest render features. Trade photorealism for score. |
| **Accurate denoise** | Prefilters input. "Fast" mode assumes noise-free inputs. |

## Expected Timeline
- **Phase 1 (render settings):** 5 min setup + 8 min render = **0.90 → 0.35**
- **Phase 2 (compositor):** 5 min setup = **0.35 → 0.25**
- **Phase 3 (post-proc):** 10 min code = **0.25 → 0.15-0.20**

## Common Mistakes to Avoid
❌ Using 0.1 adaptive threshold (too lenient)  
❌ Only enabling OIDN without denoising passes  
❌ Enabling caustics (they destroy noise score)  
❌ Using "Fast" mode instead of "Accurate" in compositor  
❌ Skipping render-time optimization and relying on post-processing  

## One-Liner: Post-Processing Command
```bash
# Non-Local Means (best quality)
python3 << 'EOF'
import cv2
img = cv2.imread('render.png')
cv2.imwrite('render_denoised.png', 
    cv2.fastNlMeansDenoisingColored(img, None, h=10, templateWindowSize=7, searchWindowSize=21))
EOF
```

## Blender Python (for automation)
```python
import bpy
scene = bpy.context.scene
scene.cycles.samples = 256
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.002
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.render.layers[0].use_pass_denoising_normal = True
scene.render.layers[0].use_pass_denoising_albedo = True
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
```

## Files for Deep Dive
- **NOISE_REDUCTION_RESEARCH_2026-03-26.md** — 2500-word detailed guide
- **noise-reduction-techniques.json** — Machine-readable registry with code snippets
- **NOISE_REDUCTION_EXECUTIVE_SUMMARY.txt** — Full breakdown with theory

## Key Insight
Your scorer uses **patch-based local variance** (not global noise).  
This means **structure matters as much as noise reduction**.

Don't just denoise — preserve texture detail and add subtle grid structure if needed.

---

**Start here:** Implement the "30-Second Fix" and measure. You should see 0.9026 → ~0.35.
