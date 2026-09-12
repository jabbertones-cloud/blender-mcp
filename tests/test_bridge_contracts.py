import ast
from pathlib import Path

from server.capability_registry import registry


ADDON_PATH = Path("blender_addon/openclaw_blender_bridge.py")
PHASE5_PATH = Path("blender_addon/new_handlers_phase5.py")
QUALITY_PATH = Path("blender_addon/quality_handlers.py")


def _source(path: Path = ADDON_PATH) -> str:
    return path.read_text(encoding="utf-8")


def _dict_keys(path: Path, required: set[str]) -> set[str]:
    tree = ast.parse(_source(path))
    candidates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = {key.value for key in node.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        if required.issubset(keys):
            candidates.append(keys)
    assert candidates, f"could not locate command registry in {path}"
    return max(candidates, key=len)


def _assigned_keys(path: Path, target_name: str) -> set[str]:
    tree = ast.parse(_source(path))
    keys = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Subscript):
                continue
            if not isinstance(target.value, ast.Name) or target.value.id != target_name:
                continue
            slice_node = target.slice
            if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                keys.add(slice_node.value)
    return keys


def _registered_bridge_commands() -> set[str]:
    base = _dict_keys(ADDON_PATH, {"ping", "get_scene_info", "create_object", "viewport_capture"})
    phase5 = _dict_keys(PHASE5_PATH, {"spatial_raycast", "dimensions_estimate", "floor_plan_data"})
    quality = _dict_keys(QUALITY_PATH, {"scene_diagnostics"}) | _assigned_keys(QUALITY_PATH, "QUALITY_HANDLERS")
    return base | phase5 | quality


def test_phase5_handlers_are_merged_into_the_live_dispatch_dict():
    source = _source()
    assert "HANDLERS.update(_PHASE5_HANDLERS)" in source
    assert "COMMANDS.update(_PHASE5_HANDLERS)" not in source
    assert "HANDLERS.update(QUALITY_HANDLERS)" in source
    assert registry.resolve_tool("scene.diagnostics").bridge_command == "scene_diagnostics"


def test_every_registry_bridge_command_has_a_registered_addon_handler():
    commands = _registered_bridge_commands()
    missing = {key: registry.resolve_tool(key).bridge_command for key in registry.keys() if registry.resolve_tool(key).bridge_command not in commands}
    assert missing == {}, f"registry points at nonexistent addon commands: {missing}"


def test_product_capabilities_use_native_registered_boundaries():
    commands = _registered_bridge_commands()
    expected = {
        "product.material": "product_material",
        "product.lighting": "product_lighting",
        "product.camera": "product_camera",
        "product.render_setup": "product_render_setup",
    }
    for key, command in expected.items():
        assert registry.resolve_tool(key).bridge_command == command
        assert command in commands
    assert registry.resolve_tool("product.animation").bridge_command == "execute_python"
    assert "execute_python" in commands


def test_product_handlers_preserve_unowned_scene_resources_and_scope_cleanup():
    source = _source(QUALITY_PATH)
    assert 'OWNER_KEY = "openclaw_owner"' in source
    assert 'OWNER_VALUE = "product_workflow"' in source
    assert 'for obj in list(scene.objects):' in source
    assert '_remove_owned(scene, "product_light")' in source
    assert '_remove_owned(scene, "product_camera")' in source
    assert '_remove_owned(scene, "product_camera_target")' in source
    assert 'bpy.data.lights.remove(data)' in source
    assert 'bpy.data.cameras.remove(data)' in source
    assert 'if obj.type == "LIGHT":\n            bpy.data.objects.remove' not in source
    assert 'obj.name.startswith("Turntable_")' not in source
    assert 'obj.name == "Product_Camera"' not in source
    assert "bpy.context.collection.objects.link" not in source
    assert "scene.collection" in source


def test_scene_diagnostics_exposes_versioned_coordinate_explicit_postconditions():
    source = _source(QUALITY_PATH)
    required = {
        "schema_version",
        "objects_truncated",
        "object_limit",
        "location_world",
        "matrix_world",
        "rotation_euler_local",
        "scale_local",
        "dimensions_evaluated",
        "materials",
        "frame_current",
        "filepath",
        "file_format",
        "color",
    }
    for field in required:
        assert f'"{field}"' in source, f"scene diagnostics missing deterministic field: {field}"
    assert "MAX_DIAGNOSTIC_OBJECTS = 500" in source
    assert "evaluated.dimensions" in source


def test_product_camera_targets_evaluated_world_space_bounds_and_preserves_prior_camera_identity():
    source = _source(QUALITY_PATH)
    assert "evaluated_depsgraph_get" in source
    assert "evaluated_get" in source
    assert "matrix_world" in source
    assert "bound_box" in source
    assert "target.location = target_obj.location" not in source
    assert 'PREVIOUS_CAMERA_KEY = "openclaw_previous_camera"' in source
    assert "not _owned(previous_active, \"product_camera\")" in source
    assert "scene[PREVIOUS_CAMERA_KEY] = previous_active.name" in source


def test_dynamic_spatial_wrappers_advertise_real_phase5_boundaries():
    commands = _registered_bridge_commands()
    expected = {
        "scene.spatial_query": "spatial_scene_bounds",
        "scene.dimensions": "dimensions_estimate",
        "scene.floor_plan": "floor_plan_data",
    }
    for key, command in expected.items():
        assert registry.resolve_tool(key).bridge_command == command
        assert command in commands


def test_viewport_capture_contract_returns_pixels_when_base64_requested():
    source = _source()
    assert 'params.get("base64", False)' in source
    assert 'result["base64"] = base64.b64encode' in source


def test_render_contract_is_image_or_animation():
    source = _source()
    assert 'render_type = params.get("type", "image")' in source
    assert 'if render_type == "animation":' in source
    schema = registry.resolve_tool("scene.render").input_schema
    assert schema["properties"]["type"]["enum"] == ["image", "animation"]


def test_execute_python_is_default_off_and_ast_guarded():
    source = _source()
    assert 'OPENCLAW_ALLOW_EXEC", "0"' in source
    assert 'disabled_by_policy' in source
    assert 'OPENCLAW_ALLOW_UNSAFE_EXEC' in source
    assert 'ast.parse' in source
