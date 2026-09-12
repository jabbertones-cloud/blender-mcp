import pytest
from unittest.mock import patch
from server.capability_executor import execute_canonical

class MockRegistry:
    def resolve_tool(self, key):
        class Cap:
            def __init__(self, key):
                self.key = key
                self.bridge_command = key
                self.mutates_scene = True
                self.family = "product"
        return Cap(key)

    def execute(self, key, args, send_command):
        return {"status": "ok"}

@pytest.fixture
def mock_executor_globals(monkeypatch):
    import server.capability_executor as cap_exec
    monkeypatch.setattr(cap_exec, "registry", MockRegistry())
    monkeypatch.setattr(cap_exec, "_CREATE_KEYS", set())
    monkeypatch.setattr(cap_exec, "_DELETE_KEYS", set())

def test_camera_diagnostics_unavailable(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {"error": "unknown command"}
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "unavailable or malformed" in res["error"]

def test_camera_wrong_active_camera(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "WrongCamera", "owned": True, "role": "product_camera"}
            }
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "does not match created camera" in res["error"]

def test_camera_wrong_role(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "role": "wrong_role"}
            }
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "wrong_role" in res["error"]

def test_camera_lens_mismatch(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "role": "product_camera", "lens_mm": 35.0, "dof_enabled": True}
            }
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target", "focal_length": 50.0, "use_dof": True}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "lens" in res["error"]

def test_camera_dof_mismatch(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "role": "product_camera", "lens_mm": 50.0, "dof_enabled": False}
            }
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target", "focal_length": 50.0, "use_dof": True}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "dof" in res["error"]

def test_camera_target_mismatch(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "role": "product_camera", "lens_mm": 50.0, "dof_enabled": True, "focus_object": "WrongTarget"}
            }
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target", "focal_length": 50.0, "use_dof": True}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "focus_object" in res["error"]

def test_camera_success(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "role": "product_camera", "lens_mm": 50.0, "dof_enabled": True, "focus_object": "Target"}
            }
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target", "focal_length": 50.0, "use_dof": True}, send_command, observe_visual=False)
    assert res["status"] == "ok"

def test_lighting_unrelated_owned_light(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "lights": [
                    {"name": "SomeRandomLight", "owned": True, "role": "product_light", "type": "AREA", "energy": 600.0}
                ]
            }
        return {"status": "ok"}

    res = execute_canonical("product.lighting", {"preset": "product_studio"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "missing or not owned" in res["error"]

def test_lighting_missing_expected_role(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "lights": [
                    {"name": "OpenClaw_Key", "owned": True, "role": "wrong_role", "type": "AREA", "energy": 600.0},
                    {"name": "OpenClaw_Fill", "owned": True, "role": "product_light", "type": "AREA", "energy": 250.0},
                    {"name": "OpenClaw_Back", "owned": True, "role": "product_light", "type": "AREA", "energy": 350.0},
                ]
            }
        return {"status": "ok"}

    res = execute_canonical("product.lighting", {"preset": "product_studio"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "wrong role" in res["error"]

def test_lighting_wrong_energy(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "lights": [
                    {"name": "OpenClaw_Key", "owned": True, "role": "product_light", "type": "AREA", "energy": 10.0},
                    {"name": "OpenClaw_Fill", "owned": True, "role": "product_light", "type": "AREA", "energy": 250.0},
                    {"name": "OpenClaw_Back", "owned": True, "role": "product_light", "type": "AREA", "energy": 350.0},
                ]
            }
        return {"status": "ok"}

    res = execute_canonical("product.lighting", {"preset": "product_studio"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "wrong energy" in res["error"]

def test_lighting_success(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "lights": [
                    {"name": "OpenClaw_Key", "owned": True, "role": "product_light", "type": "AREA", "energy": 600.0},
                    {"name": "OpenClaw_Fill", "owned": True, "role": "product_light", "type": "AREA", "energy": 250.0},
                    {"name": "OpenClaw_Back", "owned": True, "role": "product_light", "type": "AREA", "energy": 350.0},
                ]
            }
        return {"status": "ok"}

    res = execute_canonical("product.lighting", {"preset": "product_studio"}, send_command, observe_visual=False)
    assert res["status"] == "ok"
