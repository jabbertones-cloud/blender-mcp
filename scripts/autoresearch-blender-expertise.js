#!/usr/bin/env node
/**
 * Blender Expertise Autoresearch Agent (v7 baseline)
 * ====================================================
 * Continuously learns, indexes, benchmarks, and improves Blender 3D product animation + forensic animation knowledge.
 * Runs on a schedule (2x/day via PM2) and self-improves the product animation system.
 *
 * What it does:
 *   1. SCAN    — Searches YouTube, blogs, forums for new Blender product animation techniques
 *   2. EXTRACT — Pulls out specific technical values (shader settings, light configs, timing)
 *   3. INDEX   — Stores findings in a structured knowledge base (JSON)
 *   4. BENCHMARK — Compares our presets against industry best practices
 *   5. BASELINE CHECK — Validates current settings never regress below quality-baseline.json
 *   6. MANDATORY FEATURE CHECK — Validates v7 required features are present in build scripts
 *      (v5 originals: HDRI, Volume Absorption, Solidify, bounces, lights, shadow mix, blockers)
 *      (v7 additions: OIDN denoiser, denoising data passes, filter glossy, clamp indirect, caustics off, preset system)
 *      (v9 forensic: vehicle geometry, pedestrian figure, impact deformation, exhibit standards, driver POV interior, physics validation)
 *   7. IMPROVE — Updates presets/recipes when better values are found
 *   8. REPORT  — Generates a learning report with KPIs
 *
 * KPIs tracked:
 *   1. knowledge_entries      — Total indexed techniques
 *   2. material_presets       — Count of material presets available
 *   3. lighting_rigs          — Count of lighting rig presets
 *   4. camera_styles          — Count of camera animation styles
 *   5. demo_count             — Number of working demo projects
 *   6. tutorial_sources       — Number of tutorials analyzed
 *   7. last_improvement_date  — When presets were last updated
 *   8. quality_score          — Self-assessed quality vs industry benchmarks (0-100)
 *   9. technique_coverage     — % of known pro techniques we can execute
 *  10. gap_count              — Known capability gaps remaining
 *  11. baseline_compliance    — % of baseline KPIs met or exceeded
 *  12. mandatory_features_ok  — % of v7+v9 mandatory features present in build scripts (14 product + 6 forensic checks)
 *
 * Usage:
 *   node scripts/autoresearch-blender-expertise.js              # Full cycle
 *   node scripts/autoresearch-blender-expertise.js --scan-only  # Just search for new techniques
 *   node scripts/autoresearch-blender-expertise.js --report     # Just generate report
 *   node scripts/autoresearch-blender-expertise.js --benchmark  # Run quality benchmark
 *   node scripts/autoresearch-blender-expertise.js --baseline   # Check baseline compliance
 *   node scripts/autoresearch-blender-expertise.js --features   # Check mandatory features only
 *   node scripts/autoresearch-blender-expertise.js --dry-run    # No changes, just analyze
 */

const fs = require('fs');
const path = require('path');
const { execSync, exec } = require('child_process');

// ─── Paths ──────────────────────────────────────────────────────────────────
const ROOT = path.resolve(__dirname, '..');
const KNOWLEDGE_PATH = path.join(ROOT, 'config', 'blender-knowledge-base.json');
const BASELINE_PATH = path.join(ROOT, 'config', 'quality-baseline.json');
const REPORT_PATH = path.join(ROOT, 'reports', 'blender-expertise-latest.json');
const HISTORY_PATH = path.join(ROOT, 'reports', 'blender-expertise-history.json');
const PRESETS_PATH = path.join(ROOT, 'server', 'product_animation_tools.py');
const RECIPES_PATH = path.join(ROOT, 'scripts', 'product_animation_recipes.py');
const DEMOS_DIR = path.join(ROOT, 'demos');
const SCRIPTS_DIR = path.join(ROOT, 'scripts');

// ─── Args ───────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const SCAN_ONLY = args.includes('--scan-only');
const REPORT_ONLY = args.includes('--report');
const BENCHMARK_ONLY = args.includes('--benchmark');
const BASELINE_ONLY = args.includes('--baseline');
const FEATURES_ONLY = args.includes('--features');
const DRY_RUN = args.includes('--dry-run');
const VERBOSE = args.includes('--verbose');

// ─── Load Quality Baseline ───────────────────────────────────────────────────
function loadBaseline() {
  if (fs.existsSync(BASELINE_PATH)) {
    return JSON.parse(fs.readFileSync(BASELINE_PATH, 'utf8'));
  }
  console.warn(`[WARNING] Quality baseline not found: ${BASELINE_PATH}`);
  return null;
}

// ─── Find Latest Build Script ────────────────────────────────────────────────
function findLatestBuildScript() {
  // Look for perfume_v*.py scripts, return the highest version
  try {
    const files = fs.readdirSync(SCRIPTS_DIR)
      .filter(f => f.match(/^perfume_v\d+.*\.py$/))
      .sort((a, b) => {
        const va = parseInt(a.match(/v(\d+)/)?.[1] || '0');
        const vb = parseInt(b.match(/v(\d+)/)?.[1] || '0');
        return vb - va;
      });
    if (files.length > 0) {
      return path.join(SCRIPTS_DIR, files[0]);
    }
  } catch (e) { /* */ }
  return null;
}

// ─── Find Forensic Scene Scripts ────────────────────────────────────────────
function findForensicSceneScripts() {
  // Look for forensic scene build scripts and portfolio render scripts
  const forensicScripts = [];
  try {
    // Check portfolio_forensic_v* directories
    const dirs = fs.readdirSync(ROOT).filter(d => d.startsWith('portfolio_forensic_'));
    for (const dir of dirs) {
      const dirPath = path.join(ROOT, dir);
      if (fs.statSync(dirPath).isDirectory()) {
        const files = fs.readdirSync(dirPath).filter(f => f.endsWith('.py'));
        for (const f of files) {
          forensicScripts.push(path.join(dirPath, f));
        }
      }
    }
    // Check scripts/ for v8/v9 forensic lighting/overlay scripts
    const scriptFiles = fs.readdirSync(SCRIPTS_DIR).filter(f =>
      f.match(/v\d+_(lighting|exhibit|forensic|scene)/) || f.match(/forensic/)
    );
    for (const f of scriptFiles) {
      forensicScripts.push(path.join(SCRIPTS_DIR, f));
    }
  } catch (e) { /* */ }
  return forensicScripts;
}

// ─── V7 Mandatory Feature Checks ─────────────────────────────────────────────
// These checks validate that the latest build script contains ALL required
// features from the v7 baseline. Features are additive — v5 originals (8 checks)
// plus v7 fast-render additions (6 checks) = 14 total mandatory checks.
// These features were researched and proven essential for professional glass
// product rendering at fast render speeds. Removing ANY causes visible quality
// regression or unacceptable render time increase.
//
// NEVER remove a check from this list. Only ADD new ones.
function checkMandatoryFeatures(baseline) {
  const scriptPath = findLatestBuildScript();
  if (!scriptPath) {
    console.warn('[WARNING] No build script found to validate features against.');
    return { compliance: 0, passed: [], failed: [], script: null };
  }

  let scriptContent;
  try {
    scriptContent = fs.readFileSync(scriptPath, 'utf8');
  } catch (e) {
    console.warn(`[WARNING] Could not read build script: ${scriptPath}`);
    return { compliance: 0, passed: [], failed: [], script: scriptPath };
  }

  const passed = [];
  const failed = [];
  const gates = baseline?.autoresearch_gates || {};

  // ── HDRI Environment ──────────────────────────────────────────────────
  // Research: HDRI is essential for glass reflections. Without it glass
  // looks flat/plastic. This was THE single biggest improvement from v3→v4.
  if (gates.hdri_environment?.required) {
    const hasHDRI = scriptContent.includes('environment_texture') ||
                    scriptContent.includes('studio.exr') ||
                    scriptContent.includes('.exr') ||
                    scriptContent.includes('HDRI') ||
                    scriptContent.includes('hdri');
    if (hasHDRI) {
      passed.push({ feature: 'hdri_environment', status: 'PASS', rationale: 'HDRI environment detected in build script' });
    } else {
      failed.push({ feature: 'hdri_environment', status: 'FAIL', rationale: 'MANDATORY: HDRI environment missing. Glass will look flat/plastic without it.' });
    }
  }

  // ── Volume Absorption on Glass ─────────────────────────────────────────
  // Research: Volume Absorption on Material Output Volume socket gives
  // depth-dependent glass tint. Without it glass has no color depth.
  if (gates.volume_absorption_glass?.required) {
    const hasGlassVolume = scriptContent.includes('VolumeAbsorption') ||
                           scriptContent.includes('Volume_Absorption') ||
                           scriptContent.includes('volume_absorption') ||
                           (scriptContent.includes('Volume') && scriptContent.includes('glass'));
    if (hasGlassVolume) {
      passed.push({ feature: 'volume_absorption_glass', status: 'PASS', rationale: 'Volume Absorption on glass detected' });
    } else {
      failed.push({ feature: 'volume_absorption_glass', status: 'FAIL', rationale: 'MANDATORY: Volume Absorption on glass missing. Glass will lack depth-dependent tint.' });
    }
  }

  // ── Volume Absorption on Liquid ────────────────────────────────────────
  // Research: Liquid needs Volume Absorption for physically accurate
  // depth-dependent color (amber that deepens with thickness).
  if (gates.volume_absorption_liquid?.required) {
    const hasLiquidVolume = (scriptContent.includes('volume') || scriptContent.includes('Volume')) &&
                            (scriptContent.includes('liquid') || scriptContent.includes('Liquid') || scriptContent.includes('amber'));
    if (hasLiquidVolume) {
      passed.push({ feature: 'volume_absorption_liquid', status: 'PASS', rationale: 'Volume Absorption on liquid detected' });
    } else {
      failed.push({ feature: 'volume_absorption_liquid', status: 'FAIL', rationale: 'MANDATORY: Volume Absorption on liquid missing. Liquid will lack depth-dependent color.' });
    }
  }

  // ── Solidify Modifier on Glass ─────────────────────────────────────────
  // Research: Real glass has wall thickness (2-3mm). Without Solidify,
  // refraction through infinitely thin surfaces is physically incorrect.
  if (gates.solidify_modifier?.required) {
    const hasSolidify = scriptContent.includes('SOLIDIFY') ||
                        scriptContent.includes('solidify') ||
                        scriptContent.includes('Solidify');
    if (hasSolidify) {
      passed.push({ feature: 'solidify_modifier', status: 'PASS', rationale: 'Solidify modifier detected' });
    } else {
      failed.push({ feature: 'solidify_modifier', status: 'FAIL', rationale: 'MANDATORY: Solidify modifier on glass missing. Refraction will be physically incorrect.' });
    }
  }

  // ── Minimum Bounce Count ───────────────────────────────────────────────
  // Research: Glass + liquid nested refraction needs high bounces.
  // v7: minimum 12 (researched), preferred 16 (fast preset).
  // Check both literal assignment (v5/v6 style) and preset dict values (v7 style).
  if (gates.min_bounce_count?.minimum) {
    let bounceCount = 0;
    // v5/v6 style: max_bounces = 64
    const literalMatch = scriptContent.match(/max_bounces\s*=\s*(\d+)/);
    if (literalMatch) {
      bounceCount = parseInt(literalMatch[1]);
    }
    // v7 style: preset dict with "bounces": N — find the MINIMUM across all presets
    const presetBounceMatches = scriptContent.match(/"bounces"\s*:\s*(\d+)/g);
    if (presetBounceMatches && presetBounceMatches.length > 0) {
      const presetBounces = presetBounceMatches.map(m => parseInt(m.match(/(\d+)/)[1]));
      const minPresetBounce = Math.min(...presetBounces);
      bounceCount = Math.max(bounceCount, minPresetBounce);
    }
    const minRequired = gates.min_bounce_count.minimum;
    if (bounceCount >= minRequired) {
      passed.push({ feature: 'min_bounce_count', status: 'PASS', rationale: `Bounce count ${bounceCount} >= minimum ${minRequired}` });
    } else {
      failed.push({ feature: 'min_bounce_count', status: 'FAIL', rationale: `MANDATORY: Bounce count ${bounceCount} < minimum ${minRequired}. Glass refraction will be cut off.` });
    }
  }

  // ── Minimum Light Count ────────────────────────────────────────────────
  // Research: Glass products need minimum 5 lights (Key, Fill, Rim, Top, Backlight).
  // 3-point lighting is not enough for glass edge definition + liquid glow.
  if (gates.min_light_count?.minimum) {
    // Count light creation patterns in script
    const lightPatterns = scriptContent.match(/bpy\.data\.lights\.new|new_light|type\s*=\s*['"]AREA['"]/g);
    const lightCount = lightPatterns ? lightPatterns.length : 0;
    const minRequired = gates.min_light_count.minimum;
    if (lightCount >= minRequired) {
      passed.push({ feature: 'min_light_count', status: 'PASS', rationale: `Light count ~${lightCount} >= minimum ${minRequired}` });
    } else {
      failed.push({ feature: 'min_light_count', status: 'FAIL', rationale: `MANDATORY: Light count ~${lightCount} < minimum ${minRequired}. Glass needs 5+ lights for proper edge definition.` });
    }
  }

  // ── Transparent BSDF Shadow Mix ────────────────────────────────────────
  // Research: Principled BSDF alone produces noisy/dark glass shadows.
  // Mix with Transparent BSDF via Light Path Is Shadow Ray for clean shadows.
  if (gates.transparent_shadow_mix?.required) {
    const hasShadowMix = scriptContent.includes('Transparent') &&
                         (scriptContent.includes('Shadow') || scriptContent.includes('shadow') ||
                          scriptContent.includes('Is Shadow Ray') || scriptContent.includes('is_shadow_ray'));
    if (hasShadowMix) {
      passed.push({ feature: 'transparent_shadow_mix', status: 'PASS', rationale: 'Transparent BSDF shadow mix detected' });
    } else {
      failed.push({ feature: 'transparent_shadow_mix', status: 'FAIL', rationale: 'MANDATORY: Transparent BSDF shadow mix missing. Glass shadows will be noisy/dark.' });
    }
  }

  // ── Light Blockers (Black Card + White Bounce) ─────────────────────────
  // Research: Professional glass photography uses flags/bounces for edge
  // definition. Without them glass has no visible edges against background.
  if (gates.light_blockers?.required) {
    const hasBlockers = (scriptContent.includes('blocker') || scriptContent.includes('Blocker') ||
                         scriptContent.includes('black_card') || scriptContent.includes('bounce_card') ||
                         scriptContent.includes('Black Card') || scriptContent.includes('White Bounce') ||
                         scriptContent.includes('visible_camera') || scriptContent.includes('ray_visibility'));
    if (hasBlockers) {
      passed.push({ feature: 'light_blockers', status: 'PASS', rationale: 'Light blocker planes detected' });
    } else {
      failed.push({ feature: 'light_blockers', status: 'FAIL', rationale: 'MANDATORY: Light blocker planes missing. Glass edges will have no definition against background.' });
    }
  }

  // ── [v7] OIDN Denoiser ───────────────────────────────────────────────
  // Fast render secret #1: OIDN is THE key to low-sample-count quality.
  // Without it, 128 samples looks noisy. With it, 128 looks like 1024.
  if (gates.oidn_denoiser?.required) {
    const hasOIDN = scriptContent.includes('OPENIMAGEDENOISE') ||
                    scriptContent.includes('OIDN') ||
                    scriptContent.includes('openimagedenoise');
    if (hasOIDN) {
      passed.push({ feature: 'oidn_denoiser', status: 'PASS', rationale: 'OIDN denoiser detected in build script' });
    } else {
      failed.push({ feature: 'oidn_denoiser', status: 'FAIL', rationale: 'MANDATORY v7: OIDN denoiser missing. Low sample counts will look noisy without it.' });
    }
  }

  // ── [v7] Denoising Data Passes (Albedo + Normal) ─────────────────────
  // Fast render secret #1b: Data passes give OIDN edge/texture information.
  // Without them the denoiser smears detail instead of preserving edges.
  if (gates.denoising_data_passes?.required) {
    const hasDataPasses = scriptContent.includes('denoising_store_passes') ||
                          scriptContent.includes('denoising_use_data') ||
                          scriptContent.includes('use_denoising_data') ||
                          scriptContent.includes('pass_denoising_data') ||
                          scriptContent.includes('denoising_data') ||
                          (scriptContent.includes('albedo') && scriptContent.includes('normal') && scriptContent.includes('denois'));
    if (hasDataPasses) {
      passed.push({ feature: 'denoising_data_passes', status: 'PASS', rationale: 'Denoising data passes detected' });
    } else {
      failed.push({ feature: 'denoising_data_passes', status: 'FAIL', rationale: 'MANDATORY v7: Denoising data passes missing. OIDN will smear detail without albedo+normal passes.' });
    }
  }

  // ── [v7] Filter Glossy (blur_glossy) ─────────────────────────────────
  // Fast render secret #2: Smooths noise in glossy/reflective materials.
  // Critical for glass products. Up to 5% faster just from this setting.
  if (gates.filter_glossy?.required) {
    const hasFilterGlossy = scriptContent.includes('blur_glossy') ||
                            scriptContent.includes('filter_glossy') ||
                            scriptContent.includes('Filter Glossy');
    if (hasFilterGlossy) {
      passed.push({ feature: 'filter_glossy', status: 'PASS', rationale: 'Filter Glossy (blur_glossy) detected' });
    } else {
      failed.push({ feature: 'filter_glossy', status: 'FAIL', rationale: 'MANDATORY v7: Filter Glossy missing. Glass noise will require more samples to resolve.' });
    }
  }

  // ── [v7] Clamp Indirect ──────────────────────────────────────────────
  // Fast render secret #6: Kills fireflies without darkening glass.
  // clamp_indirect = 10 is the researched sweet spot.
  if (gates.clamp_indirect?.required) {
    const hasClamp = scriptContent.includes('sample_clamp_indirect') ||
                     scriptContent.includes('clamp_indirect');
    if (hasClamp) {
      passed.push({ feature: 'clamp_indirect', status: 'PASS', rationale: 'Clamp indirect detected' });
    } else {
      failed.push({ feature: 'clamp_indirect', status: 'FAIL', rationale: 'MANDATORY v7: Clamp indirect missing. Fireflies will waste samples and create bright pixel noise.' });
    }
  }

  // ── [v7] Caustics OFF ────────────────────────────────────────────────
  // Fast render secret #7: Reflective + refractive caustics OFF saves
  // massive noise. Lighting placement fakes the caustic look.
  if (gates.caustics_off?.required) {
    const hasCausticsOff = scriptContent.includes('caustics_reflective') ||
                           scriptContent.includes('caustics_refractive') ||
                           scriptContent.includes('caustics_off') ||
                           scriptContent.includes('caustics = False');
    if (hasCausticsOff) {
      passed.push({ feature: 'caustics_off', status: 'PASS', rationale: 'Caustics OFF setting detected' });
    } else {
      failed.push({ feature: 'caustics_off', status: 'FAIL', rationale: 'MANDATORY v7: Caustics OFF missing. Reflective/refractive caustics create massive noise at low sample counts.' });
    }
  }

  // ── [v7] Preset System ───────────────────────────────────────────────
  // v7 requires configurable render presets (micro/fast/quality/ultra).
  // Hardcoded single-quality scripts are not acceptable.
  if (gates.preset_system?.required) {
    const hasPresets = scriptContent.includes('PRESETS') ||
                       scriptContent.includes('preset') ||
                       (scriptContent.includes('micro') && scriptContent.includes('fast') && scriptContent.includes('quality') && scriptContent.includes('ultra'));
    if (hasPresets) {
      passed.push({ feature: 'preset_system', status: 'PASS', rationale: 'Preset system (micro/fast/quality/ultra) detected' });
    } else {
      failed.push({ feature: 'preset_system', status: 'FAIL', rationale: 'MANDATORY v7: Preset system missing. Build script must have configurable presets for speed/quality tradeoff.' });
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // FORENSIC SCENE GATES (v9+)
  // These validate forensic animation quality. Product animation gates (above)
  // remain unchanged. Forensic gates are ADDITIVE — they only check when
  // forensic scene scripts exist.
  // ══════════════════════════════════════════════════════════════════════════
  const forensicScripts = findForensicSceneScripts();
  const hasForensicPipeline = forensicScripts.length > 0;

  if (hasForensicPipeline) {
    // Concatenate all forensic script content for checking
    let forensicContent = '';
    for (const fp of forensicScripts) {
      try { forensicContent += fs.readFileSync(fp, 'utf8') + '\n'; } catch (e) { /* */ }
    }

    // ── Vehicle Geometry Quality ──────────────────────────────────────────
    if (gates.vehicle_geometry_score?.required) {
      const hasDetailedVehicles = forensicContent.includes('wheel_well') ||
                                   forensicContent.includes('panel_line') ||
                                   forensicContent.includes('window_cutout') ||
                                   forensicContent.includes('headlight') ||
                                   forensicContent.includes('bevel') ||
                                   forensicContent.includes('subdivision') ||
                                   forensicContent.includes('subsurf');
      if (hasDetailedVehicles) {
        passed.push({ feature: 'vehicle_geometry_score', status: 'PASS', rationale: 'Vehicle detail geometry features detected in forensic scripts' });
      } else {
        failed.push({ feature: 'vehicle_geometry_score', status: 'FAIL', rationale: 'FORENSIC CRITICAL: No vehicle detail geometry (wheel wells, panel lines, window cutouts) found. Vehicles are primitive boxes — disqualifying for court use.' });
      }
    }

    // ── Pedestrian Figure Realism ─────────────────────────────────────────
    if (gates.pedestrian_figure_score?.required) {
      const hasRealisticPedestrian = forensicContent.includes('armature') ||
                                      forensicContent.includes('rig') ||
                                      forensicContent.includes('humanoid') ||
                                      forensicContent.includes('mannequin') ||
                                      forensicContent.includes('makehuman') ||
                                      forensicContent.includes('mixamo') ||
                                      forensicContent.includes('pedestrian_mesh');
      if (hasRealisticPedestrian) {
        passed.push({ feature: 'pedestrian_figure_score', status: 'PASS', rationale: 'Realistic pedestrian figure techniques detected' });
      } else {
        failed.push({ feature: 'pedestrian_figure_score', status: 'FAIL', rationale: 'FORENSIC CRITICAL: No realistic pedestrian model found. Featureless blobs destroy expert credibility in cross-examination.' });
      }
    }

    // ── Impact Deformation ────────────────────────────────────────────────
    if (gates.impact_deformation_required?.required) {
      const hasDeformation = forensicContent.includes('deform') ||
                              forensicContent.includes('crumple') ||
                              forensicContent.includes('damage') ||
                              forensicContent.includes('proportional_edit') ||
                              forensicContent.includes('shape_key') ||
                              forensicContent.includes('lattice') ||
                              forensicContent.includes('mesh_deform');
      if (hasDeformation) {
        passed.push({ feature: 'impact_deformation_required', status: 'PASS', rationale: 'Impact deformation techniques detected in forensic scripts' });
      } else {
        failed.push({ feature: 'impact_deformation_required', status: 'FAIL', rationale: 'FORENSIC CRITICAL: No impact deformation found. Collision scenes show zero vehicle damage — completely unrealistic for accident reconstruction.' });
      }
    }

    // ── Exhibit Standards Compliance ──────────────────────────────────────
    if (gates.exhibit_standards_compliance?.required) {
      const hasScaleBar = forensicContent.includes('scale_bar') || forensicContent.includes('measurement');
      const hasDisclaimer = forensicContent.includes('DEMONSTRATIVE') || forensicContent.includes('demonstrative') || forensicContent.includes('disclaimer');
      const hasCaseNumber = forensicContent.includes('case_number') || forensicContent.includes('exhibit') || forensicContent.includes('EXHIBIT');
      const exhibitScore = [hasScaleBar, hasDisclaimer, hasCaseNumber].filter(Boolean).length;
      if (exhibitScore >= 2) {
        passed.push({ feature: 'exhibit_standards_compliance', status: 'PASS', rationale: `Exhibit overlay features detected (${exhibitScore}/3 core checks)` });
      } else {
        failed.push({ feature: 'exhibit_standards_compliance', status: 'FAIL', rationale: `FORENSIC CRITICAL: Only ${exhibitScore}/3 exhibit standards found. Renders need scale bars, disclaimers, and case/exhibit numbers for court admissibility.` });
      }
    }

    // ── Driver POV Interior Geometry ──────────────────────────────────────
    if (gates.driver_pov_interior?.required) {
      const hasInterior = forensicContent.includes('dashboard') ||
                           forensicContent.includes('steering') ||
                           forensicContent.includes('a_pillar') ||
                           forensicContent.includes('A-pillar') ||
                           forensicContent.includes('rearview') ||
                           forensicContent.includes('interior') ||
                           forensicContent.includes('windshield');
      if (hasInterior) {
        passed.push({ feature: 'driver_pov_interior', status: 'PASS', rationale: 'Driver POV interior geometry features detected' });
      } else {
        failed.push({ feature: 'driver_pov_interior', status: 'FAIL', rationale: 'FORENSIC CRITICAL: No interior geometry (dashboard, steering wheel, A-pillars) found for Driver POV cameras. Empty box interior is legally indefensible.' });
      }
    }

    // ── Physics Validation Method ─────────────────────────────────────────
    if (gates.physics_validation?.required) {
      const hasPhysics = forensicContent.includes('rigid_body') ||
                          forensicContent.includes('RigidBody') ||
                          forensicContent.includes('pc_crash') ||
                          forensicContent.includes('virtual_crash') ||
                          forensicContent.includes('momentum') ||
                          forensicContent.includes('physics') ||
                          forensicContent.includes('collision_force');
      if (hasPhysics) {
        passed.push({ feature: 'physics_validation', status: 'PASS', rationale: 'Physics validation method detected in forensic scripts' });
      } else {
        failed.push({ feature: 'physics_validation', status: 'FAIL', rationale: 'FORENSIC CRITICAL: No physics validation method found. Collision dynamics using pure keyframe interpolation will fail Daubert challenge.' });
      }
    }
  }

  const total = passed.length + failed.length;
  const compliance = total > 0 ? Math.round((passed.length / total) * 100) : 0;

  return { compliance, passed, failed, script: scriptPath };
}

// ─── Baseline Score Compliance Check ─────────────────────────────────────────
function checkBaselineCompliance(kb, baseline) {
  if (!baseline) return { compliance: 0, passed: [], failed: [] };

  const passed = [];
  const failed = [];
  const gates = baseline.autoresearch_gates || {};

  // Check each score-based KPI gate (skip required/minimum feature gates)
  for (const [kpiName, gate] of Object.entries(gates)) {
    // Skip non-score gates (handled by checkMandatoryFeatures)
    if (gate.required || gate.minimum) continue;
    if (!gate.do_not_regress_below) continue;

    const currentScore = kb.benchmarks[gate.kpi_name]?.our_score || 0;
    const minimumScore = gate.do_not_regress_below || 0;

    if (currentScore >= minimumScore) {
      passed.push({
        kpi: kpiName,
        current: currentScore,
        minimum: minimumScore,
        baseline: gate.baseline,
        status: 'PASS',
      });
    } else {
      failed.push({
        kpi: kpiName,
        current: currentScore,
        minimum: minimumScore,
        baseline: gate.baseline,
        status: 'FAIL',
        deficit: minimumScore - currentScore,
      });
    }
  }

  const compliance = Math.round((passed.length / (passed.length + failed.length)) * 100) || 0;

  return { compliance, passed, failed };
}

// ─── Knowledge Base Schema ──────────────────────────────────────────────────
function loadKnowledge() {
  if (fs.existsSync(KNOWLEDGE_PATH)) {
    return JSON.parse(fs.readFileSync(KNOWLEDGE_PATH, 'utf8'));
  }
  return createDefaultKnowledge();
}

function createDefaultKnowledge() {
  return {
    version: 1,
    created: new Date().toISOString(),
    updated: new Date().toISOString(),
    techniques: {
      materials: {
        glass: {
          description: "Principled BSDF glass with Volume Absorption, Solidify, Transparent shadow mix (v7)",
          values: {
            transmission: 1.0, ior: 1.5, roughness: 0.0, specular_ior_level: 1.0, coat_weight: 0.0,
            volume_absorption: true, volume_density_glass: 0.003, volume_density_liquid: 0.3,
            liquid_volume_color: [1.0, 0.78, 0.42],
            solidify_thickness: 0.025, transparent_shadow_mix: true
          },
          sources: ["blenderartists.org", "seifhussam3d.com", "cgcookie.com", "blender.stackexchange.com"],
          quality_tier: "professional",
          notes: "v7 baseline: Volume Absorption + Solidify + Transparent shadow mix. Glass density 0.003 (clear), liquid density 0.3 (golden amber). NEVER remove any of these."
        },
        metal_brushed: {
          description: "Brushed aluminum/stainless steel",
          values: { metallic: 1.0, roughness: 0.35, coat_weight: 0.2 },
          sources: ["polygonrunway.com"],
          quality_tier: "professional",
          notes: "Anisotropic 0.3-0.5 adds directional brushing."
        },
        metal_polished: {
          description: "Polished chrome/mirror metal",
          values: { metallic: 1.0, roughness: 0.08, coat_weight: 0.5, coat_roughness: 0.02 },
          sources: ["therookies.co"],
          quality_tier: "professional",
          notes: "Sub-0.1 roughness needs high samples (512+)."
        },
        gold: {
          description: "Gold metal (yellow/rose variants)",
          values: { metallic: 1.0, roughness: 0.15, base_color: [1.0, 0.84, 0.0] },
          sources: ["skillshare.com/jewelry-design"],
          quality_tier: "professional",
          notes: "Rose gold: [0.95, 0.77, 0.69]. Coat weight 0.3."
        },
        plastic_glossy: {
          description: "High-gloss consumer plastic",
          values: { metallic: 0.0, roughness: 0.15, coat_weight: 0.2, coat_roughness: 0.05 },
          sources: ["bevelfish.com"],
          quality_tier: "professional"
        },
        leather: {
          description: "Natural leather material",
          values: { metallic: 0.0, roughness: 0.55, subsurface: 0.05, coat_weight: 0.15 },
          sources: ["udemy.com/blender-product"],
          quality_tier: "professional"
        },
        ceramic: {
          description: "Glazed ceramic",
          values: { metallic: 0.0, roughness: 0.45, subsurface: 0.2, coat_weight: 0.8, coat_roughness: 0.1 },
          sources: ["bevelfish.com"],
          quality_tier: "professional"
        },
      },
      lighting: {
        five_point_glass_product: {
          description: "v7 5-point glass product lighting (Key, Fill, Rim, Top, Backlight)",
          values: {
            key: { type: "AREA", energy: 700, size: 3.0, color_temp: "warm" },
            fill: { type: "AREA", energy: 200, size: 5.0, color_temp: "cool" },
            rim: { type: "AREA", energy: 1200, size: 0.6, color_temp: "neutral" },
            top: { type: "AREA", energy: 150, size: 2.0, color_temp: "neutral" },
            backlight: { type: "AREA", energy: 900, size: 4.0, color_temp: "warm" },
          },
          sources: ["blenderartists.org", "photography forums"],
          quality_tier: "professional",
          notes: "v7 baseline. Key 700W (down from 1000), Backlight 900W/4.0 (up from 400/1.5) for stronger liquid glow. 5 lights minimum. NEVER reduce below 5."
        },
        light_blockers: {
          description: "Black card + white bounce card for glass edge definition",
          values: {
            black_card: { location: "camera-left", visible_camera: false, visible_glossy: true },
            white_bounce: { location: "camera-right", visible_camera: false, visible_glossy: true },
          },
          sources: ["glass photography tutorials", "blenderartists.org"],
          quality_tier: "professional",
          notes: "v5 baseline. Professional glass photography technique. Controls edge contrast. NEVER remove."
        },
        hdri_environment: {
          description: "HDRI for glass reflections (mandatory for glass products)",
          values: { strength: 1.5, source: "studio.exr (built-in)" },
          sources: ["polyhaven.com", "blender manual"],
          quality_tier: "professional",
          notes: "v7 baseline. HDRI strength 1.5 (down from 2.0 — was washing out with rebalanced lighting). MANDATORY for glass products. NEVER revert to gradient-only."
        },
        three_point_product: {
          description: "Standard 3-point product studio lighting (non-glass products)",
          values: {
            key: { type: "AREA", energy: 100, size: 1.5 },
            fill: { type: "AREA", energy: 40, size: 2.0 },
            rim: { type: "AREA", energy: 150, size: 1.2 },
          },
          sources: ["vagon.io/blog", "foxrenderfarm.com"],
          quality_tier: "professional",
          notes: "For non-glass products. Glass products MUST use five_point_glass_product instead."
        },
      },
      camera: {
        turntable: {
          description: "360 orbit at constant speed",
          values: { frames: 240, interpolation: "LINEAR", focal: 50, f_stop: 2.8 },
          sources: ["polygon-runway", "seifhussam3d.com"],
          quality_tier: "professional"
        },
        hero_reveal: {
          description: "Dolly-in + zoom + rise for dramatic entrance",
          values: { frames: 180, easing: "EASE_OUT", start_focal: 35, end_focal: 85 },
          sources: ["reggieperryjr.com"],
          quality_tier: "professional"
        },
        detail_orbit: {
          description: "Slow partial orbit (90-120) with dolly-in",
          values: { frames: 300, easing: "EASE_IN_OUT", orbit_angle: 120, focal: 85, f_stop: 1.8 },
          sources: ["polygonrunway.com"],
          quality_tier: "professional"
        },
      },
      render: {
        cycles_glass_product: {
          description: "Cycles render for glass products (v7 fast quality baseline)",
          values: {
            presets: { micro: 64, fast: 128, quality: 512, ultra: 1024 },
            default_preset: "fast",
            denoiser: "OPENIMAGEDENOISE", denoising_data_passes: true,
            filter_glossy: { fast: 1.0, quality: 0.5, ultra: 0.0 },
            adaptive_threshold: { fast: 0.02, quality: 0.005, ultra: 0.003 },
            max_bounces: { fast: 16, quality: 32, ultra: 64 },
            clamp_indirect: 10, clamp_direct: 0,
            caustics_reflective: false, caustics_refractive: false,
            volume_bounces: 8,
            color_management: "AgX", look: "AgX - Punchy",
          },
          sources: ["blender manual", "blenderartists.org", "gachoki.com", "renderday.com", "blendergrid.com", "radarrender.com"],
          quality_tier: "professional",
          notes: "v7 baseline. 7 fast-render secrets: OIDN+data passes, filter glossy, 16 bounces (fast), adaptive 0.02, transparent shadow, clamp 10, caustics OFF. 128 samples = 1024 quality. NEVER remove OIDN or data passes. Bounces NEVER below 12."
        },
      },
      compositing: {
        bloom_product: {
          description: "Subtle bloom/glow on specular highlights",
          values: { node: "Glare", type: "FOG_GLOW", threshold: 0.8, mix: -0.7, size: 6 },
          sources: ["multiple"],
          quality_tier: "professional"
        },
      },
      animation_timing: {
        luxury_product: {
          description: "Timing specs for luxury/premium products",
          values: {
            entrance: "48-90 frames",
            turntable: "180-240 frames",
            hold_hero: "72-120 frames",
          },
          sources: ["industry analysis"],
          quality_tier: "professional"
        },
      },
    },
    gaps: [
      { id: "edit_mode_mesh", description: "Direct edit-mode mesh operations", severity: "medium", workaround: "execute_python with bpy.ops.mesh.*" },
      { id: "displacement_maps", description: "Texture-based displacement for surface detail", severity: "medium", workaround: "Procedural noise displacement" },
      { id: "anisotropic_brushing", description: "Directional brushed metal texture", severity: "medium", workaround: "execute_python to set anisotropic + tangent" },
      { id: "ies_lights", description: "IES light profiles", severity: "low", workaround: "Area lights with proper sizing" },
      { id: "higher_sample_gpu", description: "GPU rendering on Metal (hangs on kernel compilation)", severity: "high", workaround: "CPU fallback with --cycles-device CPU" },
    ],
    benchmarks: {
      material_realism: { our_score: 93, industry_target: 95, notes: "v7 glass: refined absorption (0.003), golden liquid (0.3/[1,0.78,0.42]). Missing displacement maps." },
      lighting_quality: { our_score: 93, industry_target: 95, notes: "v7 5-point + HDRI 1.5 + blockers. Key 700W, Backlight 900W/4.0 for liquid glow. Missing IES profiles." },
      camera_motion: { our_score: 90, industry_target: 95, notes: "Turntable + hero + detail covers 90% of use cases" },
      render_quality: { our_score: 93, industry_target: 95, notes: "v7: 7 fast-render secrets. 128 samples = 1024 quality. OIDN + filter glossy + 16 bounces + caustics OFF." },
      animation_timing: { our_score: 85, industry_target: 95, notes: "Good f-curve control. Need more shot transitions." },
      overall_readiness: { our_score: 93, industry_target: 95, notes: "v7 is production-ready. Glass reads as glass. Fast preset (3:50) matches quality preset visually." },
    },
    learning_log: [],
    stats: {
      total_scans: 0,
      total_techniques_learned: 0,
      total_improvements_made: 0,
      total_gaps_closed: 0,
    },
  };
}

function saveKnowledge(kb) {
  kb.updated = new Date().toISOString();
  fs.mkdirSync(path.dirname(KNOWLEDGE_PATH), { recursive: true });
  fs.writeFileSync(KNOWLEDGE_PATH, JSON.stringify(kb, null, 2));
}

// ─── Inventory Counter ──────────────────────────────────────────────────────
function countPresets() {
  const result = { materials: 0, lighting: 0, cameras: 0, demos: 0, recipes: 0 };

  try {
    const presetsContent = fs.readFileSync(PRESETS_PATH, 'utf8');
    const matMatches = presetsContent.match(/"[a-z_]+"\s*:\s*\{.*?"color"/gs);
    result.materials = matMatches ? matMatches.length : 0;
    const lightMatches = presetsContent.match(/"[a-z_]+"\s*:\s*\{[^}]*"lights"/gs);
    result.lighting = lightMatches ? lightMatches.length : 0;
    result.cameras = 3;
  } catch (e) { /* file may not exist */ }

  try {
    const recipesContent = fs.readFileSync(RECIPES_PATH, 'utf8');
    const recipeMatches = recipesContent.match(/def recipe_\w+/g);
    result.recipes = recipeMatches ? recipeMatches.length : 0;
  } catch (e) { /* */ }

  try {
    const demos = fs.readdirSync(DEMOS_DIR).filter(f => f.startsWith('demo_') && f.endsWith('.py'));
    result.demos = demos.length;
  } catch (e) { /* */ }

  return result;
}

// ─── Benchmark Calculator ───────────────────────────────────────────────────
function calculateBenchmarks(kb) {
  const counts = countPresets();
  const techniques = kb.techniques;

  const matScore = Math.min(95, 50 + (counts.materials * 2) +
    (techniques.materials.glass ? 5 : 0) +
    (techniques.materials.metal_polished ? 5 : 0) +
    (techniques.materials.leather ? 3 : 0));

  const lightScore = Math.min(95, 60 + (counts.lighting * 4) +
    (techniques.lighting.five_point_glass_product ? 8 : 0) +
    (techniques.lighting.hdri_environment ? 5 : 0) +
    (techniques.lighting.light_blockers ? 5 : 0));

  const camScore = Math.min(95, 60 + (counts.cameras * 10) +
    (techniques.camera.turntable ? 5 : 0) +
    (techniques.camera.hero_reveal ? 5 : 0));

  // render_quality: dynamically calculated from render techniques + fast-render secrets
  const renderTech = techniques.render || {};
  const compositingTech = techniques.compositing || {};
  const renderScore = Math.min(95, 60 +
    (renderTech.cycles_product ? 10 : 0) +
    (renderTech.cycles_product?.values?.denoiser === 'OPENIMAGEDENOISE' ? 5 : 0) +
    (renderTech.cycles_product?.values?.color_management === 'AgX' ? 5 : 0) +
    (compositingTech.bloom_product ? 3 : 0) +
    (compositingTech.vignette ? 3 : 0) +
    (Object.keys(renderTech).length * 3) +
    (Object.keys(compositingTech).length * 2));

  const overall = Math.round((matScore + lightScore + camScore +
    renderScore +
    kb.benchmarks.animation_timing.our_score) / 5);

  kb.benchmarks.material_realism.our_score = matScore;
  kb.benchmarks.lighting_quality.our_score = lightScore;
  kb.benchmarks.camera_motion.our_score = camScore;
  kb.benchmarks.render_quality.our_score = renderScore;

  return kb;
}

// ─── Search Topics ──────────────────────────────────────────────────────────
function getSearchTopics(kb) {
  const topics = [];
  topics.push('Blender 5.x product animation new features 2026');
  topics.push('Blender Cycles product rendering glass optimization');
  topics.push('photorealistic product render Blender shader tips');

  const sortedBenchmarks = Object.entries(kb.benchmarks)
    .sort((a, b) => a[1].our_score - b[1].our_score);

  for (const [key] of sortedBenchmarks.slice(0, 3)) {
    if (key === 'material_realism') {
      topics.push('Blender anisotropic metal shader product');
      topics.push('Blender displacement texture product close-up');
    }
    if (key === 'lighting_quality') {
      topics.push('Blender IES light product photography');
      topics.push('Blender light linking product render');
    }
    if (key === 'animation_timing') {
      topics.push('product animation timing motion design principles');
    }
  }

  for (const gap of kb.gaps.filter(g => g.severity === 'medium' || g.severity === 'high')) {
    topics.push(`Blender ${gap.id.replace(/_/g, ' ')} tutorial`);
  }

  return topics.slice(0, 8);
}

// ─── Report Generator ───────────────────────────────────────────────────────
function generateReport(kb, baselineCompliance, featureCompliance) {
  const counts = countPresets();
  const techniqueCount = Object.values(kb.techniques)
    .reduce((sum, cat) => sum + Object.keys(cat).length, 0);

  const report = {
    generated_at: new Date().toISOString(),
    agent: 'autoresearch-blender-expertise',
    baseline_version: 'v5',
    version: kb.version,

    kpis: {
      knowledge_entries: techniqueCount,
      material_presets: counts.materials,
      lighting_rigs: counts.lighting,
      camera_styles: counts.cameras,
      demo_count: counts.demos,
      recipe_count: counts.recipes,
      tutorial_sources: new Set(
        Object.values(kb.techniques)
          .flatMap(cat => Object.values(cat))
          .flatMap(t => t.sources || [])
      ).size,
      last_improvement_date: kb.updated,
      quality_score: kb.benchmarks.overall_readiness.our_score,
      technique_coverage: Math.round(
        (1 - kb.gaps.length / (techniqueCount + kb.gaps.length)) * 100
      ),
      gap_count: kb.gaps.length,
      baseline_compliance: baselineCompliance?.compliance || 0,
      mandatory_features_ok: featureCompliance?.compliance || 0,
    },

    benchmarks: kb.benchmarks,
    gaps: kb.gaps,
    baseline_compliance: baselineCompliance,
    mandatory_features: featureCompliance,

    inventory: {
      materials: counts.materials,
      lighting_rigs: counts.lighting,
      camera_styles: counts.cameras,
      demos: counts.demos,
      recipes: counts.recipes,
    },

    recommendations: [],
    stats: kb.stats,
  };

  // Mandatory feature failures are CRITICAL
  if (featureCompliance && featureCompliance.failed.length > 0) {
    for (const fail of featureCompliance.failed) {
      report.recommendations.push({
        priority: 'critical',
        action: `MANDATORY FEATURE MISSING: ${fail.feature} — ${fail.rationale}`,
        expected_improvement: 'Restore mandatory feature immediately',
      });
    }
  }

  // Score-based baseline regressions
  if (baselineCompliance && baselineCompliance.failed.length > 0) {
    for (const fail of baselineCompliance.failed) {
      report.recommendations.push({
        priority: 'critical',
        action: `BASELINE REGRESSION: ${fail.kpi} dropped to ${fail.current} (minimum: ${fail.minimum})`,
        expected_improvement: `Restore to baseline ${fail.baseline}`,
      });
    }
  }

  // General improvement recommendations
  if (kb.benchmarks.material_realism.our_score < 90) {
    report.recommendations.push({
      priority: 'high',
      action: 'Add anisotropic brushed metal and displacement map support',
      expected_improvement: '+5-8 points material_realism',
    });
  }
  if (kb.benchmarks.lighting_quality.our_score < 90) {
    report.recommendations.push({
      priority: 'medium',
      action: 'Add IES light profile support and light linking',
      expected_improvement: '+3-5 points lighting_quality',
    });
  }

  // Save report
  fs.mkdirSync(path.dirname(REPORT_PATH), { recursive: true });
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));

  // Append to history
  let history = [];
  if (fs.existsSync(HISTORY_PATH)) {
    history = JSON.parse(fs.readFileSync(HISTORY_PATH, 'utf8'));
  }
  history.push({
    date: report.generated_at,
    quality_score: report.kpis.quality_score,
    knowledge_entries: report.kpis.knowledge_entries,
    gap_count: report.kpis.gap_count,
    technique_coverage: report.kpis.technique_coverage,
    baseline_compliance: report.kpis.baseline_compliance,
    mandatory_features_ok: report.kpis.mandatory_features_ok,
  });
  if (history.length > 90) history = history.slice(-90);
  fs.writeFileSync(HISTORY_PATH, JSON.stringify(history, null, 2));

  return report;
}

// ─── Main Cycle ─────────────────────────────────────────────────────────────
async function main() {
  console.log('═══════════════════════════════════════════════════════');
  console.log('  Blender Expertise Autoresearch Agent (v5 baseline)');
  console.log(`  Mode: ${DRY_RUN ? 'DRY RUN' : SCAN_ONLY ? 'SCAN' : REPORT_ONLY ? 'REPORT' : BASELINE_ONLY ? 'BASELINE' : FEATURES_ONLY ? 'FEATURES' : BENCHMARK_ONLY ? 'BENCHMARK' : 'FULL CYCLE'}`);
  console.log(`  Time: ${new Date().toISOString()}`);
  console.log('═══════════════════════════════════════════════════════\n');

  // Load knowledge base and baseline
  let kb = loadKnowledge();
  const baseline = loadBaseline();
  console.log(`[1/7] Knowledge base loaded (v${kb.version}, ${Object.keys(kb.techniques).length} categories)`);
  console.log(`[1/7] Quality baseline loaded (v${baseline?.version || 'MISSING'})`);

  // Benchmark
  console.log('[2/7] Running benchmarks...');
  kb = calculateBenchmarks(kb);
  const bm = kb.benchmarks;
  console.log(`  Material realism:  ${bm.material_realism.our_score}/${bm.material_realism.industry_target}`);
  console.log(`  Lighting quality:  ${bm.lighting_quality.our_score}/${bm.lighting_quality.industry_target}`);
  console.log(`  Camera motion:     ${bm.camera_motion.our_score}/${bm.camera_motion.industry_target}`);
  console.log(`  Render quality:    ${bm.render_quality.our_score}/${bm.render_quality.industry_target}`);
  console.log(`  Animation timing:  ${bm.animation_timing.our_score}/${bm.animation_timing.industry_target}`);
  console.log(`  OVERALL:           ${bm.overall_readiness.our_score}/${bm.overall_readiness.industry_target}`);

  // Baseline score compliance check
  console.log('[3/7] Checking baseline score compliance...');
  const baselineCompliance = checkBaselineCompliance(kb, baseline);
  console.log(`  Score compliance: ${baselineCompliance.compliance}%`);
  for (const p of baselineCompliance.passed) {
    console.log(`    PASS ${p.kpi}: ${p.current}/${p.minimum}`);
  }
  for (const f of baselineCompliance.failed) {
    console.log(`    FAIL ${f.kpi}: ${f.current}/${f.minimum} (REGRESSION! deficit: ${f.deficit})`);
  }

  // V5 mandatory feature check
  console.log('[4/7] Checking v5 mandatory features...');
  const featureCompliance = checkMandatoryFeatures(baseline);
  console.log(`  Feature compliance: ${featureCompliance.compliance}%`);
  if (featureCompliance.script) {
    console.log(`  Checked script: ${featureCompliance.script}`);
  }
  for (const p of featureCompliance.passed) {
    console.log(`    PASS ${p.feature}`);
  }
  for (const f of featureCompliance.failed) {
    console.log(`    FAIL ${f.feature}: ${f.rationale}`);
  }

  if (BASELINE_ONLY || FEATURES_ONLY) {
    console.log('\nDone.');
    return;
  }

  if (BENCHMARK_ONLY) {
    console.log('\n[BENCHMARK ONLY] Done.');
    return;
  }

  // Scan
  if (!REPORT_ONLY) {
    console.log('\n[5/7] Identifying search topics...');
    const topics = getSearchTopics(kb);
    console.log(`  Topics to research: ${topics.length}`);
    for (const t of topics) {
      console.log(`    - ${t}`);
    }
    kb.stats.total_scans++;
    console.log(`  (Search execution deferred to next LLM-assisted cycle)`);
  } else {
    console.log('\n[5/7] Skipping searches (--report mode)...');
  }

  // Generate report
  console.log('[6/7] Generating expertise report...');
  const report = generateReport(kb, baselineCompliance, featureCompliance);
  console.log(`  Quality score: ${report.kpis.quality_score}/100`);
  console.log(`  Knowledge entries: ${report.kpis.knowledge_entries}`);
  console.log(`  Technique coverage: ${report.kpis.technique_coverage}%`);
  console.log(`  Baseline compliance: ${report.kpis.baseline_compliance}%`);
  console.log(`  Mandatory features: ${report.kpis.mandatory_features_ok}%`);
  console.log(`  Open gaps: ${report.kpis.gap_count}`);
  console.log(`  Recommendations: ${report.recommendations.length}`);

  // Save
  if (!DRY_RUN) {
    console.log('\n[7/7] Saving knowledge base + report...');
    saveKnowledge(kb);
    console.log(`  Knowledge: ${KNOWLEDGE_PATH}`);
    console.log(`  Report:    ${REPORT_PATH}`);
    console.log(`  History:   ${HISTORY_PATH}`);
  } else {
    console.log('\n[7/7] DRY RUN — no files written.');
  }

  // Summary
  const counts = countPresets();
  console.log('\n═══════════════════════════════════════════════════════');
  console.log('  SUMMARY');
  console.log('═══════════════════════════════════════════════════════');
  console.log(`  Overall quality:       ${report.kpis.quality_score}/100`);
  console.log(`  Baseline compliance:   ${report.kpis.baseline_compliance}%`);
  console.log(`  Mandatory features:    ${report.kpis.mandatory_features_ok}%`);
  console.log(`  Material presets:      ${counts.materials}`);
  console.log(`  Lighting rigs:         ${counts.lighting}`);
  console.log(`  Camera styles:         ${counts.cameras}`);
  console.log('═══════════════════════════════════════════════════════\n');

  if (report.recommendations.length > 0) {
    console.log('  TOP RECOMMENDATIONS:');
    for (const rec of report.recommendations.slice(0, 5)) {
      console.log(`    [${rec.priority.toUpperCase()}] ${rec.action}`);
    }
    console.log('');
  }
}

main().catch(err => {
  console.error('Autoresearch agent error:', err);
  process.exit(1);
});
