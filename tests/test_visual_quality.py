from server.visual_quality import critique_visual_evidence


def test_no_pixels_is_hard_failure():
    report = critique_visual_evidence(scene={"objects": [{"name": "Bottle", "type": "MESH"}]}, viewport={"status": "ok"}, workflow="workflow.product_hero", target_object="Bottle")
    assert report["status"] == "fail"
    assert report["pixel_evidence"] is False
    assert "NO_PIXELS" in {row["code"] for row in report["findings"]}


def test_product_scene_requires_camera_and_lights():
    report = critique_visual_evidence(scene={"objects": [{"name": "Bottle", "type": "MESH"}]}, viewport={"base64": "pixels"}, workflow="workflow.product_hero", target_object="Bottle")
    codes = {row["code"] for row in report["findings"]}
    assert {"NO_CAMERA", "NO_LIGHTS"} <= codes
    assert report["status"] == "fail"


def test_complete_product_scene_requires_semantic_review_not_fake_aesthetic_pass():
    report = critique_visual_evidence(scene={"objects": [
        {"name": "Bottle", "type": "MESH"},
        {"name": "Camera", "type": "CAMERA"},
        {"name": "Key", "type": "LIGHT"},
    ]}, viewport={"data": {"base64": "pixels"}}, workflow="workflow.amazon_packshot", target_object="Bottle")
    assert report["status"] == "review_required"
    assert report["objective_score"] == 100
    assert "AMAZON_SEMANTIC_REVIEW" in {row["code"] for row in report["findings"]}


def test_missing_target_is_failure():
    report = critique_visual_evidence(scene={"objects": [
        {"name": "Camera", "type": "CAMERA"},
        {"name": "Key", "type": "LIGHT"},
    ]}, viewport={"base64": "pixels"}, workflow="workflow.product_hero", target_object="Bottle")
    assert report["status"] == "fail"
    assert "TARGET_MISSING" in {row["code"] for row in report["findings"]}
