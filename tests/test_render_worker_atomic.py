"""Native render jobs cannot overwrite user paths or publish partial PNGs."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import pytest
from PIL import Image
from server.render_job_cli import native_render
from server.render_job_paths import output_path


def test_existing_job_output_is_idempotent(monkeypatch,tmp_path):
    monkeypatch.setenv('BLENDER_RENDER_ROOT',str(tmp_path))
    job=str(uuid4());dest=output_path(job)
    Image.new('RGB', (2, 2), (10, 20, 30)).save(dest)
    monkeypatch.setattr('server.render_job_cli.subprocess.run',lambda *_a,**_k: (_ for _ in ()).throw(AssertionError('must not rerender')))
    result=native_render(tmp_path/'unused.blend',job,True)
    assert result['replayed'] and result['bytes']==len(dest.read_bytes())


def test_failed_render_does_not_publish_partial_output(monkeypatch,tmp_path):
    monkeypatch.setenv('BLENDER_RENDER_ROOT',str(tmp_path))
    monkeypatch.setenv('BLENDER_RENDER_BIN',str(Path(__file__).resolve()))
    job=str(uuid4());dest=output_path(job)
    def fail(_argv,**_kwargs):
        return SimpleNamespace(returncode=17,stdout='',stderr='Blender fault')
    monkeypatch.setattr('server.render_job_cli.subprocess.run',fail)
    with pytest.raises(RuntimeError,match='render failed'):
        native_render(tmp_path/'unused.blend',job,True)
    assert not dest.exists()
    assert not list(dest.parent.glob(job+'-*.png'))
