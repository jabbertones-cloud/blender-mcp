# Ariel: record Blender work and teach the MCP

**Status (2026-11-17):** recording is available through an independently maintained Blender extension. Automatic lesson import/promotion into this repository's five-tool MCP is **not yet implemented, merged, installed, or live-verified**. This page is a usable capture runbook and an integration contract, not a claim that the agent has learned.

## Why this is not the existing auto-learner

`scripts/auto_learner.py` records errors and outcomes of MCP demo scripts. It does **not** capture Ariel's human editing sessions, undo/redo decisions, context, selection, or a reproducible scene history. A saved `.blend` contains current scene state, not a complete ordered reconstruction of every edit.

## Independent recorder, pinned

- **Chosen:** [Blender Replay 0.3.0](https://github.com/sabetAI/blender-replay/releases/tag/v0.3.0), source [`sabetAI/blender-replay@160c840faf74db0c9f7b4dcd3ef5f7726577fcb0`](https://github.com/sabetAI/blender-replay/tree/160c840faf74db0c9f7b4dcd3ef5f7726577fcb0). The published extension is `blender_replay-0.3.0.zip`, SHA-256 `024ebd9ffbc1599797b0275fcfdea9b490e7c696b78a6059d9f9e34ccce803d8`. License: GPL-3.0-or-later. Install it **separately**; do not copy the extension's GPL files into this repo or present its code as ours.
- Captures operator history, object/mesh selection and mode context, transforms, materials, node and world/camera settings, and optional geometry checkpoints. Stores recordings in the `.blend`; manually exports `.chronicle.json`.
- The donor's committed [airport verification report](https://github.com/sabetAI/blender-replay/blob/160c840faf74db0c9f7b4dcd3ef5f7726577fcb0/verification/airport_scene/verification_report.json) reports 65 operators, 68 objects and pixel-identical replay **on that synthetic scene**. This is not proof on product scenes.
- **Alternative considered:** [Vitexus/mcp-server-blender](https://github.com/Vitexus/mcp-server-blender/blob/16ac419a42677b1e381fcbe25514f0e010e82618/addon.py) has an MIT-licensed human edit recorder with an agent/human attribution guard, but its bounded in-memory event buffer is not a complete, persistent material/mesh history. Its unrestricted agent Python execution is explicitly **not** a donor for our guided MCP.

## Recording session Ariel can use now

1. Back up the working `.blend` and verify it can be reopened. Install Blender Replay from its pinned release via **Edit > Preferences > Get Extensions > Install from Disk**; enable the extension. In the 3D Viewport press **N**, then open the **Replay** tab. The recording extension is separate from the existing OpenClaw socket bridge.
2. Choose a meaningful recording name, e.g. `spray-bottle-hero-softbox-v1`. Press **Start Recording** before editing. Work normally: model geometry, change topology, set materials and lighting, place the camera.
3. After complicated geometry/modifier work or unusual add-ons, press **Capture State Now**. Use **Pause** for unrelated/private work and **Resume** before continuing the lesson.
4. Press **Stop**. Save the `.blend`, then **Export Recording** to `<lesson>.chronicle.json`. Keep the source `.blend`, recording, references and final render together in a local, access-controlled folder; do not automatically upload recordings or asset paths.
5. Before trusting it, duplicate the original `.blend`. Test **Restore Baseline + Replay** only on the disposable copy (it can remove objects created after the baseline). Verify geometry, materials, camera, render and export; record every missing/skipped step. Do not overwrite Ariel's source.

**Coverage boundary:** Blender does not expose a guaranteed full history of *every* UI action. Modal mouse motion, some sculpt/paint operations, simulation caches, and third-party add-on internals can be absent or only represented by final-state checkpoints. Blender 5.3 behavior must be verified separately; the released donor advertises Blender 4.2+ and was verified by its authors on Blender 5.2/macOS. `bpy.msgbus` also does not see all viewport moves or animation-system changes.

## MCP teaching integration contract (unimplemented)

Preserve exactly the five guided model-facing tools: `router_set_goal`, `router_get_status`, `search_capabilities`, `get_capability_schema`, and `execute_capability`. Do not expose arbitrary recorded `bpy.ops`, source execution, or unchecked JSON as executable MCP tools.

1. **Import as untrusted evidence (read-only):** parse schema-versioned `.chronicle.json` within an explicit local allow-root with file size/element count limits. Treat paths, object names, text content and add-on names as untrusted data. Strip absolute paths, user IDs, credentials and nonessential geometry before providing model context. Report missing/skipped events; never silently convert them into success.
2. **Understand the demonstration:** link ordered operations with selection/mode, object/material/mesh before/after checkpoints and undo/redo. Give each step its exact evidence pointer, Blender version, object dependency and source-scene hash. Separate `observed` from `inferred` steps. Do not assert that a `.blend` alone recovers historical operations.
3. **Draft a bounded lesson:** map observed steps to existing canonical `CapabilityRegistry` keys and argument schemas. For an unsupported action produce a typed `unsupported` item, not raw Python, fabricated capability or a direct socket command. Store a human-readable goal, prerequisites, version bounds, parameter slots and an expected scene/render postcondition.
4. **Human review and promotion:** Ariel must approve scope, redact/private-data exposure, placeholders and output quality before a lesson is searchable. Only verified lessons enter local skill retrieval. Retain the original chronicle as evidence, not executable source.
5. **Replay on a copy, inspect and compare:** the agent executes only existing registered capabilities on a new disposable scene, with checkpoints and stop-on-failure. Validate the scene graph, actual shader assignments, camera/render, animation/export as applicable. Replay must not be called successful from an operator-count match or a single pretty render.

## Real-scene acceptance, not a green fixture

Pilot on: patch hero (1-inch scale and edges); transparent/translucent spray bottle with label/lighting; knit sock with folds and material; boxed packaging with dielines; split-skin transdermal animation; mascot rig -> FBX/Roblox; face-tracked doll; anamorphic Cookies scene; fluid spray. Record one complete human lesson per supported family, then re-create on a fresh Blender process from the mapped MCP procedure.

For each, require an independently inspected before/after `.blend`, outputs, scene-object/material/animation/export assertions, negative checks after Undo/Redo, a report of unsupported actions, and a human quality verdict. Record Blender version **5.2 vs 5.3** separately. A polished demo of cube/light is not acceptance for these scenes.

## Research and release holds

- The current repo's GitHub Research Pattern Card for guided canonical execution is [`blender-progressive-tool-guides`](https://github.com/jabbertones-cloud/githubresearchmcp/blob/main/data/pattern-cards/blender-progressive-tool-guides.md); no action-recording-specific TaskMap/Pattern Card was established in this session. Research Fabric job `82c49db4-6f33-47e3-aae1-c938200f9aa7` finished with `sufficiency.sufficient=false` / `donor_verification_blocked` and is **not** a production-code gate pass.
- No authorized Blender workstation was connected through Desktop Commander for a 5.2/5.3 live recording exercise; do not claim end-to-end acceptance, installation, trained lessons, or deployment.
- Future code must satisfy source-pinned donor/license review, independent local Blender runtime tests and the repo's release gate. **GitHub Actions stay disabled**; use a non-GitHub-Actions runner. Follow exact HEAD -> merge -> exact MAIN -> installation -> live acceptance -> adversarial/regression. Preserve original scene data and existing MCP access boundaries.
