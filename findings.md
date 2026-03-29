# Findings

- The MCP server reads `BLENDER_PORT` in `server/blender_mcp_server.py`.
- The Blender addon reads `OPENCLAW_PORT` in `blender_addon/openclaw_blender_bridge.py`.
- The checked-in `claude_mcp_config.json` uses `OPENCLAW_PORT` for secondary servers.
- `setup.sh` generates `claude_mcp_config.json`, so config consistency must be fixed there too.
- Existing docs are useful but overlapping; `.claude/skills/blender-mcp/SKILL.md` is the strongest operational document and should become the declared source of truth unless replaced.
- Live end-to-end verification is currently blocked by the absence of a running Blender bridge on `127.0.0.1:9876`.
- The repo-level health-check is more useful if it also reports known Blender 5.1 failure signals from `data/learning_journal.json`; the current implementation now surfaces those.
- The system `python3` in this shell does not have `pydantic`, while the repo `.venv` interpreter does. Runtime verification should use the configured interpreter, not assume the global one.
