import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.runtime_config import (
    build_mcp_server_env,
    resolve_blender_host,
    resolve_blender_port,
    resolve_host,
    resolve_port,
)


class ResolveBlenderPortTests(unittest.TestCase):
    def test_prefers_blender_port_when_both_are_set(self):
        env = {"BLENDER_PORT": "9877", "OPENCLAW_PORT": "9878"}
        self.assertEqual(resolve_blender_port(env), 9877)

    def test_falls_back_to_openclaw_port_for_backwards_compatibility(self):
        self.assertEqual(resolve_blender_port({"OPENCLAW_PORT": "9878"}), 9878)

    def test_defaults_to_primary_port(self):
        self.assertEqual(resolve_blender_port({}), 9876)

    def test_legacy_port_helper_still_works(self):
        self.assertEqual(resolve_port({"OPENCLAW_PORT": "9880"}), 9880)

    def test_build_mcp_server_env_sets_both_port_variables(self):
        env = build_mcp_server_env(9877)
        self.assertEqual(env["BLENDER_PORT"], "9877")
        self.assertEqual(env["OPENCLAW_PORT"], "9877")


class ResolveBlenderHostTests(unittest.TestCase):
    def test_prefers_openclaw_host(self):
        env = {"OPENCLAW_HOST": "10.0.0.1", "BLENDER_HOST": "10.0.0.2"}
        self.assertEqual(resolve_blender_host(env), "10.0.0.1")

    def test_supports_upstream_blender_host_name(self):
        self.assertEqual(resolve_blender_host({"BLENDER_HOST": "10.0.0.2"}), "10.0.0.2")

    def test_defaults_to_loopback(self):
        self.assertEqual(resolve_blender_host({}), "127.0.0.1")

    def test_legacy_host_helper_uses_same_contract(self):
        self.assertEqual(resolve_host({"BLENDER_HOST": "localhost"}), "localhost")


if __name__ == "__main__":
    unittest.main()
