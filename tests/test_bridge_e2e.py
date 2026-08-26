"""Live Blender bridge E2E for canonical execute + visual postconditions.

Skip when the bridge is down. Fail hard when BLENDER_E2E=1 and it is down.
Never treat a skipped live test as a passing quality metric.
"""
from __future__ import annotations

import json
import os
import socket

import pytest

from server.capability_executor import execute_canonical

HOST = os.getenv("BLENDER_HOST", "127.0.0.1")
PORT = int(os.getenv("BLENDER_PORT", "9876"))
REQUIRE = os.getenv("BLENDER_E2E", "").strip() in {"1", "true", "yes"}
FIXTURE = "AgentOS_E2E_Cube"


def _bridge_open() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=1.0):
            return True
    except OSError:
        return False


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

    yield send

    info = send("get_scene_info", {})
    names = []
    objects = info.get("objects") or []
    for row in objects:
        if isinstance(row, dict) and row.get("name"):
            names.append(row["name"])
    if FIXTURE in names:
        send("delete_object", {"names": [FIXTURE]})


def test_live_create_observe_delete(live_send):
    created = execute_canonical(
        "scene.create_object",
        {"type": "cube", "name": FIXTURE, "location": [0, 0, 1], "size": 1.0},
        live_send,
        observe_visual=True,
    )
    assert created["status"] == "ok"
    assert FIXTURE in (created.get("scene_delta") or {}).get("added", [])

    moved = execute_canonical(
        "scene.modify_object",
        {"name": FIXTURE, "location": [0.5, 0.0, 1.0]},
        live_send,
        observe_visual=False,
    )
    assert moved["status"] == "ok"

    lit = execute_canonical("product.lighting", {"preset": "product_studio"}, live_send)
    assert lit["status"] == "ok"
    assert lit.get("visual_check_required") is True
    assert lit.get("visual_observation")

    deleted = execute_canonical("scene.delete_object", {"names": [FIXTURE]}, live_send, observe_visual=False)
    assert deleted["status"] == "ok"
    assert FIXTURE in (deleted.get("scene_delta") or {}).get("removed", [])
