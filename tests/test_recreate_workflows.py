from server.capability_executor import execute_workflow
from server.free_stack import hdri_search_terms, polyhaven_search_terms, source_order
from server.motion_qa import score_motion_qa
from server.workflow_rank import workflow_match


class RecreateBridge:
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
        if command == "render":
            return {"status": "ok", "output_path": params.get("output_path") or "/tmp/openclaw_ref_score.png"}
        if command == "set_keyframe":
            return {"status": "ok", "frame": params.get("frame")}
        if command == "import_file":
            self.objects.append({"name": "Character", "type": "ARMATURE"})
            return {"imported": params.get("filepath"), "new_objects": ["Character"]}
        if command == "polyhaven":
            if params.get("action") == "search":
                if params.get("asset_type") == "models":
                    return {"results": [{"id": "antique_chest", "name": "Chest"}]}
                return {"results": [{"id": "studio_small_03", "name": "Studio"}]}
            if params.get("action") == "import_model":
                self.objects.append({"name": "GenAsset", "type": "MESH"})
                return {"imported": True, "asset_id": params.get("asset_id")}
            return {"applied": True, "asset_id": params.get("asset_id")}
        if command == "execute_python":
            code = str(params.get("code", ""))
            if "ARMATURE_AUTO" in code:
                self.objects.append({"name": "AutoArmature", "type": "ARMATURE"})
                return {"status": "ok", "armature": "AutoArmature"}
            if "detect_features" in code:
                return {
                    "status": "ok",
                    "loaded": True,
                    "clip": "plate",
                    "is_valid": True,
                    "average_error": 0.4,
                    "tracks": 12,
                }
            return {"status": "ok"}
        return {"status": "ok", "command": command}


def test_workflow_match_returns():
    assert workflow_match("amazon listing image")[0]["key"] == "workflow.amazon_packshot"
    assert workflow_match("360 product turntable")[0]["key"] == "workflow.turntable"
    assert workflow_match("unrelated cube") == []
    assert workflow_match("character from image mixamo")[0]["key"] == "workflow.character_from_image"
    assert workflow_match("image to 3d reconstruct from image")[0]["key"] == "workflow.image_to_asset"


def test_reconstruct_subject_maps_to_catalog_terms():
    terms = polyhaven_search_terms("reconstruct subject")
    assert "reconstruct" not in terms
    assert terms[0] == "bottle"
    assert hdri_search_terms("reconstruct subject")[0] == "studio"
    joined = " ".join(source_order()).lower()
    assert "tripo" not in joined
    assert "hunyuan" not in joined


def test_local_filepath_import_is_preferred():
    result = execute_workflow(
        "workflow.image_to_asset",
        {"filepath": "/tmp/hero.glb"},
        RecreateBridge(),
    )
    assert result["status"] == "ok"
    assert result["free_source"] == "local_filepath"
    assert result["object_name"] == "Character"
    result = execute_workflow(
        "workflow.image_to_asset",
        {"image_url": "https://example.com/ref.png", "prompt": "reconstruct subject"},
        RecreateBridge(),
    )
    assert result["status"] == "ok"
    assert result["object_name"] == "GenAsset"
    assert result["free_source"] == "polyhaven_cc0_models"
    assert result["search_term"] == "bottle"


def test_image_to_asset_fails_closed_without_new_object():
    class NoImport(RecreateBridge):
        def __call__(self, command, params=None):
            params = params or {}
            self.calls.append((command, params))
            if command == "viewport_capture":
                return {"status": "ok", "image": "base64-test"}
            if command == "get_scene_info":
                return {"status": "ok", "objects": list(self.objects)}
            if command == "polyhaven":
                if params.get("action") == "search":
                    return {"results": [{"id": "ghost", "name": "Ghost"}]}
                return {"imported": True}
            return {"status": "ok"}

    result = execute_workflow("workflow.image_to_asset", {"image_url": "https://example.com/ref.png"}, NoImport())
    assert result["status"] == "postcondition_failed"


def test_character_auto_weights():
    bridge = RecreateBridge()
    result = execute_workflow("workflow.character_from_image", {"image_url": "https://example.com/p.png"}, bridge)
    assert result["status"] == "ok"
    assert result["source"] == "polyhaven_cc0_models"
    assert any(
        "ARMATURE_AUTO" in str(params.get("code", ""))
        for name, params in bridge.calls
        if name == "execute_python"
    )


def test_libmv_and_motion_spec():
    libmv = execute_workflow("workflow.motion_from_video", {"path": "/tmp/plate.mp4"}, RecreateBridge())
    assert libmv["status"] == "ok"
    assert libmv["libmv"]["tracks"] == 12
    spec = execute_workflow(
        "workflow.motion_from_video",
        {"object_name": "Bottle", "motion_spec": {"keyframes": [{"frame": 1, "location": [0, 0, 1]}]}},
        RecreateBridge(),
    )
    assert spec["keyframes"][0]["frame"] == 1


def test_lighting_and_multiview_and_scene():
    light = execute_workflow("workflow.match_reference_lighting", {"keyword": "studio"}, RecreateBridge())
    assert light["status"] == "ok"
    assert light["asset_id"] == "studio_small_03"
    views = execute_workflow("workflow.viewport_multiview", {}, RecreateBridge())
    assert len(views["captures"]) == 4
    scene = execute_workflow("workflow.image_to_scene", {"image_url": "https://example.com/ref.png"}, RecreateBridge())
    assert scene["status"] == "ok"
    assert scene["free_source"] == "polyhaven_cc0_models"


def test_reference_score_blocked_and_injected(monkeypatch):
    from server import reference_loop

    reference_loop.reset()
    blocked = execute_workflow("workflow.reference_score", {}, RecreateBridge())
    assert blocked["blocking_reason"] == "camera_unsolved"
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
            "psnr": 40,
        },
    )
    scored = execute_workflow(
        "workflow.reference_score",
        {"output_path": "/tmp/openclaw_ref_score.png"},
        RecreateBridge(),
    )
    assert scored["verdict"] is True
    seq = execute_workflow(
        "workflow.reference_score_sequence",
        {"frames": ["/tmp/f1.png", "/tmp/f2.png"]},
        RecreateBridge(),
    )
    assert seq["sampled"] == 2
    assert seq["passed"] is True


def test_auto_score_after_asset_when_still_attached(monkeypatch):
    from server import reference_loop

    reference_loop.reset()
    reference_loop.attach({"path": "/tmp/ref.png", "role": "front"})
    monkeypatch.setattr(
        reference_loop,
        "score_render",
        lambda *a, **k: {
            "passed": False,
            "psnr": 10,
            "psnr_passed": False,
            "ssim_passed": True,
            "lpips_passed": True,
        },
    )
    result = execute_workflow("workflow.image_to_asset", {"prompt": "bottle"}, RecreateBridge())
    assert result["status"] == "ok"
    assert result["reference_score"]["verdict"] is False


def test_motion_qa_detects_skate():
    ok = score_motion_qa(
        [
            {"frame": 1, "bone": "foot", "location": [0, 0, 0], "contact": True},
            {"frame": 2, "bone": "foot", "location": [0.001, 0, 0], "contact": True},
        ]
    )
    assert ok["passed"] is True
    bad = score_motion_qa(
        [
            {"frame": 1, "bone": "foot", "location": [0, 0, 0], "contact": True},
            {"frame": 2, "bone": "foot", "location": [0.5, 0, 0], "contact": True},
        ]
    )
    assert bad["passed"] is False
    result = execute_workflow(
        "workflow.motion_qa",
        {
            "samples": [
                {"frame": 1, "bone": "foot", "location": [0, 0, 0], "contact": True},
                {"frame": 2, "bone": "foot", "location": [0.5, 0, 0], "contact": True},
            ]
        },
        RecreateBridge(),
    )
    assert result["status"] == "failed"


def test_executor_has_no_paid_generation():
    from pathlib import Path

    src = Path("server/capability_executor.py").read_text()
    assert "tripo_client" not in src
    assert "generation.hunyuan3d" not in src
    assert "TRIPO_API_KEY" not in src


def test_correct_maps_metrics():
    from server.reference_loop import correct

    assert correct({"delta_e_passed": False, "delta_e": 9})["next_key"] == "product.material"
    assert correct({"ssim_passed": False})["next_key"] == "product.camera"
    assert correct({"psnr_passed": False})["next_key"] == "product.render_setup"
