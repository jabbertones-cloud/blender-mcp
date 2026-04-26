#!/usr/bin/env python3
"""
CADAM Port — P4 (list_available_assets).

Self-contained: stubs out the FastMCP runtime, scans a temporary cache, asserts
asset grouping/resolution detection/refresh semantics. Runs without Blender.

Run:
    cd <repo>
    python3 tests/test_cadam_p4_list_assets.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import tempfile
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
        "blender_mcp_server_under_test_p4",
        str(REPO / "server" / "blender_mcp_server.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _parse(s):
    if isinstance(s, str) and s.startswith("Error:"):
        return {"_error_string": s}
    env = json.loads(s)
    return env.get("data", env)


async def test_empty_cache_no_crash(mod):
    # No env var — clean baseline
    if "OPENCLAW_ASSET_CACHE" in os.environ:
        del os.environ["OPENCLAW_ASSET_CACHE"]
    out = await mod.blender_list_available_assets(mod.ListAvailableAssetsInput(refresh=True))
    r = _parse(out)
    assert isinstance(r["providers"], list) and len(r["providers"]) >= 1
    assert "global_hints" in r
    print("  empty-cache shape OK")


async def test_polyhaven_hdri_grouping(mod):
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OPENCLAW_ASSET_CACHE"] = tmp
        ph = Path(tmp) / "polyhaven"
        ph.mkdir()
        (ph / "kiara_1_dawn_1k.exr").write_bytes(b"x" * 100)
        (ph / "kiara_1_dawn_2k.exr").write_bytes(b"x" * 1000)

        out = await mod.blender_list_available_assets(
            mod.ListAvailableAssetsInput(refresh=True, providers=["polyhaven"]))
        r = _parse(out)
        ph_entry = next(p for p in r["providers"] if p["name"] == "polyhaven")
        assert ph_entry["total_assets"] == 1, ph_entry
        asset = ph_entry["assets"][0]
        assert asset["id"] == "kiara_1_dawn"
        assert asset["type"] == "hdri"
        assert sorted(asset["resolutions_available"]) == ["1k", "2k"]
        assert len(asset["files"]) == 2
        print("  HDRI grouping (kiara_1_dawn @ 1k+2k): OK")


async def test_polyhaven_pbr_channel_grouping(mod):
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OPENCLAW_ASSET_CACHE"] = tmp
        ph = Path(tmp) / "polyhaven"
        ph.mkdir()
        (ph / "brown_mud_leaves_01_diff_2k.jpg").write_bytes(b"x")
        (ph / "brown_mud_leaves_01_nor_gl_2k.jpg").write_bytes(b"x")
        (ph / "brown_mud_leaves_01_rough_2k.jpg").write_bytes(b"x")

        out = await mod.blender_list_available_assets(
            mod.ListAvailableAssetsInput(refresh=True, providers=["polyhaven"]))
        r = _parse(out)
        ph_entry = next(p for p in r["providers"] if p["name"] == "polyhaven")
        ids = [a["id"] for a in ph_entry["assets"]]
        assert "brown_mud_leaves_01" in ids, ids
        pbr = next(a for a in ph_entry["assets"] if a["id"] == "brown_mud_leaves_01")
        assert pbr["type"] == "texture"
        assert len(pbr["files"]) == 3
        print("  PBR channel grouping (3 channels): OK")


async def test_asset_types_filter(mod):
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OPENCLAW_ASSET_CACHE"] = tmp
        ph = Path(tmp) / "polyhaven"
        ph.mkdir()
        (ph / "kiara_1_dawn_2k.exr").write_bytes(b"x")
        (ph / "wood_diff_2k.jpg").write_bytes(b"x")

        out = await mod.blender_list_available_assets(
            mod.ListAvailableAssetsInput(
                refresh=True, providers=["polyhaven"], asset_types=["hdri"]))
        r = _parse(out)
        ph_entry = next(p for p in r["providers"] if p["name"] == "polyhaven")
        types_seen = {a["type"] for a in ph_entry["assets"]}
        assert types_seen == {"hdri"}, types_seen
        print("  asset_types=['hdri'] filter excludes textures: OK")


async def test_refresh_semantics(mod):
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["OPENCLAW_ASSET_CACHE"] = tmp
        ph = Path(tmp) / "polyhaven"
        ph.mkdir()
        (ph / "kiara_1_dawn_2k.exr").write_bytes(b"x")
        # First call populates the listing cache
        await mod.blender_list_available_assets(
            mod.ListAvailableAssetsInput(refresh=True, providers=["polyhaven"]))
        # Add a file AFTER caching
        (ph / "studio_03_2k.exr").write_bytes(b"y")
        # Second call without refresh — should NOT see the new file
        out = await mod.blender_list_available_assets(
            mod.ListAvailableAssetsInput(refresh=False, providers=["polyhaven"]))
        r = _parse(out)
        ids = [a["id"] for a in r["providers"][0]["assets"]]
        assert "studio_03" not in ids, f"refresh=False should still hit listing cache: {ids}"
        # Third call with refresh — should see it
        out = await mod.blender_list_available_assets(
            mod.ListAvailableAssetsInput(refresh=True, providers=["polyhaven"]))
        r = _parse(out)
        ids = [a["id"] for a in r["providers"][0]["assets"]]
        assert "studio_03" in ids, f"refresh=True should re-scan: {ids}"
        print("  refresh=True bypasses listing cache: OK")


async def test_unknown_provider_rejected(mod):
    out = await mod.blender_list_available_assets(
        mod.ListAvailableAssetsInput(providers=["does_not_exist"]))
    r = _parse(out)
    assert "_error_string" in r and "Unknown provider" in r["_error_string"]
    print("  unknown provider rejected: OK")


def test_system_prompt_mentions_list_assets(mod):
    assert "blender_list_available_assets" in mod.BPY_GENERATION_SYSTEM_PROMPT
    assert "blender_apply_params" in mod.BPY_GENERATION_SYSTEM_PROMPT
    print("  system prompt references new tools: OK")


async def main():
    print("=== P4 list_available_assets tests ===")
    mod = _load_server()
    await test_empty_cache_no_crash(mod)
    await test_polyhaven_hdri_grouping(mod)
    await test_polyhaven_pbr_channel_grouping(mod)
    await test_asset_types_filter(mod)
    await test_refresh_semantics(mod)
    await test_unknown_provider_rejected(mod)
    test_system_prompt_mentions_list_assets(mod)
    # Cleanup
    os.environ.pop("OPENCLAW_ASSET_CACHE", None)
    print("\nALL P4 TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
