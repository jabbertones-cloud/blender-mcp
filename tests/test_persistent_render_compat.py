"""Regression for Blender 5.1-5.3 RenderSettings persistent cache API."""
from pathlib import Path
from server.product_animation_tools import _gen_render_code


def test_product_generated_render_uses_render_settings():
    code = _gen_render_code('fast', '720p', True, None, 'PNG')
    assert 'scene.render.use_persistent_data = True' in code
    assert 'scene.cycles.use_persistent_data' not in code


def test_both_native_render_handlers_use_blender_render_settings():
    for filename in ('quality_handlers.py', 'openclaw_blender_bridge.py'):
        source = (Path('blender_addon') / filename).read_text()
        assert 'scene.render.use_persistent_data = True' in source
        assert 'scene.cycles.use_persistent_data' not in source
