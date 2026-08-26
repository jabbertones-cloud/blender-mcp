import asyncio

from server.agent_loop import ActInput, blender_act
from server.session_state import SessionState, PlanStep


def _run(coro):
    return asyncio.run(coro)


def test_act_uses_step_capability_and_bridge_mapping():
    calls = []
    session = SessionState(session_id="t")
    session.todo = [PlanStep(step_id="step_1", description="add cube", tool_hint="scene.create_object", args={"type": "cube"})]

    def send(command, params):
        calls.append((command, params))
        return {"name": "Cube"}

    result = _run(blender_act(session, send, lambda x: x, ActInput(step_id="step_1")))
    assert calls == [("create_object", {"type": "cube"})]
    assert result["capability"] == "scene.create_object"
    assert result["bridge_command"] == "create_object"


def test_act_never_sends_unknown_model_string_to_socket():
    calls = []
    session = SessionState(session_id="t")
    session.todo = [PlanStep(step_id="step_1", description="add cube", tool_hint="scene.create_object")]

    def send(command, params):
        calls.append((command, params))
        return {}

    result = _run(blender_act(session, send, lambda x: x, ActInput(step_id="step_1", tool_name="blender_make_magic")))
    assert calls == []
    assert result["code"] == "CAPABILITY_NOT_FOUND"


def test_act_accepts_legacy_mcp_alias_but_maps_before_socket():
    calls = []
    session = SessionState(session_id="t")
    session.todo = [PlanStep(step_id="step_1", description="add cube", tool_hint="scene.create_object")]

    def send(command, params):
        calls.append((command, params))
        return {"ok": True}

    result = _run(blender_act(session, send, lambda x: x, ActInput(step_id="step_1", tool_name="blender_create_object", tool_args={"type": "cube"})))
    assert calls == [("create_object", {"type": "cube"})]
    assert result["capability"] == "scene.create_object"


def test_step_args_are_used_when_caller_omits_args():
    calls = []
    session = SessionState(session_id="t")
    session.todo = [PlanStep(step_id="step_1", description="move", tool_hint="scene.modify_object", args={"name": "Cube", "location": [1, 2, 3]})]

    def send(command, params):
        calls.append((command, params))
        return {"ok": True}

    _run(blender_act(session, send, lambda x: x, ActInput(step_id="step_1")))
    assert calls == [("modify_object", {"name": "Cube", "location": [1, 2, 3]})]
