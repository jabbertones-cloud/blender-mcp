from server.blender_mcp_guided import _workflow_match


def test_guided_workflow_match_returns_ranked_matches():
    amazon = _workflow_match("make an Amazon main listing image")
    assert amazon
    assert amazon[0]["key"] == "workflow.amazon_packshot"

    turntable = _workflow_match("make a 360 product turntable")
    assert any(row["key"] == "workflow.turntable" for row in turntable)

    forensic = _workflow_match("build a forensic accident reconstruction")
    assert any(row["key"] == "workflow.forensic_recon" for row in forensic)


def test_guided_workflow_match_empty_query_is_empty_list():
    assert _workflow_match("") == []
