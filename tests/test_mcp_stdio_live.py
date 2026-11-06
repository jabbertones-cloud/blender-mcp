"""Real MCP SDK client proves the guided five-tool surface reaches Blender."""
import asyncio
import os
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv('BLENDER_E2E') != '1', reason='requires real graphical Blender bridge')
def test_real_mcp_client_discovery_to_scene_read():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    script=Path(__file__).resolve().parents[1] / 'server/blender_mcp_guided.py'

    async def run():
        params=StdioServerParameters(command=sys.executable,args=[str(script)],env=dict(os.environ))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                tools=await client.list_tools()
                assert {t.name for t in tools.tools} == {
                    'router_set_goal','router_get_status','search_capabilities',
                    'get_capability_schema','execute_capability'}
                calls=[('router_set_goal',{'input':{'goal':'product hero render'}},'product-shot'),
                       ('search_capabilities',{'input':{'query':'product hero render'}},'workflow.product_hero'),
                       ('get_capability_schema',{'input':{'key':'workflow.product_hero'}},'When to use'),
                       ('execute_capability',{'input':{'key':'scene.info','arguments':{}}},'scene_name')]
                for name,args,expected in calls:
                    response=await client.call_tool(name,args)
                    assert not response.isError,(name,response)
                    text=str(response.structuredContent or response.content)
                    assert expected in text,(name,text[:400])
    asyncio.run(run())
