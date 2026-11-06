"""Offline regression checks for packaged Blender outcome guides."""
from server.workflow_guides import get_workflow_guide, list_workflow_guides


def test_all_guides_exist_and_have_failure_policy():
    guides = list_workflow_guides()
    assert len(guides) == 18
    for guide in guides:
        result = get_workflow_guide(guide["key"])
        assert "error" not in result
        assert "Failure policy" in result["content"]


def test_product_intent_finds_product_guide():
    matches = list_workflow_guides("premium product shot")
    assert any(row["key"] == "product-shot" for row in matches)


def test_unknown_and_path_traversal_fail_closed():
    for key in ("../README.md", "/etc/passwd", "unknown"):
        result = get_workflow_guide(key)
        assert result["code"] == "GUIDE_NOT_FOUND"


def test_coverage_for_every_executable_canonical_capability_and_workflow():
    from server.capability_registry import registry
    from server.capability_executor import WORKFLOW_SCHEMAS
    from server.workflow_guides import guide_for_capability
    for key in registry.keys():
        capability = registry.resolve_tool(key)
        guide = guide_for_capability(key, capability.family)
        assert guide is not None and "When" in guide["content"], key
    for key in WORKFLOW_SCHEMAS:
        guide = guide_for_capability(key, "workflow")
        assert guide is not None and "When" in guide["content"], key


def test_missing_workflows_are_now_discoverable_with_specific_intents():
    from server.workflow_rank import workflow_match
    cases = {
        "attach reference photo as plate": "workflow.reference_attach",
        "fix reference mismatch": "workflow.reference_correct",
        "execute a sequence of canonical blender capabilities": "workflow.sequence",
    }
    for goal, expected in cases.items():
        assert expected in {row["key"] for row in workflow_match(goal)}, goal
    assert "workflow.sequence" not in {row["key"] for row in workflow_match("make a product hero")}
