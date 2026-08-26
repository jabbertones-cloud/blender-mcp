from server.capability_executor import execute_canonical, execute_workflow


class FakeBridge:
    def __init__(self):
        self.calls = []
        self.objects = [{"name": "Bottle", "type": "MESH"}]

    def __call__(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command == "viewport_capture":
            return {"status": "ok", "image": "base64-test"}
        if command == "get_scene_info":
            return {"status": "ok", "objects": list(self.objects)}
        if command == "create_object":
            name = params.get("name") or "Cube"
            self.objects.append({"name": name, "type": "MESH"})
            return {"status": "ok", "name": name}
        if command == "delete_object":
            names = set(params.get("names") or [])
            self.objects = [row for row in self.objects if row["name"] not in names]
            return {"status": "ok"}
        if command == "forensic_scene":
            return {"status": "ok", "action": params.get("action")}
        if command == "hunyuan3d":
            self.objects.append({"name": "GenAsset", "type": "MESH"})
            return {"imported": True, "object_name": "GenAsset", "filepath": "/tmp/x.glb"}
        if command == "render":
            return {"status": "ok", "output_path": params.get("output_path") or "/tmp/openclaw_ref_score.png"}
        if command == "set_keyframe":
            return {"status": "ok", "frame": params.get("frame")}
        if command == "import_file":
            self.objects.append({"name": "Character", "type": "ARMATURE"})
            return {"imported": params.get("filepath"), "new_objects": ["Character"]}
        if command == "polyhaven":
            if params.get("action") == "search":
                return {"results": [{"id": "studio_small_03", "name": "Studio"}]}
            return {"applied": True, "asset_id": params.get("asset_id")}
        if command == "execute_python" and "detect_features" in str(params.get("code", "")):
            return {
                "status": "ok",
                "loaded": True,
                "clip": "plate",
                "is_valid": True,
                "average_error": 0.4,
                "tracks": 12,
            }
        return {"status": "ok", "command": command}


def test_visual_atomic_capability_always_observes_after_mutation():
    bridge = FakeBridge()
    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0, "roughness": 0.1},
        bridge,
    )
    commands = [name for name, _ in bridge.calls]
    assert commands[0] == "get_scene_info"
    assert commands[-2:] == ["set_material", "viewport_capture"] or (
        "set_material" in commands and commands[-1] == "viewport_capture"
    )
    assert result["visual_check_required"] is True
    assert result["status"] == "ok"
    assert "scene_delta" in result


def test_product_lighting_uses_wrapper_not_fake_bridge_command():
    bridge = FakeBridge()
    result = execute_canonical("product.lighting", {"preset": "cosmetics"}, bridge)
    commands = [name for name, _ in bridge.calls]
    assert "execute_python" in commands
    assert "product_lighting" not in commands
    assert commands[-1] == "viewport_capture"
    assert result["status"] == "ok"


def test_product_hero_is_one_workflow_with_required_observations():
    bridge = FakeBridge()
    result = execute_workflow(
        "workflow.product_hero",
        {
            "object_name": "Bottle",
            "material": "clear_glass",
            "lighting": "cosmetics",
            "camera_style": "hero_reveal",
            "quality": "premium",
            "resolution": "square_1080",
            "auto_render": True,
        },
        bridge,
    )
    commands = [name for name, _ in bridge.calls]
    assert result["status"] == "ok"
    assert commands[0] == "get_scene_info"
    assert commands.count("viewport_capture") >= 5
    assert "product_lighting" not in commands
    assert "product_camera" not in commands
    assert "product_render_setup" not in commands
    assert "render" in commands
    assert commands[-1] == "viewport_capture"


def test_product_hero_rejects_object_name_code_injection():
    bridge = FakeBridge()
    try:
        execute_workflow("workflow.product_hero", {"object_name": 'Bottle\"); import os; #'}, bridge)
    except ValueError as exc:
        assert "unsupported characters" in str(exc)
    else:
        raise AssertionError("unsafe object name was accepted")
    assert bridge.calls == []


def test_create_object_fails_closed_without_scene_delta():
    class NoDeltaBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "get_scene_info":
                return {"status": "ok", "objects": [{"name": "Bottle", "type": "MESH"}]}
            if command == "create_object":
                return {"status": "ok", "name": "Ghost"}
            return {"status": "ok"}

    result = execute_canonical("scene.create_object", {"type": "cube", "name": "Ghost"}, NoDeltaBridge())
    assert result["status"] == "postcondition_failed"


def test_turntable_workflow_uses_turntable_camera_style():
    bridge = FakeBridge()
    result = execute_workflow("workflow.turntable", {"object_name": "Bottle", "auto_render": False}, bridge)
    assert result["status"] == "ok"
    camera_calls = [params for command, params in bridge.calls if command == "execute_python"]
    assert camera_calls, bridge.calls
    assert any("turntable" in str(params.get("code", "")).lower() or "Turntable" in str(params.get("code", "")) for params in camera_calls)


def test_missing_viewport_pixels_fail_visual_postcondition():
    class BlindBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "viewport_capture":
                return {"status": "ok"}
            if command == "get_scene_info":
                return {"status": "ok", "objects": list(self.objects)}
            return {"status": "ok"}

    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0},
        BlindBridge(),
    )
    assert result["status"] == "postcondition_failed"
    assert result["error"] == "appearance-affecting step returned no pixel evidence"


def test_path_only_viewport_fails_visual_postcondition():
    class PathOnlyBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "viewport_capture":
                return {"status": "ok", "path": "/tmp/viewport.png", "filepath": "/tmp/viewport.png"}
            if command == "get_scene_info":
                return {"status": "ok", "objects": list(self.objects)}
            return {"status": "ok"}

    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0},
        PathOnlyBridge(),
    )
    assert result["status"] == "postcondition_failed"
    assert result["error"] == "appearance-affecting step returned no pixel evidence"


def test_path_only_viewport_capture_is_not_visual_evidence():
    class PathOnlyBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "viewport_capture":
                return {"status": "ok", "path": "/tmp/viewport.png", "filepath": "/tmp/viewport.png"}
            if command == "get_scene_info":
                return {"status": "ok", "objects": list(self.objects)}
            return {"status": "ok"}

    result = execute_canonical(
        "scene.set_material",
        {"object_name": "Bottle", "metallic": 1.0},
        PathOnlyBridge(),
    )
    assert result["status"] == "postcondition_failed"
    assert result["error"] == "appearance-affecting step returned no pixel evidence"


def test_amazon_packshot_forces_square_premium_setup():
    bridge = FakeBridge()
    result = execute_workflow("workflow.amazon_packshot", {"object_name": "Bottle"}, bridge)
    assert result["status"] == "ok"
    assert result["workflow"] == "workflow.amazon_packshot"
    assert "render" in [name for name, _ in bridge.calls]


def test_forensic_workflow_hits_forensic_bridge_command():
    bridge = FakeBridge()
    result = execute_workflow("workflow.forensic_recon", {"action": "build_road"}, bridge)
    assert result["status"] == "ok"
    assert ("forensic_scene", {"action": "build_road"}) in bridge.calls


def test_image_to_asset_imports_hunyuan_and_observes():
    bridge = FakeBridge()
    result = execute_workflow(
        "workflow.image_to_asset",
        {"image_url": "https://example.com/ref.png", "prompt": "reconstruct subject"},
        bridge,
    )
    assert result["status"] == "ok"
    assert result["object_name"] == "GenAsset"
    assert any(name == "hunyuan3d" for name, _ in bridge.calls)
    hunyuan_params = [params for name, params in bridge.calls if name == "hunyuan3d"][0]
    assert hunyuan_params["mode"] == "image_to_3d"
    assert hunyuan_params["prompt"] == "reconstruct subject"
    assert bridge.calls[-1][0] == "viewport_capture"


def test_image_to_asset_fails_closed_without_new_object():
    class NoImportBridge(FakeBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "viewport_capture":
                return {"status": "ok", "image": "base64-test"}
            if command == "get_scene_info":
                return {"status": "ok", "objects": list(self.objects)}
            if command == "hunyuan3d":
                return {"imported": True, "object_name": "Ghost"}
            return {"status": "ok"}

    result = execute_workflow("workflow.image_to_asset", {"image_url": "https://example.com/ref.png"}, NoImportBridge())
    assert result["status"] == "postcondition_failed"


def test_character_from_image_without_key_is_blocked(monkeypatch):
    from server.tripo_client import set_transport

    set_transport(None)
    monkeypatch.delenv("TRIPO_API_KEY", raising=False)
    result = execute_workflow("workflow.character_from_image", {"image_url": "https://example.com/p.png"}, FakeBridge())
    assert result["status"] == "blocked"
    assert result["blocking_reason"] == "tripo_api_key_missing"


class _FakeTripo:
    def post(self, path, body):
        if "image-to-model" in path:
            return {"code": 0, "data": {"task_id": "t_model", "status": "success"}}
        if "rig-check" in path:
            return {"code": 0, "data": {"task_id": "t_check", "status": "success", "riggable": True, "rig_type": "biped"}}
        if path.endswith("/animations/rig") or "/animations/rig" in path and "check" not in path:
            return {"code": 0, "data": {"task_id": "t_rig", "status": "success"}}
        if "retarget" in path:
            return {
                "code": 0,
                "data": {
                    "task_id": "t_anim",
                    "status": "success",
                    "output": {"model_url": "https://cdn.tripo3d.ai/output/rigged.glb"},
                },
            }
        raise AssertionError(path)

    def get(self, path):
        return {"code": 0, "data": {"status": "success", "task_id": "x"}}

    def download(self, url, dest):
        with open(dest, "wb") as handle:
            handle.write(b"glb")
        return dest


def test_character_from_image_imports_tripo_glb(monkeypatch):
    from server import tripo_client

    tripo_client.set_transport(_FakeTripo())
    monkeypatch.setattr(tripo_client, "run_character_pipeline", lambda url, dest_dir=None: {
        "filepath": "/tmp/char.glb",
        "model_task_id": "t_model",
        "rig_task_id": "t_rig",
        "anim_task_id": "t_anim",
        "rig_type": "biped",
    })
    result = execute_workflow("workflow.character_from_image", {"image_url": "https://example.com/p.png"}, FakeBridge())
    tripo_client.set_transport(None)
    assert result["status"] == "ok"
    assert result["object_name"] == "Character"
    assert result["tripo"]["rig_type"] == "biped"


def test_motion_from_video_runs_libmv_python():
    result = execute_workflow("workflow.motion_from_video", {"path": "/tmp/plate.mp4"}, FakeBridge())
    assert result["status"] == "ok"
    assert result["libmv"]["tracks"] == 12


def test_camera_solve_video_uses_libmv():
    from server import reference_loop

    reference_loop.reset()
    reference_loop.attach({"role": "motion_plate", "path": "/tmp/plate.mp4"})
    result = execute_workflow("workflow.reference_camera_solve", {}, FakeBridge())
    assert result["status"] == "ok"
    assert result["libmv"]["is_valid"] is True


def test_motion_spec_applies_keyframes():
    result = execute_workflow(
        "workflow.motion_from_video",
        {
            "object_name": "Bottle",
            "motion_spec": {"keyframes": [{"frame": 1, "location": [0, 0, 1]}]},
        },
        FakeBridge(),
    )
    assert result["status"] == "ok"
    assert result["keyframes"][0]["frame"] == 1


def test_match_reference_lighting_observes():
    result = execute_workflow("workflow.match_reference_lighting", {"preset": "product_studio"}, FakeBridge())
    assert result["status"] == "ok"
    assert result["steps"][-1]["visual_check_required"] is True


def test_match_reference_lighting_searches_polyhaven():
    result = execute_workflow("workflow.match_reference_lighting", {"keyword": "studio"}, FakeBridge())
    assert result["status"] == "ok"
    assert result["asset_id"] == "studio_small_03"


def test_viewport_multiview_captures_four_views():
    result = execute_workflow("workflow.viewport_multiview", {}, FakeBridge())
    assert result["status"] == "ok"
    assert len(result["captures"]) == 4


def test_reference_score_blocked_without_camera(monkeypatch):
    from server import reference_loop

    reference_loop.reset()
    result = execute_workflow("workflow.reference_score", {}, FakeBridge())
    assert result["status"] == "blocked"
    assert result["blocking_reason"] == "camera_unsolved"


def test_reference_score_uses_injected_metrics(monkeypatch):
    from server import reference_loop

    reference_loop.reset()
    reference_loop.attach({"path": "/tmp/ref.png", "role": "front"})
    monkeypatch.setattr(
        reference_loop,
        "score_render",
        lambda *a, **k: {
            "passed": True,
            "psnr_passed": True,
            "ssim_passed": True,
            "delta_e_passed": True,
            "lpips_passed": True,
        },
    )
    result = execute_workflow("workflow.reference_score", {"output_path": "/tmp/openclaw_ref_score.png"}, FakeBridge())
    assert result["status"] == "ok"
    assert result["verdict"] is True
    assert result["metrics"]["passed"] is True


def test_image_to_scene_adds_lighting_and_camera():
    bridge = FakeBridge()
    result = execute_workflow("workflow.image_to_scene", {"image_url": "https://example.com/ref.png"}, bridge)
    assert result["status"] == "ok"
    assert "execute_python" in [name for name, _ in bridge.calls]
    assert any("hunyuan3d" == name for name, _ in bridge.calls)

