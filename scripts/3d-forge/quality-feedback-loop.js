#!/usr/bin/env node

/**
 * Quality Feedback Loop: Prompt Refinement Engine
 * 
 * Reads autoresearch reports, identifies patterns in failures, and generates
 * specific prompt refinements that concept-generator.js reads on next run.
 * 
 * This is the CRITICAL missing piece that closes the learning loop:
 * autoresearch-agent detects patterns → quality-feedback-loop refines prompts
 * → concept-generator reads refinements → next batch learns from previous mistakes
 * 
 * CLI: node quality-feedback-loop.js [--dry-run] [--verbose]
 * 
 * Output:
 *   config/3d-forge/prompt-refinements.json (read by concept-generator)
 *   reports/3d-forge-feedback-loop-latest.json (audit trail)
 */

const fs = require('fs');
const path = require('path');

// Load .env
require('./lib/env').loadEnv();

// Configuration
const REPO_ROOT = path.join(__dirname, '../../');
const CONFIG_DIR = path.join(REPO_ROOT, 'config/3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const DATA_DIR = path.join(REPO_ROOT, 'data/3d-forge');

// Key paths
const AUTORESEARCH_REPORT_PATH = path.join(REPORTS_DIR, '3d-forge-autoresearch-latest.json');
const AUTORESEARCH_STATE_PATH = path.join(CONFIG_DIR, 'autoresearch-state.json');
const FAILURE_TAXONOMY_PATH = path.join(CONFIG_DIR, 'failure-taxonomy.json');
const PROMPT_PATTERNS_PATH = path.join(CONFIG_DIR, 'prompt-patterns.json');
const PROMPT_REFINEMENTS_PATH = path.join(CONFIG_DIR, 'prompt-refinements.json');
const FEEDBACK_LOOP_REPORT_PATH = path.join(REPORTS_DIR, '3d-forge-feedback-loop-latest.json');
const CONCEPT_TEMPLATES_PATH = path.join(CONFIG_DIR, 'concept-templates.json');

// Parse CLI args
const args = process.argv.slice(2);
const isDryRun = args.includes('--dry-run');
const isVerbose = args.includes('--verbose');

// ============================================================================
// UTILITIES
// ============================================================================

function log(msg, level = 'INFO') {
  const ts = new Date().toISOString();
  console.log(`[${ts}] [${level}] ${msg}`);
}

function vlog(msg) {
  if (isVerbose) log(msg, 'DEBUG');
}

function loadJson(filePath, fallback = {}) {
  try {
    if (!fs.existsSync(filePath)) {
      vlog(`File not found: ${filePath}`);
      return fallback;
    }
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch (err) {
    log(`Failed to parse ${filePath}: ${err.message}`, 'WARN');
    return fallback;
  }
}

function saveJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  if (!isDryRun) {
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    log(`Saved: ${filePath}`);
  } else {
    log(`[DRY-RUN] Would save: ${filePath}`);
  }
}

// ============================================================================
// CORE ANALYSIS
// ============================================================================

class QualityFeedbackLoop {
  constructor() {
    this.autoresearchReport = loadJson(AUTORESEARCH_REPORT_PATH);
    this.autoresearchState = loadJson(AUTORESEARCH_STATE_PATH);
    this.failureTaxonomy = loadJson(FAILURE_TAXONOMY_PATH);
    this.promptPatterns = loadJson(PROMPT_PATTERNS_PATH);
    this.conceptTemplates = loadJson(CONCEPT_TEMPLATES_PATH);
    
    this.refinements = {
      generated_at: new Date().toISOString(),
      applied_to_next_run: false,
      analysis: {},
      prompt_improvements: [],
      blocked_patterns: [],
      enhanced_constraints: [],
      material_specs: [],
      lighting_improvements: [],
      geometry_guardrails: [],
    };
  }

  /**
   * Analyze recurring issues from autoresearch report
   */
  analyzeRecurringIssues() {
    vlog('Analyzing recurring issues...');
    const issues = this.autoresearchReport.recurring_issues || [];
    const taxonomy = this.failureTaxonomy?.failure_codes || {};
    
    const analysis = {
      total_issues: issues.length,
      by_frequency: {},
      by_fix_category: {},
      by_severity: {},
    };

    for (const issue of issues) {
      const freq = (issue.frequency || 0).toFixed(2);
      const category = this.categorizeFix(issue.issue);
      const severity = this.determineSeverity(issue.issue);

      analysis.by_frequency[issue.issue] = {
        frequency: freq,
        count: issue.count || 1,
        category,
        severity,
        suggested_fix: issue.suggested_fix,
      };

      // Group by category
      if (!analysis.by_fix_category[category]) {
        analysis.by_fix_category[category] = [];
      }
      analysis.by_fix_category[category].push({
        issue: issue.issue,
        frequency: freq,
        fix: issue.suggested_fix,
      });

      // Group by severity
      if (!analysis.by_severity[severity]) {
        analysis.by_severity[severity] = [];
      }
      analysis.by_severity[severity].push(issue.issue);
    }

    this.refinements.analysis = analysis;
    return analysis;
  }

  /**
   * Categorize fix by type
   */
  categorizeFix(issue) {
    const lower = issue.toLowerCase();
    if (lower.includes('reference') || lower.includes('image')) return 'reference_quality';
    if (lower.includes('geometry') || lower.includes('detail') || lower.includes('topology')) return 'geometry_detail';
    if (lower.includes('material') || lower.includes('texture') || lower.includes('surface')) return 'material_surface';
    if (lower.includes('lighting') || lower.includes('render')) return 'lighting_render';
    if (lower.includes('position') || lower.includes('placement') || lower.includes('center')) return 'spatial_placement';
    if (lower.includes('edge') || lower.includes('bevel') || lower.includes('chamfer')) return 'edge_definition';
    return 'general';
  }

  /**
   * Determine severity (critical > high > medium > low)
   */
  determineSeverity(issue) {
    const lower = issue.toLowerCase();
    if (lower.includes('missing') || lower.includes('absent') || lower.includes('no ')) return 'critical';
    if (lower.includes('inconsistent') || lower.includes('varies')) return 'high';
    if (lower.includes('minimal') || lower.includes('lacks')) return 'medium';
    return 'low';
  }

  /**
   * Identify problematic Blender steps
   */
  analyzeProblematicSteps() {
    vlog('Analyzing problematic steps...');
    
    const stepPatterns = this.autoresearchReport.step_patterns || {};
    const problematicSteps = stepPatterns.problematic_steps || [];

    const blocked = [];
    const improved = [];

    for (const stepInfo of problematicSteps) {
      const step = stepInfo.step;
      const successRate = Number(stepInfo.success_rate || 0);

      // If a step fails >50% of the time, it's not reliable for prompts
      if (successRate < 50) {
        blocked.push({
          step,
          success_rate: successRate,
          reason: 'Too unreliable for general use',
          recommendation: 'Remove from concept prompt; use fallback step if critical',
        });
      } else if (successRate < 80) {
        improved.push({
          step,
          success_rate: successRate,
          reason: 'Below target threshold',
          recommendation: 'Tighten error handling; add validation step',
        });
      }
    }

    this.refinements.blocked_patterns = blocked;
    return { blocked, improved };
  }

  /**
   * Extract and enhance constraints from issues
   */
  analyzeConstraints() {
    vlog('Analyzing geometry/visual constraints...');
    
    const issues = this.autoresearchReport.recurring_issues || [];
    const constraints = [];

    // Map common issues to guardrails
    const issuePatterns = {
      'sphere positioning': {
        category: 'spatial',
        constraint: 'Position primary object at scene center (0, 0, 0). Use consistent reference frame.',
        prompt_text: 'Position the sphere at the exact center of the platform (use 0,0,0 in Blender). Ensure sphere is tangent to platform surface, not clipping or floating.',
      },
      'platform edge definition': {
        category: 'geometry',
        constraint: 'Add beveled edges to platforms (Bevel modifier, 0.1-0.2 strength). Ensure hard edges are chamfered.',
        prompt_text: 'After creating the flat platform, apply a Bevel modifier with strength 0.15mm to all edges for professional appearance.',
      },
      'surface detail': {
        category: 'geometry',
        constraint: 'Minimum 3 edge loops per major surface. No flat featureless planes.',
        prompt_text: 'Add surface detail using EdgeLoops. Every flat surface must have at least 2-3 subdivisions to prevent boring appearance.',
      },
      'material variation': {
        category: 'material',
        constraint: 'No solid flat colors. Use at least 2-3 material zones with different roughness.',
        prompt_text: 'Apply at least 2 different materials: one with roughness 0.2-0.4 (metal/gloss), one with 0.6-0.8 (matte). Mix on same object.',
      },
      'reference images': {
        category: 'inputs',
        constraint: 'Request minimum 4 reference images per concept. Reject single-angle or unclear references.',
        prompt_text: 'Use reference images showing: front, side, top, and detail views. Each reference must be at least 800px and well-lit.',
      },
      'wall thickness': {
        category: 'geometry',
        constraint: 'Minimum 1.5mm wall thickness everywhere. Measure in Blender using Volume/SurfaceArea ratio.',
        prompt_text: 'Ensure all walls are at least 1.5mm thick for 3D printing. Use Solidify modifier if creating shells.',
      },
      'lighting consistency': {
        category: 'render',
        constraint: 'Use 3-point lighting for all renders. Key:2.0, Fill:1.0, Rim:1.5 energy.',
        prompt_text: 'Set up 3-point lighting before renders: Key light at 45° (energy 2.0), Fill light opposite (1.0), Rim light back (1.5).',
      },
    };

    for (const issue of issues) {
      const lower = issue.issue.toLowerCase();
      for (const [pattern, detail] of Object.entries(issuePatterns)) {
        if (lower.includes(pattern.toLowerCase())) {
          constraints.push({
            issue: issue.issue,
            category: detail.category,
            constraint: detail.constraint,
            prompt_enhancement: detail.prompt_text,
            frequency: issue.frequency || 0,
          });
        }
      }
    }

    this.refinements.enhanced_constraints = constraints;
    return constraints;
  }

  /**
   * Generate material specifications from visual issues
   */
  generateMaterialSpecs() {
    vlog('Generating material specifications...');
    
    const visual = this.autoresearchReport.kpis?.visual_quality_avg || 0;
    const specs = [];

    // Base specs that apply to all runs
    const baseSpecs = [
      {
        name: 'primary_surface',
        use_case: 'Main object body/shell',
        metallic: 0.0,
        roughness: 0.3,
        ior: 1.5,
        subsurface_weight: 0.0,
        note: 'Matte finish with slight specularity for readability',
      },
      {
        name: 'accent_material',
        use_case: 'Detail areas, edges, inlays',
        metallic: 0.7,
        roughness: 0.2,
        ior: 1.5,
        subsurface_weight: 0.0,
        note: 'Metallic for visual interest and contrast',
      },
      {
        name: 'platform_surface',
        use_case: 'Base, supports, flat surfaces',
        metallic: 0.0,
        roughness: 0.6,
        ior: 1.5,
        subsurface_weight: 0.0,
        note: 'Matte platform for visual separation',
      },
    ];

    // Adjust if quality is low
    if (visual < 5.0) {
      specs.push({
        name: 'quality_boost',
        reason: 'Visual quality is low, increase detail and variation',
        adjustments: [
          'Add normal maps to all surfaces',
          'Use procedural textures for micro-detail',
          'Increase specularity for product-like appearance',
          'Add slight subsurface scattering to organic shapes',
        ],
      });
    }

    // Add color palette guidance
    specs.push({
      name: 'color_palette',
      guidance: 'Use high-contrast color scheme for marketplace appeal',
      recommendations: [
        'Primary color: dark or saturated (avoid grey)',
        'Secondary color: light or complementary',
        'Accent color: bright for details (optional)',
        'Avoid pure white/black unless essential',
      ],
    });

    this.refinements.material_specs = [...baseSpecs, ...specs];
    return specs;
  }

  /**
   * Generate lighting improvements from failure patterns
   */
  generateLightingImprovements() {
    vlog('Generating lighting improvements...');
    
    const topErrors = this.autoresearchReport.step_patterns?.top_errors || [];
    const improvements = [];

    // Check for render-related errors
    const renderErrors = topErrors.filter(e => 
      e.affected_steps.some(s => s.includes('render'))
    );

    if (renderErrors.length > 0) {
      improvements.push({
        issue: 'Render failures detected',
        improvement: 'Enable 3-point lighting setup before all renders',
        implementation: {
          step: 'setup_3point_lighting',
          parameters: {
            key_light: { type: 'SUN', energy: 2.0, angle: 45 },
            fill_light: { type: 'SUN', energy: 1.0, angle: 180 },
            rim_light: { type: 'SUN', energy: 1.5, angle: 270 },
            world_strength: 0.5,
            samples: 128,
            use_motion_blur: false,
          },
        },
      });

      improvements.push({
        issue: 'Multiple render angles needed',
        improvement: 'Render from standard viewpoints (hero, front, side, top, detail)',
        implementation: {
          angles: [
            { name: 'hero', rotation: '45° azimuth, 30° elevation', focus: 'primary subject' },
            { name: 'front', rotation: '0° azimuth, 0° elevation', focus: 'frontal detail' },
            { name: 'side', rotation: '90° azimuth, 0° elevation', focus: 'profile' },
            { name: 'top', rotation: 'overhead', focus: 'top surface detail' },
            { name: 'detail', rotation: 'macro 1:1', focus: 'fine surface features' },
          ],
        },
      });
    }

    this.refinements.lighting_improvements = improvements;
    return improvements;
  }

  /**
   * Generate geometry guardrails
   */
  generateGeometryGuardrails() {
    vlog('Generating geometry guardrails...');
    
    const mechanicalChecks = this.autoresearchState?.mechanical_check_breakdown || {};
    const guardrails = [];

    // If any mechanical check is failing, add guardrails
    for (const [checkType, data] of Object.entries(mechanicalChecks)) {
      const passRate = Number(data.pass_rate || 100);
      if (passRate < 100) {
        guardrails.push({
          check: checkType,
          pass_rate: passRate,
          requirement: this.getCheckRequirement(checkType),
          enforcement: this.getCheckEnforcement(checkType),
          validation_step: `validate_${checkType}`,
        });
      }
    }

    // Add general geometry rules
    guardrails.push({
      check: 'manifold_surface',
      requirement: 'All meshes must be watertight (manifold)',
      enforcement: 'After geometry creation, run Mesh → Clean Up → Remove Doubles, then check for non-manifold edges',
      validation_step: 'check_manifold',
    });

    guardrails.push({
      check: 'no_loose_geometry',
      requirement: 'No floating vertices or disconnected edges',
      enforcement: 'Select All, Mesh → Clean Up → Delete Loose. Verify edge count decreases.',
      validation_step: 'check_loose_verts',
    });

    guardrails.push({
      check: 'sensible_scale',
      requirement: 'Object bounding box within 10mm-500mm range (real-world scale)',
      enforcement: 'Use Blender\'s dimension tool. If too small, scale up; if huge, scale down.',
      validation_step: 'check_bounding_box',
    });

    this.refinements.geometry_guardrails = guardrails;
    return guardrails;
  }

  getCheckRequirement(checkType) {
    const reqs = {
      manifold: 'Surface is topologically correct, no holes or inverted normals',
      tri_count: 'Triangle count within budget (Roblox: 4k, Game: 50k, STL: unlimited)',
      loose_verts: 'No disconnected geometry floating in space',
      degenerate_faces: 'No zero-area faces, all faces have valid normal',
      wall_thickness: 'All walls at least 1.5mm thick (for 3D print)',
      bounding_box: 'Model fits within reasonable dimensions for export format',
    };
    return reqs[checkType] || 'Geometry quality check';
  }

  getCheckEnforcement(checkType) {
    const enforcement = {
      manifold: 'Run Mesh → Clean Up, verify non-manifold edge count = 0',
      tri_count: 'Run Modifier → Decimate if needed, target ratio = budget/current_count',
      loose_verts: 'Select All, Mesh → Clean Up → Delete Loose',
      degenerate_faces: 'Mesh → Cleanup → Degenerate Faces. Face count should not increase.',
      wall_thickness: 'Use modifiers: Solidify or Boolean with proper thickness',
      bounding_box: 'Check Object Properties → Dimensions; scale if needed',
    };
    return enforcement[checkType] || 'Run validation check';
  }

  /**
   * Generate prompt improvements based on all analysis
   */
  generatePromptImprovements() {
    vlog('Generating prompt improvements...');
    
    const improvements = [];
    const analysis = this.refinements.analysis || {};
    const constraints = this.refinements.enhanced_constraints || [];
    const guardrails = this.refinements.geometry_guardrails || [];

    // Improvement 1: Add constraint preamble
    if (constraints.length > 0) {
      const constraintText = constraints
        .map(c => `• ${c.constraint}`)
        .join('\n');
      
      improvements.push({
        type: 'add_constraint_section',
        position: 'after_concept_description',
        content: `MANDATORY CONSTRAINTS:\n${constraintText}\n`,
        rationale: 'Previous runs had constraint violations; make them explicit',
      });
    }

    // Improvement 2: Add reference image guidance
    const refIssues = analysis.by_fix_category?.reference_quality || [];
    if (refIssues.length > 0) {
      improvements.push({
        type: 'add_input_guidance',
        position: 'before_generation',
        content: `REQUEST REFERENCE IMAGES:\n- Front, side, top, and detail views\n- Minimum 4 angles, each 800px+\n- Well-lit, clear focus\n- Show material and finish\n`,
        rationale: 'Reference quality issues detected in recurring failures',
      });
    }

    // Improvement 3: Add geometry guardrails
    if (guardrails.length > 0) {
      const guardrailText = guardrails
        .slice(0, 3)
        .map(g => `• ${g.requirement}`)
        .join('\n');
      
      improvements.push({
        type: 'add_geometry_guardrails',
        position: 'before_blender_steps',
        content: `GEOMETRY GUARDRAILS:\n${guardrailText}\nVerify each step produces clean, watertight geometry.\n`,
        rationale: 'Mechanical validation failures reduced by enforcing geometry rules',
      });
    }

    // Improvement 4: Add material spec section
    const materialSpecs = this.refinements.material_specs || [];
    if (materialSpecs.length > 0) {
      const specs = materialSpecs.filter(s => !s.reason).slice(0, 2);
      const specText = specs
        .map(s => `${s.name}: Metallic ${s.metallic}, Roughness ${s.roughness}`)
        .join('\n');
      
      improvements.push({
        type: 'add_material_specs',
        position: 'in_materials_step',
        content: `MATERIAL SPECIFICATIONS:\n${specText}\nApply at least 2 materials for visual variety.\n`,
        rationale: 'Material variety improves visual scores',
      });
    }

    // Improvement 5: Add lighting setup
    const lightingImprovements = this.refinements.lighting_improvements || [];
    if (lightingImprovements.length > 0) {
      improvements.push({
        type: 'add_lighting_setup',
        position: 'before_renders',
        content: `LIGHTING SETUP:\n- Key light: 45° angle, 2.0 energy\n- Fill light: 180° angle, 1.0 energy\n- Rim light: 270° angle, 1.5 energy\n- World background: 0.5 strength\n- Samples: 128+\n`,
        rationale: 'Standardized lighting reduces render quality variance',
      });
    }

    this.refinements.prompt_improvements = improvements;
    return improvements;
  }

  /**
   * Build the final refinements config
   */
  buildRefinementsConfig() {
    vlog('Building refinements config...');

    // Analyze all aspects
    this.analyzeRecurringIssues();
    this.analyzeProblematicSteps();
    this.analyzeConstraints();
    this.generateMaterialSpecs();
    this.generateLightingImprovements();
    this.generateGeometryGuardrails();
    this.generatePromptImprovements();

    // Add metadata
    this.refinements.version = '1.0';
    this.refinements.based_on_report = path.basename(AUTORESEARCH_REPORT_PATH);
    this.refinements.run_number = this.autoresearchReport.run_number || 0;
    this.refinements.kpis_snapshot = {
      production_quality_score_avg: this.autoresearchReport.kpis?.production_quality_score_avg,
      visual_quality_avg: this.autoresearchReport.kpis?.visual_quality_avg,
      mechanical_pass_rate: this.autoresearchReport.kpis?.mechanical_pass_rate,
    };

    return this.refinements;
  }

  /**
   * Apply refinements: save to config that concept-generator reads
   */
  applyRefinements() {
    vlog('Applying refinements...');

    const config = this.buildRefinementsConfig();

    // Save the refinements config
    saveJson(PROMPT_REFINEMENTS_PATH, config);

    // Also update the state file to mark that refinements were applied
    const state = loadJson(AUTORESEARCH_STATE_PATH);
    state.last_feedback_loop = new Date().toISOString();
    state.last_refinements_applied = config.prompt_improvements.length;
    saveJson(AUTORESEARCH_STATE_PATH, state);

    // Generate audit report
    const auditReport = {
      generated_at: new Date().toISOString(),
      based_on_report: path.basename(AUTORESEARCH_REPORT_PATH),
      status: isDryRun ? 'dry_run' : 'applied',
      summary: {
        issues_analyzed: config.analysis.total_issues,
        blocked_patterns: config.blocked_patterns.length,
        constraints_added: config.enhanced_constraints.length,
        prompt_improvements: config.prompt_improvements.length,
        guardrails_defined: config.geometry_guardrails.length,
      },
      refinements_config_path: PROMPT_REFINEMENTS_PATH,
      next_steps: [
        'concept-generator.js will read prompt-refinements.json on next run',
        'Improved prompts will incorporate all identified constraints',
        'Monitor next batch for quality improvements',
        'Iterate: autoresearch → feedback-loop → concept-generator',
      ],
    };

    saveJson(FEEDBACK_LOOP_REPORT_PATH, auditReport);

    log(`Quality feedback loop completed. ${config.prompt_improvements.length} improvements generated.`);
    return auditReport;
  }
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  try {
    log('=== Quality Feedback Loop Starting ===');
    
    // Check if autoresearch report exists
    if (!fs.existsSync(AUTORESEARCH_REPORT_PATH)) {
      log(`Autoresearch report not found at ${AUTORESEARCH_REPORT_PATH}`, 'WARN');
      log('Run autoresearch-agent.js first to generate baseline analysis.');
      process.exit(1);
    }

    const loop = new QualityFeedbackLoop();
    const auditReport = loop.applyRefinements();

    // Print summary
    log('\n=== Feedback Loop Summary ===');
    log(`Issues analyzed: ${auditReport.summary.issues_analyzed}`);
    log(`Blocked patterns: ${auditReport.summary.blocked_patterns}`);
    log(`Constraints added: ${auditReport.summary.constraints_added}`);
    log(`Prompt improvements: ${auditReport.summary.prompt_improvements}`);
    log(`Guardrails defined: ${auditReport.summary.guardrails_defined}`);
    
    log('\n=== Next Steps ===');
    auditReport.next_steps.forEach(step => log(`  → ${step}`));

    if (isDryRun) {
      log('\n[DRY-RUN] No files were actually written. Run without --dry-run to apply.', 'INFO');
    }

    log('=== Quality Feedback Loop Complete ===');
  } catch (error) {
    log(`Fatal error: ${error.message}`, 'ERROR');
    if (isVerbose) console.error(error);
    process.exit(1);
  }
}

if (require.main === module) {
  main().catch(err => {
    log(`Unhandled error: ${err.message}`, 'ERROR');
    process.exit(1);
  });
}

module.exports = { QualityFeedbackLoop };
