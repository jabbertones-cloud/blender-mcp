import pytest
import sys
from unittest.mock import MagicMock
import threading

sys.modules['bpy'] = MagicMock()
sys.modules['mathutils'] = MagicMock()

import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import blender_addon.openclaw_blender_bridge as obb

def test_callback_exception_sets_event():
    data = {"command": "test", "id": "123"}
    response_event = threading.Event()
    response_holder = [None]

    original_process_command = obb.process_command

    def fake_process_command(d):
        raise RuntimeError("Catastrophic Blender crash")

    try:
        obb.process_command = fake_process_command

        def callback(d=data, evt=response_event, holder=response_holder):
            try:
                holder[0] = obb.process_command(d)
            except Exception as e:
                holder[0] = {"id": d.get("id", "unknown"), "error": f"Bridge internal error: {str(e)}"}
            finally:
                evt.set()

        callback()

        assert response_event.is_set(), "Event must be set even if process_command raises an exception"
        assert response_holder[0] is not None
        assert "Bridge internal error" in response_holder[0]["error"]
    finally:
        obb.process_command = original_process_command


def test_falsy_response_not_timeout():
    response_holder_falsey = [{}]
    resp1 = response_holder_falsey[0] if response_holder_falsey[0] is not None else {"error": "Timeout waiting for Blender execution"}
    assert resp1 == {}

    response_holder_none = [None]
    resp2 = response_holder_none[0] if response_holder_none[0] is not None else {"error": "Timeout waiting for Blender execution"}
    assert "Timeout" in resp2["error"]
