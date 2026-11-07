"""Real RQ worker-child hard-exit recovery with built-in retry and JSON serializer."""
import os
import subprocess
import sys
from pathlib import Path
import pytest


def crash_once(marker):
    flag=Path(marker)
    if not flag.exists():
        flag.write_text('first work-horse started')
        os._exit(17)
    return {'state':'recovered','marker':str(flag)}


@pytest.mark.skipif(os.getenv('BLENDER_RENDER_E2E')!='1', reason='needs dedicated Redis')
def test_rq_retries_abrupt_child_exit_same_job_id(tmp_path, isolated_render_broker):
    from redis import Redis
    from rq import Queue, Retry
    from rq.serializers import JSONSerializer
    from rq.job import Job
    url=os.environ['BLENDER_RENDER_REDIS_URL']
    queue=Queue('blender-mcp-render-fault-v1',connection=Redis.from_url(url),serializer=JSONSerializer)
    marker=tmp_path/'attempt.txt'
    job=queue.enqueue(crash_once,str(marker),job_timeout=25,retry=Retry(max=1),result_ttl=200)
    project=Path(__file__).resolve().parents[1]
    env=dict(os.environ,PYTHONPATH=str(project/'tests')+os.pathsep+str(project))
    command=[str(Path(sys.executable).with_name('rq')),'worker',queue.name,'--burst','--url',url,
             '--serializer','rq.serializers.JSONSerializer']
    proc=subprocess.run(command,cwd=project,env=env,capture_output=True,text=True,timeout=70)
    assert proc.returncode==0,proc.stdout[-1300:]+proc.stderr[-1300:]
    saved=Job.fetch(job.id,connection=queue.connection,serializer=JSONSerializer)
    assert saved.get_status()=='finished' and saved.return_value()['state']=='recovered'
    assert saved.retries_left==0 and marker.is_file()
