# OpenClaw Blender MCP Skill Bank — Phase 4

**Index of Self-Evolving Recipes (v0.1.x)**

This document provides an overview of the skill bank structure, recipe organization, and CLI usage.

## Directory Structure

```
.claude/skills/blender-mcp/
├── recipes/
│   ├── MANIFEST.json                                    # Recipe registry (5 recipes, 425 total lines)
│   ├── product-viz-3point-v0.1.0.md                    # 3-point lighting (75 lines)
│   ├── forensic-accident-reconstruction-v0.1.0.md      # Accident scene (80 lines)
│   ├── procedural-wood-floor-v0.1.0.md                 # Wood floor generation (85 lines)
│   ├── cyberpunk-desk-scene-v0.1.0.md                  # Neon desk workspace (90 lines)
│   ├── character-rigging-starter-v0.1.0.md             # Humanoid rigging (95 lines)
│   └── .history/                                        # Version history and evaluation logs
├── skill_evo.py                                         # CLI runner (REMP loop orchestrator)
└── INDEX.md                                             # This file
```

## Recipe Tiers & Categories

### Lighting (1 recipe, 75 lines)
- **product-viz-3point** — Professional 3-point lighting rig (key 2000W, fill 800W, back 1200W)
  - Trigger patterns: `product photography`, `lighting setup`, `3-point light`
  - Tools: Blender.Scene, Blender.Light, Blender.RenderEngine
  - Runtime: ~45 seconds
  - Status: DEVELOPMENT (v0.1.0)

### Forensics (1 recipe, 80 lines)
- **forensic-accident-reconstruction** — Multi-vehicle accident scene with witness cameras
  - Trigger patterns: `accident reconstruction`, `forensic scene`, `vehicle positioning`
  - Tools: Blender.Scene, Blender.Mesh, Blender.Camera, Blender.Material
  - Runtime: ~60 seconds
  - Dependencies: GCS v1.0+ (Geometric Constraint Solver)
  - Status: DEVELOPMENT (v0.1.0)

### Materials (1 recipe, 85 lines)
- **procedural-wood-floor** — Geometry Nodes hardwood floor with wear variation
  - Trigger patterns: `wood floor`, `procedural floor`, `geometry nodes`
  - Tools: Blender.GeometryNodes, Blender.Material, Blender.Modifier
  - Runtime: ~50 seconds
  - Status: DEVELOPMENT (v0.1.0)

### Scene Composition (1 recipe, 90 lines)
- **cyberpunk-desk-scene** — Neon-lit workspace with volumetric fog and HDRI
  - Trigger patterns: `cyberpunk scene`, `neon lighting`, `volumetric effects`
  - Tools: Blender.Scene, Blender.Material, Blender.World, Blender.RenderEngine
  - Runtime: ~70 seconds
  - Status: DEVELOPMENT (v0.1.0)
  - Tier: STRATEGIC (complex multi-system orchestration)

### Rigging (1 recipe, 95 lines)
- **character-rigging-starter** — Humanoid armature with IK chains and auto-weights
  - Trigger patterns: `character rigging`, `humanoid armature`, `inverse kinematics`
  - Tools: Blender.Armature, Blender.Modifier, Blender.Constraint
  - Runtime: ~65 seconds
  - Status: DEVELOPMENT (v0.1.0)

## Skill Bank Statistics

| Metric | Value |
|--------|-------|
| Total Recipes | 5 |
| Total Lines | 425 |
| Total Verification Constraints | 31 |
| Total Python Snippets | 30 |
| Average Runtime | 58 seconds |
| Promoted Recipes | 0 (all v0.1.0) |
| Total Usage | 0 |

## CLI Usage

### Commands

#### `skill_evo.py replay <recipe_id> [--version VERSION]`
Load and re-execute recipe steps without constraint validation.
```bash
python skill_evo.py replay product-viz-3point
python skill_evo.py replay forensic-accident-reconstruction --version 0.1.0
```

#### `skill_evo.py evaluate <recipe_id> [--version VERSION]`
Run recipe against all GCS constraints and collect metrics.
```bash
python skill_evo.py evaluate procedural-wood-floor
python skill_evo.py evaluate character-rigging-starter --version 0.1.0
```

#### `skill_evo.py mutate <recipe_id> --delta JSON [--version VERSION]`
Create new version (v0.1.1, v0.1.2...) with parameter variations.
```bash
python skill_evo.py mutate product-viz-3point --delta '{"key_energy": 2500, "back_energy": 1500}'
python skill_evo.py mutate procedural-wood-floor --delta '{"plank_width": 0.2, "roughness": 0.4}'
```

#### `skill_evo.py promote <recipe_id> [--version VERSION]`
Mark recipe as production-ready (promoted=true in MANIFEST.json).
```bash
python skill_evo.py promote product-viz-3point
python skill_evo.py promote forensic-accident-reconstruction --version 0.1.0
```

#### `skill_evo.py extract <recipe_id> [--output DIR] [--version VERSION]`
Export recipe to standalone shareable markdown file.
```bash
python skill_evo.py extract cyberpunk-desk-scene --output ~/exports/
python skill_evo.py extract character-rigging-starter --version 0.1.0 --output .
```

#### `skill_evo.py status [recipe_id]`
Show recipe version history and usage statistics.
```bash
python skill_evo.py status                              # All recipes
python skill_evo.py status product-viz-3point           # Specific recipe
```

## Recipe Format

Each recipe is a Markdown file with:

### 1. YAML Frontmatter
```yaml
---
id: product-viz-3point
version: 0.1.0
title: 3-Point Product Lighting Setup
category: lighting
trigger_patterns: [product photography, lighting setup, 3-point light]
tools_used: [Blender.Scene, Blender.Light, Blender.RenderEngine]
dependencies: [blender>=3.0]
---
```

### 2. Description Section
Natural language explanation of the recipe's purpose and use case.

### 3. Numbered Steps
Sequential instructions with execute_python code blocks using single quotes.

### 4. Verification JSON
GCS-compatible constraint definitions:
```json
{
  "light_count": 3,
  "light_type_distribution": {
    "key": "AREA",
    "fill": "AREA",
    "back": "AREA"
  },
  "light_energy_ratio": {
    "min": 1.8,
    "max": 3.0
  },
  "spatial_separation": ">=4.5m",
  "render_settings": {
    "engine": "CYCLES",
    "samples": 128,
    "denoiser": "OPTIX"
  }
}
```

### 5. Known Failure Modes
Troubleshooting guide for common execution errors.

## REMP Loop Workflow

```
┌─────────────────────────────────────────────────────────┐
│ Replay (load & execute steps)                           │
│ ↓                                                       │
│ Evaluate (validate GCS constraints, compute metrics)    │
│ ↓                                                       │
│ Mutate (generate parameter variations → new version)    │
│ ↓                                                       │
│ Promote (mark as production-ready)                      │
│ ↓                                                       │
│ Extract (export for sharing/reuse)                      │
└─────────────────────────────────────────────────────────┘
```

## Versioning Scheme

Recipes follow semantic versioning: `v{major}.{minor}.{patch}`

- **v0.1.0** — Initial development seed recipes (5 recipes, current)
- **v0.1.1+** — Mutation variants with parameter changes
- **v0.2.0+** — Minor revisions and constraint refinements
- **v1.0.0+** — Promoted to production-ready status

## GCS Constraint Verification

All recipes include verification JSON compatible with the Geometric Constraint Solver:

- **Spatial Constraints**: object positions, distances, separations
- **Attribute Constraints**: material properties, render settings, bone counts
- **Relational Constraints**: parent-child hierarchies, modifier stacks
- **Numeric Constraints**: ranges, ratios, tolerance bands

## Next Steps (Phase 5-6)

- Create `eval/run.py` — main evaluation runner
- Create `eval/lego_eval/adapter.py` — LEGO-Eval benchmark (130 instructions)
- Create `eval/blender_gym/adapter.py` — BlenderGym integration (245 scenes)
- Create `.github/workflows/eval.yml` — GitHub Actions CI/CD
- Create `eval/README.md` — evaluation framework documentation

## File Statistics

| File | Lines | Type |
|------|-------|------|
| MANIFEST.json | ~140 | JSON registry |
| skill_evo.py | ~280 | Python CLI |
| INDEX.md | ~200 | Documentation |
| 5 × Recipe Files | 425 total | Markdown + JSON |
| **Total Phase 4** | **~1,045** | **All new files** |

---

*Last updated: 2026-04-23*  
*OpenClaw Blender MCP — Phase 4: Self-Evolving Skill Bank*
