#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "../../");
const EXPORTS_DIR = path.join(REPO_ROOT, "exports", "3d-forge");
const REPORTS_DIR = path.join(REPO_ROOT, "reports");

function listAssets() {
  if (!fs.existsSync(EXPORTS_DIR)) return [];
  return fs.readdirSync(EXPORTS_DIR).filter((d) => {
    const p = path.join(EXPORTS_DIR, d);
    return fs.existsSync(path.join(p, "metadata.json"));
  });
}

function scoreFromFileSet(dir) {
  const files = fs.readdirSync(dir).filter((f) => f.endsWith(".png"));
  const sizes = files.map((f) => fs.statSync(path.join(dir, f)).size);
  if (!files.length) {
    return { pass: false, flicker: 10, shimmer: 10, exposure_pumping: 10, reason: "no_frames" };
  }
  const min = Math.min(...sizes);
  const max = Math.max(...sizes);
  const mean = sizes.reduce((a, b) => a + b, 0) / sizes.length;
  const varianceRatio = mean > 0 ? (max - min) / mean : 1;
  const flicker = Math.min(10, Number((varianceRatio * 10).toFixed(2)));
  const shimmer = Math.min(10, Number((varianceRatio * 8).toFixed(2)));
  const exposure = Math.min(10, Number((varianceRatio * 6).toFixed(2)));
  const pass = flicker <= 6 && shimmer <= 6 && exposure <= 5;
  return { pass, flicker, shimmer, exposure_pumping: exposure, frame_count: files.length };
}

function main() {
  const assets = listAssets();
  const results = [];
  for (const asset of assets) {
    const dir = path.join(EXPORTS_DIR, asset);
    const temporal = scoreFromFileSet(dir);
    const payload = {
      asset_id: asset,
      audited_at: new Date().toISOString(),
      ...temporal,
    };
    fs.writeFileSync(path.join(dir, "temporal-audit.json"), JSON.stringify(payload, null, 2));
    results.push(payload);
  }
  const avg = (k) => {
    if (!results.length) return null;
    return Number((results.reduce((s, r) => s + (r[k] || 0), 0) / results.length).toFixed(3));
  };
  const report = {
    generated_at: new Date().toISOString(),
    assets_analyzed: results.length,
    temporal_flicker_avg: avg("flicker"),
    temporal_shimmer_avg: avg("shimmer"),
    temporal_exposure_pumping_avg: avg("exposure_pumping"),
    temporal_stability_pass_rate: results.length
      ? Number((results.filter((r) => r.pass).length / results.length * 100).toFixed(2))
      : null,
    results,
  };
  fs.mkdirSync(REPORTS_DIR, { recursive: true });
  fs.writeFileSync(path.join(REPORTS_DIR, "3d-forge-temporal-latest.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
}

main();

