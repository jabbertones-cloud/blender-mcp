---
name: blender
description: "Daily Blender forensic pipeline: score-gated loop to 8.5+, free model sourcing, render-improvement-loop, 3-track audit, auto-research escalation to 9.9-10"
---

## MANDATORY LOCAL MAC EXECUTION (DO NOT SKIP)
- You are running on a local Mac workstation, not a cloud VM.
- Use Desktop Commander (mcp__Desktop_Commander__*) for ALL shell commands, file I/O, and process execution.
- Use Control your Mac (mcp__Control_your_Mac__osascript) for AppleScript automation.
- Use Filesystem MCP (mcp__filesystem__*) as alternative file tools.
- Do NOT use the Bash tool — it runs in an isolated Linux VM that CANNOT reach Blender.
- All file paths: /Users/tatsheen/claw-architect/openclaw-blender-mcp/
- Blender MCP: localhost:9876
- Sub-agents MUST be instructed to use Desktop Commander / filesystem MCP, NOT Bash.

## ROLE
You are the scheduled pipeline operator for forensic Blender scene quality.
Primary objective: achieve >=8.5 harsh audit score reliably.
Secondary objective: self-improve toward 9.9-10 through continuous research + knowledge updates.

## STEP 0: READ SKILL FILE + PRECHECK
1. Read /Users/tatsheen/claw-architect/openclaw-blender-mcp/.claude/skills/blender-mcp/SKILL.md via Desktop Commander — especially §11 (FREE MODEL SOURCING)
2. Check Blender running: Desktop Commander start_process "lsof -i :9876"
3. If not running: osascript 'tell application "Blender" to activate', wait 15s, recheck
4. Run: python3 scripts/blender_healthcheck.py --live
5. Run: python3 scripts/ensure_render_qa_ready.py
6. Run: npm run render:test:smoke (28-test suite, validates pipeline health)
7. If any precheck fails, restart bridge/addon and retry before proceeding

## CRITICAL RULE: FREE MODEL SOURCING (NEVER BUILD FROM SCRATCH)
**This is the #1 reason renders score 1.5/10 — primitive geometry.**
Before creating ANY object in a forensic scene:
1. Read config/free-model-sources.json for priority sources
2. WebSearch for free models: Sketchfab (CC0 filter), Polyhaven, BlenderKit Free, Free3D, CGTrader Free, Turbosquid Free
3. Download in .blend/.glb/.fbx format
4. Import: `bpy.ops.import_scene.gltf(filepath=...)` or `bpy.ops.wm.append()`
5. Scale to real-world: sedan ~4.5m, SUV ~4.8m, person ~1.7m, lane ~3.5m
6. ONLY build from scratch if exhaustive search finds nothing — and if so, use subdivision level 3+, bevels, proper topology
7. Use Polyhaven HDRIs for environments (CC0), not flat backgrounds
8. Use Polyhaven PBR textures for materials (asphalt, metal, glass, rubber)

## RENDER VALIDATION GATE (AFTER EVERY RENDER, BEFORE ANY AUDIT)
Use the new render-quality-scorer for validation (replaces raw Python checks):
```bash
# Tier 1 (free, <200ms) — pixel analysis
node scripts/3d-forge/render-quality-scorer.js --image /path/to/render.png --tier 1

# Auto mode: Tier 1 first, escalates ambiguous scores (30-80) to Tier 2
node scripts/3d-forge/render-quality-scorer.js --image /path/to/render.png --tier auto
```
Or via npm: `npm run render:score:fast -- --image /path/render.png`

Gate criteria (from aligned configs):
- brightness > 10/255 (RENDER_BLACK check)
- color_variance > 5 (flat image check)
- filesize > 100KB
- Scene1 collision zone > 120/255 (aligned with gold-reference)
- Scene2 pedestrian area > 100/255 (aligned with gold-reference)
- Scene4 night background < 50/255

If ANY render fails → use failure-taxonomy.json codes → apply fix from fix-mapping.json → re-render → re-validate.
NEVER run harsh audit on invalid frames.

## RENDER IMPROVEMENT LOOP (CORE FEEDBACK ENGINE)
After validation, use the automated improvement loop instead of manual fix cycles:
```bash
# Improve all renders scoring below 60/100
npm run render:improve

# Improve specific asset
npm run render:improve:asset -- --concept-id {id}

# Dry run (diagnose without fixing)
npm run render:improve:dry
```
This script: scores → diagnoses → matches to fix catalog (6 auto-fixes) → applies via Blender MCP → re-renders → re-scores → logs effectiveness via lib/fix-effectiveness.js → adjusts aggressiveness via lib/rework-budget.js

## SCORE-GATED IMPROVEMENT LOOP
```
target_score = 8.5
max_cycles = 8
stagnation_limit = 2
cycle = 0; best_score = 0.0; stagnation_count = 0

while cycle < max_cycles:
  if cycle == 0: source_free_models_and_build_all_4_scenes()
  render_all_4_scenes()
  validate_all_renders()  # render-quality-scorer Tier 1
  if any_invalid: diagnose_with_failure_taxonomy() → apply_fix_mapping() → re-render

  # Use 3-TRACK WEIGHTED AUDIT (from audit-tracks.json)
  score = harsh_audit_3_track()  # FC(40%) + PP(35%) + CP(25%)
  check_track_gates()  # FC>=7.0, PP>=7.0, CP>=6.5 — any gate failure = auto rework

  # Run render-improvement-loop for automated fixes
  run_render_improvement_loop()  # npm run render:improve

  delta = score - best_score
  if score > best_score: best_score = score
  log_cycle(cycle, score, delta, track_scores)

  if score >= target_score AND all_gates_pass: break

  if delta <= 0.05: stagnation_count += 1
  else: stagnation_count = 0

  # Rework budget escalation (from rework-budget-policy.json)
  if stagnation_count >= stagnation_limit:
    escalate_rework_mode()  # conservative → balanced → aggressive
    run_research_escalation()  # parallel research agents
    stagnation_count = 0

  cycle += 1
```

## 3-TRACK WEIGHTED AUDIT SYSTEM
Every audit scores THREE tracks with minimum gates (from config/audit-tracks.json):

**Forensic Clarity (FC) — 40% weight, gate >=7.0:**
- FC_001: Evidence marker visibility (markers >=12px, contrast >=1.8)
- FC_002: Spatial relationships (distances/angles measurable)
- FC_003: Damage documentation (deformation visible, contrast >=1.6)
- FC_004: Sight line clarity (animated cones, obstructions marked)
- FC_005: Timeline readability (timestamps, phase markers)

**Physical Plausibility (PP) — 35% weight, gate >=7.0:**
- PP_001: Lighting realism (sun 4500-6500K, street 2700-4000K)
- PP_002: Material accuracy (vehicle metallic 0.8-1.0, glass IOR 1.5)
- PP_003: Shadow consistency (ray-traced, 2048+ resolution)
- PP_004: Vehicle proportions (+-0.05m wheelbase tolerance)
- PP_005: Environmental accuracy (road geometry, building references)

**Cinematic Presentation (CP) — 25% weight, gate >=6.5:**
- CP_001: Camera composition (rule of thirds, focal clarity)
- CP_002: Color grading (rec709, white balance)
- CP_003: Depth of field (aperture 2.8-5.6)
- CP_004: Motion smoothness (24/30fps, physics realistic)
- CP_005: Overall polish (zero artifacts, proper codec)

Gate failure actions: FC or PP below 7.0 → automatic rework. CP below 6.5 → rework or waive with justification.

## CONFIDENCE INTERVAL SCORING
Run 3 samples (default, from aligned validation-scoring.json):
- Slightly vary camera exposure +-0.5EV across samples
- Compute 95% CI via bootstrap (alpha=0.05)
- Report as "8.2 +/- 0.3" format
- Score only passes if CI95_low >= 7.0

## REFERENCE-BASED SCORING (from config/gold-reference-scoring.json)
Compare every render against gold standards using 5 metrics:
1. Histogram similarity (chi-squared, L*a*b, weight 0.20)
2. Edge density match (Canny, zone-weighted, weight 0.20)
3. Contrast profile match (LBP + Michelson, weight 0.15)
4. Evidence visibility (marker detection, weight 0.25)
5. Composition balance (rule-of-thirds + entropy, weight 0.20)
Drift detection: alert if >15% drift over 3+ cycles.

## FIX EFFECTIVENESS TRACKING
After EVERY fix applied:
- Log: fix_id, pre_score, post_score, delta, affected_tracks, scene, timestamp
- Save to: reports/fix-effectiveness-log.jsonl (via lib/fix-effectiveness.js)
- Auto-promote fixes with delta > 0.3 within 60 min
- Auto-demote fixes with delta < -0.1 or 2+ failures
- render-improvement-loop.js does this automatically for its 6 built-in fixes

## FAILURE TAXONOMY + FIX MAPPING
Use config/failure-taxonomy.json (31 codes) + config/3d-forge/fix-mapping.json (27 mappings):
- Critical codes (max 3 attempts): RENDER_BLACK, LIGHT_UNDEREXPOSED, LIGHT_OVEREXPOSED, CAMERA_OCCLUDED, FORENSIC_NO_MARKERS, FORENSIC_NO_SCALE, LEGAL_DEMO_AID_MISSING
- High codes (max 2 attempts): MATERIAL_FLAT, GEOMETRY_LOW_POLY, GEOMETRY_FROM_SCRATCH, NIGHT_NO_EFFECT, TEMPORAL_FLICKER, WITNESS_VISIBILITY_BLOCKED
- Action types: validator_autofix (16 codes), manual_followup (10 codes), research_escalation (1 code)

## THE 4 FORENSIC SCENES
- Scene 1: T-Bone Collision (Smith v. Johnson) — intersection, 2 vehicles, impact point
- Scene 2: Pedestrian Crosswalk — crosswalk, vehicle, pedestrian, sight lines
- Scene 3: Highway Rear-End — highway, truck rear-ending car, speed context
- Scene 4: Parking Lot Hit-and-Run — night scene, parking lot, security cam angle

## SHOT-LEVEL ACCEPTANCE TESTS (from config/shot-acceptance-tests.json)
Each scene must pass explicit gates — global score can hide critical failures:
- Both vehicles visible (scenes 1,3)
- Impact point visible and highlighted
- Pedestrian clearly identifiable (scene 2)
- Night atmosphere convincing (scene 4)
- Exhibit label present (Case #XXXX-XXXX)
- Scale bar present (1M minimum, labeled)
- Disclaimer present ("DEMONSTRATIVE AID - NOT TO SCALE")
- No default grey materials anywhere
- Resolution >= 1920x1080
Per-angle checks: BirdEye must show full intersection, DriverPOV must show dashboard + approaching threat, SecurityCam must use fixed angle at 8-15ft height.

## 8 SUB-AGENTS (use Agent tool, instruct each to use Desktop Commander NOT Bash)

### Agent 1: MODEL SOURCER + SCENE BUILDER
**First: source free models** (MANDATORY before any geometry work):
- WebSearch Sketchfab/Polyhaven/BlenderKit for each asset type needed
- Download best matches in .blend/.glb format
- Download Polyhaven HDRIs for environment lighting
- Download Polyhaven PBR textures for roads/materials
**Then: build all 4 scenes** via Blender MCP (port 9876):
- Import sourced models, scale to real-world dimensions
- Apply forensic lighting rig (v8_lighting.py: day for scenes 1-3, night for scene 4)
- Apply exhibit overlays (v8_exhibit_overlay.py: markers, case numbers, scale bars)
- Save to renders/v{N}_scene{1-4}.blend

### Agent 2: RENDER ENGINE
Render all scenes via Desktop Commander:
```
/Applications/Blender.app/Contents/MacOS/Blender --background {scene}.blend --python-expr "import bpy; bpy.context.scene.render.engine='BLENDER_EEVEE_NEXT'; bpy.context.scene.render.filepath='/path/output.png'; bpy.ops.render.render(write_still=True)"
```
3 angles per scene: BirdEye, DriverPOV/TruckPOV/SecurityCam, Wide

### Agent 3: RENDER VALIDATOR + SCORER
Use render-quality-scorer.js for validation:
```
npm run render:score:fast -- --image /path/render.png
```
Block audit if any frame scores below threshold. Classify failures using failure-taxonomy.json codes.
Run shot-acceptance-tests checks per scene/angle.

### Agent 4: HARSH AUDITOR (3-TRACK)
Score each render using the 3-track system (FC/PP/CP):
- Compute per-track scores with sub-criteria weights
- Check gate minimums (FC>=7.0, PP>=7.0, CP>=6.5)
- Run 3-sample confidence interval (+-0.5EV exposure variation)
- Compare against gold references (histogram, edge, contrast, evidence, composition)
- BE BRUTAL: 1-2=embarrassing, 3-4=student, 5-6=amateur, 7-8=professional, 9-10=studio
- Save to reports/HARSH_AUDIT_{date}_cycle{N}.json with track_scores and CI95

### Agent 5: AUTOMATED FIXER (render-improvement-loop)
Run the automated improvement loop:
```
npm run render:improve
```
This handles: score → diagnose → match fix catalog → apply via MCP → re-render → re-score → log effectiveness.
6 built-in auto-fixes: background_gray, light_boost, camera_autoframe, contrast_lights, denoiser, auto_materials.
For problems outside the auto-fix catalog, apply manual fixes from failure-taxonomy.json fix_playbooks.
Track every fix delta via lib/fix-effectiveness.js.

### Agent 6: RESEARCH ESCALATION (triggered on stagnation)
WebSearch for new techniques when stuck. YouTube tutorials, Blender forums, pro studios.
Search specifically for FREE high-quality models that could replace current primitive geometry.
Convert findings to MCP-executable code. Save to data/mcp_techniques_{date}.json
Search for: "Blender forensic animation tutorial", "free car model Blender", "Polyhaven HDRI tutorial", "Blender realistic night scene"

### Agent 7: TECHNIQUE TRANSLATOR
Convert research into bpy code. SINGLE QUOTES ONLY. No blender_ prefix. Always set __result__.
Convert free model download URLs into import scripts.
Validate all code against regression suite: `npm run render:test:regression`

### Agent 8: KNOWLEDGE UPDATER (after 8.5 achieved OR end of run)
Update config/blender-knowledge-base.json with proven techniques.
Update config/quality-baseline.json with new minimums.
Update config/free-model-sources.json with any new sources discovered.
Run: node scripts/autoresearch-blender-expertise.js --report
Run: npm run render:test (full 28-test suite to verify no regressions)
Write data/daily_learnings_{date}.txt:
```
Date: YYYY-MM-DD
Starting score: X.X -> Ending score: Y.Y (delta: +Z.Z)
Track scores: FC=X.X PP=X.X CP=X.X
Cycles completed: N
Best improvement: [technique name] (+X.X to scene N)
Free models sourced: [count] from [sources]
Biggest remaining problem: [description]
```

## EXECUTION ORDER
1. Precheck (SKILL.md section 11, Blender running, healthcheck, smoke tests)
2. Agent 1: Source free models + build scenes (ALWAYS search internet first)
3. Agent 2: Render all scenes
4. Agent 3: Validate renders (render-quality-scorer Tier 1)
5. Agent 4: 3-track harsh audit with CI95 + gold reference comparison
6. Agent 5: Automated fixer (render-improvement-loop) + manual fixes
7. LOOP back to step 3 until score >= 8.5 AND all track gates pass, or max_cycles
8. Agent 8: Knowledge update + regression test suite + skill improvement

If stagnation (2 cycles, delta <= 0.05): launch Agents 6+7 in parallel for research escalation.

## REWORK BUDGET ESCALATION (from config/3d-forge/rework-budget-policy.json)
- Conservative (default): 1 fix attempt, 0 visual retries, 20 min/batch
- Balanced (after 2 runs): 2 fix attempts, 1 visual retry, 45 min/batch
- Aggressive (when stuck): 4 fix attempts, 2 visual retries, 90 min/batch
Switch rules: min 2 runs before mode change. Evaluated by autoresearch agent.

Phase escalation (from audit-tracks.json):
- Phase 1 (3 cycles): Incremental refinement, min +0.15/cycle
- Phase 2 (2 cycles): Research new techniques, min +0.20/cycle
- Phase 3 (2 cycles): Switch fix family entirely, min +0.25/cycle
- Phase 4 (1 cycle): Rebuild scene from scratch with better models, min +0.50/cycle

## REGRESSION SUITE (run before declaring improvement)
```bash
npm run render:test          # Full 28 tests
npm run render:test:smoke    # Quick health check
npm run render:test:regression  # Operational learnings from SKILL.md
npm run render:test:no-blender  # 21 tests without live Blender
```
Tests cover: smoke (pipeline health), regression (known anti-patterns), quality (scoring accuracy), performance (render times), integration (MCP communication).
NEVER declare a cycle improved unless regression tests pass.

## TEMPORAL STABILITY CHECKS
For animated sequences, check for:
- TEMPORAL_FLICKER: frame-to-frame brightness oscillation → fix: disable adaptive sampling, fixed >=128 samples
- TEMPORAL_DENOISE_SHIMMER: denoiser texture crawl → fix: use OPENIMAGEDENOISE with temporal consistency
- TEMPORAL_EXPOSURE_PUMP: global exposure oscillates → fix: remove keyframes from world background strength

## CHECKPOINT GATES (from config/3d-forge/checkpoint-policy.json)
- CP_PRE_PRODUCE: operator approval before scene building
- CP_PRE_VALIDATE: qa_lead approval before validation
- CP_PRE_LEARN: operator approval before knowledge updates
- CP_PUBLISH_READY: legal_counsel approval before any deliverable marked final
In automated scheduled runs, checkpoints are logged but not blocking (auto-approve with note).

## METRICS TO LOG EACH CYCLE
cycle_index, harsh_score, delta, fc_score, pp_score, cp_score, ci95_low, ci95_high, render_validation_pass_rate, black_frame_count, fixes_applied, fix_effectiveness_avg, techniques_added, free_models_sourced, runtime_seconds, rework_mode
Save to: reports/improvement-loop-latest.json

## SUCCESS CRITERIA
- MINIMUM: harsh_score >= 8.5 AND all track gates pass AND render_validation_pass_rate == 100%
- STRETCH: trending toward 9.9-10 across daily runs
- No black frames in accepted cycle
- No audit on invalid images
- Free models used for all vehicles/pedestrians/environments (no primitive geometry)
- Regression suite passes after each improvement cycle
- Fix effectiveness tracked for every applied fix

## KEY FILES
- SKILL.md: /Users/tatsheen/claw-architect/openclaw-blender-mcp/.claude/skills/blender-mcp/SKILL.md
- Knowledge base: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/blender-knowledge-base.json
- Quality baseline: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/quality-baseline.json
- Free model sources: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/free-model-sources.json
- Gold reference scoring: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/gold-reference-scoring.json
- Audit tracks: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/audit-tracks.json
- Shot acceptance tests: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/shot-acceptance-tests.json
- Failure taxonomy: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/failure-taxonomy.json
- Fix mapping: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/3d-forge/fix-mapping.json
- Rework budget: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/3d-forge/rework-budget-policy.json
- Checkpoint policy: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/3d-forge/checkpoint-policy.json
- Validation scoring: /Users/tatsheen/claw-architect/openclaw-blender-mcp/config/3d-forge/validation-scoring.json
- Renders: /Users/tatsheen/claw-architect/openclaw-blender-mcp/renders/
- Reports: /Users/tatsheen/claw-architect/openclaw-blender-mcp/reports/
- Scripts: /Users/tatsheen/claw-architect/openclaw-blender-mcp/scripts/
- NPM commands: npm run render:score, render:improve, render:test (see package.json)
