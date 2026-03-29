#!/usr/bin/env node
/**
 * 3D Asset Quality Dashboard Generator
 * Creates an interactive HTML dashboard from metrics data
 *
 * Usage:
 *   node quality-dashboard.js [--metrics-file PATH] [--output-file PATH]
 */

const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.join(__dirname, '..', '..');
const REPORTS_DIR = path.join(REPO_ROOT, 'reports');
const DEFAULT_METRICS_FILE = path.join(REPORTS_DIR, '3d-forge-metrics-latest.json');
const DEFAULT_OUTPUT_FILE = path.join(REPORTS_DIR, '3d-forge-dashboard.html');

class DashboardGenerator {
  constructor(metricsFile) {
    this.metricsFile = metricsFile;
    this.metrics = null;
  }

  loadMetrics() {
    if (!fs.existsSync(this.metricsFile)) {
      throw new Error(`Metrics file not found: ${this.metricsFile}`);
    }
    this.metrics = JSON.parse(fs.readFileSync(this.metricsFile, 'utf-8'));
  }

  generateHTML() {
    if (!this.metrics) {
      throw new Error('Metrics not loaded');
    }

    const m = this.metrics;
    const s = m.summary;

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>3D Forge Quality Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js"></script>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      margin: 0;
      padding: 20px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
    }
    .container {
      max-width: 1400px;
      margin: 0 auto;
    }
    h1 {
      color: white;
      text-align: center;
      margin-bottom: 10px;
    }
    .timestamp {
      color: rgba(255,255,255,0.8);
      text-align: center;
      font-size: 12px;
      margin-bottom: 30px;
    }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 20px;
      margin-bottom: 30px;
    }
    .kpi-card {
      background: white;
      border-radius: 12px;
      padding: 25px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      transition: transform 0.2s, box-shadow 0.2s;
    }
    .kpi-card:hover {
      transform: translateY(-5px);
      box-shadow: 0 15px 40px rgba(0,0,0,0.3);
    }
    .kpi-label {
      font-size: 12px;
      color: #666;
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 10px;
    }
    .kpi-value {
      font-size: 42px;
      font-weight: bold;
      color: #333;
      line-height: 1;
      margin-bottom: 5px;
    }
    .kpi-unit {
      font-size: 14px;
      color: #999;
    }
    .kpi-subtext {
      font-size: 12px;
      color: #999;
      margin-top: 8px;
    }
    .charts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
      gap: 20px;
      margin-bottom: 30px;
    }
    .chart-card {
      background: white;
      border-radius: 12px;
      padding: 25px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    .chart-title {
      font-size: 18px;
      font-weight: 600;
      color: #333;
      margin-bottom: 20px;
    }
    canvas {
      max-height: 300px;
    }
    .table-card {
      background: white;
      border-radius: 12px;
      padding: 25px;
      box-shadow: 0 10px 30px rgba(0,0,0,0.2);
      margin-bottom: 30px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th {
      background: #f5f5f5;
      padding: 15px;
      text-align: left;
      font-weight: 600;
      font-size: 12px;
      text-transform: uppercase;
      color: #666;
      border-bottom: 2px solid #eee;
    }
    td {
      padding: 12px 15px;
      border-bottom: 1px solid #eee;
    }
    tr:hover {
      background: #fafafa;
    }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-pass {
      background: #d4edda;
      color: #155724;
    }
    .badge-warn {
      background: #fff3cd;
      color: #856404;
    }
    .badge-fail {
      background: #f8d7da;
      color: #721c24;
    }
    .severity-critical { color: #dc3545; font-weight: 600; }
    .severity-high { color: #fd7e14; font-weight: 600; }
    .severity-medium { color: #ffc107; font-weight: 600; }
    .severity-info { color: #0dcaf0; }
    .footer {
      text-align: center;
      color: rgba(255,255,255,0.8);
      font-size: 12px;
      padding-top: 20px;
      border-top: 1px solid rgba(255,255,255,0.2);
      margin-top: 40px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>3D Forge Asset Quality Dashboard</h1>
    <div class="timestamp">Generated: ${new Date(m.timestamp).toLocaleString()}</div>

    <!-- KPI Cards -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Pass Rate</div>
        <div class="kpi-value">${s.pass_rate_percent}%</div>
        <div class="kpi-subtext">${s.assets_passed} of ${s.total_assets} passed</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Quality Score</div>
        <div class="kpi-value">${s.average_quality_score}</div>
        <div class="kpi-unit">/100</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg Production Time</div>
        <div class="kpi-value">${(s.average_production_time_ms / 1000).toFixed(1)}s</div>
        <div class="kpi-unit">per asset</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Assets</div>
        <div class="kpi-value">${s.total_assets}</div>
        <div class="kpi-subtext">
          <span class="badge badge-pass">${s.assets_passed} Pass</span>
          <span class="badge badge-warn">${s.assets_needs_revision} Revision</span>
          <span class="badge badge-fail">${s.assets_rejected} Reject</span>
        </div>
      </div>
    </div>

    <!-- Charts -->
    <div class="charts-grid">
      <!-- Verdict Distribution -->
      <div class="chart-card">
        <div class="chart-title">Verdict Distribution</div>
        <canvas id="verdictChart"></canvas>
      </div>

      <!-- Score Distribution -->
      <div class="chart-card">
        <div class="chart-title">Quality Score Distribution</div>
        <canvas id="scoreChart"></canvas>
      </div>

      <!-- Mechanical Check Pass Rates -->
      <div class="chart-card">
        <div class="chart-title">Mechanical Check Results</div>
        <canvas id="checksChart"></canvas>
      </div>

      <!-- Visual Dimensions -->
      <div class="chart-card">
        <div class="chart-title">Visual Quality Dimensions</div>
        <canvas id="visualChart"></canvas>
      </div>

      <!-- Platform Performance -->
      <div class="chart-card">
        <div class="chart-title">Platform Performance</div>
        <canvas id="platformChart"></canvas>
      </div>

      <!-- Failure Phase Distribution -->
      <div class="chart-card">
        <div class="chart-title">Failures by Phase</div>
        <canvas id="phaseChart"></canvas>
      </div>
    </div>

    <!-- Mechanical Check Details Table -->
    <div class="table-card">
      <div class="chart-title">Mechanical Check Details</div>
      <table>
        <thead>
          <tr>
            <th>Check Name</th>
            <th>Pass Rate</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${this.renderCheckTable()}
        </tbody>
      </table>
    </div>

    <!-- Suggestions -->
    ${m.improvement_suggestions && m.improvement_suggestions.length > 0 ? `
    <div class="table-card">
      <div class="chart-title">Improvement Suggestions</div>
      <table>
        <thead>
          <tr>
            <th>Severity</th>
            <th>Message</th>
          </tr>
        </thead>
        <tbody>
          ${m.improvement_suggestions.map(s => `
          <tr>
            <td><span class="severity-${s.severity}">${s.severity.toUpperCase()}</span></td>
            <td>${s.message}</td>
          </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
    ` : ''}

    <div class="footer">
      <p>Dashboard powered by Chart.js | Data sourced from 3D Forge validation pipeline</p>
    </div>
  </div>

  <script>
    const chartConfig = {
      defaults: {
        font: { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" },
        plugins: { legend: { labels: { usePointStyle: true } } }
      }
    };

    Chart.defaults.set(chartConfig.defaults);

    // Verdict Distribution
    new Chart(document.getElementById('verdictChart'), {
      type: 'doughnut',
      data: {
        labels: ['Passed', 'Needs Revision', 'Rejected'],
        datasets: [{
          data: [${s.assets_passed}, ${s.assets_needs_revision}, ${s.assets_rejected}],
          backgroundColor: ['#28a745', '#ffc107', '#dc3545'],
          borderColor: '#fff',
          borderWidth: 2
        }]
      },
      options: { responsive: true, maintainAspectRatio: true }
    });

    // Score Distribution
    const scoreData = ${JSON.stringify(m.quality_trends.score_distribution)};
    new Chart(document.getElementById('scoreChart'), {
      type: 'bar',
      data: {
        labels: ['0-20', '20-40', '40-60', '60-80', '80-100'],
        datasets: [{
          label: 'Assets',
          data: [
            scoreData['0-20'],
            scoreData['20-40'],
            scoreData['40-60'],
            scoreData['60-80'],
            scoreData['80-100']
          ],
          backgroundColor: '#667eea',
          borderRadius: 6
        }]
      },
      options: {
        indexAxis: 'x',
        responsive: true,
        plugins: { legend: { display: false } }
      }
    });

    // Mechanical Checks
    const checks = ${JSON.stringify(m.quality_trends.check_pass_rates)};
    const checkNames = Object.keys(checks);
    const checkRates = checkNames.map(k => checks[k].pass_rate);
    new Chart(document.getElementById('checksChart'), {
      type: 'bar',
      data: {
        labels: checkNames,
        datasets: [{
          label: 'Pass Rate %',
          data: checkRates,
          backgroundColor: checkRates.map(r => r >= 80 ? '#28a745' : r >= 50 ? '#ffc107' : '#dc3545'),
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: { x: { min: 0, max: 100 } }
      }
    });

    // Visual Dimensions
    const visual = ${JSON.stringify(m.visual_check_results)};
    const visualNames = Object.keys(visual).map(k => k.replace(/_/g, ' '));
    const visualScores = Object.values(visual);
    new Chart(document.getElementById('visualChart'), {
      type: 'radar',
      data: {
        labels: visualNames,
        datasets: [{
          label: 'Score (0-10)',
          data: visualScores,
          borderColor: '#667eea',
          backgroundColor: 'rgba(102, 126, 234, 0.1)',
          borderWidth: 2,
          pointBackgroundColor: '#667eea',
          pointBorderColor: '#fff',
          pointBorderWidth: 2
        }]
      },
      options: {
        responsive: true,
        scales: { r: { min: 0, max: 10 } }
      }
    });

    // Platform Performance
    const platforms = ${JSON.stringify(m.by_platform)};
    const platformNames = Object.keys(platforms);
    const platformRates = platformNames.map(p => platforms[p].pass_rate_percent);
    new Chart(document.getElementById('platformChart'), {
      type: 'bar',
      data: {
        labels: platformNames,
        datasets: [{
          label: 'Pass Rate %',
          data: platformRates,
          backgroundColor: '#764ba2',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { min: 0, max: 100 } }
      }
    });

    // Failure Phases
    const phases = ${JSON.stringify(m.failure_analysis.failure_by_phase)};
    const phaseNames = Object.keys(phases);
    const phaseCounts = Object.values(phases);
    new Chart(document.getElementById('phaseChart'), {
      type: 'doughnut',
      data: {
        labels: phaseNames,
        datasets: [{
          data: phaseCounts,
          backgroundColor: ['#667eea', '#764ba2', '#f093fb', '#4facfe'],
          borderColor: '#fff',
          borderWidth: 2
        }]
      },
      options: { responsive: true, maintainAspectRatio: true }
    });
  </script>
</body>
</html>`;
  }

  renderCheckTable() {
    const checks = this.metrics.quality_trends.check_pass_rates;
    return Object.entries(checks)
      .map(([name, stats]) => {
        let badgeClass = 'badge-fail';
        if (stats.pass_rate >= 80) badgeClass = 'badge-pass';
        else if (stats.pass_rate >= 50) badgeClass = 'badge-warn';

        return `
        <tr>
          <td><strong>${name}</strong></td>
          <td><strong>${stats.pass_rate}%</strong></td>
          <td>${stats.pass}</td>
          <td>${stats.fail}</td>
          <td><span class="badge ${badgeClass}">${stats.pass_rate >= 80 ? 'Good' : stats.pass_rate >= 50 ? 'Fair' : 'Poor'}</span></td>
        </tr>
        `;
      })
      .join('');
  }

  write(outputFile) {
    const html = this.generateHTML();
    fs.writeFileSync(outputFile, html);
    console.log(`Dashboard generated: ${outputFile}`);
  }
}

async function main() {
  try {
    const generator = new DashboardGenerator(DEFAULT_METRICS_FILE);
    generator.loadMetrics();
    generator.write(DEFAULT_OUTPUT_FILE);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { DashboardGenerator };
