"""Typed MCP render submission uses only native Blender and RQ's tested broker."""
import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4
import pytest
from server.capability_executor import execute_workflow
from server.blender_mcp_guided import GoalInput, SearchInput, SchemaInput, router_set_goal, search_capabilities, get_capability_schema
from server.render_job_paths import scene_path, output_path
from server.render_queue_api import connection


def no_bridge(*args, **kwargs):
    raise AssertionError('Background job must not write to live Blender socket')


def test_exposes_native_render_without_an_extra_mcp_tool():
    goal=asyncio.run(router_set_goal(GoalInput(goal='background render a saved scene')))
    match=asyncio.run(search_capabilities(SearchInput(query='background render')))
    schema=asyncio.run(get_capability_schema(SchemaInput(key='workflow.render_enqueue')))
    assert goal['recommended_first']['key']=='workflow.render_enqueue'
    assert match['results'][0]['key']=='workflow.render_enqueue'
    assert schema['capability']['input_schema']['required']==['scene_path']


@pytest.mark.parametrize("goal,expected", [
    ("queue background Blender render of saved scene", "workflow.render_enqueue"),
    ("queue a background render of a saved scene", "workflow.render_enqueue"),
    ("start an asynchronous render of the saved scene", "workflow.render_enqueue"),
    ("render this scene in the background", "workflow.render_enqueue"),
    ("check background Blender render job status", "workflow.render_status"),
    ("show progress of the background render", "workflow.render_status"),
    ("is the background render finished?", "workflow.render_status"),
    ("render a png", "scene.render"),
])
def test_background_render_goal_disambiguation(goal, expected):
    result = asyncio.run(router_set_goal(GoalInput(goal=goal)))
    assert result["recommended_first"]["key"] == expected, (goal, result)


def test_schema_rejects_code_or_client_selected_output():
    with pytest.raises(ValueError):
        execute_workflow('workflow.render_enqueue',{'scene_path':'/tmp/example.blend','code':'evil()'},no_bridge)
    with pytest.raises(ValueError):
        execute_workflow('workflow.render_enqueue',{'scene_path':'/tmp/example.blend','output_path':'/tmp/output.png'},no_bridge)
    with pytest.raises(ValueError):
        execute_workflow('workflow.render_enqueue',{'scene_path':'/tmp/example.blend','preview':'yes'},no_bridge)


def test_root_rejects_escape_and_invalid_extension(monkeypatch,tmp_path):
    workspace=tmp_path/'workspace';workspace.mkdir()
    allowed=workspace/'saved.blend';allowed.write_bytes(b'BLENDER')
    outside=tmp_path/'private.blend';outside.write_bytes(b'BLENDER')
    (workspace/'escape.blend').symlink_to(outside)
    monkeypatch.setenv('BLENDER_RENDER_ROOT',str(workspace))
    assert scene_path(str(allowed))==allowed
    for file in [outside,workspace/'escape.blend',tmp_path/'missing.blend']:
        with pytest.raises((ValueError,OSError)):
            scene_path(str(file))
    with pytest.raises(ValueError):
        output_path('a'*36)
    assert output_path(str(uuid4())).is_relative_to(workspace)
    (workspace/'Blender MCP Renders').rename(workspace/'safe')
    (workspace/'Blender MCP Renders').symlink_to(tmp_path)
    with pytest.raises(ValueError):
        output_path(str(uuid4()))


def test_broker_rejects_external_redis(monkeypatch):
    for uri in ['redis://10.0.0.1:6379/0','rediss://127.0.0.1:6379/0','redis://user:password@localhost:6379/0']:
        monkeypatch.setenv('BLENDER_RENDER_REDIS_URL',uri)
        with pytest.raises(ValueError):
            connection()


def test_unconfigured_render_fails_closed(monkeypatch,tmp_path):
    monkeypatch.delenv('BLENDER_RENDER_ROOT',raising=False)
    monkeypatch.delenv('BLENDER_QUALITY_ROOT',raising=False)
    result=execute_workflow('workflow.render_enqueue',{'scene_path':str(tmp_path/'a.blend')},no_bridge)
    assert result['status']=='blocked'


def test_broker_down_is_a_typed_block_not_an_uncaught_exception(monkeypatch,tmp_path):
    root=tmp_path/'workspace';root.mkdir()
    scene=root/'saved.blend';scene.write_bytes(b'BLENDER')
    monkeypatch.setenv('BLENDER_RENDER_ROOT',str(root))
    monkeypatch.setenv('BLENDER_RENDER_REDIS_URL','redis://127.0.0.1:6398/0')
    result=execute_workflow('workflow.render_enqueue',{'scene_path':str(scene)},no_bridge)
    assert result['status']=='blocked' and 'ConnectionError' in result['error']
