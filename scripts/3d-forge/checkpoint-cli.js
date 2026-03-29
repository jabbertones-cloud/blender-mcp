#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "../../");
const POLICY_PATH = path.join(REPO_ROOT, "config", "3d-forge", "checkpoint-policy.json");
const CHECKPOINTS_DIR = path.join(REPO_ROOT, "data", "3d-forge", "checkpoints");

function arg(flag) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : null;
}

function loadPolicy() {
  return JSON.parse(fs.readFileSync(POLICY_PATH, "utf8"));
}

function statePath(runId) {
  return path.join(CHECKPOINTS_DIR, `${runId}.json`);
}

function ensure(runId) {
  const p = statePath(runId);
  if (fs.existsSync(p)) return JSON.parse(fs.readFileSync(p, "utf8"));
  const policy = loadPolicy();
  const state = {
    run_id: runId,
    created_at: new Date().toISOString(),
    checkpoints: (policy.required_checkpoints || []).map((cp) => ({
      id: cp.id,
      before_stage: cp.before_stage,
      status: "pending",
      approved_by: null,
      approved_at: null,
      notes: ""
    }))
  };
  fs.mkdirSync(CHECKPOINTS_DIR, { recursive: true });
  fs.writeFileSync(p, JSON.stringify(state, null, 2));
  return state;
}

function save(runId, state) {
  fs.mkdirSync(CHECKPOINTS_DIR, { recursive: true });
  fs.writeFileSync(statePath(runId), JSON.stringify(state, null, 2));
}

function main() {
  const action = arg("--action") || "list";
  const runId = arg("--run-id");
  if (!runId) {
    console.error("missing --run-id");
    process.exit(1);
  }
  const state = ensure(runId);

  if (action === "list") {
    console.log(JSON.stringify(state, null, 2));
    return;
  }
  if (action === "approve") {
    const checkpointId = arg("--checkpoint");
    const by = arg("--by") || "operator";
    const notes = arg("--notes") || "";
    const cp = state.checkpoints.find((c) => c.id === checkpointId);
    if (!cp) {
      console.error(`checkpoint not found: ${checkpointId}`);
      process.exit(1);
    }
    cp.status = "approved";
    cp.approved_by = by;
    cp.approved_at = new Date().toISOString();
    cp.notes = notes;
    save(runId, state);
    console.log(JSON.stringify({ ok: true, approved: checkpointId, by }, null, 2));
    return;
  }
  if (action === "reject") {
    const checkpointId = arg("--checkpoint");
    const by = arg("--by") || "operator";
    const notes = arg("--notes") || "";
    const cp = state.checkpoints.find((c) => c.id === checkpointId);
    if (!cp) {
      console.error(`checkpoint not found: ${checkpointId}`);
      process.exit(1);
    }
    cp.status = "rejected";
    cp.approved_by = by;
    cp.approved_at = new Date().toISOString();
    cp.notes = notes;
    save(runId, state);
    console.log(JSON.stringify({ ok: true, rejected: checkpointId, by }, null, 2));
    return;
  }
  console.error(`unknown action: ${action}`);
  process.exit(1);
}

main();

