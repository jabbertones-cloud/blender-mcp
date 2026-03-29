#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.healthcheck import (
    build_report,
    collect_failure_signals,
    inspect_claude_mcp_config,
    run_healthcheck,
)
from server.runtime_config import DEFAULT_BLENDER_HOST, DEFAULT_BLENDER_PORT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenClaw Blender MCP health-check")
    parser.add_argument(
        "--config",
        default=str(ROOT / "claude_mcp_config.json"),
        help="Path to MCP config JSON",
    )
    parser.add_argument("--live", action="store_true", help="Probe a live Blender bridge with ping")
    parser.add_argument("--host", default=DEFAULT_BLENDER_HOST, help="Host for live probe")
    parser.add_argument("--port", type=int, default=DEFAULT_BLENDER_PORT, help="Port for live probe")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config) if args.config else None
    repo_root = ROOT if config_path is None else config_path.resolve().parent
    report = build_report(
        repo_root=repo_root,
        live=args.live,
        host=args.host,
        port=args.port,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("OpenClaw Blender MCP health-check")
        offline = report["offline"]
        print(f"- Repo skill: {offline['repo_skill']['status']}")
        print(f"- Codex skill: {offline['codex_skill']['status']}")
        if offline["claude_mcp_config"]:
            print("- MCP config targets:")
            for entry in offline["claude_mcp_config"]:
                print(f"  - {entry['name']}: {entry['target_host']}:{entry['target_port']}")
        if offline["config_findings"]:
            print("- Config findings:")
            for finding in offline["config_findings"]:
                print(f"  - {finding}")
        else:
            print("- Config findings: none")
        if offline["runtime_findings"]:
            print("- Runtime findings:")
            for finding in offline["runtime_findings"]:
                print(f"  - {finding}")
        else:
            print("- Runtime findings: none")
        if offline["failure_signals"]:
            print("- Failure signals:")
            for signal in offline["failure_signals"]:
                print(f"  - {signal['signal']} ({signal['severity']})")
        else:
            print("- Failure signals: none")

        live = report["live"]
        print(f"- Live probe: {live['status']}")
        if live["status"] != "skipped":
            if live.get("ok"):
                response = live.get("response", {})
                print(f"  - Blender response: {json.dumps(response)[:200]}")
            else:
                print(f"  - Error: {live.get('error', live.get('message', 'unknown error'))}")

    if report["offline"]["config_findings"] or report["offline"]["runtime_findings"]:
        return 1
    if args.live and report["live"]["status"] != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
