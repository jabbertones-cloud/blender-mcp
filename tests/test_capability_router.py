from server.capability_router import recommend, plan_goal


CASES = {
    "bevel the bottle cap edges": "blender_apply_modifier",
    "smart UV unwrap the label mesh": "blender_uv_unwrap",
    "put the monitor on top of the desk": "blender_semantic_place",
    "create softbox product photography lighting": "blender_product_lighting",
    "make a procedural wood material": "blender_procedural_material",
    "cut a hole through the wall with a boolean difference": "blender_boolean_operation",
    "bake the normal texture": "blender_texture_bake",
    "make a 360 product turntable animation": "blender_product_animation",
    "build an accident reconstruction for court": "blender_forensic_scene",
    "configure cycles samples and output resolution": "blender_set_render_settings",
    "render the final image": "blender_render",
    "check whether these objects overlap": "blender_spatial",
}


def test_specific_intents_choose_specific_tools():
    failures = []
    for task, expected in CASES.items():
        result = recommend(task)
        actual = result["primary"]["tool"]
        if actual != expected:
            failures.append((task, expected, actual, result))
    assert not failures, failures


def test_unknown_mutation_does_not_guess():
    result = recommend("make this feel more premium somehow")
    assert result["decision"] == "inspect_then_plan"
    assert result["primary"]["tool"] == "blender_get_scene_info"


def test_product_specific_tools_beat_generic_overlaps():
    assert recommend("set up product photography lighting for the bottle")["primary"]["tool"] == "blender_product_lighting"
    assert recommend("set up a hero product camera angle")["primary"]["tool"] == "blender_product_camera"
    assert recommend("set up an ecommerce product render")["primary"]["tool"] == "blender_product_render_setup"


def test_plan_has_concrete_tools_and_verification():
    steps = plan_goal("make a hero product shot with softbox lighting and render the final image", max_steps=6)
    assert steps[0]["tool_hint"] == "blender_get_scene_info"
    hints = [step.get("tool_hint") for step in steps]
    assert "blender_product_lighting" in hints
    assert "blender_render" in hints
    assert hints[-1] == "blender_verify"
    assert all(step.get("tool_hint") is not None for step in steps)


def test_power_user_plan_skips_mandatory_inspection_and_verify():
    steps = plan_goal("bevel the cap", max_steps=4, profile="power-user")
    assert steps[0]["tool_hint"] == "blender_apply_modifier"
    assert all(step.get("tool_hint") != "blender_verify" for step in steps)
