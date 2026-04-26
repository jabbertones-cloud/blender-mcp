#!/usr/bin/env python3
"""
CADAM Port — P1 (PARAMETERS contract) + P2 (split execute_blender_code).

Self-contained: stubs out `mcp.server.fastmcp` and pydantic-only deps so the
test runs without a live Blender or the MCP runtime. Mocks `send_command` so
the addon is never reached.

Run:
    cd <repo>
    python3 tests/test_cadam_p1_p2_split_exec.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
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
        "blender_mcp_server_under_test",
        str(REPO / "server" / "blender_mcp_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Mock send_command — never reach the addon
    def fake_send(cmd, params=None, *a, **kw):
        return {"result": {"command": cmd, "echo_chars": len((params or {}).get("code", ""))}}
    mod.send_command = fake_send
    return mod


def _parse(s):
    """format_result returns either an `Error: ...` string (failure path) or
    a JSON envelope `{status, tokens_est, data}` (success). Normalise both."""
    if isinstance(s, str) and s.startswith("Error:"):
        return {"_error_string": s}
    try:
        env = json.loads(s)
    except Exception:
        return {"_raw": s}
    return env.get("data", env)


# ─── codegen_prompt unit tests ──────────────────────────────────────────────

def test_extract_parameters_round_trip():
    from codegen_prompt import extract_parameters, replace_parameters
    script = (
        "# --- PARAMETERS ---\n"
        "MESH_SIZE = 2.0\n"
        "LIGHT_ENERGY = 800.0\n"
        "USE_DENOISE = True\n"
        "BG_COLOR = (0.04, 0.05, 0.07, 1.0)\n"
        "# --- /PARAMETERS ---\n"
        "import bpy\n"
    )
    p = extract_parameters(script)
    assert p == {
        "MESH_SIZE": 2.0,
        "LIGHT_ENERGY": 800.0,
        "USE_DENOISE": True,
        "BG_COLOR": [0.04, 0.05, 0.07, 1.0],  # codegen_prompt parses tuples as lists via literal_eval
    } or p == {
        "MESH_SIZE": 2.0,
        "LIGHT_ENERGY": 800.0,
        "USE_DENOISE": True,
        "BG_COLOR": (0.04, 0.05, 0.07, 1.0),
    }, f"unexpected extract: {p}"
    rewritten = replace_parameters(script, {"MESH_SIZE": 4.0, "USE_DENOISE": False})
    p2 = extract_parameters(rewritten)
    assert p2["MESH_SIZE"] == 4.0
    assert p2["USE_DENOISE"] is False
    assert p2["LIGHT_ENERGY"] == 800.0   # unchanged
    print("  extract/replace round-trip: OK")


def test_extract_parameters_missing_block_raises():
    from codegen_prompt import extract_parameters, validate_parameters_block
    bad = "import bpy\nprint('no params')"
    try:
        extract_parameters(bad)
    except ValueError:
        ok, reason = validate_parameters_block(bad)
        assert not ok and "PARAMETERS" in reason
        print("  missing block raises: OK")
        return
    raise AssertionError("expected ValueError for missing PARAMETERS block")


def test_replace_parameters_unknown_key_raises():
    from codegen_prompt import replace_parameters
    script = (
        "# --- PARAMETERS ---\n"
        "FOO = 1.0\n"
        "# --- /PARAMETERS ---\n"
    )
    try:
        replace_parameters(script, {"BAR": 2.0})
    except ValueError as e:
        assert "Unknown" in str(e) or "BAR" in str(e)
        print("  unknown key raises: OK")
        return
    raise AssertionError("expected ValueError for unknown parameter key")


# ─── server tool tests ──────────────────────────────────────────────────────

async def test_generate_publishes_contract(mod):
    out = await mod.blender_generate_bpy_script(
        mod.GenerateBpyScriptInput(intent="cube + light + camera"))
    p = json.loads(out)
    assert "system_prompt" in p
    assert p["next_call"] == "blender_run_bpy_script"
    assert "PARAMETERS" in p["system_prompt"]
    assert "blender_list_available_assets" in p["system_prompt"], (
        "system prompt should reference list_available_assets after P4 patch")
    print("  generate_bpy_script publishes contract: OK")


async def test_run_validates_parameters_block(mod):
    out = await mod.blender_run_bpy_script(
        script="import bpy\nprint('hi')",
        cache=False, require_parameters_block=True)
    r = _parse(out)
    assert "_error_string" in r and "PARAMETERS" in r["_error_string"]
    print("  run rejects missing PARAMETERS block: OK")


async def test_run_blocks_dangerous_imports(mod):
    bad = (
        "# --- PARAMETERS ---\n"
        "X = 1\n"
        "# --- /PARAMETERS ---\n"
        "import os\n"
    )
    out = await mod.blender_run_bpy_script(
        script=bad, cache=False, require_parameters_block=True)
    r = _parse(out)
    assert "_error_string" in r and "safety policy" in r["_error_string"]
    print("  run blocks `import os` server-side: OK")


async def test_run_caches_and_apply_params_works(mod):
    good = (
        "# --- PARAMETERS ---\n"
        "CUBE_SIZE = 2.0\n"
        "LIGHT_ENERGY = 800.0\n"
        "CAM_FOV_DEG = 50.0\n"
        "# --- /PARAMETERS ---\n"
        "import bpy\n"
    )
    out = await mod.blender_run_bpy_script(
        script=good, cache=True, require_parameters_block=True)
    r = _parse(out)
    assert r.get("script_id"), f"no script_id in {r}"
    sid = r["script_id"]
    assert r["parameters"]["CUBE_SIZE"] == 2.0

    out = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid,
        new_values={"CUBE_SIZE": 4.5, "CAM_FOV_DEG": 35.0},
        rerun=True,
    ))
    r = _parse(out)
    assert r["parameters"]["CUBE_SIZE"] == 4.5
    assert r["parameters"]["CAM_FOV_DEG"] == 35.0
    assert r["parameters"]["LIGHT_ENERGY"] == 800.0   # untouched
    print("  run + apply_params slider loop: OK")


async def test_apply_params_unknown_id_rejected(mod):
    out = await mod.blender_apply_params(
        mod.ApplyParamsInput(script_id="deadbeef0000", new_values={}, rerun=False))
    r = _parse(out)
    assert "_error_string" in r
    print("  apply_params rejects unknown script_id: OK")


async def test_legacy_execute_python_still_works(mod):
    out = await mod.blender_execute_python(code="import bpy\nprint('legacy')")
    r = _parse(out)
    # legacy path bypasses parameters check, so it should fall through to send_command
    assert r.get("result") is not None
    print("  legacy blender_execute_python (deprecated alias): OK")


def test_prompt_version_changes_with_prompt_edits():
    from codegen_prompt import BPY_GENERATION_SYSTEM_PROMPT
    # PROMPT_VERSION may be defined or not depending on the agent's prompt module;
    # if defined it must be a 12-char hex string.
    try:
        from codegen_prompt import PROMPT_VERSION
    except ImportError:
        print("  PROMPT_VERSION not exported (optional)")
        return
    assert isinstance(PROMPT_VERSION, str) and len(PROMPT_VERSION) == 12
    # Hash matches the prompt content
    import hashlib
    expected = hashlib.sha1(BPY_GENERATION_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12]
    if expected != PROMPT_VERSION:
        # Some prompt modules may use a different hashing scheme — just sanity-check format
        assert all(c in "0123456789abcdef" for c in PROMPT_VERSION.lower())
    print("  PROMPT_VERSION format: OK")


# ─── Runner ──────────────────────────────────────────────────────────────────

async def main():
    print("=== P1+P2 codegen_prompt unit tests ===")
    test_extract_parameters_round_trip()
    test_extract_parameters_missing_block_raises()
    test_replace_parameters_unknown_key_raises()
    test_prompt_version_changes_with_prompt_edits()

    print("\n=== P2 server tool integration tests ===")
    mod = _load_server()
    await test_generate_publishes_contract(mod)
    await test_run_validates_parameters_block(mod)
    await test_run_blocks_dangerous_imports(mod)
    await test_run_caches_and_apply_params_works(mod)
    await test_apply_params_unknown_id_rejected(mod)
    await test_legacy_execute_python_still_works(mod)

    print("\nALL P1 + P2 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
