#!/usr/bin/env python3
"""Keep the OpenClaw Blender bridge alive in --background mode for E2E tests.

Blender exits after a normal --python script finishes, while the bridge executes
queued bpy work from its main-thread timer callback. This runner deliberately
owns that main-thread pump so CI exercises the same socket -> queue -> Blender
execution boundary without depending on a GUI event loop.
"""
from __future__ import annotations

import signal
import time

import bpy

_STOP = False


def _request_stop(_signum, _frame) -> None:
    global _STOP
    _STOP = True


signal.signal(signal.SIGTERM, _request_stop)
signal.signal(signal.SIGINT, _request_stop)

# Enabling the addon imports it and register() auto-starts the socket listener.
bpy.ops.preferences.addon_enable(module="openclaw_blender_bridge")
import openclaw_blender_bridge as bridge  # noqa: E402

print(f"[HeadlessBridgeRunner] bridge={bridge.HOST}:{bridge.PORT}", flush=True)

try:
    while not _STOP and bridge.running:
        # Execute queued callbacks on Blender's main thread. In GUI mode
        # bpy.app.timers owns this; --background scripts need an explicit pump.
        bridge.timer_callback()
        time.sleep(max(0.005, min(float(getattr(bridge, "TIMER_INTERVAL", 0.1)), 0.1)))
finally:
    bridge.running = False
    print("[HeadlessBridgeRunner] stopping", flush=True)
