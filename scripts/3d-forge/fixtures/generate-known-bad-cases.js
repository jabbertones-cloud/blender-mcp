#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.join(__dirname, "../../../");
const OUT_DIR = path.join(REPO_ROOT, "data", "3d-forge", "hall-of-failures-artifacts");

fs.mkdirSync(OUT_DIR, { recursive: true });
const manifest = {
  generated_at: new Date().toISOString(),
  note: "Placeholder fixture generator. Add real synthetic frame sets here.",
  artifacts_dir: OUT_DIR,
};
fs.writeFileSync(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));
console.log(JSON.stringify({ ok: true, out: path.join(OUT_DIR, "manifest.json") }, null, 2));

