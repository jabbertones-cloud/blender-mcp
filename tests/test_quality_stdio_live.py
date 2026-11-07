"""Live five-tool MCP client audits a failed and repaired saved Blender scene."""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(os.getenv('BLENDER_QUALITY_E2E') != '1', reason='requires two real QA fixture scenes')
def test_mcp_technical_quality_failure_to_fix():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    before = Path(os.environ['BLENDER_QUALITY_TEST_SCENE'])
    fixed = Path(os.environ['BLENDER_QUALITY_TEST_FIXED_SCENE'])
    digest = hashlib.sha256(before.read_bytes()).hexdigest()
    script = Path(__file__).resolve().parents[1] / 'server/blender_mcp_guided.py'

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(script)], env=dict(os.environ))
        async with stdio_client(params) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                tools = await client.list_tools()
                assert len(tools.tools) == 5
                schema = await client.call_tool('get_capability_schema', {'input': {'key': 'workflow.quality_inspect'}})
                assert not schema.isError
                contract = schema.structuredContent or json.loads(schema.content[0].text)
                assert 'read-only' in str(contract['capability']['description']).lower()
                for path, expected_pass in ((before, False), (fixed, True)):
                    response = await client.call_tool('execute_capability', {
                        'input': {'key': 'workflow.quality_inspect', 'arguments': {'scene_path': str(path)}}})
                    assert not response.isError, response
                    result = response.structuredContent or json.loads(response.content[0].text)
                    assert result['workflow'] == 'workflow.quality_inspect'
                    assert result['technical_pass'] is expected_pass, result
                    assert 'python' not in str(result).lower()
                    if not expected_pass:
                        assert 'materials' in [g['id'] for g in result['failed_gates']]
                    else:
                        assert result['status'] in {'ok', 'review_required'}
                return True
    assert asyncio.run(run())
    assert hashlib.sha256(before.read_bytes()).hexdigest() == digest
