from server.quality_loop import run_quality_loop
from server.quality_repair import next_objective_repair, repair_for_finding


def finding(code, severity="error"):
    return {"code": code, "severity": severity}


def test_review_findings_are_never_auto_repaired():
    action = repair_for_finding(finding("AESTHETIC_REVIEW", "review"), workflow="workflow.product_hero", target_object="Bottle")
    assert action.repairable is False
    assert action.capability is None


def test_target_missing_fails_closed_before_other_mutation():
    review = {"status": "fail", "findings": [finding("TARGET_MISSING"), finding("NO_CAMERA")]}
    action = next_objective_repair(review, workflow="workflow.product_hero", target_object="Bottle")
    assert action is not None and action.repairable is False


def test_loop_repairs_one_finding_then_recaptures():
    state = {"camera": False, "reviews": 0, "mutations": []}
    def review():
        state["reviews"] += 1
        if not state["camera"]:
            return {"status": "fail", "findings": [finding("NO_CAMERA")]}
        return {"status": "review_required", "findings": [finding("AESTHETIC_REVIEW", "review")], "pixel_evidence": True}
    def execute(key, args):
        state["mutations"].append((key, args))
        assert key == "product.camera"
        state["camera"] = True
        return {"status": "ok"}
    out = run_quality_loop(workflow="workflow.product_hero", target_object="Bottle", review_once=review, execute_canonical=execute, max_repairs=3)
    assert out["status"] == "review_required"
    assert state["reviews"] == 2
    assert len(state["mutations"]) == 1
    assert out["repair_count"] == 1


def test_loop_stops_at_budget():
    def review():
        return {"status": "fail", "findings": [finding("NO_CAMERA")]}
    calls = []
    def execute(key, args):
        calls.append(key)
        return {"status": "ok"}
    out = run_quality_loop(workflow="workflow.product_hero", target_object="Bottle", review_once=review, execute_canonical=execute, max_repairs=2)
    assert out["status"] == "fail"
    assert calls == ["product.camera", "product.camera"]
    assert out["repair_count"] == 2
