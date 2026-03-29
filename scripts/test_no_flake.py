#!/usr/bin/env python3
"""
Single no-flake local test runner (Layers 0-3).

Layers:
  0) Offline deterministic
  1) Bridge smoke
  2) Render QA gate contract
  3) External-tool negative-path contract (no keys expected)
"""

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(command: str, cwd: Path) -> Dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return {
        "command": command,
        "exit_code": proc.returncode,
        "output": proc.stdout,
    }


def send_raw_command(host: str, port: int, timeout: float, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    import socket

    payload = {"id": f"no-flake-{command}", "command": command, "params": params}
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    sock.sendall(json.dumps(payload).encode("utf-8"))
    chunks: List[bytes] = []
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


def main() -> int:
    parser = argparse.ArgumentParser(description="No-flake local test runner for Blender MCP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9876)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--skip-layer3", action="store_true")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    report: Dict[str, Any] = {
        "ok": False,
        "layers": [],
        "summary": {},
    }

    # Layer 0
    layer0_cmds = [
        "python3 -m unittest tests.test_runtime_config tests.test_healthcheck -v",
        "python3 scripts/blender_healthcheck.py",
    ]
    layer0_results = [run_cmd(cmd, ROOT) for cmd in layer0_cmds]
    layer0_ok = all(r["exit_code"] == 0 for r in layer0_results)
    report["layers"].append({"name": "layer0_offline_deterministic", "ok": layer0_ok, "results": layer0_results})
    if not layer0_ok:
        report["summary"]["failed_at"] = "layer0"
        print(json.dumps(report, indent=2))
        return 1

    # Layer 1
    layer1_results: List[Dict[str, Any]] = []
    if not args.skip_live:
        layer1_results.append(run_cmd(f"python3 scripts/blender_healthcheck.py --live --host {shlex.quote(args.host)} --port {args.port}", ROOT))
    layer1_results.append(run_cmd("python3 scripts/ensure_render_qa_ready.py", ROOT))
    layer1_ok = all(r["exit_code"] == 0 for r in layer1_results)
    report["layers"].append({"name": "layer1_bridge_smoke", "ok": layer1_ok, "results": layer1_results})
    if not layer1_ok:
        report["summary"]["failed_at"] = "layer1"
        print(json.dumps(report, indent=2))
        return 1

    # Layer 2
    layer2_cmds = [
        "python3 scripts/render_qa_cli.py --profile cinema --min-score 60 --max-failed 10 --max-warnings 20",
        "python3 scripts/render_qa_cli.py --strict --min-score 85 --max-failed 0 --max-warnings 2",
    ]
    layer2_results = [run_cmd(cmd, ROOT) for cmd in layer2_cmds]
    # Non-flake contract: render_qa_cli must not return infra error code 2.
    layer2_ok = all(r["exit_code"] in (0, 1) for r in layer2_results)
    report["layers"].append({"name": "layer2_render_qa_contract", "ok": layer2_ok, "results": layer2_results})
    if not layer2_ok:
        report["summary"]["failed_at"] = "layer2"
        print(json.dumps(report, indent=2))
        return 1

    # Layer 3
    if not args.skip_layer3:
        layer3_checks: List[Dict[str, Any]] = []
        layer3_ok = True
        for command_name, payload, expected_env_key in [
            ("sketchfab", {"action": "search", "query": "cinematic", "count": 1}, "SKETCHFAB_API_TOKEN"),
            ("hunyuan3d", {"action": "status", "job_id": "demo"}, "HUNYUAN3D_API_KEY"),
        ]:
            try:
                response = send_raw_command(args.host, args.port, args.timeout, command_name, payload)
                raw_err = str(response.get("error", ""))
                result = response.get("result", {})
                inner_err = str(result.get("error", "")) if isinstance(result, dict) else ""
                combined = f"{raw_err} {inner_err}".strip()
                ok = (expected_env_key in combined) or (combined == "")
                # If keys are configured, command may succeed (combined == "").
                if not ok:
                    layer3_ok = False
                layer3_checks.append({
                    "command": command_name,
                    "ok": ok,
                    "expected_env_key": expected_env_key,
                    "response": response,
                })
            except Exception as e:
                layer3_ok = False
                layer3_checks.append({
                    "command": command_name,
                    "ok": False,
                    "error": str(e),
                    "expected_env_key": expected_env_key,
                })
        report["layers"].append({"name": "layer3_external_negative_path", "ok": layer3_ok, "checks": layer3_checks})
        if not layer3_ok:
            report["summary"]["failed_at"] = "layer3"
            print(json.dumps(report, indent=2))
            return 1

    report["ok"] = True
    report["summary"]["failed_at"] = None
    out = json.dumps(report, indent=2)
    print(out)
    if args.json_out:
        Path(args.json_out).write_text(out + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

