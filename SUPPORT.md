# Blender MCP support

**Reviewed:** November 17, 2026

OpenClaw Blender MCP connects an AI/MCP client to Blender through a local bridge. The repository's **recommended default** is the five-tool, search-first guided server; the larger legacy/expert tool catalog is an alternative interface, not the default model-facing surface.

## Get support

- **README and setup architecture:** [Blender MCP README](README.md)
- **Existing public issues:** https://github.com/jabbertones-cloud/blender-mcp/issues
- **Report a reproducible bug:** https://github.com/jabbertones-cloud/blender-mcp/issues/new/choose
- **MCP protocol documentation:** https://modelcontextprotocol.io/

This is source-level support for locally operated software. It does not establish a hosted commercial service, an approved ChatGPT plugin or guaranteed availability of third-party asset services.

## First check the correct tool surface

The guided server registers `router_set_goal`, `router_get_status`, `search_capabilities`, `get_capability_schema` and `execute_capability`. Clients should **search**, inspect the schema for a canonical capability key, then execute that exact key. The legacy server has a larger catalog with different names. Do not pass a guessed alias to `execute_capability` or assume every legacy tool name is available on the guided server.

| Symptom | Next diagnostic |
| --- | --- |
| MCP tools not detected | Confirm the client is launching the intended guided or legacy entrypoint and show a sanitized startup error |
| Blender bridge connection fails | Confirm Blender and the local bridge are running and reachable on the configured local transport; report OS, Blender and Python versions |
| `CAPABILITY_NOT_FOUND` | Call `search_capabilities`, then `get_capability_schema`, and use the exact canonical key returned |
| Wrong object/material/render output | Provide a minimal non-sensitive Blender scene, goal, canonical capability key, validated arguments, and observed result |
| A plan ends without final render | Report the planner configuration, step limit, critique result and whether the final render operation actually ran |

## Public reporting and private information

Public issues should include a non-sensitive reproduction, MCP client and version, Blender/Python versions, server entrypoint, error label, and expected versus observed behavior. Remove secrets, licensed or confidential assets, customer models, private file paths, internal IP addresses and private project materials.

For suspected vulnerabilities use the repository owner's private security reporting path where available. Do not publish exploit instructions or active secrets in public tickets. GitHub issue actions by agents require the user's own GitHub authorization and explicit approval before posting.

No GitHub Actions workflow was created or enabled as part of this support documentation.
