#!/usr/bin/env python3
"""
Tests for the v3.1.1 needs_input payload (Issue #6).

Coverage:
  apply_params:
    1. Unknown override key → typed needs_input with kind="enum" + choices
    2. Empty new_values when script has tunable params → needs_input listing keys
    3. Valid override (no change in behaviour) → still works (regression)

  router_set_goal:
    4. Empty goal → needs_input(field="goal", kind="string")
    5. Invalid profile → needs_input(field="profile", kind="enum", choices=[...])
    6. Valid input → still works (regression)

  plan:
    7. Missing goal (no session goal, no input goal) → needs_input(field="goal")

  3-step flow:
    8. needs_input → answer → needs_input → answer → success (apply_params)

Self-contained: stubs FastMCP, mocks send_command, no live Blender required.

Run:
    cd <repo>
    python3 tests/test_needs_input.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "server"))


def _stub_fastmcp() -> None:
    if "mcp.server.fastmcp" in sys.modules:
        return
    fake_mcp = types.ModuleType("mcp")
    fake_server = types.ModuleType("mcp.server")
    fake_fast = types.ModuleType("mcp.server.fastmcp")

    class _FastMCP:
        def __init__(self, *a, **kw): pass
        def tool(self, **kw):
            def deco(fn): return fn
            return deco
        def run(self, *a, **kw): pass

    fake_fast.FastMCP = _FastMCP
    sys.modules["mcp"] = fake_mcp
    sys.modules["mcp.server"] = fake_server
    sys.modules["mcp.server.fastmcp"] = fake_fast


def _load_server():
    _stub_fastmcp()
    spec = importlib.util.spec_from_file_location(
        "blender_mcp_server_under_test_needs_input",
        str(REPO / "server" / "blender_mcp_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    def fake_send(cmd, params=None, *a, **kw):
        return {"result": {"command": cmd, "echo_chars": len((params or {}).get("code", ""))}}
    mod.send_command = fake_send
    return mod


def _parse(out):
    """format_result returns either an `Error: ...` string or a JSON envelope
    `{status, tokens_est, data}`. Unwrap the data payload like the existing
    CADAM tests do — needs_input lives inside `data` for the server tools.
    For the agent_loop tools we mock format_result with json.dumps so the
    payload is at the top level; in that case env has no 'data' key and we
    return env unchanged."""
    if isinstance(out, str) and out.startswith("Error:"):
        return {"_error_string": out}
    try:
        env = json.loads(out)
    except Exception:
        return {"_raw": out}
    return env.get("data", env)


# ─── helpers for the agent_loop side ─────────────────────────────────────────

def _load_agent_loop():
    """Import server/agent_loop.py with the same stub trick."""
    _stub_fastmcp()
    # session_state and verify are required deps; load them as siblings
    sys.path.insert(0, str(REPO / "server"))
    spec = importlib.util.spec_from_file_location(
        "agent_loop_under_test", str(REPO / "server" / "agent_loop.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_session(agent_loop_mod, goal=None, profile="default"):
    """Build a SessionState with sensible defaults for tests."""
    session = agent_loop_mod.SessionState(session_id="test-session")
    session.goal = goal
    session.profile = profile
    session.conversation_turn = 0
    return session


def _mock_format_result(payload):
    """Mirror of server.format_result: JSON-stringify."""
    return json.dumps(payload)


def _mock_send_command(cmd, params=None, *a, **kw):
    return {"result": {"command": cmd}}


# ============================================================================
# apply_params needs_input tests
# ============================================================================

async def test_apply_params_unknown_key_returns_needs_input(mod):
    good = (
        "# --- PARAMETERS ---\n"
        "WIDTH = 1.0\n"
        "HEIGHT = 2.0\n"
        "# --- /PARAMETERS ---\n"
        "import bpy\n"
    )
    out = await mod.blender_run_bpy_script(script=good, cache=True, require_parameters_block=True)
    sid = _parse(out)["script_id"]

    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid,
        new_values={"DEPTH": 7.0},  # DEPTH is not in PARAMETERS
        rerun=False,
    ))
    r = _parse(out)
    assert r.get("status") == "needs_input", f"expected needs_input, got {r}"
    ni = r["needs_input"]
    assert ni["field"] == "DEPTH"
    assert ni["kind"] == "enum"
    assert set(ni["choices"]) == {"WIDTH", "HEIGHT"}
    assert ni["available"] == {"WIDTH": 1.0, "HEIGHT": 2.0}
    assert "blender_apply_params" in ni["hint"]
    print("  apply_params unknown key → needs_input(enum): OK")


async def test_apply_params_empty_overrides_returns_needs_input(mod):
    good = (
        "# --- PARAMETERS ---\n"
        "ENERGY = 800.0\n"
        "# --- /PARAMETERS ---\n"
        "import bpy\n"
    )
    out = await mod.blender_run_bpy_script(script=good, cache=True, require_parameters_block=True)
    sid = _parse(out)["script_id"]

    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid,
        new_values={},
        rerun=False,
    ))
    r = _parse(out)
    assert r.get("status") == "needs_input", f"expected needs_input, got {r}"
    ni = r["needs_input"]
    assert ni["field"] == "ENERGY"
    assert ni["kind"] == "number"
    assert ni["default"] == 800.0
    assert ni["available"] == {"ENERGY": 800.0}
    print("  apply_params empty overrides → needs_input(default): OK")


async def test_apply_params_valid_override_still_works(mod):
    """Regression: valid overrides must continue to succeed."""
    good = (
        "# --- PARAMETERS ---\n"
        "X = 1\n"
        "# --- /PARAMETERS ---\n"
        "import bpy\n"
    )
    out = await mod.blender_run_bpy_script(script=good, cache=True, require_parameters_block=True)
    sid = _parse(out)["script_id"]

    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid,
        new_values={"X": 42},
        rerun=False,
    ))
    r = _parse(out)
    assert r.get("status") != "needs_input", f"unexpected needs_input: {r}"
    assert r["parameters"]["X"] == 42
    print("  apply_params valid override → success (regression): OK")


# ============================================================================
# router_set_goal needs_input tests
# ============================================================================

async def test_router_empty_goal_returns_needs_input(agent_loop_mod):
    session = _make_session(agent_loop_mod)
    inp = agent_loop_mod.SetGoalInput(goal="", profile="default")
    out = await agent_loop_mod.blender_router_set_goal(
        session, _mock_send_command, _mock_format_result, inp,
    )
    r = _parse(out)
    assert r.get("status") == "needs_input", f"expected needs_input, got {r}"
    ni = r["needs_input"]
    assert ni["field"] == "goal"
    assert ni["kind"] == "string"
    assert "non-empty goal" in ni["description"]
    print("  router_set_goal empty goal → needs_input(string): OK")


async def test_router_invalid_profile_returns_needs_input(agent_loop_mod):
    session = _make_session(agent_loop_mod)
    inp = agent_loop_mod.SetGoalInput(goal="Build a chair", profile="bogus")
    out = await agent_loop_mod.blender_router_set_goal(
        session, _mock_send_command, _mock_format_result, inp,
    )
    r = _parse(out)
    assert r.get("status") == "needs_input", f"expected needs_input, got {r}"
    ni = r["needs_input"]
    assert ni["field"] == "profile"
    assert ni["kind"] == "enum"
    assert "default" in ni["choices"]
    assert "llm-guided" in ni["choices"]
    assert ni["default"] == "default"
    print("  router_set_goal invalid profile → needs_input(enum): OK")


async def test_router_valid_input_still_works(agent_loop_mod):
    """Regression."""
    session = _make_session(agent_loop_mod)
    inp = agent_loop_mod.SetGoalInput(goal="Build a chair", profile="llm-guided")
    out = await agent_loop_mod.blender_router_set_goal(
        session, _mock_send_command, _mock_format_result, inp,
    )
    r = _parse(out)
    # _parse unwraps the {status, data: {...}} envelope, so success-payload
    # fields land at the top level.
    assert "needs_input" not in r, f"unexpected needs_input: {r}"
    assert r["goal"] == "Build a chair"
    assert r["profile"] == "llm-guided"
    print("  router_set_goal valid input → success (regression): OK")


# ============================================================================
# plan needs_input test
# ============================================================================

async def test_plan_missing_goal_returns_needs_input(agent_loop_mod):
    session = _make_session(agent_loop_mod, goal=None)  # no session goal
    inp = agent_loop_mod.PlanInput(goal=None)            # no input goal
    out = await agent_loop_mod.blender_plan(
        session, _mock_send_command, _mock_format_result, inp,
    )
    r = _parse(out)
    assert r.get("status") == "needs_input", f"expected needs_input, got {r}"
    ni = r["needs_input"]
    assert ni["field"] == "goal"
    assert ni["kind"] == "string"
    assert "blender_router_set_goal" in ni["hint"]
    print("  plan missing goal → needs_input(string): OK")


# ============================================================================
# 3-step needs_input → answer → needs_input → answer → success
# ============================================================================

async def test_three_step_clarification_flow(mod):
    """The full conversational pattern from issue #6 acceptance criteria."""
    good = (
        "# --- PARAMETERS ---\n"
        "WIDTH = 1.0\n"
        "DEPTH = 2.0\n"
        "# --- /PARAMETERS ---\n"
        "import bpy\n"
    )
    out = await mod.blender_run_bpy_script(script=good, cache=True, require_parameters_block=True)
    sid = _parse(out)["script_id"]

    # Step 1: caller passes wrong key → needs_input
    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid, new_values={"HEIGHT": 9.0}, rerun=False,
    ))
    r1 = _parse(out)
    assert r1["status"] == "needs_input"
    assert "WIDTH" in r1["needs_input"]["choices"]

    # Step 2: caller corrects to a valid key but with an empty payload now
    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid, new_values={}, rerun=False,
    ))
    r2 = _parse(out)
    assert r2["status"] == "needs_input"

    # Step 3: caller now passes a valid override → success
    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid, new_values={"WIDTH": 5.5}, rerun=False,
    ))
    r3 = _parse(out)
    assert r3.get("status") != "needs_input", f"still needs input: {r3}"
    assert r3["parameters"]["WIDTH"] == 5.5
    assert r3["parameters"]["DEPTH"] == 2.0  # untouched
    print("  3-step needs_input → answer → needs_input → answer → success: OK")


# ============================================================================
# Driver
# ============================================================================

async def main():
    mod = _load_server()
    agent_loop_mod = _load_agent_loop()

    print("\n=== needs_input v3.1.1 — Issue #6 ===\n")

    # apply_params
    await test_apply_params_unknown_key_returns_needs_input(mod)
    await test_apply_params_empty_overrides_returns_needs_input(mod)
    await test_apply_params_valid_override_still_works(mod)

    # router_set_goal
    await test_router_empty_goal_returns_needs_input(agent_loop_mod)
    await test_router_invalid_profile_returns_needs_input(agent_loop_mod)
    await test_router_valid_input_still_works(agent_loop_mod)

    # plan
    await test_plan_missing_goal_returns_needs_input(agent_loop_mod)

    # 3-step flow
    await test_three_step_clarification_flow(mod)

    print("\nALL needs_input TESTS PASSED\n")


if __name__ == "__main__":
    asyncio.run(main())
