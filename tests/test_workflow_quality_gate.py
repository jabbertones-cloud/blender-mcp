from server.capability_executor import execute_workflow


class FakeBridge:
    def __init__(self, *, include_camera=True, include_light=True, pixels=True):
        self.include_camera = include_camera
        self.include_light = include_light
        self.pixels = pixels

    def __call__(self, command, params):
        if command == "get_scene_info":
            objects = [{"name": "Bottle", "type": "MESH"}]
            if self.include_camera:
                objects.append({"name": "Camera", "type": "CAMERA"})
            if self.include_light:
                objects.append({"name": "Key", "type": "LIGHT"})
            return {"objects": objects}
        if command == "viewport_capture":
            return {"base64": "pixels" if self.pixels else ""}
        if command in {"execute_python", "render"}:
            return {"status": "ok"}
        return {"status": "ok"}


def test_product_hero_cannot_finish_plain_ok_when_semantic_review_is_required():
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, FakeBridge())
    assert out["status"] == "review_required"
    assert out["quality_review"]["pixel_evidence"] is True
    assert out["quality_review"]["objective_score"] == 100
    assert any(row["code"] == "AESTHETIC_REVIEW" for row in out["quality_review"]["findings"])


def test_amazon_packshot_cannot_finish_plain_ok_before_semantic_review():
    out = execute_workflow("workflow.amazon_packshot", {"object_name": "Bottle"}, FakeBridge())
    assert out["status"] == "review_required"
    assert any(row["code"] == "AMAZON_SEMANTIC_REVIEW" for row in out["quality_review"]["findings"])


def test_product_workflow_fails_objective_quality_gate_without_camera():
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, FakeBridge(include_camera=False))
    assert out["status"] == "fail"
    assert any(row["code"] == "NO_CAMERA" for row in out["quality_review"]["findings"])


def test_turntable_is_also_quality_gated():
    out = execute_workflow("workflow.turntable", {"object_name": "Bottle"}, FakeBridge())
    assert out["status"] == "review_required"
    assert out["quality_review"]["objective_score"] == 100
