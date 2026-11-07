"""Use Blender's own background process and atomic artifact publication."""
import os
import subprocess
import tempfile
from pathlib import Path
from .render_job_paths import output_path


def native_render(scene, job_id, preview):
    final = output_path(job_id)
    if final.is_file() and final.open('rb').read(8) == b'\x89PNG\r\n\x1a\n':
        return {'path': str(final), 'bytes': final.stat().st_size, 'replayed': True}
    blender = os.getenv('BLENDER_RENDER_BIN') or os.getenv('BLENDER_QUALITY_BIN')
    if not blender or not Path(blender).is_file():
        raise ValueError('A configured Blender executable is required')
    fd, temp = tempfile.mkstemp(prefix=job_id + '-', suffix='.png', dir=final.parent)
    os.close(fd)
    Path(temp).unlink()
    try:
        env = {key: os.environ[key] for key in ('HOME', 'PATH', 'TMPDIR') if key in os.environ}
        env.update(BLENDER_MCP_RENDER_TEMP=temp, BLENDER_MCP_RENDER_PREVIEW='1' if preview else '0')
        script = str(Path(__file__).with_name('render_native_script.py'))
        process = subprocess.run([blender, '--background', '--factory-startup', '--disable-autoexec',
                                  '--python-exit-code', '1', str(scene), '--python', script],
                                 capture_output=True, text=True, timeout=600, env=env)
        if process.returncode or not Path(temp).is_file() or Path(temp).open('rb').read(8) != b'\x89PNG\r\n\x1a\n':
            raise RuntimeError(f'Blender render failed (exit={process.returncode})')
        os.replace(temp, final)
        return {'path': str(final), 'bytes': final.stat().st_size, 'replayed': False}
    finally:
        Path(temp).unlink(missing_ok=True)
