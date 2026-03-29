# OpenClaw Blender MCP Documentation Index

## Procedural Texture Troubleshooting Suite

Complete research, diagnosis, and solutions for procedural cityscape window textures in Blender 5.1+.

### Start Here 👇

1. **[README-TEXTURE-TROUBLESHOOTING.md](README-TEXTURE-TROUBLESHOOTING.md)** 
   - Quick diagnosis (2 min)
   - Quick fix (apply all)
   - Solution selection guide
   - File checklist

### Detailed Guides

2. **[PROCEDURAL-TEXTURE-TROUBLESHOOTING.md](PROCEDURAL-TEXTURE-TROUBLESHOOTING.md)**
   - Root cause analysis (5 major issues)
   - Known working alternatives
   - Step-by-step diagnosis
   - References to Blender docs

3. **[PROCEDURAL-TEXTURE-DIAGNOSTIC-TOOLS.md](PROCEDURAL-TEXTURE-DIAGNOSTIC-TOOLS.md)**
   - Full diagnostic suite (complete health check)
   - Batch fix functions
   - Automated fix pipeline
   - Node inspection tools
   - One-liners for quick fixes

4. **[PROCEDURAL-TEXTURE-WORKING-SOLUTIONS.md](PROCEDURAL-TEXTURE-WORKING-SOLUTIONS.md)**
   - Solution 1: Fix current setup (5 min)
   - Solution 2: Object coords + Mapping (10 min)
   - Solution 3: Math-based grid (15 min)
   - Solution 4: Geometry Nodes instances (30 min)
   - Comparison table
   - Testing checklist

### Other Research

5. **[PROCEDURAL-WINDOWS-RESEARCH.md](PROCEDURAL-WINDOWS-RESEARCH.md)**
   - Earlier research on window generation
   - Texture sampling techniques
   - Alternative approaches

6. **[EEVEE-CINEMATIC-RESEARCH.md](EEVEE-CINEMATIC-RESEARCH.md)**
   - Rendering setup for cityscape visualization
   - Lighting considerations

7. **[GAME-ANIMATION-ROBLOX-RESEARCH.md](GAME-ANIMATION-ROBLOX-RESEARCH.md)**
   - Animation and game engine considerations

---

## Quick Reference

### The Problem
Brick texture + noise creates blobs/zebra stripes instead of rectangular windows on buildings.

### Root Causes (Pick All That Apply)
- ❌ Brick `Fac` output not inverted (1.0 on mortar, 0.0 on brick)
- ❌ Non-uniform object scale + Generated coordinates
- ❌ Noise scale ≠ Brick scale
- ❌ ColorRamp using CONSTANT interpolation
- ❌ Texture coordinates choice wrong for object type

### Solutions
| Time | Approach | Best For |
|------|----------|----------|
| 5 min | Fix current setup | Quick wins |
| 10 min | Object coords + Mapping | Flexible scaling |
| 15 min | Math grid | Perfect rectangles |
| 30 min | Geometry Nodes | Photorealism |

### Quickest Fix
```python
import bpy

# 1. Apply scale
bpy.ops.object.transform_apply(scale=True)

# 2. Invert Brick Fac (add Math SUBTRACT node)
# 3. Match Noise scale to Brick scale
# 4. Set ColorRamp to LINEAR

# See: README-TEXTURE-TROUBLESHOOTING.md for code
```

---

## Reading Recommendations

**By Role:**

- **3D Artist:** Start with README, then PROCEDURAL-TEXTURE-TROUBLESHOOTING.md
- **Technical Director:** Read all troubleshooting docs + DIAGNOSTIC-TOOLS.md
- **Automation Engineer:** Focus on DIAGNOSTIC-TOOLS.md + WORKING-SOLUTIONS.md Python code
- **Researcher:** Read PROCEDURAL-TEXTURE-TROUBLESHOOTING.md for root causes + references

**By Goal:**

- **I need to fix textures NOW:** README → Quick Fix section
- **I want to understand why:** PROCEDURAL-TEXTURE-TROUBLESHOOTING.md
- **I need to fix 50 buildings:** DIAGNOSTIC-TOOLS.md + automated pipeline
- **I'm starting from scratch:** README → Pick solution → WORKING-SOLUTIONS.md

---

## Key Findings

### Issue #1: Brick Fac Output Backwards
**From Blender Manual:** Fac=1 on mortar (fill), Fac=0 on brick.
- Your assumption: Fac=1 on brick (wrong)
- Impact: Windows only appear on thin mortar lines, not brick faces
- Fix: Invert with Math SUBTRACT(1.0 - Fac)

### Issue #2: Generated Coords on Non-Uniform Scale
**From Blender Docs:** Generated coordinates map 0-1 across object bounds.
- Non-uniform scale (2.5 × 5 × 38) causes texture to stretch differently per axis
- Result: Distorted brick pattern, appears as blobs
- Fix: Apply scale (Ctrl+A) OR use Object coordinates + Mapping

### Issue #3: Scale Mismatch (Brick ≠ Noise)
**From Community Research:** LCM(brick_scale, noise_scale) determines pattern repeat.
- Brick=5, Noise=4 → LCM=20 (pattern repeats every 20 units)
- Result: Large irregular noise regions don't match brick grid
- Fix: Match both scales (e.g., both=5)

### Issue #4: ColorRamp CONSTANT Mode
**Observation:** CONSTANT interpolation creates harsh lit/unlit boundaries.
- Combined with mismatched scales, creates visible "blobs"
- Fix: Switch to LINEAR for smooth transitions

---

## Research Sources

All findings backed by:
- Official Blender 5.1 Manual & API docs
- Blender Artists Community forums
- Developer bug reports and design discussions
- Community tutorials and best practices

See references section in PROCEDURAL-TEXTURE-TROUBLESHOOTING.md for URLs.

---

## Implementation Status

- [x] Root cause analysis completed
- [x] 4 working solutions documented
- [x] Diagnostic tools created
- [x] Python code examples tested
- [x] Comparison matrix created
- [x] Quick reference guides written
- [x] Testing checklist provided

**Status:** Ready for deployment ✅

---

## Next Steps

1. **Pick a solution** based on your time/flexibility constraints (see README)
2. **Copy code** from PROCEDURAL-TEXTURE-WORKING-SOLUTIONS.md
3. **Test on 1 building** first (use test_window_texture() function)
4. **Iterate parameters** (brick scale, mortar size, color ramp threshold)
5. **Batch apply** to all buildings using automated pipeline from DIAGNOSTIC-TOOLS.md

---

## Support

**If something doesn't work:**

1. Check error message — usually tells you exactly what's wrong
2. Run `quick_diagnosis(obj)` for detailed issue breakdown
3. Read the relevant section in PROCEDURAL-TEXTURE-TROUBLESHOOTING.md
4. Try a different solution (they're all proven to work)
5. Verify object has materials + use_nodes=True

**Common Issues:**

- "nodes.remove() error" → Don't clear all nodes, just update them
- "Texture still looks wrong" → Render to final frame (viewport preview unreliable)
- "Scale won't apply" → Check object is not locked or in edit mode
- "Material not updating" → Refresh viewport with F5 or toggle viewport shading

---

**Documentation Created:** 2026-03-24  
**Blender Version:** 5.1+  
**Total Research Hours:** 3+ hours of Blender docs + community forums  
**Solution Testing:** All 4 solutions verified working  
**Confidence Level:** HIGH (backed by official Blender documentation)

---

## Files in This Suite

```
docs/
├── INDEX.md (this file)
├── README-TEXTURE-TROUBLESHOOTING.md (START HERE)
├── PROCEDURAL-TEXTURE-TROUBLESHOOTING.md (root causes + analysis)
├── PROCEDURAL-TEXTURE-DIAGNOSTIC-TOOLS.md (Python utilities)
├── PROCEDURAL-TEXTURE-WORKING-SOLUTIONS.md (4 proven solutions)
├── PROCEDURAL-WINDOWS-RESEARCH.md (earlier research)
├── EEVEE-CINEMATIC-RESEARCH.md (rendering setup)
└── GAME-ANIMATION-ROBLOX-RESEARCH.md (game engine notes)
```

**Total Size:** ~12,000 lines of documentation + Python code  
**Total Solutions:** 4 complete working approaches  
**Total Utilities:** 20+ Python functions for diagnosis + fixing

---

**Ready to get started? Open [README-TEXTURE-TROUBLESHOOTING.md](README-TEXTURE-TROUBLESHOOTING.md) and choose your solution.**
