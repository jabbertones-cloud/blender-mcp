#!/usr/bin/env node
/**
 * 3D Asset Metrics Tracker
 * Analyzes all validation data and generates comprehensive metrics reports
 *
 * Usage:
 *   node metrics-tracker.js [--tier learning|production|premium] [--output-dir PATH]
 */

const fs = require('fs');
const path = require('path');

class Logger {
  info(...args) {
    console.log('[metrics]', ...args);
  }
  warn(...args) {
    console.warn('[metrics:warn]', ...args);
  }
  error(...args) {
    console.error('[metrics:error]', ...args);
  }
}

const logger = new Logger();

const REPO_ROOT = path.join(__dirname, '..', '..');
const EXPORTS_DIR = path.join(REPO_ROOT, 'exports', '3d-forge');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const DATA_DIR = path.join(REPO_ROOT, 'data', '3d-forge');

// Ensure data directory exists
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

class MetricsTracker {
  constructor() {
    this.validations = [];
    this.metadataMap = {};
  }

  loadAllData() {
    if (!fs.existsSync(EXPORTS_DIR)) {
      logger.warn(`Exports directory not found: ${EXPORTS_DIR}`);
      return;
    }

    const folders = fs.readdirSync(EXPORTS_DIR).filter(f => {
      const stat = fs.statSync(path.join(EXPORTS_DIR, f));
      return stat.isDirectory();
    });

    logger.info(`Found ${folders.length} concept folders`);

    for (const folder of folders) {
      const conceptDir = path.join(EXPORTS_DIR, folder);
      const metadataPath = path.join(conceptDir, 'metadata.json');
      const validationPath = path.join(conceptDir, 'validation.json');

      // Load metadata
      if (fs.existsSync(metadataPath)) {
        try {
          const metadata = JSON.parse(fs.readFileSync(metadataPath, 'utf-8'));
          this.metadataMap[folder] = metadata;
        } catch (e) {
          logger.warn(`Failed to parse metadata: ${metadataPath}`);
        }
      }

      // Load validation
      if (fs.existsSync(validationPath)) {
        try {
          const validation = JSON.parse(fs.readFileSync(validationPath, 'utf-8'));
          this.validations.push(validation);
        } catch (e) {
          logger.warn(`Failed to parse validation: ${validationPath}`);
        }
      }
    }

    logger.info(`Loaded ${this.validations.length} validation records`);
  }

  computeMetrics() {
    const metrics = {
      timestamp: new Date().toISOString(),
      summary: {
        total_assets: this.validations.length,
        assets_passed: 0,
        assets_needs_revision: 0,
        assets_rejected: 0,
        pass_rate_percent: 0,
        average_quality_score: 0,
        average_production_time_ms: 0,
      },
      by_verdict: {
        PASS: [],
        NEEDS_REVISION: [],
        REJECT: [],
      },
      by_tier: {
        learning: { count: 0, pass: 0, avg_score: 0 },
        production: { count: 0, pass: 0, avg_score: 0 },
        premium: { count: 0, pass: 0, avg_score: 0 },
      },
      by_platform: {},
      by_category: {},
      mechanical_check_results: {},
      visual_check_results: {},
      failure_analysis: {
        most_common_failures: [],
        failure_by_phase: {},
      },
      quality_trends: {
        score_distribution: {
          '0-20': 0, '20-40': 0, '40-60': 0, '60-80': 0, '80-100': 0,
        },
        check_pass_rates: {},
      },
      improvement_suggestions: [],
    };

    if (this.validations.length === 0) {
      return metrics;
    }

    // Process each validation
    let totalScore = 0;
    let totalTime = 0;
    const failureCount = {};
    const checkResults = {};
    const visualDimensions = {
      shape_accuracy: [], proportion_accuracy: [], detail_level: [],
      material_quality: [], marketplace_readiness: [],
    };

    for (const v of this.validations) {
      // Count verdicts
      if (v.overall_verdict === 'PASS') {
        metrics.summary.assets_passed++;
        metrics.by_verdict.PASS.push(v.concept_id);
      } else if (v.overall_verdict === 'NEEDS_REVISION') {
        metrics.summary.assets_needs_revision++;
        metrics.by_verdict.NEEDS_REVISION.push(v.concept_id);
      } else {
        metrics.summary.assets_rejected++;
        metrics.by_verdict.REJECT.push(v.concept_id);
      }

      // Score accumulation
      const score = v.production_quality_score || 0;
      totalScore += score;

      // Time accumulation
      if (v.total_duration_ms) {
        totalTime += v.total_duration_ms;
      }

      // Mechanical checks
      if (v.mechanical?.checks) {
        for (const [checkName, checkResult] of Object.entries(v.mechanical.checks)) {
          if (!checkResults[checkName]) {
            checkResults[checkName] = { pass: 0, fail: 0, pass_rate: 0 };
          }
          if (checkResult.passed) {
            checkResults[checkName].pass++;
          } else {
            checkResults[checkName].fail++;
          }
        }
      }

      // Visual dimensions
      if (v.visual) {
        if (v.visual.shape_accuracy) visualDimensions.shape_accuracy.push(v.visual.shape_accuracy);
        if (v.visual.proportion_accuracy) visualDimensions.proportion_accuracy.push(v.visual.proportion_accuracy);
        if (v.visual.detail_level) visualDimensions.detail_level.push(v.visual.detail_level);
        if (v.visual.material_quality) visualDimensions.material_quality.push(v.visual.material_quality);
        if (v.visual.marketplace_readiness) visualDimensions.marketplace_readiness.push(v.visual.marketplace_readiness);
      }

      // Platform tracking
      const platform = v.metadata?.platform || 'unknown';
      if (!metrics.by_platform[platform]) {
        metrics.by_platform[platform] = { count: 0, passed: 0, avg_score: 0, scores: [] };
      }
      metrics.by_platform[platform].count++;
      if (v.overall_verdict === 'PASS') {
        metrics.by_platform[platform].passed++;
      }
      metrics.by_platform[platform].scores.push(score);

      // Failure analysis
      if (v.failure_taxonomy && Array.isArray(v.failure_taxonomy)) {
        for (const failure of v.failure_taxonomy) {
          const code = failure.failure_code;
          failureCount[code] = (failureCount[code] || 0) + 1;

          const phase = failure.phase || 'unknown';
          if (!metrics.failure_analysis.failure_by_phase[phase]) {
            metrics.failure_analysis.failure_by_phase[phase] = 0;
          }
          metrics.failure_analysis.failure_by_phase[phase]++;
        }
      }

      // Score distribution
      if (score < 20) metrics.quality_trends.score_distribution['0-20']++;
      else if (score < 40) metrics.quality_trends.score_distribution['20-40']++;
      else if (score < 60) metrics.quality_trends.score_distribution['40-60']++;
      else if (score < 80) metrics.quality_trends.score_distribution['60-80']++;
      else metrics.quality_trends.score_distribution['80-100']++;
    }

    // Finalize metrics
    metrics.summary.pass_rate_percent = Number(
      ((metrics.summary.assets_passed / this.validations.length) * 100).toFixed(2)
    );
    metrics.summary.average_quality_score = Number((totalScore / this.validations.length).toFixed(1));
    metrics.summary.average_production_time_ms = Math.round(totalTime / this.validations.length);

    // Platform stats
    for (const platform in metrics.by_platform) {
      const p = metrics.by_platform[platform];
      p.avg_score = Number((p.scores.reduce((a, b) => a + b, 0) / p.scores.length).toFixed(1));
      p.pass_rate_percent = Number(((p.passed / p.count) * 100).toFixed(1));
      delete p.scores;
    }

    // Mechanical check pass rates
    for (const checkName in checkResults) {
      const c = checkResults[checkName];
      const total = c.pass + c.fail;
      c.pass_rate = Number(((c.pass / total) * 100).toFixed(1));
    }
    metrics.quality_trends.check_pass_rates = checkResults;

    // Visual dimensions average
    const visualAvg = {};
    for (const [dim, values] of Object.entries(visualDimensions)) {
      if (values.length > 0) {
        const avg = values.reduce((a, b) => a + b, 0) / values.length;
        visualAvg[dim] = Number(avg.toFixed(2));
      }
    }
    metrics.visual_check_results = visualAvg;

    // Top failures
    const sortedFailures = Object.entries(failureCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    metrics.failure_analysis.most_common_failures = sortedFailures.map(([code, count]) => ({
      failure_code: code,
      count,
      percent_of_failures: Number(
        ((count / Object.values(failureCount).reduce((a, b) => a + b, 0)) * 100).toFixed(1)
      ),
    }));

    return metrics;
  }

  generateSuggestions(metrics) {
    const suggestions = [];

    // Pass rate
    const passRate = metrics.summary.pass_rate_percent;
    if (passRate < 10) {
      suggestions.push({
        severity: 'critical',
        message: `Pass rate is ${passRate}% — nearly all assets are failing. Review validator thresholds or generation quality.`,
      });
    } else if (passRate < 30) {
      suggestions.push({
        severity: 'high',
        message: `Pass rate is ${passRate}% — too low for production. Consider relaxing thresholds or improving generation prompts.`,
      });
    } else if (passRate > 90) {
      suggestions.push({
        severity: 'info',
        message: `Pass rate is ${passRate}% — excellent! Consider tightening thresholds for premium tier.`,
      });
    }

    // Check-specific failures
    const checkRates = metrics.quality_trends.check_pass_rates;
    for (const [checkName, stats] of Object.entries(checkRates)) {
      if (stats.pass_rate < 50) {
        suggestions.push({
          severity: 'high',
          message: `Check '${checkName}' fails ${100 - stats.pass_rate}% of the time. This is your biggest blocker.`,
          check_name: checkName,
        });
      }
    }

    // Platform analysis
    for (const [platform, stats] of Object.entries(metrics.by_platform)) {
      if (stats.pass_rate_percent < passRate - 20) {
        suggestions.push({
          severity: 'medium',
          message: `Platform '${platform}' has ${stats.pass_rate_percent}% pass rate vs ${passRate}% overall — ${platform}-specific issues detected.`,
          platform,
        });
      }
    }

    // Visual quality
    const visualAvg = metrics.visual_check_results;
    for (const [dim, score] of Object.entries(visualAvg)) {
      if (score < 5) {
        suggestions.push({
          severity: 'high',
          message: `Visual dimension '${dim}' averages ${score}/10 — very low. Focus generation improvements here.`,
          dimension: dim,
        });
      }
    }

    // Average quality score
    const avgScore = metrics.summary.average_quality_score;
    if (avgScore < 50) {
      suggestions.push({
        severity: 'critical',
        message: `Average quality score is ${avgScore}/100 — well below production standard (70+).`,
      });
    }

    return suggestions;
  }

  writeReports(metrics) {
    // Machine-readable metrics
    const latestPath = path.join(REPORTS_DIR, '3d-forge-metrics-latest.json');
    fs.writeFileSync(latestPath, JSON.stringify(metrics, null, 2));
    logger.info(`Metrics saved to ${latestPath}`);

    // Historical record (append-only)
    const historyPath = path.join(DATA_DIR, 'metrics-history.json');
    let history = [];
    if (fs.existsSync(historyPath)) {
      try {
        history = JSON.parse(fs.readFileSync(historyPath, 'utf-8'));
      } catch (e) {
        logger.warn('Could not load history, starting fresh');
        history = [];
      }
    }
    history.push(metrics);
    fs.writeFileSync(historyPath, JSON.stringify(history, null, 2));
    logger.info(`History appended to ${historyPath}`);

    // Markdown report
    const mdPath = path.join(REPORTS_DIR, '3d-forge-metrics-latest.md');
    const mdContent = this.generateMarkdownReport(metrics);
    fs.writeFileSync(mdPath, mdContent);
    logger.info(`Markdown report saved to ${mdPath}`);
  }

  generateMarkdownReport(metrics) {
    const s = metrics.summary;
    const suggestions = metrics.improvement_suggestions;

    let md = `# 3D Forge Metrics Report\n\n`;
    md += `Generated: ${metrics.timestamp}\n\n`;

    md += `## Summary\n\n`;
    md += `| Metric | Value |\n`;
    md += `|--------|-------|\n`;
    md += `| Total Assets | ${s.total_assets} |\n`;
    md += `| Passed | ${s.assets_passed} (${s.pass_rate_percent}%) |\n`;
    md += `| Needs Revision | ${s.assets_needs_revision} |\n`;
    md += `| Rejected | ${s.assets_rejected} |\n`;
    md += `| Avg Quality Score | ${s.average_quality_score}/100 |\n`;
    md += `| Avg Production Time | ${s.average_production_time_ms}ms |\n\n`;

    md += `## Platform Performance\n\n`;
    for (const [platform, stats] of Object.entries(metrics.by_platform)) {
      md += `### ${platform}\n`;
      md += `- Count: ${stats.count}\n`;
      md += `- Pass Rate: ${stats.pass_rate_percent}%\n`;
      md += `- Avg Score: ${stats.avg_score}/100\n\n`;
    }

    md += `## Mechanical Check Results\n\n`;
    const checkRates = metrics.quality_trends.check_pass_rates;
    for (const [checkName, stats] of Object.entries(checkRates)) {
      md += `- **${checkName}**: ${stats.pass_rate}% pass (${stats.pass} pass, ${stats.fail} fail)\n`;
    }
    md += `\n`;

    md += `## Visual Quality Scores\n\n`;
    for (const [dim, score] of Object.entries(metrics.visual_check_results)) {
      md += `- **${dim}**: ${score}/10\n`;
    }
    md += `\n`;

    if (suggestions && suggestions.length > 0) {
      md += `## Improvement Suggestions\n\n`;
      for (const sugg of suggestions) {
        const severity = sugg.severity.toUpperCase();
        md += `### [${severity}] ${sugg.message}\n\n`;
      }
    }

    md += `## Score Distribution\n\n`;
    const dist = metrics.quality_trends.score_distribution;
    md += `\`\`\`\n`;
    md += `0-20:   ${this.bar(dist['0-20'], 50)}\n`;
    md += `20-40:  ${this.bar(dist['20-40'], 50)}\n`;
    md += `40-60:  ${this.bar(dist['40-60'], 50)}\n`;
    md += `60-80:  ${this.bar(dist['60-80'], 50)}\n`;
    md += `80-100: ${this.bar(dist['80-100'], 50)}\n`;
    md += `\`\`\`\n`;

    return md;
  }

  bar(count, maxWidth) {
    const width = Math.min(maxWidth, count * 2);
    return '█'.repeat(width) + ` (${count})`;
  }
}

async function main() {
  try {
    const tracker = new MetricsTracker();
    tracker.loadAllData();

    const metrics = tracker.computeMetrics();
    metrics.improvement_suggestions = tracker.generateSuggestions(metrics);

    tracker.writeReports(metrics);

    logger.info(`\nMetrics Summary:`);
    logger.info(`  Total Assets: ${metrics.summary.total_assets}`);
    logger.info(`  Pass Rate: ${metrics.summary.pass_rate_percent}%`);
    logger.info(`  Avg Quality Score: ${metrics.summary.average_quality_score}/100`);
    logger.info(`  Suggestions Generated: ${metrics.improvement_suggestions.length}`);
  } catch (err) {
    logger.error(`Fatal error: ${err.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { MetricsTracker };
