#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "../../");
const HOF_PATH = path.join(REPO_ROOT, "data", "3d-forge", "hall-of-failures.json");
const REPORTS_DIR = path.join(REPO_ROOT, "reports");
const TEMPORAL_REPORT = path.join(REPORTS_DIR, "3d-forge-temporal-latest.json");

function loadJson(p, fallback) {
  try {
    if (!fs.existsSync(p)) return fallback;
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return fallback;
  }
}

function main() {
  const hof = loadJson(HOF_PATH, { cases: [] });
  const temporal = loadJson(TEMPORAL_REPORT, { results: [] });
  const byAsset = new Map((temporal.results || []).map((r) => [r.asset_id, r]));
  const checks = [];

  for (const c of hof.cases || []) {
    const assetId = c.asset_ref?.asset_id;
    const t = byAsset.get(assetId);
    if (!t) {
      checks.push({ case_id: c.case_id, status: "missing_asset", pass: false });
      continue;
    }
    const thr = c.thresholds || {};
    const pass =
      (typeof thr.flicker_max !== "number" || t.flicker <= thr.flicker_max) &&
      (typeof thr.shimmer_max !== "number" || t.shimmer <= thr.shimmer_max) &&
      (typeof thr.exposure_pumping_max !== "number" || t.exposure_pumping <= thr.exposure_pumping_max);
    checks.push({
      case_id: c.case_id,
      asset_id: assetId,
      pass,
      measured: { flicker: t.flicker, shimmer: t.shimmer, exposure_pumping: t.exposure_pumping },
      thresholds: thr,
    });
  }

  const report = {
    generated_at: new Date().toISOString(),
    total_cases: checks.length,
    pass_rate: checks.length ? Number((checks.filter((c) => c.pass).length / checks.length * 100).toFixed(2)) : 100,
    checks,
  };
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  fs.writeFileSync(path.join(REPORTS_DIR, "3d-forge-regression-suite-latest.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}

main();

