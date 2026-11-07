"""Read-only Quality Lab workflow is typed, scoped and strips executable fixes."""
import asyncio
import hashlib
import os
import sys
from types import SimpleNamespace

import pytest

from server.blender_mcp_guided import GoalInput, SearchInput, SchemaInput, router_set_goal, search_capabilities, get_capability_schema
from server.capability_executor import execute_workflow


def no_bridge(*_args, **_kw):
    raise AssertionError('Quality inspection must not call the mutable Blender bridge')


def test_discover_quality_workflow_without_sixth_mcp_tool():
    goal = asyncio.run(router_set_goal(GoalInput(goal='check scene quality')))
    found = asyncio.run(search_capabilities(SearchInput(query='quality audit')))
    schema = asyncio.run(get_capability_schema(SchemaInput(key='workflow.quality_inspect')))
    assert goal['recommended_first']['key'] == 'workflow.quality_inspect'
    assert found['results'][0]['key'] == 'workflow.quality_inspect'
    assert schema['capability']['input_schema']['required'] == ['scene_path']
    assert schema['usage_guide']['key'] == 'inspection'


def test_missing_config_fails_closed(monkeypatch):
    monkeypatch.delenv('BLENDER_QUALITY_ROOT', raising=False)
    monkeypatch.delenv('BLENDER_QUALITY_BIN', raising=False)
    result = execute_workflow('workflow.quality_inspect', {'scene_path': '/tmp/demo.blend'}, no_bridge)
    assert result['status'] == 'blocked'


def test_schema_rejects_unrecognized_args_without_running_blender():
    with pytest.raises(ValueError):
        execute_workflow('workflow.quality_inspect', {'scene_path': '/tmp/demo.blend', 'code': 'bpy.ops.wm.quit_blender()'}, no_bridge)
    with pytest.raises(ValueError):
        execute_workflow('workflow.quality_inspect', {'scene_path': '/tmp/demo.blend', 'strict_contact': 'yes'}, no_bridge)


def test_symlink_escape_and_invalid_extension_blocked(monkeypatch, tmp_path):
    root, outside = tmp_path / 'allowed', tmp_path / 'outside.blend'
    root.mkdir(); outside.write_bytes(b'BLENDER')
    (root / 'leak.blend').symlink_to(outside)
    (root / 'notes.txt').write_text('anything')
    monkeypatch.setenv('BLENDER_QUALITY_ROOT', str(root))
    monkeypatch.setenv('BLENDER_QUALITY_BIN', sys.executable)
    for path in (root / 'leak.blend', root / 'notes.txt', outside):
        res = execute_workflow('workflow.quality_inspect', {'scene_path': str(path)}, no_bridge)
        assert res['status'] == 'blocked'


def test_structured_fixes_never_expose_arbitrary_python(monkeypatch, tmp_path):
    from server import scene_quality_adapter
    root = tmp_path / 'scene'; root.mkdir()
    file = root / 'file.blend'; file.write_bytes(b'BLENDER')
    monkeypatch.setenv('BLENDER_QUALITY_ROOT', str(root))
    monkeypatch.setenv('BLENDER_QUALITY_BIN', sys.executable)
    fake = SimpleNamespace(
        BlenderError=RuntimeError,
        check=lambda *_args, **_kwargs: {'all_gates_passed': False,
            'failed_gates': [{'id': 'materials'}], 'checks': [{'id': 'materials', 'passed': False}],
            'fixes': [{'problem': 'no material', 'action': 'assign one', 'python': 'evil()'}],
            'warnings': [], 'files': {'report_json': '/tmp/report.json'}})
    monkeypatch.setitem(sys.modules, 'blender_quality', SimpleNamespace(api=fake))
    result = execute_workflow('workflow.quality_inspect', {'scene_path': str(file)}, no_bridge)
    assert result['status'] == 'failed' and result['failed_gates'][0]['id'] == 'materials'
    assert result['suggested_actions'] == [{'problem': 'no material', 'action': 'assign one'}]
    assert 'evil' not in str(result)


@pytest.mark.skipif(os.getenv('BLENDER_E2E') != '1', reason='requires real pinned Blender Quality Lab and test scene')
def test_real_quality_lab_reports_scene_without_mutating_blend(monkeypatch):
    from pathlib import Path
    path = Path(os.environ['BLENDER_QUALITY_TEST_SCENE'])
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = execute_workflow('workflow.quality_inspect', {'scene_path': str(path)}, no_bridge)
    assert result['status'] in {'failed', 'review_required', 'ok'}, result
    assert result['read_only'] and len(result['checks']) >= 8
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    assert result['report_json'] and Path(result['report_json']).is_file()


def test_pinned_quality_lab_sabotage_fixture_detects_missing_material():
    from blender_quality import api
    from pathlib import Path
    root = Path(__file__).parent / 'fixtures/quality_lab'
    original = api.score(root / 'missing_material.json')
    repaired = api.score(root / 'assigned_material.json')
    assert [x['id'] for x in original['checks'] if not x['passed']] == ['materials']
    assert [x['id'] for x in repaired['checks'] if not x['passed']] == []
    assert sum(x['passed'] for x in repaired['checks']) == 10
