import contextlib
import importlib.util
import io
import sys
import subprocess
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.healthcheck import validate_mcp_server_config, validate_mcp_server_runtime


class ValidateMcpServerConfigTests(unittest.TestCase):
    def test_accepts_matching_dual_port_env(self):
        config = {
            "mcpServers": {
                "blender-2": {
                    "command": "python3",
                    "args": ["server/blender_mcp_server.py"],
                    "env": {
                        "BLENDER_PORT": "9877",
                        "OPENCLAW_PORT": "9877",
                    },
                }
            }
        }

        findings = validate_mcp_server_config(config)

        self.assertEqual(findings, [])

    def test_reports_mismatched_port_env(self):
        config = {
            "mcpServers": {
                "blender-2": {
                    "command": "python3",
                    "args": ["server/blender_mcp_server.py"],
                    "env": {
                        "BLENDER_PORT": "9877",
                        "OPENCLAW_PORT": "9878",
                    },
                }
            }
        }

        findings = validate_mcp_server_config(config)

        self.assertTrue(any("port mismatch" in finding.lower() for finding in findings))

    def test_reports_missing_command_path(self):
        config = {
            "mcpServers": {
                "blender": {
                    "command": "",
                    "args": [],
                    "env": {},
                }
            }
        }

        findings = validate_mcp_server_config(config)

        self.assertTrue(any("command" in finding.lower() for finding in findings))


class ValidateMcpServerRuntimeTests(unittest.TestCase):
    def test_accepts_interpreter_when_required_modules_are_available(self):
        config = {
            "mcpServers": {
                "blender": {
                    "command": sys.executable,
                    "args": [],
                    "env": {},
                }
            }
        }

        findings = validate_mcp_server_runtime(config, required_modules=("json",))

        self.assertEqual(findings, [])

    def test_reports_dependency_probe_failure(self):
        config = {
            "mcpServers": {
                "blender": {
                    "command": sys.executable,
                    "args": [],
                    "env": {},
                }
            }
        }

        findings = validate_mcp_server_runtime(
            config, required_modules=("definitely_missing_openclaw_module",)
        )

        self.assertTrue(any("dependency probe failed" in finding.lower() for finding in findings))

    def test_reports_timeout_as_finding_instead_of_crashing(self):
        config = {
            "mcpServers": {
                "blender": {
                    "command": sys.executable,
                    "args": [],
                    "env": {},
                }
            }
        }

        with mock.patch(
            "server.healthcheck.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=[sys.executable], timeout=5),
        ):
            findings = validate_mcp_server_runtime(config, required_modules=("json",))

        self.assertTrue(any("timed out" in finding.lower() for finding in findings))


def load_script_module(relative_path: str):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_path.stem.replace(".", "_"), module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BlenderHealthcheckCliTests(unittest.TestCase):
    def test_main_fails_when_runtime_findings_exist(self):
        cli = load_script_module("scripts/blender_healthcheck.py")
        report = {
            "offline": {
                "repo_skill": {"status": "ok"},
                "codex_skill": {"status": "ok"},
                "claude_mcp_config": [],
                "config_findings": [],
                "runtime_findings": ["blender: dependency probe failed"],
                "failure_signals": [],
            },
            "live": {"status": "skipped", "reason": "live checks disabled"},
        }

        with mock.patch.object(cli, "build_report", return_value=report):
            with mock.patch.object(sys, "argv", ["blender_healthcheck.py"]):
                exit_code = cli.main()

        self.assertEqual(exit_code, 1)

    def test_main_prints_runtime_findings(self):
        cli = load_script_module("scripts/blender_healthcheck.py")
        report = {
            "offline": {
                "repo_skill": {"status": "ok"},
                "codex_skill": {"status": "ok"},
                "claude_mcp_config": [],
                "config_findings": [],
                "runtime_findings": ["blender: dependency probe failed"],
                "failure_signals": [],
            },
            "live": {"status": "skipped", "reason": "live checks disabled"},
        }

        stdout = io.StringIO()
        with mock.patch.object(cli, "build_report", return_value=report):
            with mock.patch.object(sys, "argv", ["blender_healthcheck.py"]):
                with contextlib.redirect_stdout(stdout):
                    cli.main()

        self.assertIn("Runtime findings", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
