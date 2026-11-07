"""Adversarial export validation: bridge success must not mean asset success."""
from pathlib import Path
from unittest.mock import patch

import pytest

from server.gltf_validation import file_signature, validate_export
from server.capability_executor import execute_canonical


def test_real_m2_export_passes():
    path = Path("/tmp/m2_blender_export_20261106.glb")
    if not path.exists():
        pytest.skip("M2 fixture not present on this host")
    result = validate_export(str(path))
    assert result["valid"], result


def test_missing_empty_non_glb_and_invalid_bytes_fail(tmp_path):
    missing = tmp_path / "missing.glb"
    assert not validate_export(str(missing))["valid"]
    empty = tmp_path / "empty.glb"
    empty.touch()
    assert not validate_export(str(empty))["valid"]
    broken = tmp_path / "broken.glb"
    broken.write_bytes(b"glTF" + b"\\x00" * 20)
    assert not validate_export(str(broken))["valid"]
    other = tmp_path / "other.fbx"
    other.write_bytes(b"not glb")
    assert not validate_export(str(other))["valid"]


def test_unchanged_export_is_rejected(tmp_path):
    path = tmp_path / "old.glb"
    path.write_bytes(b"glTF" + b"\\x00" * 20)
    assert not validate_export(str(path), previous=file_signature(str(path)))["valid"]


def test_validator_unavailable_fails_closed(tmp_path):
    path = tmp_path / "fresh.glb"
    path.write_bytes(b"glTF" + b"\\x00" * 20)
    with patch("server.gltf_validation.subprocess.run", side_effect=FileNotFoundError):
        assert not validate_export(str(path))["valid"]


def test_guided_export_rejects_forged_bridge_success(tmp_path):
    path = tmp_path / "broken.glb"
    def bridge(command, args):
        if command == "export_file":
            path.write_bytes(b"bad output")
            return {"exported": str(path)}
        return {"objects": []}
    response = execute_canonical("io.export", {"filepath": str(path), "action": "auto"}, bridge)
    assert response["status"] == "postcondition_failed"
    assert response["export_validation"]["valid"] is False


def test_non_glb_keeps_existing_export_contract(tmp_path):
    path = tmp_path / "model.fbx"
    def bridge(command, args):
        if command == "export_file":
            return {"exported": str(path)}
        return {"objects": []}
    response = execute_canonical("io.export", {"filepath": str(path), "action": "auto"}, bridge)
    assert response["status"] == "ok"
    assert "export_validation" not in response


def test_validator_malformed_return_is_a_structured_failure(tmp_path):
    path = tmp_path / "bad.glb"
    def bridge(command, args):
        if command == "export_file":
            path.write_bytes(b"garbage")
            return {"exported": str(path)}
        return {"objects": []}
    with patch("server.gltf_validation.validate_export", return_value=None):
        response = execute_canonical("io.export", {"filepath": str(path)}, bridge)
    assert response["status"] == "postcondition_failed"
    assert response["error"] == "Malformed GLB validation result"
