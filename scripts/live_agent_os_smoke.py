#!/usr/bin/env python3
"""Real Blender bridge smoke for the Agent OS execution floor.

This is intentionally small and honest. It verifies observable world-state
changes against a live Blender bridge; it does not claim to be LEGO-Eval or a
scene-generation benchmark.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
from typing import Any


def send(host: str, port: int, command: str, params: dict | None = None, request_id: int = 1) -> dict:
    payload = {"id": str(request_id), "command": command, "params": params or {}}
    with socket.create_connection((host, port), timeout=15) as sock:
        sock.settimeout(30)
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
                    raise RuntimeError(f"{command}: {data['error']}")
                return data.get("result", data)
            except json.JSONDecodeError:
                continue
    raise RuntimeError(f"{command}: empty or invalid response")


def object_names(scene: dict) -> set[str]:
    return {str(row.get("name")) for row in scene.get("objects", []) if isinstance(row, dict) and row.get("name")}


def assert_ok(result: Any, label: str) -> None:
    if not isinstance(result, dict):
        raise AssertionError(f"{label}: expected dict, got {type(result).__name__}")
    if result.get("error"):
        raise AssertionError(f"{label}: {result['error']}")


def run(host: str, port: int) -> None:
    name = "AgentOS_Live_Smoke_Cube"
    rid = 1

    ping = send(host, port, "ping", request_id=rid); rid += 1
    assert_ok(ping, "ping")

    # Cleanup stale fixture if a previous interrupted run left it behind.
    before = send(host, port, "get_scene_info", request_id=rid); rid += 1
    if name in object_names(before):
        send(host, port, "delete_object", {"names": [name]}, request_id=rid); rid += 1

    created = send(host, port, "create_object", {
        "type": "cube",
        "name": name,
        "location": [0, 0, 0],
        "rotation": [0, 0, 0],
        "scale": [1, 1, 1],
        "size": 1.0,
    }, request_id=rid); rid += 1
    assert_ok(created, "create_object")

    after_create = send(host, port, "get_scene_info", request_id=rid); rid += 1
    if name not in object_names(after_create):
        raise AssertionError("create_object returned without observable scene postcondition")

    moved = send(host, port, "modify_object", {"name": name, "location": [1.25, -0.5, 0.75]}, request_id=rid); rid += 1
    assert_ok(moved, "modify_object")

    details = send(host, port, "get_object_data", {"name": name}, request_id=rid); rid += 1
    assert_ok(details, "get_object_data")
    location = details.get("location")
    if location is not None:
        rounded = [round(float(x), 2) for x in location]
        if rounded != [1.25, -0.5, 0.75]:
            raise AssertionError(f"modify_object postcondition mismatch: {rounded}")

    viewport = send(host, port, "viewport_capture", {"base64": True}, request_id=rid); rid += 1
    assert_ok(viewport, "viewport_capture")
    if not any(k in viewport for k in ("base64", "image", "image_base64", "data", "filepath")):
        raise AssertionError("viewport_capture returned no image evidence")

    deleted = send(host, port, "delete_object", {"names": [name]}, request_id=rid); rid += 1
    assert_ok(deleted, "delete_object")

    after_delete = send(host, port, "get_scene_info", request_id=rid)
    if name in object_names(after_delete):
        raise AssertionError("delete_object returned without observable scene postcondition")

    print(json.dumps({
        "status": "PASS",
        "host": host,
        "port": port,
        "checks": [
            "bridge_ping",
            "create_observable",
            "modify_observable",
            "viewport_evidence",
            "delete_observable",
        ],
    }, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9876)
    args = parser.parse_args()
    try:
        run(args.host, args.port)
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
