from server.capability_executor import execute_canonical, execute_workflow


class FakeBridge:
    def __init__(self):
        self.calls = []
        self.objects = [{"name": "Bottle", "type": "MESH"}]

    def __call__(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == "viewport_capture":
            return {"status": "ok", "image": "base64-test"}
        if command == "get_scene_info":
            return {"status": "ok", "objects": list(self.objects)}
        if command == "create_object":
            name = params.get("name") or "Cube"
            self.objects.append({"name": name, "type": "MESH"})
            return {"status": "ok", "name": name}
        if command == "delete_object":
            names = set(params.get("names") or [])
            self.objects = [row for row in self.objects if row["name"] not in names]
            return {"status": "ok"}
        if command == "forensic_scene":
            return {"status": "ok", "action": params.get("action")}
        return {"status": "ok", "command": command}


def test_visual_atomic_capability_always_observes_after_mutation():
    bridge = FakeBridge()
    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0, "roughness": 0.1},
        bridge,
    )
    commands = [name for name, _ in bridge.calls]
    assert commands[0] == "get_scene_info"
    assert commands[-2:] == ["set_material", "viewport_capture"] or (
        "set_material" in commands and commands[-1] == "viewport_capture"
    )
    assert result["visual_check_required"] is True
    assert result["status"] == "ok"
    assert "scene_delta" in result


def test_product_lighting_uses_wrapper_not_fake_bridge_command():
    bridge = FakeBridge()
    result = execute_canonical("product.lighting", {"preset": "cosmetics"}, bridge)
    commands = [name for name, _ in bridge.calls]
    assert "execute_python" in commands
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
    assert "render" in commands
    assert commands[-1] == "viewport_capture"


def test_product_hero_rejects_object_name_code_injection():
    bridge = FakeBridge()
    try:
        execute_workflow("workflow.product_hero", {"object_name": 'Bottle\"); import os; #'}, bridge)
    except ValueError as exc:
        assert "unsupported characters" in str(exc)
    else:
        raise AssertionError("unsafe object name was accepted")
    assert bridge.calls == []


def test_create_object_fails_closed_without_scene_delta():
    class NoDeltaBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "get_scene_info":
                return {"status": "ok", "objects": [{"name": "Bottle", "type": "MESH"}]}
            if command == "create_object":
                return {"status": "ok", "name": "Ghost"}
            return {"status": "ok"}

    result = execute_canonical("scene.create_object", {"type": "cube", "name": "Ghost"}, NoDeltaBridge())
    assert result["status"] == "postcondition_failed"


def test_turntable_workflow_uses_turntable_camera_style():
    bridge = FakeBridge()
    result = execute_workflow("workflow.turntable", {"object_name": "Bottle", "auto_render": False}, bridge)
    assert result["status"] == "ok"
    camera_calls = [params for command, params in bridge.calls if command == "execute_python"]
    assert camera_calls, bridge.calls
    assert any("turntable" in str(params.get("code", "")).lower() or "Turntable" in str(params.get("code", "")) for params in camera_calls)


def test_missing_viewport_pixels_fail_visual_postcondition():
    class BlindBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "viewport_capture":
                return {"status": "ok"}
            if command == "get_scene_info":
                return {"status": "ok", "objects": list(self.objects)}
            return {"status": "ok"}

    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0},
        BlindBridge(),
    )
    assert result["status"] == "postcondition_failed"


def test_amazon_packshot_forces_square_premium_setup():
    bridge = FakeBridge()
    result = execute_workflow("workflow.amazon_packshot", {"object_name": "Bottle"}, bridge)
    assert result["status"] == "ok"
    assert result["workflow"] == "workflow.amazon_packshot"
    assert "render" in [name for name, _ in bridge.calls]


def test_forensic_workflow_hits_forensic_bridge_command():
    bridge = FakeBridge()
    result = execute_workflow("workflow.forensic_recon", {"action": "build_road"}, bridge)
    assert result["status"] == "ok"
    assert ("forensic_scene", {"action": "build_road"}) in bridge.calls
