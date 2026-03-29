#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "../../");
const HOF_PATH = path.join(REPO_ROOT, "data", "3d-forge", "hall-of-failures.json");

function load() {
  if (!fs.existsSync(HOF_PATH)) return { version: "v1", generated_at: new Date().toISOString(), cases: [] };
  return JSON.parse(fs.readFileSync(HOF_PATH, "utf8"));
}

function save(data) {
  fs.mkdirSync(path.dirname(HOF_PATH), { recursive: true });
  data.generated_at = new Date().toISOString();
  fs.writeFileSync(HOF_PATH, JSON.stringify(data, null, 2));
}

function arg(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : null;
}

function main() {
  const action = arg("--action") || "list";
  const data = load();
  if (action === "list") {
    console.log(JSON.stringify({ count: data.cases.length, cases: data.cases.map((c) => ({ case_id: c.case_id, label: c.label, status: c.status })) }, null, 2));
    return;
  }
  if (action === "add") {
    const caseId = arg("--case-id");
    const label = arg("--label") || caseId;
    const assetId = arg("--asset-id");
    if (!caseId || !assetId) {
      console.error("add requires --case-id and --asset-id");
      process.exit(1);
    }
    data.cases.push({
      case_id: caseId,
      label,
      failure_modes: ["multi_mode"],
      severity: "high",
      source_type: "real_run",
      asset_ref: { asset_id: assetId },
      artifacts: { frame_glob: `exports/3d-forge/${assetId}/*.png` },
      expected_signals: {},
      thresholds: { flicker_max: 6, shimmer_max: 6, exposure_pumping_max: 5 },
      status: "active",
      first_seen_at: new Date().toISOString(),
      last_seen_at: new Date().toISOString()
    });
    save(data);
    console.log(JSON.stringify({ ok: true, added: caseId }, null, 2));
    return;
  }
  if (action === "remove") {
    const caseId = arg("--case-id");
    const before = data.cases.length;
    data.cases = data.cases.filter((c) => c.case_id !== caseId);
    save(data);
    console.log(JSON.stringify({ ok: true, removed: before - data.cases.length }, null, 2));
    return;
  }
  console.error(`unknown action: ${action}`);
  process.exit(1);
}

main();

