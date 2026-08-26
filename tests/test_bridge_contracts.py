import ast
from pathlib import Path

from server.capability_registry import registry


ADDON_PATH = Path("blender_addon/openclaw_blender_bridge.py")
PRODUCT_WRAPPER_KEYS = {
    "product.material",
    "product.lighting",
    "product.camera",
    "product.render_setup",
}


def _source() -> str:
    return ADDON_PATH.read_text(encoding="utf-8")


def _registered_bridge_commands() -> set[str]:
    tree = ast.parse(_source())
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {
            key.value
            for key in node.keys
            if isinstance(key, ast.Constant) and isinstance(key.value, str)
        }
        if {"ping", "get_scene_info", "create_object", "viewport_capture"}.issubset(keys):
            candidates.append(keys)
    assert candidates, "could not locate addon command-handler registry"
    return max(candidates, key=len)


def test_every_direct_registry_bridge_command_has_a_registered_addon_handler():
    commands = _registered_bridge_commands()
    missing = {}
    for key in registry.keys():
        if key in PRODUCT_WRAPPER_KEYS:
            continue
        cap = registry.resolve_tool(key)
        if cap.bridge_command not in commands:
            missing[key] = cap.bridge_command
    assert missing == {}, f"registry points at nonexistent addon commands: {missing}"


def test_product_wrappers_depend_only_on_registered_execute_python_boundary():
    commands = _registered_bridge_commands()
    assert "execute_python" in commands
    for key in PRODUCT_WRAPPER_KEYS:
        cap = registry.resolve_tool(key)
        assert cap.key == key


def test_viewport_capture_contract_returns_pixels_when_base64_requested():
    source = _source()
    assert 'params.get("base64", False)' in source
    assert 'result["base64"] = base64.b64encode' in source


def test_render_contract_is_image_or_animation():
    source = _source()
    assert 'render_type = params.get("type", "image")' in source
    assert 'if render_type == "animation":' in source


def test_execute_python_is_default_off_and_ast_guarded():
    source = _source()
    assert 'OPENCLAW_ALLOW_EXEC", "0"' in source
    assert 'disabled_by_policy' in source
    assert 'OPENCLAW_ALLOW_UNSAFE_EXEC' in source
    assert 'ast.parse' in source
