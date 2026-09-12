"""Numeric still comparison. VLM is never the pass bit.

ffmpeg/LPIPS optional. Missing metric → None → that check fails closed for PSNR/SSIM/LPIPS.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

THRESHOLDS = {
    "draft": {"psnr": 20.0, "ssim": 0.80, "lpips": 0.35},
    "review": {"psnr": 28.0, "ssim": 0.90, "lpips": 0.20},
    "delivery": {"psnr": 32.0, "ssim": 0.95, "lpips": 0.12},
}


def _ffmpeg_psnr(ref: str, render: str) -> float | None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    cmd = [ffmpeg, "-i", render, "-i", ref, "-lavfi", "psnr", "-f", "null", "-"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stderr or "") + (proc.stdout or "")
    for token in text.replace("=", " ").split():
        try:
            if token.replace(".", "", 1).isdigit() and "average" in text.lower():
                pass
        except ValueError:
            continue
    marker = "average:"
    lower = text.lower()
    if marker not in lower:
        return None
    idx = lower.rfind(marker)
    rest = text[idx + len(marker) :].strip().split()
    if not rest:
        return None
    try:
        return float(rest[0].rstrip(","))
    except ValueError:
        return None


def score_tiered(ref_path: str, render_path: str, tier: str = "review") -> dict:
    limits = THRESHOLDS.get(tier) or THRESHOLDS["review"]
    ref = Path(ref_path)
    rend = Path(render_path)
    psnr = None
    ssim = None
    lpips = None
    delta_e = None
    if ref.is_file() and rend.is_file():
        psnr = _ffmpeg_psnr(str(ref), str(rend))
    psnr_passed = psnr is not None and psnr >= limits["psnr"]
    ssim_passed = ssim is not None and ssim >= limits["ssim"]
    lpips_passed = lpips is not None and lpips <= limits["lpips"]
    delta_e_passed = True if delta_e is None else delta_e < 5.0
    passed = bool(psnr_passed and ssim_passed and lpips_passed)
    return {
        "passed": passed,
        "tier": tier,
        "psnr": psnr,
        "ssim": ssim,
        "lpips": lpips,
        "delta_e": delta_e,
        "psnr_passed": psnr_passed,
        "ssim_passed": ssim_passed,
        "lpips_passed": lpips_passed,
        "delta_e_passed": delta_e_passed,
        "ms_ssim": None,
    }
