"""blender_product_shot — the outcome-shaped replacement for the product_* tools.

Outcome contract (the fleet's outcome-contracts standard; local contract
statement in guides/product-shot.md):
  Outcome:  "The packshot render of this subject matches this brief."
  Spec:     ProductShotInput (subject, presets, framing, background,
            output, optional golden image + thresholds).
  Test:     the render is produced, the repo's render_quality_audit has
            no failed checks, and — when a golden image is supplied —
            PSNR/SSIM vs the golden clear the brief's thresholds.
  Metric:   first-try brief-match rate (from the failure log + caller
            aggregation of verdicts).
  Evidence: render path + audit summary + similarity metrics are
            returned with every verdict. The tool never returns a bare
            "success": it returns a verdict and what is off.

This tool deliberately reuses the preset machinery the six product_*
tools built (materials, lighting rigs, quality/resolution maps and the
bpy code generators in product_animation_tools.py) — the presets were
never the problem. What it adds is the missing half: one call that runs
the whole procedure (material → lighting → camera → render settings →
compositor → render), then verifies the result and says so.

Failures are data: every failed verdict is appended as one JSON line
to the failure log (default: <repo>/data/product_shot_failures.jsonl,
override with env BLENDER_PRODUCT_SHOT_FAILURE_LOG).
"""
from __future__ import annotations

import base64
import json
import math
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

try:  # server runs as a package (from repo root) or flat (from server/)
    from server.product_animation_tools import (
        LightingRigPreset,
        ProductMaterialPreset,
        QUALITY_MAP,
        RES_MAP,
        RenderQuality,
        ResolutionPreset,
        _gen_compositor_code,
        _gen_lighting_code,
        _gen_material_code,
        _gen_render_code,
    )
    from server.image_similarity import compare_png_bytes, decode_png_gray
except ModuleNotFoundError:  # pragma: no cover - flat layout fallback
    from product_animation_tools import (  # type: ignore
        LightingRigPreset,
        ProductMaterialPreset,
        QUALITY_MAP,
        RES_MAP,
        RenderQuality,
        ResolutionPreset,
        _gen_compositor_code,
        _gen_lighting_code,
        _gen_material_code,
        _gen_render_code,
    )
    from image_similarity import compare_png_bytes, decode_png_gray  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════════
# INPUT MODEL — the brief
# ═══════════════════════════════════════════════════════════════════════════════

class Viewpoint(str, Enum):
    three_quarter = "three_quarter"  # classic packshot angle
    front = "front"
    side = "side"
    top = "top"
    hero_low = "hero_low"  # slightly below centre, looking up


class BackgroundMode(str, Enum):
    transparent = "transparent"  # alpha background (film_transparent)
    gradient = "gradient"        # gradient world backdrop
    studio = "studio"            # lighting rig's flat world colour


class ProductShotInput(BaseModel):
    """The brief for one packshot. Everything has a sane packshot default;
    only the subject (or an asset to load) is required."""

    subject: Optional[str] = Field(
        default=None,
        description="Name of the object already in the scene to shoot. "
                    "Omit only when asset_path is given (first imported mesh is used).",
    )
    asset_path: Optional[str] = Field(
        default=None,
        description="Optional 3D file (FBX/OBJ/GLB/STL/…) to import before shooting. "
                    "Path is resolved on the Blender host.",
    )

    # Material (presets dissolved from blender_product_material)
    material_preset: Optional[ProductMaterialPreset] = Field(
        default=None, description="Product material preset to apply (skip to keep existing material)")
    color_override: Optional[list] = Field(
        default=None, description="Override material base colour [R,G,B] or [R,G,B,A], 0-1")
    roughness_override: Optional[float] = Field(default=None, ge=0, le=1)
    imperfections: bool = Field(
        default=False, description="Add fingerprint/dust roughness variation for photorealism")

    # Lighting (rig presets dissolved from blender_product_lighting)
    lighting_preset: LightingRigPreset = Field(default=LightingRigPreset.product_studio)
    background: BackgroundMode = Field(default=BackgroundMode.transparent)
    hdri_path: Optional[str] = Field(default=None, description="HDRI on the Blender host (overrides rig world)")
    hdri_strength: float = Field(default=1.5, ge=0)
    shadow_catcher: bool = Field(default=True, description="Add a shadow-catcher ground plane")

    # Framing (dissolved from blender_product_camera, still-frame variant)
    viewpoint: Viewpoint = Field(default=Viewpoint.three_quarter)
    camera_distance: float = Field(default=4.0, gt=0.5, description="Camera distance from subject centre")
    camera_height: float = Field(default=1.2, description="Camera height above subject centre (negative = below)")
    focal_length: float = Field(default=50.0, ge=12, le=300, description="Lens focal length in mm")
    f_stop: float = Field(default=2.8, ge=0.5, le=32)
    use_dof: bool = Field(default=True, description="Depth of field focused on the subject")

    # Render (presets dissolved from blender_product_render_setup)
    quality: RenderQuality = Field(default=RenderQuality.balanced)
    resolution: ResolutionPreset = Field(default=ResolutionPreset.full_hd)
    output_format: str = Field(default="PNG", description="PNG, JPEG, or EXR (golden compare needs PNG)")
    output_path: Optional[str] = Field(
        default=None, description="Where the render is written (Blender host). Default: /tmp/product_shot.png")
    bloom: bool = Field(default=False, description="Compositor bloom/glow (off by default: goldens compare clean renders)")
    vignette: bool = Field(default=False, description="Compositor vignette")

    # Verification — the test half of the contract
    golden_image: Optional[str] = Field(
        default=None,
        description="Reference PNG (readable by the MCP server) to compare the render against. "
                    "Without it the verdict rests on render existence + settings audit only.",
    )
    min_psnr_db: float = Field(default=30.0, ge=0, description="Minimum PSNR (dB) vs golden for a pass")
    min_ssim: float = Field(default=0.90, ge=0, le=1, description="Minimum SSIM vs golden for a pass")

    @model_validator(mode="after")
    def _need_subject_or_asset(self):
        if not self.subject and not self.asset_path:
            raise ValueError("product shot needs a subject (object in scene) or an asset_path to import")
        return self


# Azimuth (degrees around the subject, 0 = +X side) and a height multiplier
# applied to the brief's camera_height, per viewpoint.
_VIEWPOINTS = {
    "three_quarter": {"azimuth_deg": -35.0, "height_scale": 1.0},
    "front": {"azimuth_deg": -90.0, "height_scale": 0.6},
    "side": {"azimuth_deg": 0.0, "height_scale": 0.8},
    "top": {"azimuth_deg": -35.0, "height_scale": 2.2},
    "hero_low": {"azimuth_deg": -35.0, "height_scale": -0.35},
}


# ═══════════════════════════════════════════════════════════════════════════════
# BLENDER-SIDE CODE — static product camera
# (The product_* camera generator only builds ANIMATED rigs; a packshot
#  needs the same rig frozen at frame 1. Same names, so the two tools
#  overwrite each other's rigs cleanly instead of piling up cameras.)
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_static_camera_code(brief: ProductShotInput) -> str:
    vp = _VIEWPOINTS[brief.viewpoint.value]
    azimuth = math.radians(vp["azimuth_deg"])
    height = brief.camera_height * vp["height_scale"]
    dx = brief.camera_distance * math.cos(azimuth)
    dy = brief.camera_distance * math.sin(azimuth)
    target = json.dumps(brief.subject)
    return f"""
import bpy, math
target = bpy.data.objects.get({target})
if not target:
    __result__ = {{"error": "Object '" + {target} + "' not found"}}
else:
    for o in list(bpy.data.objects):
        if o.name == "Product_Camera":
            bpy.data.objects.remove(o, do_unlink=True)
    # Frame the evaluated bounding-box centre, not the object origin —
    # origins are routinely metres away from the visible mesh.
    centre = target.location.copy()
    if hasattr(target, "bound_box") and target.bound_box:
        try:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = target.evaluated_get(dg)
            corners = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
            if corners:
                centre = sum(corners, Vector()) / len(corners)
        except Exception:
            pass
    cd = bpy.data.cameras.new("ProductCamData")
    cd.lens = {brief.focal_length}
    cd.sensor_width = 36
    cd.dof.use_dof = {brief.use_dof}
    cd.dof.focus_object = target
    cd.dof.aperture_fstop = {brief.f_stop}
    co = bpy.data.objects.new("Product_Camera", cd)
    bpy.context.collection.objects.link(co)
    co.location = (centre.x + {dx}, centre.y + {dy}, centre.z + {height})
    tr = co.constraints.new('TRACK_TO')
    tr.target = target
    tr.track_axis = 'TRACK_NEGATIVE_Z'
    tr.up_axis = 'UP_Y'
    scene = bpy.context.scene
    scene.camera = co
    scene.frame_set(1)
    __result__ = {{"status": "ok", "camera": "Product_Camera",
                   "viewpoint": "{brief.viewpoint.value}",
                   "framing_centre": [centre.x, centre.y, centre.z]}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# FAILURE LOG — "failures are data"
# ═══════════════════════════════════════════════════════════════════════════════

def default_failure_log_path() -> str:
    override = os.getenv("BLENDER_PRODUCT_SHOT_FAILURE_LOG")
    if override:
        return override
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(repo_root, "data", "product_shot_failures.jsonl")


def _append_failure_log(path: str, record: Dict[str, Any]) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        return True
    except OSError:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATION — procedure, evidence, verdict
# ═══════════════════════════════════════════════════════════════════════════════

def _step_error(result: Any) -> Optional[str]:
    if isinstance(result, dict) and result.get("error"):
        return str(result["error"])
    return None


def _safe_call(send_command_fn, command: str, params: dict) -> Dict[str, Any]:
    """One bridge call that can never raise: transport exceptions become
    error dicts, so the orchestrator always reaches a verdict (fail-closed)."""
    try:
        resp = send_command_fn(command, params)
    except Exception as exc:  # socket timeout, reset, refused mid-flight…
        return {"error": f"{command} raised {type(exc).__name__}: {exc}"}
    return resp if isinstance(resp, dict) else {"error": f"{command} returned non-dict {type(resp).__name__}"}


def _jsonable_metrics(metrics: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if metrics is None:
        return None
    out = dict(metrics)
    if out.get("psnr_db") == float("inf"):
        out["psnr_db"] = None
        out["identical_to_golden"] = True
    return out


def execute_product_shot(
    send_command_fn,
    brief: ProductShotInput,
    *,
    failure_log_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full product-shot outcome and return the verdict dict.

    send_command_fn(command, params) -> dict is the bridge channel
    (the server's send_command). Every step's response is checked; the
    first hard failure stops the procedure, but the verdict — with what
    is off — is always returned and always logged on failure.
    """
    spec = brief.model_dump(mode="json")
    result: Dict[str, Any] = {
        "outcome": "packshot render matches the brief",
        "tool": "blender_product_shot",
        "spec": spec,
        "steps": {},
        "similarity": None,
        "whats_off": [],
    }

    def fail(reason: str) -> Dict[str, Any]:
        result["whats_off"].append(reason)
        result["verdict"] = "fail"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": "blender_product_shot",
            "verdict": "fail",
            "spec": spec,
            "whats_off": list(result["whats_off"]),
            "similarity": _jsonable_metrics(result.get("similarity")),
            "audit": result.get("audit"),
            "render": result.get("render"),
        }
        result["failure_logged"] = _append_failure_log(
            failure_log_path or default_failure_log_path(), record)
        return result

    # 0. Bridge alive?
    ping = _safe_call(send_command_fn, "ping", {})
    if _step_error(ping):
        result["steps"]["ping"] = {"status": "error"}
        return fail(f"bridge unreachable: {_step_error(ping)}")
    result["steps"]["ping"] = {"status": "ok"}

    # 1. Subject: import first if asked, then confirm it exists.
    if brief.asset_path:
        imported = _safe_call(send_command_fn, "import_file", {"filepath": brief.asset_path})
        if _step_error(imported):
            result["steps"]["import"] = {"status": "error"}
            return fail(f"asset import failed: {_step_error(imported)}")
        result["steps"]["import"] = {"status": "ok", "result": imported}

    scene = _safe_call(send_command_fn, "get_scene_info", {})
    if _step_error(scene):
        result["steps"]["get_scene_info"] = {"status": "error"}
        return fail(f"could not read scene: {_step_error(scene)}")
    objects = [o for o in scene.get("objects", []) if isinstance(o, dict)]
    names = {str(o.get("name")) for o in objects}

    subject = brief.subject
    if subject is None:
        meshes = [str(o["name"]) for o in objects
                  if o.get("type") == "MESH" and o.get("name")]
        if not meshes:
            return fail("asset imported but no mesh object appeared in the scene")
        subject = meshes[-1]
        result["subject_resolved"] = subject
    if subject not in names:
        return fail(
            f"subject '{subject}' is not in the scene "
            f"(scene has: {', '.join(sorted(names)[:12]) or 'nothing'})")
    result["subject"] = subject
    result["steps"]["subject"] = {"status": "ok"}
    # The generators address objects by name; pin the resolved name, and
    # re-dump the spec so verdicts/logs record what was actually shot.
    brief = brief.model_copy(update={"subject": subject})
    spec = brief.model_dump(mode="json")
    result["spec"] = spec

    def run_step(name: str, command: str, params: dict) -> Optional[Dict[str, Any]]:
        """Run one procedure step. Returns the bridge result on success;
        on error, records the failure verdict and returns None."""
        resp = _safe_call(send_command_fn, command, params)
        err = _step_error(resp)
        if err:
            result["steps"][name] = {"status": "error"}
            fail(f"{name} step failed: {err}")
            return None
        result["steps"][name] = {"status": "ok", "result": resp}
        return resp

    # 2. Material → 3. Lighting → 4. Camera → 5. Render settings (+compositor)
    if brief.material_preset is not None:
        code = _gen_material_code(
            brief.material_preset.value, subject,
            color_override=brief.color_override,
            roughness_override=brief.roughness_override,
            add_imperfections=brief.imperfections,
        )
        if run_step("material", "execute_python", {"code": code}) is None:
            return result

    gradient = brief.background is BackgroundMode.gradient
    code = _gen_lighting_code(
        brief.lighting_preset.value, brief.shadow_catcher, gradient,
        hdri_path=brief.hdri_path, hdri_strength=brief.hdri_strength,
    )
    if run_step("lighting", "execute_python", {"code": code}) is None:
        return result

    if run_step("camera", "execute_python",
                {"code": _gen_static_camera_code(brief)}) is None:
        return result

    output_path = brief.output_path or "/tmp/product_shot.png"
    code = _gen_render_code(
        brief.quality.value, brief.resolution.value,
        brief.background is BackgroundMode.transparent,
        output_path, brief.output_format,
    )
    if run_step("render_settings", "execute_python", {"code": code}) is None:
        return result
    if run_step("compositor", "execute_python",
                {"code": _gen_compositor_code(brief.bloom, brief.vignette)}) is None:
        return result

    # 6. Render the still.
    render = run_step("render", "render",
                      {"type": "image", "output_path": output_path})
    if render is None:
        return result
    result["render"] = {
        "path": render.get("output_path", output_path),
        "resolution": render.get("resolution"),
        "engine": render.get("engine"),
    }

    # 7. Settings audit (the repo's existing gate).
    audit = _safe_call(send_command_fn, "render_quality_audit", {
        "profile": "cinema",
        "strict": False,
        "min_samples": QUALITY_MAP[brief.quality.value]["samples"],
        "require_exr": False,        # a PNG packshot is a legitimate spec
        "require_motion_blur": False,  # still frame
        "require_dof": brief.use_dof,
        "require_compositor": brief.bloom or brief.vignette,
    })
    if _step_error(audit):
        result["steps"]["render_quality_audit"] = {"status": "error"}
        return fail(f"render_quality_audit failed: {_step_error(audit)}")
    summary = audit.get("summary", {}) if isinstance(audit, dict) else {}
    failed_checks = [c.get("id") for c in audit.get("checks", [])
                     if isinstance(c, dict) and c.get("status") == "fail"]
    warn_checks = [c.get("id") for c in audit.get("checks", [])
                   if isinstance(c, dict) and c.get("status") == "warn"]
    result["audit"] = {
        "score": summary.get("score"),
        "passed": summary.get("passed"),
        "warnings": summary.get("warnings"),
        "failed": summary.get("failed"),
        "failed_checks": failed_checks,
        "warning_checks": warn_checks,
    }
    result["steps"]["render_quality_audit"] = {"status": "ok"}
    if failed_checks:
        return fail(f"render audit failed checks: {', '.join(failed_checks)}")
    if warn_checks:
        result["whats_off"].append(
            f"advisory audit warnings (not failing): {', '.join(warn_checks)}")

    # 8. Pixel evidence + golden compare (the test).
    render_bytes, evidence_source = _acquire_render_pixels(
        send_command_fn, result["render"], brief)
    result["evidence"] = {"pixels_source": evidence_source}

    if brief.golden_image:
        if render_bytes is None:
            return fail(
                "no render pixels available to compare against the golden "
                "(render file not on this host and viewport capture returned none)")
        try:
            with open(brief.golden_image, "rb") as fh:
                golden_bytes = fh.read()
        except OSError as exc:
            return fail(f"golden image unreadable: {exc}")
        try:
            metrics = compare_png_bytes(render_bytes, golden_bytes)
        except ValueError as exc:
            return fail(f"image comparison failed: {exc}")
        result["similarity"] = _jsonable_metrics(metrics)
        shortfalls = []
        psnr = metrics["psnr_db"]
        if psnr != float("inf") and psnr < brief.min_psnr_db:
            shortfalls.append(f"PSNR {psnr:.2f} dB < required {brief.min_psnr_db} dB")
        if metrics["ssim"] < brief.min_ssim:
            shortfalls.append(f"SSIM {metrics['ssim']:.4f} < required {brief.min_ssim}")
        if metrics.get("golden_resampled"):
            result["whats_off"].append(
                f"golden size {metrics['golden_size']} != render size "
                f"{metrics['render_size']}; golden was resampled for comparison")
        if shortfalls:
            return fail("render does not match golden: " + "; ".join(shortfalls))
        result["basis"] = ["render produced", "render audit clean",
                           "golden-image PSNR/SSIM above thresholds"]
    else:
        result["basis"] = [
            "render produced", "render audit clean",
            "no golden supplied — visual match itself is unverified; "
            "supply golden_image to close that leg",
        ]
        if render_bytes is not None:
            try:
                w, h, gray = decode_png_gray(render_bytes)
                result["evidence"]["dimensions"] = [w, h]
                if gray:
                    mean = sum(gray) / len(gray)
                    var = sum((v - mean) ** 2 for v in gray) / len(gray)
                    if var ** 0.5 < 0.002:
                        result["whats_off"].append(
                            "advisory: render is one flat colour — subject "
                            "missing, unlit, or out of frame (not failing: "
                            "a white-on-white shot is legitimate)")
            except ValueError:
                pass

    result["verdict"] = "pass"
    result["metric"] = {
        "first_try": True,
        "note": "Track brief-match rate by aggregating verdicts; "
                "every failure is in the failure log with its spec.",
    }
    return result


def _acquire_render_pixels(send_command_fn, render_info, brief):
    """Get the rendered pixels as bytes, wherever Blender actually is.

    Preferred: the file the render wrote, when this host can read it
    (the usual single-host setup). Fallback: a full engine re-render
    through viewport_capture, which returns base64 from any host.
    Returns (bytes|None, source label).
    """
    path = (render_info or {}).get("path")
    if path and brief.output_format.upper() == "PNG" and os.path.isfile(path):
        try:
            with open(path, "rb") as fh:
                return fh.read(), "render_file"
        except OSError:
            pass
    res_w, res_h = RES_MAP[brief.resolution.value]
    capture = _safe_call(send_command_fn, "viewport_capture", {
        "mode": "full_render",
        "use_scene_camera": True,
        "base64": True,
        "width": res_w,
        "height": res_h,
    })
    if isinstance(capture, dict) and capture.get("base64"):
        try:
            return base64.b64decode(capture["base64"]), "viewport_capture"
        except (ValueError, TypeError):
            return None, "none"
    return None, "none"


# ═══════════════════════════════════════════════════════════════════════════════
# MCP REGISTRATION
# ═══════════════════════════════════════════════════════════════════════════════

def register_product_shot_tools(mcp_instance, send_command_fn, format_result_fn):
    """Register blender_product_shot. Same registrar shape as the
    product tools, so blender_mcp_server can wire it via _try_register."""

    @mcp_instance.tool(
        name="blender_product_shot",
        annotations={"title": "Product Shot (verified outcome)", "readOnlyHint": False,
                     "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    )
    async def blender_product_shot(params: ProductShotInput) -> str:
        """Produce ONE verified packshot still of a product, in one call.

        Runs material → lighting → camera → render settings → compositor →
        render via the product preset machinery, then verifies the result:
        the repo's render-quality audit must pass, and when you supply a
        golden_image the render must clear your PSNR/SSIM thresholds.

        Returns a verdict, never a bare success: {verdict, render path,
        audit summary, similarity metrics, what's off}. Failed verdicts
        are appended to data/product_shot_failures.jsonl.

        Use this instead of the six product_* step tools when the job is
        "a packshot of X". Use blender_product_animation for turntables
        and other moving shots. Note: the lighting step replaces all
        existing lights (rig presets own the stage), and the bridge must
        allow execute_python (OPENCLAW_ALLOW_EXEC=1), same as the
        existing product tools.

        Example: subject="Bottle", material_preset="clear_glass",
          lighting_preset="cosmetics", golden_image="/path/to/approved.png"
        """
        verdict = execute_product_shot(send_command_fn, params)
        return format_result_fn(verdict)

    return ["blender_product_shot"]
