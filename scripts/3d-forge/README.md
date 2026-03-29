# 3D Forge Production Pipeline Scripts

## Overview

Two core scripts manage the 3D asset production pipeline:

### 1. **forge-orchestrator.js** — Main Pipeline Runner

Chains all production stages sequentially:
```
SCAN → HARVEST → GENERATE → PRODUCE → VALIDATE → LEARN
```

#### Usage

```bash
# Full pipeline (default)
node forge-orchestrator.js

# Full pipeline with limit
node forge-orchestrator.js --limit 10

# Run specific stages
node forge-orchestrator.js --scan-only
node forge-orchestrator.js --produce-only
node forge-orchestrator.js --validate-only

# Test without execution
node forge-orchestrator.js --dry-run --verbose

# Combined
node forge-orchestrator.js --full --limit 5 --verbose
```

#### Output

- **State**: `reports/3d-forge-pipeline-state.json`
  - Tracks trends_scanned, images_harvested, concepts_generated, assets_produced, assets_validated, assets_passed/rejected
  - Records stage timings and errors

### 2. **autoresearch-agent.js** — Learning & Quality Agent

Monitors production KPIs and drives continuous improvement.

#### Usage

```bash
# Full analysis
node autoresearch-agent.js

# Dry run (analysis only, no state save)
node autoresearch-agent.js --dry-run

# Verbose output
node autoresearch-agent.js --verbose

# Combined
node autoresearch-agent.js --dry-run --verbose
```

#### 12 KPIs Tracked

1. **production_success_rate** — % of concepts producing valid assets (target ≥80%)
2. **validation_pass_rate** — % of assets passing all checks (target ≥70%)
3. **visual_quality_avg** — Average quality score (target ≥7.0)
4. **mechanical_pass_rate** — % passing mechanical checks (target ≥90%)
5. **revision_rate** — % needing revision (target ≤30%)
6. **reject_rate** — % rejected (target ≤15%)
7. **cost_per_asset_usd** — LLM cost per asset (target ≤$0.50)
8. **time_per_asset_seconds** — Production time (target ≤300s)
9. **steps_failed_rate** — % of blender steps failing (target ≤10%)
10. **trend_to_asset_hours** — Time from trend to validated asset (target ≤12h)
11. **ref_images_per_concept** — Avg reference images (target ≥10)
12. **concepts_per_trend** — Avg concepts per trend (target ≥3)

#### Learning Engine

Analyzes all production data and generates:

- **Prompt Pattern Analysis** → `config/3d-forge/prompt-patterns.json`
  - Reliable vs unreliable blender step sequences
  - Success rate per modifier/tool
  
- **Category Success Analysis** → `config/3d-forge/autoresearch-state.json`
  - Categories ranked by quality × demand
  
- **Image-to-Quality Correlation**
  - Do more reference images improve output?
  - Which image sources (Serper vs Unsplash) correlate with better quality?
  
- **Recurring Issues** → Top issues extracted from validation data
  - Auto-suggested fixes (e.g., "proportions off" → enhance dimension prompts)

#### Auto-Remediation

Detects and recommends fixes for:
- **Regressions** — If any KPI drops >10% (suggest rollback)
- **High Failure Rate** — If steps_failed_rate >25% (remove failing types)
- **Low Quality** — If visual_quality_avg <6.0 (increase reference images)
- **High Cost** — If cost >$1/asset (switch to cheaper model)

#### Output

- **State**: `config/3d-forge/autoresearch-state.json`
  - KPI history (last 30 runs)
  - Category rankings
  - Prompt pattern scores
  - Recurring issues
  - Applied remediations

- **Report**: `reports/3d-forge-autoresearch-latest.json`
  - Current KPI values
  - Detailed pattern analysis
  - Top category and issue insights
  - Auto-remediation recommendations

## Data Flow

```
exports/
  ├─ <asset-id>/
  │  ├─ metadata.json       ← Production metadata (cost, time, blender steps)
  │  └─ validation.json     ← Validation results (quality score, issues)
  └─ ...

data/3d-forge/
  ├─ concepts/*.json        ← Generated concepts (category, demand, ref images)
  └─ ...

config/3d-forge/
  ├─ autoresearch-state.json     ← Learning state (KPI history, patterns)
  └─ prompt-patterns.json        ← Pattern analysis results

reports/
  ├─ 3d-forge-pipeline-state.json       ← Pipeline execution state
  └─ 3d-forge-autoresearch-latest.json  ← Latest analysis report
```

## Integration with Mission Control

Both scripts are registered in `config/mission-control-agents.json`:

- **forge-orchestrator**: Runs full pipeline (0 2 * * * UTC) or triggered via dashboard
- **autoresearch-agent**: Runs after validation (0:30, 6:30, 12:30, 18:30 UTC)

## Performance Notes

- **Orchestrator**: ~15 min timeout per stage; supports `--limit N` for batch sizing
- **Autoresearch**: Analyzes all production data in-memory; typical run <30s
- **State**: Persists to JSON; no database required
- **Errors**: Logged to state.errors array; pipeline continues with remaining items

## Typical Schedule

```
0:00 UTC  → Orchestrator full pipeline (SCAN → HARVEST → GENERATE → PRODUCE → VALIDATE)
0:30 UTC  → Autoresearch learns from 0:00 batch
6:00 UTC  → Orchestrator (repeat)
6:30 UTC  → Autoresearch
12:00 UTC → Orchestrator
12:30 UTC → Autoresearch
18:00 UTC → Orchestrator
18:30 UTC → Autoresearch
```

Each autoresearch run triggers remediations and logs recommendations to guide next cycle.
