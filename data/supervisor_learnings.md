# Supervisor Learnings — 2026-03-26

## Summary
- Total experiments: 20
- Win rate: 85%
- Best fix type: detail
- Plateau: No

## Fix Type Effectiveness
- **detail**: 100% win rate, avg delta 20.2, 3 trials
- **exposure**: 100% win rate, avg delta 1.9, 3 trials
- **denoise**: 100% win rate, avg delta 0.7, 10 trials
- **contrast**: 100% win rate, avg delta 0.6, 1 trials
- **overlay_forensic**: 0% win rate, avg delta -0.5, 3 trials

## Recommendations
- [PREFER] denoise has 100% win rate over 10 trials (avg delta: 0.7)
- [PREFER] detail has 100% win rate over 3 trials (avg delta: 20.2)
- [PREFER] exposure has 100% win rate over 3 trials (avg delta: 1.9)
- [AVOID] overlay_forensic has only 0% win rate over 3 trials — not effective
- [PROVEN] Best fix for scene1_BirdEye is denoise (best delta: +0.5)
- [PROVEN] Best fix for scene2_DriverPOV is detail (best delta: +19.4)
- [PROVEN] Best fix for scene3_BirdEye is exposure (best delta: +3.3)
- [PROVEN] Best fix for scene1_DriverPOV is detail (best delta: +19.5)
- [PROVEN] Best fix for scene2_BirdEye is denoise (best delta: +3.1)
- [PROVEN] Best fix for scene3_DriverPOV is detail (best delta: +21.7)
- [PROVEN] Best fix for scene3_WideAngle is contrast (best delta: +0.6)

## Best Camera+Fix Combos
- scene1_BirdEye + denoise: avg +0.3 (100% win rate, 8 tries)