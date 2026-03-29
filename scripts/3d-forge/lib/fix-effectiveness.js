"use strict";

const fs = require("fs");
const path = require("path");

function appendFixEffect(logPath, event) {
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.appendFileSync(logPath, JSON.stringify(event) + "\n");
}

function loadFixEvents(logPath) {
  if (!fs.existsSync(logPath)) return [];
  const lines = fs.readFileSync(logPath, "utf8").split("\n").map((l) => l.trim()).filter(Boolean);
  const events = [];
  for (const l of lines) {
    try {
      events.push(JSON.parse(l));
    } catch {
      // ignore malformed line
    }
  }
  return events;
}

function buildFixPriority(events) {
  const byFix = new Map();
  for (const ev of events) {
    const key = ev.fix_id || "unknown_fix";
    if (!byFix.has(key)) byFix.set(key, { attempts: 0, success: 0, delta: 0, durations: [] });
    const row = byFix.get(key);
    row.attempts += 1;
    if (ev.success) row.success += 1;
    row.delta += Number(ev.delta_score || 0);
    if (typeof ev.duration_ms === "number") row.durations.push(ev.duration_ms);
  }

  const rankings = [...byFix.entries()].map(([fix_id, row]) => {
    const successRate = row.attempts ? row.success / row.attempts : 0;
    const avgDelta = row.attempts ? row.delta / row.attempts : 0;
    const avgDuration = row.durations.length
      ? row.durations.reduce((a, b) => a + b, 0) / row.durations.length
      : 0;
    const priorityScore = (successRate * 0.6) + (Math.max(0, avgDelta) / 20 * 0.4);
    return {
      fix_id,
      attempts: row.attempts,
      success_rate: Number(successRate.toFixed(3)),
      avg_delta_score: Number(avgDelta.toFixed(3)),
      avg_duration_ms: Math.round(avgDuration),
      priority_score: Number(priorityScore.toFixed(3)),
    };
  }).sort((a, b) => b.priority_score - a.priority_score);

  return rankings;
}

module.exports = {
  appendFixEffect,
  loadFixEvents,
  buildFixPriority,
};

