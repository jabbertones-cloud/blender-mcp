from server.quality_loop import run_quality_loop


def test_quality_loop_repairs_missing_camera_after_setup():
    reviews = [
        {"status": "fail", "findings": [{"code": "NO_CAMERA", "severity": "error"}]},
        {"status": "review_required", "findings": [{"code": "AESTHETIC_REVIEW", "severity": "review"}]},
    ]
    calls = []

    def review_once():
        return reviews.pop(0)

    def execute(capability, arguments):
        calls.append((capability, arguments))
        return {"status": "ok"}

    out = run_quality_loop(
        workflow="workflow.product_hero",
        target_object="Bottle",
        review_once=review_once,
        execute_canonical=execute,
    )

    assert out["status"] == "review_required"
    assert out["repair_count"] == 1
    assert calls == [("product.camera", {"style": "hero_reveal", "target_object": "Bottle"})]


def test_quality_loop_repairs_missing_lights_after_setup():
    reviews = [
        {"status": "fail", "findings": [{"code": "NO_LIGHTS", "severity": "error"}]},
        {"status": "review_required", "findings": [{"code": "AESTHETIC_REVIEW", "severity": "review"}]},
    ]
    calls = []

    out = run_quality_loop(
        workflow="workflow.product_hero",
        target_object="Bottle",
        review_once=lambda: reviews.pop(0),
        execute_canonical=lambda capability, arguments: calls.append((capability, arguments)) or {"status": "ok"},
    )

    assert out["status"] == "review_required"
    assert out["repair_count"] == 1
    assert calls == [("product.lighting", {"preset": "product_studio", "shadow_catcher": True})]


def test_quality_loop_never_repairs_review_findings():
    calls = []
    out = run_quality_loop(
        workflow="workflow.product_hero",
        target_object="Bottle",
        review_once=lambda: {"status": "review_required", "findings": [{"code": "AESTHETIC_REVIEW", "severity": "review"}]},
        execute_canonical=lambda capability, arguments: calls.append((capability, arguments)) or {"status": "ok"},
    )
    assert out["status"] == "review_required"
    assert out["repair_count"] == 0
    assert calls == []


def test_quality_loop_respects_explicit_repair_budget():
    calls = []

    def review_once():
        return {"status": "fail", "findings": [{"code": "NO_PIXELS", "severity": "error"}]}

    out = run_quality_loop(
        workflow="workflow.product_hero",
        target_object="Bottle",
        review_once=review_once,
        execute_canonical=lambda capability, arguments: calls.append((capability, arguments)) or {"status": "ok"},
        max_repairs=2,
    )
    assert out["status"] == "fail"
    assert out["repair_count"] == 2
    assert out["repair_budget"] == 2
    # NO_PIXELS is an observation retry, never a scene mutation.
    assert calls == []
