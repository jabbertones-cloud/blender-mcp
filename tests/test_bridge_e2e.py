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
