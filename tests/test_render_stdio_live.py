"""External MCP SDK client proves background render stays inside five-tool router."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.getenv('BLENDER_RENDER_E2E') != '1', reason='requires isolated Redis AOF broker and native Blender')
def test_real_sdk_client_queues_and_inspects_native_render(isolated_render_broker):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    root=Path(__file__).resolve().parents[1]
    scene=Path(os.environ['BLENDER_RENDER_TEST_SCENE'])
    digest=hashlib.sha256(scene.read_bytes()).hexdigest()

    async def run():
        server=StdioServerParameters(command=sys.executable,args=[str(root/'server/blender_mcp_guided.py')],env=dict(os.environ,PYTHONPATH=str(root)))
        async with stdio_client(server) as streams:
            async with ClientSession(*streams) as client:
                await client.initialize()
                tools=await client.list_tools()
                assert len(tools.tools)==5
                r=await client.call_tool('router_set_goal',{'input':{'goal':'queue a background render of a saved scene'}})
                assert not r.isError and 'workflow.render_enqueue' in str(r.structuredContent or json.loads(r.content[0].text))
                r=await client.call_tool('get_capability_schema',{'input':{'key':'workflow.render_enqueue'}})
                assert not r.isError and 'scene_path' in str(r.structuredContent or json.loads(r.content[0].text))
                r=await client.call_tool('execute_capability',{'input':{'key':'workflow.render_enqueue','arguments':{'scene_path':str(scene),'preview':True}}})
                assert not r.isError,r
                queued=r.structuredContent or json.loads(r.content[0].text)
                assert queued['status']=='queued',queued
                job=queued['job_id']
                denied=await client.call_tool('execute_capability',{'input':{'key':'workflow.render_enqueue','arguments':{'scene_path':'/tmp/outside-workspace.blend'}}})
                bad=denied.structuredContent or json.loads(denied.content[0].text)
                assert bad['status']=='blocked',bad
                worker=subprocess.run([str(Path(sys.executable).with_name('rq')),'worker','blender-mcp-render-v1','--burst',
                                        '--url',os.environ['BLENDER_RENDER_REDIS_URL'],
                                        '--serializer','rq.serializers.JSONSerializer'],cwd=str(root),
                                       env=dict(os.environ,PYTHONPATH=str(root)),capture_output=True,text=True,timeout=90)
                assert worker.returncode==0,worker.stdout[-1500:]+worker.stderr[-1500:]
                r=await client.call_tool('execute_capability',{'input':{'key':'workflow.render_status','arguments':{'job_id':job}}})
                assert not r.isError,r
                finished=r.structuredContent or json.loads(r.content[0].text)
                assert finished['status']=='finished',finished
                artifact=Path(finished['render']['path'])
                assert artifact.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
                return job
    job=asyncio.run(run())
    assert job and hashlib.sha256(scene.read_bytes()).hexdigest()==digest
