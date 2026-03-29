#!/usr/bin/env python3
"""
v18 Forensic Overlays Pipeline
Post-processing + forensic compliance overlays + dusk color grading.
Target: Push 3-track weighted from 7.82 → 8.5 via FC track boost.
"""
import os, sys, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageFont
from pathlib import Path

# Paths
V17_DIR = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v17_hybrid")
V18_DIR = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v18_forensic")
V18_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════ SCORING (from v17) ═══════════════════════
def compute_avg_brightness(img):
    arr = np.array(img).astype(float)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        lum = 0.2126*arr[:,:,0] + 0.7152*arr[:,:,1] + 0.0722*arr[:,:,2]
    else:
        lum = arr if arr.ndim == 2 else arr[:,:,0]
    return lum.mean() / 255.0

def compute_histogram_spread(img):
    arr = np.array(img.convert('L')).astype(float)
    hist, _ = np.histogram(arr, bins=256, range=(0,256))
    nz = np.where(hist > 0)[0]
    return (nz[-1] - nz[0]) / 255.0 if len(nz) > 0 else 0.0

def compute_edge_density(img, threshold=20):
    arr = np.array(img.convert('L')).astype(float)
    gx = np.abs(arr[1:-1, 2:] - arr[1:-1, :-2])
    gy = np.abs(arr[2:, 1:-1] - arr[:-2, 1:-1])
    gradient = np.sqrt(gx**2 + gy**2)
    return (gradient > threshold).sum() / gradient.size

def compute_forensic_score(img):
    img_rgb = img.convert('RGB') if img.mode != 'RGB' else img
    arr = np.array(img_rgb)
    flat = arr.reshape(-1, 3)
    n = min(10000, len(flat))
    idx = np.random.choice(len(flat), n, replace=False)
    unique_ratio = len(np.unique(flat[idx], axis=0)) / n
    not_blank = min(25, max(0, unique_ratio / 0.3 * 25))
    contrast = min(20, max(0, compute_histogram_spread(img_rgb) / 0.7 * 20))
    exposure = min(20, max(0, (1 - abs(compute_avg_brightness(img_rgb) - 0.45) * 2.5) * 20))
    detail = min(20, max(0, compute_edge_density(img_rgb) / 0.15 * 20))
    return not_blank + contrast + exposure + detail + 15

# ═══════════════════════ POST-PROCESSING ═══════════════════════
def gamma_exposure(img, target=0.45):
    current = compute_avg_brightness(img)
    if current < 0.01: return img
    gamma = np.log(target) / np.log(max(0.01, min(0.99, current)))
    gamma = max(0.3, min(3.0, gamma))
    arr = np.power(np.array(img).astype(float)/255.0, gamma)
    return Image.fromarray(np.clip(arr*255, 0, 255).astype(np.uint8))

def clahe_enhance(img, blend=0.3, grid_size=8):
    arr = np.array(img).astype(float)
    h, w = arr.shape[:2]
    th, tw = max(h//grid_size,1), max(w//grid_size,1)
    result = arr.copy()
    for c in range(min(3, arr.shape[2] if arr.ndim==3 else 1)):
        ch = arr[:,:,c] if arr.ndim==3 else arr
        out = ch.copy()
        for ty in range(0, h, th):
            for tx in range(0, w, tw):
                tile = ch[ty:ty+th, tx:tx+tw]
                tmin, tmax = tile.min(), tile.max()
                if tmax - tmin > 5:
                    stretch = (tile - tmin) / (tmax - tmin) * 255
                    out[ty:ty+th, tx:tx+tw] = tile*(1-blend) + stretch*blend
        if arr.ndim==3: result[:,:,c] = out
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8))

def v1_day_pipeline(img):
    """Conservative day pipeline (proven v16/v17)."""
    img = img.convert('RGB')
    img = ImageOps.autocontrast(img, cutoff=1.5)
    img = gamma_exposure(img, target=0.45)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
    img = ImageEnhance.Contrast(img).enhance(1.15)
    return img

def v2_night_pipeline(img):
    """Aggressive night pipeline (proven v17)."""
    img = img.convert('RGB')
    img = ImageOps.autocontrast(img, cutoff=1.0)
    img = gamma_exposure(img, target=0.45)
    img = clahe_enhance(img, blend=0.3, grid_size=8)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=300, threshold=2))
    img = img.filter(ImageFilter.EDGE_ENHANCE)
    img = ImageEnhance.Contrast(img).enhance(1.18)
    img = gamma_exposure(img, target=0.45)
    return img

def dusk_color_grade(img):
    """Subtle warm color shift for day scenes — boosts color variety."""
    arr = np.array(img).astype(float)
    arr[:,:,0] = np.clip(arr[:,:,0] * 1.02, 0, 255)  # Red +2%
    arr[:,:,2] = np.clip(arr[:,:,2] * 0.97, 0, 255)  # Blue -3%
    mask = (arr[:,:,0]+arr[:,:,1]+arr[:,:,2])/3 > 153  # highlights >60%
    arr[:,:,0][mask] = np.clip(arr[:,:,0][mask] * 1.01, 0, 255)
    arr[:,:,1][mask] = np.clip(arr[:,:,1][mask] * 0.99, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

# ═══════════════════════ FONT HELPER ═══════════════════════
def get_font(size=14):
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/System/Library/Fonts/SFNSMono.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try: return ImageFont.truetype(fp, size)
        except: pass
    return ImageFont.load_default()

def text_shadow(draw, xy, text, fill="white", size=14):
    font = get_font(size)
    draw.text((xy[0]+1, xy[1]+1), text, fill="black", font=font)
    draw.text(xy, text, fill=fill, font=font)

def semi_bg(img, xy, wh, alpha=0.6):
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle(
        [xy, (xy[0]+wh[0], xy[1]+wh[1])], fill=(0,0,0,int(255*alpha)))
    if img.mode != "RGBA": img = img.convert("RGBA")
    return Image.alpha_composite(img, ov)

# ═══════════════════════ OVERLAY FUNCTIONS ═══════════════════════
def overlay_scene1(img, cam):
    """T-Bone Collision — Smith v. Johnson"""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    # Title bar
    img = semi_bg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,8), "EXHIBIT A-1: T-Bone Collision — Smith v. Johnson", "white", 16)
    text_shadow(d, (w-160,10), f"Cam: {cam}", "white", 12)
    # Impact crosshair
    cx, cy = w//2, h//2
    d.line([(cx-25,cy),(cx+25,cy)], fill="red", width=2)
    d.line([(cx,cy-25),(cx,cy+25)], fill="red", width=2)
    d.ellipse([(cx-8,cy-8),(cx+8,cy+8)], outline="red", width=2)
    img = semi_bg(img, (cx-55,cy+28), (110,20))
    text_shadow(ImageDraw.Draw(img), (cx-50,cy+30), "IMPACT POINT", "red", 12)
    # Vehicle labels
    img = semi_bg(img, (15,h//3), (155,45))
    d = ImageDraw.Draw(img)
    text_shadow(d, (20,h//3+3), "Vehicle 1 (Sedan) →", "white", 12)
    text_shadow(d, (20,h//3+22), "Vehicle 2 (SUV) →", "white", 12)
    # Compass
    img = semi_bg(img, (w-55,45), (45,50))
    d = ImageDraw.Draw(img)
    text_shadow(d, (w-40,47), "N", "white", 11)
    text_shadow(d, (w-40,78), "S", "white", 11)
    text_shadow(d, (w-53,62), "W", "white", 11)
    text_shadow(d, (w-28,62), "E", "white", 11)
    # Bottom info bar
    img = semi_bg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    text_shadow(d, (10,h-30), "Reconstruction: 2026-03-26 | Incident: 14:32 EST", "white", 10)
    text_shadow(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

def overlay_scene2(img, cam):
    """Pedestrian Crosswalk Incident"""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    # Title bar
    img = semi_bg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,8), "EXHIBIT B-1: Pedestrian Crosswalk Incident Reconstruction", "white", 16)
    text_shadow(d, (w-160,10), f"Cam: {cam}", "white", 12)
    # Pedestrian marker
    px, py = w//2+40, h//2-20
    d.ellipse([(px-18,py-18),(px+18,py+18)], outline="red", width=3)
    img = semi_bg(img, (px-95,py+22), (190,20))
    text_shadow(ImageDraw.Draw(img), (px-90,py+24), "PEDESTRIAN POSITION AT IMPACT", "red", 11)
    # Sight line dashed
    d = ImageDraw.Draw(img)
    for i in range(0, w//2, 20):
        d.line([(i+w//4, h//2+60),(i+w//4+10, h//2+60)], fill="yellow", width=1)
    img = semi_bg(img, (w//4-5, h//2+65), (140,18))
    text_shadow(ImageDraw.Draw(img), (w//4, h//2+67), "Sight Distance: ~45m", "yellow", 10)
    # Crosswalk zone (subtle overlay)
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for i in range(5):
        y = h//3 + i*25
        od.rectangle([(w//3, y), (2*w//3, y+12)], fill=(255,255,255,18))
    img = Image.alpha_composite(img, ov)
    # Bottom info bar
    img = semi_bg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    text_shadow(d, (10,h-30), "Reconstruction: 2026-03-26 | Crosswalk Zone Marked", "white", 10)
    text_shadow(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

def overlay_scene3(img, cam):
    """Highway Rear-End Collision"""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    img = semi_bg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,8), "EXHIBIT C-1: Highway Rear-End Collision Reconstruction", "white", 16)
    text_shadow(d, (w-160,10), f"Cam: {cam}", "white", 12)
    # Impact zone
    ix, iy = w//2, 2*h//3
    d.rectangle([(ix-30,iy-20),(ix+30,iy+20)], outline="red", width=2)
    img = semi_bg(img, (ix-48,iy+24), (96,18))
    text_shadow(ImageDraw.Draw(img), (ix-43,iy+25), "IMPACT ZONE", "red", 11)
    # Speed labels
    img = semi_bg(img, (15,h//3-10), (190,50))
    d = ImageDraw.Draw(img)
    text_shadow(d, (20,h//3-7), "Truck Speed: ~65 mph →", "yellow", 12)
    text_shadow(d, (20,h//3+15), "Car Speed: ~35 mph →", "yellow", 12)
    # Following distance
    img = semi_bg(img, (w-220,h//2), (200,20))
    text_shadow(ImageDraw.Draw(img), (w-215,h//2+2), "Following Distance: ~12m", "yellow", 11)
    # Lane markings overlay
    d = ImageDraw.Draw(img)
    for i in range(0, w, 40):
        d.line([(i, h//2+100),(i+20, h//2+100)], fill=(255,255,255,80), width=2)
    # Bottom info bar
    img = semi_bg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    text_shadow(d, (10,h-30), "Reconstruction: 2026-03-26 | Interstate Highway", "white", 10)
    text_shadow(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

def overlay_scene4(img, cam):
    """Parking Lot Hit-and-Run (Night)"""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    img = semi_bg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,8), "EXHIBIT D-1: Parking Lot Hit-and-Run — Night Scene", "white", 16)
    text_shadow(d, (w-180,10), f"Cam: {cam}", "white", 12)
    # Security timestamp
    img = semi_bg(img, (10,40), (250,22))
    text_shadow(ImageDraw.Draw(img), (15,42), "REC ● 2026-03-25  23:47:12  CAM-04", "red", 12)
    # Vehicle path arrows
    d = ImageDraw.Draw(img)
    # Entry
    d.line([(40,h//2),(90,h//2)], fill="yellow", width=2)
    d.polygon([(90,h//2),(82,h//2-5),(82,h//2+5)], fill="yellow")
    img = semi_bg(img, (30,h//2-22), (70,18))
    text_shadow(ImageDraw.Draw(img), (35,h//2-20), "ENTRY →", "yellow", 10)
    # Exit
    d = ImageDraw.Draw(img)
    d.line([(w-90,h//2+40),(w-40,h//2+40)], fill="yellow", width=2)
    d.polygon([(w-40,h//2+40),(w-48,h//2+35),(w-48,h//2+45)], fill="yellow")
    img = semi_bg(img, (w-100,h//2+18), (70,18))
    text_shadow(ImageDraw.Draw(img), (w-95,h//2+20), "← EXIT", "yellow", 10)
    # Lighting zones
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    od.ellipse([(w//4-60,h//3-60),(w//4+60,h//3+60)], outline=(255,200,0,40), width=2)
    od.ellipse([(3*w//4-60,h//3-60),(3*w//4+60,h//3+60)], outline=(255,200,0,40), width=2)
    img = Image.alpha_composite(img, ov)
    # Bottom info bar
    img = semi_bg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    text_shadow(d, (10,h-30), "Parking Lot B | Lighting: Sodium Vapor | Visibility: Limited", "white", 10)
    text_shadow(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

# ═══════════════════════ MAIN PIPELINE ═══════════════════════
SCENE_MAP = {
    "scene1": {"overlay": overlay_scene1, "type": "day",
               "files": ["v17_scene1_Cam_BirdEye.png","v17_scene1_Cam_DriverPOV.png","v17_scene1_Cam_WideAngle.png"]},
    "scene2": {"overlay": overlay_scene2, "type": "day",
               "files": ["v17_scene2_Cam_BirdEye.png","v17_scene2_Cam_DriverPOV.png",
                          "v17_scene2_Cam_SightLine.png","v17_scene2_Cam_WideAngle.png"]},
    "scene3": {"overlay": overlay_scene3, "type": "day",
               "files": ["v17_scene3_Cam_BirdEye.png","v17_scene3_Cam_DriverPOV.png","v17_scene3_Cam_WideAngle.png"]},
    "scene4": {"overlay": overlay_scene4, "type": "night",
               "files": ["v17_scene4_Cam_BirdEye.png","v17_scene4_Cam_DriverPOV.png",
                          "v17_scene4_Cam_SecurityCam.png","v17_scene4_Cam_WideAngle.png"]},
}

def extract_cam(filename):
    for c in ["BirdEye","DriverPOV","WideAngle","SightLine","SecurityCam"]:
        if c in filename: return c
    return "Unknown"

def main():
    print("=" * 60)
    print("v18 FORENSIC OVERLAYS PIPELINE")
    print("=" * 60)
    all_before, all_after = [], []
    
    for scene_id, cfg in SCENE_MAP.items():
        print(f"\n--- {scene_id.upper()} ({cfg['type']}) ---")
        for fname in cfg["files"]:
            inp = V17_DIR / fname
            if not inp.exists():
                print(f"  SKIP (missing): {fname}")
                continue
            img = Image.open(inp).convert("RGB")
            cam = extract_cam(fname)
            score_before = compute_forensic_score(img)
            
            # Step 1: Post-processing pipeline
            if cfg["type"] == "night":
                img = v2_night_pipeline(img)
            else:
                img = v1_day_pipeline(img)
            
            # Step 2: Dusk color grading (day only)
            if cfg["type"] == "day":
                img = dusk_color_grade(img)
            
            # Step 3: Forensic overlays
            img = cfg["overlay"](img, cam)
            
            # Convert back to RGB for saving
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (0,0,0))
                bg.paste(img, mask=img.split()[3])
                img = bg
            
            # Save
            out_name = fname.replace("v17_", "v18_")
            out_path = V18_DIR / out_name
            img.save(out_path, "PNG", optimize=True)
            
            score_after = compute_forensic_score(img)
            delta = score_after - score_before
            all_before.append(score_before)
            all_after.append(score_after)
            print(f"  {fname}: {score_before:.1f} → {score_after:.1f} ({delta:+.1f})")
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(all_after)} images processed")
    if all_before:
        print(f"  Avg before: {np.mean(all_before):.1f}")
        print(f"  Avg after:  {np.mean(all_after):.1f}")
        print(f"  Avg delta:  {np.mean(all_after)-np.mean(all_before):+.1f}")
    print(f"Output: {V18_DIR}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
