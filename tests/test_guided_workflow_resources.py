"""Contract tests for guided MCP resource registration and workflow guidance."""
import ast
from pathlib import Path

from server.workflow_guides import get_workflow_guide, list_workflow_guides


def test_guided_server_exposes_guide_resources_without_new_tools():
    source = Path("server/blender_mcp_guided.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    resource_uris = []
    tool_names = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if isinstance(decorator.func, ast.Attribute) and isinstance(decorator.func.value, ast.Name) and decorator.func.value.id == "mcp":
                if decorator.func.attr == "resource" and decorator.args and isinstance(decorator.args[0], ast.Constant):
                    resource_uris.append(decorator.args[0].value)
                if decorator.func.attr == "tool":
                    for kw in decorator.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                            tool_names.append(kw.value.value)
    assert "blender://guides" in resource_uris
    assert "blender://guides/{key}" in resource_uris
    assert set(tool_names) == {"router_set_goal", "router_get_status", "search_capabilities", "get_capability_schema", "execute_capability"}


def test_every_guide_has_real_content():
    for row in list_workflow_guides():
        guide = get_workflow_guide(row["key"])
        assert guide["content"].startswith("# ")
        assert len(guide["content"]) > 200
        assert "Failure policy" in guide["content"]


def test_guide_names_cannot_escape_package():
    for key in ("..", "../../server/blender_mcp_guided.py", "modeling.md", "MODELing", ""):
        assert get_workflow_guide(key)["code"] == "GUIDE_NOT_FOUND"
