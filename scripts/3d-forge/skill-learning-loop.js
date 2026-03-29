#!/usr/bin/env node
/**
 * Skill Learning Loop — Metrics → Skill Planner Feedback Engine
 *
 * Reads post-validation metrics (from metrics-tracker.js) and generates
 * skill-plan-adjustments.json that the SkillExecutor's planSkillsForConcept()
 * consumes on the next run to auto-correct weak dimensions.
 *
 * Learning signals:
 *   1. Visual dimension scores → recommend specific skills for weak areas
 *   2. Mechanical failure rates → recommend prevalidation skills
 *   3. Skill utilization rates → flag underused skills
 *   4. Hall-of-failures patterns → targeted fixes for recurring failures
 *   5. Category-specific performance → per-category skill overrides
 *
 * Output: config/3d-forge/skill-plan-adjustments.json
 *
 * Usage:
 *   node skill-learning-loop.js [--metrics-path PATH] [--dry-run]
 */

const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { promisify } = require('util');

const execFileAsync = promisify(execFile);

const REPO_ROOT = path.join(__dirname, '..', '..');
const CONFIG_DIR = path.join(REPO_ROOT, 'config', '3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const DATA_DIR = path.join(REPO_ROOT, 'data', '3d-forge');
const ADJUSTMENTS_PATH = path.join(CONFIG_DIR, 'skill-plan-adjustments.json');

const isDryRun = process.argv.includes('--dry-run');

function log(msg, level = 'info') {
  const ts = new Date().toISOString();
  console.log(`[${ts}] [LEARN:${level.toUpperCase()}] ${msg}`);
}

/**
 * Visual dimension → skill recommendation map
 * When a visual dimension scores below threshold, these skills are recommended
 */
const DIMENSION_SKILL_MAP = {
  shape_accuracy: {
    threshold: 5.0,
    skills: ['proportion_reference_check', 'scale_normalizer'],
    phase: 'prevalidate',
    reason: 'Low shape accuracy indicates geometry doesn\'t match reference proportions'
  },
  proportion_accuracy: {
    threshold: 5.0,
    skills: ['proportion_reference_check', 'scale_normalizer'],
    phase: 'prevalidate',
    reason: 'Incorrect proportions — enforce reference dimensions'
  },
  detail_level: {
    threshold: 4.0,
    skills: ['subdivision_detail_pass', 'displacement_micro_detail', 'bevel_modifier_edges'],
    phase: 'polish',
    reason: 'Insufficient surface detail — add subdivision and micro-displacement'
  },
  material_quality: {
    threshold: 5.0,
    skills: ['displacement_micro_detail', 'default_product_material'],
    phase: 'materials',
    reason: 'Material quality too low — ensure noise-based micro-detail and proper base material'
  },
  marketplace_readiness: {
    threshold: 4.0,
    skills: ['marketplace_product_shot', 'three_point_product_lighting', 'camera_depth_of_field'],
    phase: 'camera',
    reason: 'Not marketplace-ready — add product photography setup'
  },
  lighting_quality: {
    threshold: 5.0,
    skills: ['hdri_environment_lighting', 'three_point_product_lighting'],
    phase: 'lighting',
    reason: 'Poor lighting quality — add HDRI + studio lights'
  },
  render_quality: {
    threshold: 5.0,
    skills: ['cycles_production_render', 'noise_reduction_three_layer'],
    phase: 'render',
    reason: 'Render quality too low — increase samples and add denoising'
  }
};

/**
 * Mechanical failure → skill recommendation map
 */
const MECHANICAL_SKILL_MAP = {
  wall_thickness: {
    threshold: 70, // pass rate percent
    skills: ['wall_thickness_enforcer'],
    phase: 'prevalidate',
    priority: 'critical'
  },
  manifold: {
    threshold: 85,
    skills: ['boolean_cleanup', 'scene_cleanup'],
    phase: 'prevalidate',
    priority: 'critical'
  },
  bounding_box: {
    threshold: 70,
    skills: ['scale_normalizer', 'proportion_reference_check'],
    phase: 'prevalidate',
    priority: 'high'
  },
  degenerate_faces: {
    threshold: 90,
    skills: ['boolean_cleanup', 'scene_cleanup'],
    phase: 'prevalidate',
    priority: 'medium'
  }
};

class SkillLearningLoop {
  constructor() {
    this.metrics = null;
    this.hallOfFailures = [];
    this.existingAdjustments = {};
  }

  loadInputs() {
    // Load latest metrics
    const metricsPath = path.join(REPORTS_DIR, '3d-forge-metrics-latest.json');
    if (fs.existsSync(metricsPath)) {
      try {
        this.metrics = JSON.parse(fs.readFileSync(metricsPath, 'utf-8'));
        log(`Loaded metrics: ${this.metrics.summary?.total_assets || 0} assets`);
      } catch (e) {
        log(`Failed to parse metrics: ${e.message}`, 'warn');
      }
    } else {
      log('No metrics file found — generating from scratch', 'warn');
    }

    // Load hall-of-failures
    const hofPath = path.join(DATA_DIR, 'hall-of-failures.json');
    if (fs.existsSync(hofPath)) {
      try {
        this.hallOfFailures = JSON.parse(fs.readFileSync(hofPath, 'utf-8'));
        log(`Loaded ${this.hallOfFailures.length} failure cases`);
      } catch (e) {
        log(`Failed to parse hall-of-failures: ${e.message}`, 'warn');
      }
    }

    // Load existing adjustments (to merge/evolve, not overwrite)
    if (fs.existsSync(ADJUSTMENTS_PATH)) {
      try {
        this.existingAdjustments = JSON.parse(fs.readFileSync(ADJUSTMENTS_PATH, 'utf-8'));
        log(`Loaded existing adjustments (generation ${this.existingAdjustments.generation || 0})`);
      } catch (e) {
        this.existingAdjustments = {};
      }
    }
  }

  /**
   * Analyze visual dimension scores and generate skill recommendations
   */
  analyzeVisualDimensions() {
    const recommendations = [];

    if (!this.metrics?.visual_check_results) {
      log('No visual dimension data available', 'warn');
      return recommendations;
    }

    const visual = this.metrics.visual_check_results;

    for (const [dimension, config] of Object.entries(DIMENSION_SKILL_MAP)) {
      const score = visual[dimension];
      if (score === undefined || score === null) continue;

      if (score < config.threshold) {
        const deficit = config.threshold - score;
        recommendations.push({
          type: 'visual_dimension',
          dimension,
          current_score: score,
          target_score: config.threshold,
          deficit: Number(deficit.toFixed(2)),
          skills: config.skills,
          phase: config.phase,
          reason: config.reason,
          priority: deficit > 3 ? 'critical' : deficit > 1.5 ? 'high' : 'medium',
          action: 'ensure_included'  // Make sure these skills are in the plan
        });

        log(`Visual gap: ${dimension} = ${score}/${config.threshold} (deficit ${deficit.toFixed(1)}) → ${config.skills.join(', ')}`);
      }
    }

    return recommendations;
  }

  /**
   * Analyze mechanical check pass rates and generate skill recommendations
   */
  analyzeMechanicalFailures() {
    const recommendations = [];

    if (!this.metrics?.quality_trends?.check_pass_rates) {
      log('No mechanical check data available', 'warn');
      return recommendations;
    }

    const checks = this.metrics.quality_trends.check_pass_rates;

    for (const [checkName, config] of Object.entries(MECHANICAL_SKILL_MAP)) {
      const checkData = checks[checkName];
      if (!checkData) continue;

      if (checkData.pass_rate < config.threshold) {
        recommendations.push({
          type: 'mechanical_failure',
          check: checkName,
          current_pass_rate: checkData.pass_rate,
          target_pass_rate: config.threshold,
          skills: config.skills,
          phase: config.phase,
          priority: config.priority,
          reason: `${checkName} pass rate ${checkData.pass_rate}% < ${config.threshold}% target`,
          action: 'force_include'  // These MUST be in the plan
        });

        log(`Mechanical gap: ${checkName} = ${checkData.pass_rate}% (target ${config.threshold}%) → ${config.skills.join(', ')}`);
      }
    }

    return recommendations;
  }

  /**
   * Analyze failure patterns from hall-of-failures
   */
  analyzeFailurePatterns() {
    const recommendations = [];

    if (!this.hallOfFailures.length) return recommendations;

    // Count failure codes
    const failureCounts = {};
    for (const failure of this.hallOfFailures) {
      const code = failure.failure_code || failure.type || 'unknown';
      failureCounts[code] = (failureCounts[code] || 0) + 1;
    }

    // Top 3 most common failures
    const sorted = Object.entries(failureCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3);

    for (const [code, count] of sorted) {
      const pct = ((count / this.hallOfFailures.length) * 100).toFixed(1);

      // Map failure codes to skill recommendations
      const skillMap = {
        wall_thickness: ['wall_thickness_enforcer'],
        manifold: ['boolean_cleanup'],
        bounding_box: ['scale_normalizer'],
        degenerate_faces: ['boolean_cleanup', 'scene_cleanup'],
        VISUAL_LOW_SCORE: ['displacement_micro_detail', 'three_point_product_lighting', 'marketplace_product_shot'],
        VISUAL_NEEDS_REVISION: ['hdri_environment_lighting', 'camera_depth_of_field'],
        low_detail_level: ['subdivision_detail_pass', 'displacement_micro_detail'],
        low_material_quality: ['default_product_material', 'displacement_micro_detail'],
        low_marketplace_readiness: ['marketplace_product_shot'],
        low_proportion_accuracy: ['proportion_reference_check'],
        low_shape_accuracy: ['proportion_reference_check', 'scale_normalizer'],
        skill_planner_underutilization: [],  // Meta-failure, handled by this loop itself
      };

      const skills = skillMap[code] || [];
      if (skills.length > 0) {
        recommendations.push({
          type: 'failure_pattern',
          failure_code: code,
          occurrences: count,
          percent_of_failures: Number(pct),
          skills,
          priority: count >= 3 ? 'critical' : 'high',
          reason: `Recurring failure: ${code} (${pct}% of failures)`,
          action: 'force_include'
        });
      }
    }

    return recommendations;
  }

  /**
   * Generate category-specific overrides based on per-category performance
   */
  analyzeCategoryPerformance() {
    const overrides = {};

    if (!this.metrics?.by_category) return overrides;

    for (const [category, stats] of Object.entries(this.metrics.by_category)) {
      if (stats.avg_score < 60) {
        overrides[category] = {
          extra_skills: ['displacement_micro_detail', 'marketplace_product_shot'],
          skip_skills: [],
          reason: `Category '${category}' avg score ${stats.avg_score} < 60`
        };
      }
    }

    return overrides;
  }

  /**
   * Build the final adjustments object
   */
  buildAdjustments() {
    const visualRecs = this.analyzeVisualDimensions();
    const mechRecs = this.analyzeMechanicalFailures();
    const failureRecs = this.analyzeFailurePatterns();
    const categoryOverrides = this.analyzeCategoryPerformance();

    const allRecs = [...visualRecs, ...mechRecs, ...failureRecs];

    // Deduplicate skills across recommendations
    const forceInclude = {};  // phase → Set of skill names
    const ensureInclude = {}; // phase → Set of skill names

    for (const rec of allRecs) {
      const phase = rec.phase || 'prevalidate';
      const action = rec.action || 'ensure_included';

      if (action === 'force_include') {
        if (!forceInclude[phase]) forceInclude[phase] = new Set();
        for (const skill of rec.skills) forceInclude[phase].add(skill);
      } else {
        if (!ensureInclude[phase]) ensureInclude[phase] = new Set();
        for (const skill of rec.skills) ensureInclude[phase].add(skill);
      }
    }

    // Convert Sets to arrays
    const forceIncludeObj = {};
    for (const [phase, skills] of Object.entries(forceInclude)) {
      forceIncludeObj[phase] = Array.from(skills);
    }
    const ensureIncludeObj = {};
    for (const [phase, skills] of Object.entries(ensureInclude)) {
      ensureIncludeObj[phase] = Array.from(skills);
    }

    const generation = (this.existingAdjustments.generation || 0) + 1;

    const adjustments = {
      generated_at: new Date().toISOString(),
      generation,
      source_metrics: {
        total_assets: this.metrics?.summary?.total_assets || 0,
        pass_rate: this.metrics?.summary?.pass_rate_percent || 0,
        avg_quality_score: this.metrics?.summary?.average_quality_score || 0,
      },
      recommendations_count: allRecs.length,
      force_include: forceIncludeObj,
      ensure_include: ensureIncludeObj,
      category_overrides: categoryOverrides,
      recommendations: allRecs.map(r => ({
        type: r.type,
        target: r.dimension || r.check || r.failure_code,
        priority: r.priority,
        skills: r.skills,
        phase: r.phase,
        reason: r.reason,
      })),
      // Confidence score: higher generation + more data = more confidence
      confidence: Math.min(1.0, (generation * 0.1) + (this.metrics?.summary?.total_assets || 0) * 0.005),
    };

    return adjustments;
  }

  writeAdjustments(adjustments) {
    if (isDryRun) {
      log('DRY RUN — would write:');
      console.log(JSON.stringify(adjustments, null, 2));
      return;
    }

    fs.mkdirSync(CONFIG_DIR, { recursive: true });
    fs.writeFileSync(ADJUSTMENTS_PATH, JSON.stringify(adjustments, null, 2));
    log(`Skill plan adjustments written to ${ADJUSTMENTS_PATH} (generation ${adjustments.generation})`);
  }
}

async function runMetricsTrackerOnce() {
  const script = path.join(__dirname, 'metrics-tracker.js');
  log('No metrics file — running metrics-tracker.js...');
  await execFileAsync('node', [script], {
    cwd: REPO_ROOT,
    timeout: 180000,
    maxBuffer: 10 * 1024 * 1024,
  });
}

async function main() {
  log('=== Skill Learning Loop Starting ===');

  const loop = new SkillLearningLoop();
  loop.loadInputs();

  if (!loop.metrics) {
    try {
      await runMetricsTrackerOnce();
    } catch (e) {
      log(`metrics-tracker failed: ${e.message}`, 'warn');
    }
    loop.loadInputs();
  }

  if (!loop.metrics) {
    log('No metrics available after metrics-tracker — nothing to learn', 'warn');
    process.exit(0);
  }

  const adjustments = loop.buildAdjustments();
  loop.writeAdjustments(adjustments);

  // Summary
  log(`\n=== Learning Loop Summary ===`);
  log(`Metrics source: ${adjustments.source_metrics.total_assets} assets, ${adjustments.source_metrics.pass_rate}% pass rate`);
  log(`Recommendations: ${adjustments.recommendations_count}`);
  log(`Force-include skills: ${Object.values(adjustments.force_include).flat().length}`);
  log(`Ensure-include skills: ${Object.values(adjustments.ensure_include).flat().length}`);
  log(`Category overrides: ${Object.keys(adjustments.category_overrides).length}`);
  log(`Confidence: ${(adjustments.confidence * 100).toFixed(0)}%`);
  log(`Generation: ${adjustments.generation}`);
  log('=== Learning Loop Complete ===');
}

main().catch(err => {
  log(`Fatal error: ${err.message}`, 'error');
  process.exit(1);
});

module.exports = { SkillLearningLoop };
