"use strict";

const fs = require("fs");
const path = require("path");

function loadJson(p, fallback) {
  try {
    if (!fs.existsSync(p)) return fallback;
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return fallback;
  }
}

function saveJson(p, data) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, JSON.stringify(data, null, 2));
}

function evaluateMode(kpis) {
  if (!kpis) return "balanced";
  if ((kpis.validation_pass_rate ?? 100) < 40 || (kpis.production_quality_score_avg ?? 100) < 60) {
    return "aggressive";
  }
  if ((kpis.cost_per_asset_usd ?? 0) > 1 || (kpis.steps_failed_rate ?? 0) > 25) {
    return "conservative";
  }
  return "balanced";
}

module.exports = {
  loadJson,
  saveJson,
  evaluateMode,
};

