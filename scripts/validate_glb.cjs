'use strict';
// The official Khronos glTF-Validator owns specification validation.
const fs = require('node:fs');
const path = require('node:path');
const { validateBytes } = require('gltf-validator');

(async () => {
  const file = process.argv[2];
  if (!file || path.extname(file).toLowerCase() !== '.glb') throw new Error('Expected an exported .glb');
  const report = await validateBytes(new Uint8Array(fs.readFileSync(file)), {
    format: 'glb', uri: path.basename(file), maxIssues: 40,
  });
  const issues = report.issues || {};
  const messages = issues.messages || [];
  const errors = Math.max(Number(issues.numErrors || 0), messages.filter(m => m.severity === 0).length);
  const warnings = Math.max(Number(issues.numWarnings || 0), messages.filter(m => m.severity === 1).length);
  process.stdout.write(JSON.stringify({ valid: errors === 0, errors, warnings, messages }) + '\n');
  if (errors) process.exitCode = 1;
})().catch(error => {
  process.stdout.write(JSON.stringify({ valid: false, errors: 1, reason: String(error) }) + '\n');
  process.exitCode = 1;
});
