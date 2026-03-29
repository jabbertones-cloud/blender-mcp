# Progress Log

## 2026-03-26

- Indexed `openclaw-blender-mcp` with jCodeMunch for symbol-level inspection.
- Audited server/addon/config/doc layout.
- Identified env var mismatch across server, addon, and generated config.
- Started implementation pass with planning, TDD, and verification workflow.
- Added failing unit tests for runtime config and config health-check validation.
- Added `server/runtime_config.py` and `server/healthcheck.py`.
- Added `scripts/blender_healthcheck.py` and npm script aliases.
- Updated server env resolution to support both `BLENDER_PORT` and `OPENCLAW_PORT`.
- Updated `setup.sh`, `claude_mcp_config.json`, `README.md`, `BLENDER_SKILLS_REFERENCE.md`, and the repo Blender skill to declare a single operational source of truth.
- Added Codex-native skill wrapper at `/Users/tatsheen/.codex/skills/blender-mcp/SKILL.md`.
- Verified unit tests pass, static health-check passes, and live health-check fails cleanly with `connection refused` when Blender is not running.
- Reproduced and fixed a timeout/crash in the interpreter dependency probe used by the health-check.
- Verified live health-check succeeds against the Blender bridge currently listening on `127.0.0.1:9876`.
- Verified `python3 tests/qa_runner.py --quick` passes 69/69 against the live Blender instance.
- Verified full live multi-instance routing on `127.0.0.1:9877` and `127.0.0.1:9878` with successful health-check probes returning `instance_id` values `blender-9877` and `blender-9878`.
- Confirmed direct TCP connectivity on ports `9877` and `9878` while the extra Blender processes were running.
