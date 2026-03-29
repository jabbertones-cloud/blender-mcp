"use strict";

const fs = require("fs");

function loadJson(path, fallback) {
  try {
    if (!fs.existsSync(path)) return fallback;
    return JSON.parse(fs.readFileSync(path, "utf8"));
  } catch {
    return fallback;
  }
}

function classifyFailures(validation, taxonomyConfig) {
  const failures = [];
  const classes = (taxonomyConfig && taxonomyConfig.classes) || [];
  const checks = validation?.mechanical?.checks || {};
  const visual = validation?.visual || {};
  const shotGates = validation?.scoring?.shot_gates || null;

  for (const item of classes) {
    const rule = item.detect_from || {};
    let hit = false;
    if (rule.type === "mechanical_check_failed" && rule.check) {
      hit = !!checks[rule.check] && checks[rule.check].passed === false;
    } else if (rule.type === "visual_average_lt" && typeof rule.value === "number") {
      hit = typeof visual.average === "number" && visual.average < rule.value;
    } else if (rule.type === "visual_verdict" && typeof rule.equals === "string") {
      hit = String(visual.verdict || "") === rule.equals;
    } else if (rule.type === "shot_gate_failed") {
      hit = shotGates && shotGates.enabled && shotGates.overall_pass === false;
    }
    if (hit) {
      failures.push({
        failure_code: item.failure_code,
        severity: item.severity || "medium",
        phase: item.phase || "validate",
        tags: item.tags || [],
      });
    }
  }
  return failures;
}

module.exports = {
  loadJson,
  classifyFailures,
};

