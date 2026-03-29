/**
 * Minimal .env loader — no dependencies.
 * Call loadEnv() at the top of any 3D Forge script.
 * Walks up from __dirname to find the nearest .env file.
 */

const fs = require('fs');
const path = require('path');

function loadEnv() {
  // Walk up from this file's directory to find .env
  let dir = path.resolve(__dirname, '..', '..', '..');
  const maxUp = 5;
  for (let i = 0; i < maxUp; i++) {
    const envPath = path.join(dir, '.env');
    if (fs.existsSync(envPath)) {
      const lines = fs.readFileSync(envPath, 'utf8').split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) continue;
        const eqIdx = trimmed.indexOf('=');
        if (eqIdx === -1) continue;
        const key = trimmed.slice(0, eqIdx).trim();
        let value = trimmed.slice(eqIdx + 1).trim();
        // Strip surrounding quotes
        if ((value.startsWith('"') && value.endsWith('"')) ||
            (value.startsWith("'") && value.endsWith("'"))) {
          value = value.slice(1, -1);
        }
        // Don't overwrite existing env vars
        if (!process.env[key]) {
          process.env[key] = value;
        }
      }
      return envPath;
    }
    dir = path.dirname(dir);
  }
  return null;
}

module.exports = { loadEnv };
