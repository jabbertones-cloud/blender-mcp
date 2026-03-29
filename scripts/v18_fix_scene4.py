#!/usr/bin/env python3
"""v18 Scene 4 fix: apply ONLY overlays to v17 night renders (already processed)."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path

V17_DIR = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v17_hybrid")
V18_DIR = Path("/Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/v18_forensic")

def get_font(size=14):
    for fp in ["/System/Library/Fonts/Helvetica.ttc",
               "/System/Library/Fonts/SFNSMono.ttf"]:
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

def overlay_scene4(img, cam):
    """Parking Lot Hit-and-Run (Night) — OVERLAY ONLY, no reprocessing."""
    if img.mode != "RGBA": img = img.convert("RGBA")
    w, h = img.size
    # Title bar
    img = semi_bg(img, (0,0), (w,36))
    d = ImageDraw.Draw(img)
    text_shadow(d, (10,8), "EXHIBIT D-1: Parking Lot Hit-and-Run — Night Scene", "white", 16)
    text_shadow(d, (w-180,10), f"Cam: {cam}", "white", 12)
    # Security timestamp
    img = semi_bg(img, (10,40), (250,22))
    text_shadow(ImageDraw.Draw(img), (15,42), "REC ● 2026-03-25  23:47:12  CAM-04", "red", 12)
    # Vehicle path arrows
    d = ImageDraw.Draw(img)
    d.line([(40,h//2),(90,h//2)], fill="yellow", width=2)
    d.polygon([(90,h//2),(82,h//2-5),(82,h//2+5)], fill="yellow")
    img = semi_bg(img, (30,h//2-22), (70,18))
    text_shadow(ImageDraw.Draw(img), (35,h//2-20), "ENTRY →", "yellow", 10)
    d = ImageDraw.Draw(img)
    d.line([(w-90,h//2+40),(w-40,h//2+40)], fill="yellow", width=2)
    d.polygon([(w-40,h//2+40),(w-48,h//2+35),(w-48,h//2+45)], fill="yellow")
    img = semi_bg(img, (w-100,h//2+18), (70,18))
    text_shadow(ImageDraw.Draw(img), (w-95,h//2+20), "← EXIT", "yellow", 10)
    # Lighting zone circles
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

def extract_cam(filename):
    for c in ["BirdEye","DriverPOV","WideAngle","SecurityCam"]:
        if c in filename: return c
    return "Unknown"

def main():
    files = ["v17_scene4_Cam_BirdEye.png","v17_scene4_Cam_DriverPOV.png",
             "v17_scene4_Cam_SecurityCam.png","v17_scene4_Cam_WideAngle.png"]
    for fname in files:
        inp = V17_DIR / fname
        if not inp.exists():
            print(f"SKIP: {fname}"); continue
        img = Image.open(inp).convert("RGB")
        cam = extract_cam(fname)
        img = overlay_scene4(img, cam)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (0,0,0))
            bg.paste(img, mask=img.split()[3])
            img = bg
        out = V18_DIR / fname.replace("v17_", "v18_")
        img.save(out, "PNG", optimize=True)
        print(f"  {fname} → {out.name} (overlay only)")
    print("Scene 4 fix complete.")

if __name__ == "__main__":
    main()
