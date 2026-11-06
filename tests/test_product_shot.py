"""Tests for blender_product_shot — the outcome-shaped packshot tool.

No real Blender here: the bridge is a fake that speaks the same
unwrapped-result contract as the server's send_command(). These tests
prove the procedure, the verdict logic, and the failure log. The live
proof (a real render on a Blender host) is tracked in the PR.
"""
import asyncio
import base64
import json

import pytest
from pydantic import ValidationError

from server.image_similarity import encode_png_gray
from server.product_shot import (
    ProductShotInput,
    default_failure_log_path,
    execute_product_shot,
    register_product_shot_tools,
)


# ─── Fake bridge ────────────────────────────────────────────────────────────

BOTTLE = {"name": "Bottle", "type": "MESH"}
CAMERA = {"name": "OldCam", "type": "CAMERA"}


class FakeBridge:
    """Mimics send_command(): already-unwrapped bridge results."""

    def __init__(self, objects=None, *, ping_error=None, audit_failed=(),
                 audit_warnings=(), step_errors=None, capture_b64=None):
        self.objects = list(objects if objects is not None else [BOTTLE])
        self.ping_error = ping_error
        self.audit_failed = set(audit_failed)
        self.audit_warnings = set(audit_warnings)
        self.step_errors = step_errors or {}  # step marker -> error string
        self.capture_b64 = capture_b64
        self.calls = []

    def commands(self):
        return [c for c, _ in self.calls]

    def __call__(self, command, params=None):
        params = params or {}
        self.calls.append((command, params))
        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            return {"error": f"fake bridge: unhandled command {command}"}
        return handler(params)

    def _cmd_ping(self, _params):
        if self.ping_error:
            return {"error": self.ping_error}
        return {"blender_version": "4.2.0", "file": "test.blend", "objects": len(self.objects)}

    def _cmd_get_scene_info(self, _params):
        return {"scene_name": "Scene", "objects": list(self.objects)}

    def _cmd_import_file(self, params):
        name = "ImportedMesh"
        self.objects.append({"name": name, "type": "MESH"})
        return {"imported": [name], "filepath": params.get("filepath")}

    _STEP_MARKERS = (
        ("material", "Principled BSDF"),
        ("lighting", "Key_Light"),
        ("camera", "ProductCamData"),
        ("render_settings", "adaptive_threshold"),
        ("compositor", "CompositorNodeRLayers"),
    )

    def _cmd_execute_python(self, params):
        code = params.get("code", "")
        for step, marker in self._STEP_MARKERS:
            if marker in code:
                if step in self.step_errors:
                    return {"error": self.step_errors[step]}
                return {"status": "ok", "step": step}
        return {"status": "ok", "step": "unknown"}

    def _cmd_render(self, params):
        return {
            "rendered": "image",
            "output_path": params.get("output_path"),
            "resolution": "1920x1080",
            "engine": "CYCLES",
        }

    def _cmd_render_quality_audit(self, _params):
        checks = [{"id": "engine_cycles", "status": "pass"},
                  {"id": "samples_minimum", "status": "pass"}]
        for cid in self.audit_failed:
            checks.append({"id": cid, "status": "fail"})
        for cid in self.audit_warnings:
            checks.append({"id": cid, "status": "warn"})
        failed = len(self.audit_failed)
        return {
            "summary": {"profile": "cinema", "strict": False,
                        "score": 100 - 25 * failed, "passed": 2,
                        "warnings": len(self.audit_warnings), "failed": failed},
            "checks": checks,
            "snapshot": {"engine": "CYCLES"},
        }

    def _cmd_viewport_capture(self, _params):
        if self.capture_b64 is None:
            return {"filepath": "/remote/viewport.png", "mode": "full_render"}
        return {"filepath": "/remote/viewport.png", "mode": "full_render",
                "base64": self.capture_b64}


def _flat_png(value, size=8):
    return encode_png_gray(size, size, [value] * (size * size))


# ─── Brief validation ───────────────────────────────────────────────────────

def test_brief_needs_subject_or_asset():
    with pytest.raises(ValidationError):
        ProductShotInput()
    ProductShotInput(subject="Bottle")
    ProductShotInput(asset_path="/models/bottle.glb")


def test_brief_defaults_are_packshot_sane():
    brief = ProductShotInput(subject="Bottle")
    assert brief.lighting_preset.value == "product_studio"
    assert brief.viewpoint.value == "three_quarter"
    assert brief.background.value == "transparent"
    assert brief.min_psnr_db == 30.0 and brief.min_ssim == 0.90


# ─── Happy paths ────────────────────────────────────────────────────────────

def test_pass_without_golden_states_its_basis(tmp_path):
    log = tmp_path / "failures.jsonl"
    bridge = FakeBridge()
    verdict = execute_product_shot(
        bridge,
        ProductShotInput(subject="Bottle", output_path=str(tmp_path / "shot.png")),
        failure_log_path=str(log))
    assert verdict["verdict"] == "pass"
    assert verdict["similarity"] is None
    assert any("no golden supplied" in b for b in verdict["basis"])
    assert not log.exists()  # passes are not failure-logged
    # The whole procedure ran, in order (4 snippet steps: lighting,
    # camera, render settings, compositor — no material without a preset).
    seq = [c for c in bridge.commands() if c != "get_scene_info"]
    assert seq == ["ping", "execute_python", "execute_python", "execute_python",
                   "execute_python", "render", "render_quality_audit",
                   "viewport_capture"]


def test_pass_with_identical_golden(tmp_path):
    render_file = tmp_path / "shot.png"
    render_file.write_bytes(_flat_png(0.42))
    golden = tmp_path / "golden.png"
    golden.write_bytes(_flat_png(0.42))
    bridge = FakeBridge()
    verdict = execute_product_shot(
        bridge,
        ProductShotInput(subject="Bottle", output_path=str(render_file),
                         golden_image=str(golden)),
        failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "pass"
    assert verdict["similarity"]["ssim"] == pytest.approx(1.0)
    assert verdict["similarity"]["identical_to_golden"] is True
    assert verdict["evidence"]["pixels_source"] == "render_file"


def test_pass_via_viewport_capture_when_render_is_remote(tmp_path):
    golden = tmp_path / "golden.png"
    golden.write_bytes(_flat_png(0.42))
    capture = base64.b64encode(_flat_png(0.42)).decode("ascii")
    bridge = FakeBridge(capture_b64=capture)
    verdict = execute_product_shot(
        bridge,
        ProductShotInput(subject="Bottle",
                         output_path="/blender-host-only/shot.png",
                         golden_image=str(golden)),
        failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "pass"
    assert verdict["evidence"]["pixels_source"] == "viewport_capture"


def test_asset_import_resolves_subject(tmp_path):
    bridge = FakeBridge(objects=[])
    verdict = execute_product_shot(
        bridge, ProductShotInput(asset_path="/models/widget.glb"),
        failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "pass"
    assert verdict["subject"] == "ImportedMesh"
    assert bridge.commands().index("import_file") < bridge.commands().index("get_scene_info")


# ─── Failure paths: verdict + what's off + failure log ─────────────────────

def _read_log(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_golden_mismatch_fails_and_logs(tmp_path):
    render_file = tmp_path / "shot.png"
    render_file.write_bytes(_flat_png(1.0))       # blown white
    golden = tmp_path / "golden.png"
    golden.write_bytes(_flat_png(0.0))            # approved shot is black
    log = tmp_path / "failures.jsonl"
    verdict = execute_product_shot(
        FakeBridge(),
        ProductShotInput(subject="Bottle", output_path=str(render_file),
                         golden_image=str(golden)),
        failure_log_path=str(log))
    assert verdict["verdict"] == "fail"
    assert any("PSNR" in w and "SSIM" in w for w in verdict["whats_off"])
    assert verdict["failure_logged"] is True
    (record,) = _read_log(log)
    assert record["spec"]["subject"] == "Bottle"
    assert record["similarity"]["ssim"] < 0.90
    assert record["render"]["path"] == str(render_file)
    assert record["timestamp"]


def test_missing_subject_fails_fast_and_logs(tmp_path):
    log = tmp_path / "failures.jsonl"
    bridge = FakeBridge(objects=[CAMERA])
    verdict = execute_product_shot(bridge, ProductShotInput(subject="Bottle"),
                                   failure_log_path=str(log))
    assert verdict["verdict"] == "fail"
    assert "not in the scene" in verdict["whats_off"][0]
    assert "render" not in bridge.commands()  # never got that far
    assert len(_read_log(log)) == 1


def test_bridge_down_fails_and_logs(tmp_path):
    log = tmp_path / "failures.jsonl"
    bridge = FakeBridge(ping_error="Cannot connect to Blender")
    verdict = execute_product_shot(bridge, ProductShotInput(subject="Bottle"),
                                   failure_log_path=str(log))
    assert verdict["verdict"] == "fail"
    assert bridge.commands() == ["ping"]
    assert len(_read_log(log)) == 1


def test_raising_bridge_still_gets_a_verdict(tmp_path):
    def exploding_bridge(command, _params=None):
        raise ConnectionError("socket went away")

    verdict = execute_product_shot(exploding_bridge, ProductShotInput(subject="Bottle"),
                                   failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "fail"
    assert "ConnectionError" in verdict["whats_off"][0]


def test_audit_failures_fail_the_verdict(tmp_path):
    bridge = FakeBridge(audit_failed={"samples_minimum"})
    verdict = execute_product_shot(bridge, ProductShotInput(subject="Bottle"),
                                   failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "fail"
    assert "render" in bridge.commands()  # the render happened; the gate caught it
    assert "samples_minimum" in verdict["whats_off"][-1]
    assert verdict["audit"]["failed"] == 1


def test_audit_warnings_advisory_only(tmp_path):
    bridge = FakeBridge(audit_warnings={"color_management"})
    verdict = execute_product_shot(bridge, ProductShotInput(subject="Bottle"),
                                   failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "pass"
    assert any("advisory" in w for w in verdict["whats_off"])


def test_step_error_stops_procedure(tmp_path):
    bridge = FakeBridge(step_errors={"material": "shader blew up"})
    verdict = execute_product_shot(
        bridge,
        ProductShotInput(subject="Bottle", material_preset="clear_glass"),
        failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "fail"
    assert "material step failed" in verdict["whats_off"][0]
    assert "render" not in bridge.commands()


def test_unreadable_golden_fails_closed(tmp_path):
    render_file = tmp_path / "shot.png"
    render_file.write_bytes(_flat_png(0.5))
    verdict = execute_product_shot(
        FakeBridge(),
        ProductShotInput(subject="Bottle", output_path=str(render_file),
                         golden_image=str(tmp_path / "nope.png")),
        failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "fail"
    assert "golden image unreadable" in verdict["whats_off"][-1]


def test_no_pixels_anywhere_fails_closed(tmp_path):
    golden = tmp_path / "golden.png"
    golden.write_bytes(_flat_png(0.5))
    verdict = execute_product_shot(
        FakeBridge(capture_b64=None),  # remote render, capture returns nothing
        ProductShotInput(subject="Bottle", output_path="/remote/shot.png",
                         golden_image=str(golden)),
        failure_log_path=str(tmp_path / "f.jsonl"))
    assert verdict["verdict"] == "fail"
    assert "no render pixels" in verdict["whats_off"][-1]


# ─── Registration + failure-log path ────────────────────────────────────────

class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, *, name, annotations=None):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


def test_registration_and_tool_roundtrip(tmp_path):
    mcp = _FakeMCP()
    bridge = FakeBridge()
    names = register_product_shot_tools(mcp, bridge, lambda d: json.dumps(d))
    assert names == ["blender_product_shot"]
    out = asyncio.run(mcp.tools["blender_product_shot"](ProductShotInput(subject="Bottle")))
    payload = json.loads(out)
    assert payload["verdict"] == "pass"
    assert payload["tool"] == "blender_product_shot"


def test_failure_log_path_env_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.jsonl"
    monkeypatch.setenv("BLENDER_PRODUCT_SHOT_FAILURE_LOG", str(target))
    assert default_failure_log_path() == str(target)
    monkeypatch.delenv("BLENDER_PRODUCT_SHOT_FAILURE_LOG")
    assert default_failure_log_path().endswith("data/product_shot_failures.jsonl")
