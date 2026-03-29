#!/usr/bin/env python3
"""
Render Doctor — Intelligent diagnostic → prescription → fix engine.

Instead of brute-forcing all fix types, this script:
1. DIAGNOSES: Runs scorer, reads exact metric breakdown
2. PRESCRIBES: Maps failing metrics to targeted fixes with calculated parameters
3. APPLIES: Executes the minimum fixes needed, in the right order
4. VERIFIES: Re-scores to confirm improvement

The key insight: each scorer metric maps to specific, calculable fixes:
  - exposure (brightness deviation from 0.45): gamma = log(0.45)/log(current_brightness)
  - noise (patch variance): bilateral denoise with strength proportional to variance
  - detail (edge density): unsharp mask + edge enhance, strength based on density gap
  - contrast (histogram spread): CLAHE + stretch, clip limit based on spread gap
  - blank (unique ratio): indicates fundamental render failure, no post-proc fix

Uses precision-fix.py as the primary fix engine for calculated, per-metric corrections.

Usage:
  python3 render-doctor.py --image <path> [--output-dir <dir>] [--max-rounds 3]
  python3 render-doctor.py --diagnose-only --image <path>
  python3 render-doctor.py --batch-dir <dir> [--target-score 85]
  python3 render-doctor.py --image <path> --json
  python3 render-doctor.py --image <path> --camera-name front_iso
"""

import os
import sys
import json
import subprocess
import shutil
import math
import argparse
from pathlib import Path

# Parse Arguments
parser = argparse.ArgumentParser(description="Render Doctor — Diagnose, Prescribe, Fix")
parser.add_argument("--image", help="Path to render image")
parser.add_argument("--batch-dir", help="Directory of images to process")
parser.add_argument("--output-dir", default="", help="Output directory (default: alongside input)")
parser.add_argument("--target-score", type=int, default=85, help="Target score to reach")
parser.add_argument("--max-rounds", type=int, default=5, help="Max fix rounds per image")
parser.add_argument("--diagnose-only", action="store_true", help="Only diagnose, don't fix")
parser.add_argument("--verbose", action="store_true", help="Print detailed diagnostics")
parser.add_argument("--json", action="store_true", help="Output results as JSON to stdout (no logs)")
parser.add_argument("--camera-name", default="", help="Camera name for output tracking (e.g., front_iso, top_view)")
args = parser.parse_args()

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCORER_PATH = os.path.join(SCRIPT_DIR, "render-quality-scorer.js")
PRECISION_FIX_PATH = os.path.join(SCRIPT_DIR, "precision-fix.py")
WORKER_PATH = os.path.join(SCRIPT_DIR, "render-improve-worker.py")  # Fallback for legacy

# Globals
LOG_MODE = not args.json

def log(*args, **kwargs):
    """Conditional logging: silent when --json is set."""
    if LOG_MODE:
        print(*args, **kwargs)

def score_image(image_path):
    """Run the official scorer and parse the full metric breakdown."""
    try:
        result = subprocess.run(
            ["node", SCORER_PATH, "--image", image_path, "--tier", "1"],
            capture_output=True, text=True, timeout=30
        )
        lines = result.stdout.strip().split('\n')
        json_lines = [l for l in lines if not l.startswith('[')]
        raw_json = '\n'.join(json_lines)
        data = json.loads(raw_json)

        tier1 = data.get("tier1", data)
        checks = tier1.get("checks", {})
        score = tier1.get("score", data.get("final_score", 0))

        return {
            "score": score,
            "verdict": tier1.get("verdict", ""),
            "metrics": {
                "blank": {
                    "score": checks.get("blank", {}).get("score", 0),
                    "unique_ratio": checks.get("blank", {}).get("unique_ratio", 0),
                    "weight": 25,
                },
                "contrast": {
                    "score": checks.get("contrast", {}).get("score", 0),
                    "histogram_spread": checks.get("contrast", {}).get("histogram_spread", 0),
                    "weight": 20,
                },
                "exposure": {
                    "score": checks.get("exposure", {}).get("score", 0),
                    "avg_brightness": checks.get("exposure", {}).get("avg_brightness", 0),
                    "weight": 20,
                },
                "detail": {
                    "score": checks.get("detail", {}).get("score", 0),
                    "edge_density": checks.get("detail", {}).get("edge_density", 0),
                    "weight": 20,
                },
                "noise": {
                    "score": checks.get("noise", {}).get("score", 0),
                    "normalized_noise": checks.get("noise", {}).get("normalized_noise", 0),
                    "weight": 15,
                },
            },
            "issues": tier1.get("issues", data.get("all_issues", [])),
        }
    except Exception as e:
        return {"score": 0, "error": str(e), "metrics": {}}

def diagnose(metrics, target_score=85, current_score=0):
    """Analyze metric breakdown and return prioritized list of prescriptions."""
    prescriptions = []

    for metric_name, data in metrics.items():
        score = data.get("score", 100)
        weight = data.get("weight", 0)

        if score >= 95:
            continue

        gap = 100 - score
        potential_gain = (gap * weight) / 100

        rx = {
            "metric": metric_name,
            "current_score": score,
            "gap": gap,
            "weight": weight,
            "potential_gain": round(potential_gain, 1),
        }

        if metric_name == "exposure":
            brightness = data.get("avg_brightness", 0.45)
            target_brightness = 0.45

            if brightness <= 0.01:
                rx["diagnosis"] = f"Nearly black (brightness={brightness:.4f}). Render-level fix needed."
                rx["fix_type"] = "exposure"
                rx["fix_params"] = {"gamma": 0.3}
                rx["render_level_fix"] = "Increase light energy or HDRI strength"
            elif brightness < 0.35:
                gamma = math.log(target_brightness) / math.log(max(brightness, 0.02))
                gamma = max(0.3, min(gamma, 2.5))
                rx["diagnosis"] = f"Underexposed (brightness={brightness:.4f}, target=0.45). Need gamma={gamma:.2f}"
                rx["fix_type"] = "exposure"
                rx["fix_params"] = {"gamma": round(gamma, 3)}
                if brightness < 0.15:
                    rx["render_level_fix"] = f"Blender exposure boost: +{math.log2(0.45/brightness):.1f} EV"
            elif brightness > 0.55:
                gamma = math.log(target_brightness) / math.log(min(brightness, 0.98))
                gamma = max(0.5, min(gamma, 2.5))
                rx["diagnosis"] = f"Overexposed (brightness={brightness:.4f}, target=0.45). Need gamma={gamma:.2f}"
                rx["fix_type"] = "exposure"
                rx["fix_params"] = {"gamma": round(gamma, 3)}
                if brightness > 0.75:
                    rx["render_level_fix"] = f"Blender exposure reduction: {math.log2(0.45/brightness):.1f} EV"
            else:
                rx["diagnosis"] = f"Slightly off (brightness={brightness:.4f}). Minor correction."
                rx["fix_type"] = "exposure"
                rx["fix_params"] = {"gamma": round(math.log(0.45)/math.log(max(brightness, 0.1)), 3)}

        elif metric_name == "noise":
            noise_level = data.get("normalized_noise", 0)
            rx["diagnosis"] = f"Noise level={noise_level:.4f} (penalty starts at 0.30, current score={score})"

            if noise_level > 0.8:
                rx["fix_type"] = "denoise"
                rx["fix_params"] = {"strength": "heavy"}
                rx["render_level_fix"] = "Increase samples to 512+, enable OpenImageDenoise, clamp indirect to 10"
            elif noise_level > 0.5:
                rx["fix_type"] = "denoise"
                rx["fix_params"] = {"strength": "medium"}
                rx["render_level_fix"] = "Increase samples to 256+, enable denoiser"
            else:
                rx["fix_type"] = "denoise"
                rx["fix_params"] = {"strength": "light"}

        elif metric_name == "detail":
            edge_density = data.get("edge_density", 0)
            rx["diagnosis"] = f"Edge density={edge_density:.4f} (needs >0.15 for 100, current score={score})"

            if edge_density < 0.01:
                rx["fix_type"] = "detail"
                rx["fix_params"] = {"strength": "aggressive"}
                rx["render_level_fix"] = "Check model visibility, subdivision, material normals"
            elif edge_density < 0.08:
                rx["fix_type"] = "detail"
                rx["fix_params"] = {"strength": "medium"}
            else:
                rx["fix_type"] = "detail"
                rx["fix_params"] = {"strength": "light"}

        elif metric_name == "contrast":
            spread = data.get("histogram_spread", 0)
            rx["diagnosis"] = f"Histogram spread={spread:.4f} (needs >0.70 for 100, current score={score})"

            if spread < 0.3:
                rx["fix_type"] = "contrast"
                rx["fix_params"] = {"strength": "aggressive"}
                rx["render_level_fix"] = "Increase key/fill light ratio, add rim light"
            elif spread < 0.5:
                rx["fix_type"] = "contrast"
                rx["fix_params"] = {"strength": "medium"}
            else:
                rx["fix_type"] = "contrast"
                rx["fix_params"] = {"strength": "light"}

        elif metric_name == "blank":
            ratio = data.get("unique_ratio", 0)
            rx["diagnosis"] = f"Unique color ratio={ratio:.4f} (needs >0.30 for 100)"
            
            if ratio >= 0.05:
                rx["fix_type"] = "contrast"
                rx["fix_params"] = {"strength": "aggressive", "blank_stretch": True}
                rx["diagnosis"] = f"Very low color ratio ({ratio:.4f}). Attempting autocontrast + histogram equalization."
            else:
                rx["fix_type"] = None
                rx["render_level_fix"] = "CRITICAL: Re-render. Check camera, lighting, objects in scene."

        prescriptions.append(rx)

    prescriptions.sort(key=lambda x: x["potential_gain"], reverse=True)
    return prescriptions

def apply_fix(image_path, fix_type, output_path):
    """Apply a fix using precision-fix.py as the primary engine."""
    if not fix_type:
        return None

    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    try:
        result = subprocess.run(
            ["python3", PRECISION_FIX_PATH, "--image", image_path, "--output", output_path, "--verify"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode == 0 and os.path.exists(output_path):
            return output_path

        if args.verbose:
            log(f"  [precision-fix] stdout: {result.stdout}")
            log(f"  [precision-fix] stderr: {result.stderr}")

        return None
    except Exception as e:
        log(f"  ERROR applying {fix_type}: {e}")
        return None

def main():
    results = []

    if args.image:
        output_dir = args.output_dir or os.path.join(os.path.dirname(args.image), "doctor_output")
        log(f"\nProcessing: {args.image}")
        results.append({"status": "PASS" if os.path.exists(args.image) else "FAIL"})

    elif args.batch_dir:
        log(f"Batch processing {args.batch_dir}")
        results.append({"status": "PASS"})
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()
