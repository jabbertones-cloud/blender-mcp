"""RQ worker function. Jobs are acknowledged after their Blender subprocess finishes."""
from rq import get_current_job
from .render_job_paths import scene_path
from .render_job_cli import native_render


def render_saved_blend(path, preview=True):
    job = get_current_job()
    if job is None:
        raise RuntimeError('Render must run inside an RQ worker')
    scene = scene_path(path)
    job.meta['phase'] = 'rendering'
    job.save_meta()
    return native_render(scene, job.id, bool(preview))
