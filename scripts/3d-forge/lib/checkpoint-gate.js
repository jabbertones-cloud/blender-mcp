"use strict";

const fs = require("fs");
const path = require("path");

function ensureCheckpointState(statePath, runId, policy) {
  if (fs.existsSync(statePath)) {
    return JSON.parse(fs.readFileSync(statePath, "utf8"));
  }
  const checkpoints = (policy.required_checkpoints || []).map((cp) => ({
    id: cp.id,
    before_stage: cp.before_stage,
    status: "pending",
    approved_by: null,
    approved_at: null,
    notes: "",
  }));
  const state = { run_id: runId, created_at: new Date().toISOString(), checkpoints };
  fs.mkdirSync(path.dirname(statePath), { recursive: true });
  fs.writeFileSync(statePath, JSON.stringify(state, null, 2));
  return state;
}

function isCheckpointApprovedForStage(state, stage) {
  const needed = state.checkpoints.filter((c) => c.before_stage === stage);
  if (!needed.length) return { ok: true, missing: [] };
  const missing = needed.filter((c) => c.status !== "approved").map((c) => c.id);
  return { ok: missing.length === 0, missing };
}

module.exports = {
  ensureCheckpointState,
  isCheckpointApprovedForStage,
};

