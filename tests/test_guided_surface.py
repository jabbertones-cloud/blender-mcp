import asyncio

from server.blender_mcp_guided import mcp


EXPECTED_GUIDED_TOOLS = {
    "router_set_goal",
    "router_get_status",
    "search_capabilities",
    "get_capability_schema",
    "execute_capability",
}


def test_guided_server_exposes_exactly_five_model_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == EXPECTED_GUIDED_TOOLS
    assert len(tools) == 5
