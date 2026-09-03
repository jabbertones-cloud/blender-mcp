from server.visual_quality import critique_visual_evidence


class SceneBridge:
    def __init__(self):
        self.calls = []

    def __call__(self, command, params=None):
        self.calls.append((command, params or {}))
        if command == "scene_diagnostics":
            return {"objects": [
                {"name": "Bottle", "type": "MESH"},
                {"name": "Camera", "type": "CAMERA"},
                {"name": "Key", "type": "LIGHT"},
            ], "camera_present": True, "light_count": 1}
        if command == "viewport_capture":
            return {"base64": "pixels"}
        raise AssertionError(command)


def test_critic_contract_uses_scene_and_model_visible_pixels():
    bridge = SceneBridge()
    diagnostics = bridge("scene_diagnostics", {})
    viewport = bridge("viewport_capture", {"base64": True})
    report = critique_visual_evidence(
        scene=diagnostics,
        viewport=viewport,
        diagnostics=diagnostics,
        workflow="workflow.amazon_packshot",
        target_object="Bottle",
    )
    assert bridge.calls == [("scene_diagnostics", {}), ("viewport_capture", {"base64": True})]
    assert report["pixel_evidence"] is True
    assert report["status"] == "review_required"
