from server.capability_executor import execute_canonical, execute_workflow


class FakeBridge:
    def __init__(self):
        self.calls = []

    def __call__(self, command, params=None):
        self.calls.append((command, params or {}))
        if command == "viewport_capture":
            return {"status": "ok", "image": "base64-test"}
        if command == "get_scene_info":
            return {"status": "ok", "objects": [{"name": "Bottle", "type": "MESH"}]}
        return {"status": "ok", "command": command}


def test_visual_atomic_capability_always_observes_after_mutation():
    bridge = FakeBridge()
    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0, "roughness": 0.1},
        bridge,
    )
    commands = [name for name, _ in bridge.calls]
    assert commands == ["set_material", "viewport_capture"]
    assert result["visual_check_required"] is True
    assert result["status"] == "ok"


def test_product_lighting_uses_wrapper_not_fake_bridge_command():
    bridge = FakeBridge()
    result = execute_canonical("product.lighting", {"preset": "cosmetics"}, bridge)
    commands = [name for name, _ in bridge.calls]
    assert commands[0] == "execute_python"
    assert "product_lighting" not in commands
    assert commands[-1] == "viewport_capture"
    assert result["status"] == "ok"


def test_product_hero_is_one_workflow_with_required_observations():
    bridge = FakeBridge()
    result = execute_workflow(
        "workflow.product_hero",
        {
            "object_name": "Bottle",
            "material": "clear_glass",
            "lighting": "cosmetics",
            "camera_style": "hero_reveal",
            "quality": "premium",
            "resolution": "square_1080",
            "auto_render": True,
        },
        bridge,
    )
    commands = [name for name, _ in bridge.calls]
    assert result["status"] == "ok"
    assert commands[0] == "get_scene_info"
    assert commands.count("viewport_capture") >= 5
    assert "product_lighting" not in commands
    assert "product_camera" not in commands
    assert "product_render_setup" not in commands
    assert commands[-2:] == ["render", "viewport_capture"]


def test_product_hero_rejects_object_name_code_injection():
    bridge = FakeBridge()
    try:
        execute_workflow("workflow.product_hero", {"object_name": 'Bottle\"); import os; #'}, bridge)
    except ValueError as exc:
        assert "unsupported characters" in str(exc)
    else:
        raise AssertionError("unsafe object name was accepted")
    assert bridge.calls == []
