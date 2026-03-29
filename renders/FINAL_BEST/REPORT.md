# Hyperrealistic Forensic Render Quality Report

## Executive Summary

**Average Score: 94.7/100** across 16 camera renders of 4 forensic accident scenes.
14 of 16 renders exceed the 85-point quality threshold. 5 achieve perfect 100.

This represents a complete pipeline upgrade from basic geometry + post-processing (v20 baseline)
to physically-based Cycles rendering with real 3D vehicle models, HDRI environment lighting,
PBR materials, and targeted post-processing optimization.

## Score Breakdown

| Scene | Camera | Score | Status |
|-------|--------|-------|--------|
| 1: T-Bone Collision | BirdEye | 84 | PLATEAU |
| 1: T-Bone Collision | DriverPOV | 100 | PERFECT |
| 1: T-Bone Collision | SecurityCam | 99 | EXCELLENT |
| 1: T-Bone Collision | Wide | 89 | GOOD |
| 2: Pedestrian Crosswalk | BirdEye | 85 | PASS |
| 2: Pedestrian Crosswalk | DriverPOV | 100 | PERFECT |
| 2: Pedestrian Crosswalk | SecurityCam | 96 | EXCELLENT |
| 2: Pedestrian Crosswalk | Wide | 100 | PERFECT |
| 3: Highway Rear-End | BirdEye | 94 | EXCELLENT |
| 3: Highway Rear-End | DriverPOV | 100 | PERFECT |
| 3: Highway Rear-End | SecurityCam | 99 | EXCELLENT |
| 3: Highway Rear-End | Wide | 99 | EXCELLENT |
| 4: Parking Lot Hit-Run | BirdEye | 99 | EXCELLENT |
| 4: Parking Lot Hit-Run | DriverPOV | 84 | PLATEAU |
| 4: Parking Lot Hit-Run | SecurityCam | 87 | GOOD |
| 4: Parking Lot Hit-Run | Wide | 100 | PERFECT |

## Technology Stack

### Render Pipeline
- Blender Cycles (physically-based path tracer)
- Metal GPU acceleration (macOS)
- OpenImageDenoise post-render
- Filmic color management + Medium Contrast
- 64-128 samples per camera

### 3D Assets (all CC0/open license)
- 12 OpenX production vehicle models (.blend)
- 7 Polyhaven HDRI environment maps (2K EXR)
- PBR asphalt texture set (diffuse + normal + roughness)

### Vehicle Assignments
- Scene 1: BMW X1 2016 + Volvo V60 Polestar 2013
- Scene 2: Hyundai Tucson 2015
- Scene 3: Audi Q7 2015 + Dacia Duster 2010
- Scene 4: GMC Hummer 2021 + Mini Countryman 2016

### HDRI Environment Maps
- Scene 1: urban_street_01 (London urban street)
- Scene 2: crosswalk (Polyhaven pedestrian crossing)
- Scene 3: derelict_overpass (Polyhaven highway) / wide_street_01 (fallback)
- Scene 4: cobblestone_street_night (Polyhaven night urban)

### Post-Processing (applied on Cycles renders)
- combined_conservative: 56% win rate (default)
- combined_aggressive: 19% (SecurityCam angles)
- detail: 13% (DriverPOV angles)
- denoise: 13% (noisy cameras)

## Improvement Journey

| Version | Avg Score | Method |
|---------|-----------|--------|
| v9 (baseline) | ~65 | Basic geometry, EEVEE |
| v18 | ~85 | Forensic overlays + grading |
| v20 | 95.2 | Optimized post-processing |
| v21-hyper raw | 60.75 | Cycles + real models (no post-proc) |
| v21-hyper final | **94.7** | Cycles + models + post-processing |

## Plateau Analysis

Two cameras remain at 84 despite exhaustive optimization:

1. **scene1_BirdEye (84)**: Noise-limited. Overhead angle captures more HDRI reflection noise.
   256 samples + OpenImageDenoise still insufficient. Needs 512+ samples or camera repositioning.

2. **scene4_DriverPOV (84)**: Brightness-limited. Night scene produces 0.13 brightness (target 0.45).
   Boosted street lights to 2000W + added fill light + raised HDRI to 0.3 — still dark.
   Needs fundamentally different night lighting approach.

## Files

All 16 best renders: `renders/FINAL_BEST/*_BEST.png`
Hyperrealistic .blend files: `renders/hyperrealistic/hyperrealistic_scene{1-4}.blend`
Worker agent state: `agent-state/agents/blender_render_worker/`
