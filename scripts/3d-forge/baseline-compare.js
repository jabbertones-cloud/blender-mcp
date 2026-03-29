#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "../../");
const REPORTS_DIR = path.join(REPO_ROOT, "reports");
const BASELINE_PATH = path.join(REPO_ROOT, "config", "3d-forge", "temporal-baseline.json");
const TEMPORAL_PATH = path.join(REPORTS_DIR, "3d-forge-temporal-latest.json");
const AUTORESEARCH_PATH = path.join(REPORTS_DIR, "3d-forge-autoresearch-latest.json");

function loadJson(p, fallback) {
  try {
    if (!fs.existsSync(p)) return fallback;
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return fallback;
  }
}

function main() {
  const baseline = loadJson(BASELINE_PATH, { targets: {} });
  const temporal = loadJson(TEMPORAL_PATH, {});
  const auto = loadJson(AUTORESEARCH_PATH, {});
  const t = baseline.targets || {};
  const result = {
    generated_at: new Date().toISOString(),
    checks: {
      temporal_flicker_avg: {
        value: temporal.temporal_flicker_avg ?? null,
        target_max: t.temporal_flicker_avg_max ?? null,
        pass: typeof temporal.temporal_flicker_avg === "number" && typeof t.temporal_flicker_avg_max === "number"
          ? temporal.temporal_flicker_avg <= t.temporal_flicker_avg_max
          : null,
      },
      temporal_shimmer_avg: {
        value: temporal.temporal_shimmer_avg ?? null,
        target_max: t.temporal_shimmer_avg_max ?? null,
        pass: typeof temporal.temporal_shimmer_avg === "number" && typeof t.temporal_shimmer_avg_max === "number"
          ? temporal.temporal_shimmer_avg <= t.temporal_shimmer_avg_max
          : null,
      },
      temporal_exposure_pumping_avg: {
        value: temporal.temporal_exposure_pumping_avg ?? null,
        target_max: t.temporal_exposure_pumping_avg_max ?? null,
        pass: typeof temporal.temporal_exposure_pumping_avg === "number" && typeof t.temporal_exposure_pumping_avg_max === "number"
          ? temporal.temporal_exposure_pumping_avg <= t.temporal_exposure_pumping_avg_max
          : null,
      },
      temporal_stability_pass_rate: {
        value: temporal.temporal_stability_pass_rate ?? null,
        target_min: t.temporal_stability_pass_rate_min ?? null,
        pass: typeof temporal.temporal_stability_pass_rate === "number" && typeof t.temporal_stability_pass_rate_min === "number"
          ? temporal.temporal_stability_pass_rate >= t.temporal_stability_pass_rate_min
          : null,
      },
      validation_pass_rate: {
        value: auto.kpis?.validation_pass_rate ?? null
      }
    }
  };

  const passValues = Object.values(result.checks).map((v) => v.pass).filter((v) => typeof v === "boolean");
  result.overall_pass = passValues.length ? passValues.every(Boolean) : false;

  fs.writeFileSync(path.join(REPORTS_DIR, "3d-forge-baseline-compare-latest.json"), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
}

main();

