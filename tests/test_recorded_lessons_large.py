"""Streaming Blender Replay import regression and adversarial tests."""
import hashlib
import json
from pathlib import Path

import pytest

from server.recorded_lessons import import_recording, get_approved


def _write(path, events, **extra):
    doc = {"schema_version": 1, "recording_state": "stopped",
           "blender_version": "5.3.0", "name": "Sample",
           "warnings": [], "events": events, **extra}
    path.write_text(json.dumps(doc))
    return doc


def test_stream_import_preserves_event_indices_and_sha(tmp_path):
    source = tmp_path / "recording.chronicle.json"
    events = [{"type": "segment", "phase": "start"}]
    events += [{"type": "context", "context": {"mode": "OBJECT"}} for _ in range(10001)]
    events += [{"type": "operator", "idname": "MESH_OT_primitive_cube_add"}]
    _write(source, events)
    lesson = import_recording(source, directory=tmp_path / "lessons",
                              identifier="training-01", goal="Create cube")
    assert lesson["provenance"]["event_count"] == len(events)
    assert lesson["provenance"]["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert lesson["coverage"]["operators"] == 1
    assert lesson["steps"][0]["evidence_event"] == len(events) - 1
    assert lesson["coverage"]["truncated"] is False
    assert get_approved("lesson.training-01", root=tmp_path / "lessons") is None


def test_malformed_event_rejected(tmp_path):
    source = tmp_path / "invalid.chronicle.json"
    _write(source, [{"type": "untrusted"}])
    with pytest.raises(ValueError, match="Invalid recording event"):
        import_recording(source, directory=tmp_path / "out",
                         identifier="invalid-01", goal="X")


def test_incomplete_recording_rejected(tmp_path):
    source = tmp_path / "active.chronicle.json"
    _write(source, [], recording_state="active")
    with pytest.raises(ValueError, match="Incomplete recording"):
        import_recording(source, directory=tmp_path / "out",
                         identifier="active-01", goal="X")


def test_event_count_limit(tmp_path, monkeypatch):
    import server.recorded_lessons as lessons
    monkeypatch.setattr(lessons, "MAX_EVENTS", 10)
    source = tmp_path / "excess.chronicle.json"
    _write(source, [{"type": "context"}] * 11)
    with pytest.raises(ValueError, match="event limit"):
        import_recording(source, directory=tmp_path / "out",
                         identifier="excess-01", goal="X")


def test_malformed_json_rejected(tmp_path):
    source = tmp_path / "corrupt.chronicle.json"
    source.write_text('{"events":[{"type":"operator"}]')
    with pytest.raises(ValueError):
        import_recording(source, directory=tmp_path / "out",
                         identifier="corrupt-01", goal="X")
