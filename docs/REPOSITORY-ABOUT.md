# Repository metadata (GitHub UI)

Use this file to keep the GitHub **About** section aligned with the real codebase. Last audited with the tool list in `server/blender_mcp_server.py` + `server/product_animation_tools.py`.

## Short description (≤ 350 characters)

```
MCP server for Blender: 65 FastMCP tools, TCP bridge to bpy, multi-instance ports (9876–9885), 3D Forge asset pipeline, product animation presets, render QA — OpenClaw.
```

## Topics (suggested)

`blender` `mcp` `model-context-protocol` `fastmcp` `bpy` `3d` `openclaw` `ai-3d` `rendering` `glb` `stl` `python`

## Optional website

If you publish docs: repository URL or `https://github.com/jabbertones-cloud/blender-mcp`

## What to avoid in the About field

- Claiming “35 tools” (obsolete; current total is **65**).
- Implying HTTP access — transport is **MCP over stdio** to the Python server, then **TCP** to Blender.
