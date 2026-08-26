"""Live Blender bridge E2E for canonical execute + visual postconditions.

Skip when the bridge is down. Fail hard when BLENDER_E2E=1 and it is down.
Never treat a skipped live test as a passing quality metric.
"""
from __future__ import annotations

import json
import os
import re
import socket

import pytest

from server.capability_executor import execute_canonical

HOST = os.getenv("BLENDER_HOST", "127.0.0.1")
PORT = int(os.getenv("BLENDER_PORT", "9876"))
REQUIRE = os.getenv("BLENDER_E2E", "").strip().lower() in {"1", "true", "yes"}
FIXTURE = "AgentOS_E2E_Cube"
_FIXTURE_RE = re.compile(rf"^{re.escape(FIXTURE)}(?:\.\d+)?$")


def _bridge_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1.0):
            return True
    except OSError:
        return False


def _scene_names(send) -> list[str]:
    info = send("get_scene_info", {})
    objects = info.get("objects") or [] if isinstance(info, dict) else []
    return [str(row["name"]) for row in objects if isinstance(row, dict) and row.get("name")]


def _fixture_family(send) -> list[str]:
    return [name for name in _scene_names(send) if _FIXTURE_RE.fullmatch(name)]


def _remove_fixture_family(send) -> None:
    stale = _fixture_family(send)
    if stale:
        result = send("delete_object", {"names": stale})
        if isinstance(result, dict) and result.get("error"):
            pytest.fail(f"failed to clean stale Blender E2E fixtures {stale}: {result['error']}")
    remaining = _fixture_family(send)
    if remaining:
        pytest.fail(f"stale Blender E2E fixtures remain after cleanup: {remaining}")


@pytest.fixture
def live_send():
    if not _bridge_open():
        if REQUIRE:
            pytest.fail(f"BLENDER_E2E=1 but no Blender bridge on {HOST}:{PORT}")
        pytest.skip(f"Blender bridge not listening on {HOST}:{PORT}")

    counter = {"n": 0}

    def send(command: str, params: dict | None = None) -> dict:
        counter["n"] += 1
        payload = {"id": str(counter["n"]), "command": command, "params": params or {}}
        with socket.create_connection((HOST, PORT), timeout=15) as sock:
            sock.settimeout(45)
            sock.sendall(json.dumps(payload).encode("utf-8"))
            chunks = []
            while True:
                chunk = sock.recv(1048576)
                if not chunk:
                    break
                chunks.append(chunk)
                try:
                    data = json.loads(b"".join(chunks).decode("utf-8"))
                    if data.get("error"):
                        return {"error": data["error"]}
                    return data.get("result", data)
                except json.JSONDecodeError:
                    continue
        return {"error": "empty bridge response"}

    _remove_fixture_family(send)
    try:
        yield send
    finally:
        _remove_fixture_family(send)


def test_live_create_observe_delete(live_send):
    created = execute_canonical(
        "scene.create_object",
        {"type": "cube", "name": FIXTURE, "location": [0, 0, 1], "size": 1.0},
        live_send,
        observe_visual=True,
    )
    assert created["status"] == "ok"
    assert FIXTURE in (created.get("scene_delta") or {}).get("added", [])
    assert not any(name.startswith(FIXTURE + ".") for name in _scene_names(live_send))

    moved = execute_canonical(
        "scene.modify_object",
        {"name": FIXTURE, "location": [0.5, 0.0, 1.0]},
        live_send,
        observe_visual=False,
    )
    assert moved["status"] == "ok"

    exec_probe = live_send("execute_python", {"code": "result = {'agent_os_probe': True}"})
    if exec_probe.get("disabled_by_policy"):
        message = (
            "product workflow live proof requires explicit OPENCLAW_ALLOW_EXEC=1 on the trusted Blender runner; "
            "the addon correctly defaults execute_python to disabled"
        )
        if REQUIRE:
            pytest.fail(message)
        pytest.skip(message)
    assert not exec_probe.get("error"), exec_probe

    lit = execute_canonical("product.lighting", {"preset": "product_studio"}, live_send)
    assert lit["status"] == "ok", lit
    assert lit.get("visual_check_required") is True
    observation = lit.get("visual_observation") or {}
    payload = observation.get("data", observation) if isinstance(observation, dict) else {}
    assert isinstance(payload.get("base64"), str) and payload["base64"], observation

    deleted = execute_canonical("scene.delete_object", {"names": [FIXTURE]}, live_send, observe_visual=False)
    assert deleted["status"] == "ok"
    assert FIXTURE in (deleted.get("scene_delta") or {}).get("removed", [])
    assert _fixture_family(live_send) == []


def test_live_product_hero_repairs_deleted_camera(live_send):
    from server.capability_executor import execute_workflow

    exec_probe = live_send("execute_python", {"code": "result = {'agent_os_probe': True}"})
    if exec_probe.get("disabled_by_policy"):
        message = "live camera-repair proof requires OPENCLAW_ALLOW_EXEC=1"
        if REQUIRE:
            pytest.fail(message)
        pytest.skip(message)

    created = execute_canonical(
        "scene.create_object",
        {"type": "cube", "name": FIXTURE, "location": [0, 0, 1], "size": 1.0},
        live_send,
        observe_visual=False,
    )
    assert created["status"] == "ok"

    wiped = live_send(
        "execute_python",
        {
            "code": (
                "import bpy\n"
                "removed = 0\n"
                "for obj in list(bpy.data.objects):\n"
                "    if obj.type == 'CAMERA':\n"
                "        bpy.data.objects.remove(obj, do_unlink=True)\n"
                "        removed += 1\n"
                "result = {'removed_cameras': removed}\n"
            )
        },
    )
    assert not wiped.get("error"), wiped

    out = execute_workflow("workflow.product_hero", {"object_name": FIXTURE, "auto_render": False}, live_send)
    diag = live_send("scene_diagnostics", {})
    if isinstance(diag, dict) and diag.get("error"):
        message = f"scene_diagnostics not registered on live addon: {diag['error']}"
        if REQUIRE:
            pytest.fail(message)
        pytest.skip(message)
    assert diag.get("camera_present") is True or any(
        (row.get("type") or "").upper() == "CAMERA" for row in (diag.get("objects") or []) if isinstance(row, dict)
    )
    assert out["status"] in {"review_required", "pass", "fail"}
    if out["status"] == "fail":
        codes = {row["code"] for row in (out.get("quality_review") or {}).get("findings") or []}
        assert "NO_CAMERA" not in codes, out


def test_live_recreate_attach_score_returns_numeric_fields(live_send, tmp_path):
    from server import reference_loop
    from server.capability_executor import execute_workflow

    png = tmp_path / "ref.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
        b"\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    reference_loop.reset()
    attached = execute_workflow(
        "workflow.reference_attach",
        {"path": str(png), "role": "front", "tier": "draft"},
        live_send,
    )
    assert attached["status"] == "ok"
    scored = execute_workflow(
        "workflow.reference_score",
        {"output_path": str(tmp_path / "render.png")},
        live_send,
    )
    metrics = scored.get("metrics") or {}
    assert "passed" in metrics
    assert "psnr_passed" in metrics
    assert "ssim_passed" in metrics
    assert "lpips_passed" in metrics

