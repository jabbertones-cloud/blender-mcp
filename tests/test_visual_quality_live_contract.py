from server.visual_quality import critique_visual_evidence


class SceneBridge:
    def __init__(self):
        self.calls = []

    def __call__(self, command, params=None):
        self.calls.append((command, params or {}))
        if command == "get_scene_info":
            return {"objects": [
                {"name": "Bottle", "type": "MESH"},
                {"name": "Camera", "type": "CAMERA"},
                {"name": "Key", "type": "LIGHT"},
            ]}
        if command == "viewport_capture":
            return {"base64": "pixels"}
        raise AssertionError(command)


def test_critic_contract_uses_scene_and_model_visible_pixels():
    bridge = SceneBridge()
    scene = bridge("get_scene_info", {})
    viewport = bridge("viewport_capture", {"base64": True})
    report = critique_visual_evidence(scene=scene, viewport=viewport, workflow="workflow.amazon_packshot", target_object="Bottle")
    assert bridge.calls == [("get_scene_info", {}), ("viewport_capture", {"base64": True})]
    assert report["pixel_evidence"] is True
    assert report["status"] == "review_required"
