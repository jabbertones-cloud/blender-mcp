import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_mcp_config_keeps_guided_default_and_explicit_power_surface():
    config = json.loads((ROOT / "claude_mcp_config.json").read_text(encoding="utf-8"))["mcpServers"]
    assert config["blender"]["args"][0].endswith("server/blender_mcp_guided.py")
    assert config["blender-power"]["args"][0].endswith("server/blender_mcp_server.py")
    for name, port in (("blender-2", "9877"), ("blender-3", "9878")):
        assert config[name]["args"][0].endswith("server/blender_mcp_guided.py")
        assert config[name]["env"]["BLENDER_PORT"] == port
        assert config[name]["env"]["OPENCLAW_PORT"] == port


def test_setup_generator_preserves_same_guided_topology():
    source = (ROOT / "setup.sh").read_text(encoding="utf-8")
    assert '"blender"' in source
    assert '"blender-power"' in source
    assert 'server/blender_mcp_guided.py' in source
    assert 'server/blender_mcp_server.py' in source
    assert source.count('server/blender_mcp_guided.py') >= 3
    assert '"BLENDER_PORT": "9877"' in source
    assert '"OPENCLAW_PORT": "9877"' in source
    assert '"BLENDER_PORT": "9878"' in source
    assert '"OPENCLAW_PORT": "9878"' in source
