"""Corrupt output must not be replayed, published, or reported as finished."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from PIL import Image
import pytest

from server.render_artifact import valid_png
from server.render_job_cli import native_render
from server.render_job_paths import output_path
from server.render_queue_api import status


@pytest.mark.parametrize("damage", ["signature", "truncated", "crc", "wrong_format"])
def test_full_png_validation_rejects_damage(tmp_path, damage):
    path = tmp_path / "render.png"
    Image.new("RGBA", (16, 16), (20, 40, 60, 255)).save(path)
    content = path.read_bytes()
    if damage == "signature":
        path.write_bytes(b"\x89PNG\r\n\x1a\nCORRUPT_NOT_IMAGE")
    elif damage == "truncated":
        path.write_bytes(content[:len(content) // 2])
    elif damage == "crc":
        path.write_bytes(content[:18] + bytes([content[18] ^ 255]) + content[19:])
    else:
        Image.new("RGB", (16, 16)).save(path, format="JPEG")
    assert not valid_png(path)


def test_valid_png_decodes_and_replays(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_RENDER_ROOT", str(tmp_path))
    job = str(uuid4())
    dest = output_path(job)
    Image.new("RGBA", (8, 8)).save(dest)
    monkeypatch.setattr("server.render_job_cli.subprocess.run", lambda *_a, **_k: pytest.fail("rerendered valid PNG"))
    assert valid_png(dest)
    assert native_render(tmp_path / "unused.blend", job, True)["replayed"] is True


def test_corrupt_previous_result_does_not_replay(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_RENDER_ROOT", str(tmp_path))
    monkeypatch.setenv("BLENDER_RENDER_BIN", str(Path(__file__).resolve()))
    job = str(uuid4())
    output_path(job).write_bytes(b"\x89PNG\r\n\x1a\nINVALID")
    monkeypatch.setattr("server.render_job_cli.subprocess.run", lambda *_a, **_k: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="render failed"):
        native_render(tmp_path / "unused.blend", job, True)


def test_corrupt_successful_subprocess_cannot_publish(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_RENDER_ROOT", str(tmp_path))
    monkeypatch.setenv("BLENDER_RENDER_BIN", str(Path(__file__).resolve()))
    job = str(uuid4())
    def fake_blender(_argv, **kwargs):
        Path(kwargs["env"]["BLENDER_MCP_RENDER_TEMP"]).write_bytes(b"\x89PNG\r\n\x1a\nINVALID")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("server.render_job_cli.subprocess.run", fake_blender)
    with pytest.raises(RuntimeError, match="render failed"):
        native_render(tmp_path / "unused.blend", job, True)
    dest = output_path(job)
    assert not dest.exists()
    assert not list(dest.parent.glob(job + "-*.png"))


def test_finished_status_detects_damaged_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("BLENDER_RENDER_ROOT", str(tmp_path))
    job = str(uuid4())
    output_path(job).write_bytes(b"\x89PNG\r\n\x1a\nINVALID")
    fake_job = SimpleNamespace(id=job, retries_left=0, get_status=lambda refresh: "finished",
                               return_value=lambda: {"path": str(output_path(job))})
    monkeypatch.setattr("server.render_queue_api.connection", lambda: object())
    monkeypatch.setattr("server.render_queue_api.Job.fetch", lambda *_a, **_kw: fake_job)
    result = status({"job_id": job})
    assert result["status"] == "artifact_invalid"
    assert "render" not in result
