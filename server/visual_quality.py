"""Deterministic visual-quality checks for Blender agent workflows.

This is deliberately model-independent: it turns scene/render evidence into a
stable quality report that an LLM can reason over without pretending that the
mere existence of pixels means the result is good.
"""
from __future__ import annotations

from typing import Any


def _payload(result: Any) -> dict:
    if not isinstance(result, dict):
        return {}
    data = result.get("data", result)
    return data if isinstance(data, dict) else {}


def _objects(scene: Any) -> list[dict]:
    rows = _payload(scene).get("objects") or []
    return [row for row in rows if isinstance(row, dict)]


def critique_visual_evidence(
    *,
    scene: Any,
    viewport: Any,
    workflow: str | None = None,
    target_object: str | None = None,
) -> dict:
    """Return deterministic quality findings and an actionable revision plan.

    This does not claim aesthetic understanding. It verifies objective scene
    prerequisites and whether actual pixels were returned, then leaves semantic
    image judgement to the model/client that can see those pixels.
    """
    payload = _payload(viewport)
    pixels = next(
        (payload.get(key) for key in ("base64", "image", "image_base64")
         if isinstance(payload.get(key), str) and payload.get(key).strip()),
        None,
    )
    objects = _objects(scene)
    names = {str(row.get("name")) for row in objects if row.get("name")}
    types = [str(row.get("type") or "").upper() for row in objects]
    findings: list[dict] = []

    def add(code: str, severity: str, message: str, fix: str) -> None:
        findings.append({"code": code, "severity": severity, "message": message, "recommended_fix": fix})

    if not pixels:
        add("NO_PIXELS", "error", "No model-visible pixel payload was returned.", "Capture viewport pixels with base64=true before accepting visual quality.")
    if not objects:
        add("EMPTY_SCENE", "error", "Scene contains no inspectable objects.", "Inspect or rebuild the scene before visual review.")
    if target_object and target_object not in names:
        add("TARGET_MISSING", "error", f"Target object '{target_object}' is absent from the scene.", "Resolve the canonical object name before camera/material/render work.")
    if workflow in {"workflow.product_hero", "workflow.amazon_packshot", "workflow.turntable"}:
        if "CAMERA" not in types:
            add("NO_CAMERA", "error", "Product workflow has no camera object.", "Create and aim a product camera at the target.")
        if "LIGHT" not in types:
            add("NO_LIGHTS", "error", "Product workflow has no light objects.", "Create a studio key/fill/rim lighting setup.")
        if target_object and target_object in names and len(objects) < 3:
            add("UNDERBUILT_STAGE", "warning", "Product stage has very little supporting scene structure.", "Inspect lighting, camera, background and shadow-catching support before final render.")
    if workflow == "workflow.amazon_packshot":
        add("AMAZON_SEMANTIC_REVIEW", "review", "Pixel evidence still requires semantic review for product framing, background cleanliness, legibility and unwanted props.", "Inspect the returned pixels before accepting the listing image.")
    elif workflow in {"workflow.product_hero", "workflow.turntable"}:
        add("AESTHETIC_REVIEW", "review", "Objective prerequisites pass only part of the quality bar.", "Inspect the returned pixels for composition, highlight shape, material readability, clipping and visual hierarchy.")

    blocking = [row for row in findings if row["severity"] == "error"]
    reviews = [row for row in findings if row["severity"] == "review"]
    score = max(0, 100 - 30 * len(blocking) - 10 * len([r for r in findings if r["severity"] == "warning"]))
    return {
        "status": "fail" if blocking else "review_required" if reviews else "pass",
        "objective_score": score,
        "pixel_evidence": bool(pixels),
        "findings": findings,
        "revision_plan": [row["recommended_fix"] for row in findings if row["severity"] in {"error", "warning", "review"}],
        "note": "Objective score is deterministic scene/evidence validation, not an aesthetic model score.",
    }
