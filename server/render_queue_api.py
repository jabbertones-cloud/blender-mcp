"""RQ Redis status and submission, bound to the authorized local Blender workspace."""
import os
from urllib.parse import urlparse
from redis import Redis
from rq import Queue, Retry
from rq.job import Job
from rq.exceptions import NoSuchJobError
from rq.serializers import JSONSerializer
from .render_job_paths import scene_path, output_path
from .render_jobs_worker import render_saved_blend

def connection():
    uri = os.getenv('BLENDER_RENDER_REDIS_URL', 'redis://127.0.0.1:6399/0')
    parsed = urlparse(uri)
    if parsed.scheme != 'redis' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Render Redis must be a local unauthenticated instance')
    redis = Redis.from_url(uri, socket_connect_timeout=2, socket_timeout=2)
    redis.ping()
    return redis


def submit(args):
    scene = scene_path(args['scene_path'])
    queue = Queue('blender-mcp-render-v1', connection=connection(), serializer=JSONSerializer)
    job = queue.enqueue(render_saved_blend, str(scene), bool(args.get('preview', True)),
                        job_timeout=600, retry=Retry(max=1), result_ttl=86400, failure_ttl=86400)
    return {'status': 'queued', 'job_id': job.id, 'output_path': str(output_path(job.id)), 'preview': bool(args.get('preview', True))}


def status(args):
    path = output_path(args['job_id'])
    try:
        job = Job.fetch(args['job_id'], connection=connection(), serializer=JSONSerializer)
    except NoSuchJobError:
        return {'status': 'not_found', 'job_id': args['job_id']}
    state = job.get_status(refresh=True)
    response = {'status': str(getattr(state, 'value', state)), 'job_id': job.id, 'retries_left': job.retries_left}
    if response['status'] == 'finished' and path.is_file():
        response['render'] = job.return_value()
    return response
