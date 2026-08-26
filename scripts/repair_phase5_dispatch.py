#!/usr/bin/env python3
"""Repair the Phase 5 addon dispatch typo without weakening any gate.

The addon socket dispatcher reads HANDLERS, but the Phase 5 loader historically
updated an undefined COMMANDS name. This script performs one exact replacement
and fails closed if the source is already different.
"""
from pathlib import Path

PATH = Path("blender_addon/openclaw_blender_bridge.py")
OLD = "    COMMANDS.update(_PHASE5_HANDLERS)"
NEW = "    HANDLERS.update(_PHASE5_HANDLERS)"

source = PATH.read_text(encoding="utf-8")
old_count = source.count(OLD)
new_count = source.count(NEW)

if old_count == 0 and new_count == 1:
    print("phase5 dispatch already repaired")
    raise SystemExit(0)
if old_count != 1 or new_count != 0:
    raise SystemExit(
        f"refusing ambiguous repair: old_count={old_count} new_count={new_count} path={PATH}"
    )

PATH.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
print("repaired Phase 5 dispatch: COMMANDS -> HANDLERS")
