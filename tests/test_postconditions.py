import pytest
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

def test_camera_false_positive(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {"camera_present": False}
        if cmd == "get_scene_info":
            return {"objects": []}
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "no camera found" in res["error"]

def test_camera_success(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "lens_mm": 50.0, "dof_enabled": True}
            }
        if cmd == "get_scene_info":
            return {"objects": []}
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target", "focal_length": 50.0, "use_dof": True}, send_command, observe_visual=False)
    assert res["status"] == "ok"

def test_camera_lens_mismatch(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "camera_present": True,
                "camera": {"name": "Camera", "owned": True, "lens_mm": 35.0, "dof_enabled": True}
            }
        if cmd == "get_scene_info":
            return {"objects": []}
        return {"status": "ok", "camera": "Camera"}

    res = execute_canonical("product.camera", {"target_object": "Target", "focal_length": 50.0, "use_dof": True}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "lens" in res["error"]

def test_lighting_success(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "lights": [
                    {"name": "Light1", "owned": True},
                    {"name": "Light2", "owned": True}
                ]
            }
        if cmd == "get_scene_info":
            return {"objects": []}
        return {"status": "ok", "lights": ["Light1", "Light2"]}

    res = execute_canonical("product.lighting", {"preset": "studio"}, send_command, observe_visual=False)
    assert res["status"] == "ok"

def test_lighting_missing_lights(mock_executor_globals):
    def send_command(cmd, args):
        if cmd == "scene_diagnostics":
            return {
                "lights": [
                    {"name": "Light1", "owned": True}
                ]
            }
        if cmd == "get_scene_info":
            return {"objects": []}
        return {"status": "ok", "lights": ["Light1", "Light2"]}

    res = execute_canonical("product.lighting", {"preset": "studio"}, send_command, observe_visual=False)
    assert res["status"] == "postcondition_failed"
    assert "expected lights missing" in res["error"]
