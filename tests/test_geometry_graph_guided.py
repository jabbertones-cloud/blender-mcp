"""Portable policy tests; real Blender dogfood runs separately on M3."""
import json
from pathlib import Path
from server.capability_registry import registry

def test_graph_search_and_canonical_capability():
    for request in ("rebuild node graph from blend", "spray nodes", "procedural reconstruction"):
        matches = registry.search_capabilities(request, limit=5)
        assert matches and matches[0]["key"] == "model.geometry_nodes"

def test_build_graph_requires_bounded_structured_spec():
    cap = registry.resolve_tool("model.geometry_nodes")
    schema = cap.input_schema
    assert "spec" in schema["properties"]
    assert schema["properties"]["spec"]["additionalProperties"] is False
    node_schema = schema["properties"]["spec"]["properties"]["nodes"]
    link_schema = schema["properties"]["spec"]["properties"]["links"]
    assert node_schema["maxItems"] == 200
    assert link_schema["maxItems"] == 500

def test_no_raw_python_or_new_mcp_public_tool():
    repo = Path(__file__).resolve().parents[1]
    addon = (repo / "blender_addon/openclaw_blender_bridge.py").read_text()
    assert "from .graph_transaction import build_graph" in addon
    assert 'if action == "build_graph"' in addon
    guided = (repo / "server/blender_mcp_guided.py").read_text()
    assert "execute_capability" in guided and "search_capabilities" in guided
    vendor = (repo / "blender_addon/blenderwright_graph_donor.provenance.json")
    data = json.loads(vendor.read_text())
    assert data["license"] == "MIT"
    assert len(data["commit"]) == 40
