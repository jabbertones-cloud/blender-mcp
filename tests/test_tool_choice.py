from server.capability_registry import registry, CapabilityNotFound


CASES = [
    ("add a cube", "create"),
    ("three point lights", "lighting"),
    ("make it look like chrome", "material"),
    ("render a png", "render"),
    ("what's in the scene", "inspect"),
    ("move the camera", "camera"),
    ("delete the default cube", "mutate"),
    ("hdri background", "world"),
]


def test_intent_family_floor():
    failures = []
    for intent, family in CASES:
        cap = registry.route_intent(intent)
        if cap.family != family:
            failures.append((intent, family, cap.key, cap.family))
    assert not failures, failures


def test_resolve_accepts_canonical_mcp_and_bridge_names():
    canonical = registry.resolve_tool("scene.create_object")
    assert canonical.key == "scene.create_object"
    assert registry.resolve_tool("blender_create_object").key == canonical.key
    assert registry.resolve_tool("create_object").key == canonical.key


def test_unknown_tool_is_distinct_error():
    try:
        registry.resolve_tool("blender_make_it_better")
    except CapabilityNotFound as exc:
        assert "Re-search capabilities" in str(exc)
    else:
        raise AssertionError("unknown capability must fail before Blender dispatch")


def test_search_returns_canonical_keys_only():
    rows = registry.search_capabilities("make chrome material", limit=5)
    assert rows[0]["key"] == "scene.set_material"
    assert all(not row["key"].startswith("blender_") for row in rows)
