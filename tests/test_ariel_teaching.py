"""Ariel teaching tests — NEW file (2026-11-17 reconstruction).

This is a deliberately minimal, live-path test file for the teaching commit.
It is NOT a restoration of the test suite removed 2026-11-08 on Scott's
order (see TESTS-REMOVED.md) — it only pins the behaviours this commit adds:
the registry building at 68 capabilities, Ariel's own search terms routing
to the right capabilities, the addon-boundary metadata, and the changed
Python files compiling. Ariel/Scott: keep or drop this file as you see fit.
"""
import json
import py_compile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def registry():
    from server.capability_registry import registry as reg

    return reg


def test_registry_builds_at_68_capabilities(registry):
    keys = registry.keys()
    assert len(keys) == 68, f"expected 68 capabilities, got {len(keys)}"
    assert "scene.health" in keys
    assert "scene.human_activity" in keys


@pytest.mark.parametrize(
    "query,expected",
    [
        # Ariel's language (taught from her files)
        ("patch lighting for the bottle", "product.lighting"),
        ("mascot rig bones", "rig.armature"),
        ("fluid spray emitter", "physics.particles"),
        ("fspy photo match camera", "product.camera"),
        ("anamorphic animation", "animation.advanced"),
        ("check scene health for missing textures", "scene.health"),
        # Pre-existing README example routes must be unchanged
        ("add a cube", "scene.create_object"),
        ("chrome", "scene.set_material"),
        ("hdri", "scene.world"),
        ("what's in the scene", "scene.info"),
    ],
)
def test_searches_route(registry, query, expected):
    rows = registry.search_capabilities(query)
    assert rows, f"no results for {query!r}"
    assert rows[0]["key"] == expected, f"{query!r} -> {rows[0]['key']}, want {expected}"
    assert rows[0]["score"] == 100.0


def test_boundary_metadata(registry):
    human = registry.resolve_tool("scene.human_activity")
    assert human.requires_gui is True
    assert human.bridge_command == "drain_human_activity"
    sculpt = registry.resolve_tool("model.sculpt")
    assert sculpt.requires_gui is True
    assert "retopoflow" in sculpt.state_setup.lower()
    camera = registry.resolve_tool("product.camera")
    assert camera.requires_addon_enabled == "keentools"
    gn = registry.resolve_tool("model.geometry_nodes")
    assert "socket NAME" in gn.state_setup


def test_workflow_guide_registered_and_discoverable():
    from server.workflow_guides import get_workflow_guide, list_workflow_guides

    hits = list_workflow_guides("patch")
    assert any(h["key"] == "ariel-workflow" for h in hits)
    guide = get_workflow_guide("ariel-workflow")
    assert "content" in guide and "TriLamp" in guide["content"]


def test_profile_json_parses_and_keeps_provenance_separate():
    profile = json.loads((ROOT / "config" / "ariel_workflow_profile.json").read_text())
    assert profile["presets"]["lighting"]["trilamp"]["ratio"] == "2:1:1"
    corpora = profile["provenance_separation"]["corpora"]
    assert set(corpora) == {"ariel-files", "artist-live", "external"}


@pytest.mark.parametrize(
    "relpath",
    [
        "blender_addon/openclaw_blender_bridge.py",
        "blender_addon/quality_handlers.py",
        "blender_addon/human_activity.py",
        "scripts/blender_inspect.py",
        "server/capability_registry.py",
        "server/capability_router.py",
        "server/workflow_guides.py",
    ],
)
def test_changed_python_files_compile(relpath):
    py_compile.compile(str(ROOT / relpath), doraise=True)
