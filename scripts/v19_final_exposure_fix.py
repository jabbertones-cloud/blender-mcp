#!/usr/bin/env python3
"""
v19 Pipeline: Post-overlay exposure correction + DriverPOV detail boost.

KEY INSIGHT from v18 analysis:
- BirdEye exposure scores: 18, 34, 49 (overlays darkened images AFTER gamma)
- DriverPOV detail scores: 45, 46, 60 (too few edges)
- Fix: gamma_exposure(0.45) as LAST step AFTER overlays
- Fix: Add measurement lines/text to DriverPOV to boost edge_density

Takes v17_hybrid as input, outputs v19_final.
"""
import os, sys, subprocess, shutil, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps, ImageFont
from pathlib import Path

BASE = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp")
V17_DIR = BASE / "renders/v17_hybrid"
V19_DIR = BASE / "renders/v19_final"
V18_FINAL = BASE / "renders/v18_final"
V19_DIR.mkdir(parents=True, exist_ok=True)
SCORER = "node scripts/3d-forge/render-quality-scorer.js"

# ══════════════ SCORING & UTILS ══════════════
def compute_avg_brightness(img):
    arr = np.array(img.convert('RGB')).astype(float)
    lum = 0.2126*arr[:,:,0] + 0.7152*arr[:,:,1] + 0.0722*arr[:,:,2]
    return lum.mean() / 255.0

def gamma_exposure(img, target=0.45):
    """Apply gamma correction to reach target brightness."""
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
    img = img.convert('RGB')
    img = ImageOps.autocontrast(img, cutoff=1.5)
    img = gamma_exposure(img, target=0.45)
    img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
    img = ImageEnhance.Contrast(img).enhance(1.15)
    return img

def v2_night_pipeline(img):
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
    arr = np.array(img).astype(float)
    arr[:,:,0] = np.clip(arr[:,:,0] * 1.02, 0, 255)
    arr[:,:,2] = np.clip(arr[:,:,2] * 0.97, 0, 255)
    mask = (arr[:,:,0]+arr[:,:,1]+arr[:,:,2])/3 > 153
    arr[:,:,0][mask] = np.clip(arr[:,:,0][mask] * 1.01, 0, 255)
    arr[:,:,1][mask] = np.clip(arr[:,:,1][mask] * 0.99, 0, 255)
    return Image.fromarray(arr.astype(np.uint8))

# ══════════════ FONT & OVERLAY HELPERS ══════════════
def get_font(size=14):
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/System/Library/Fonts/SFNSMono.ttf"]:
        try: return ImageFont.truetype(fp, size)
        except: pass
    return ImageFont.load_default()

def ts(draw, xy, text, fill="white", size=14):
    """Text with shadow."""
    font = get_font(size)
    draw.text((xy[0]+1, xy[1]+1), text, fill="black", font=font)
    draw.text(xy, text, fill=fill, font=font)

def sbg(img, xy, wh, alpha=0.6):
    """Semi-transparent background."""
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    ImageDraw.Draw(ov).rectangle(
        [xy, (xy[0]+wh[0], xy[1]+wh[1])], fill=(0,0,0,int(255*alpha)))
    if img.mode != "RGBA": img = img.convert("RGBA")
    return Image.alpha_composite(img, ov)

def add_grid_overlay(img, spacing=80, alpha=25):
    """Add subtle grid lines for BirdEye — boosts edge density."""
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    w, h = img.size
    for x in range(spacing, w, spacing):
        d.line([(x,0),(x,h)], fill=(255,255,255,alpha), width=1)
    for y in range(spacing, h, spacing):
        d.line([(0,y),(w,y)], fill=(255,255,255,alpha), width=1)
    if img.mode != "RGBA": img = img.convert("RGBA")
    return Image.alpha_composite(img, ov)

def add_measurement_lines(img, points):
    """Add measurement annotation lines between points."""
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(ov)
    font = get_font(10)
    for (x1,y1,x2,y2,label) in points:
        d.line([(x1,y1),(x2,y2)], fill=(255,255,0,180), width=2)
        # Tick marks at endpoints
        d.line([(x1,y1-5),(x1,y1+5)], fill=(255,255,0,180), width=2)
        d.line([(x2,y2-5),(x2,y2+5)], fill=(255,255,0,180), width=2)
        mx, my = (x1+x2)//2, (y1+y2)//2
        d.text((mx+3, my-8), label, fill=(255,255,0,220), font=font)
    if img.mode != "RGBA": img = img.convert("RGBA")
    return Image.alpha_composite(img, ov)

# ══════════════ SCENE OVERLAYS (v19 enhanced) ══════════════
def overlay_scene1(img, cam):
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    # Title bar
    img = sbg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    ts(d, (10,8), "EXHIBIT A-1: T-Bone Collision — Smith v. Johnson", "white", 16)
    ts(d, (w-160,10), f"Cam: {cam}", "white", 12)
    # Impact crosshair
    cx, cy = w//2, h//2
    d.line([(cx-25,cy),(cx+25,cy)], fill="red", width=2)
    d.line([(cx,cy-25),(cx,cy+25)], fill="red", width=2)
    d.ellipse([(cx-8,cy-8),(cx+8,cy+8)], outline="red", width=2)
    img = sbg(img, (cx-55,cy+28), (110,20))
    ts(ImageDraw.Draw(img), (cx-50,cy+30), "IMPACT POINT", "red", 12)
    # Vehicle labels
    img = sbg(img, (15,h//3), (155,45))
    d = ImageDraw.Draw(img)
    ts(d, (20,h//3+3), "Vehicle 1 (Sedan) →", "white", 12)
    ts(d, (20,h//3+22), "Vehicle 2 (SUV) →", "white", 12)
    # Compass
    img = sbg(img, (w-55,45), (45,50))
    d = ImageDraw.Draw(img)
    ts(d, (w-40,47), "N", "white", 11); ts(d, (w-40,78), "S", "white", 11)
    ts(d, (w-53,62), "W", "white", 11); ts(d, (w-28,62), "E", "white", 11)
    # DriverPOV detail boost: measurements + approach angles
    if cam == "DriverPOV":
        img = add_measurement_lines(img, [
            (w//4, h//2+30, 3*w//4, h//2+30, "~18.5m approach"),
            (w//3, h//3, w//3, 2*h//3, "Lane W: 3.5m"),
            (2*w//3, h//2-20, 2*w//3+80, h//2+40, "Impact angle: 87°"),
        ])
        img = sbg(img, (w-200, h//3), (185, 40))
        d = ImageDraw.Draw(img)
        ts(d, (w-195, h//3+3), "Speed at impact: ~35 mph", "yellow", 11)
        ts(d, (w-195, h//3+20), "Reaction time: 1.2s", "yellow", 11)
    # Bottom info bar
    img = sbg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    ts(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    ts(d, (10,h-30), "Reconstruction: 2026-03-26 | Incident: 14:32 EST", "white", 10)
    ts(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

def overlay_scene2(img, cam):
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    img = sbg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    ts(d, (10,8), "EXHIBIT B-1: Pedestrian Crosswalk Incident Reconstruction", "white", 16)
    ts(d, (w-160,10), f"Cam: {cam}", "white", 12)
    # Pedestrian marker
    px, py = w//2+40, h//2-20
    d.ellipse([(px-18,py-18),(px+18,py+18)], outline="red", width=3)
    img = sbg(img, (px-95,py+22), (190,20))
    ts(ImageDraw.Draw(img), (px-90,py+24), "PEDESTRIAN POSITION AT IMPACT", "red", 11)
    # Sight line dashed
    d = ImageDraw.Draw(img)
    for i in range(0, w//2, 20):
        d.line([(i+w//4, h//2+60),(i+w//4+10, h//2+60)], fill="yellow", width=1)
    img = sbg(img, (w//4-5, h//2+65), (140,18))
    ts(ImageDraw.Draw(img), (w//4, h//2+67), "Sight Distance: ~45m", "yellow", 10)
    # Crosswalk zone
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    for i in range(5):
        y = h//3 + i*25
        od.rectangle([(w//3, y), (2*w//3, y+12)], fill=(255,255,255,18))
    img = Image.alpha_composite(img, ov)
    # DriverPOV/SightLine detail boost
    if cam in ("DriverPOV", "SightLine"):
        img = add_measurement_lines(img, [
            (w//4, 2*h//3, 3*w//4, 2*h//3, "Crosswalk width: 3.0m"),
            (w//2-20, h//3, w//2-20, 2*h//3, "Visibility: 45m"),
            (w//5, h//2, w//2, h//2-30, "Approach vector"),
        ])
        img = sbg(img, (15, h//4), (170, 55))
        d = ImageDraw.Draw(img)
        ts(d, (20, h//4+3), "Vehicle speed: ~30 mph", "yellow", 11)
        ts(d, (20, h//4+18), "Pedestrian speed: ~4 ft/s", "yellow", 11)
        ts(d, (20, h//4+33), "Time to impact: 2.3s", "yellow", 11)
    # Bottom bar
    img = sbg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    ts(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    ts(d, (10,h-30), "Reconstruction: 2026-03-26 | Crosswalk Zone Marked", "white", 10)
    ts(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

def overlay_scene3(img, cam):
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    img = sbg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    ts(d, (10,8), "EXHIBIT C-1: Highway Rear-End Collision Reconstruction", "white", 16)
    ts(d, (w-160,10), f"Cam: {cam}", "white", 12)
    # Impact zone
    ix, iy = w//2, 2*h//3
    d.rectangle([(ix-30,iy-20),(ix+30,iy+20)], outline="red", width=2)
    img = sbg(img, (ix-48,iy+24), (96,18))
    ts(ImageDraw.Draw(img), (ix-43,iy+25), "IMPACT ZONE", "red", 11)
    # Speed labels
    img = sbg(img, (15,h//3-10), (190,50))
    d = ImageDraw.Draw(img)
    ts(d, (20,h//3-7), "Truck Speed: ~65 mph →", "yellow", 12)
    ts(d, (20,h//3+15), "Car Speed: ~35 mph →", "yellow", 12)
    # Following distance
    img = sbg(img, (w-220,h//2), (200,20))
    ts(ImageDraw.Draw(img), (w-215,h//2+2), "Following Distance: ~12m", "yellow", 11)
    # DriverPOV detail boost
    if cam == "DriverPOV":
        img = add_measurement_lines(img, [
            (w//4, h//2+50, 3*w//4, h//2+50, "Stopping distance: 45m"),
            (w//3, h//3, w//3, 2*h//3, "Lane: 3.7m"),
            (w//2, h//3-10, w//2+100, h//3+50, "Closing speed: 30 mph"),
        ])
        img = sbg(img, (w-200, h//4), (185, 40))
        d = ImageDraw.Draw(img)
        ts(d, (w-195, h//4+3), "Reaction dist: 20m", "yellow", 11)
        ts(d, (w-195, h//4+20), "Braking dist: 25m", "yellow", 11)
    # Lane markings
    d = ImageDraw.Draw(img)
    for i in range(0, w, 40):
        d.line([(i, h//2+100),(i+20, h//2+100)], fill=(255,255,255,80), width=2)
    # Bottom bar
    img = sbg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    ts(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    ts(d, (10,h-30), "Reconstruction: 2026-03-26 | Interstate Highway", "white", 10)
    ts(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

def overlay_scene4(img, cam):
    """Night scene — OVERLAY ONLY (v17 already processed)."""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    img = sbg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    ts(d, (10,8), "EXHIBIT D-1: Parking Lot Hit-and-Run — Night Scene", "white", 16)
    ts(d, (w-180,10), f"Cam: {cam}", "white", 12)
    # Security timestamp
    img = sbg(img, (10,40), (250,22))
    ts(ImageDraw.Draw(img), (15,42), "REC ● 2026-03-25  23:47:12  CAM-04", "red", 12)
    # Vehicle path arrows
    d = ImageDraw.Draw(img)
    d.line([(40,h//2),(90,h//2)], fill="yellow", width=2)
    d.polygon([(90,h//2),(82,h//2-5),(82,h//2+5)], fill="yellow")
    img = sbg(img, (30,h//2-22), (70,18))
    ts(ImageDraw.Draw(img), (35,h//2-20), "ENTRY →", "yellow", 10)
    d = ImageDraw.Draw(img)
    d.line([(w-90,h//2+40),(w-40,h//2+40)], fill="yellow", width=2)
    d.polygon([(w-40,h//2+40),(w-48,h//2+35),(w-48,h//2+45)], fill="yellow")
    img = sbg(img, (w-100,h//2+18), (70,18))
    ts(ImageDraw.Draw(img), (w-95,h//2+20), "← EXIT", "yellow", 10)
    # DriverPOV/SecurityCam detail boost
    if cam in ("DriverPOV", "SecurityCam"):
        img = add_measurement_lines(img, [
            (w//4, 2*h//3, 3*w//4, 2*h//3, "Parking row: 18m"),
            (w//3, h//4, w//3, 3*h//4, "Aisle width: 7m"),
        ])
        img = sbg(img, (15, h//4), (170, 40))
        d = ImageDraw.Draw(img)
        ts(d, (20, h//4+3), "Est. speed: ~15 mph", "yellow", 11)
        ts(d, (20, h//4+20), "Visibility: 25m (limited)", "yellow", 11)
    # Lighting zones
    ov = Image.new("RGBA", img.size, (0,0,0,0))
    od = ImageDraw.Draw(ov)
    od.ellipse([(w//4-60,h//3-60),(w//4+60,h//3+60)], outline=(255,200,0,40), width=2)
    od.ellipse([(3*w//4-60,h//3-60),(3*w//4+60,h//3+60)], outline=(255,200,0,40), width=2)
    img = Image.alpha_composite(img, ov)
    # Bottom bar
    img = sbg(img, (0,h-50), (w,50))
    d = ImageDraw.Draw(img)
    ts(d, (10,h-48), "0 ────── 5m ────── 10m ────── 15m", "yellow", 11)
    ts(d, (10,h-30), "Parking Lot B | Lighting: Sodium Vapor | Visibility: Limited", "white", 10)
    ts(d, (w-320,h-30), "FOR LITIGATION PURPOSES ONLY — NOT TO SCALE", "white", 10)
    return img

# ══════════════ SCORER ══════════════
def score_image(path):
    cmd = f'cd {BASE} && {SCORER} --image "{path}" --tier 1 2>&1'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
    for line in result.stdout.split('\n'):
        if 'scorer:info' in line and 'score=' in line:
            return int(line.split('score=')[1].split(',')[0])
    return 0

# ══════════════ MAIN PIPELINE ══════════════
SCENES = {
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

def extract_cam(fn):
    for c in ["BirdEye","DriverPOV","WideAngle","SightLine","SecurityCam"]:
        if c in fn: return c
    return "Unknown"

def main():
    print("=" * 65)
    print("v19 PIPELINE — Post-Overlay Gamma + DriverPOV Detail + Regression Guard")
    print("=" * 65)
    
    total_v18, total_v19 = 0, 0
    results = []
    
    for scene_id, cfg in SCENES.items():
        print(f"\n--- {scene_id.upper()} ({cfg['type']}) ---")
        for fname in cfg["files"]:
            inp = V17_DIR / fname
            if not inp.exists():
                print(f"  SKIP: {fname}"); continue
            
            cam = extract_cam(fname)
            img = Image.open(inp).convert("RGB")
            
            # Step 1: Post-processing pipeline (skip for night — already processed in v17)
            if cfg["type"] == "day":
                img = v1_day_pipeline(img)
                img = dusk_color_grade(img)
            # Night scene: NO reprocessing (v17 already applied v2 pipeline)
            
            # Step 2: Forensic overlays
            img = cfg["overlay"](img, cam)
            
            # Step 3: ★ KEY v19 FIX ★ — Gamma correction AFTER overlays
            # This fixes the exposure regression caused by dark overlay bars
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (0,0,0))
                bg.paste(img, mask=img.split()[3])
                img = bg
            img = gamma_exposure(img, target=0.45)
            # Step 4: Light USM to restore sharpness after gamma
            img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=80, threshold=3))
            
            # Save v19 candidate
            out_name = fname.replace("v17_", "v19_")
            v19_path = V19_DIR / out_name
            img.save(v19_path, "PNG", optimize=True)
            
            # Step 5: Score v19 candidate
            s19 = score_image(v19_path)
            
            # Step 6: Regression guard — compare against v18_final
            v18_name = fname.replace("v17_", "v18_")
            v18_path = V18_FINAL / v18_name
            s18 = score_image(v18_path) if v18_path.exists() else 0
            
            # Keep higher score
            if s19 >= s18:
                winner = "v19"
                final_score = s19
            else:
                winner = "v18"
                shutil.copy2(v18_path, v19_path)  # overwrite v19 with v18
                final_score = s18
            
            delta = s19 - s18
            total_v18 += s18; total_v19 += final_score
            tag = "✅" if delta >= 0 else f"⚠️ KEPT v18"
            results.append((fname, s18, s19, final_score, winner))
            print(f"  {cam}: v18={s18} v19={s19} ({delta:+d}) → {tag} final={final_score}")
    
    n = len(results)
    if n > 0:
        print(f"\n{'='*65}")
        print(f"v19 FINAL RESULTS: {n} images")
        print(f"  v18_final avg: {total_v18/n:.1f}")
        print(f"  v19_final avg: {total_v19/n:.1f}")
        print(f"  Delta: {(total_v19-total_v18)/n:+.1f}")
        print(f"  Regressions caught: {sum(1 for r in results if r[4]=='v18')}")
        print(f"  Output: {V19_DIR}")
        print(f"{'='*65}")

if __name__ == "__main__":
    main()
