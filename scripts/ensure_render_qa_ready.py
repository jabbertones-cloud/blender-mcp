#!/usr/bin/env python3
"""
Ensure Blender bridge has render_quality_audit loaded before QA runs.

Exit codes:
  0 = ready
  1 = not ready after reload attempts
  2 = connection/protocol error
"""

import argparse
import json
import socket
import sys
import time
from typing import Any, Dict


def send_command(host: str, port: int, timeout: float, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"id": f"ensure-{command}", "command": command, "params": params}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    sock.sendall(json.dumps(payload).encode("utf-8"))

    chunks = []
    while True:
        chunk = sock.recv(1024 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
        try:
            parsed = json.loads(b"".join(chunks).decode("utf-8"))
            sock.close()
            return parsed
        except json.JSONDecodeError:
            continue
    sock.close()
    return json.loads(b"".join(chunks).decode("utf-8"))


def has_command(host: str, port: int, timeout: float, command: str) -> bool:
    # Send a probe call; if command exists, handler-level error is acceptable.
    response = send_command(host, port, timeout, command, {})
    err = str(response.get("error", ""))
    if "Unknown command" in err:
        return False
    result = response.get("result", {})
    if isinstance(result, dict):
        inner_err = str(result.get("error", ""))
        if "Unknown command" in inner_err:
            return False
    return True


def attempt_reload(host: str, port: int, timeout: float) -> Dict[str, Any]:
    code = (
        "import bpy\n"
        "bpy.ops.script.reload()\n"
        "__result__ = {'reloaded': True, 'file': bpy.data.filepath}\n"
    )
    return send_command(host, port, timeout, "execute_python", {"code": code})


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure render_quality_audit handler is live")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--attempts", type=int, default=2, help="Reload attempts if command missing")
    parser.add_argument("--wait-seconds", type=float, default=1.0, help="Wait between reload and re-check")
    args = parser.parse_args()

    report: Dict[str, Any] = {
        "ok": False,
        "host": args.host,
        "port": args.port,
        "command": "render_quality_audit",
        "attempts": [],
    }

    try:
        if has_command(args.host, args.port, args.timeout, "render_quality_audit"):
            report["ok"] = True
            report["status"] = "ready"
            print(json.dumps(report, indent=2))
            return 0

        for i in range(args.attempts):
            attempt_info: Dict[str, Any] = {"attempt": i + 1}
            try:
                reload_resp = attempt_reload(args.host, args.port, args.timeout)
                attempt_info["reload_response"] = reload_resp
            except Exception as e:
                attempt_info["reload_error"] = str(e)
            time.sleep(args.wait_seconds)
            try:
                ready = has_command(args.host, args.port, args.timeout, "render_quality_audit")
                attempt_info["ready_after_reload"] = ready
                report["attempts"].append(attempt_info)
                if ready:
                    report["ok"] = True
                    report["status"] = "ready_after_reload"
                    print(json.dumps(report, indent=2))
                    return 0
            except Exception as e:
                attempt_info["probe_error"] = str(e)
                report["attempts"].append(attempt_info)

        report["status"] = "missing_command_after_reload"
        report["error"] = (
            "render_quality_audit is not registered in the running Blender bridge. "
            "Restart Blender/addon instance on this port and re-run."
        )
        print(json.dumps(report, indent=2))
        return 1
    except Exception as e:
        report["status"] = "connection_or_protocol_error"
        report["error"] = str(e)
        print(json.dumps(report, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())

