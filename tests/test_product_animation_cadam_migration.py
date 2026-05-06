#!/usr/bin/env python3
"""
Tests for the v3.1.1 product_animation_tools.py CADAM migration (Issue #10).

Verifies:
  1. run_cadam_script wraps an opaque snippet in a PARAMETERS block, validates,
     caches, and returns a script_id.
  2. run_cadam_script blocks dangerous code (server-side AST gate still active).
  3. register_product_tools accepts the new 4-arg signature.
  4. register_product_tools falls back to legacy signature (3-arg) cleanly.
  5. When wired with run_cadam_script_fn, every product-animation tool emits a
     non-None script_id (proving every site went through the contract).
  6. apply_params can be called on a script_id produced by a product-animation
     site — i.e. the cache entry is genuine.

Self-contained: stubs FastMCP, mocks send_command, no live Blender required.

Run:
    cd <repo>
    python3 tests/test_product_animation_cadam_migration.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
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
        "blender_mcp_server_pa_migration",
        str(REPO / "server" / "blender_mcp_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def fake_send(cmd, params=None, *a, **kw):
        return {"result": {"command": cmd, "echo_chars": len((params or {}).get("code", ""))}}
    mod.send_command = fake_send
    return mod


def _parse(out):
    if isinstance(out, str) and out.startswith("Error:"):
        return {"_error_string": out}
    try:
        env = json.loads(out)
    except Exception:
        return {"_raw": out}
    return env.get("data", env)


# ============================================================================
# 1. run_cadam_script unit tests
# ============================================================================

def test_run_cadam_script_wraps_and_caches(mod):
    snippet = "import bpy\nprint('hello')"
    r = mod.run_cadam_script(
        snippet,
        parameters={"OBJECT_NAME": "Cube", "ENERGY": 800.0},
        cache=True,
        script_kind="test_kind",
    )
    assert r.get("script_id"), f"expected script_id, got {r}"
    assert r["parameters"] == {"OBJECT_NAME": "Cube", "ENERGY": 800.0}
    sid = r["script_id"]
    # Cached entry should exist with the kind tag
    entry = mod._SCRIPT_CACHE.get(sid)
    assert entry is not None
    assert entry["script_kind"] == "test_kind"
    # The wrapped script must contain the PARAMETERS block + the original code
    assert "# --- PARAMETERS ---" in entry["script"]
    assert "OBJECT_NAME = " in entry["script"]
    assert "print('hello')" in entry["script"]
    print("  run_cadam_script wraps + caches with kind tag: OK")


def test_run_cadam_script_blocks_dangerous_code(mod):
    snippet = "import os\nos.system('rm -rf /')"
    r = mod.run_cadam_script(snippet, parameters={"X": 1}, cache=False)
    assert r.get("blocked_by_policy") is True, f"expected block, got {r}"
    assert "safety policy" in r.get("error", "")
    print("  run_cadam_script blocks `import os` server-side: OK")


def test_run_cadam_script_rejects_bad_param_names(mod):
    # lowercase parameter names are not allowed
    r = mod.run_cadam_script("import bpy", parameters={"object_name": "Cube"}, cache=False)
    assert r.get("blocked_by_policy") is True
    assert "UPPER_SNAKE_CASE" in r.get("error", "")
    print("  run_cadam_script rejects lowercase param names: OK")


def test_run_cadam_script_no_params_works(mod):
    """Empty parameters dict still goes through the contract (cache + AST)."""
    r = mod.run_cadam_script("import bpy\npass", parameters={}, cache=True, script_kind="empty")
    assert r.get("script_id"), f"expected script_id, got {r}"
    sid = r["script_id"]
    entry = mod._SCRIPT_CACHE.get(sid)
    assert entry is not None
    # Empty PARAMETERS block must still be present (server validates structure)
    assert "# --- PARAMETERS ---" in entry["script"]
    assert "# --- /PARAMETERS ---" in entry["script"]
    print("  run_cadam_script handles empty parameters: OK")


# ============================================================================
# 2. register_product_tools signature compat tests
# ============================================================================

def test_register_product_tools_accepts_4_args():
    from product_animation_tools import register_product_tools
    sig = inspect.signature(register_product_tools)
    params = list(sig.parameters.keys())
    assert "run_cadam_script_fn" in params, f"missing run_cadam_script_fn arg in {params}"
    # Must be optional (default None) so legacy 3-arg calls still work
    default = sig.parameters["run_cadam_script_fn"].default
    assert default is None, f"run_cadam_script_fn must default to None, got {default}"
    print("  register_product_tools has optional 4th arg (run_cadam_script_fn): OK")


# ============================================================================
# 3. End-to-end: every migrated site emits a script_id when wired
# ============================================================================

class _CapturingMCP:
    """Stub that captures the registered tool functions so we can call them."""
    def __init__(self):
        self.tools = {}
    def tool(self, **kw):
        name = kw.get("name", "<unknown>")
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


async def test_every_product_tool_emits_script_id(mod):
    from product_animation_tools import (
        register_product_tools,
        ProductMaterialInput, ProductLightingInput, ProductCameraInput,
        ProductRenderInput, FCurveInput,
    )

    # Reset the cache so we can count fresh entries
    mod._SCRIPT_CACHE.clear()
    cap = _CapturingMCP()
    register_product_tools(cap, mod.send_command, lambda x: json.dumps(x), mod.run_cadam_script)
    assert "blender_product_material" in cap.tools

    # blender_product_material
    mat = ProductMaterialInput(preset="glossy_plastic", object_name="Cube")
    out = await cap.tools["blender_product_material"](mat)
    r = _parse(out)
    assert r.get("script_id"), f"product_material missing script_id: {r}"

    # blender_product_lighting
    lit = ProductLightingInput(preset="product_studio")
    out = await cap.tools["blender_product_lighting"](lit)
    r = _parse(out)
    assert r.get("script_id"), f"product_lighting missing script_id: {r}"

    # blender_product_camera
    cam = ProductCameraInput(style="turntable", target_object="Cube")
    out = await cap.tools["blender_product_camera"](cam)
    r = _parse(out)
    assert r.get("script_id"), f"product_camera missing script_id: {r}"

    # blender_product_render_setup (emits 2 script_ids — render + compositor)
    rd = ProductRenderInput(quality="balanced", resolution="1080p", output_path="/tmp/test/####")
    out = await cap.tools["blender_product_render_setup"](rd)
    r = _parse(out)
    assert r["render"].get("script_id"), f"render-step missing script_id: {r}"
    assert r["compositor"].get("script_id"), f"compositor-step missing script_id: {r}"

    # blender_fcurve_edit
    fc = FCurveInput(object_name="Camera", data_path="location", interpolation="BEZIER")
    out = await cap.tools["blender_fcurve_edit"](fc)
    r = _parse(out)
    assert r.get("script_id"), f"fcurve_edit missing script_id: {r}"

    # Cache should now have at least 6 entries (one per call above; the
    # render_setup tool emits 2)
    assert len(mod._SCRIPT_CACHE) >= 6, f"expected >=6 cache entries, got {len(mod._SCRIPT_CACHE)}"
    print(f"  every product tool routed through CADAM ({len(mod._SCRIPT_CACHE)} script_ids cached): OK")


async def test_apply_params_works_on_product_tool_script(mod):
    """Sanity: a script_id produced by a product_animation site is genuinely
    re-runnable via apply_params (the cache entry is well-formed)."""
    from product_animation_tools import register_product_tools, ProductMaterialInput
    mod._SCRIPT_CACHE.clear()
    cap = _CapturingMCP()
    register_product_tools(cap, mod.send_command, lambda x: json.dumps(x), mod.run_cadam_script)
    out = await cap.tools["blender_product_material"](
        ProductMaterialInput(preset="gold", object_name="Ring")
    )
    sid = _parse(out)["script_id"]

    # Re-run with a tweaked PRESET parameter
    out2 = await mod.blender_apply_params(mod.ApplyParamsInput(
        script_id=sid,
        new_values={"PRESET": "rose_gold"},
        rerun=False,
    ))
    r = _parse(out2)
    # When rerun=False we get the rewritten parameters back
    assert r["parameters"]["PRESET"] == "rose_gold"
    assert r["parameters"]["OBJECT_NAME"] == "Ring"
    print("  apply_params works on a product_animation script_id (round-trip): OK")


# ============================================================================
# 4. Legacy back-compat: 3-arg register call still works
# ============================================================================

def test_legacy_3arg_register_still_works(mod):
    from product_animation_tools import register_product_tools
    cap = _CapturingMCP()
    # Call WITHOUT run_cadam_script_fn — should not raise
    names = register_product_tools(cap, mod.send_command, lambda x: json.dumps(x))
    assert "blender_product_material" in names
    assert len(cap.tools) >= 6
    print("  legacy 3-arg register_product_tools still works: OK")


# ============================================================================
# Driver
# ============================================================================

async def main():
    mod = _load_server()
    print("\n=== product_animation CADAM migration — Issue #10 ===\n")

    # run_cadam_script unit tests
    test_run_cadam_script_wraps_and_caches(mod)
    test_run_cadam_script_blocks_dangerous_code(mod)
    test_run_cadam_script_rejects_bad_param_names(mod)
    test_run_cadam_script_no_params_works(mod)

    # Signature compat
    test_register_product_tools_accepts_4_args()
    test_legacy_3arg_register_still_works(mod)

    # End-to-end migration
    await test_every_product_tool_emits_script_id(mod)
    await test_apply_params_works_on_product_tool_script(mod)

    print("\nALL product_animation CADAM migration TESTS PASSED\n")


if __name__ == "__main__":
    asyncio.run(main())
