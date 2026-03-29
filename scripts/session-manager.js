#!/usr/bin/env node
/**
 * Session Manager for Blender Forensic Pipeline
 * Manages checkpoint state, prioritizes improvements, and tracks progress
 */

const fs = require('fs');
const path = require('path');

const CHECKPOINT_PATH = path.join(__dirname, '../data/session_checkpoint.json');
const IMPROVEMENT_PLAN_PATH = path.join(__dirname, '../data/improvement_plan.json');

class SessionManager {
  constructor() {
    this.checkpoint = null;
    this.improvementPlan = null;
    this.loadCheckpoint();
    this.loadImprovementPlan();
  }

  /**
   * Load and parse session checkpoint from disk
   */
  loadCheckpoint() {
    try {
      const raw = fs.readFileSync(CHECKPOINT_PATH, 'utf8');
      this.checkpoint = JSON.parse(raw);
      console.log(`[SessionManager] Loaded checkpoint - Run #${this.checkpoint.run_count}, Best score: ${this.checkpoint.best_overall_score}`);
    } catch (err) {
      console.error(`[SessionManager] Failed to load checkpoint: ${err.message}`);
      process.exit(1);
    }
  }

  /**
   * Load improvement plan
   */
  loadImprovementPlan() {
    try {
      const raw = fs.readFileSync(IMPROVEMENT_PLAN_PATH, 'utf8');
      this.improvementPlan = JSON.parse(raw);
      console.log(`[SessionManager] Loaded improvement plan - Phase: ${this.improvementPlan.current_phase_progress.phase}`);
    } catch (err) {
      console.error(`[SessionManager] Failed to load improvement plan: ${err.message}`);
      process.exit(1);
    }
  }

  /**
   * Determine the next action based on current state
   * Returns { type, priority, details }
   */
  getNextAction() {
    const phase = this.improvementPlan.current_phase_progress;
    const problems = this.checkpoint.known_problems.filter(p => !p.fix_attempted);
    
    // Critical blocking issues take highest priority
    if (problems.some(p => p.id === 'SCENE4_BLANK' && p.severity === 'critical')) {
      return {
        type: 'fix_scene',
        priority: 'critical',
        details: {
          problem: 'SCENE4_BLANK',
          target: 'scene4_parking',
          action: 'Apply night-scene lighting setup with area lights and HDRI',
          expectedGain: '+40_score_points'
        }
      };
    }

    if (problems.some(p => p.id === 'LOW_CONTRAST_POV' && p.severity === 'high')) {
      return {
        type: 'fix_scene',
        priority: 'high',
        details: {
          problem: 'LOW_CONTRAST_POV',
          targets: ['scene1_tbone', 'scene2_pedestrian', 'scene3_highway'],
          action: 'Increase key light intensity and add fill lights to POV/Wide angles',
          expectedGain: '+25_score_per_angle'
        }
      };
    }

    // If in foundation phase and still have low-scoring renders
    if (phase.phase === 'foundation' && phase.renders_above_50 < phase.renders_total) {
      return {
        type: 'fix_scene',
        priority: 'high',
        details: {
          action: 'Systematically boost all renders above 50/100 baseline',
          low_scorers: this.getLowScoringRenders(50),
          approach: 'Apply proven 3_point_area_lighting technique'
        }
      };
    }

    // Learning opportunity if problems are solved
    const nextSkill = this.checkpoint.youtube_skill_progress.skills_in_progress[0] ||
                      this.checkpoint.youtube_skill_progress.skills_queued[0];
    
    if (nextSkill) {
      return {
        type: 'learn_skill',
        priority: 'medium',
        details: {
          skill: nextSkill,
          source: this.checkpoint.youtube_skill_progress.next_tutorial,
          estimatedDuration: '45_minutes',
          expectedGain: '+15_score_after_practice'
        }
      };
    }

    return {
      type: 'research',
      priority: 'low',
      details: {
        focus: 'Investigate next phase improvements',
        suggestions: this.checkpoint.next_priorities.slice(0, 2)
      }
    };
  }

  /**
   * Get all renders scoring below threshold
   */
  getLowScoringRenders(threshold = 50) {
    const scores = this.checkpoint.v11_render_scores;
    return Object.entries(scores)
      .filter(([_, score]) => score < threshold)
      .map(([key, score]) => ({ render: key, score }))
      .sort((a, b) => a.score - b.score);
  }

  /**
   * Calculate improvement velocity (score change per run)
   */
  getScoreTrend() {
    const history = this.checkpoint.score_history;
    if (history.length < 2) return null;

    const recent = history.slice(-2);
    const prev = recent[0].score;
    const curr = recent[1].score;

    // Skip if no actual score yet
    if (!prev || !curr) return null;

    const delta = curr - prev;
    const velocity = delta > 0 ? 'improving' : delta < 0 ? 'degrading' : 'stable';
    
    return {
      previousScore: prev,
      currentScore: curr,
      delta: delta.toFixed(2),
      velocity: velocity,
      improvement_percent: ((delta / prev) * 100).toFixed(1)
    };
  }

  /**
   * Update checkpoint after a run completes
   */
  updateCheckpoint(results) {
    // Increment run count
    this.checkpoint.run_count += 1;
    this.checkpoint.last_run = new Date().toISOString();
    this.checkpoint.current_version = results.version || this.checkpoint.current_version;

    // Update render scores if provided
    if (results.render_scores) {
      this.checkpoint.v11_render_scores = {
        ...this.checkpoint.v11_render_scores,
        ...results.render_scores
      };
    }

    // Update overall best score
    if (results.overall_score && results.overall_score > this.checkpoint.best_overall_score) {
      this.checkpoint.best_overall_score = results.overall_score;
    }

    // Mark problems as fixed if applicable
    if (results.problems_fixed && Array.isArray(results.problems_fixed)) {
      results.problems_fixed.forEach(problemId => {
        const problem = this.checkpoint.known_problems.find(p => p.id === problemId);
        if (problem) {
          problem.fix_attempted = true;
        }
      });
    }

    // Add new proven techniques
    if (results.new_techniques && Array.isArray(results.new_techniques)) {
      this.checkpoint.proven_techniques.push(...results.new_techniques);
    }

    // Add to score history
    if (results.overall_score !== undefined) {
      this.checkpoint.score_history.push({
        version: this.checkpoint.current_version,
        score: results.overall_score,
        date: new Date().toISOString().split('T')[0]
      });
    }

    // Save updated checkpoint
    this.saveCheckpoint();
  }

  /**
   * Save checkpoint to disk
   */
  saveCheckpoint() {
    try {
      fs.writeFileSync(
        CHECKPOINT_PATH,
        JSON.stringify(this.checkpoint, null, 2),
        'utf8'
      );
      console.log(`[SessionManager] Checkpoint saved - Run #${this.checkpoint.run_count}`);
    } catch (err) {
      console.error(`[SessionManager] Failed to save checkpoint: ${err.message}`);
    }
  }

  /**
   * Export summary for debugging
   */
  getSummary() {
    return {
      runCount: this.checkpoint.run_count,
      bestScore: this.checkpoint.best_overall_score,
      currentVersion: this.checkpoint.current_version,
      trend: this.getScoreTrend(),
      nextAction: this.getNextAction(),
      blockers: this.checkpoint.known_problems.filter(p => !p.fix_attempted)
    };
  }
}

module.exports = SessionManager;

// CLI usage
if (require.main === module) {
  const manager = new SessionManager();
  const summary = manager.getSummary();
  console.log('\n[SessionManager] Current State:');
  console.log(JSON.stringify(summary, null, 2));
}