from server.capability_executor import execute_workflow


class FakeBridge:
    def __init__(self, *, include_camera=True, include_light=True, pixels=True, objects=None):
        self.include_camera = include_camera
        self.include_light = include_light
        self.pixels = pixels
        self.objects = list(objects) if objects is not None else [{"name": "Bottle", "type": "MESH"}]
        self.calls = []
        self._quality_started = False

    def _scene_objects(self):
        rows = list(self.objects)
        names = {row["name"] for row in rows}
        if self.include_camera and "Camera" not in names:
            rows.append({"name": "Camera", "type": "CAMERA"})
        if self.include_light and "Key" not in names:
            rows.append({"name": "Key", "type": "LIGHT"})
        return rows

    def _diagnostics(self):
        rows = self._scene_objects()
        lights = [row for row in rows if row["type"] == "LIGHT"]
        camera = next((row for row in rows if row["type"] == "CAMERA"), None)
        return {
            "objects": rows,
            "object_count": len(rows),
            "camera_present": camera is not None,
            "camera": {"name": camera["name"], "lens_mm": 50.0, "dof_enabled": False} if camera else None,
            "light_count": len(lights),
            "lights": [{"name": row["name"], "type": "AREA", "energy": 100.0} for row in lights],
            "world": {"present": True, "name": "World", "uses_nodes": False, "environment_textures": []},
            "render": {"engine": "CYCLES", "samples": 256},
        }

    def __call__(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        if command in {"scene_diagnostics", "get_scene_info"}:
            if command == "scene_diagnostics":
                self._quality_started = True
            payload = self._diagnostics()
            if command == "get_scene_info":
                return {"objects": payload["objects"]}
            return payload
        if command == "viewport_capture":
            if self._quality_started:
                self.quality_viewports = getattr(self, "quality_viewports", 0) + 1
                if getattr(self, "fail_first_quality_pixels", False) and self.quality_viewports == 1:
                    return {"status": "ok"}
            return {"base64": "pixels" if self.pixels else ""}
        if command == "product_camera":
            self.include_camera = True
            return {"status": "ok"}
        if command == "product_lighting":
            self.include_light = True
            return {"status": "ok"}
        if command in {"product_material", "product_render_setup", "execute_python", "render"}:
            return {"status": "ok"}
        return {"status": "ok"}


def _mutate_after_quality(bridge: FakeBridge) -> list[tuple]:
    started = False
    out = []
    for command, params in bridge.calls:
        if command == "scene_diagnostics":
            started = True
            continue
        if started and command in {"product_camera", "product_lighting", "execute_python"}:
            out.append((command, params))
    return out


def test_product_hero_cannot_finish_plain_ok_when_semantic_review_is_required():
    bridge = FakeBridge()
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, bridge)
    assert out["status"] == "review_required"
    assert out["quality_review"]["pixel_evidence"] is True
    assert out["quality_review"]["objective_score"] == 100
    assert any(row["code"] == "AESTHETIC_REVIEW" for row in out["quality_review"]["findings"])
    assert out["quality_review"].get("repair_count", 0) == 0
    assert _mutate_after_quality(bridge) == []


def test_amazon_packshot_cannot_finish_plain_ok_before_semantic_review():
    out = execute_workflow("workflow.amazon_packshot", {"object_name": "Bottle"}, FakeBridge())
    assert out["status"] == "review_required"
    assert any(row["code"] == "AMAZON_SEMANTIC_REVIEW" for row in out["quality_review"]["findings"])


def test_product_workflow_setup_supplies_missing_camera_before_quality_review():
    bridge = FakeBridge(include_camera=False)
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, bridge)
    assert out["status"] == "review_required"
    assert bridge.include_camera is True
    assert "product_camera" in [name for name, _ in bridge.calls]
    assert not any(row["code"] == "NO_CAMERA" for row in out["quality_review"]["findings"])
    assert out["quality_review"].get("repair_count", 0) == 0


def test_product_workflow_setup_supplies_missing_lights_before_quality_review():
    bridge = FakeBridge(include_light=False)
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, bridge)
    assert out["status"] == "review_required"
    assert bridge.include_light is True
    assert "product_lighting" in [name for name, _ in bridge.calls]
    assert not any(row["code"] == "NO_LIGHTS" for row in out["quality_review"]["findings"])
    assert out["quality_review"].get("repair_count", 0) == 0


def test_missing_target_fails_closed_without_stage_repair():
    bridge = FakeBridge(objects=[{"name": "Other", "type": "MESH"}])
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, bridge)
    assert out["status"] == "fail"
    assert any(row["code"] == "TARGET_MISSING" for row in out["quality_review"]["findings"])
    assert _mutate_after_quality(bridge) == []
    assert not any(attempt.get("capability") in {"product.camera", "product.lighting"} for attempt in out["quality_review"].get("repair_attempts") or [])


def test_turntable_is_also_quality_gated():
    out = execute_workflow("workflow.turntable", {"object_name": "Bottle"}, FakeBridge())
    assert out["status"] == "review_required"
    assert out["quality_review"]["objective_score"] == 100


def test_missing_quality_pixels_are_recaptured():
    bridge = FakeBridge()
    bridge.fail_first_quality_pixels = True
    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, bridge)
    assert out["status"] == "review_required"
    assert out["quality_review"]["pixel_evidence"] is True
    assert any(attempt.get("finding_code") == "NO_PIXELS" for attempt in out["quality_review"]["repair_attempts"])


def test_unknown_diagnostics_falls_back_to_scene_info():
    class LegacyBridge(FakeBridge):
        def __call__(self, command, params=None):
            if command == "scene_diagnostics":
                self.calls.append((command, params or {}))
                return {"error": "Unknown command: scene_diagnostics"}
            return super().__call__(command, params)

    out = execute_workflow("workflow.product_hero", {"object_name": "Bottle"}, LegacyBridge())
    assert out["status"] == "review_required"
    assert out["quality_review"]["pixel_evidence"] is True
