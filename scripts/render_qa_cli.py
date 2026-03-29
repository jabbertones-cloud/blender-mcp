#!/usr/bin/env python3
"""
Standalone render QA gate for Blender MCP.

Usage examples:
  python3 scripts/render_qa_cli.py
  python3 scripts/render_qa_cli.py --profile cinema --strict --min-score 85 --max-failed 0 --max-warnings 2
  python3 scripts/render_qa_cli.py --json-out /tmp/render-qa.json
"""

import argparse
import json
import os
import socket
import sys
from typing import Any, Dict


def _to_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    return normalized in ("1", "true", "yes", "on")


def send_command(host: str, port: int, timeout: float, command: str, params: Dict[str, Any]) -> Dict[str, Any]:
    payload = {"id": "render-qa-cli", "command": command, "params": params}
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Blender render QA gate (JSON output + threshold exit code)")
    p.add_argument("--host", default="127.0.0.1", help="Blender bridge host")
    p.add_argument("--port", type=int, default=9876, help="Blender bridge port")
    p.add_argument("--timeout", type=float, default=30.0, help="Socket timeout in seconds")

    p.add_argument("--profile", default="cinema", help="QA profile (cinema/preview/animation)")
    p.add_argument("--strict", action="store_true", help="Strict mode for QA handler")
    p.add_argument("--min-samples", type=int, default=None)
    p.add_argument("--require-exr", type=str, default=None, help="true/false")
    p.add_argument("--require-motion-blur", type=str, default=None, help="true/false")
    p.add_argument("--require-dof", type=str, default=None, help="true/false")
    p.add_argument("--require-compositor", type=str, default=None, help="true/false")
    p.add_argument("--max-exposure", type=float, default=None)
    p.add_argument("--max-adaptive-threshold", type=float, default=None)

    p.add_argument("--min-score", type=int, default=80, help="Minimum allowed score")
    p.add_argument("--max-failed", type=int, default=0, help="Maximum allowed failed checks")
    p.add_argument("--max-warnings", type=int, default=999, help="Maximum allowed warning checks")

    p.add_argument("--json-out", default="", help="Optional output file path for JSON report")
    p.add_argument(
        "--blend-path",
        default="",
        help="Optional .blend file to open on the bridge (execute_python) before render_quality_audit",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()

    params: Dict[str, Any] = {
        "profile": args.profile,
        "strict": args.strict,
    }
    if args.min_samples is not None:
        params["min_samples"] = args.min_samples
    if args.require_exr is not None:
        params["require_exr"] = _to_bool(args.require_exr)
    if args.require_motion_blur is not None:
        params["require_motion_blur"] = _to_bool(args.require_motion_blur)
    if args.require_dof is not None:
        params["require_dof"] = _to_bool(args.require_dof)
    if args.require_compositor is not None:
        params["require_compositor"] = _to_bool(args.require_compositor)
    if args.max_exposure is not None:
        params["max_exposure"] = args.max_exposure
    if args.max_adaptive_threshold is not None:
        params["max_adaptive_threshold"] = args.max_adaptive_threshold

    report: Dict[str, Any] = {
        "ok": False,
        "gate": {},
        "raw": None,
        "error": None,
    }

    blend_path = (args.blend_path or "").strip()
    if blend_path:
        ap = os.path.abspath(blend_path)
        if not os.path.isfile(ap):
            report["error"] = f"blend_path_not_found: {ap}"
            print(json.dumps(report, indent=2))
            return 2
        code = "import bpy\nbpy.ops.wm.open_mainfile(filepath=%s)" % json.dumps(ap)
        try:
            send_command(args.host, args.port, args.timeout, "execute_python", {"code": code})
        except Exception as e:
            report["error"] = f"open_blend_failed: {str(e)}"
            print(json.dumps(report, indent=2))
            return 2
        report["blend_path"] = ap
        report["blend_loaded"] = True

    try:
        raw = send_command(args.host, args.port, args.timeout, "render_quality_audit", params)
    except Exception as e:
        report["error"] = f"connection_or_command_failed: {str(e)}"
        print(json.dumps(report, indent=2))
        return 2

    if isinstance(raw, dict) and raw.get("error"):
        report["error"] = raw.get("error")
        report["raw"] = raw
        print(json.dumps(report, indent=2))
        return 2

    result = raw.get("result", raw) if isinstance(raw, dict) else {}
    if not isinstance(result, dict) or result.get("error"):
        report["error"] = result.get("error", "invalid_result_shape")
        report["raw"] = raw
        print(json.dumps(report, indent=2))
        return 2

    summary = result.get("summary", {}) if isinstance(result, dict) else {}
    score = int(summary.get("score", 0))
    failed = int(summary.get("failed", 0))
    warnings = int(summary.get("warnings", 0))

    gate_pass = (
        score >= args.min_score and failed <= args.max_failed and warnings <= args.max_warnings
    )

    report["ok"] = gate_pass
    report["gate"] = {
        "min_score": args.min_score,
        "max_failed": args.max_failed,
        "max_warnings": args.max_warnings,
        "actual_score": score,
        "actual_failed": failed,
        "actual_warnings": warnings,
    }
    report["raw"] = result

    out = json.dumps(report, indent=2)
    print(out)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            f.write(out + "\n")

    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())

