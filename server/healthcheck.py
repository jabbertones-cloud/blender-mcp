import json
import socket
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.runtime_config import DEFAULT_BLENDER_HOST, DEFAULT_BLENDER_PORT


def load_json_file(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def validate_mcp_server_config(config: Dict[str, Any]) -> List[str]:
    findings: List[str] = []
    servers = config.get("mcpServers")

    if not isinstance(servers, dict) or not servers:
        return ["Missing or invalid 'mcpServers' object"]

    for name, server in servers.items():
        if not isinstance(server, dict):
            findings.append(f"{name}: invalid server entry")
            continue

        command = server.get("command")
        if not isinstance(command, str) or not command.strip():
            findings.append(f"{name}: missing command")

        env = server.get("env") or {}
        if not isinstance(env, dict):
            findings.append(f"{name}: invalid env object")
            continue

        blender_port = env.get("BLENDER_PORT")
        openclaw_port = env.get("OPENCLAW_PORT")

        if blender_port and openclaw_port and blender_port != openclaw_port:
            findings.append(
                f"{name}: port mismatch between BLENDER_PORT={blender_port} and OPENCLAW_PORT={openclaw_port}"
            )

        if blender_port and not openclaw_port:
            findings.append(f"{name}: missing OPENCLAW_PORT companion for BLENDER_PORT")

        if openclaw_port and not blender_port:
            findings.append(f"{name}: missing BLENDER_PORT companion for OPENCLAW_PORT")

    return findings


def validate_mcp_server_runtime(
    config: Dict[str, Any], required_modules: tuple = ("mcp", "pydantic")
) -> List[str]:
    findings: List[str] = []
    servers = config.get("mcpServers")

    if not isinstance(servers, dict) or not servers:
        return ["Missing or invalid 'mcpServers' object"]

    modules_literal = repr(tuple(required_modules))
    probe_code = (
        "import importlib.util, sys\n"
        f"modules = {modules_literal}\n"
        "missing = [name for name in modules if importlib.util.find_spec(name) is None]\n"
        "if missing:\n"
        "    sys.stderr.write(','.join(missing))\n"
        "    raise SystemExit(1)\n"
    )

    for name, server in servers.items():
        if not isinstance(server, dict):
            findings.append(f"{name}: invalid server entry")
            continue

        command = server.get("command")
        if not isinstance(command, str) or not command.strip():
            findings.append(f"{name}: missing command")
            continue

        args = server.get("args") or []
        if args:
            script_path = Path(args[0])
            if not script_path.exists():
                findings.append(f"{name}: server script not found: {script_path}")

        if "python" not in Path(command).name.lower():
            continue

        try:
            result = subprocess.run(
                [command, "-c", probe_code],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            findings.append(f"{name}: dependency probe timed out")
            continue
        except OSError as exc:
            findings.append(f"{name}: dependency probe failed: {exc}")
            continue

        if result.returncode != 0:
            error_text = (result.stderr or result.stdout).strip() or "unknown import failure"
            findings.append(f"{name}: dependency probe failed: {error_text}")

    return findings


def inspect_claude_mcp_config(config_path: Path) -> List[Dict[str, Any]]:
    if not config_path.exists():
        return []

    config = load_json_file(config_path)
    servers = config.get("mcpServers", {})
    summary: List[Dict[str, Any]] = []
    for name, server in servers.items():
        env = server.get("env") or {}
        target_port = env.get("BLENDER_PORT") or env.get("OPENCLAW_PORT") or str(DEFAULT_BLENDER_PORT)
        summary.append(
            {
                "name": name,
                "target_host": env.get("OPENCLAW_HOST", DEFAULT_BLENDER_HOST),
                "target_port": int(target_port),
                "has_primary_port_env": "BLENDER_PORT" in env,
                "has_legacy_port_env": "OPENCLAW_PORT" in env,
            }
        )
    return summary


def collect_failure_signals(journal_path: Path) -> List[Dict[str, str]]:
    if not journal_path.exists():
        return []

    try:
        raw = json.loads(journal_path.read_text())
    except json.JSONDecodeError:
        return [{"signal": "journal-unparseable", "severity": "warn"}]

    if isinstance(raw, dict):
        entries = raw.get("entries", [])
    elif isinstance(raw, list):
        entries = raw
    else:
        return [{"signal": "journal-unparseable", "severity": "warn"}]

    signal_map = [
        (
            "TIME_MT_editor_menus",
            {"signal": "keentools-time-menu-import", "severity": "error"},
        ),
        (
            "This Python version (3.13) isn't compatible with (3.11)",
            {"signal": "python-version-mismatch", "severity": "error"},
        ),
        (
            "unegister_class",
            {"signal": "addon-unregister-typo", "severity": "warn"},
        ),
        (
            "missing bl_rna attribute",
            {"signal": "addon-unregister-bl-rna", "severity": "warn"},
        ),
    ]

    discovered: List[Dict[str, str]] = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        message = entry.get("error_message", "")
        for needle, signal in signal_map:
            if needle in message and signal["signal"] not in seen:
                discovered.append(signal)
                seen.add(signal["signal"])
    return discovered


def probe_blender_socket(
    host: str = DEFAULT_BLENDER_HOST, port: int = DEFAULT_BLENDER_PORT, timeout: float = 2.0
) -> Dict[str, Any]:
    payload = {"id": "healthcheck", "command": "ping", "params": {}}

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.sendall(json.dumps(payload).encode("utf-8"))

        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                data = json.loads(b"".join(chunks).decode("utf-8"))
                return {
                    "ok": "error" not in data or not data.get("error"),
                    "host": host,
                    "port": port,
                    "response": data.get("result", data),
                }
            except json.JSONDecodeError:
                continue

        raw = b"".join(chunks).decode("utf-8")
        return {
            "ok": False,
            "host": host,
            "port": port,
            "error": "invalid JSON response" if raw else "empty response",
            "raw": raw,
        }
    except ConnectionRefusedError:
        return {"ok": False, "host": host, "port": port, "error": "connection refused"}
    except socket.timeout:
        return {"ok": False, "host": host, "port": port, "error": f"timeout after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "host": host, "port": port, "error": str(exc)}
    finally:
        try:
            sock.close()
        except Exception:
            pass


def run_healthcheck(
    config_path: Optional[Path] = None,
    live: bool = False,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
) -> Dict[str, Any]:
    report: Dict[str, Any] = {"config": None, "findings": [], "runtime_findings": [], "live": None}

    if config_path:
        config = load_json_file(config_path)
        report["config"] = str(config_path)
        report["findings"] = validate_mcp_server_config(config)
        report["runtime_findings"] = validate_mcp_server_runtime(config)

    if live:
        report["live"] = probe_blender_socket(host=host, port=port)

    return report


def build_report(
    repo_root: Path,
    codex_home: Optional[Path] = None,
    live: bool = False,
    host: str = DEFAULT_BLENDER_HOST,
    port: int = DEFAULT_BLENDER_PORT,
) -> Dict[str, Any]:
    codex_home = codex_home or Path.home() / ".codex"
    repo_skill_path = repo_root / ".claude" / "skills" / "blender-mcp" / "SKILL.md"
    codex_skill_path = codex_home / "skills" / "blender-mcp" / "SKILL.md"
    config_path = repo_root / "claude_mcp_config.json"
    journal_path = repo_root / "data" / "learning_journal.json"

    config = load_json_file(config_path) if config_path.exists() else None
    report: Dict[str, Any] = {
        "repo_root": str(repo_root),
        "offline": {
            "repo_skill": {
                "status": "ok" if repo_skill_path.exists() else "missing",
                "path": str(repo_skill_path),
            },
            "codex_skill": {
                "status": "ok" if codex_skill_path.exists() else "missing",
                "path": str(codex_skill_path),
            },
            "claude_mcp_config": inspect_claude_mcp_config(config_path),
            "config_findings": validate_mcp_server_config(config)
            if config is not None
            else ["missing claude_mcp_config.json"],
            "runtime_findings": validate_mcp_server_runtime(config)
            if config is not None
            else ["missing claude_mcp_config.json"],
            "failure_signals": collect_failure_signals(journal_path),
        },
        "live": {"status": "skipped", "reason": "live checks disabled"},
    }

    if live:
        live_report = probe_blender_socket(host=host, port=port)
        report["live"] = {
            "status": "ok" if live_report.get("ok") else "error",
            **live_report,
        }

    return report
