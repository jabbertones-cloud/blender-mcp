# Task Plan

## Goal
Implement a high-value improvement pass for the Blender MCP repo:
- fix the port/env mismatch
- establish one operational source of truth for Blender usage
- add a Codex-native Blender skill for subagents
- add a Blender 5.1 health-check and verification path

## Phases
- [completed] Phase 1: Add planning files and capture current findings
- [completed] Phase 2: Add failing tests for runtime config and health-check behavior
- [completed] Phase 3: Implement shared runtime config and health-check script
- [completed] Phase 4: Fix generated MCP config and checked-in config consistency
- [completed] Phase 5: Consolidate source-of-truth docs and add Codex-native skill
- [completed] Phase 6: Run verification and review results
- [completed] Phase 7: Verify live multi-instance routing on ports 9877 and 9878

## Constraints
- Do not revert unrelated dirty worktree changes outside this repo
- Use apply_patch for edits
- Prefer minimal, test-backed changes

## Errors Encountered
- Documentation-engineer subagent failed once due to unsupported default model in this environment; respawn with a supported model
