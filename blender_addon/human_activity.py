# Human-activity recorder for the OpenClaw Blender bridge.
#
# PORTED from ahujasid/mcp-for-blender (addon.py, "Manual edit capture"),
# Copyright (c) 2025 Siddharth Ahuja, MIT License:
#
#   Permission is hereby granted, free of charge, to any person obtaining a
#   copy of this software and associated documentation files (the
#   "Software"), to deal in the Software without restriction, including
#   without limitation the rights to use, copy, modify, merge, publish,
#   distribute, sublicense, and/or sell copies of the Software, and to
#   permit persons to whom the Software is furnished to do so, subject to
#   the following conditions: The above copyright notice and this
#   permission notice shall be included in all copies or substantial
#   portions of the Software.
#
#   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#   EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#   MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#   NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
#   LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
#   OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
#   WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# Source: https://github.com/ahujasid/blender-mcp — addon.py,
# class UserEditRecorder + drain_human_activity (verified against the
# upstream clone, 2026-11-17).
#
# Adaptation for this bridge (changes from upstream, kept minimal):
#   * Consent lives in this module instead of upstream's addon-preferences
#     telemetry flag. It is OFF by default and fails closed. It can be
#     enabled by the OPENCLAW_HUMAN_ACTIVITY=1 environment variable at
#     addon load, or at runtime via the set_human_activity_consent bridge
#     command — which the MCP side may only send after the artist has
#     explicitly opted in. Handlers attach only while consent is on.
#   * Agent attribution: the bridge's process_command() wraps every
#     dispatched command in recorder.agent_command(), so operators the
#     agent itself triggers are never recorded as the artist's.
#   * Purpose here: FORWARD learning only. The recorder captures what the
#     artist does in live sessions from now on; it cannot recover past
#     work. Past work is learned from her .blend files (see
#     config/ariel_workflow_profile.json). Drained events are labelled
#     "artist-live" and must never be merged blindly with file-derived or
#     external-corpus patterns.
"""Capture the operators the ARTIST runs in a live Blender session.

Consent-gated, off by default. See module header for provenance (MIT port).
"""
from __future__ import annotations

import os
import time
from collections import deque
from contextlib import contextmanager

import bpy
from bpy.app.handlers import persistent

MAX_EDIT_EVENTS = 256

# Operators that fire constantly during interactive work and carry no
# meaningful intent on their own. (Upstream list, unchanged.)
_IGNORED_OPERATORS = frozenset({
    "view3d.rotate",
    "view3d.move",
    "view3d.zoom",
    "view3d.dolly",
    "view3d.view_axis",
    "view3d.view_orbit",
    "view3d.view_pan",
    "view3d.smoothview",
    "view3d.cursor3d",
    "wm.tool_set_by_id",
    "wm.context_set_value",
    "screen.animation_step",
})

# Operator properties holding filesystem paths. Never recorded.
_PATH_PROPERTY_NAMES = frozenset({
    "filepath",
    "filename",
    "directory",
    "filepath_raw",
    "relpath",
})
_PATH_PROPERTY_SUBSTRINGS = ("filepath", "filename", "directory", "_dir", "path")
MAX_OPERATOR_PROPERTY_CHARS = 200

# depsgraph_update_post fires on every scene update, many times per second
# during interactive drags.
EDIT_POLL_MIN_INTERVAL = 0.1


def _is_path_property(identifier):
    """True if an operator property likely holds a filesystem path."""
    lowered = identifier.lower()
    if lowered in _PATH_PROPERTY_NAMES:
        return True
    return any(token in lowered for token in _PATH_PROPERTY_SUBSTRINGS)


class UserEditRecorder:
    """Buffers human-originated operator and undo events for the MCP server.

    Anything that happens while an agent command is running is attributed to
    the agent, not the human; `agent_command()` brackets that window.
    (Ported from upstream — see module header.)
    """

    def __init__(self):
        self._events = deque(maxlen=MAX_EDIT_EVENTS)
        self._agent_depth = 0
        self._last_operator_count = 0
        self._seen_baseline = False
        self._last_poll_time = 0.0

    @contextmanager
    def agent_command(self):
        """Suppress capture for the duration of an agent-issued command."""
        self._agent_depth += 1
        try:
            yield
        finally:
            self._agent_depth = max(0, self._agent_depth - 1)
            self._resync_operator_baseline()

    @property
    def _suppressed(self):
        return self._agent_depth > 0

    def _operator_stack(self):
        try:
            return list(bpy.context.window_manager.operators)
        except Exception:
            return []

    def _resync_operator_baseline(self):
        self._last_operator_count = len(self._operator_stack())
        self._seen_baseline = True

    def poll_operators(self, now=None):
        """Emit rows for operators run since the last poll. Main thread only.

        Throttled to EDIT_POLL_MIN_INTERVAL.
        """
        if self._suppressed:
            return
        now = time.time() if now is None else now
        if (now - self._last_poll_time) < EDIT_POLL_MIN_INTERVAL:
            return
        self._last_poll_time = now
        stack = self._operator_stack()
        count = len(stack)

        # First poll only establishes a baseline.
        if not self._seen_baseline:
            self._last_operator_count = count
            self._seen_baseline = True
            return

        if count <= self._last_operator_count:
            # Unchanged, or shrank because of an undo. Hold the high-water
            # mark so a later redo does not replay emitted operators.
            return

        for op in stack[self._last_operator_count:count]:
            self._record_operator(op)
        self._last_operator_count = count

    def _record_operator(self, op):
        try:
            bl_idname = getattr(op, "bl_idname", None)
            if not bl_idname:
                return
            # bl_idname is UPPER_CASE_OT_form; normalise to bpy.ops form.
            normalized = bl_idname.lower().replace("_ot_", ".", 1)
            if normalized in _IGNORED_OPERATORS:
                return
            self._events.append({
                "kind": "operator",
                "bl_idname": normalized,
                "name": getattr(op, "name", None),
                "properties": self._operator_properties(op),
                "timestamp": time.time(),
            })
        except Exception as e:
            print(f"[OpenClaw] Human-activity capture: failed to record operator: {e}")

    @staticmethod
    def _operator_properties(op):
        """Best-effort scalar snapshot of an operator's resolved properties."""
        props = {}
        try:
            rna_props = op.properties.bl_rna.properties
        except Exception:
            return props
        for prop in rna_props:
            if prop.identifier == "rna_type":
                continue
            if _is_path_property(prop.identifier):
                continue
            try:
                value = getattr(op.properties, prop.identifier)
            except Exception:
                continue
            if isinstance(value, str):
                props[prop.identifier] = value[:MAX_OPERATOR_PROPERTY_CHARS]
            elif isinstance(value, (bool, int, float)):
                props[prop.identifier] = value
            elif hasattr(value, "__len__") and not isinstance(value, (dict, bytes)):
                try:
                    items = [
                        v[:MAX_OPERATOR_PROPERTY_CHARS] if isinstance(v, str) else v
                        for v in value
                        if isinstance(v, (bool, int, float, str))
                    ]
                    if items and len(items) <= 16:
                        props[prop.identifier] = items
                except Exception:
                    continue
        return props

    def record_undo(self, kind):
        """Record an undo/redo. This is the strongest rejection signal we get."""
        if self._suppressed:
            return
        self._events.append({
            "kind": kind,
            "timestamp": time.time(),
        })
        # Keep the high-water mark so a redo does not re-emit consumed entries.
        self._last_operator_count = max(
            self._last_operator_count, len(self._operator_stack())
        )
        self._seen_baseline = True

    def drain(self):
        """Hand buffered events to the MCP server and clear them."""
        events = list(self._events)
        self._events.clear()
        return events


_edit_recorder = UserEditRecorder()


def get_edit_recorder():
    return _edit_recorder


# ---------------------------------------------------------------------------
# Consent gate (adaptation — see module header). OFF by default, fails closed.
# ---------------------------------------------------------------------------

_consent = os.environ.get("OPENCLAW_HUMAN_ACTIVITY", "") == "1"


def consent_enabled() -> bool:
    return bool(_consent)


def set_consent(enabled: bool) -> bool:
    global _consent
    _consent = bool(enabled)
    sync_capture_handlers()
    return _consent


@persistent
def _openclaw_undo_post(scene, depsgraph=None):
    _edit_recorder.record_undo("undo")


@persistent
def _openclaw_redo_post(scene, depsgraph=None):
    _edit_recorder.record_undo("redo")


@persistent
def _openclaw_depsgraph_post(scene, depsgraph=None):
    _edit_recorder.poll_operators()


_CAPTURE_HANDLERS = [
    (bpy.app.handlers.undo_post, _openclaw_undo_post),
    (bpy.app.handlers.redo_post, _openclaw_redo_post),
    (bpy.app.handlers.depsgraph_update_post, _openclaw_depsgraph_post),
]


def sync_capture_handlers() -> bool:
    """Attach capture handlers only while consent is on; detach otherwise."""
    try:
        for handler_list, fn in _CAPTURE_HANDLERS:
            if _consent:
                if fn not in handler_list:
                    handler_list.append(fn)
            else:
                if fn in handler_list:
                    handler_list.remove(fn)
        return _consent
    except Exception as e:
        print(f"[OpenClaw] Human-activity handler sync failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Bridge handlers
# ---------------------------------------------------------------------------

def handle_drain_human_activity(params):
    """Return artist-originated events buffered since the last drain.

    Consent is enforced here as well as MCP-side: with consent off the
    buffer is cleared and nothing is returned, so events never accumulate
    for an artist who has not opted in. (Upstream semantics, preserved.)
    """
    try:
        if not consent_enabled():
            get_edit_recorder().drain()
            return {"events": [], "consent": False,
                    "note": "human-activity recording is OFF (consent not given); buffer cleared"}
        return {"events": get_edit_recorder().drain(), "consent": True,
                "provenance": "artist-live"}
    except Exception as e:
        return {"error": str(e)}


def handle_human_activity_status(params):
    return {
        "consent": consent_enabled(),
        "buffered_events": len(get_edit_recorder()._events),
        "handlers_attached": all(fn in lst for lst, fn in _CAPTURE_HANDLERS) if consent_enabled() else False,
        "provenance": "artist-live",
        "note": ("Recorder learns FORWARD from live sessions only; it cannot "
                 "recover past work. Past work is learned from .blend files."),
    }


def handle_set_human_activity_consent(params):
    """Enable/disable recording. The MCP side may only call this after the
    artist has explicitly opted in (or out) — never silently."""
    enabled = bool((params or {}).get("enabled", False))
    state = set_consent(enabled)
    return {"consent": state}


HUMAN_ACTIVITY_HANDLERS = {
    "drain_human_activity": handle_drain_human_activity,
    "human_activity_status": handle_human_activity_status,
    "set_human_activity_consent": handle_set_human_activity_consent,
}

# Attach at import only if the environment opted in before Blender started.
if _consent:
    sync_capture_handlers()
