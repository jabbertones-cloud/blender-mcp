"""Offline regression checks for packaged Blender outcome guides."""
from server.workflow_guides import get_workflow_guide, list_workflow_guides


def test_all_guides_exist_and_have_failure_policy():
    guides = list_workflow_guides()
    assert len(guides) == 9
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
