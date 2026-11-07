"""Real M2 test: MCP enqueues an RQ job; separate worker runs native Blender CLI."""
import asyncio
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.getenv('BLENDER_RENDER_E2E') != '1',reason='needs dedicated AOF Redis and native Blender 5.x')
def test_mcp_worker_render_persists_result_across_processes():
    from server.capability_executor import execute_workflow
    from server.render_queue_api import status
    root=Path(os.environ['BLENDER_RENDER_ROOT'])
    scene=Path(os.environ['BLENDER_RENDER_TEST_SCENE'])
    digest=hashlib.sha256(scene.read_bytes()).hexdigest()
    out=execute_workflow('workflow.render_enqueue',{'scene_path':str(scene),'preview':True},lambda *_a,**_k: 1)
    assert out['status']=='queued',out
    project=str(Path(__file__).resolve().parents[1])
    proc=subprocess.run([str(Path(sys.executable).with_name('rq')),'worker','blender-mcp-render-v1','--burst',
                         '--url',os.environ['BLENDER_RENDER_REDIS_URL'],
                         '--serializer','rq.serializers.JSONSerializer'],
                        cwd=project,env=dict(os.environ,PYTHONPATH=project),capture_output=True,text=True,timeout=110)
    assert proc.returncode==0,proc.stdout[-1700:]+proc.stderr[-1700:]
    finished=status({'job_id':out['job_id']})
    assert finished['status']=='finished',finished
    output=Path(finished['render']['path'])
    assert output.is_relative_to(root) and output.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n'
    assert hashlib.sha256(scene.read_bytes()).hexdigest()==digest
